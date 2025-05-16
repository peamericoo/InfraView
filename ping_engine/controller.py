# ping_engine/controller.py
import socket
import asyncio

# Centraliza comandos de controle direto da engine
# sem passar pela interface (GUI <-> orchestrator)

def add_server_live(ip: str):
    from ping_engine.interface import get_orchestrator
    loop = get_orchestrator().loop
    asyncio.run_coroutine_threadsafe(get_orchestrator().add_server(ip), loop)


def remove_server_live(ip: str):
    from ping_engine.interface import get_orchestrator
    loop = get_orchestrator().loop
    asyncio.run_coroutine_threadsafe(get_orchestrator().remove_server(ip), loop)


def edit_server_live(old_ip: str, new_ip: str):
    from ping_engine.interface import get_orchestrator
    loop = get_orchestrator().loop
    orchestrator = get_orchestrator()
    asyncio.run_coroutine_threadsafe(orchestrator.remove_server(old_ip), loop)
    asyncio.run_coroutine_threadsafe(orchestrator.add_server(new_ip), loop)


# Usado em operações em lote (recarrega todos os IPs do banco)
def reload_all_servers_from_db():
    from ping_engine.interface import get_orchestrator
    from core.database import get_all_servers
    loop = get_orchestrator().loop
    ip_list = [{"ip": row[1]} for row in get_all_servers()]
    asyncio.run_coroutine_threadsafe(get_orchestrator().reload_servers(ip_list), loop)

def add_server_and_refresh(ip: str):
    from ping_engine.interface import get_orchestrator
    loop = get_orchestrator().loop
    orchestrator = get_orchestrator()
    asyncio.run_coroutine_threadsafe(orchestrator.add_server(ip), loop)
    asyncio.run_coroutine_threadsafe(orchestrator.restart_stream(), loop)

def test_tcp_port(ip, port, timeout=2):
    """Testa se uma porta TCP está aberta."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def test_multiple_ports(ip, ports, timeout=2):
    """Testa várias portas TCP e retorna True se alguma responder."""
    return any(test_tcp_port(ip, port, timeout) for port in ports)