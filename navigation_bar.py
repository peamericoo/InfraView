import os
import logging
from PyQt5.QtWidgets import QWidget, QPushButton, QGraphicsDropShadowEffect
from PyQt5.QtGui import QIcon, QColor, QPainter, QPainterPath, QCursor
from PyQt5.QtCore import pyqtSignal, QSize, Qt, QPropertyAnimation, QTimer, QPointF, QPoint
from control_ping import toggle_pause

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def load_icon(filename, fallback_icon=QIcon()):
    """
    Tenta carregar o ícone a partir do filename. Se não existir, retorna um ícone fallback.
    """
    if os.path.exists(filename):
        return QIcon(filename)
    else:
        logging.warning("Arquivo '%s' não encontrado. Usando fallback.", filename)
        return fallback_icon

class NavigationBar(QWidget):
    """
    Barra de navegação vertical para ser posicionada no lado esquerdo da aplicação.
    - Inicia "fechada" com 10px de largura.
    - Ao passar o mouse, expande para 80px.
    - Quando o mouse sai, contrai para 10px.
    - Possui botões que se movem de forma sincronizada, com margem configurável entre eles
      e com margem superior ajustável.
    """
    addServerClicked = pyqtSignal()
    homeClicked = pyqtSignal()  # Novo sinal para o botão Home

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
        self.button_margin = 10    # Distância vertical entre os botões
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
        
        # Animações para todos os botões
        self.home_anim = QPropertyAnimation(self.btn_home, b"pos")
        self.home_anim.setDuration(self.animation_duration)
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
        
        # Tente carregar o stylesheet a partir de um arquivo .qss, se existir; caso contrário, usa inline.
        qss_file = "navigation_bar.qss"
        if os.path.exists(qss_file):
            with open(qss_file, "r") as f:
                self.setStyleSheet(f.read())
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: #2C3E50;
                }
            """)

        # Estilo padrão para botões redondos
        button_style = """
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
        """

        # Botão Home (novo)
        self.btn_home = QPushButton(self)
        self.btn_home.setIcon(load_icon("home.svg"))
        self.btn_home.setIconSize(QSize(24, 24))
        self.btn_home.setToolTip("Página Inicial")
        self.btn_home.setFixedSize(40, 40)
        btn_home_shadow = QGraphicsDropShadowEffect(self.btn_home)
        btn_home_shadow.setBlurRadius(15)
        btn_home_shadow.setOffset(2, 2)
        self.btn_home.setGraphicsEffect(btn_home_shadow)
        self.btn_home.setStyleSheet(button_style)
        self.btn_home.clicked.connect(self.onHomeClicked)
        self.btn_home.hide()

        # Botão de adicionar servidor (redondo)
        self.btn_add = QPushButton(self)
        self.btn_add.setIcon(load_icon("add.svg"))
        self.btn_add.setIconSize(QSize(24, 24))
        self.btn_add.setToolTip("Adicionar Servidor")
        self.btn_add.setFixedSize(40, 40)
        btn_shadow = QGraphicsDropShadowEffect(self.btn_add)
        btn_shadow.setBlurRadius(15)
        btn_shadow.setOffset(2, 2)
        self.btn_add.setGraphicsEffect(btn_shadow)
        # Se houver um arquivo de estilos externo, os estilos poderão ser carregados por lá; caso contrário, usa o padrão.
        self.btn_add.setStyleSheet(button_style)
        self.btn_add.clicked.connect(self.onAddClicked)
        self.btn_add.hide()

        # Botão de pausar/despausar (redondo)
        self.btn_pause = QPushButton(self)
        self.btn_pause.setIcon(load_icon("unpause.svg"))
        self.btn_pause.setIconSize(QSize(24, 24))
        self.btn_pause.setToolTip("Despausar Pings")
        self.btn_pause.setFixedSize(40, 40)
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
            
            # Posiciona o botão Home na parte superior
            self.btn_home.move(new_x, self.top_margin)
            
            # Posiciona o botão adicionar abaixo do botão Home
            home_bottom = self.top_margin + self.btn_home.height() + self.button_margin
            self.btn_add.move(new_x, home_bottom)
            
            # Posiciona o botão pausar abaixo do botão adicionar
            add_bottom = home_bottom + self.btn_add.height() + self.button_margin
            self.btn_pause.move(new_x, add_bottom)
        else:
            # Botões ficam ocultos quando a barra está recolhida
            self.btn_home.move(-btn_width, self.top_margin)
            self.btn_add.move(-btn_width, self.top_margin + self.btn_home.height() + self.button_margin)
            self.btn_pause.move(-self.btn_pause.width(), self.top_margin + self.btn_home.height() + self.btn_add.height() + 2*self.button_margin)
        
        logging.debug("Botões posicionados: btn_home=(%d, %d), btn_add=(%d, %d), btn_pause=(%d, %d)",
                      self.btn_home.x(), self.btn_home.y(), 
                      self.btn_add.x(), self.btn_add.y(), 
                      self.btn_pause.x(), self.btn_pause.y())

    def enterEvent(self, event):
        logging.info("Mouse entrou na NavigationBar: expandindo.")
        self.hide_timer.stop()
        self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Verifica se o cursor realmente saiu da área da NavigationBar.
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            logging.info("Mouse saiu da NavigationBar: iniciando contração.")
            self.hide_timer.start()
        super().leaveEvent(event)

    def expand(self):
        if self.is_expanded:
            logging.debug("NavigationBar já está expandida.")
            return
        
        # Desconecta os sinais de animação se necessário
        try:
            self.btn_anim.finished.disconnect(self.onCollapseFinished)
            self.pause_anim.finished.disconnect(self.onCollapseFinished)
            self.home_anim.finished.disconnect(self.onCollapseFinished)
        except Exception:
            pass
            
        logging.info("Expandindo a NavigationBar...")
        self.width_anim.stop()
        self.width_anim_max.stop()
        
        # Mostra todos os botões
        self.btn_home.show()
        self.btn_add.show()
        self.btn_pause.show()
        
        # Animação da largura da barra
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(self.expanded_width)
        self.width_anim_max.setStartValue(self.width())
        self.width_anim_max.setEndValue(self.expanded_width)
        self.width_anim.start()
        self.width_anim_max.start()
        
        # Calcula posições finais para os botões
        final_x = (self.expanded_width - self.btn_home.width()) // 2
        
        # Animação para btn_home (novo)
        self.home_anim.stop()
        final_y_home = self.top_margin
        self.home_anim.setStartValue(self.btn_home.pos())
        self.home_anim.setEndValue(QPointF(final_x, final_y_home))
        self.home_anim.start()
        
        # Animação para btn_add
        self.btn_anim.stop()
        final_y_add = self.top_margin + self.btn_home.height() + self.button_margin
        self.btn_anim.setStartValue(self.btn_add.pos())
        self.btn_anim.setEndValue(QPointF(final_x, final_y_add))
        self.btn_anim.start()
        
        # Animação para btn_pause
        self.pause_anim.stop()
        final_y_pause = final_y_add + self.btn_add.height() + self.button_margin
        
        if self.first_expand:
            # Para a primeira vez, movemos diretamente sem animação
            self.btn_home.move(final_x, final_y_home)
            self.btn_add.move(final_x, final_y_add)
            self.btn_pause.move(final_x, final_y_pause)
            self.first_expand = False
        else:
            self.pause_anim.setStartValue(self.btn_pause.pos())
            self.pause_anim.setEndValue(QPointF(final_x, final_y_pause))
            self.pause_anim.start()
        
        self.is_expanded = True
        logging.info("NavigationBar expandida.")

    def collapse(self):
        if not self.is_expanded:
            logging.debug("NavigationBar já está contraída.")
            return
        logging.info("Contraindo a NavigationBar...")
        
        self.width_anim.stop()
        self.width_anim_max.stop()
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(self.closed_width)
        self.width_anim_max.setStartValue(self.width())
        self.width_anim_max.setEndValue(self.closed_width)
        self.width_anim.start()
        self.width_anim_max.start()
        
        # Animação para esconder todos os botões para fora da tela
        offscreen_x = -self.btn_home.width()
        
        # Animação para btn_home
        self.home_anim.stop()
        current_pos_home = self.btn_home.pos()
        final_y_home = current_pos_home.y()
        self.home_anim.setStartValue(current_pos_home)
        self.home_anim.setEndValue(QPointF(offscreen_x, final_y_home))
        self.home_anim.finished.connect(self.onCollapseFinished)
        self.home_anim.start()
        
        # Animação para btn_add
        self.btn_anim.stop()
        current_pos = self.btn_add.pos()
        final_y = current_pos.y()
        self.btn_anim.setStartValue(current_pos)
        self.btn_anim.setEndValue(QPointF(offscreen_x, final_y))
        self.btn_anim.finished.connect(self.onCollapseFinished)
        self.btn_anim.start()
        
        # Animação para btn_pause
        self.pause_anim.stop()
        current_pos_pause = self.btn_pause.pos()
        final_y_pause = current_pos_pause.y()
        self.pause_anim.setStartValue(current_pos_pause)
        self.pause_anim.setEndValue(QPointF(offscreen_x, final_y_pause))
        self.pause_anim.finished.connect(self.onCollapseFinished)
        self.pause_anim.start()
        
        self.is_expanded = False

    def onCollapseFinished(self):
        logging.info("Animação de retração concluída; ocultando botões.")
        try:
            # Desconecta todos os sinais para evitar chamadas repetidas
            self.home_anim.finished.disconnect(self.onCollapseFinished)
            self.btn_anim.finished.disconnect(self.onCollapseFinished)
            self.pause_anim.finished.disconnect(self.onCollapseFinished)
        except Exception as e:
            logging.error("Erro ao desconectar sinal: %s", e)
        
        if not self.is_expanded:
            # Oculta todos os botões quando a barra estiver contraída
            if self.btn_home and not self.btn_home.isHidden():
                self.btn_home.hide()
            if self.btn_add and not self.btn_add.isHidden():
                self.btn_add.hide()
            if self.btn_pause and not self.btn_pause.isHidden():
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
            self.btn_pause.setIcon(load_icon("unpause.svg"))
            self.btn_pause.setToolTip("Despausar Pings")
        else:
            self.btn_pause.setStyleSheet("""
                QPushButton {
                    background-color: lightcoral;
                    border: none;
                    border-radius: 20px;
                }
            """)
            self.btn_pause.setIcon(load_icon("pause.svg"))
            self.btn_pause.setToolTip("Pausar Pings")
        self.btn_pause.setIconSize(QSize(24, 24))

    def onAddClicked(self, event=None):
        main_win = self.window()
        if main_win and hasattr(main_win, "showEditServers"):
            main_win.showEditServers()

    def onHomeClicked(self, event=None):
        # Emite o sinal que pode ser conectado pela aplicação principal
        self.homeClicked.emit()
        logging.info("Botão Home clicado")
        
        # Se houver uma função para navegar para a página inicial no widget pai, chamá-la
        main_win = self.window()
        if main_win and hasattr(main_win, "showHomePage"):
            main_win.showHomePage()

# Exemplo de teste:
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    nav_bar = NavigationBar()
    nav_bar.homeClicked.connect(lambda: logging.info("Clique no botão Home"))
    nav_bar.addServerClicked.connect(lambda: logging.info("Clique no botão de Adicionar Servidor"))
    nav_bar.resize(80, 300)
    nav_bar.show()
    sys.exit(app.exec_())