# ping_engine/orchestrator.py

import asyncio
import logging
import grpc
from ping_engine import analytics, database_access
from ping_engine.go.infraview.pingservice import pingservice_pb2, pingservice_pb2_grpc

logger = logging.getLogger(__name__)

class PingOrchestrator:
    def __init__(self, address="localhost:50051"):
        self.address = address
        self.channel = grpc.aio.insecure_channel(self.address)
        self.stub = None
        self.status_callbacks = []
        self.callback = None
        self.stream_task = None
        self.ready = False

    async def connect(self):
        self.stub = pingservice_pb2_grpc.PingServiceStub(await self.channel.__aenter__())
        logger.info("Conectado ao serviço gRPC em %s", self.address)
        self.ready = True

    async def add_server(self, ip: str):
        req = pingservice_pb2.AddRequest(ip=ip)
        ack = await self.stub.AddServer(req)
        logger.debug("AddServer: %s", ack.message)
        return ack.success

    async def remove_server(self, ip: str):
        req = pingservice_pb2.RemoveRequest(ip=ip)
        ack = await self.stub.RemoveServer(req)
        logger.debug("RemoveServer: %s", ack.message)
        return ack.success

    def add_status_callback(self, coro):
        self.status_callbacks.append(coro)

    async def _stream_loop(self, ip_list):
        if self.stub is None:
            print("[ERRO] stream_status: stub não está conectado")
            return

        try:
            req = pingservice_pb2.StatusRequest(ips=ip_list)
            stream = self.stub.StreamStatus(req)

            print("[ORCHESTRATOR] stream_status iniciado — recebendo atualizações...")
            async for update in stream:
                update_data = {
                    update.ip: {
                        "ip": update.ip,
                        "latency": update.latency,
                        "online": update.online,
                        "status": update.status,
                        "timestamp": update.timestamp
                    }
                }
                print("[ORCHESTRATOR] Update recebido do Go:", update_data)
                for cb in self.status_callbacks:
                    await cb(update_data)

        except grpc.aio.AioRpcError as e:
            print("[ERRO] Falha no stream_status:", e)

    async def stream_status(self, ip_list):
        if self.stream_task:
            if self.stream_task:
                self.stream_task.cancel()
                await asyncio.sleep(0.1)  # Dá tempo do cancelamento ocorrer
                self.stream_task = None

                print("[ORCHESTRATOR] stream_status anterior cancelado com sucesso")

        self.stream_task = asyncio.create_task(self._stream_loop(ip_list))

    async def restart_stream(self):
        from core.database import get_all_servers
        ips = [row[1] for row in get_all_servers()]
        await self.stream_status(ips)

    async def reload_servers(self, ip_list: list[dict]):
        for item in ip_list:
            await self.remove_server(item["ip"])
            await self.add_server(item["ip"])

        print("[ORCHESTRATOR] reiniciando stream_status após reload_servers")
        await self.stream_status([item["ip"] for item in ip_list])

    async def wait_until_ready(self):
        while not self.ready:
            await asyncio.sleep(0.1)

    async def close(self):
        await self.channel.__aexit__(None, None, None)


# Executado uma vez para garantir que o banco existe
database_access.create_tables()

# Callback padrão opcional (pode ser sobrescrito pelo test_engine.py)
async def status_handler(data):
    data["status"] = analytics.analyze_ping(data)
    database_access.save_ping_result(data)
    print(f"[PING] {data['ip']} → {data['status']} ({data['latency']}ms)")
