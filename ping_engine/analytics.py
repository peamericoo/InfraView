# ping_engine/analytics.py

from collections import deque
import statistics
import time

# Histórico por IP: últimos 10 pings
_latency_history = {}

# Tempo mínimo entre análises (em segundos)
_ANALYSIS_WINDOW = 60

def analyze_ping(data: dict) -> str:
    """
    Recebe o ping atual e retorna o status interpretado:
    estável, flutuante, instável, risco crescente
    """
    ip = data["ip"]
    latency = data["latency"]
    online = data["online"]
    timestamp = time.time()

    history = _latency_history.get(ip, deque(maxlen=10))
    history.append((timestamp, latency if online else None))
    _latency_history[ip] = history

    # Se menos de 5 dados → modo "observação"
    if len(history) < 5:
        return "observação"

    # Contar quantos foram offline
    offline_count = sum(1 for _, l in history if l is None)

    if offline_count >= 3:
        return "instável"

    # Latências válidas
    latencies = [l for _, l in history if l is not None]

    if not latencies:
        return "offline"

    # Verificar variação
    stddev = statistics.stdev(latencies) if len(latencies) >= 2 else 0
    mean = statistics.mean(latencies)

    if stddev > mean * 0.5:
        return "flutuante"

    # Detectar crescimento progressivo
    if _is_latency_growing(latencies):
        return "risco crescente"

    return "estável"

def _is_latency_growing(latencies: list[float]) -> bool:
    if len(latencies) < 4:
        return False
    # Detectar se últimos 3 estão em crescimento
    return latencies[-3] < latencies[-2] < latencies[-1]
