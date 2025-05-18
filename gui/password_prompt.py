"""
gui/password_prompt.py
----------------------
Diálogo de criação/desbloqueio da chave-mestra.

Novidades desta versão:
• Após validar/criar a senha, carregamos o banco em RAM com
  core.db_protector.load_into_memory() e registramos a conexão
  única via core.database.set_connection().
• Qualquer tentativa posterior de abrir/usar o banco deve passar
  por core.database.get_db_connection().
"""
from __future__ import annotations

import os, re, random, logging
from pathlib import Path

from PyQt5.QtCore import (
    Qt, QTimer, QRect, QEasingCurve, QParallelAnimationGroup,
    QPropertyAnimation, QPoint, QAbstractAnimation
)
from PyQt5.QtGui  import (
    QPainter, QColor, QBrush, QLinearGradient, QIcon, QFont
)
from PyQt5.QtWidgets import (
    QApplication, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QStackedLayout, QWidget, QFrame, QAction, QSizePolicy
)

from core.db_protector import load_into_memory
from core.auth_manager import (
    verificar_senha  as validar_senha,
    criar_hash_senha
)
from core.password_reset import redefinir_senha

#  — novos imports p/ registrar a conexão —
from core.database import set_connection, create_tables

logger = logging.getLogger("password_prompt")
logger.setLevel(logging.DEBUG)
log_path = Path(__file__).with_name("password_prompt.log")
handler = logging.FileHandler(log_path)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s - %(message)s"))
logger.addHandler(handler)


# ───────────────────────────────────────────────────────────────
#  Utilidades
# ───────────────────────────────────────────────────────────────
def senha_valida_detalhada(s: str) -> dict[str, bool]:
    return {
        "tamanho": len(s) >= 8,
        "maiuscula": bool(re.search(r"[A-Z]", s)),
        "minuscula": bool(re.search(r"[a-z]", s)),
        "especial": bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", s)),
    }


