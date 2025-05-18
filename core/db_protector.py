"""
core/db_protector.py
--------------------
Responsável por:
• Descriptografar infra_encrypted.enc → criar conexão ':memory:'
• Gerar dump SQL da conexão em memória e salvar novamente criptografado

Criptografia: Fernet (symmetric + autenticidade)
A chave é derivada em core.auth_manager.get_fernet_key(password)
"""

from __future__ import annotations

import sqlite3
import os
from pathlib import Path
import logging

from cryptography.fernet import Fernet
from core.auth_manager import get_fernet_key

logger = logging.getLogger(__name__)

# Caminho FIXO do arquivo criptografado
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
ENC_PATH = DATA_DIR / "infra_encrypted.enc"


# =============================================================================
# Carregar banco em RAM
# =============================================================================
def load_into_memory(password: str) -> sqlite3.Connection:
    """
    • Se infra_encrypted.enc existir → descriptografa → executa SQL dump
    • Caso contrário → retorna conexão vazia ':memory:'
    """
    logger.debug("Carregando banco em memória a partir de %s", ENC_PATH.name)
    conn = sqlite3.connect(":memory:", check_same_thread=False)

    if not ENC_PATH.exists():
        logger.info("Nenhum arquivo .enc encontrado – criando banco novo em RAM.")
        return conn

    key = get_fernet_key(password)
    fernet = Fernet(key)

    encrypted_data = ENC_PATH.read_bytes()
    try:
        decrypted_bytes: bytes = fernet.decrypt(encrypted_data)
    except Exception as exc:
        logger.error("Falha ao descriptografar banco: %s", exc)
        raise ValueError("Senha incorreta ou dados corrompidos.") from exc

    sql_script = decrypted_bytes.decode("utf-8", errors="ignore")
    conn.executescript(sql_script)
    logger.info("Banco carregado na memória com sucesso.")
    return conn


# =============================================================================
# Persistir banco (dump → criptografa → grava .enc)
# =============================================================================
def _dump_sql(conn: sqlite3.Connection) -> bytes:
    """Retorna dump completo do banco em formato bytes (UTF-8)."""
    dump_text = "\n".join(conn.iterdump())
    return dump_text.encode("utf-8")


def save_encrypted_dump(conn: sqlite3.Connection, password: str) -> None:
    """
    Gera dump SQL do *conn*, criptografa com Fernet e sobrescreve infra_encrypted.enc.
    Nunca deixa arquivo temporário descriptografado no disco.
    """
    logger.debug("Salvando dump criptografado em %s", ENC_PATH.name)
    sql_bytes = _dump_sql(conn)
    if len(sql_bytes) < 10:
        raise ValueError("Dump SQL vazio ou inválido – nada foi salvo.")

    key = get_fernet_key(password)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(sql_bytes)

    tmp_path = ENC_PATH.with_suffix(".tmp")
    tmp_path.write_bytes(encrypted)
    os.replace(tmp_path, ENC_PATH)  # atomic move
    logger.info("Dump criptografado salvo com sucesso.")


# -----------------------------------------------------------------------------
# NÃO há função get_decrypted_db_path — banco plaintext não é mais gerado.
# -----------------------------------------------------------------------------
