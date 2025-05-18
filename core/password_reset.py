"""
core/password_reset.py
----------------------
Fluxo de redefinição de senha:
1. Valida senha atual
2. Gera novo hash + salt (auth.json)
3. Dump completo do banco em RAM (conn.iterdump())
4. Criptografa com a chave derivada da nova senha
5. Sobrescreve data/infra_encrypted.enc de forma atômica
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from cryptography.fernet import Fernet

from core.auth_manager import (
    verificar_senha,
    criar_hash_senha,
    get_fernet_key
)

logger = logging.getLogger(__name__)

# Caminho fixo do arquivo .enc
ENC_PATH = Path(__file__).resolve().parent.parent / "data" / "infra_encrypted.enc"


# ---------------------------------------------------------------------------
def _dump_sql_bytes(conn) -> bytes:
    """Retorna dump SQL completo do banco em bytes UTF-8."""
    dump_text = "\n".join(conn.iterdump())
    return dump_text.encode("utf-8")


def redefinir_senha(senha_atual: str, nova_senha: str, conn) -> bool:
    """
    • Valida a senha atual
    • Escreve novo auth.json (novo hash + salt)
    • Re-criptografa o banco com a nova senha
    """
    try:
        logger.info("Iniciando processo de redefinição de senha…")

        if not verificar_senha(senha_atual):
            logger.warning("Senha atual incorreta.")
            return False
        logger.debug("Senha atual verificada com sucesso.")

        # 1) Gera novo hash/salt e grava auth.json
        criar_hash_senha(nova_senha)
        logger.debug("Novo hash e salt gerados.")

        # 2) Dump do banco em memória
        sql_bytes = _dump_sql_bytes(conn)
        if len(sql_bytes) < 10:
            logger.error("Dump SQL insuficiente, abortando.")
            return False

        # 3) Criptografa dump com a nova chave
        fernet = Fernet(get_fernet_key(nova_senha))
        encrypted_dump = fernet.encrypt(sql_bytes)

        # 4) Escritura atômica do novo .enc
        temp_path = ENC_PATH.with_suffix(".tmp")
        temp_path.write_bytes(encrypted_dump)
        os.replace(temp_path, ENC_PATH)

        logger.info("Redefinição de senha concluída com sucesso.")
        return True

    except Exception as exc:
        logger.exception("Erro durante redefinição de senha: %s", exc)
        return False
