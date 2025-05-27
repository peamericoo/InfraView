# ping_engine/scheduler.py
"""
Scheduler revisado
──────────────────
* Distribui de forma **determinística** os pings de servidores "estáveis"
  ao longo do intervalo, evitando bursts.
* Qualquer status diferente de "estável" é considerado prioritário e pingado
  assim que o `ping_interval` expira.
* Respeita intervalos dinâmicos atualizados em `profile["ping_interval"]`.
* Usa `ping_engine.constants` para valores padrão.

Campos utilizados/atualizados em cada `profile`:
    * `ping_interval`   – intervalo atual em segundos
    * `next_ping_at`    – timestamp agendado do próximo ping
    * `slot_offset`     – deslocamento calculado para distribuição (estáveis)
"""

from __future__ import annotations

import time
from typing import Dict, List, Any

from ping_engine.constants import PING_INTERVALS_BY_STATUS, DEFAULT_PING_INTERVAL

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_ping_interval(status: str | None) -> float:
    """Retorna intervalo em segundos para o *status* dado."""
    if not status:
        return DEFAULT_PING_INTERVAL
    return PING_INTERVALS_BY_STATUS.get(status.lower(), DEFAULT_PING_INTERVAL)


# ---------------------------------------------------------------------------
# SCHEDULER PRINCIPAL
# ---------------------------------------------------------------------------

def distribute_pings(profiles: Dict[str, Dict[str, Any]]) -> List[str]:
    """Decide quais IPs devem ser pingados **agora**.

    Estratégia:
    1. Agrupa servidores "estáveis" para espaçar os pings dentro do
       próprio intervalo (`slot_offset`).
    2. Outros status (instável/offline/risco/...) são pingados sempre que o
       `ping_interval` expira, sem distribuição adicional.
    3. Atualiza `profile["next_ping_at"]` de cada IP após decidir ping.
    """

    now = time.time()
    ips_to_ping: List[str] = []

    # ----------------- Determina distribuição para estáveis ----------------
    stable_ips = [ip for ip, p in profiles.items() if p.get("status") == "estável"]
    total_stable = len(stable_ips)

    # Define slot_offset (cacheado em profile) para evitar recalcular sempre
    if total_stable:
        spacing_map = {}
        for idx, ip in enumerate(sorted(stable_ips)):
            spacing_map[ip] = idx  # posição determinística (ordem alfabética)

        for ip in stable_ips:
            prof = profiles[ip]
            if "slot_offset" not in prof or prof["slot_offset"] is None:
                interval = prof.get("ping_interval", DEFAULT_PING_INTERVAL)
                spacing = interval / total_stable
                prof["slot_offset"] = spacing_map[ip] * spacing

    # -------------------- Loop principal de decisão ------------------------
    for ip, prof in profiles.items():
        interval = prof.get("ping_interval") or get_ping_interval(prof.get("status"))
        prof["ping_interval"] = interval  # garante consistência

        # inicializa planejamento, se necessário
        if "next_ping_at" not in prof:
            if prof.get("status") == "estável" and total_stable:
                prof["next_ping_at"] = now + prof.get("slot_offset", 0)
            else:
                prof["next_ping_at"] = now

        # deve pingar agora?
        if now >= prof["next_ping_at"]:
            ips_to_ping.append(ip)
            # agenda próximo
            prof["next_ping_at"] = now + interval

    return ips_to_ping
