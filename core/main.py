"""
main.py
=======
Ponto de entrada do InfraView.

Principais mudanças:
• A PasswordPrompt agora já carrega/gera o banco em RAM e registra a
  conexão global em core.database.set_connection(). main.py apenas
  precisa recuperar a senha para salvar o dump no encerramento.
• Não existe mais banco plaintext em disco.
"""     
import sys
import logging
from PyQt5.QtWidgets import QApplication, QDialog

from gui.password_prompt import PasswordPrompt
from gui.gui import MainWindow
from core.updater import verificar_e_atualizar
from core.engine_boot import launch_engine
from core.auth_manager import is_password_set
from core.db_protector import save_encrypted_dump
from core.database import get_db_connection

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)


def solicitar_senha() -> str | None:
    """
    Abre o diálogo de senha (modo criação ou desbloqueio) e
    devolve a senha inserida, ou None se o usuário cancelar.
    """
    prompt = PasswordPrompt(modo_criacao=not is_password_set())
    resultado = prompt.exec_()

    if resultado != QDialog.Accepted:
        return None
    return prompt.get_password()


def main() -> None:
    try:
        logger.info("Inicializando QApplication…")
        app = QApplication(sys.argv)

        # Etapa 1 – atualizar se necessário
        verificar_e_atualizar()

        # Etapa 2 – inicializar engine Go/ICMP (caso não esteja rodando)
        launch_engine()

        # Etapa 3 – diálogo de senha
        senha = solicitar_senha()
        if senha is None:
            logger.info("Aplicação encerrada: usuário cancelou a autenticação.")
            return

        # Etapa 4 – abrir GUI principal
        logger.info("Instanciando janela principal…")
        window = MainWindow()
        window.show()

        exit_code = app.exec_()

        # Etapa 5 – dump criptografado
        logger.info("Salvando dump criptografado antes de sair…")
        save_encrypted_dump(get_db_connection(), senha)

        sys.exit(exit_code)

    except Exception as exc:
        logger.exception("Erro crítico não tratado: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        input("\n[ERRO] Pressione ENTER para sair...")
