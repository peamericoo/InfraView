from PyQt5.QtWidgets import (QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                             QHBoxLayout, QMessageBox, QStackedLayout, QWidget,
                             QApplication, QFrame, QToolButton, QStyle, QAction)

from PyQt5.QtGui import QFont, QColor, QPainter, QLinearGradient, QBrush, QIcon
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QAction, QSizePolicy
from PyQt5.QtCore import Qt, QPropertyAnimation, QAbstractAnimation, QRect, QTimer, QParallelAnimationGroup, QEasingCurve, QPoint
from core.db_protector import load_into_memory
import re
import random
import os
import logging
from core.auth_manager import verificar_senha as validar_senha, criar_hash_senha
from core.password_reset import redefinir_senha
from core.database import set_connection, create_tables     # NOVO
from core import database
import core

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
    ANIM_STYLE = "slide"
    def __init__(self, modo_criacao=True, redefinindo=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Proteção por Senha - InfraView")
        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
                font-family: 'Segoe UI';
                font-size: 17pt;
                color: #CCCCCC;
            }
            QLineEdit {
                background-color: #2C2C2C;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 8px;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #55AAFF;
            }
            QPushButton {
                background-color: #3A3F44;
                color: white;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5A5F66;
            }
            QLabel[title="true"] {
                font-size: 16pt;
                font-weight: bold;
                color: #FFFFFF;
            }
            QLabel {
                font-size: 10pt;
            }
        """)

        self.resize(500, 360)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)

        self.shadow_frame = QFrame()
        self.shadow_frame.setObjectName("shadowFrame")
        self.shadow_frame.setStyleSheet("""
            QFrame#shadowFrame {
                background-color: #1E1E1E;
                border-radius: 18px;
            }
        """)
        sombra = QGraphicsDropShadowEffect(self)
        sombra.setBlurRadius(30)
        sombra.setOffset(0, 0)
        sombra.setColor(QColor(0, 0, 0, 160))
        self.shadow_frame.setGraphicsEffect(sombra)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(30, 30, 30, 30)
        outer_layout.addWidget(self.shadow_frame)

        self.stack = QStackedLayout()
        self.stack.setStackingMode(QStackedLayout.StackAll)
        inner_layout = QVBoxLayout(self.shadow_frame)
        inner_layout.setContentsMargins(20, 20, 20, 20)
        inner_layout.addLayout(self.stack)

        self.modo_criacao = modo_criacao
        self.redefinindo = redefinindo
        self.resultado = None
        self._anims = []


        # Logging de inicialização
        logger.debug(f"[INIT] modo_criacao={self.modo_criacao}, redefinindo={self.redefinindo}")
        logger.debug(f"[INIT] Stack count = {self.stack.count()}")


        self.page_unlock = QWidget()
        layout_unlock = QVBoxLayout()
        self.page_unlock.setLayout(layout_unlock)
        layout_unlock.setContentsMargins(0, 20, 0, 0)   # topo uniforme
        layout_unlock.setSpacing(14)
        label_unlock = QLabel("Bem-vindo de volta! Digite sua chave para abrir o cofre:")
        label_unlock.setProperty("title", True)
        layout_unlock.addWidget(label_unlock)
        self.input_unlock = QLineEdit()
        self._attach_eye(self.input_unlock)
        layout_unlock.addWidget(self.input_unlock)
        btn_unlock = QPushButton("Desbloquear")
        btn_unlock.setDefault(True)  
        btn_unlock.clicked.connect(self.confirmar_desbloqueio)
        layout_unlock.addWidget(btn_unlock, alignment=Qt.AlignRight)
        btn_redefinir = QPushButton("Redefinir senha")
        btn_redefinir.clicked.connect(self.ativar_redefinicao) 
        layout_unlock.addWidget(btn_redefinir, alignment=Qt.AlignCenter)
        self.stack.addWidget(self.page_unlock)

        self.page_senha = QWidget()
        layout_senha = QVBoxLayout()
        self.page_senha.setLayout(layout_senha)
        layout_senha.setContentsMargins(0, 20, 0, 0)
        layout_senha.setSpacing(10)
        label_senha = QLabel("Crie sua chave-mestra para blindar seus dados:")
        label_senha.setProperty("title", True)
        layout_senha.addWidget(label_senha)
        self.input_senha = QLineEdit()
        self.input_senha.setEchoMode(QLineEdit.Password)
        self._attach_eye(self.input_senha)
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
        btn_proximo = QPushButton("Próximo")
        btn_proximo.clicked.connect(self.verificar_primeiro)          # única conexão
        self.input_senha.returnPressed.connect(btn_proximo.click)     # Enter → botão
        layout_senha.addWidget(btn_proximo, alignment=Qt.AlignRight)  # só um add

        self.stack.addWidget(self.page_senha)

        self.page_confirmar = QWidget()
        layout_conf = QVBoxLayout()
        self.page_confirmar.setLayout(layout_conf)
        layout_conf.setContentsMargins(0, 20, 0, 0)
        layout_conf.setSpacing(10)
        label_conf = QLabel("Repita a chave-mestra para garantir:")
        label_conf.setProperty("title", True)
        layout_conf.addWidget(label_conf)
        self.input_confirmar = QLineEdit()
        self.input_confirmar.setEchoMode(QLineEdit.Password)
        self._attach_eye(self.input_confirmar)
        layout_conf.addWidget(self.input_confirmar)
        btn_finalizar = QPushButton("Finalizar")
        btn_finalizar.clicked.connect(self.verificar_confirmacao)
        self.input_confirmar.returnPressed.connect(btn_finalizar.click)
        layout_conf.addWidget(btn_finalizar, alignment=Qt.AlignRight)

        self.stack.addWidget(self.page_confirmar)

        self.page_verificar_antiga = QWidget()
        layout_antiga = QVBoxLayout()
        layout_antiga.setSpacing(10)
        layout_antiga.setContentsMargins(0, 20, 0, 0)
        self.page_verificar_antiga.setLayout(layout_antiga)
        label_antiga = QLabel("Primeiro, confirme sua chave atual:")
        label_antiga.setProperty("title", True)
        layout_antiga.addWidget(label_antiga)
        self.input_antiga = QLineEdit()
        self.input_antiga.setEchoMode(QLineEdit.Password)
        self._attach_eye(self.input_antiga)
        layout_antiga.addWidget(self.input_antiga)
        btn_verificar_antiga = QPushButton("Verificar")
        btn_verificar_antiga.clicked.connect(self.validar_antiga)
        self.input_antiga.returnPressed.connect(btn_verificar_antiga.click)
        layout_antiga.addWidget(btn_verificar_antiga, alignment=Qt.AlignRight)

        self.stack.addWidget(self.page_verificar_antiga)

        self.page_intro = QWidget()
        layout_intro = QVBoxLayout()
        layout_intro.setContentsMargins(0, 20, 0, 0)   # mesmo topo
        layout_intro.setSpacing(14)
        self.page_intro.setLayout(layout_intro)

        label_intro = QLabel("Bem-vindo ao InfraView!\nVamos preparar sua segurança")
        label_intro.setProperty("title", True)
        layout_intro.addWidget(label_intro)

        btn_intro = QPushButton("Próximo")
        btn_intro.clicked.connect(lambda: self.mudar_pagina_animado(1))
        layout_intro.addWidget(btn_intro, alignment=Qt.AlignRight)

        self.stack.addWidget(self.page_intro)
        for i in range(self.stack.count()):
            w = self.stack.widget(i)
            if i != self.stack.currentIndex():
                w.hide()

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(300)
        screen_center = QApplication.desktop().screen().rect().center()
        self.move(screen_center - self.rect().center())
        self.anim.setStartValue(QRect(self.x(), self.y() - 20, self.width(), self.height()))
        self.anim.setEndValue(QRect(self.x(), self.y(), self.width(), self.height()))
        QTimer.singleShot(50, self.anim.start)

        if redefinindo:
            logger.debug("[INIT] Redefinindo senha: página 3 (verificar atual)")
            self.mudar_pagina_animado(3)
        elif not modo_criacao:
            logger.debug("[INIT] Senha já criada: página 0 (login)")
            self.mudar_pagina_animado(0)
        else:
            logger.debug("[INIT] Primeiro uso: página 4 (boas-vindas)")
            self.mudar_pagina_animado(4)

        self.gradient_start = QColor(30, 30, 60)
        self.gradient_end = QColor(60, 30, 30)
        self.gradient_target = self.gerar_cor_aleatoria()
        self.gradient_timer = QTimer(self)
        self.gradient_timer.timeout.connect(self.atualizar_degrade)
        self.gradient_timer.start(40)
        
        # ─── Bloqueia redimensionamento ───
        self.adjustSize()               # garante tamanho mínimo ideal
        self.setFixedSize(self.size())  # trava largura e altura

    # ---------- caixas de mensagem padronizadas ----------
    def _msgbox(self, icon: QMessageBox.Icon, titulo: str, texto: str):
        """
        QMessageBox dark:
        • Fundo #181818
        • Texto branco #FFF, Segoe UI 12 pt (aplicado a TODOS os QLabel internos)
        • Ícone 24 px alinhado
        • Botão OK centralizado
        """
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(titulo)
        box.setText(texto)
        box.setStandardButtons(QMessageBox.Ok)

        # ---------- estilo ----------
        box.setStyleSheet("""
            QMessageBox {
                background:#181818;
            }
            /* pega QUALQUER QLabel dentro da message-box                 */
            QMessageBox QLabel {
                color:#FFFFFF;
                font-family:"Segoe UI";
                font-size:12pt;
            }
            /* Ícone – reserva coluna fixa e centra                       */
            QLabel#qt_msgboxex_icon_label {
                min-width:24px; max-width:24px;
                qproperty-alignment: AlignVCenter | AlignHCenter;
            }
            /* Texto – leve deslocamento para não colar no ícone          */
            QLabel#qt_msgbox_label {
                margin-left:6px;
                qproperty-alignment: AlignVCenter | AlignLeft;
            }
            QPushButton {
                background:#32363A;
                color:#FFFFFF;
                border-radius:6px;
                padding:8px 26px;
                font-family:"Segoe UI";
                font-size:11pt;
                font-weight:bold;
            }
            QPushButton:hover  { background:#4A4E52; }
            QPushButton:pressed{ background:#2A2E32; }
        """)

        # Reduz o pixmap do ícone
        if icon != QMessageBox.NoIcon:
            pix = box.iconPixmap()
            if not pix.isNull():
                box.setIconPixmap(pix.scaled(24, 24, Qt.KeepAspectRatio,
                                             Qt.SmoothTransformation))

        # Centraliza o botão OK
        ok_btn = box.button(QMessageBox.Ok)
        ok_btn.setMinimumWidth(120)
        box.layout().setAlignment(ok_btn, Qt.AlignHCenter)

        # Sombra sutil
        eff = QGraphicsDropShadowEffect(box)
        eff.setBlurRadius(20)
        eff.setOffset(0, 4)
        eff.setColor(QColor(0, 0, 0, 160))
        box.setGraphicsEffect(eff)

        # ---------- força fonte/cor via fallback ----------
        for lbl in box.findChildren(QLabel):
            lbl.setStyleSheet(
                "color:#FFFFFF; font-family:'Segoe UI'; font-size:12pt;"
            )

        box.exec_()


    def warn(self, title: str, text: str):   # ⚠️
        self._msgbox(QMessageBox.Warning, title, text)

    def crit(self, title: str, text: str):   # ❌
        self._msgbox(QMessageBox.Critical, title, text)

    def ativar_redefinicao(self):
        logger.debug("[BTN] Botão 'Redefinir senha' clicado – ativando fluxo de redefinição")
        self.redefinindo = True
        self.old_password = None
        self.mudar_pagina_animado(3)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, self.gradient_start)
        gradient.setColorAt(1.0, self.gradient_end)

        brush = QBrush(gradient)

        # Pintar atrás do frame com base no tamanho real
        frame_geom = self.shadow_frame.geometry()
        rect = QRect(frame_geom.left(), frame_geom.top(), frame_geom.width(), frame_geom.height())
        rect = rect.adjusted(-30, -30, 30, 30)
        painter.fillRect(rect, brush)

        # ───────────────────────── olho (show/hide) ─────────────────────────
    def _attach_eye(self, line_edit: QLineEdit):
        """Adiciona ação trailing que alterna visibilidade da senha."""
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        eye_open   = QIcon(os.path.join(assets_dir, "eye_open.png"))
        eye_closed = QIcon(os.path.join(assets_dir, "eye_closed.png"))

        act = QAction(eye_closed, "Mostrar / ocultar senha", line_edit)
        act.setCheckable(True)

        def toggle(checked):
            line_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
            act.setIcon(eye_open if checked else eye_closed)

        act.toggled.connect(toggle)

        # alinhamento automático no lado direito
        line_edit.addAction(act, QLineEdit.TrailingPosition)
        line_edit.setEchoMode(QLineEdit.Password)

    def atualizar_validacao(self):
        estados = senha_valida_detalhada(self.input_senha.text())
        for chave, estado in estados.items():
            cor = "lightgreen" if estado else "gray"
            self.requisitos[chave].setStyleSheet(f"color: {cor}")

    def verificar_primeiro(self):
        senha = self.input_senha.text().strip()
        validacoes = senha_valida_detalhada(senha)
        if not all(validacoes.values()):
            self.warn("Senha fraca", "A senha ainda não cumpre…")
            return
        self.mudar_pagina_animado(2)

    def verificar_confirmacao(self):
        """Confere se as duas senhas digitadas coincidem
        e conclui criação / redefinição."""
        senha       = self.input_senha.text().strip()
        confirmacao = self.input_confirmar.text().strip()

        if senha != confirmacao:
            self.warn("Erro", "As senhas não coincidem.")
            self.input_senha.clear()
            self.input_confirmar.clear()
            self.mudar_pagina_animado(1)
            return

        # ---------------- criação ou redefinição ----------------
        if self.redefinindo:
            # Recarrega banco usando a senha antiga
            try:
                conn = load_into_memory(self.old_password)
            except Exception:
                self.crit("Erro", "Não foi possível acessar o banco com a senha atual.")
                return

            if not redefinir_senha(self.old_password, senha, conn):
                self.crit("Erro", "Falha ao redefinir a senha.")
                return

            # Reabre cofre com a nova senha
            try:
                novo_conn = load_into_memory(senha)
                set_connection(novo_conn)
                create_tables()
            except Exception:
                self.crit("Erro", "Erro ao recarregar banco após redefinir a senha.")
                return
        else:
            criar_hash_senha(senha)
            try:
                conn = load_into_memory(senha)
                set_connection(conn)
                create_tables()
            except Exception as e:
                self.crit("Erro", f"Erro ao criar banco inicial: {e}")
                return

        self.resultado = senha
        self.accept()

        logger.debug("[prompt] confirm. redefinindo=%s", self.redefinindo)


    def confirmar_desbloqueio(self):
        """Tenta abrir o cofre com a senha digitada."""
        senha = self.input_unlock.text().strip()

        if not senha:
            self.warn("Erro", "Digite a senha para continuar.")
            return
        if not validar_senha(senha):
            self.crit("Erro", "Senha incorreta.")
            return

        try:
            conn = load_into_memory(senha)
            set_connection(conn)
            create_tables()
        except Exception as e:
            self.crit("Erro", f"Falha ao abrir o banco: {e}")
            return

        self.resultado = senha
        self.accept()

    def validar_antiga(self):
        """Valida a senha atual antes de iniciar a redefinição."""
        senha = self.input_antiga.text().strip()

        if not senha:
            self.warn("Erro", "Digite a senha atual.")
            return
        if not validar_senha(senha):
            self.crit("Erro", "Senha incorreta.")
            return

        # senha antiga correta → continua fluxo
        self.old_password = senha
        self.redefinindo  = True
        self.mudar_pagina_animado(1)

    def get_password(self):
        return self.resultado

    # ---------- helper público -----------
    def mostrar_erro(self, msg: str):
        self.crit("Erro", msg)


    def gerar_cor_aleatoria(self):
        return QColor(
            random.randint(20, 60),
            random.randint(20, 60),
            random.randint(40, 80)
        )

    def atualizar_degrade(self):
        # Suavemente aproxima a cor alvo
        def interpolate(c1, c2, factor):
            return QColor(
                int(c1.red() + (c2.red() - c1.red()) * factor),
                int(c1.green() + (c2.green() - c1.green()) * factor),
                int(c1.blue() + (c2.blue() - c1.blue()) * factor)
            )

        self.gradient_start = interpolate(self.gradient_start, self.gradient_target, 0.01)
        self.gradient_end = interpolate(self.gradient_end, self.gradient_target, 0.01)

        # Quando chega perto, muda o alvo
        if all(abs(self.gradient_start.getRgb()[i] - self.gradient_target.getRgb()[i]) < 3 for i in range(3)):
            self.gradient_target = self.gerar_cor_aleatoria()

        self.update()

        # ───────────────── TRANSIÇÃO ENTRE PÁGINAS ──────────────────
    def mudar_pagina_animado(self, novo_indice: int):
        atual = self.stack.currentWidget()
        nova  = self.stack.widget(novo_indice)
        if atual is nova:
            return

        # Garante que a nova página comece “invisível”
        nova.setGraphicsEffect(None)

        # ----- CONFIGURAÇÕES COMUNS -----
        dur = 300

        if self.ANIM_STYLE == "crossfade":
            # Pré-aplica efeito 0-opacity à nova página
            eff_nova = QGraphicsOpacityEffect(nova)
            eff_nova.setOpacity(0.0)
            nova.setGraphicsEffect(eff_nova)

            eff_atual = QGraphicsOpacityEffect(atual)
            atual.setGraphicsEffect(eff_atual)

            fade_out = QPropertyAnimation(eff_atual, b"opacity", self)
            fade_out.setDuration(dur)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)

            fade_in = QPropertyAnimation(eff_nova, b"opacity", self)
            fade_in.setDuration(dur)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)

            grp = QParallelAnimationGroup(self)
            grp.addAnimation(fade_out)
            grp.addAnimation(fade_in)

            # Troca de página ANTES de iniciar ⇒ nada pisca
            self.stack.setCurrentWidget(nova)

            def _limpa():
                atual.setGraphicsEffect(None)
                nova.setGraphicsEffect(None)
                self._limpar_animacoes()
            grp.finished.connect(_limpa)
            grp.start()
            self._anims.append(grp)

        elif self.ANIM_STYLE == "slide":
            # ---------- CONFIG ---------
            dur   = 350                         # ms
            curve = QEasingCurve.InOutCubic     # curva suave

            # Direção: ▶ se avança, ◀ se volta
                        # --------------------------------------------------------
            # Ordem lógica do fluxo: 0 ➜ 3 ➜ 1 ➜ 2
            ordem_fluxo = [0, 3, 1, 2]
            idx_atual   = self.stack.currentIndex()
            try:
                forward = ordem_fluxo.index(novo_indice) > ordem_fluxo.index(idx_atual)
            except ValueError:
                # Se alguma das telas não estiver na lista,
                # cai no critério numérico como antes
                forward = novo_indice > idx_atual
            # --------------------------------------------------------

            direction = 1 if forward else -1    # +1 = dir→esq

            # Geometria base relativa ao shadow_frame (0,0,w,h)
            base_geom = atual.geometry()
            w, h      = base_geom.width(), base_geom.height()

            # Posições de entrada/saída
            geom_in  = base_geom.translated(direction * w, 0)
            geom_out = base_geom.translated(-direction * w, 0)

            # Deixa nova página visível sobre a antiga
            nova.setGeometry(geom_in)
            nova.show()
            nova.raise_()

            # ─── Animações ───
            move_out = QPropertyAnimation(atual, b"geometry", self)
            move_out.setDuration(dur)
            move_out.setEasingCurve(curve)
            move_out.setStartValue(base_geom)
            move_out.setEndValue(geom_out)

            move_in  = QPropertyAnimation(nova, b"geometry", self)
            move_in.setDuration(dur)
            move_in.setEasingCurve(curve)
            move_in.setStartValue(geom_in)
            move_in.setEndValue(base_geom)

            grp = QParallelAnimationGroup(self)
            grp.addAnimation(move_out)
            grp.addAnimation(move_in)

            def _fim_slide():
                # nova passa a ser corrente; antiga some
                self.stack.setCurrentWidget(nova)
                atual.hide()
                self._limpar_animacoes()

            grp.finished.connect(_fim_slide)
            grp.start()
            self._anims.append(grp)



        elif self.ANIM_STYLE == "zoom":
            # Aplica efeito de opacidade + scale na nova página
            eff_nova = QGraphicsOpacityEffect(nova)
            eff_nova.setOpacity(0.0)
            nova.setGraphicsEffect(eff_nova)
            self.stack.setCurrentWidget(nova)

            fade_in = QPropertyAnimation(eff_nova, b"opacity", self)
            fade_in.setDuration(dur)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)

            geom_init = nova.geometry()
            geom_zoom = QRect(
                geom_init.center().x(), geom_init.center().y(),
                0, 0
            )

            zoom_anim = QPropertyAnimation(nova, b"geometry", self)
            zoom_anim.setDuration(dur)
            zoom_anim.setStartValue(geom_zoom)
            zoom_anim.setEndValue(geom_init)

            grp = QParallelAnimationGroup(self)
            grp.addAnimation(fade_in)
            grp.addAnimation(zoom_anim)

            grp.finished.connect(lambda: nova.setGraphicsEffect(None))
            grp.finished.connect(self._limpar_animacoes)
            grp.start()
            self._anims.append(grp)

        else:
            # Fallback instantâneo
            self.stack.setCurrentWidget(nova)

            # ───────────────────────── helper interno ─────────────────────────
    def _limpar_animacoes(self):
        """Remove referências a animações já finalizadas para
        evitar vazamento de memória e manter a lista _anims enxuta."""
        self._anims = [
            a for a in self._anims
            if a.state() != QAbstractAnimation.Stopped
        ]



    # ──────────────────────────────────────────────────────────────
    # DEBUG ▸ Loga posição/tamanho dos widgets 1 s após abrir diálogo
    def logar_componentes_visuais(self):
        try:
            logger.debug(
                "[input_unlock] Pos=(%d, %d) Size=(%dx%d)",
                self.input_unlock.x(), self.input_unlock.y(),
                self.input_unlock.width(), self.input_unlock.height()
            )
            logger.debug(
                "[input_senha] Pos=(%d, %d) Size=(%dx%d)",
                self.input_senha.x(), self.input_senha.y(),
                self.input_senha.width(), self.input_senha.height()
            )
            logger.debug(
                "[input_confirmar] Pos=(%d, %d) Size=(%dx%d)",
                self.input_confirmar.x(), self.input_confirmar.y(),
                self.input_confirmar.width(), self.input_confirmar.height()
            )
            logger.debug(
                "[input_antiga] Pos=(%d, %d) Size=(%dx%d)",
                self.input_antiga.x(), self.input_antiga.y(),
                self.input_antiga.width(), self.input_antiga.height()
            )
        except Exception as e:
            # Caso algum componente ainda não exista,
            # evita crash e registra o motivo
            logger.warning("Falha ao logar componentes: %s", e)
  

    