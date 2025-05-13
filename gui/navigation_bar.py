import os
import logging
from PyQt5.QtWidgets import QWidget, QPushButton, QGraphicsDropShadowEffect
from PyQt5.QtGui import QIcon, QPainter, QPainterPath, QColor, QCursor
from PyQt5.QtCore import pyqtSignal, QSize, Qt, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QTimer, QPoint, QPointF
from core.utils import get_data_path
from core.database import get_all_servers
from ping_engine import interface
from gui.loading_overlay import LoadingOverlay
from ping_engine.interface import get_orchestrator
import asyncio

logger = logging.getLogger(__name__)
ASSETS_PATH = get_data_path("assets")

class NavigationBar(QWidget):
    """
    Barra de navegação vertical com animação suave:
    - Expande/retrai largura com animação gradual.
    - Botões deslizam de fora para dentro de forma sincronizada.
    - Desenha retângulo arredondado no paintEvent.
    - Emite sinais addServerClicked e homeClicked.
    """
    addServerClicked = pyqtSignal()
    homeClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.visible_closed_width = 2
        self.invisible_margin = 8
        self.closed_width = self.visible_closed_width + self.invisible_margin
        self.expanded_width = 80
        self.animation_duration = 280  # ms
        self.easing = QEasingCurve.InOutCubic
        self.border_radius = 5
        self.is_expanded = False
        self.is_animating = False
        self.top_margin = 20
        self.button_margin = 10

        self.initUI()
        self.setupAnimations()
        self.setupTimer()

    def initUI(self):
        self.setMinimumWidth(self.closed_width)
        self.setMaximumWidth(self.closed_width)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)
        self.setStyleSheet("QWidget { background-color: transparent; }")

        self.btn_home = self._createButton("home.svg", "Página Inicial", self.onHomeClicked)
        self.btn_add  = self._createButton("add.svg",  "Editar Servidores", self.onAddClicked)
        self.btn_pause= self._createButton("unpause.svg","Despausar Pings", self.onPauseClicked)
        for btn in (self.btn_home, self.btn_add, self.btn_pause):
            btn.move(-btn.width(), self.top_margin)
            btn.hide()

    def _createButton(self, icon_name, tooltip, handler):
        btn = QPushButton(self)
        btn.setIcon(QIcon(os.path.join(ASSETS_PATH, icon_name)))
        btn.setIconSize(QSize(24, 24))
        btn.setToolTip(tooltip)
        btn.setFixedSize(64, 40)
        effect = QGraphicsDropShadowEffect(btn)
        effect.setBlurRadius(15)
        effect.setOffset(2, 2)
        btn.setGraphicsEffect(effect)
        btn.setStyleSheet(
            "QPushButton { background-color: #1A2B3C; color: white; border: none; border-radius: 12px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #324860; }"
            "QPushButton:pressed { background-color: #3E5B7A; }"
        )
        btn.clicked.connect(handler)
        return btn

    def setupAnimations(self):
        self.anim_group = QParallelAnimationGroup(self)
        self.min_width_anim = QPropertyAnimation(self, b"minimumWidth")
        self.max_width_anim = QPropertyAnimation(self, b"maximumWidth")
        for anim in (self.min_width_anim, self.max_width_anim):
            anim.setDuration(self.animation_duration)
            anim.setEasingCurve(self.easing)
            self.anim_group.addAnimation(anim)
        self.btn_anims = []
        for btn in (self.btn_home, self.btn_add, self.btn_pause):
            anim = QPropertyAnimation(btn, b"pos")
            anim.setDuration(self.animation_duration)
            anim.setEasingCurve(self.easing)
            self.anim_group.addAnimation(anim)
            self.btn_anims.append(anim)
        self.anim_group.finished.connect(self._onAnimationFinished)

    def setupTimer(self):
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(400)
        self.hide_timer.timeout.connect(self.collapse)

    def enterEvent(self, event):
        super().enterEvent(event)
        if not self.is_animating:
            self.hide_timer.stop()
            self.expand()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if not self.is_animating and not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.hide_timer.start()

    def expand(self):
        if self.is_expanded or self.is_animating:
            return
        self.is_animating = True
        try:
            for btn in (self.btn_home, self.btn_add, self.btn_pause): btn.show()
            start_w = self.width()
            for anim in (self.min_width_anim, self.max_width_anim):
                anim.setStartValue(start_w)
                anim.setEndValue(self.expanded_width)
            off_x = -self.btn_home.width()
            final_x = (self.expanded_width - self.btn_home.width()) // 2
            positions = [
                self.top_margin,
                self.top_margin + self.btn_home.height() + self.button_margin,
                self.top_margin + self.btn_home.height() + self.btn_add.height() + 2*self.button_margin
            ]
            for anim, btn, y in zip(self.btn_anims, (self.btn_home, self.btn_add, self.btn_pause), positions):
                anim.setStartValue(QPoint(off_x, y))
                anim.setEndValue(QPoint(final_x, y))
            self.anim_group.start()
            self.is_expanded = True
        except Exception:
            logger.exception("Erro ao expandir navigation bar")
            self.is_animating = False

    def collapse(self):
        if not self.is_expanded or self.is_animating:
            return
        self.is_animating = True
        try:
            start_w = self.width()
            for anim in (self.min_width_anim, self.max_width_anim):
                anim.setStartValue(start_w)
                anim.setEndValue(self.closed_width)
            off_x = -self.btn_home.width()
            positions = [btn.pos().y() for btn in (self.btn_home, self.btn_add, self.btn_pause)]
            for anim, y in zip(self.btn_anims, positions):
                anim.setStartValue(QPoint(self.btn_home.pos().x(), y))
                anim.setEndValue(QPoint(off_x, y))
            self.anim_group.start()
            self.is_expanded = False
        except Exception:
            logger.exception("Erro ao retrair navigation bar")
            self.is_animating = False

    def _onAnimationFinished(self):
        if not self.is_expanded:
            for btn in (self.btn_home, self.btn_add, self.btn_pause): btn.hide()
        self.is_animating = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        path = QPainterPath()
        path.moveTo(rect.topLeft())
        path.lineTo(rect.topRight() - QPointF(self.border_radius, 0))
        path.arcTo(rect.right() - 2*self.border_radius, rect.top(), 2*self.border_radius, 2*self.border_radius, 90, -90)
        path.lineTo(rect.bottomRight() - QPointF(0, self.border_radius))
        path.arcTo(rect.right() - 2*self.border_radius, rect.bottom() - 2*self.border_radius, 2*self.border_radius, 2*self.border_radius, 0, -90)
        path.lineTo(rect.bottomLeft())
        path.lineTo(rect.topLeft())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2C3E50"))
        painter.drawPath(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_expanded and not self.is_animating:
            final_x = (self.width() - self.btn_home.width()) // 2
            y_positions = [
                self.top_margin,
                self.top_margin + self.btn_home.height() + self.button_margin,
                self.top_margin + self.btn_home.height() + self.btn_add.height() + 2*self.button_margin
            ]
            for btn, y in zip((self.btn_home, self.btn_add, self.btn_pause), y_positions):
                btn.move(final_x, y)

    def onPauseClicked(self):
        print("[INFO] Botão de pausa clicado (sem ação).")


    def _finalize_resume(self, main_win):
        from core.database import get_all_servers
        ip_list = [{"ip": row[1]} for row in get_all_servers()]
        orchestrator = get_orchestrator()
        loop = orchestrator.loop

        # Realiza reload dos servidores (remove e adiciona de novo)
        asyncio.run_coroutine_threadsafe(orchestrator.reload_servers(ip_list), loop)

        # Após reload, inicia o stream de status
        asyncio.run_coroutine_threadsafe(orchestrator.resume_all_servers(), loop)



    def _finalize_pause(self, main_win):
        import asyncio
        from ping_engine.interface import get_orchestrator
        asyncio.run_coroutine_threadsafe(get_orchestrator().pause_all_servers(), get_orchestrator().loop)
        if main_win.loading_overlay:
            main_win.loading_overlay.deleteLater()
            main_win.loading_overlay = None
        self.btn_pause.setIcon(QIcon(os.path.join(ASSETS_PATH, "unpause.svg")))
        self.btn_pause.setToolTip("Despausar Pings")
        main_win.monitor_paused = True



    def onAddClicked(self):
        # 1) emite o sinal conectado em MainWindow.__init__
        self.addServerClicked.emit()
        # 2) abre a tela de edição de servidores
        main_win = self.window()
        if main_win and hasattr(main_win, "showEditServers"):
            main_win.showEditServers()

    def onHomeClicked(self):
        self.homeClicked.emit()
        main_win = self.window()
        if main_win and hasattr(main_win, "showHomePage"):
            main_win.showHomePage()

# Teste standalone
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    nav = NavigationBar()
    nav.resize(80, 300)
    nav.show()
    sys.exit(app.exec_())