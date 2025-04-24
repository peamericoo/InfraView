# utils.py
import ipaddress
import socket
import subprocess
from core.monitor import test_ping_like_monitor
from pathlib import Path

def validate_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def resolve_and_ping(domain: str) -> str | None:
    try:
        resolved_ip = socket.gethostbyname(domain)
    except Exception:
        return None

    if test_ping_like_monitor(resolved_ip):
        return resolved_ip
    return None

def get_data_path(filename):
    return Path(__file__).resolve().parent.parent / filename