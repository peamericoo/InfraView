# monitor.py (Lógica adaptativa híbrida ICMP + TCP SYN Check com logging detalhado)
import asyncio
import platform
import re
import logging
from typing import Tuple
from PyQt5.QtCore import QThread, pyqtSignal

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def async_ping(ip: str, timeout: int = 2) -> Tuple[bool, int]:
    is_windows = platform.system().lower() == 'windows'
    timeout_value = str(timeout * 1000) if is_windows else str(timeout)
    count_flag = '-n' if is_windows else '-c'
    timeout_flag = '-w' if is_windows else '-W'
    command = ['ping', count_flag, '1', timeout_flag, timeout_value, ip]

    logging.debug(f"ICMP Ping Command: {command}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout + 1)
        output = stdout.decode('utf-8', errors='replace')
        success = "ttl=" in output.lower() or "bytes from" in output.lower()
        latency = parse_latency(output) if success else 0
        logging.debug(f"ICMP Ping {ip} success: {success}, latency: {latency} ms")
        return success, latency
    except Exception as e:
        logging.error(f"ICMP Ping Exception for {ip}: {e}")
        return False, 0

def parse_latency(output: str) -> int:
    patterns = [r'time[=<]\s?(\d+\.?\d*)\s?ms', r'(\d+\.?\d*)\s?ms']
    for pattern in patterns:
        match = re.search(pattern, output.lower())
        if match:
            return int(round(float(match.group(1))))
    return 0

async def tcp_ping(ip: str, port: int = 80, timeout: int = 2) -> bool:
    logging.debug(f"TCP Ping {ip}:{port}")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        logging.debug(f"TCP Ping {ip}:{port} success")
        return True
    except Exception as e:
        logging.error(f"TCP Ping Exception for {ip}:{port}: {e}")
        return False

class MonitorThread(QThread):
    update_signal = pyqtSignal(dict)

    def __init__(self, servers: list, group_size: int = 20, interval_group: float = 1.0, interval_ping: float = 2.0):
        super().__init__()
        self.servers = servers
        self.group_size = group_size
        self.interval_group = interval_group  # Intervalo curto entre grupos
        self.interval_ping = interval_ping    # Intervalo padrão entre cada ping
        self._running = True

        self.server_data = {}
        for ip in servers:
            self.server_data[ip] = {'online': False, 'latency': -1, 'fail_count': 0}

    def stop(self):
        self._running = False

    def run(self):
        asyncio.run(self.monitor_loop())

    async def monitor_loop(self):
        groups = [self.servers[i:i + self.group_size] for i in range(0, len(self.servers), self.group_size)]
        while self._running:
            for group in groups:
                await self.ping_group(group)
                await asyncio.sleep(self.interval_group)  # intervalo curto entre grupos

    async def ping_group(self, group):
        semaphore = asyncio.Semaphore(self.group_size)

        async def ping_host(ip):
            async with semaphore:
                success, latency = await async_ping(ip)
                if not success:
                    success = await tcp_ping(ip)
                if success:
                    self.server_data[ip].update({'online': True, 'latency': latency, 'fail_count': 0})
                else:
                    self.server_data[ip]['fail_count'] += 1
                    if self.server_data[ip]['fail_count'] >= 3:
                        self.server_data[ip]['online'] = False
                logging.debug(f"Ping result for {ip}: {self.server_data[ip]}")

        tasks = [ping_host(ip) for ip in group]
        await asyncio.gather(*tasks)
        self.update_signal.emit(self.server_data)

