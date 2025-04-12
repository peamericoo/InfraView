import logging
from PyQt5.QtWidgets import QWidget, QPushButton, QGraphicsDropShadowEffect
from PyQt5.QtGui import QIcon, QColor, QPainter, QPainterPath
from PyQt5.QtCore import pyqtSignal, QSize, Qt, QPropertyAnimation, QTimer, QPointF, QPoint

# Configuração básica do logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class NavigationBar(QWidget):
    """
    Barra de navegação vertical para ser posicionada no lado esquerdo da aplicação.

    - Inicia "fechada" com apenas 10px de largura (2px “visíveis” + 8px invisíveis para detecção).
    - Ao passar o mouse, expande suavemente para 80px.
    - Quando o mouse sai, espera 400ms e contrai de novo para 10px.
    - O botão (com o ícone "add.svg") fica fixo no topo, centralizado horizontalmente,
      e somente é exibido durante a expansão, deslizando suavemente para dentro e para fora.
    - O fundo (retângulo) tem bordas arredondadas apenas nos cantos superiores e inferiores direitos,
      enquanto os cantos esquerdos permanecem agudos.
    """
    addServerClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Largura "fechada": 2px visíveis + 8px de margem invisível = 10px totais.
        self.visible_closed_width = 2
        self.invisible_margin = 8
        self.closed_width = self.visible_closed_width + self.invisible_margin  # 10px
        self.expanded_width = 80
        self.animation_duration = 280  # ms
        # Define o raio para os cantos arredondados (apenas para os cantos direitos)
        self.border_radius = 5

        self.is_expanded = False

        # Inicializa a UI antes das animações para garantir que o botão seja criado.
        self.initUI()
        self.setupAnimations()
        self.setupTimer()

    def setupAnimations(self):
        """Configura as animações para as propriedades de largura e para o posicionamento do botão."""
        logging.info("Configurando animações de largura e do botão...")
        self.width_anim = QPropertyAnimation(self, b"minimumWidth")
        self.width_anim.setDuration(self.animation_duration)

        self.width_anim_max = QPropertyAnimation(self, b"maximumWidth")
        self.width_anim_max.setDuration(self.animation_duration)

        # Animação para a propriedade de posição do botão
        self.btn_anim = QPropertyAnimation(self.btn_add, b"pos")
        self.btn_anim.setDuration(self.animation_duration)
        logging.info("Animações configuradas.")

    def setupTimer(self):
        """Configura o timer para fechar a barra 400ms após o mouse sair."""
        logging.info("Configurando timer de contração...")
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(400)
        self.hide_timer.timeout.connect(self.collapse)
        logging.info("Timer configurado.")

    def initUI(self):
        """Inicializa a barra "fechada" (10px) e configura o botão de adicionar."""
        logging.info("Inicializando UI da NavigationBar...")
        # Inicia com a largura fechada (10px: 2 visíveis + 8 invisíveis)
        self.setMinimumWidth(self.closed_width)
        self.setMaximumWidth(self.closed_width)

        # Define o fundo e efeito de sombra (o fundo será desenhado no paintEvent)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)
        self.setStyleSheet("""
            QWidget {
                background-color: #2C3E50;
            }
        """)

        # Cria o botão para adicionar servidor como filho direto do widget (fora de layout)
        self.btn_add = QPushButton(self)
        self.btn_add.setIcon(QIcon("add.svg"))
        self.btn_add.setIconSize(QSize(24, 24))
        self.btn_add.setToolTip("Adicionar Servidor")
        self.btn_add.setFixedSize(40, 40)

        # Efeito de sombra para o botão
        btn_shadow = QGraphicsDropShadowEffect(self.btn_add)
        btn_shadow.setBlurRadius(15)
        btn_shadow.setOffset(2, 2)
        self.btn_add.setGraphicsEffect(btn_shadow)

        # Estiliza o botão com borda arredondada
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
        # Inicialmente o botão fica oculto
        self.btn_add.hide()

        logging.info("UI da NavigationBar inicializada.")

    def paintEvent(self, event):
        """
        Desenha o retângulo de fundo com a cor definida (#2C3E50)
        e bordas arredondadas apenas nos cantos superiores e inferiores direitos.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()

        # Cria um QPainterPath para personalizar os cantos arredondados.
        path = QPainterPath()
        # Começa no topo esquerdo (sem arredondamento)
        path.moveTo(rect.topLeft())
        # Linha horizontal até antes do canto superior direito, que será arredondado.
        path.lineTo(rect.topRight() - QPointF(self.border_radius, 0))
        # Arco para o canto superior direito (arredondado)
        path.arcTo(rect.right() - 2 * self.border_radius, rect.top(), 2 * self.border_radius, 2 * self.border_radius, 90, -90)
        # Linha vertical descendo até antes do canto inferior direito, arredondado.
        path.lineTo(rect.bottomRight() - QPointF(0, self.border_radius))
        # Arco para o canto inferior direito (arredondado)
        path.arcTo(rect.right() - 2 * self.border_radius, rect.bottom() - 2 * self.border_radius, 2 * self.border_radius, 2 * self.border_radius, 0, -90)
        # Linha horizontal até o canto inferior esquerdo (sem arredondamento)
        path.lineTo(rect.bottomLeft())
        # Linha vertical subindo de volta ao topo esquerdo
        path.lineTo(rect.topLeft())
        path.closeSubpath()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2C3E50"))
        painter.drawPath(path)

    def resizeEvent(self, event):
        """Reposiciona o botão conforme a barra for redimensionada."""
        super().resizeEvent(event)
        self.updateButtonPosition()
        logging.debug("NavigationBar resized: width=%d", self.width())

    def updateButtonPosition(self):
        """
        Centraliza o botão horizontalmente na área visível (quando expandida)
        ou o posiciona fora (à esquerda) quando contraída.
        """
        btn_width = self.btn_add.width()
        # Se estiver expandida, o botão fica centralizado na barra; caso contrário, é movido para fora.
        if self.is_expanded:
            new_x = (self.width() - btn_width) // 2
        else:
            new_x = -btn_width  # Fora da área visível à esquerda
        new_y = 5  # Fixo 5px do topo
        self.btn_add.move(new_x, new_y)
        logging.debug("Botão posicionado em (%d, %d)", self.btn_add.x(), self.btn_add.y())

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
        """Expande a barra para o tamanho expandido e anima o botão para o centro."""
        if self.is_expanded:
            logging.debug("NavigationBar já está expandida.")
            return
        
        # Remove o callback da animação de retração se estiver conectado.
        try:
            self.btn_anim.finished.disconnect(self.onCollapseFinished)
        except Exception:
            pass

        logging.info("Expandindo a NavigationBar...")
        self.width_anim.stop()
        self.width_anim_max.stop()

        self.btn_add.show()

        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(self.expanded_width)
        self.width_anim_max.setStartValue(self.width())
        self.width_anim_max.setEndValue(self.expanded_width)
        self.width_anim.start()
        self.width_anim_max.start()

        # Anima o botão para a posição central na nova largura
        self.btn_anim.stop()
        final_x = (self.expanded_width - self.btn_add.width()) // 2
        final_y = 5  # 5px do topo
        self.btn_anim.setStartValue(self.btn_add.pos())
        self.btn_anim.setEndValue(QPointF(final_x, final_y))
        self.btn_anim.start()

        self.is_expanded = True
        logging.info("NavigationBar expandida.")

    def collapse(self):
        """Recontra a barra para a largura fechada e anima o botão para sair da área visível."""
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

        # Anima o botão para deslizar para fora (à esquerda)
        self.btn_anim.stop()
        current_pos = self.btn_add.pos()
        offscreen_x = -self.btn_add.width()
        final_y = current_pos.y()
        self.btn_anim.setStartValue(current_pos)
        self.btn_anim.setEndValue(QPointF(offscreen_x, final_y))
        self.btn_anim.finished.connect(self.onCollapseFinished)
        self.btn_anim.start()

        self.is_expanded = False

    def onCollapseFinished(self):
        """Callback chamado após a animação de retração concluir; oculta o botão se a barra estiver contraída."""
        logging.info("Animação de retração concluída; ocultando botão.")
        try:
            self.btn_anim.finished.disconnect(self.onCollapseFinished)
        except Exception as e:
            logging.error("Erro ao desconectar o sinal de retração: %s", e)
        if not self.is_expanded:
            self.btn_add.hide()

# Exemplo de teste:
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    nav_bar = NavigationBar()
    nav_bar.addServerClicked.connect(lambda: logging.info("Clique no botão de Adicionar Servidor"))
    nav_bar.resize(80, 300)  # Tamanho de teste
    nav_bar.show()
    sys.exit(app.exec_())
