# ping_engine/controller.py

import asyncio
from ping_engine.interface import get_orchestrator

# Centraliza comandos de controle direto da engine
# sem passar pela interface (GUI <-> orchestrator)

def add_server_live(ip: str):
    loop = get_orchestrator().loop
    asyncio.run_coroutine_threadsafe(get_orchestrator().add_server(ip), loop)


def remove_server_live(ip: str):
    loop = get_orchestrator().loop
    asyncio.run_coroutine_threadsafe(get_orchestrator().remove_server(ip), loop)


def edit_server_live(old_ip: str, new_ip: str):
    loop = get_orchestrator().loop
    orchestrator = get_orchestrator()
    asyncio.run_coroutine_threadsafe(orchestrator.remove_server(old_ip), loop)
    asyncio.run_coroutine_threadsafe(orchestrator.add_server(new_ip), loop)


# Usado em operações em lote (recarrega todos os IPs do banco)
def reload_all_servers_from_db():
    from core.database import get_all_servers
    loop = get_orchestrator().loop
    ip_list = [{"ip": row[1]} for row in get_all_servers()]
    asyncio.run_coroutine_threadsafe(get_orchestrator().reload_servers(ip_list), loop)

def add_server_and_refresh(ip: str):
    loop = get_orchestrator().loop
    orchestrator = get_orchestrator()
    asyncio.run_coroutine_threadsafe(orchestrator.add_server(ip), loop)
    asyncio.run_coroutine_threadsafe(orchestrator.restart_stream(), loop)
