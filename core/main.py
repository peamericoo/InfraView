# main.py
import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from gui.password_prompt import PasswordPrompt
from gui.gui import MainWindow
from core.updater import verificar_e_atualizar
from core.auth_manager import is_password_set, criar_hash_senha, verificar_senha
from core.db_protector import load_into_memory
import core.database as database
from core.engine_boot import launch_engine  # novo

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

def solicitar_senha():
    if is_password_set():
        prompt = PasswordPrompt(modo_criacao=False)
    else:
        prompt = PasswordPrompt(modo_criacao=True)

    resultado = prompt.exec_()
    if resultado != prompt.Accepted:
        return None

    senha = prompt.get_password()
    return senha

def main():
    try:
        print("Inicializando QApplication...")
        app = QApplication(sys.argv)

        # Verifica atualizações
        verificar_e_atualizar()

        # Inicia a engine Go, se necessário
        launch_engine()

        # Prompt de senha (criar ou autenticar)
        senha = solicitar_senha()
        if not senha:
            print("A inicialização foi cancelada pelo usuário.")
            return

        # Carrega o banco em memória
        conn = load_into_memory(senha)
        database._db = conn

        # Garante criação das tabelas se for primeira execução
        from core.database import create_tables
        create_tables()

        print("Instanciando MainWindow...")
        window = MainWindow()
        print("MainWindow instanciado.")

        window.show()
        print("Janela exibida. Executando app...")
        app.exec_()

        print("Salvando banco antes de encerrar...")
        from core.db_protector import save_encrypted_dump
        save_encrypted_dump(database.get_db_connection(), senha)

        print("Aplicação encerrada com sucesso.")

    except Exception as e:
        print(f"Erro durante a execução: {e}")
        logger.exception("Erro crítico em main.py")

if __name__ == "__main__":
    main()