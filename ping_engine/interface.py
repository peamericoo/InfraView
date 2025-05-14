# ping_engine/interface.py

import asyncio
import threading

from ping_engine.orchestrator import PingOrchestrator
from ping_engine import database_access, analytics, scheduler, cache

_loop = None
_orchestrator = None
_callback = None
_ping_snapshot = {}

def _run_async_loop():
    global _loop, _orchestrator
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    _orchestrator = PingOrchestrator()
    _orchestrator.loop = _loop

    def loop_forever():
        print("[DEBUG] Iniciando loop asyncio com run_forever()")
        try:
            _loop.run_until_complete(_start_engine())
            _loop.run_forever()
        except Exception as e:
            print("[ERRO] Loop asyncio encerrou com erro:", e)

    threading.Thread(target=loop_forever, daemon=True).start()

def start_engine(callback):
    """
    Inicia a engine em background. Deve ser chamada pela GUI.
    """
    global _callback
    _callback = callback
    threading.Thread(target=_run_async_loop, daemon=True).start()

async def _start_engine():
    await _orchestrator.connect()

    database_access.create_tables()
    _orchestrator.add_status_callback(_handle_status)

    # Recupera IPs do banco
    from core.database import get_all_servers
    db_rows = get_all_servers()
    ips = [row[1] for row in db_rows]
    for ip in ips:
        await _orchestrator.add_server(ip)

    await _orchestrator.stream_status(ips)

async def _handle_status(update_dict):
    """
    Recebe múltiplos updates da engine Go em um dicionário por IP.
    Atualiza cache, histórico, analisa status e envia snapshot para GUI.
    """
    global _ping_snapshot

    current_ips = list_servers()

    for ip, data in update_dict.items():
        if ip not in current_ips:
            continue  # Ignora updates de IPs já removidos

        data["status"] = analytics.analyze_ping(data)
        database_access.save_ping_result(data)
        cache.update(ip, data["status"], data["latency"])
        _ping_snapshot[ip] = data

    # Remove IPs que não estão mais ativos
    for ip in list(_ping_snapshot.keys()):
        if ip not in current_ips:
            _ping_snapshot.pop(ip, None)

    if _callback:
        _callback(_ping_snapshot.copy())

def add_server(ip):
    asyncio.run_coroutine_threadsafe(_orchestrator.add_server(ip), _loop)

def remove_server(ip):
    asyncio.run_coroutine_threadsafe(_orchestrator.remove_server(ip), _loop)

def get_server_status(ip):
    return {
        "status": cache.get_status(ip),
        "latency": cache.get_latency(ip),
        "last_ping": cache.get_last_ping_time(ip)
    }

def list_servers():
    from core.database import get_all_servers
    db_rows = get_all_servers()
    return [row[1] for row in db_rows]

def test_loop():
    import asyncio
    async def hello():
        print("[DEBUG] safe_stream() TESTE rodando dentro do loop")
    asyncio.run_coroutine_threadsafe(hello(), _loop)

def get_orchestrator():
    global _orchestrator
    return _orchestrator
