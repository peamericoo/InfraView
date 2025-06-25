import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ping_engine import scheduler


def test_distribute_pings_paused():
    profiles = {
        '1.1.1.1': {'status': 'estável', 'paused': False},
        '2.2.2.2': {'status': 'instável', 'paused': True},
    }
    ips = scheduler.distribute_pings(profiles)
    assert '2.2.2.2' not in ips
    assert '1.1.1.1' in ips