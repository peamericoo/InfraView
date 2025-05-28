from datetime import datetime, timedelta
from typing import Dict, Optional
from core.pause_manager import is_paused  # dependência direta para consultar o banco

STATUS_TIMEOUT_SECONDS = 30  # Tolerância para ausência de ping

def get_logical_status(ip: str, status: Optional[Dict]) -> str:
    """
    Retorna o status lógico atual de um IP:
    - 'pausado' se o IP estiver marcado como pausado
    - 'offline' se o último ping for muito antigo ou inexistente
    - 'online' se status['online'] = True e timestamp válido
    """
    if is_paused(ip):
        return "pausado"

    if not status or not isinstance(status, dict):
        return "offline"

    ts_str = status.get("timestamp")
    if not ts_str:
        return "offline"

    try:
        ts = datetime.fromisoformat(ts_str)
    except ValueError:
        return "offline"

    diff = datetime.now().astimezone() - ts
    if diff > timedelta(seconds=STATUS_TIMEOUT_SECONDS):
        return "offline"

    return "online" if status.get("online", False) else "offline"
