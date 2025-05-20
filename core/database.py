"""
core/database.py
----------------
ÚNICA fonte de verdade do banco de dados: uma conexão SQLite em memória
compartilhada pela aplicação inteira.

Como usar nos demais módulos:
    from core.database import get_db_connection, insert_server, ...

    conn = get_db_connection()   # devolve a mesma conexão ':memory:'
"""
from __future__ import annotations

import sqlite3
import json
from typing import Optional, List, Tuple, Dict, Any

# ———————————————————————————————————————————————————————————
# Conexão global em memória
# ———————————————————————————————————————————————————————————
_DB_CONN: Optional[sqlite3.Connection] = None


def set_connection(conn: sqlite3.Connection) -> None:
    """
    Chamado exatamente uma vez (logo depois de descriptografar ou criar o banco).
    """
    global _DB_CONN
    _DB_CONN = conn
    _enable_pragmas(conn)
    _create_tables_if_needed(conn)


def get_db_connection() -> sqlite3.Connection:
    """
    Retorna a conexão única em memória. Lança erro se ainda não inicializada.
    """
    if _DB_CONN is None:
        raise RuntimeError("Database connection has not been initialised.")
    return _DB_CONN


# ———————————————————————————————————————————————————————————
# Configurações de PRAGMA
# ———————————————————————————————————————————————————————————
def _enable_pragmas(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    # Tudo fica em memória; menos risco de corrupção e sem I/O extra
    cur.execute("PRAGMA journal_mode = MEMORY;")
    cur.execute("PRAGMA synchronous  = NORMAL;")
    cur.close()


# ———————————————————————————————————————————————————————————
# Criação de esquema
# ———————————————————————————————————————————————————————————
def _create_tables_if_needed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # ---- Pastas -------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name   TEXT UNIQUE NOT NULL,
            color  TEXT NOT NULL
        );
    """)

    # dentro de _create_tables_if_needed()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sefaz_status (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         DATETIME DEFAULT CURRENT_TIMESTAMP,
            doc_type   TEXT NOT NULL,          -- nfe | nfce
            status     TEXT NOT NULL,          -- cStat
            motivo     TEXT NOT NULL           -- xMotivo
        );
    """)

    # ---- Servidores ---------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS servers (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            ip        TEXT NOT NULL,
            folder_id INTEGER,
            status    TEXT NOT NULL DEFAULT 'running',
            FOREIGN KEY(folder_id) REFERENCES folders(id)
        );
    """)

    # ---- Logs ICMP / SNMP (exemplo) ------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ping_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id  INTEGER NOT NULL,
            latency_ms INTEGER,
            success    INTEGER,
            ts         DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(server_id) REFERENCES servers(id)
        );
    """)

    conn.commit()
    cur.close()


# Exposto apenas para casos especiais (ex.: migração de JSON)
def create_tables() -> None:
    """Garante que o schema exista (usa a conexão já inicializada)."""
    _create_tables_if_needed(get_db_connection())


# ======================================================================
# CRUD – FOLDERS
# ======================================================================
def insert_folder(name: str, color: str) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO folders (name, color) VALUES (?, ?);",
            (name, color)
        )
        conn.commit()


def get_all_folders() -> List[Dict[str, str]]:
    cur = get_db_connection().cursor()
    cur.execute("SELECT name, color FROM folders;")
    rows = cur.fetchall()
    cur.close()
    return [{"name": n, "color": c} for n, c in rows]


def update_folder_name_and_color(
    current_name: str,
    new_name: str | None = None,
    new_color: str | None = None
) -> None:
    if not (new_name or new_color):
        return  # Nada a atualizar

    fields, params = [], []
    if new_name:
        fields.append("name = ?")
        params.append(new_name)
    if new_color:
        fields.append("color = ?")
        params.append(new_color)

    params.append(current_name)
    query = f"UPDATE folders SET {', '.join(fields)} WHERE name = ?;"

    with get_db_connection() as conn:
        conn.execute(query, tuple(params))
        conn.commit()


