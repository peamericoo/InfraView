from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QGraphicsOpacityEffect, QPushButton, QMainWindow
from PyQt5.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, pyqtProperty, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QPixmap, QImage
import math
import random

class LoadingOverlay(QWidget):
    def __init__(self, parent=None, message=None, on_finished=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(30, 60, 114, 180), stop:1 rgba(42, 82, 152, 180));
        """)


        self.setGeometry(parent.rect())

        self.pausing_phrases = [
            "Desconectando pacotes", "Desligando sondas", "Guardando logs", "Reduzindo tráfego",
            "Organizando os bytes", "Pausando escuta", "Desligando conexões", "Silenciando o ruído"
        ]
        self.unpausing_phrases = [
            "Retomando a escuta", "Disparando pacotes", "Subindo sinal", "Reativando sensores",
            "Acelerando os bits", "Monitoramento ligado", "Pingando servidores", "Foco total ativado"
        ]
        self.done_phrases = [
            "Pronto!", "Sucesso", "Tudo certo por aqui", "Missão cumprida", "Acabou a espera",
            "Tudo funcionando", "Iniciando", "Agindo", "Preparado!", "Vamos começar"
        ]
        self.done_phrases = [
            "Pronto!", "Sucesso", "Tudo certo por aqui", "Missão cumprida", "Acabou a espera",
            "Tudo funcionando", "Iniciando", "Agindo", "Preparado!", "Vamos começar"
        ]

        self.final_message = random.choice(self.done_phrases)
        if message == "pausing":
            self.base_message = random.choice(self.pausing_phrases)
        elif message == "unpausing":
            self.base_message = random.choice(self.unpausing_phrases)
        elif isinstance(message, str):
            self.base_message = message
        else:
            self.base_message = random.choice(self.unpausing_phrases + self.pausing_phrases)


        self.typing_index = 0
        self.dot_state = 0
        self.phase = "typing_initial"

        # Roda animada estilo com pulsação e aceleração
        self.base_angle_speed = 2
        self.current_speed = 0
        self.max_speed = 8
        self.pulsation_phase = 0
        self.span_value = random.randint(150, 250)  # Antes era entre 120 e 200
        self.initial_span = self.span_value
        self.angle = 0

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        # ✨ Fade-in suave
        self.opacity_effect.setOpacity(0.0)
        self.fade_in_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_anim.setDuration(900)
        self.fade_in_anim.setStartValue(0.0)
        self.fade_in_anim.setEndValue(1.0)
        self.fade_in_anim.start()


        self.label = QLabel("", self)
        self.label.setStyleSheet("color: #FFFFFF; font-family: 'Segoe UI', sans-serif; font-size: 16pt; font-weight: bold; background: transparent;")
        self.label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.label)
        layout.addStretch()
        layout.setAlignment(Qt.AlignHCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self.handle_typing)
        self.typing_timer.start(50)

        self.dot_timer = QTimer(self)
        self.dot_timer.timeout.connect(self.update_dots)

        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self.update_spinner)
        self.spinner_timer.start(30)

        self.acceleration_timer = QTimer(self)
        self.acceleration_timer.timeout.connect(self.accelerate_spinner)
        self.acceleration_timer.start(30)

        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self.start_fadeout)

        self.cycle_count = 0  # Contador para ciclos de alongamento/encurtamento
        self.max_cycles = 3  # Número de ciclos desejados
        self._span_value = self.span_value  # Adiciona um atributo privado para animação
        self.on_finished = on_finished 
        # ⬛️ Animação do gradiente aleatório
        self.gradient_angle = random.randint(0, 360)
        self.current_gradient = random.choice([
            (QColor(44, 62, 80, 200), QColor(52, 73, 94, 200)),
            (QColor(30, 39, 46, 200), QColor(47, 79, 79, 200)),
            (QColor(33, 47, 61, 200), QColor(64, 92, 107, 200)),
        ])

        self.gradient_timer = QTimer(self)
        self.gradient_timer.timeout.connect(self.animate_gradient)
        self.gradient_timer.start(100)
        
    @pyqtProperty(float)
    def span_value(self):
        return self._span_value

    @span_value.setter
    def span_value(self, value):
        self._span_value = value
        self.update()  # Atualiza a tela para refletir a mudança

    def animate_gradient(self):
        self.gradient_angle = (self.gradient_angle + random.uniform(0.5, 1.5)) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Gradiente animado com ângulo aleatório
        w, h = self.width(), self.height()
        angle = math.radians(self.gradient_angle)
        x1 = w / 2 + math.cos(angle) * w
        y1 = h / 2 + math.sin(angle) * h
        x2 = w / 2 - math.cos(angle) * w
        y2 = h / 2 - math.sin(angle) * h

        gradient = QLinearGradient(QPointF(x1, y1), QPointF(x2, y2))
        color1 = self.current_gradient[0]
        color2 = self.current_gradient[1]

        mid1 = QColor(
            (color1.red() + color2.red()) // 2,
            (color1.green() + color2.green()) // 2,
            (color1.blue() + color2.blue()) // 2,
            (color1.alpha() + color2.alpha()) // 2,
        )

        mid2 = QColor(
            (color1.red() * 3 + color2.red()) // 4,
            (color1.green() * 3 + color2.green()) // 4,
            (color1.blue() * 3 + color2.blue()) // 4,
            (color1.alpha() * 3 + color2.alpha()) // 4,
        )

        gradient.setColorAt(0.0, color1)
        gradient.setColorAt(0.25, mid2)
        gradient.setColorAt(0.5, mid1)
        gradient.setColorAt(0.75, mid2)
        gradient.setColorAt(1.0, color2)

        painter.fillRect(self.rect(), gradient)

        # Spinner
        center = self.rect().center()
        spinner_radius = 20 + 2 * (0.5 + 0.5 * math.sin(self.pulsation_phase * math.pi / 180))
        painter.translate(center.x(), center.y() - 40)

        pen = QPen()
        pen.setWidth(4)
        pen.setColor(QColor("white"))  # ← cor branca aqui
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        rect = QRectF(-spinner_radius, -spinner_radius, spinner_radius * 2, spinner_radius * 2)
        start_angle = int(self.angle * 16)
        span_angle = int(self.span_value * 16)
        painter.drawArc(rect, start_angle, span_angle)

    def update_spinner(self):
        self.angle = (self.angle + self.current_speed) % 360
        self.pulsation_phase = (self.pulsation_phase + 5) % 360
        self.update()

    def accelerate_spinner(self):
        if self.current_speed < self.max_speed:
            self.current_speed += 0.2
            self.span_value = self.initial_span - ((self.current_speed / self.max_speed) * (self.initial_span - 60))
        else:
            self.current_speed = self.max_speed
            self.span_value = 60
            self.acceleration_timer.stop()
            # Inicia o ciclo de desaceleração
            self.decelerate_spinner()

    def decelerate_spinner(self):
        self.deceleration_timer = QTimer(self)
        self.deceleration_timer.timeout.connect(self._decelerate_step)
        self.deceleration_timer.start(30)

    def _decelerate_step(self):
        if self.current_speed > 0:
            self.current_speed -= 0.3
            self.span_value = 60 + ((1 - self.current_speed / self.max_speed) * (self.initial_span - 60))
        else:
            if self.cycle_count < self.max_cycles:
                # Reinicia o ciclo de alongamento/encurtamento
                self.cycle_count += 1
                self.current_speed = 0
                self.accelerate_spinner()  # Reinicia a aceleração
            else:
                # Finaliza o ciclo de desaceleração
                self.deceleration_timer.stop()

    def handle_typing(self):
        if self.phase == "typing_initial":
            if self.typing_index < len(self.base_message):
                self.typing_index += 1
                self.label.setText(self.base_message[:self.typing_index])
            else:
                self.typing_timer.stop()
                QTimer.singleShot(850, self.start_dots)  # Tempo de exibição dos pontos
        elif self.phase == "typing_final":
            if self.typing_index == 0:
                # Inicia a transição suave para 360 graus
                self.start_spinner_transition()
            if self.typing_index < len(self.final_message):
                self.typing_index += 1
                self.label.setText(self.final_message[:self.typing_index])
            else:
                self.typing_timer.stop()
                QTimer.singleShot(1050, self.prepare_final_fade)  # Tempo antes do fade final

    def start_spinner_transition(self):
        if self.span_value >= 360:
            return

        # Cria uma animação para suavizar a transição para 360 graus
        self.spinner_animation = QPropertyAnimation(self, b"span_value")
        self.spinner_animation.setDuration(1000)  # Duração da transição (1 segundo)
        self.spinner_animation.setStartValue(self.span_value)
        self.spinner_animation.setEndValue(360)  # Transição para o contorno completo

        # Garante que o spinner continue girando durante a transição
        self.spinner_animation.valueChanged.connect(self.update_spinner_during_transition)
        self.spinner_animation.finished.connect(self.on_spinner_transition_complete)
        self.spinner_animation.start()

    def update_spinner_during_transition(self, value):
        # Atualiza o ângulo continuamente durante a transição
        self.angle = (self.angle + self.current_speed) % 360
        self.update()  # Redesenha o spinner

    def on_spinner_transition_complete(self):
        # Certifica-se de que o spinner está no estado final (360 graus)
        self.span_value = 360
        self.update()  # Redesenha o spinner para garantir o estado final

    def start_dots(self):
        self.dot_state = 0
        self.dot_timer.start(500)
        QTimer.singleShot(1250, self.start_erasing)

    def update_dots(self):
        self.dot_state = (self.dot_state + 1) % 4
        self.label.setText(self.base_message + "." * self.dot_state)

    def start_erasing(self):
        self.dot_timer.stop()
        self.phase = "erasing_initial"
        self.typing_index = len(self.base_message)
        self.typing_timer.timeout.disconnect()
        self.typing_timer.timeout.connect(self.erase_initial)
        self.typing_timer.start(30)

    def erase_initial(self):
        if self.typing_index > 0:
            self.typing_index -= 1
            self.label.setText(self.base_message[:self.typing_index])
        else:
            self.typing_timer.stop()
            self.phase = "typing_final"
            self.typing_index = 0
            self.typing_timer.timeout.disconnect()
            self.typing_timer.timeout.connect(self.handle_typing)
            self.typing_timer.start(50)

    def prepare_final_fade(self):
        self.phase = "erasing_final"
        self.typing_index = len(self.final_message)
        self.typing_timer.timeout.disconnect()
        self.typing_timer.timeout.connect(self.erase_final)
        self.typing_timer.start(30)

    def erase_final(self):
        if self.typing_index > 0:
            self.typing_index -= 1
            self.label.setText(self.final_message[:self.typing_index])
        else:
            self.typing_timer.stop()
            self.start_fadeout()  # O fade-out é chamado aqui, no final do fluxo principal

    def start_fadeout(self):
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(800)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self._final_hide)
        self.fade_animation.start()

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if event.type() == QEvent.Resize:
            self.setGeometry(obj.rect())
        return super().eventFilter(obj, event)

    def _final_hide(self):
        self.spinner_timer.stop()
        self.hide()
        self.deleteLater()

        if callable(self.on_finished):
            self.on_finished()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Teste de Overlay")
    window.resize(800, 600)
    window.setStyleSheet("background-color: #1E1E1E;")
    overlay = LoadingOverlay(window)
    overlay.show()
    window.show()
    sys.exit(app.exec_())
    