# core/password_reset.py
import os
import logging
from core.auth_manager import verificar_senha, criar_hash_senha, get_fernet_key
from core.db_protector import dump_from_memory
from pathlib import Path
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)
ENC_PATH = Path(__file__).resolve().parent.parent / "data" / "infra_encrypted.enc"

def redefinir_senha(senha_atual: str, nova_senha: str, conn) -> bool:
    try:
        logger.info("Iniciando processo de redefinição de senha...")

        if not verificar_senha(senha_atual):
            logger.warning("Senha atual incorreta.")
            return False

        logger.debug("Senha atual verificada com sucesso.")

        # Regerar salt + hash e salvar novo auth.json
        criar_hash_senha(nova_senha)
        logger.debug("Novo hash e salt gerados com sucesso.")

        # Dump do banco atual
        sql_dump = dump_from_memory(conn)
        if len(sql_dump) < 10:
            logger.error("Dump SQL insuficiente, abortando.")
            return False

        # Criptografar com nova senha
        nova_chave = get_fernet_key(nova_senha)
        fernet = Fernet(nova_chave)
        encrypted_dump = fernet.encrypt(sql_dump)

        # Substituição atômica
        temp_path = ENC_PATH.with_suffix(".tmp")
        with open(temp_path, "wb") as f:
            f.write(encrypted_dump)
        os.replace(temp_path, ENC_PATH)

        logger.info("Redefinição de senha concluída com sucesso.")
        return True

    except Exception as e:
        logger.exception("Erro durante redefinição de senha:")
        return False
