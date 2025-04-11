# monitor.py
import asyncio
import random
import platform
import re
from typing import Tuple
from PyQt5.QtCore import QThread, pyqtSignal

# Função de ping assíncrono que retorna um Tuple[bool, int]
async def async_ping(ip: str, timeout: int = 2) -> Tuple[bool, int]:
    is_windows = platform.system().lower() == 'windows'
    count_flag = '-n' if is_windows else '-c'
    timeout_flag = '-w' if is_windows else '-W'
    command = ['ping', count_flag, '1', timeout_flag, str(timeout), ip]
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 1)
        output = stdout.decode('utf-8', errors='replace')
        success = ("ttl=" in output.lower() or "bytes from" in output.lower())
        latency = parse_latency(output) if success else 0
        return success, latency
    except Exception:
        return False, 0

def parse_latency(output: str) -> int:
    patterns = [r'time[=<]\s?(\d+\.?\d*)\s?ms', r'(\d+\.?\d*)\s?ms']
    for pattern in patterns:
        match = re.search(pattern, output.lower())
        if match:
            try:
                return int(round(float(match.group(1))))
            except:
                continue
    return 0

class MonitorThread(QThread):
    """
    MonitorThread realiza a verificação de pings para uma lista de IPs,
    utilizando uma das três estratégias:
      - 'random': Cada ping é agendado com um atraso aleatório.
      - 'backoff': Intervalo dinâmico que aumenta conforme as falhas.
      - 'scheduler': Cada ping é agendado individualmente por um scheduler central.
    """
    update_signal = pyqtSignal(dict)  # Emite um dicionário com {ip: {'online': bool, 'latency': int}}

    def __init__(self, servers: list, interval: int = 2, mode: str = "random"):
        super().__init__()
        self.servers = servers  # Lista de endereços IP
        self.interval = interval  # Intervalo base em segundos
        self.mode = mode  # Modo de execução: "random", "backoff" ou "scheduler"
        self._running = True

        # Limite de falhas consecutivas para considerar offline
        self.offline_threshold = 3

        # Armazena dados de cada servidor (fail_count, last_latency, online)
        # Assim controlamos quando marcar offline.
        self.server_data = {}
        for ip in self.servers:
            self.server_data[ip] = {
                'fail_count': 0,       # Quantas falhas consecutivas
                'last_latency': -1,     # Última latência bem-sucedida
                'online': False         # Status atual
            }

    def stop(self):
        self._running = False

    def run(self):
        asyncio.run(self.monitor_loop())

    async def monitor_loop(self):
        if self.mode == "random":
            await self.monitor_loop_random_delay()
        elif self.mode == "backoff":
            await self.monitor_loop_backoff()
        elif self.mode == "scheduler":
            await self.monitor_loop_scheduler()
        else:
            # Caso o modo não seja reconhecido, usa-se o modo aleatório como padrão.
            await self.monitor_loop_random_delay()

    # ---------------------------------------------------------------------------
    # Modo 1: Atraso Aleatório ("random")
    # ---------------------------------------------------------------------------
    async def monitor_loop_random_delay(self):
        while self._running:
            tasks = []
            for ip in self.servers:
                # Define um atraso aleatório entre 0.1 e o intervalo base para cada ping
                delay = random.uniform(0.1, self.interval)
                tasks.append(self.schedule_ping(ip, delay))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Trata os resultados
            for ip, res in zip(self.servers, results):
                if isinstance(res, tuple):
                    success, latency = res
                    self.update_server_data(ip, success, latency)

            # Monta o dicionário final para a GUI
            status_dict = {}
            for ip in self.servers:
                data = self.server_data[ip]
                status_dict[ip] = {
                    'online': data['online'],
                    'latency': data['last_latency'] if data['online'] else -1
                }

            self.update_signal.emit(status_dict)
            await asyncio.sleep(self.interval)

    async def schedule_ping(self, ip: str, delay: float):
        await asyncio.sleep(delay)
        return await async_ping(ip)

    # ---------------------------------------------------------------------------
    # Modo 2: Backoff Dinâmico ("backoff")
    # ---------------------------------------------------------------------------
    async def monitor_loop_backoff(self):
        base_interval = self.interval
        while self._running:
            tasks = []
            # Calcula delays com base nas falhas consecutivas
            for ip in self.servers:
                failure_count = self.server_data[ip]['fail_count']
                dynamic_delay = base_interval * (1 + failure_count)
                tasks.append(self.schedule_ping(ip, dynamic_delay))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for ip, res in zip(self.servers, results):
                if isinstance(res, tuple):
                    success, latency = res
                    self.update_server_data(ip, success, latency)

            # Monta o dicionário final para a GUI
            status_dict = {}
            for ip in self.servers:
                data = self.server_data[ip]
                status_dict[ip] = {
                    'online': data['online'],
                    'latency': data['last_latency'] if data['online'] else -1
                }

            self.update_signal.emit(status_dict)
            await asyncio.sleep(base_interval)

    # ---------------------------------------------------------------------------
    # Modo 3: Scheduler Centralizado ("scheduler")
    # ---------------------------------------------------------------------------
    async def monitor_loop_scheduler(self):
        # Cada IP possui seu próximo horário de execução armazenado
        next_run = {ip: 0 for ip in self.servers}
        base_interval = self.interval

        while self._running:
            current_time = asyncio.get_event_loop().time()
            tasks = []
            for ip in self.servers:
                if current_time >= next_run[ip]:
                    tasks.append(self.ping_and_reschedule(ip, base_interval, next_run))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

                # Monta o dicionário final para a GUI
                status_dict = {}
                for ip in self.servers:
                    data = self.server_data[ip]
                    status_dict[ip] = {
                        'online': data['online'],
                        'latency': data['last_latency'] if data['online'] else -1
                    }

                self.update_signal.emit(status_dict)

            await asyncio.sleep(0.1)

    async def ping_and_reschedule(self, ip: str, base_interval: int, next_run: dict):
        result = await async_ping(ip)
        if isinstance(result, tuple):
            success, latency = result
            self.update_server_data(ip, success, latency)

        # Define o próximo horário com base no intervalo base mais um jitter aleatório
        next_run[ip] = asyncio.get_event_loop().time() + base_interval + random.uniform(0.1, 0.5)
        return result

    # ---------------------------------------------------------------------------
    # Função auxiliar para atualizar dados do servidor
    # ---------------------------------------------------------------------------
    def update_server_data(self, ip: str, success: bool, latency: int):
        data = self.server_data[ip]
        if success:
            data['fail_count'] = 0
            data['online'] = True
            data['last_latency'] = latency
        else:
            data['fail_count'] += 1
            # Verifica se atingiu o limiar de falhas consecutivas
            if data['fail_count'] >= self.offline_threshold:
                data['online'] = False
            # Mantém a última latência se ele ainda não está offline
            # Se fail_count < threshold, continua online c/ latência anterior.
