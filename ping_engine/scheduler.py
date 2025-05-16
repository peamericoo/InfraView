# ping_engine/scheduler.py
import time
from ping_engine.constants import PING_INTERVALS_BY_STATUS, DEFAULT_PING_INTERVAL

def get_ping_interval(status: str) -> float:
    status = status.lower()
    return PING_INTERVALS_BY_STATUS.get(status, DEFAULT_PING_INTERVAL)

def distribute_pings(profiles):
    """
    Retorna uma lista de IPs que devem ser pingados *agora*,
    escalonando para distribuir os pings ao longo do intervalo.
    """
    now = time.time()
    ips_to_ping = []

    # Coleta só os estáveis e calcula o slot de distribuição
    estaveis = [ip for ip, p in profiles.items() if p.get("status") == "estável"]
    total_estaveis = len(estaveis)

    for i, (ip, profile) in enumerate(profiles.items()):
        interval = profile.get("ping_interval", 10)
        # Se nunca pingou ou chegou a hora de pingar
        if "next_ping_at" not in profile or now >= profile["next_ping_at"]:
            # Escalonar os "estáveis"
            if profile.get("status") == "estável" and total_estaveis > 0:
                slot = estaveis.index(ip)  # Índice entre os estáveis
                spacing = interval / total_estaveis
                profile["next_ping_at"] = now + interval
                # Ping só se chegou no slot certo (arredonda para cima)
                if now % interval < spacing:
                    ips_to_ping.append(ip)
            else:
                # Outros perfis pingam normalmente
                profile["next_ping_at"] = now + interval
                ips_to_ping.append(ip)
    return ips_to_ping
