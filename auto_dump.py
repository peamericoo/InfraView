# auto_dump.py
"""
Gera automaticamente um dump SQL do banco em RAM após `delay` segundos.
O arquivo é salvo como dump_YYYYMMDD_HHMMSS.sql na própria pasta do projeto.
"""

import threading
from datetime import datetime
import logging

log = logging.getLogger("auto_dump")

def _do_dump():
    try:
        from core.database import get_db_connection
        conn = get_db_connection()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"dump_{timestamp}.sql"

        with open(path, "w", encoding="utf-8") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")

        log.info("[AUTO_DUMP] Dump salvo em %s", path)
    except Exception as e:
        log.error("[AUTO_DUMP] Falha ao gerar dump: %s", e)

def schedule_dump(delay: int = 10):
    """
    Agende no ponto em que o banco já está inicializado:
        import auto_dump
        auto_dump.schedule_dump(10)   # 10 s
    """
    t = threading.Timer(delay, _do_dump)
    t.daemon = True   # não impede o app de fechar
    t.start()
