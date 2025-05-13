import sqlite3
from pathlib import Path
import json
import os
import sys
import shutil
from core.db_protector import get_decrypted_db_path

# ========================
# Gerenciamento do caminho
# ========================
def get_executable_folder():
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

def get_db_path():
    appdata = os.getenv('APPDATA') or os.getenv('LOCALAPPDATA')
    if not appdata:
        raise RuntimeError("Não foi possível localizar o APPDATA.")

    infraview_folder = Path(appdata) / "InfraView"
    infraview_folder.mkdir(exist_ok=True)

    db_path = infraview_folder / "infra.db"

    if not db_path.exists():
        try:
            source_db = get_executable_folder() / "data" / "infra.db"
            shutil.copy(source_db, db_path)
        except Exception as e:
            print(f"Erro ao copiar infra.db inicial: {e}")

    return db_path

# ========================
# Nova conexão padrão
# ========================
_db = None

def get_db_connection():
    return sqlite3.connect(get_decrypted_db_path(), check_same_thread=False)


# ========================
# Criação de Tabelas
# ========================
def create_tables():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ip TEXT NOT NULL,
                folder_id INTEGER,
                status TEXT NOT NULL DEFAULT 'running',
                FOREIGN KEY(folder_id) REFERENCES folders(id)
            )
        ''')
        conn.commit()

# ========================
# Funções para Pastas
# ========================
def insert_folder(name, color):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO folders (name, color) VALUES (?, ?)", (name, color))
        conn.commit()

def get_all_folders():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name, color FROM folders")
        rows = c.fetchall()
        return [{"name": row[0], "color": row[1]} for row in rows]

def update_folder_name_and_color(current_name, new_name=None, new_color=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        update_fields = []
        params = []

        if new_name:
            update_fields.append("name = ?")
            params.append(new_name)

        if new_color:
            update_fields.append("color = ?")
            params.append(new_color)

        if not update_fields:
            return  # Nada a atualizar

        query = f"UPDATE folders SET {', '.join(update_fields)} WHERE name = ?"
        params.append(current_name)
        c.execute(query, tuple(params))
        conn.commit()

def remove_folder_by_name(folder_name):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
        result = c.fetchone()
        if result:
            folder_id = result[0]
            c.execute("UPDATE servers SET folder_id = NULL WHERE folder_id = ?", (folder_id,))
            c.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
            conn.commit()

# ========================
# Funções para Servidores
# ========================
def insert_server(name, ip, folder_name=None, status="running"):
    with get_db_connection() as conn:
        c = conn.cursor()
        folder_id = None
        if folder_name:
            c.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
            result = c.fetchone()
            folder_id = result[0] if result else None
        c.execute("INSERT INTO servers (name, ip, status, folder_id) VALUES (?, ?, ?, ?)",
                  (name, ip, status, folder_id))
        conn.commit()

def get_all_servers():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT s.name, s.ip, s.status, f.name, f.color
            FROM servers s
            LEFT JOIN folders f ON s.folder_id = f.id
        """)
        return c.fetchall()

def update_server_info(current_name, new_name=None, new_ip=None, new_status=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        update_fields = []
        params = []

        if new_name:
            update_fields.append("name = ?")
            params.append(new_name)

        if new_ip:
            update_fields.append("ip = ?")
            params.append(new_ip)

        if new_status:
            update_fields.append("status = ?")
            params.append(new_status)

        if not update_fields:
            return  # Nada a atualizar

        query = f"UPDATE servers SET {', '.join(update_fields)} WHERE name = ?"
        params.append(current_name)
        c.execute(query, tuple(params))
        conn.commit()

def update_server_folder(server_name, folder_name):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
        result = c.fetchone()
        if result:
            folder_id = result[0]
            c.execute("UPDATE servers SET folder_id = ? WHERE name = ?", (folder_id, server_name))
            conn.commit()

def remove_server_by_name(server_name):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM servers WHERE name = ?", (server_name,))
        affected = c.rowcount
        conn.commit()
        return affected > 0

# ========================
# Migração a partir de JSON
# ========================
def migrate_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    create_tables()

    for folder in data.get("folders", []):
        insert_folder(folder["name"], folder["color"])

    for server in data.get("servers", []):
        insert_server(server["name"], server["ip"], server.get("folder"), server.get("status", "running"))
