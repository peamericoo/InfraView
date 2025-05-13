# core/db_protector.py

import sqlite3
from pathlib import Path
from cryptography.fernet import Fernet
from core.auth_manager import get_fernet_key
import os
import logging

logger = logging.getLogger(__name__)

ENC_PATH = Path(__file__).resolve().parent.parent / "data" / "infra_encrypted.enc"

def load_into_memory(password: str) -> sqlite3.Connection:
    logger.debug("Carregando banco em memória a partir de .enc")
    key = get_fernet_key(password)
    fernet = Fernet(key)

    if not ENC_PATH.exists():
        logger.warning("Arquivo .enc não encontrado, criando banco vazio")
        return sqlite3.connect(":memory:", check_same_thread=False)

    with open(ENC_PATH, "rb") as f:
        encrypted_data = f.read()

    try:
        decrypted = fernet.decrypt(encrypted_data)
    except Exception as e:
        logger.error("Falha ao descriptografar banco: %s", e)
        raise ValueError("Senha incorreta ou dados corrompidos.")

    sql_script = decrypted.decode("utf-8", errors="ignore")

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript(sql_script)
    logger.info("Banco carregado em memória com sucesso.")
    return conn

def dump_from_memory(conn: sqlite3.Connection) -> bytes:
    logger.debug("Gerando dump SQL do banco em memória")
    dump = "\n".join(conn.iterdump()).encode("utf-8")
    return dump

def save_encrypted_dump(conn: sqlite3.Connection, password: str):
    logger.debug("Salvando banco criptografado em .enc")
    key = get_fernet_key(password)
    fernet = Fernet(key)

    sql_dump = dump_from_memory(conn)
    if len(sql_dump) < 10:
        raise ValueError("Dump SQL inválido ou vazio.")

    encrypted = fernet.encrypt(sql_dump)

    temp_path = ENC_PATH.with_suffix(".tmp")
    with open(temp_path, "wb") as f:
        f.write(encrypted)

    os.replace(temp_path, ENC_PATH)
    logger.info("Dump criptografado salvo com sucesso em %s", ENC_PATH)

# ✅ Adicionado para compatibilidade com a engine
def get_decrypted_db_path() -> Path:
    """
    Retorna o caminho físico do banco já descriptografado (em uso na RAM).
    """
    appdata = os.getenv('APPDATA') or os.getenv('LOCALAPPDATA')
    if not appdata:
        raise RuntimeError("APPDATA não localizado.")

    return Path(appdata) / "InfraView" / "infra.db"
