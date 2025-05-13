# ping_engine/scheduler.py

from ping_engine.constants import PING_INTERVALS_BY_STATUS, DEFAULT_PING_INTERVAL

def get_ping_interval(status: str) -> float:
    """
    Retorna o intervalo (em segundos) ideal de ping para o status atual.
    Utiliza o mapeamento centralizado definido em constants.py.
    """
    status = status.lower()
    return PING_INTERVALS_BY_STATUS.get(status, DEFAULT_PING_INTERVAL)
