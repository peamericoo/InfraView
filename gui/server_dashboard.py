from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFrame,
    QTextEdit,
    QSizePolicy,
    QPushButton,
)
from PyQt5.QtCore import Qt, QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from datetime import datetime
import time

from core.status_logic import get_logical_status
from core import pause_manager


class ServerDashboard(QWidget):
    def __init__(self, server_name, ip, interface):
        super().__init__()
        self.server_name = server_name
        self.ip = ip
        self.interface = interface

        self.paused = pause_manager.is_paused(ip)  # estado inicial

        self.status = None

        self.setWindowTitle(f"InfraView • {server_name} ({ip})")
        self.setMinimumSize(1300, 800)
        self.setStyleSheet(
            "font-family: 'Segoe UI'; background-color: #1e1e1e; color: #cccccc;"
        )

        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(2000)

        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ────────────────────────────────────────────────────────────────────
    # UI
    # ────────────────────────────────────────────────────────────────────
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # --- Painel esquerdo -------------------------------------------
        left_panel = QVBoxLayout()
        left_panel.setSpacing(20)
        left_panel.addWidget(self.build_identity_block())
        left_panel.addWidget(self.build_stats_block())
        left_panel.addWidget(self.build_alerts_block())
        left_panel.addStretch()

        left_widget = QWidget()
        left_widget.setLayout(left_panel)

        # --- Painel direito (gráfico) -----------------------------------
        right_panel = QVBoxLayout()
        chart_box = self.build_latency_chart()
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_panel.addWidget(chart_box)

        right_widget = QWidget()
        right_widget.setLayout(right_panel)

        layout.addWidget(left_widget, 2)
        layout.addWidget(right_widget, 3)

    # ------------------------------------------------------------------
    def stylized_field(self, label_text):
        container = QFrame()
        container.setStyleSheet("background-color: #2a2a2e; border-radius: 6px;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 6, 10, 6)
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 11pt; color: white;")
        layout.addWidget(label)
        return container

    # ------------------------------------------------------------------
    def build_identity_block(self):
        box = QGroupBox("Identidade do Servidor")
        self.apply_box_style(box)
        layout = QVBoxLayout()

        self.name_label = self.stylized_field(f"Nome: {self.server_name}")
        self.ip_label = self.stylized_field(f"IP: {self.ip}")
        self.status_label = QLabel("Status lógico: -")
        self.status_label.setAlignment(Qt.AlignLeft)
        self.status_label.setStyleSheet(
            "font-size: 11pt; padding: 6px 10px; border-radius: 6px;"
        )

        # >>> PAUSE-RESUME STYLE (criação do botão)
        self.pause_btn = QPushButton()
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.setFixedHeight(32)
        self.pause_btn.clicked.connect(self.on_toggle_pause)
        self._update_pause_button()  # define texto e cor inicial
        # <<< PAUSE-RESUME STYLE

        layout.addWidget(self.name_label)
        layout.addWidget(self.ip_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.pause_btn)  # botão visível logo abaixo do status

        self.online_label = self.stylized_field("Online: -")
        self.method_label = self.stylized_field("Método: -")

        layout.addWidget(self.online_label)
        layout.addWidget(self.method_label)

        box.setLayout(layout)
        return box

    # ------------------------------------------------------------------
    def build_stats_block(self):
        box = QGroupBox("Latência e Estatísticas")
        self.apply_box_style(box)
        layout = QVBoxLayout()

        self.latency_label = self.stylized_field("Latência atual: -")
        self.avg_label = self.stylized_field("Média: -")
        self.std_label = self.stylized_field("Desvio padrão: -")
        self.stable_label = self.stylized_field("Estável há: - ciclos")
        self.last_seen_label = self.stylized_field("Último ping: -")
        self.next_ping_label = self.stylized_field("Próximo ping: -")

        layout.addWidget(self.latency_label)
        layout.addWidget(self.avg_label)
        layout.addWidget(self.std_label)
        layout.addWidget(self.stable_label)
        layout.addWidget(self.last_seen_label)
        layout.addWidget(self.next_ping_label)

        box.setLayout(layout)
        return box

    # ------------------------------------------------------------------
    def build_alerts_block(self):
        box = QGroupBox("Alertas e Falhas Recentes")
        self.apply_box_style(box)
        layout = QVBoxLayout()

        self.alerts_text = QTextEdit()
        self.alerts_text.setReadOnly(True)
        self.alerts_text.setStyleSheet(
            "background-color: #1e1e1e; color: white; font-size: 10pt; padding: 10px;"
        )

        layout.addWidget(self.alerts_text)
        box.setLayout(layout)
        return box

    # ------------------------------------------------------------------
    def build_latency_chart(self):
        box = QGroupBox("Gráfico de Latência")
        self.apply_box_style(box)

        self.figure = Figure(facecolor="#252526")
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor("#1e1e1e")
        self.ax.tick_params(colors="white")
        self.ax.xaxis.label.set_color("white")
        self.ax.yaxis.label.set_color("white")
        self.ax.title.set_color("white")

        self.ax.set_title("Histórico de Latência")
        self.ax.set_xlabel("Tempo")
        self.ax.set_ylabel("ms")
        self.ax.grid(True, color="#333333")
        self.figure.tight_layout()
        self.figure.autofmt_xdate()

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        box.setLayout(layout)
        return box

    # ------------------------------------------------------------------
    def apply_box_style(self, box):
        box.setStyleSheet(
            """
            QGroupBox {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 10px;
                margin-top: 8px;
                padding: 10px;
                color: white;
                font-size: 10pt;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                top: -3px;
                padding: 6px 12px;
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3A3A3A, stop:1 #2D2D30
                );
                border-radius: 5px;
            }
        """
        )

    # ────────────────────────────────────────────────────────────────────
    # BOTÃO DE PAUSA – ESTILO E COMPORTAMENTO
    # ────────────────────────────────────────────────────────────────────
    # >>> PAUSE-RESUME STYLE (funções)
    def _update_pause_button(self):
        """Aplica texto e degradê conforme estado `self.paused`."""
        if self.paused:
            text = "Retomar"
            bg_grad = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #6B6B6B, stop:1 #3C3C3C)"
            )
            bg_grad_hover = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #7d7d7d, stop:1 #4a4a4a)"
            )
        else:
            text = "Pausar"
            bg_grad = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #007ACC, stop:1 #00C8FF)"
            )
            bg_grad_hover = (
                "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 #1589e6, stop:1 #33d5ff)"
            )

        self.pause_btn.setText(text)
        self.pause_btn.setStyleSheet(
            f"""
            QPushButton {{
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                background: {bg_grad};
                color: #ffffff;
                font-size: 11pt;
                font-weight: 600;
            }}
            QPushButton:hover:!disabled {{
                background: {bg_grad_hover};
            }}
            QPushButton:disabled {{
                background-color: #4e4e4e;
                color: #aaaaaa;
            }}
        """
        )

    def on_toggle_pause(self):
        self.pause_btn.setDisabled(True)  # evita duplo-clique
        try:
            pause_manager.toggle_pause(self.ip, not self.paused)
            self.paused = not self.paused
            self._update_pause_button()
        finally:
            QTimer.singleShot(300, lambda: self.pause_btn.setDisabled(False))
    # <<< PAUSE-RESUME STYLE

    # ────────────────────────────────────────────────────────────────────
    # ATUALIZAÇÃO DE STATUS
    # ────────────────────────────────────────────────────────────────────
    def update_status(self):
        status_dict = self.interface.get_full_snapshot()
        status = status_dict.get(self.ip)
        if not status:
            return

        profile = status.get("profile", {})
        self.paused = profile.get("paused", False)
        self._update_pause_button()

        # ➕ DEFINIÇÃO ANTECIPADA DE logical_status
        logical_status = get_logical_status(self.ip, status)

        self.status_label.setText(f"Status lógico: {logical_status}")

        status_colors = {
            "estavel": "#2ECC71",
            "instável": "#F39C12",
            "offline": "#E74C3C",
            "flutuante": "#f1c40f",
            "risco crescente": "#d35400",
            "observação": "#3498db",
            "firewall": "#9b59b6",
            "online_tcp": "#1abc9c",
            "crítico": "#c0392b",
            "erro_analise": "#bdc3c7",
            "pausado": "#95a5a6",
        }
        color = status_colors.get(logical_status.lower(), "#cccccc")
        self.status_label.setStyleSheet(
            f"""
            font-size: 11pt;
            padding: 6px 10px;
            border-radius: 6px;
            background-color: {color};
            color: black;
        """
        )

        is_online = logical_status == "online"

        self.online_label.layout().itemAt(0).widget().setText(
            f"Online: {'Sim' if is_online else 'Não'}"
        )
        self.method_label.layout().itemAt(0).widget().setText(
            f"Método: {profile.get('preferred_method', '-').upper()}"
        )

        self.latency_label.layout().itemAt(0).widget().setText(
            f"Latência atual: {status.get('latency', '-')} ms"
        )
        self.avg_label.layout().itemAt(0).widget().setText(
            f"Média: {round(profile.get('latency_avg', 0), 2)} ms"
        )
        self.std_label.layout().itemAt(0).widget().setText(
            f"Desvio padrão: {round(profile.get('latency_std', 0), 2)} ms"
        )
        self.stable_label.layout().itemAt(0).widget().setText(
            f"Estável há: {profile.get('stable_count', 0)} ciclos"
        )

        last_seen = profile.get("last_seen", "-")
        self.last_seen_label.layout().itemAt(0).widget().setText(
            f"Último ping: {last_seen[-8:] if last_seen != '-' else '-'}"
        )

        next_ping = profile.get("next_ping_at")
        if next_ping:
            restante = round(next_ping - time.time())
            self.next_ping_label.layout().itemAt(0).widget().setText(
                f"Próximo ping: em {restante}s"
            )

        # ---------- gráfico ------------------------------------------------
        self.ax.clear()
        history = profile.get("history", [])[-30:]
        if history:
            x = [datetime.fromisoformat(p["timestamp"]) for p in history]
            y = [p["latency"] for p in history]
            self.ax.fill_between(x, y, color="#4dd0e1", alpha=0.4)
            self.ax.plot(x, y, color="#4dd0e1", linewidth=2)
            self.ax.set_title("Histórico de Latência")
            self.ax.set_xlabel("Tempo")
            self.ax.set_ylabel("ms")
            self.ax.grid(True, color="#333333")
            self.figure.tight_layout()
            self.figure.autofmt_xdate()
        self.canvas.draw()

        # --------- alertas / falhas ---------------------------------------
        alerts = profile.get("alerts", [])
        failures = profile.get("failures", [])

        lines = []
        if alerts:
            lines.append("ALERTAS ATIVOS:")
            lines.extend(f"- {a}" for a in alerts)
            lines.append("")

        if failures:
            lines.append("FALHAS RECENTES:")
            for fail in failures[-5:]:
                ts = fail.get("timestamp", "--")
                msg = fail.get("mensagem", "(erro desconhecido)")
                lines.append(f"- [{ts[-8:]}] {msg}")

        self.alerts_text.setPlainText(
            "\n".join(lines) if lines else "Nenhum alerta ou falha recente."
        )


        # ---------- gráfico ------------------------------------------------
        self.ax.clear()
        history = profile.get("history", [])[-30:]
        if history:
            x = [datetime.fromisoformat(p["timestamp"]) for p in history]
            y = [p["latency"] for p in history]
            self.ax.fill_between(x, y, color="#4dd0e1", alpha=0.4)
            self.ax.plot(x, y, color="#4dd0e1", linewidth=2)
            self.ax.set_title("Histórico de Latência")
            self.ax.set_xlabel("Tempo")
            self.ax.set_ylabel("ms")
            self.ax.grid(True, color="#333333")
            self.figure.tight_layout()
            self.figure.autofmt_xdate()
        self.canvas.draw()

        # --------- alertas / falhas ---------------------------------------
        alerts = profile.get("alerts", [])
        failures = profile.get("failures", [])

        lines = []
        if alerts:
            lines.append("ALERTAS ATIVOS:")
            lines.extend(f"- {a}" for a in alerts)
            lines.append("")

        if failures:
            lines.append("FALHAS RECENTES:")
            for fail in failures[-5:]:
                ts = fail.get("timestamp", "--")
                msg = fail.get("mensagem", "(erro desconhecido)")
                lines.append(f"- [{ts[-8:]}] {msg}")

        self.alerts_text.setPlainText(
            "\n".join(lines) if lines else "Nenhum alerta ou falha recente."
        )
