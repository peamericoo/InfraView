import logging
from PyQt5.QtWidgets import QWidget, QPushButton, QGraphicsDropShadowEffect
from PyQt5.QtGui import QIcon, QColor, QPainter, QPainterPath
from PyQt5.QtCore import pyqtSignal, QSize, Qt, QPropertyAnimation, QTimer, QPointF, QPoint
from control_ping import toggle_pause

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class NavigationBar(QWidget):
    """
    Barra de navegação vertical para ser posicionada no lado esquerdo da aplicação.
    - Inicia "fechada" com 10px de largura.
    - Ao passar o mouse, expande para 80px.
    - Quando o mouse sai, contrai para 10px.
    - Possui um botão de adicionar (add.svg) e um botão de pausar/despausar (pause/unpause)
      que se movem de forma sincronizada, com margem configurável entre eles e com margem superior ajustável.
    """
    addServerClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.visible_closed_width = 2
        self.invisible_margin = 8
        self.closed_width = self.visible_closed_width + self.invisible_margin  # 10px
        self.expanded_width = 80
        self.animation_duration = 280  # ms
        self.border_radius = 5
        self.is_expanded = False
        self.pings_paused = True  # Inicialmente, os pings estão pausados
        self.top_margin = 20      # Margem superior desejada
        self.pause_margin = 10    # Distância vertical entre os botões
        self.first_expand = True  # Para evitar animação indesejada na primeira vez
        self.initUI()
        self.setupAnimations()
        self.setupTimer()

    def setupAnimations(self):
        logging.info("Configurando animações de largura e dos botões...")
        self.width_anim = QPropertyAnimation(self, b"minimumWidth")
        self.width_anim.setDuration(self.animation_duration)
        self.width_anim_max = QPropertyAnimation(self, b"maximumWidth")
        self.width_anim_max.setDuration(self.animation_duration)
        self.btn_anim = QPropertyAnimation(self.btn_add, b"pos")
        self.btn_anim.setDuration(self.animation_duration)
        self.pause_anim = QPropertyAnimation(self.btn_pause, b"pos")
        self.pause_anim.setDuration(self.animation_duration)
        logging.info("Animações configuradas.")

    def setupTimer(self):
        logging.info("Configurando timer de contração...")
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(400)
        self.hide_timer.timeout.connect(self.collapse)
        logging.info("Timer configurado.")

    def initUI(self):
        logging.info("Inicializando UI da NavigationBar...")
        self.setMinimumWidth(self.closed_width)
        self.setMaximumWidth(self.closed_width)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)
        self.setStyleSheet("""
            QWidget {
                background-color: #2C3E50;
            }
        """)

        # Botão de adicionar servidor (redondo)
        self.btn_add = QPushButton(self)
        self.btn_add.setIcon(QIcon("add.svg"))
        self.btn_add.setIconSize(QSize(24, 24))
        self.btn_add.setToolTip("Adicionar Servidor")
        self.btn_add.setFixedSize(40, 40)
        btn_shadow = QGraphicsDropShadowEffect(self.btn_add)
        btn_shadow.setBlurRadius(15)
        btn_shadow.setOffset(2, 2)
        self.btn_add.setGraphicsEffect(btn_shadow)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #ECF0F1;
                border: none;
                border-radius: 20px;
            }
            QPushButton:hover {
                background-color: #BDC3C7;
            }
            QPushButton:pressed {
                background-color: #95A5A6;
            }
        """)
        self.btn_add.clicked.connect(self.addServerClicked.emit)
        self.btn_add.hide()

        # Novo botão de pausar/despausar (redondo)
        self.btn_pause = QPushButton(self)
        self.btn_pause.setIcon(QIcon("unpause.svg"))
        self.btn_pause.setIconSize(QSize(24, 24))
        self.btn_pause.setToolTip("Despausar Pings")
        self.btn_pause.setFixedSize(40, 40)
        # Define style fixo para cada estado (sem hover alterando a cor)
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: lightgreen;
                border: none;
                border-radius: 20px;
            }
        """)
        self.btn_pause.clicked.connect(self.onPauseClicked)
        self.btn_pause.hide()

        logging.info("UI da NavigationBar inicializada.")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        path = QPainterPath()
        path.moveTo(rect.topLeft())
        path.lineTo(rect.topRight() - QPointF(self.border_radius, 0))
        path.arcTo(rect.right() - 2 * self.border_radius, rect.top(), 2 * self.border_radius, 2 * self.border_radius, 90, -90)
        path.lineTo(rect.bottomRight() - QPointF(0, self.border_radius))
        path.arcTo(rect.right() - 2 * self.border_radius, rect.bottom() - 2 * self.border_radius, 2 * self.border_radius, 2 * self.border_radius, 0, -90)
        path.lineTo(rect.bottomLeft())
        path.lineTo(rect.topLeft())
        path.closeSubpath()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2C3E50"))
        painter.drawPath(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateButtonPosition()
        logging.debug("NavigationBar resized: width=%d", self.width())

    def updateButtonPosition(self):
        btn_width = self.btn_add.width()
        if self.is_expanded:
            new_x = (self.width() - btn_width) // 2
            self.btn_add.move(new_x, self.top_margin)
            new_y_pause = self.top_margin + self.btn_add.height() + self.pause_margin
            self.btn_pause.move(new_x, new_y_pause)
        else:
            self.btn_add.move(-btn_width, self.top_margin)
            self.btn_pause.move(-self.btn_pause.width(), self.top_margin)
        logging.debug("Botões posicionados: btn_add=(%d, %d), btn_pause=(%d, %d)",
                      self.btn_add.x(), self.btn_add.y(), self.btn_pause.x(), self.btn_pause.y())

    def enterEvent(self, event):
        logging.info("Mouse entrou na NavigationBar: expandindo.")
        self.hide_timer.stop()
        self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        logging.info("Mouse saiu da NavigationBar: iniciando contração.")
        self.hide_timer.start()
        super().leaveEvent(event)

    def expand(self):
        if self.is_expanded:
            logging.debug("NavigationBar já está expandida.")
            return
        try:
            self.btn_anim.finished.disconnect(self.onCollapseFinished)
            self.pause_anim.finished.disconnect(self.onCollapseFinished)
        except Exception:
            pass
        logging.info("Expandindo a NavigationBar...")
        self.width_anim.stop()
        self.width_anim_max.stop()
        self.btn_add.show()
        self.btn_pause.show()
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(self.expanded_width)
        self.width_anim_max.setStartValue(self.width())
        self.width_anim_max.setEndValue(self.expanded_width)
        self.width_anim.start()
        self.width_anim_max.start()
        # Animação para btn_add
        self.btn_anim.stop()
        final_x = (self.expanded_width - self.btn_add.width()) // 2
        final_y = self.top_margin
        self.btn_anim.setStartValue(self.btn_add.pos())
        self.btn_anim.setEndValue(QPointF(final_x, final_y))
        self.btn_anim.start()
        # Animação para btn_pause
        self.pause_anim.stop()
        final_x_pause = (self.expanded_width - self.btn_pause.width()) // 2
        final_y_pause = self.top_margin + self.btn_add.height() + self.pause_margin
        if self.first_expand:
            self.btn_pause.move(final_x_pause, final_y_pause)
            self.first_expand = False
        else:
            self.pause_anim.setStartValue(self.btn_pause.pos())
            self.pause_anim.setEndValue(QPointF(final_x_pause, final_y_pause))
            self.pause_anim.start()
        self.is_expanded = True
        logging.info("NavigationBar expandida.")

    def collapse(self):
        if not self.is_expanded:
            logging.debug("NavigationBar já está contraída.")
            return
        logging.info("Contratando a NavigationBar...")
        self.width_anim.stop()
        self.width_anim_max.stop()
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(self.closed_width)
        self.width_anim_max.setStartValue(self.width())
        self.width_anim_max.setEndValue(self.closed_width)
        self.width_anim.start()
        self.width_anim_max.start()
        # Animação para btn_add
        self.btn_anim.stop()
        current_pos = self.btn_add.pos()
        offscreen_x = -self.btn_add.width()
        final_y = current_pos.y()
        self.btn_anim.setStartValue(current_pos)
        self.btn_anim.setEndValue(QPointF(offscreen_x, final_y))
        self.btn_anim.finished.connect(self.onCollapseFinished)
        self.btn_anim.start()
        # Animação para btn_pause
        self.pause_anim.stop()
        current_pos_pause = self.btn_pause.pos()
        offscreen_x_pause = -self.btn_pause.width()
        final_y_pause = current_pos_pause.y()
        self.pause_anim.setStartValue(current_pos_pause)
        self.pause_anim.setEndValue(QPointF(offscreen_x_pause, final_y_pause))
        self.pause_anim.start()
        self.is_expanded = False

    def onCollapseFinished(self):
        logging.info("Animação de retração concluída; ocultando botões.")
        try:
            self.btn_anim.finished.disconnect(self.onCollapseFinished)
            self.pause_anim.finished.disconnect(self.onCollapseFinished)
        except Exception as e:
            logging.error("Erro ao desconectar sinal: %s", e)
        if not self.is_expanded:
            self.btn_add.hide()
            self.btn_pause.hide()

    def onPauseClicked(self):
        main_window = self.window()
        toggle_pause(main_window)
        # Aplica style fixo de acordo com o estado
        if main_window.monitor_paused:
            self.btn_pause.setStyleSheet("""
                QPushButton {
                    background-color: lightgreen;
                    border: none;
                    border-radius: 20px;
                }
            """)
            self.btn_pause.setIcon(QIcon("unpause.svg"))
            self.btn_pause.setToolTip("Despausar Pings")
        else:
            self.btn_pause.setStyleSheet("""
                QPushButton {
                    background-color: lightcoral;
                    border: none;
                    border-radius: 20px;
                }
            """)
            self.btn_pause.setIcon(QIcon("pause.svg"))
            self.btn_pause.setToolTip("Pausar Pings")
        self.btn_pause.setIconSize(QSize(24,24))

# Exemplo de teste:
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    nav_bar = NavigationBar()
    nav_bar.addServerClicked.connect(lambda: logging.info("Clique no botão de Adicionar Servidor"))
    nav_bar.resize(80, 300)
    nav_bar.show()
    sys.exit(app.exec_())
