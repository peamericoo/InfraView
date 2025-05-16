# ping_engine/analytics.py
from datetime import datetime
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

def _is_latency_growing(latencies: list[float], window=4) -> bool:
    if len(latencies) < window:
        return False
    # Checa se há crescimento em toda a janela final
    recent = latencies[-window:]
    return all(earlier < later for earlier, later in zip(recent, recent[1:]))

def is_intermitente(history: list[dict]) -> bool:
    # Detecta 3 ou mais quedas curtas nos últimos 60 min
    import time
    now = time.time()
    offline_events = [
        h for h in history
        if not h["online"] and (now - datetime.fromisoformat(h["timestamp"]).timestamp()) < 3600
    ]
    return len(offline_events) >= 3

def detecta_pico_diario(history: list[dict]) -> str | None:
    """
    Detecta se há picos de latência em horários semelhantes.
    Retorna o horário previsto para o próximo pico, se houver.
    """
    import collections
    # Extrai a hora de cada registro com latência > 200ms
    horario_picos = [h["timestamp"][11:13] for h in history if h["latency"] and h["latency"] > 200]
    contagem = collections.Counter(horario_picos)
    if contagem:
        pico_mais_comum, freq = contagem.most_common(1)[0]
        if freq >= 2:  # Se já aconteceu mais de uma vez no mesmo horário
            return pico_mais_comum
    return None
