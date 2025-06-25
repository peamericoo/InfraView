from __future__ import annotations

"""Offline failure tracking utilities.

This module persists failure events in the shared in-memory SQLite database.
It exposes a small API to record and query failures by server. The status of a
server must always be derived using :func:`core.status_logic.get_logical_status`.
"""

from datetime import datetime
from typing import Dict, List, Optional

from core.database import get_db_connection
from core.status_logic import get_logical_status


# ---------------------------------------------------------------------------
# Database schema
# ---------------------------------------------------------------------------

def init_schema() -> None:
    """Ensure the failures table exists."""
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            reason TEXT NOT NULL,
            resolved BOOLEAN DEFAULT 0
        );
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Recording and resolving failures
# ---------------------------------------------------------------------------

def record_failure(ip: str, reason: str, status: Optional[Dict] = None) -> int:
    """Insert a failure event for ``ip`` if not paused.

    Parameters
    ----------
    ip:
        Server IP.
    reason:
        Short description of the failure.
    status:
        Optional status dictionary obtained from the ping engine. If provided it
        is forwarded to :func:`get_logical_status` for proper evaluation.
    Returns
    -------
    int
        ID of the created failure row or ``-1`` when ignored (paused).
    """
    logical = get_logical_status(ip, status)
    if logical == "pausado":
        return -1

    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO failures (server_id, timestamp, reason, resolved) VALUES (?,?,?,0);",
        (ip, ts, reason),
    )
    conn.commit()
    return int(cur.lastrowid)


def resolve_failure(failure_id: int) -> None:
    """Mark a failure as resolved."""
    conn = get_db_connection()
    conn.execute("UPDATE failures SET resolved = 1 WHERE id = ?;", (failure_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def list_failures(ip: str) -> List[tuple]:
    """Return all failures of ``ip`` ordered by timestamp desc."""
    cur = get_db_connection().cursor()
    cur.execute(
        "SELECT id, server_id, timestamp, reason, resolved FROM failures "
        "WHERE server_id = ? ORDER BY timestamp DESC;",
        (ip,),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def list_servers_with_failures() -> List[str]:
    """Return distinct server IDs that recorded failures."""
    cur = get_db_connection().cursor()
    cur.execute("SELECT DISTINCT server_id FROM failures ORDER BY server_id;")
    servers = [r[0] for r in cur.fetchall()]
    cur.close()
    return servers