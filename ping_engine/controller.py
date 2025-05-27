# ping_engine/controller.py
"""
Funções utilitárias que controlam a engine a partir de ações da GUI
(add/remove/edit/reload) sem bloquear a thread de interface.

As chamadas assíncronas são despachadas para o loop da engine por
asyncio.run_coroutine_threadsafe() com timeout curto para não travar.
"""

import socket
import asyncio
import concurrent.futures
from typing import Iterable, Sequence

_TIMEOUT_SCHEDULE = 2  # segundos para despachar tarefas no loop da engine


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _submit(coro, loop):
    """
    Despacha corrotina para o loop da engine.
    Se não conseguir enfileirar em até _TIMEOUT_SCHEDULE, descarta.
    """
    try:
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        fut.add_done_callback(lambda f: f.exception())  # loga exceções
    except concurrent.futures.TimeoutError:
        print("[WARN] loop de engine ocupado – descartando tarefa")


# ──────────────────────────────────────────────────────────────────────────────
# AÇÕES AO VIVO
# ──────────────────────────────────────────────────────────────────────────────
def add_server_live(ip: str):
    from ping_engine.interface import get_orchestrator
    orchestrator = get_orchestrator()
    _submit(orchestrator.add_server(ip), orchestrator.loop)


def remove_server_live(ip: str):
    from ping_engine.interface import get_orchestrator
    orchestrator = get_orchestrator()
    _submit(orchestrator.remove_server(ip), orchestrator.loop)


def edit_server_live(old_ip: str, new_ip: str):
    from ping_engine.interface import get_orchestrator
    orchestrator = get_orchestrator()
    _submit(orchestrator.remove_server(old_ip), orchestrator.loop)
    _submit(orchestrator.add_server(new_ip), orchestrator.loop)


# ──────────────────────────────────────────────────────────────────────────────
# RELOAD EM LOTE
# ──────────────────────────────────────────────────────────────────────────────
def reload_all_servers_from_db():
    from ping_engine.interface import get_orchestrator
    from core.database import get_all_servers

    orchestrator = get_orchestrator()
    ip_list = [{"ip": row[1]} for row in get_all_servers()]
    _submit(orchestrator.reload_servers(ip_list), orchestrator.loop)


def add_server_and_refresh(ip: str):
    """
    Adiciona servidor e reinicia stream imediatamente,
    útil quando a GUI precisa refletir já o novo IP.
    """
    from ping_engine.interface import get_orchestrator

    orchestrator = get_orchestrator()
    _submit(orchestrator.add_server(ip), orchestrator.loop)
    _submit(orchestrator.restart_stream(), orchestrator.loop)


# ──────────────────────────────────────────────────────────────────────────────
# TESTES DE PORTA (executados em thread pool para não travar GUI)
# ──────────────────────────────────────────────────────────────────────────────
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def _test_tcp_port_sync(ip: str, port: int, timeout: float) -> bool:
    """Função síncrona que testa uma porta TCP."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


async def test_tcp_port(ip: str, port: int, timeout: float = 2) -> bool:
    """Testa se uma porta TCP está aberta (async, não bloqueia a GUI)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_EXECUTOR, _test_tcp_port_sync, ip, port, timeout)


async def test_multiple_ports(ip: str, ports: Sequence[int], timeout: float = 2) -> bool:
    """Retorna True se qualquer porta em *ports* estiver aberta."""
    results = await asyncio.gather(
        *(test_tcp_port(ip, p, timeout) for p in ports),
        return_exceptions=True,
    )
    return any(res is True for res in results)
