# ping_engine/constants.py

# Portas padrão usadas em fallback TCP
TCP_FALLBACK_PORTS = [22, 80, 443, 3389]

# Tempo máximo de espera por resposta do ping (em segundos)
PING_TIMEOUT = 2.0

# Intervalo padrão entre pings para IPs sem classificação
DEFAULT_PING_INTERVAL = 20.0

# Limite de histórico de latência por IP
MAX_LATENCY_HISTORY = 10

# Janela mínima de análise para decidir perfil (em pings)
MIN_ANALYSIS_WINDOW = 5

# Estados possíveis reconhecidos pela engine
STATUS_ENUM = [
    "estável",
    "flutuante",
    "instável",
    "risco crescente",
    "observação",
    "offline",
    "firewall"
]

# Intervalos sugeridos por status
PING_INTERVALS_BY_STATUS = {
    "observação": 10.0,
    "estável": 180.0,
    "flutuante": 30.0,
    "risco crescente": 15.0,
    "instável": 10.0,
    "offline": 5.0,
    "firewall": 20.0
}
