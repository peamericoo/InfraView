# ping_engine/database_access.py
import json
from core.database import get_db_connection

def create_tables():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ping_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                latency REAL,
                online BOOLEAN,
                status TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()

def save_ping_result(data: dict):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ping_results (ip, latency, online, status, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data["ip"],
            data["latency"],
            data["online"],
            data["status"],
            data["timestamp"]
        ))
        conn.commit()

def create_profile_and_event_tables():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS ip_profiles (
                ip TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS engine_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                event_type TEXT,
                message TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def save_ip_profile(ip, profile_dict):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO ip_profiles (ip, profile_json, last_update)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (ip, json.dumps(profile_dict)))
        conn.commit()

def load_ip_profile(ip):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT profile_json FROM ip_profiles WHERE ip = ?", (ip,))
        row = c.fetchone()
        if row:
            return json.loads(row[0])
        return None

def load_all_ip_profiles():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT ip, profile_json FROM ip_profiles")
        profiles = {}
        for ip, profile_json in c.fetchall():
            profiles[ip] = json.loads(profile_json)
        return profiles

def save_engine_event(ip, event_type, message, details=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO engine_events (ip, event_type, message, details)
            VALUES (?, ?, ?, ?)
        """, (ip, event_type, message, json.dumps(details) if details else None))
        conn.commit()

def delete_server_data(ip):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Remove histórico de ping
        cursor.execute("DELETE FROM ping_results WHERE ip = ?", (ip,))
        # Remove perfil do IP
        cursor.execute("DELETE FROM ip_profiles WHERE ip = ?", (ip,))
        # Remove eventos da engine
        cursor.execute("DELETE FROM engine_events WHERE ip = ?", (ip,))
        conn.commit()
