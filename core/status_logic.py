from datetime import datetime, timedelta
from typing import Dict, Optional

STATUS_TIMEOUT_SECONDS = 30  # Tolerância para ausência de ping

def is_server_online(status: Optional[Dict]) -> bool:
    if not status or not isinstance(status, dict):
        return False

    ts_str = status.get("timestamp")
    if not ts_str:
        return False

    try:
        ts = datetime.fromisoformat(ts_str)
    except ValueError:
        return False

    # Corrige a diferença de timezone
    diff = datetime.now().astimezone() - ts
    if diff > timedelta(seconds=STATUS_TIMEOUT_SECONDS):
        return False

    return status.get("online", False)
