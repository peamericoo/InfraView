from PyQt5.QtWidgets import (QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QStackedLayout, QWidget, QApplication)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QTimer
from core.db_protector import load_into_memory
import re
import logging
from core.auth_manager import (
    verificar_senha as validar_senha,
    criar_hash_senha
)
from core.password_reset import redefinir_senha
from core import database
import core
                      # ← para salvar .enc


logger = logging.getLogger("password_prompt")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("password_prompt.log")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def senha_valida_detalhada(s):
    return {
        'tamanho': len(s) >= 8,
        'maiuscula': bool(re.search(r"[A-Z]", s)),
        'minuscula': bool(re.search(r"[a-z]", s)),
        'especial': bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", s))
    }


class PasswordPrompt(QDialog):
    def __init__(self, modo_criacao=True, redefinindo=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Proteção por Senha - InfraView")
        self.resize(460, 320)
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #CCCCCC;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            QLineEdit {
                background-color: #2D2D30;
                color: white;
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton {
                background-color: #3A3A3A;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QLabel[title="true"] {
                font-size: 16pt;
                font-weight: bold;
                color: white;
            }
        """)

        self.modo_criacao = modo_criacao
        self.redefinindo = redefinindo
        self.resultado = None

        self.stack = QStackedLayout(self)

        if not modo_criacao:
            self.page_unlock = QWidget()
            layout_unlock = QVBoxLayout(self.page_unlock)
            layout_unlock.setSpacing(14)

            label = QLabel("Digite sua senha para desbloquear o banco:")
            label.setProperty("title", True)
            layout_unlock.addWidget(label)

            self.input_unlock = QLineEdit()
            self.input_unlock.setEchoMode(QLineEdit.Password)
            layout_unlock.addWidget(self.input_unlock)

            btn_unlock = QPushButton("Desbloquear")
            btn_unlock.clicked.connect(self.confirmar_desbloqueio)
            layout_unlock.addWidget(btn_unlock, alignment=Qt.AlignRight)

            self.btn_redefinir = QPushButton("Redefinir senha")
            self.btn_redefinir.clicked.connect(lambda: self.stack.setCurrentIndex(3))
            layout_unlock.addWidget(self.btn_redefinir, alignment=Qt.AlignCenter)

            self.stack.addWidget(self.page_unlock)

        else:
            self.page_intro = QWidget()
            layout_intro = QVBoxLayout(self.page_intro)
            layout_intro.setAlignment(Qt.AlignCenter)
            label_intro = QLabel("Bem-vindo ao InfraView\nVamos começar!")
            label_intro.setProperty("title", True)
            label_intro.setAlignment(Qt.AlignCenter)
            layout_intro.addWidget(label_intro)

            self.btn_proximo_intro = QPushButton("Próximo")
            self.btn_proximo_intro.clicked.connect(lambda: self.stack.setCurrentIndex(1))
            layout_intro.addWidget(self.btn_proximo_intro, alignment=Qt.AlignCenter)

            self.stack.addWidget(self.page_intro)

        self.page_senha = QWidget()
        layout_senha = QVBoxLayout(self.page_senha)
        layout_senha.setSpacing(10)

        label_senha = QLabel("Crie uma senha para proteger seu banco de dados:")
        label_senha.setProperty("title", True)
        layout_senha.addWidget(label_senha)

        self.input_senha = QLineEdit()
        self.input_senha.setEchoMode(QLineEdit.Password)
        self.input_senha.textChanged.connect(self.atualizar_validacao)
        layout_senha.addWidget(self.input_senha)

        self.requisitos = {
            'tamanho': QLabel("• Mínimo de 8 caracteres"),
            'maiuscula': QLabel("• Uma letra maiúscula"),
            'minuscula': QLabel("• Uma letra minúscula"),
            'especial': QLabel("• Um caractere especial (!@#$...)")
        }
        for lbl in self.requisitos.values():
            lbl.setStyleSheet("color: gray")
            layout_senha.addWidget(lbl)

        self.btn_proximo_senha = QPushButton("Próximo")
        self.btn_proximo_senha.clicked.connect(self.verificar_primeiro)
        layout_senha.addWidget(self.btn_proximo_senha, alignment=Qt.AlignRight)

        self.stack.addWidget(self.page_senha)

        self.page_confirmar = QWidget()
        layout_confirmar = QVBoxLayout(self.page_confirmar)
        layout_confirmar.setSpacing(10)

        label_conf = QLabel("Confirme sua nova senha:")
        label_conf.setProperty("title", True)
        layout_confirmar.addWidget(label_conf)

        self.input_confirmar = QLineEdit()
        self.input_confirmar.setEchoMode(QLineEdit.Password)
        layout_confirmar.addWidget(self.input_confirmar)

        self.btn_finalizar = QPushButton("Finalizar")
        self.btn_finalizar.clicked.connect(self.verificar_confirmacao)
        layout_confirmar.addWidget(self.btn_finalizar, alignment=Qt.AlignRight)

        self.stack.addWidget(self.page_confirmar)

        self.page_verificar_antiga = QWidget()
        layout_antiga = QVBoxLayout(self.page_verificar_antiga)

        label = QLabel("Para redefinir, informe sua senha atual:")
        label.setProperty("title", True)
        layout_antiga.addWidget(label)

        self.input_antiga = QLineEdit()
        self.input_antiga.setEchoMode(QLineEdit.Password)
        layout_antiga.addWidget(self.input_antiga)

        self.btn_verificar_antiga = QPushButton("Verificar")
        self.btn_verificar_antiga.clicked.connect(self.validar_antiga)
        layout_antiga.addWidget(self.btn_verificar_antiga, alignment=Qt.AlignRight)

        self.stack.addWidget(self.page_verificar_antiga)

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(300)
        screen_center = QApplication.desktop().screen().rect().center()
        self.move(screen_center - self.rect().center())
        self.anim.setStartValue(QRect(self.x(), self.y() - 20, self.width(), self.height()))
        self.anim.setEndValue(QRect(self.x(), self.y(), self.width(), self.height()))
        QTimer.singleShot(50, self.anim.start)

        if not modo_criacao:
            self.stack.setCurrentIndex(0)
        elif redefinindo:
            self.stack.setCurrentIndex(3)
        else:
            self.stack.setCurrentIndex(0)

    def atualizar_validacao(self):
        estados = senha_valida_detalhada(self.input_senha.text())
        for chave, estado in estados.items():
            cor = "lightgreen" if estado else "gray"
            self.requisitos[chave].setStyleSheet(f"color: {cor}")

    def verificar_primeiro(self):
        senha = self.input_senha.text().strip()
        validacoes = senha_valida_detalhada(senha)
        if not all(validacoes.values()):
            QMessageBox.warning(self, "Senha fraca", "A senha ainda não cumpre todos os requisitos.")
            return
        self.stack.setCurrentIndex(2)

    def verificar_confirmacao(self):
        senha = self.input_senha.text().strip()
        confirmacao = self.input_confirmar.text().strip()

        if senha != confirmacao:
            QMessageBox.warning(self, "Erro", "As senhas não coincidem.")
            self.input_senha.clear()
            self.input_confirmar.clear()
            self.stack.setCurrentIndex(1)
            return

        if self.redefinindo:
            try:
                conn = load_into_memory(self.old_password)
            except Exception:
                self.mostrar_erro("Não foi possível acessar o banco com a senha atual.")
                return


            sucesso = redefinir_senha(self.old_password, senha, conn)
            if not sucesso:
                self.mostrar_erro("Erro ao redefinir senha.")
                return

            # Recarrega banco com nova senha
            try:
                novo_conn = load_into_memory(senha)
                core.database._db = novo_conn
                from core.database import create_tables
                create_tables()
            except Exception as e:
                self.mostrar_erro("Erro ao recarregar banco após redefinir a senha.")
                return

        else:
            criar_hash_senha(senha)  # primeiro uso

        self.resultado = senha
        self.accept()
        logger.debug("[prompt] confirm. redefinindo=%s", self.redefinindo)


    def confirmar_desbloqueio(self):
        senha = self.input_unlock.text().strip()
        if not senha:
            QMessageBox.warning(self, "Erro", "Digite a senha para continuar.")
            return
        if not validar_senha(senha):
            QMessageBox.critical(self, "Erro", "Senha incorreta.")
            return
        self.resultado = senha
        self.accept()

    def validar_antiga(self):
        senha = self.input_antiga.text().strip()
        if not senha:
            QMessageBox.warning(self, "Erro", "Digite a senha atual.")
            return
        if not validar_senha(senha):
            QMessageBox.critical(self, "Erro", "Senha incorreta.")
            return

        # ✓ senha antiga correta
        self.old_password = senha            # ← guarda para re-cifrar
        self.redefinindo = True              # ← ativa modo redefinição
        self.stack.setCurrentIndex(1)        # segue p/ tela de nova senha
        logger.debug("[prompt] senha atual OK, segue redefinição")

    def get_password(self):
        return self.resultado

    # ---------- helper público -----------
    def mostrar_erro(self, msg: str):
        QMessageBox.critical(self, "Erro", msg)