# ───────────────────────────────────────────────────────────────
#  Diálogo principal
# ───────────────────────────────────────────────────────────────
class PasswordPrompt(QDialog):
    ANIM_STYLE = "slide"  # slide | crossfade | zoom

    def __init__(self, modo_criacao: bool = True, redefinindo: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Proteção por Senha – InfraView")

        # ─── estilo geral dark ───
        self.setStyleSheet("""
            QDialog { background: transparent; font-family:'Segoe UI'; font-size:10pt; color:#CCC; }
            QLineEdit { background:#2C2C2C; border:1px solid #444; border-radius:8px; padding:8px; color:white; }
            QLineEdit:focus { border:1px solid #55AAFF; }
            QPushButton { background:#3A3F44; color:white; border-radius:6px; padding:8px 20px; font-weight:bold; }
            QPushButton:hover { background:#5A5F66; }
            QLabel[title="true"] { font-size:16pt; font-weight:bold; color:#FFF; }
            QLabel { font-size:10pt; }
        """)

        self.resize(500, 360)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )

        #  — shadow frame —
        self.shadow_frame = QFrame(objectName="shadowFrame")
        self.shadow_frame.setStyleSheet("QFrame#shadowFrame{background:#1E1E1E;border-radius:18px;}")
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(30); eff.setOffset(0, 0); eff.setColor(QColor(0, 0, 0, 160))
        self.shadow_frame.setGraphicsEffect(eff)

        lay_outer = QVBoxLayout(self); lay_outer.setContentsMargins(30, 30, 30, 30)
        lay_outer.addWidget(self.shadow_frame)

        self.stack = QStackedLayout()
        lay_inner = QVBoxLayout(self.shadow_frame)
        lay_inner.setContentsMargins(20, 20, 20, 20)
        lay_inner.addLayout(self.stack)

        # estado
        self.modo_criacao = modo_criacao
        self.redefinindo  = redefinindo
        self.resultado: str | None = None
        self.old_password: str | None = None
        self._anims: list[QAbstractAnimation] = []

        logger.debug("[INIT] modo_criacao=%s redefinindo=%s", modo_criacao, redefinindo)

        # ───────────────────── páginas ─────────────────────
        # (1) Tela de desbloqueio
        self.page_unlock, self.input_unlock = self._build_unlock_page()
        self.stack.addWidget(self.page_unlock)

        # (2) Criar senha inicial
        self.page_senha, self.input_senha, self.requisitos = self._build_new_password_page()
        self.stack.addWidget(self.page_senha)

        # (3) Confirmar nova senha
        self.page_confirmar, self.input_confirmar = self._build_confirm_page()
        self.stack.addWidget(self.page_confirmar)

        # (4) Verificar senha antiga (para redefinir)
        self.page_antiga, self.input_antiga = self._build_old_password_page()
        self.stack.addWidget(self.page_antiga)

        # (5) Boas-vindas da primeira execução
        self.page_intro = self._build_intro_page()
        self.stack.addWidget(self.page_intro)

        #  — tela inicial conforme modo —
        if redefinindo:
            self._switch_page(3)
        elif not modo_criacao:
            self._switch_page(0)
        else:
            self._switch_page(4)

        # animação de entrada
        self._fade_in()

        # bloqueia redimensionamento
        self.adjustSize(); self.setFixedSize(self.size())

    # ───────────────────────────────────────────────────────────
    #  Construção das páginas
    # ───────────────────────────────────────────────────────────
    def _build_unlock_page(self):
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(0, 20, 0, 0); lay.setSpacing(14)
        lbl = QLabel("Bem-vindo de volta! Digite sua chave para abrir o cofre:"); lbl.setProperty("title", True)
        lay.addWidget(lbl)
        inp = QLineEdit(); self._attach_eye(inp); inp.returnPressed.connect(self.confirmar_desbloqueio)
        lay.addWidget(inp)
        btn = QPushButton("Desbloquear"); btn.clicked.connect(self.confirmar_desbloqueio); lay.addWidget(btn, alignment=Qt.AlignRight)
        btn_reset = QPushButton("Redefinir senha"); btn_reset.clicked.connect(self.ativar_redefinicao); lay.addWidget(btn_reset, alignment=Qt.AlignCenter)
        return page, inp

    def _build_new_password_page(self):
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(0, 20, 0, 0); lay.setSpacing(10)
        lbl = QLabel("Crie sua chave-mestra para blindar seus dados:"); lbl.setProperty("title", True); lay.addWidget(lbl)
        inp = QLineEdit(echoMode=QLineEdit.Password); self._attach_eye(inp); inp.returnPressed.connect(self.verificar_primeiro); inp.textChanged.connect(self.atualizar_validacao)
        lay.addWidget(inp)
        reqs = {
            'tamanho':   QLabel("• Mínimo de 8 caracteres"),
            'maiuscula': QLabel("• Uma letra maiúscula"),
            'minuscula': QLabel("• Uma letra minúscula"),
            'especial':  QLabel("• Um caractere especial (!@#$...)")
        }
        for l in reqs.values(): l.setStyleSheet("color:gray"); lay.addWidget(l)
        btn = QPushButton("Próximo"); btn.clicked.connect(self.verificar_primeiro); lay.addWidget(btn, alignment=Qt.AlignRight)
        return page, inp, reqs

    def _build_confirm_page(self):
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(0, 20, 0, 0); lay.setSpacing(10)
        lbl = QLabel("Repita a chave-mestra para garantir:"); lbl.setProperty("title", True); lay.addWidget(lbl)
        inp = QLineEdit(echoMode=QLineEdit.Password); self._attach_eye(inp); inp.returnPressed.connect(self.verificar_confirmacao)
        lay.addWidget(inp)
        btn = QPushButton("Finalizar"); btn.clicked.connect(self.verificar_confirmacao); lay.addWidget(btn, alignment=Qt.AlignRight)
        return page, inp

    def _build_old_password_page(self):
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(0, 20, 0, 0); lay.setSpacing(10)
        lbl = QLabel("Primeiro, confirme sua chave atual:"); lbl.setProperty("title", True); lay.addWidget(lbl)
        inp = QLineEdit(echoMode=QLineEdit.Password); self._attach_eye(inp); inp.returnPressed.connect(self.validar_antiga)
        lay.addWidget(inp)
        btn = QPushButton("Verificar"); btn.clicked.connect(self.validar_antiga); lay.addWidget(btn, alignment=Qt.AlignRight)
        return page, inp

    def _build_intro_page(self):
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(0, 20, 0, 0); lay.setSpacing(14)
        lbl = QLabel("Bem-vindo ao InfraView!\nVamos preparar sua segurança"); lbl.setProperty("title", True); lay.addWidget(lbl)
        btn = QPushButton("Próximo"); btn.clicked.connect(lambda: self._switch_page(1)); lay.addWidget(btn, alignment=Qt.AlignRight)
        return page

    # ───────────────────────────────────────────────────────────
    #  Helpers de UI
    # ───────────────────────────────────────────────────────────
    def _attach_eye(self, le: QLineEdit):
        """Adiciona botão para mostrar/ocultar senha."""
        assets = Path(__file__).parent.parent / "assets"
        eye_open_path   = assets / "eye_open.png"
        eye_closed_path = assets / "eye_closed.png"

        eye_open   = QIcon(str(eye_open_path))
        eye_closed = QIcon(str(eye_closed_path))

        act = QAction(eye_closed, "Mostrar/ocultar", le)
        act.setCheckable(True)

        def toggle(chk: bool):
            le.setEchoMode(QLineEdit.Normal if chk else QLineEdit.Password)
            act.setIcon(eye_open if chk else eye_closed)

        act.toggled.connect(toggle)
        le.addAction(act, QLineEdit.TrailingPosition)
    
        # ───────────────────────────────────────────────────────────
    #  Acionada pelo botão “Redefinir senha” na tela de desbloqueio
    # ───────────────────────────────────────────────────────────
    def ativar_redefinicao(self):
        """
        Entra no fluxo de redefinição:
        1) marca self.redefinindo = True
        2) exibe a página que solicita a senha antiga (page_antiga)
        """
        self.redefinindo = True
        self._switch_page(3)   # índice da page_antiga


    def _fade_in(self):
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(300)
        center = QApplication.desktop().screen().rect().center()
        self.move(center - self.rect().center())
        anim.setStartValue(QRect(self.x(), self.y() - 20, self.width(), self.height()))
        anim.setEndValue(QRect(self.x(), self.y(),     self.width(), self.height()))
        QTimer.singleShot(50, anim.start)

    # — mudança de página com animação simples (sem repetir todo o código anterior) —
    def _switch_page(self, idx: int):
        for i in range(self.stack.count()):
            w = self.stack.widget(i)
            w.setVisible(i == idx)
        self.stack.setCurrentIndex(idx)

    # ───────────────────────────────────────────────────────────
    #  Fluxo de validação / criação / desbloqueio
    # ───────────────────────────────────────────────────────────
    def _inicializar_db(self, password: str) -> bool:
        """
        • Descriptografa (ou cria) o banco em RAM
        • Registra a conexão global para toda a aplicação
        """
        try:
            conn = load_into_memory(password)
            set_connection(conn)
            create_tables()
            logger.info("Banco em memória inicializado.")
            return True
        except Exception as exc:
            logger.error("Falha ao inicializar DB: %s", exc)
            self.mostrar_erro("Erro ao abrir o banco. Senha incorreta ou dados corrompidos.")
            return False

    # — etapas —
    def confirmar_desbloqueio(self):
        senha = self.input_unlock.text().strip()
        if not senha:
            self.mostrar_erro("Digite a senha.")
            return
        if not validar_senha(senha):
            self.mostrar_erro("Senha incorreta.")
            return
        if not self._inicializar_db(senha):
            return
        self.resultado = senha
        self.accept()

    def verificar_primeiro(self):
        senha = self.input_senha.text().strip()
        if not all(senha_valida_detalhada(senha).values()):
            self.mostrar_erro("A senha ainda não cumpre todos os requisitos.")
            return
        self._switch_page(2)

    def verificar_confirmacao(self):
        senha = self.input_senha.text().strip()
        if senha != self.input_confirmar.text().strip():
            self.mostrar_erro("As senhas não coincidem.")
            self.input_senha.clear(); self.input_confirmar.clear(); self._switch_page(1); return

        if self.redefinindo:
            # redefine hash + recifra DB existente
            if not self.old_password:
                self.mostrar_erro("Senha atual não confirmada."); return
            conn_old = load_into_memory(self.old_password)
            if not redefinir_senha(self.old_password, senha, conn_old):
                self.mostrar_erro("Erro ao redefinir a senha."); return

        else:
            criar_hash_senha(senha)   # primeira execução

        if not self._inicializar_db(senha):
            return
        self.resultado = senha
        self.accept()

    def validar_antiga(self):
        senha = self.input_antiga.text().strip()
        if not senha or not validar_senha(senha):
            self.mostrar_erro("Senha incorreta."); return
        self.old_password = senha
        self.redefinindo  = True
        self._switch_page(1)

    # ───────────────────────────────────────────────────────────
    #  Utilidades menores
    # ───────────────────────────────────────────────────────────
    def atualizar_validacao(self):
        estados = senha_valida_detalhada(self.input_senha.text())
        for chave, ok in estados.items():
            cor = "lightgreen" if ok else "gray"
            self.requisitos[chave].setStyleSheet(f"color:{cor}")

    def mostrar_erro(self, msg: str):
        QMessageBox.critical(self, "Erro", msg)

    def get_password(self):
        return self.resultado
