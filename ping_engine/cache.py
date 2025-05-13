# ping_engine/cache.py

import time

# Estrutura de cache por IP
_cache = {}

def update(ip: str, status: str, latency: float):
    """
    Atualiza o cache de um IP com novo status, latência e timestamp.
    """
    _cache[ip] = {
        "status": status,
        "latency": latency,
        "last_updated": time.time()
    }

def get_status(ip: str) -> str:
    """
    Retorna o último status conhecido do IP.
    """
    return _cache.get(ip, {}).get("status")

def get_latency(ip: str) -> float:
    """
    Retorna a última latência conhecida do IP.
    """
    return _cache.get(ip, {}).get("latency")

def get_last_ping_time(ip: str) -> float:
    """
    Retorna o timestamp do último ping recebido.
    """
    return _cache.get(ip, {}).get("last_updated", 0)

def has_changed(ip: str, new_status: str) -> bool:
    """
    Retorna True se o status mudou desde o último valor em cache.
    """
    return get_status(ip) != new_status

def clear():
    """
    Limpa todo o cache (para testes).
    """
    _cache.clear()
