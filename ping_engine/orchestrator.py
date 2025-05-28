"""
PingOrchestrator
================
Cérebro assíncrono da engine de ping.

▶ Recursos principais
• Distribui pings via scheduler.distribute_pings().
• Watchdog reinicia loops travados.
• Pipeline completo: analytics → fallback TCP → persistência.
• NOVO: suporte a **Pausar / Retomar** ping por servidor.

Marcas de alteração:
    # >>> PAUSE-RESUME (início) ......  linha adicionada/modificada
    # <<< PAUSE-RESUME (fim) .........  linha adicionada/modificada
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import time
from datetime import datetime
from typing import Dict, List, Any

import grpc

from ping_engine import analytics, database_access, scheduler
from ping_engine.controller import test_multiple_ports
from ping_engine.go.infraview.pingservice import (
    pingservice_pb2,
    pingservice_pb2_grpc,
)

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# CONSTANTES WATCHDOG
# ────────────────────────────────────────────────────────────────────
_WATCHDOG_TICK = 2           # intervalo de verificação (s)
_WATCHDOG_MIN_TIMEOUT = 15   # timeout mínimo (s) para considerar travado
_FALLBACK_PORTS = [22, 80, 443, 3389]

# ────────────────────────────────────────────────────────────────────
# CLASSE PRINCIPAL
# ────────────────────────────────────────────────────────────────────
class PingOrchestrator:
    def __init__(self, address: str = "localhost:50051"):
        self.address = address
        self.channel = grpc.aio.insecure_channel(self.address)
        self.stub: pingservice_pb2_grpc.PingServiceStub | None = None

        self.status_callbacks: List = []       # corrotinas a serem notificadas
        self.stream_task: asyncio.Task | None = None
        self.watchdog_task: asyncio.Task | None = None

        # Perfis de cada IP
        self.profiles: Dict[str, Dict[str, Any]] = {}

        self.ready: bool = False               # conexão gRPC estabelecida

    # ───────────────────────────── CONEXÃO gRPC ─────────────────────────────
    async def connect(self) -> None:
        """Estabelece stub gRPC (não bloqueia se falhar – lança exceção)."""
        try:
            self.stub = pingservice_pb2_grpc.PingServiceStub(
                await self.channel.__aenter__()
            )
            logger.info("Conectado ao serviço gRPC em %s", self.address)
            self.ready = True
        except Exception as e:
            logger.error("Erro ao conectar gRPC: %s", e)
            self.ready = False
            raise

    async def wait_until_ready(self):
        """Bloqueia até o stub gRPC estar pronto (útil na inicialização)."""
        while not self.ready:
            await asyncio.sleep(0.1)

    async def close(self):
        """Fecha o canal gRPC (encerramento gracioso)."""
        await self.channel.__aexit__(None, None, None)

    # ───────────────────────────── CRUD DE SERVIDORES ──────────────────────
    async def add_server(self, ip: str) -> bool:
        if self.stub is None:
            raise RuntimeError("Stub gRPC não inicializado")
        ack = await self.stub.AddServer(pingservice_pb2.AddRequest(ip=ip))
        if ack.success and ip not in self.profiles:
            self.profiles[ip] = self._init_profile(ip)
        return ack.success

    async def remove_server(self, ip: str) -> bool:
        if self.stub is None:
            raise RuntimeError("Stub gRPC não inicializado")
        ack = await self.stub.RemoveServer(pingservice_pb2.RemoveRequest(ip=ip))
        self.profiles.pop(ip, None)
        return ack.success

    # >>> PAUSE-RESUME (início)
    # ----------------------------------------------------------------------
    #  NOVOS MÉTODOS para pausar e retomar o ping de um servidor
    # ----------------------------------------------------------------------
    async def pause_server(self, ip: str) -> bool:
        """
        Suspende temporariamente o ping do IP.

        1. Chama RPC gRPC PauseServer.
        2. Marca profile['paused']=True e status='pausado'.
        3. Persiste no banco via database_access.
        """
        if self.stub is None:
            raise RuntimeError("Stub gRPC não inicializado")
        ack = await self.stub.PauseServer(pingservice_pb2.PauseRequest(ip=ip))
        if ack.success:
            profile = self.profiles.get(ip) or self._init_profile(ip)
            profile["paused"] = True
            profile["status"] = "pausado"
            self.profiles[ip] = profile
            database_access.save_ip_profile(ip, profile)
        return ack.success

    async def resume_server(self, ip: str) -> bool:
        """
        Retoma o ping do IP previamente pausado.

        1. Chama RPC gRPC ResumeServer.
        2. Remove flag 'paused' e restaura status anterior (ou 'observação').
        3. Persiste no banco via database_access.
        """
        if self.stub is None:
            raise RuntimeError("Stub gRPC não inicializado")
        ack = await self.stub.ResumeServer(pingservice_pb2.ResumeRequest(ip=ip))
        if ack.success:
            profile = self.profiles.get(ip) or self._init_profile(ip)
            profile["paused"] = False
            if profile.get("last_status"):
                profile["status"] = profile["last_status"]
            else:
                profile["status"] = "observação"
            self.profiles[ip] = profile
            database_access.save_ip_profile(ip, profile)
        return ack.success
    # <<< PAUSE-RESUME (fim)

    async def reload_servers(self, ip_list: List[Dict[str, str]]) -> None:
        """Remove e adiciona novamente todos os IPs informados (hot-reload)."""
        for item in ip_list:
            await self.remove_server(item["ip"])
            await self.add_server(item["ip"])
        logger.info("[ORCHESTRATOR] reload_servers concluído")
        await self.stream_status([it["ip"] for it in ip_list])

    # ─────────────────────── PERFIS PERSISTENTES (DB) ──────────────────────
    def refresh_profiles_from_db(self):
        """Cria tabelas (se necessário) e carrega perfis salvos."""
        database_access.create_tables()
        self.profiles = database_access.load_all_ip_profiles() or {}

    # ───────────────────────── CALLBACKS PARA GUI ──────────────────────────
    def add_status_callback(self, coro) -> None:
        """Registra corrotina callback para receber updates processados."""
        self.status_callbacks.append(coro)

    # ────────────────────────── LOOP DE STREAM gRPC ────────────────────────
    async def _stream_loop(self, _placeholder):
        """Abre StreamStatus, processa updates e repassa aos callbacks."""
        if self.stub is None:
            logger.error("stream_status: stub não conectado")
            return

        while True:
            # >>> PAUSE-RESUME (início)
            # Descartar IPs pausados antes do agendamento extra de segurança
            active_profiles = {
                ip: prof for ip, prof in self.profiles.items()
                if not prof.get("paused")
            }
            ips_to_ping = scheduler.distribute_pings(active_profiles)
            # <<< PAUSE-RESUME (fim)

            if not ips_to_ping:
                await asyncio.sleep(0.5)
                continue

            req = pingservice_pb2.StatusRequest(ips=ips_to_ping)
            stream = self.stub.StreamStatus(req)
            logger.debug("PingLoop escalonado para: %s", ips_to_ping)

            async for upd in stream:
                upd_dict = {
                    upd.ip: {
                        "ip": upd.ip,
                        "latency": upd.latency,
                        "online": upd.online,
                        "status": upd.status,
                        "timestamp": upd.timestamp,
                    }
                }

                try:
                    processed = await self.process_update(upd_dict)
                except Exception as e:
                    logger.error("Erro no pipeline IP %s: %s", upd.ip, e)
                    logger.debug(traceback.format_exc())
                    continue

                for cb in self.status_callbacks:
                    await cb(processed)

            await asyncio.sleep(0.5)           # evita tight-loop no EOF

    async def stream_status(self, ip_list):
        """(Re)inicia o stream e garante watchdog ativo."""
        if self.stream_task:
            self.stream_task.cancel()
            await asyncio.sleep(0.1)

        self.stream_task = asyncio.create_task(self._stream_loop(ip_list))

        if self.watchdog_task is None or self.watchdog_task.done():
            self.watchdog_task = asyncio.create_task(self._watchdog_loop())

    async def restart_stream(self):
        """Busca IPs do banco e reinicia stream_status (ex.: após add)."""
        from core.database import get_all_servers
        ips = [row[1] for row in get_all_servers()]
        await self.stream_status(ips)

    # ───────────────────────────── WATCHDOG LOOP ───────────────────────────
    async def _watchdog_loop(self):
        """Verifica periodicamente se algum worker parou de enviar updates."""
        while True:
            await asyncio.sleep(_WATCHDOG_TICK)
            now = time.time()

            for ip, profile in list(self.profiles.items()):
                if profile.get("paused"):      # >>> PAUSE-RESUME
                    continue                   # ignora pausados
                last_seen_iso = profile.get("last_seen")
                if not last_seen_iso:
                    continue
                try:
                    last_seen_ts = datetime.fromisoformat(last_seen_iso).timestamp()
                except Exception:
                    continue

                interval = profile.get("ping_interval", 10)
                timeout = max(_WATCHDOG_MIN_TIMEOUT, interval * 2 + 5)

                if now - last_seen_ts > timeout:
                    if profile.get("wd_flag"):
                        # segunda verificação → reinicia pingLoop
                        logger.warning("Watchdog reinicia %s", ip)
                        database_access.save_engine_event(
                            ip,
                            "alerta",
                            "watchdog: reiniciar pingLoop",
                            profile,
                        )
                        try:
                            await self.remove_server(ip)
                            await self.add_server(ip)
                            profile.pop("wd_flag", None)
                        except Exception as e:
                            logger.error("Falha watchdog %s: %s", ip, e)
                    else:
                        # primeira detecção
                        profile["wd_flag"] = True
                        profile["status"] = "sem_resposta"
                        database_access.save_engine_event(
                            ip,
                            "alerta",
                            "watchdog: sem resposta de pingLoop",
                            profile,
                        )
                        logger.warning(
                            "Watchdog flag %s (%.1fs sem update)",
                            ip,
                            now - last_seen_ts,
                        )

    # ───────────────────────────── LÓGICA CENTRAL ──────────────────────────
    def _init_profile(self, ip: str) -> Dict[str, Any]:
        """Perfil padrão de um IP recém-adicionado."""
        return {
            "ip": ip,
            "status": "observação",
            "history": [],
            "latency_avg": None,
            "latency_std": None,
            "last_seen": None,
            "stable_count": 0,
            "preferred_method": "icmp",
            "ping_interval": 10,
            "failures": [],
            "alerts": [],
            "ultimos_alertas": {},
            "paused": False,            # >>> PAUSE-RESUME
        }

    async def process_update(self, update_data: Dict[str, Dict[str, Any]]):
        """Pipeline completo para um(s) update(s) recebido(s)."""
        for ip, data in update_data.items():
            profile = self.profiles.get(ip) or self._init_profile(ip)
            self.profiles[ip] = profile

            # Se estiver pausado, ignorar (não deveria chegar aqui, mas seguro)
            if profile.get("paused"):          # >>> PAUSE-RESUME
                continue

            # --- histórico (máx 300 amostras em memória) ----------------
            profile["history"].append(
                {
                    "latency": data["latency"],
                    "online": data["online"],
                    "timestamp": data["timestamp"],
                }
            )
            profile["history"] = profile["history"][-300:]

            # --- analytics / classificação --------------------------------
            try:
                profile["status"] = analytics.analyze_ping(data)
            except Exception as e:
                logger.error("analytics %s: %s", ip, e)
                profile["status"] = "erro_analise"

            # --- fallback TCP (ICMP→TCP) ----------------------------------
            if (
                profile.get("last_status") == "estável"
                and profile["status"] in {"offline", "instável"}
                and not profile.get("fallback_checked")
            ):
                tcp_ok = await test_multiple_ports(ip, _FALLBACK_PORTS)
                if tcp_ok:
                    profile["status"] = "online_tcp"
                    profile["preferred_method"] = "tcp"
                    profile["alerts"].append("ICMP bloqueado; TCP responde")
                    database_access.save_engine_event(
                        ip, "alerta", "ICMP bloqueado, TCP responde", profile
                    )
                else:
                    profile["status"] = "crítico"
                    profile["alerts"].append("Sem resposta ICMP/TCP — crítico")
                    database_access.save_engine_event(
                        ip,
                        "crítico",
                        "Sem resposta ICMP/TCP",
                        profile,
                    )
                    profile["ping_interval"] = max(2, profile["ping_interval"] // 2)
                    profile["fallback_start_time"] = time.time()
                profile["fallback_checked"] = True

            # remove fallback após 5 min
            if profile.get("fallback_start_time") and time.time() - profile["fallback_start_time"] > 300:
                profile.pop("fallback_start_time", None)
                profile.pop("fallback_checked", None)
                profile["ping_interval"] = scheduler.get_ping_interval(profile["status"])

            # --- métricas básicas -----------------------------------------
            latencies = [h["latency"] for h in profile["history"] if h["latency"] is not None]
            if latencies:
                profile["latency_avg"] = sum(latencies) / len(latencies)
                if len(latencies) > 2:
                    mean = profile["latency_avg"]
                    profile["latency_std"] = (
                        sum((l - mean) ** 2 for l in latencies) / (len(latencies) - 1)
                    ) ** 0.5
                else:
                    profile["latency_std"] = 0
            else:
                profile["latency_avg"] = profile["latency_std"] = None

            profile["last_seen"] = data["timestamp"]

            # --- persistência (fila assíncrona via database_access) -------
            database_access.save_ping_result(
                {
                    "ip": ip,
                    "latency": data["latency"],
                    "online": data["online"],
                    "status": profile["status"],
                    "timestamp": data["timestamp"],
                }
            )
            database_access.save_ip_profile(ip, profile)

            # --- resposta para GUI ----------------------------------------
            update_data[ip]["profile"] = profile
            update_data[ip]["message"] = self._status_message(profile)
            profile["last_status"] = profile["status"]

        return update_data

    # ------------------------------------------------------------------
    def _status_message(self, profile: Dict[str, Any]) -> str:
        status = profile["status"]
        return {
            "estável": "Servidor responde normalmente.",
            "flutuante": "Variação de latência detectada.",
            "instável": "Conexão intermitente.",
            "offline": "Servidor offline.",
            "risco crescente": "Latência subindo — atenção.",
            "crítico": "Sem resposta ICMP/TCP.",
            "online_tcp": "Responde apenas TCP (ICMP bloqueado).",
            "sem_resposta": "Worker não envia dados — watchdog atento.",
            "pausado": "Monitoramento pausado pelo usuário.",   # >>> PAUSE-RESUME
        }.get(status, f"Status: {status}")
