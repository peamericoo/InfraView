# ping_engine/analytics.py
"""
Análise otimizada de latência
────────────────────────────
* Usa deque de tamanho definido em constants.MAX_LATENCY_HISTORY
  (default 10) – já mantinha O(1) espaço; permanece.
* Limpeza automática de IPs inativos após 1 h (_HISTORY_TTL_SECONDS).
* Calcula média e desvio-padrão incremental em O(1) usando algoritmo de
  variância on-line de Welford (evita statistics.stdev sobre lista).
"""

from __future__ import annotations

import time
from collections import deque, defaultdict
from typing import Deque, Dict, Tuple, Optional

from ping_engine.constants import MAX_LATENCY_HISTORY, MIN_ANALYSIS_WINDOW

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
_HISTORY_TTL_SECONDS = 3600  # 1 h sem updates ⇒ apaga do dicionário

# ---------------------------------------------------------------------------
# ESTRUTURA: { ip: deque[(ts, latency|None)] }
# ---------------------------------------------------------------------------
_latency_history: Dict[str, Deque[Tuple[float, Optional[float]]]] = defaultdict(
    lambda: deque(maxlen=MAX_LATENCY_HISTORY)
)
_last_seen: Dict[str, float] = {}  # para TTL cleanup

# ---------------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------------
def analyze_ping(data: dict) -> str:
    """
    Recebe o ping atual e retorna o status interpretado.
    Possíveis estados: estável, flutuante, instável, risco crescente,
    observação, offline.
    """
    ip = data["ip"]
    latency = data["latency"] if data["online"] else None
    now = time.time()

    history = _latency_history[ip]
    history.append((now, latency))
    _last_seen[ip] = now

    # Limpamos IPs inativos de tempos em tempos
    if len(_last_seen) % 200 == 0:  # cada 200 atualizações ≈ O(1)
        _purge_inactive(now)

    # Menos de MIN_ANALYSIS_WINDOW entradas → observação
    if len(history) < MIN_ANALYSIS_WINDOW:
        return "observação"

 # 1️⃣ Distribui amostras
    latencies      = [l for _, l in history if l is not None]
    offline_count  = len(history) - len(latencies)

    # Se NENHUMA latência válida foi registrada → offline
    if offline_count >= MIN_ANALYSIS_WINDOW and not latencies:
        return "offline"

    # 2️⃣ Caso exista mistura de respostas e falhas → instável
    if offline_count >= 3:
        return "instável"

    mean, stddev = _running_stats(latencies)

    if stddev > mean * 0.5:
        return "flutuante"

    if _is_latency_growing(latencies):
        return "risco crescente"

    return "estável"

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _purge_inactive(now: float):
    for ip, ts in list(_last_seen.items()):
        if now - ts > _HISTORY_TTL_SECONDS:
            _last_seen.pop(ip, None)
            _latency_history.pop(ip, None)

def _running_stats(latencies):
    """Retorna (mean, stddev) calculados incrementalmente."""
    mean = 0.0
    m2 = 0.0
    n = 0
    for x in latencies:
        n += 1
        delta = x - mean
        mean += delta / n
        m2 += delta * (x - mean)
    variance = (m2 / (n - 1)) if n > 1 else 0.0
    return mean, variance ** 0.5

def _is_latency_growing(latencies, window=4):
    if len(latencies) < window:
        return False
    recent = latencies[-window:]
    return all(a < b for a, b in zip(recent, recent[1:]))

def is_intermitente(history):
    # Mantido igual à versão anterior
    import datetime, time as _t
    now = _t.time()
    offline_events = [
        h for h in history
        if not h["online"] and (now - datetime.datetime.fromisoformat(h["timestamp"]).timestamp()) < 3600
    ]
    return len(offline_events) >= 3

def detecta_pico_diario(history):
    # Mantido igual
    import collections
    horario_picos = [h["timestamp"][11:13] for h in history if h["latency"] and h["latency"] > 200]
    contagem = collections.Counter(horario_picos)
    if contagem:
        pico_mais_comum, freq = contagem.most_common(1)[0]
        if freq >= 2:
            return pico_mais_comum
    return None
