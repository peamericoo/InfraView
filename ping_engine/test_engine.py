# ping_engine/test_engine.py

import sys
import os
import asyncio

# Garante que o Python reconheça ping_engine como pacote
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ping_engine.orchestrator import PingOrchestrator
from ping_engine import database_access, analytics, scheduler

# Cria as tabelas se necessário
database_access.create_tables()

# Callback para lidar com os dados recebidos do Go
async def status_handler(data):
    data["status"] = analytics.analyze_ping(data)
    database_access.save_ping_result(data)

    interval = scheduler.get_ping_interval(data["status"])

    print(f"\n[STATUS] IP: {data['ip']}")
    print(f"  ↪ Latência: {data['latency']}ms")
    print(f"  ↪ Online: {data['online']}")
    print(f"  ↪ Classificação: {data['status']}")
    print(f"  ↪ Próximo ping sugerido: {interval}s")
    print(f"  ↪ Timestamp: {data['timestamp']}")

# Função principal
async def main():
    orchestrator = PingOrchestrator()
    await orchestrator.connect()
    orchestrator.add_status_callback(status_handler)

    # IPs de teste — personalize aqui com servidores reais se quiser
    await orchestrator.add_server("8.8.8.8")
    await orchestrator.add_server("1.1.1.1")

    print("[INFO] Streaming iniciado...")
    await orchestrator.stream_status(["8.8.8.8", "1.1.1.1"])

if __name__ == "__main__":
    asyncio.run(main())