def remove_folder_by_name(folder_name: str) -> None:
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM folders WHERE name = ?;", (folder_name,))
        res = cur.fetchone()
        if not res:
            return
        folder_id = res[0]
        cur.execute("UPDATE servers SET folder_id = NULL WHERE folder_id = ?;", (folder_id,))
        cur.execute("DELETE FROM folders WHERE id = ?;", (folder_id,))
        conn.commit()
        cur.close()


# ======================================================================
# CRUD – SERVERS
# ======================================================================
def insert_server(
    name: str,
    ip: str,
    folder_name: str | None = None,
    status: str = "running"
) -> None:
    with get_db_connection() as conn:
        cur = conn.cursor()
        folder_id = None
        if folder_name:
            cur.execute("SELECT id FROM folders WHERE name = ?;", (folder_name,))
            res = cur.fetchone()
            folder_id = res[0] if res else None

        cur.execute(
            "INSERT INTO servers (name, ip, status, folder_id) VALUES (?,?,?,?);",
            (name, ip, status, folder_id)
        )
        conn.commit()
        cur.close()


def get_all_servers() -> List[Tuple[Any, ...]]:
    cur = get_db_connection().cursor()
    cur.execute("""
        SELECT s.name, s.ip, s.status, f.name, f.color
          FROM servers s
     LEFT JOIN folders f ON s.folder_id = f.id;
    """)
    rows = cur.fetchall()
    cur.close()
    return rows


def update_server_info(
    current_name: str,
    new_name: str | None = None,
    new_ip: str | None = None,
    new_status: str | None = None
) -> None:
    if not (new_name or new_ip or new_status):
        return

    fields, params = [], []
    if new_name:
        fields.append("name = ?")
        params.append(new_name)
    if new_ip:
        fields.append("ip = ?")
        params.append(new_ip)
    if new_status:
        fields.append("status = ?")
        params.append(new_status)

    params.append(current_name)
    query = f"UPDATE servers SET {', '.join(fields)} WHERE name = ?;"

    with get_db_connection() as conn:
        conn.execute(query, tuple(params))
        conn.commit()


def update_server_folder(server_name: str, folder_name: str) -> None:
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM folders WHERE name = ?;", (folder_name,))
        res = cur.fetchone()
        if not res:
            return
        folder_id = res[0]
        cur.execute("UPDATE servers SET folder_id = ? WHERE name = ?;", (folder_id, server_name))
        conn.commit()
        cur.close()


def remove_server_by_name(server_name: str) -> str | None:
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT ip FROM servers WHERE name = ?;", (server_name,))
        res = cur.fetchone()
        if not res:
            return None
        ip = res[0]
        cur.execute("DELETE FROM servers WHERE name = ?;", (server_name,))
        conn.commit()
        cur.close()
        return ip


# ======================================================================
# Migração de JSON (opcional)
# ======================================================================
def migrate_from_json(json_path: str) -> None:
    with open(json_path, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    create_tables()

    for folder in data.get("folders", []):
        insert_folder(folder["name"], folder["color"])

    for server in data.get("servers", []):
        insert_server(
            server["name"],
            server["ip"],
            server.get("folder"),
            server.get("status", "running"),
        )

# core/database.py
def insert_sefaz_status(doc_type: str, status: str, motivo: str) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO sefaz_status (doc_type, status, motivo) VALUES (?,?,?);",
            (doc_type, status, motivo)
        )
        conn.commit()

def get_latest_sefaz_status(doc_type: str = "nfe") -> Optional[Tuple[str, str, str]]:
    cur = get_db_connection().cursor()
    cur.execute(
        "SELECT ts, status, motivo FROM sefaz_status "
        "WHERE doc_type = ? ORDER BY ts DESC LIMIT 1;",
        (doc_type,)
    )
    row = cur.fetchone()
    cur.close()
    return row
