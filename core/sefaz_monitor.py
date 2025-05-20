"""
core/sefaz_monitor.py
---------------------
Serviço assíncrono para monitorar o status da SEFAZ (NFe/NFCe).

• Loop 1-1-2-1-1 min (repete).
• Persistência: tabela sefaz_status (core.database.insert_sefaz_status).
• GUI: callback on_update(payload) — disparado a cada ciclo (OK ou erro).
• Log dedicado: core/sefaz_monitor.log (rotativo, não vai p/ terminal).
"""
from __future__ import annotations

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from lxml import etree
from pynfe.processamento.comunicacao import ComunicacaoSefaz
from pynfe.utils.flags import NAMESPACE_NFE

from core.database import insert_sefaz_status

# ----------------------------------------------------------------------
# Logger exclusivo
# ----------------------------------------------------------------------
_LOG_PATH = Path(__file__).with_name("sefaz_monitor.log")
_HANDLER = RotatingFileHandler(
    _LOG_PATH, maxBytes=200_000, backupCount=5, encoding="utf-8"
)
_HANDLER.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

_logger = logging.getLogger("sefaz_monitor")
_logger.setLevel(logging.DEBUG)          # mude p/ INFO se quiser menos verboso
_logger.addHandler(_HANDLER)
_logger.propagate = False                # não polui o terminal

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
@dataclass(slots=True)
class SefazConfig:
    uf: str
    certificado_path: str
    certificado_senha: str
    doc_type: str = "nfe"     # "nfe" ou "nfce"
    homologacao: bool = True  # True = ambiente de testes


# ----------------------------------------------------------------------
# Serviço assíncrono
# ----------------------------------------------------------------------
class SefazMonitor:
    _INTERVAL_PATTERN = (60, 60, 120, 60, 60)  # 1,1,2,1,1 min → segundos

    def __init__(
        self,
        cfg: SefazConfig,
        on_update: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.cfg = cfg
        self.on_update = on_update
        self._stop_evt = asyncio.Event()

        if not Path(cfg.certificado_path).exists():
            raise FileNotFoundError(f"Certificado não encontrado: {cfg.certificado_path}")

    # -------------------- API pública -------------------- #
    async def start(self) -> None:
        _logger.info("Monitor iniciado (UF=%s, doc=%s)", self.cfg.uf.upper(), self.cfg.doc_type)
        idx = 0
        pat_len = len(self._INTERVAL_PATTERN)

        while not self._stop_evt.is_set():
            next_interval = self._INTERVAL_PATTERN[idx]
            _logger.debug("⟳ ciclo %s — next_interval=%ss", idx, next_interval)

            await self._check_once(next_interval)

            # espera até próximo ciclo ou stop
            try:
                await asyncio.wait_for(self._stop_evt.wait(), timeout=next_interval)
            except asyncio.TimeoutError:
                pass
            _logger.debug("⤺ fim sleep — stop_evt=%s", self._stop_evt.is_set())

            idx = (idx + 1) % pat_len

        _logger.info("Monitor finalizado.")

    def stop(self) -> None:
        self._stop_evt.set()

    # -------------------- Lógica interna -------------------- #
    async def _check_once(self, next_interval: int) -> None:
        """
        Consulta a SEFAZ. Sempre envia payload (sucesso ou erro) para a GUI.
        """
        payload = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "next_in": next_interval,
            "status": "ERR",
            "motivo": "Falha na consulta",
        }

        try:
            _logger.debug("Iniciando consulta SEFAZ…")
            con = ComunicacaoSefaz(
                self.cfg.uf,
                self.cfg.certificado_path,
                self.cfg.certificado_senha,
                self.cfg.homologacao,
            )

            xml_resp = con.status_servico(self.cfg.doc_type)
            payload.update(self._parse_xml(xml_resp.content))  # status/motivo ok

            insert_sefaz_status(self.cfg.doc_type, payload["status"], payload["motivo"])
            _logger.info("%s – %s", payload["status"], payload["motivo"])

        except Exception as exc:  # noqa: BLE001
            payload["motivo"] = f"Erro: {type(exc).__name__}"
            _logger.exception("Erro ao consultar SEFAZ", exc_info=exc)

        # envia p/ GUI (thread-safe via sinal)
        if self.on_update:
            self.on_update(payload)

    # -------------------- Helpers -------------------- #
    @staticmethod
    def _parse_xml(raw_xml: bytes) -> dict:
        root = etree.fromstring(raw_xml)[0][0]
        ns = {"ns": NAMESPACE_NFE}

        status = root.xpath("ns:retConsStatServ/ns:cStat", namespaces=ns)[0].text
        motivo = root.xpath("ns:retConsStatServ/ns:xMotivo", namespaces=ns)[0].text

        return {"status": status, "motivo": motivo}
