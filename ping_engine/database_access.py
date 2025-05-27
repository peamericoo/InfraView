# ping_engine/database_access.py
"""
Acesso ao banco de dados (SQLite) com fila de escrita serializada.
Correção: o *writer thread* só é iniciado **após** `create_tables()`
ter garantido a inicialização da conexão global (core.database.set_connection).
"""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Callable, Any

from core.database import get_db_connection

###############################################################################
# FILA DE ESCRITA
###############################################################################

_WRITE_QUEUE: "queue.Queue[tuple[Callable[..., None], tuple[Any, ...], dict[str, Any]]]" = queue.Queue(maxsize=2000)
_WRITER_STARTED = threading.Event()


def _writer_loop() -> None:
    """Thread dedicada: espera conexão estar pronta e consome a fila."""
    conn = None
    while conn is None:
        try:
            conn = get_db_connection()
        except RuntimeError:
            time.sleep(0.1)  # espera core.database.set_connection
            continue

    cur = conn.cursor()
    print("[DB_WRITER] iniciado e conectado ao banco")

    while True:
        func, args, kwargs = _WRITE_QUEUE.get()
        try:
            func(cur, *args, **kwargs)
            conn.commit()
        except Exception as exc:
            print(f"[DB_WRITER] erro em {func.__name__}: {exc}")
            conn.rollback()
        finally:
            _WRITE_QUEUE.task_done()


def _ensure_writer_started():
    if not _WRITER_STARTED.is_set():
        threading.Thread(target=_writer_loop, name="db-writer", daemon=True).start()
        _WRITER_STARTED.set()

###############################################################################
# HELPERS DE ENFILEIRAMENTO
###############################################################################

def _enqueue(func: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    """Coloca tarefa na fila sem bloquear (descarta se cheia)."""
    _ensure_writer_started()
    try:
        _WRITE_QUEUE.put_nowait((func, args, kwargs))
    except queue.Full:
        print(f"[WARN] Fila DB cheia – descartando {func.__name__}")

###############################################################################
# FUNÇÕES SQL UNITÁRIAS – Recebem CURSOR
###############################################################################

def _save_ping(cur, data: dict) -> None:
    cur.execute(
        """
        INSERT INTO ping_results (ip, latency, online, status, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            data["ip"],
            data["latency"],
            data["online"],
            data["status"],
            data["timestamp"],
        ),
    )


def _save_engine_event(cur, ip: str, event_type: str, message: str, details: Any | None = None) -> None:
    cur.execute(
        """
        INSERT INTO engine_events (ip, event_type, message, details)
        VALUES (?, ?, ?, ?)
        """,
        (
            ip,
            event_type,
            message,
            json.dumps(details) if details else None,
        ),
    )


def _save_ip_profile(cur, ip: str, profile_dict: dict) -> None:
    cur.execute(
        """
        INSERT OR REPLACE INTO ip_profiles (ip, profile_json, last_update)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
        (
            ip,
            json.dumps(profile_dict),
        ),
    )


def _delete_server_data(cur, ip: str) -> None:
    cur.execute("DELETE FROM ping_results WHERE ip = ?", (ip,))
    cur.execute("DELETE FROM ip_profiles WHERE ip = ?", (ip,))
    cur.execute("DELETE FROM engine_events WHERE ip = ?", (ip,))

###############################################################################
# API PÚBLICA
###############################################################################
# Retro‑compatibilidade
###############################################################################

def create_profile_and_event_tables():
    """Alias legacy → mantido para código existente."""
    create_tables()

###############################################################################
###############################################################################

def create_tables() -> None:
    """Cria tabelas (sincrono) e garante que writer esteja ativo."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ping_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                latency REAL,
                online BOOLEAN,
                status TEXT,
                timestamp TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ip_profiles (
                ip TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS engine_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                event_type TEXT,
                message TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

    _ensure_writer_started()


def save_ping_result(data: dict) -> None:
    _enqueue(_save_ping, data)


def save_ip_profile(ip: str, profile_dict: dict) -> None:
    _enqueue(_save_ip_profile, ip, profile_dict)


def save_engine_event(ip: str, event_type: str, message: str, details: Any | None = None) -> None:
    _enqueue(_save_engine_event, ip, event_type, message, details)


def delete_server_data(ip: str) -> None:
    _enqueue(_delete_server_data, ip)

###############################################################################
# FUNÇÕES DE LEITURA (síncronas)
###############################################################################

def load_ip_profile(ip: str):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT profile_json FROM ip_profiles WHERE ip = ?", (ip,))
        row = c.fetchone()
        return json.loads(row[0]) if row else None


def load_all_ip_profiles():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT ip, profile_json FROM ip_profiles")
        return {ip: json.loads(profile) for ip, profile in c.fetchall()}
