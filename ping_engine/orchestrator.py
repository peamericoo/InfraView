# ping_engine/orchestrator.py
import asyncio
import logging
import traceback
import grpc
from datetime import datetime
import time
from ping_engine import scheduler
import time
from ping_engine import analytics, database_access, scheduler
from ping_engine.go.infraview.pingservice import pingservice_pb2, pingservice_pb2_grpc
from ping_engine import database_access
from ping_engine.controller import test_multiple_ports


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

        # Carrega perfis salvos do banco ao inicializar
        self.profiles = {}

    async def connect(self):
        try:
            self.stub = pingservice_pb2_grpc.PingServiceStub(await self.channel.__aenter__())
            logger.info("Conectado ao serviço gRPC em %s", self.address)
            self.ready = True
        except Exception as e:
            logger.error(f"Erro ao conectar ao serviço gRPC: {e}")
            self.ready = False
            raise

    async def add_server(self, ip: str):
        try:
            req = pingservice_pb2.AddRequest(ip=ip)
            ack = await self.stub.AddServer(req)
            logger.debug("AddServer: %s", ack.message)
            # Inicializa perfil do IP ao adicionar
            if ip not in self.profiles:
                self.profiles[ip] = self._init_profile(ip)
            return ack.success
        except Exception as e:
            logger.error(f"Erro ao adicionar servidor {ip}: {e}")
            return False

    async def remove_server(self, ip: str):
        try:
            req = pingservice_pb2.RemoveRequest(ip=ip)
            ack = await self.stub.RemoveServer(req)
            logger.debug("RemoveServer: %s", ack.message)
            # Remove perfil do IP
            self.profiles.pop(ip, None)
            return ack.success
        except Exception as e:
            logger.error(f"Erro ao remover servidor {ip}: {e}")
            return False
    
        # ------------------------------------------------------------------
    # Inicialização atrasada (chame logo após a senha ser validada)
    # ------------------------------------------------------------------
    def refresh_profiles_from_db(self):
        """
        Cria tabelas da engine (se ainda não existirem) e carrega
        todos os perfis de IP salvos. Deve ser chamado SOMENTE
        depois que core.database.set_connection() já estiver OK.
        """
        database_access.create_profile_and_event_tables()
        self.profiles = database_access.load_all_ip_profiles()


    def add_status_callback(self, coro):
        self.status_callbacks.append(coro)


    async def _stream_loop(self, ip_list):
        if self.stub is None:
            logger.error("stream_status: stub não está conectado")
            return

        while True:
            # === AQUI: distribua os pings de acordo com o escalonamento ===
            ips_to_ping = scheduler.distribute_pings(self.profiles)
            if not ips_to_ping:
                await asyncio.sleep(0.5)
                continue
            req = pingservice_pb2.StatusRequest(ips=ips_to_ping)
            stream = self.stub.StreamStatus(req)
            logger.info(f"Enviando para ping só os IPs escalonados agora: {ips_to_ping}")

            async for update in stream:
                update_data = {update.ip: {
                    "ip": update.ip,
                    "latency": update.latency,
                    "online": update.online,
                    "status": update.status,
                    "timestamp": update.timestamp
                }}
                try:
                    processed_data = self.process_update(update_data)
                except Exception as e:
                    logger.error(f"Erro no pipeline de decisão do IP {update.ip}: {e}")
                    logger.debug(traceback.format_exc())
                    continue

                for cb in self.status_callbacks:
                    await cb(processed_data)
            await asyncio.sleep(0.5)  # para não travar o loop

    async def stream_status(self, ip_list):
        if self.stream_task:
            self.stream_task.cancel()
            await asyncio.sleep(0.1)
            self.stream_task = None
            logger.info("[ORCHESTRATOR] stream_status anterior cancelado com sucesso")
        self.stream_task = asyncio.create_task(self._stream_loop(ip_list))

    async def restart_stream(self):
        from core.database import get_all_servers
        ips = [row[1] for row in get_all_servers()]
        await self.stream_status(ips)

    async def reload_servers(self, ip_list: list[dict]):
        for item in ip_list:
            await self.remove_server(item["ip"])
            await self.add_server(item["ip"])
        logger.info("[ORCHESTRATOR] reiniciando stream_status após reload_servers")
        await self.stream_status([item["ip"] for item in ip_list])

    async def wait_until_ready(self):
        while not self.ready:
            await asyncio.sleep(0.1)

    async def close(self):
        await self.channel.__aexit__(None, None, None)

    # ------------------ NOVA LÓGICA CENTRAL ------------------------

    def _init_profile(self, ip):
        # Inicializa perfil detalhado do IP
        return {
            "ip": ip,
            "status": "observação",
            "history": [],
            "latency_avg": None,
            "latency_std": None,
            "last_seen": None,
            "stable_count": 0,  # Pings estáveis seguidos
            "preferred_method": "icmp",  # ou tcp
            "ping_interval": 10,  # segundos (ajustável)
            "failures": [],
            "activity_window": None,  # (hora_inicio, hora_fim)
            "alerts": [],
            "ultimos_alertas": {},
            # ... futuro: perfil horário, tags, etc.
        }

    def process_update(self, update_data):
        """
        Pipeline central: recebe update {ip: {dados}}, atualiza perfil, decide ação,
        registra histórico, grava logs e devolve status detalhado para interface.
        """
        for ip, data in update_data.items():
            FALLBACK_PORTS = [22, 80, 443, 3389]
            # 1. Carrega/cria perfil do IP
            profile = self.profiles.get(ip) or self._init_profile(ip)
            self.profiles[ip] = profile

            # 2. Atualiza histórico
            profile["history"].append({
                "latency": data["latency"],
                "online": data["online"],
                "timestamp": data["timestamp"]
            })
            if len(profile["history"]) > 300:
                profile["history"] = profile["history"][-300:]  # Limita histórico em memória

            # 3. Analytics: status inteligente
            try:
                analyzed_status = analytics.analyze_ping(data)
                profile["status"] = analyzed_status
            except Exception as e:
                logger.error(f"Erro na análise de padrão do IP {ip}: {e}")
                profile["status"] = "erro_analise"
            # ----------------- FALLBACK TCP: CENÁRIO 3 -----------------
            # Detecta possível queda súbita após estabilidade
            if (
                profile.get("last_status") == "estável"
                and profile["status"] in ["offline", "instável"]
                and not profile.get("fallback_checked")
            ):
                # Tenta fallback TCP nas portas comuns
                tcp_ok = test_multiple_ports(ip, FALLBACK_PORTS)
                if tcp_ok:
                    profile["status"] = "online_tcp"
                    profile["preferred_method"] = "tcp"
                    profile["alerts"].append("ICMP bloqueado, mas porta TCP está aberta (firewall?)")
                    database_access.save_engine_event(ip, "alerta", "ICMP bloqueado, TCP responde", profile)
                else:
                    profile["status"] = "crítico"
                    profile["alerts"].append("Falha confirmada: nem ICMP nem TCP respondem. Fallback ativado.")
                    database_access.save_engine_event(ip, "crítico", "Servidor não responde nem ICMP nem TCP (queda súbita confirmada)", profile)
                    # Duplica frequência temporariamente
                    profile["ping_interval"] = max(2, profile["ping_interval"] // 2)
                    profile["fallback_start_time"] = time.time()
                profile["fallback_checked"] = True  # Marca que já tentou

            # Após 5 minutos, remove fallback
            if profile.get("fallback_start_time"):
                if time.time() - profile["fallback_start_time"] > 300:
                    profile.pop("fallback_start_time", None)
                    profile.pop("fallback_checked", None)
                    profile["ping_interval"] = scheduler.get_ping_interval(profile["status"])
                    profile["alerts"].append("Intervalo de ping restaurado após fallback crítico.")

            # 4. Cenários inteligentes: observação, estável, flutuante
            if profile["status"] == "observação":
                # Cenário 5: IP recém-adicionado
                profile.setdefault("obs_start_time", data["timestamp"])
                # Converte string ISO8601 para timestamp epoch
                obs_start_dt = datetime.fromisoformat(profile["obs_start_time"])
                obs_elapsed = time.time() - obs_start_dt.timestamp()
                # Mantém ping a cada 10s durante os 2 primeiros minutos OU até 10 pings válidos
                profile["ping_interval"] = 10
                valid_pings = [h for h in profile["history"] if h["latency"] is not None]
                if obs_elapsed > 90 and len(valid_pings) >= 10:
                    # Faz análise com base nos primeiros 10 pings válidos
                    latencies = [h["latency"] for h in valid_pings[-30:]]
                    if len(latencies) < 3 or any(l is None for l in latencies):
                        # Se poucos pings válidos, continua observação
                        pass
                    else:
                        mean = sum(latencies) / len(latencies)
                        stddev = (sum((l - mean) ** 2 for l in latencies) / (len(latencies)-1)) ** 0.5 if len(latencies) > 2 else 0
                        if stddev > mean * 0.5:
                            # Alta variação já de início → flutuante
                            profile["status"] = "flutuante"
                            profile["alerts"].append("Alerta: IP recém-adicionado já apresentou variação alta.")
                            database_access.save_engine_event(ip, "alerta", "IP recém-adicionado detectado como flutuante", profile)
                            profile.pop("obs_start_time", None)
                        else:
                            # Perfil estável
                            profile["status"] = "estável"
                            profile["alerts"].append("IP classificado como estável após observação inicial.")
                            database_access.save_engine_event(ip, "info", "IP classificado como estável após observação inicial.", profile)
                            profile.pop("obs_start_time", None)
            elif profile["status"] == "estável":
                profile["stable_count"] += 1
                ultimos = profile.setdefault("ultimos_alertas", {})
                ultimo_promovido = ultimos.get("promocao_estavel", 0)
                if profile["stable_count"] >= 30 and not profile.get("promovido_estavel") and time.time() - ultimo_promovido > 86400:
                    profile["ping_interval"] = 15
                    profile["alerts"].append("Frequência reduzida para 30s — estável")
                    database_access.save_engine_event(ip, "info", "Frequência reduzida para 30s — estável", profile)
                    profile["promovido_estavel"] = True
                    ultimos["promocao_estavel"] = time.time()
                else:
                    profile["ping_interval"] = 10
            # ainda em observação, ping mais rápido
            else:
                profile["stable_count"] = 0
                profile["ping_interval"] = scheduler.get_ping_interval(profile["status"])


            # 5. Atualiza médias/estatísticas
            latencies = [h["latency"] for h in profile["history"] if h["latency"] is not None]
            if latencies:
                profile["latency_avg"] = sum(latencies) / len(latencies)
                if len(latencies) > 2:
                    mean = profile["latency_avg"]
                    profile["latency_std"] = (sum((l - mean) ** 2 for l in latencies) / (len(latencies)-1)) ** 0.5
                else:
                    profile["latency_std"] = 0
            else:
                profile["latency_avg"] = None
                profile["latency_std"] = None

            profile["last_seen"] = data["timestamp"]

            # 6. Grava log detalhado no banco (banco já integrado)
            database_access.save_ping_result({
                "ip": ip,
                "latency": data["latency"],
                "online": data["online"],
                "status": profile["status"],
                "timestamp": data["timestamp"]
            })

            # Salva/atualiza o perfil persistente no banco
            database_access.save_ip_profile(ip, profile)

            # 7. Prepara resposta detalhada para interface
            update_data[ip].update({
                "profile": profile,  # Perfil completo do IP
                "message": self._status_message(profile),  # Mensagem amigável
            })
            profile["last_status"] = profile["status"]
        
             # ----- Latência Crescente (Cenário 8) -----
            if profile["status"] == "risco crescente":
                ultimos = profile.setdefault("ultimos_alertas", {})
                ultimo_risco = ultimos.get("risco_crescente", 0)
                if "watch_risk_start" not in profile and (time.time() - ultimo_risco > 1800):  # 30 min
                    profile["watch_risk_start"] = time.time()
                    profile["alerts"].append("Atenção: latência está subindo, possível falha próxima.")
                    database_access.save_engine_event(ip, "alerta", "Latência subindo, risco de falha.", profile)
                    ultimos["risco_crescente"] = time.time()
                if time.time() - profile.get("watch_risk_start", 0) < 3600:
                    profile["ping_interval"] = 10
                else:
                    profile.pop("watch_risk_start", None)
            else:
                profile.pop("watch_risk_start", None)

            # ----- Falha Intermitente (Cenário 7) -----
            if analytics.is_intermitente(profile["history"]):
                ultimos = profile.setdefault("ultimos_alertas", {})
                ultimo_intermitente = ultimos.get("falha_intermitente", 0)
                intervalo_min = 1800  # 30 minutos em segundos

                if time.time() - ultimo_intermitente > intervalo_min:
                    profile["status"] = "instável"
                    alerta = "Falha intermitente detectada (quedas recorrentes)."
                    if alerta not in profile["alerts"]:
                        profile["alerts"].append(alerta)
                    profile["ping_interval"] = 10
                    database_access.save_engine_event(ip, "alerta", alerta, profile)
                    ultimos["falha_intermitente"] = time.time()

            # ----- Pico de Latência Diário (Cenário 2) -----
            pico_horario = analytics.detecta_pico_diario(profile["history"])
            if pico_horario:
                alerta = f"Latência alta prevista às {pico_horario}h (pico recorrente detectado)."
                agora = time.time()
                ultimos = profile.setdefault("ultimos_alertas", {})
                ultimo_pico = ultimos.get("pico_diario", 0)
                # Só alerta se faz >1h do último alerta desse tipo
                if agora - ultimo_pico > 3600:
                    if alerta not in profile["alerts"]:
                        profile["alerts"].append(alerta)
                        database_access.save_engine_event(ip, "alerta", alerta, profile)
                    ultimos["pico_diario"] = agora
                profile["ping_interval"] = 10

        return update_data
    
    def _status_message(self, profile):
        status = profile["status"]
        if status == "estável":
            return "Tudo normal. O servidor está respondendo bem."
        elif status == "flutuante":
            return "Detectamos variação de latência. Pode ser congestão de rede."
        elif status == "instável":
            return "Conexão intermitente, recomendamos verificar cabo/rede."
        elif status == "offline":
            return "Servidor está offline. Verifique conexão ou energia."
        elif status == "risco crescente":
            return "Atenção: latência está subindo. Possível falha em breve."
        elif status == "crítico":
            return "Servidor em estado crítico. Não responde nem ICMP nem TCP."
        elif status == "online_tcp":
            return "Servidor responde apenas via TCP (ICMP bloqueado ou firewall ativo)."
        else:
            return f"Status: {status}"

