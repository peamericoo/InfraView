"""
core/pause_manager.py
---------------------
Interface síncrona para pausar / retomar o ping de um servidor.

• Atualiza o banco SQLite          (core.database)
• Atualiza o perfil JSON           (ping_engine.database_access)
• Dispara ação em tempo-real       (ping_engine.controller)

Uso:
    from core.pause_manager import toggle_pause, is_paused

    toggle_pause("192.168.0.10", pause=True)   # Pausar
    toggle_pause("192.168.0.10", pause=False)  # Retomar
"""
from __future__ import annotations

from typing import Dict

from core import database
from ping_engine import database_access, controller

# ----------------------------------------------------------------------
# Cache simples em memória para consultas rápidas na GUI
# ----------------------------------------------------------------------
_PAUSED_CACHE: Dict[str, bool] = {}


def is_paused(ip: str) -> bool:
    """Retorna True se o servidor estiver pausado (cache → BD)."""
    cached = _PAUSED_CACHE.get(ip)
    if cached is not None:
        return cached

    # Consulta rápida ao BD
    rows = database.get_all_servers()
    _PAUSED_CACHE.update({row[1]: row[2] == "paused" for row in rows})  # ip → status
    return _PAUSED_CACHE.get(ip, False)


# ----------------------------------------------------------------------
# Operação principal
# ----------------------------------------------------------------------
def toggle_pause(ip: str, pause: bool) -> None:
    """
    Pausa ou retoma o ping para `ip`.

    🔒 Executa três passos, na ordem:
       1. Atualiza status no BD (tabela 'servers')
       2. Atualiza perfil JSON em ping_engine.database_access
       3. Chama engine em tempo real via ping_engine.controller
    """
    new_status = "paused" if pause else "running"

    # 1. Banco de dados --------------------------------------------------
    # Precisamos do NOME atual para usar update_server_info()
    for name, ip_addr, *_ in database.get_all_servers():
        if ip_addr == ip:
            database.update_server_info(current_name=name, new_status=new_status)
            break

    # 2. Perfil JSON -----------------------------------------------------
    profile = database_access.load_ip_profile(ip) or {}
    profile["paused"] = pause
    profile["status"] = "pausado" if pause else profile.get("status", "estável")
    database_access.save_ip_profile(ip, profile)

    # 3. Engine em tempo-real -------------------------------------------
    if pause:
        controller.pause_server_live(ip)
    else:
        controller.resume_server_live(ip)

    # 4. Cache -----------------------------------------------------------
    _PAUSED_CACHE[ip] = pause
