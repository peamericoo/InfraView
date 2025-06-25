import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ping_engine.analytics as analytics


def test_analyze_ping_stable(monkeypatch):
    ip = '1.2.3.4'
    data = {'ip': ip, 'latency': 10.0, 'online': True}
    for _ in range(6):
        status = analytics.analyze_ping(data)
    assert status == 'estável'


def test_analyze_ping_offline():
    ip = '5.6.7.8'
    data = {'ip': ip, 'latency': None, 'online': False}
    for _ in range(5):
        status = analytics.analyze_ping(data)
    assert status == 'offline'