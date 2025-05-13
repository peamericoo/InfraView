# utils.py

import ipaddress
import socket
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
        return resolved_ip
    except Exception:
        return None

def test_ping_like_monitor(ip: str) -> bool:
    """
    Placeholder: ping real é feito pela engine Go. Aqui apenas validamos IP resolvido.
    """
    return True  # ou False se quiser negar temporariamente

def get_data_path(filename):
    return Path(__file__).resolve().parent.parent / filename
