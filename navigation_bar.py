from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QGraphicsDropShadowEffect
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, QSize, Qt, QPropertyAnimation, QTimer

class NavigationBar(QWidget):
    """
    Barra de navegação vertical para ser posicionada no lado esquerdo da aplicação.

    - Inicia "fechada" com 2px de largura (quase 0, para visualmente desaparecer).
    - Ao passar o mouse, expande suavemente para 80px.
    - Quando o mouse sai, espera 400ms e contrai de novo para 2px.
    - O botão com o ícone "add.svg" fica no topo, centralizado, com tamanho fixo e leve margem.
    """
    addServerClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.closed_width = 2    # largura mínima para capturar eventos
        self.expanded_width = 80
        self.animation_duration = 280  # ms
        self.setupAnimations()
        self.setupTimer()
        self.initUI()
        self.is_expanded = False

    def setupAnimations(self):
        # Anima as propriedades minimumWidth e maximumWidth do widget
        self.width_anim = QPropertyAnimation(self, b"minimumWidth")
        self.width_anim.setDuration(self.animation_duration)
        self.width_anim_max = QPropertyAnimation(self, b"maximumWidth")
        self.width_anim_max.setDuration(self.animation_duration)

    def setupTimer(self):
        # Timer para fechar 400ms após o mouse sair
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(400)
        self.hide_timer.timeout.connect(self.collapse)

    def initUI(self):
        # Inicia com largura fechada (2px)
        self.setMinimumWidth(self.closed_width)
        self.setMaximumWidth(self.closed_width)

        # Aplica um efeito de sombra no container (o retângulo)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)

        # Define fundo escuro para o container
        self.setStyleSheet("""
            QWidget {
                background-color: #2C3E50;
            }
        """)

        # Configura o layout para posicionar o botão no topo central com margens leves
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Cria o botão para adicionar servidor
        self.btn_add = QPushButton()
        self.btn_add.setIcon(QIcon("add.svg"))
        self.btn_add.setIconSize(QSize(24, 24))
        self.btn_add.setToolTip("Adicionar Servidor")
        self.btn_add.setFixedSize(40, 40)
        
        # Aplica sombreamento ao botão
        btn_shadow = QGraphicsDropShadowEffect(self.btn_add)
        btn_shadow.setBlurRadius(15)
        btn_shadow.setOffset(2, 2)
        self.btn_add.setGraphicsEffect(btn_shadow)
        
        # Define o estilo do botão
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
        layout.addWidget(self.btn_add)
        self.setLayout(layout)

    def enterEvent(self, event):
        self.hide_timer.stop()
        self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hide_timer.start()
        super().leaveEvent(event)

    def expand(self):
        if self.is_expanded:
            return
        self.width_anim.stop()
        self.width_anim_max.stop()
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(self.expanded_width)
        self.width_anim_max.setStartValue(self.width())
        self.width_anim_max.setEndValue(self.expanded_width)
        self.width_anim.start()
        self.width_anim_max.start()
        self.is_expanded = True

    def collapse(self):
        if not self.is_expanded:
            return
        self.width_anim.stop()
        self.width_anim_max.stop()
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(self.closed_width)
        self.width_anim_max.setStartValue(self.width())
        self.width_anim_max.setEndValue(self.closed_width)
        self.width_anim.start()
        self.width_anim_max.start()
        self.is_expanded = False

# Exemplo de teste: execute este arquivo isoladamente para ver o comportamento
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    nav_bar = NavigationBar()
    nav_bar.addServerClicked.connect(lambda: print("Clique no botão de Adicionar Servidor"))
    nav_bar.show()
    sys.exit(app.exec_())
