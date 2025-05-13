# ping_engine/database_access.py

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
