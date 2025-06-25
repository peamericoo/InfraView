# ping_engine/interface.py
"""
Engine ↔ GUI bridge (versão com correções)
──────────────────────────────────────────
Correções nesta revisão:
1. **Barreira de inicialização** – `_loop_ready` (threading.Event) garante
   que chamadas públicas (`add_server`, etc.) só sejam despachadas após o
   loop e o orchestrator estarem prontos.
2. **Consulta ao DB em thread pool** – dentro do worker, a verificação de
   servidores existentes (`list_servers`) roda em `run_in_executor`, evitando
   bloqueio do loop.
"""

from __future__ import annotations

import asyncio
import threading
import logging
from typing import Dict, Tuple, Any

from ping_engine.orchestrator import PingOrchestrator
from ping_engine import database_access, analytics, scheduler, cache
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAIS
# ─────────────────────────────────────────────────────────────────────────────
_loop: asyncio.AbstractEventLoop | None = None
_orchestrator: PingOrchestrator | None = None
_callback = None                           # função da GUI que recebe snapshot
_ping_snapshot: Dict[str, Dict[str, Any]] = {}

# Fila de processamento assíncrono
_QUEUE_MAXSIZE = 1000
_WORKER_COUNT = 4
_proc_queue: asyncio.Queue[Tuple[str, Dict[str, Any]]] | None = None

# Barrier de prontidão
_loop_ready = threading.Event()

# ─────────────────────────────────────────────────────────────────────────────
# LOOP & BOOTSTRAP
# ─────────────────────────────────────────────────────────────────────────────

def _run_async_loop():
    """Cria o loop asyncio dedicado à engine Go + workers."""
    global _loop, _orchestrator, _proc_queue

    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    _proc_queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)

    _orchestrator = PingOrchestrator()
    _orchestrator.loop = _loop

    async def main_async():
        await _start_engine()
        _loop_ready.set()  # sinaliza que o loop/orchestrator estão prontos
        await asyncio.Event().wait()  # mantém vivo

    _loop.run_until_complete(main_async())


def start_engine(callback):
    """Iniciado pela GUI — spawna thread com loop asyncio dedicado."""
    global _callback
    _callback = callback
    threading.Thread(target=_run_async_loop, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# ENGINE STARTUP
# ─────────────────────────────────────────────────────────────────────────────

async def _start_engine():
    """Conecta ao orchestrator, cria workers e recupera IPs do DB."""
    await _orchestrator.connect()

    database_access.create_tables()
    _orchestrator.add_status_callback(_handle_status)

    # Workers
    for i in range(_WORKER_COUNT):
        _loop.create_task(_worker_loop(), name=f"worker-{i}")

    # ------------------------------------------------------------------
    # IPs salvos no banco — agora respeitando status 'paused'
    # ------------------------------------------------------------------
    from core.database import get_all_servers

    ips: list[str] = []
    for name, ip, status, *_ in get_all_servers():        # ← capturamos STATUS
        await _orchestrator.add_server(ip)

        # >>> PAUSE-BOOT (início)
        if status == "paused":
            # Mantém perfil em memória e envia RPC PauseServer
            await _orchestrator.pause_server(ip)
        # <<< PAUSE-BOOT (fim)

        ips.append(ip)

    await _orchestrator.stream_status(ips)

# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK → FILA  (NÃO BLOQUEANTE)
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_status(update_dict: Dict[str, Dict[str, Any]]):
    for ip, data in update_dict.items():
        try:
            _proc_queue.put_nowait((ip, data))
        except asyncio.QueueFull:
            logger.warning("Fila de processamento cheia – descartando %s", ip)

# ─────────────────────────────────────────────────────────────────────────────
# WORKERS  (CONSOMEM A FILA)
# ─────────────────────────────────────────────────────────────────────────────

async def _worker_loop():
    while True:
        ip, data = await _proc_queue.get()
        try:
            status = await _loop.run_in_executor(None, analytics.analyze_ping, data)
            data["status"] = status
            await _loop.run_in_executor(None, database_access.save_ping_result, data)

            cache.update(ip, data["status"], data["latency"])
            _ping_snapshot[ip] = data

            # Verifica se IP ainda existe (execução em thread pool para evitar bloqueio)
            servers_set = await _loop.run_in_executor(None, list_servers)
            if ip not in servers_set:
                _ping_snapshot.pop(ip, None)

            if _callback:
                _callback(_ping_snapshot.copy())

        except Exception as exc:
            logger.error("worker processando %s: %s", ip, exc)
        finally:
            _proc_queue.task_done()

# ─────────────────────────────────────────────────────────────────────────────
# WRAPPERS PÚBLICOS USADOS PELA GUI
# ─────────────────────────────────────────────────────────────────────────────

def _wait_until_ready(timeout=5):
    if not _loop_ready.wait(timeout):
        raise RuntimeError("Engine loop não inicializado em tempo hábil")


def add_server(ip: str):
    """Solicita ao orchestrator a inclusão de um IP para monitoramento."""
    _wait_until_ready()
    asyncio.run_coroutine_threadsafe(_orchestrator.add_server(ip), _loop)


def remove_server(ip: str):
    """Remove o IP do monitoramento em execução."""
    _wait_until_ready()
    asyncio.run_coroutine_threadsafe(_orchestrator.remove_server(ip), _loop)


def get_server_status(ip: str):
    """Retorna o snapshot de status armazenado em cache para o IP."""
    return {
        "status": cache.get_status(ip),
        "latency": cache.get_latency(ip),
        "last_ping": cache.get_last_ping_time(ip),
    }


def list_servers():
    """Lista todos os IPs cadastrados no banco de dados."""
    from core.database import get_all_servers
    return [row[1] for row in get_all_servers()]


def get_orchestrator() -> PingOrchestrator:
    """Retorna a instância global do orchestrator após garantia de prontidão."""
    _wait_until_ready()
    return _orchestrator


def get_full_snapshot():
    """Copia o snapshot completo de dados de ping acumulados."""
    return _ping_snapshot.copy()
