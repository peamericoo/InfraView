CONSULTA_SEFAZ_ATIVA = False 

import json
import os
from datetime import datetime, timedelta
import re
import logging
import hashlib
from core.utils import get_data_path, validate_ip, resolve_and_ping
from gui.hive_view import HiveView
import mplcursors
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QTableWidget, QTableWidgetItem,
    QInputDialog, QMessageBox, QPlainTextEdit, QLabel, QGroupBox, QAbstractItemView, QSizePolicy, QScrollArea, QFrame,
    QGraphicsDropShadowEffect
)
from PyQt5.QtMultimedia import QSound
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QColor, QFont, QPainter, QBrush, QPen
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QSize, QEasingCurve, QSize, QTimer
from PyQt5.QtWidgets import QFrame
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from ping_engine import interface
from core.database import get_db_connection
from core.database import get_all_servers, insert_server
from gui.navigation_bar import NavigationBar
from ping_engine import interface


# Importa a tela de edição de servidores
from gui.edit_servers import EditServersWidget

from gui.loading_overlay import LoadingOverlay

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

ASSETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
OFFLINE_SOUND_PATH = os.path.join(ASSETS_PATH, "notification-2-269292.wav")

def create_circle_pixmap(color: QColor, diameter=12) -> QPixmap:
    pixmap = QPixmap(diameter, diameter)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QBrush(color))
    painter.setPen(QPen(Qt.NoPen))
    painter.drawEllipse(0, 0, diameter, diameter)
    painter.end()
    return pixmap

class MainWindow(QMainWindow):
    ping_update_signal = pyqtSignal(dict)  # sinal para atualizar a tabela com segurança
    sefaz_update_signal = pyqtSignal(dict) 
    def __init__(self):
        super().__init__()
        self.monitor_paused = False
        self.ping_update_signal.connect(self.update_table)
        self.setWindowIcon(QIcon(os.path.join(ASSETS_PATH, "logo.ico")))
        self.sarcasm_phrases = [
            "Zabbix ainda está instalando dependências...",
            "Grafana exige um DevOps só pra rodar.",
            "SNMP deveria ser crime em 2025.",
            "InfraView não precisa de plugins mágicos.",
            "Zabbix? Interface digna de Windows 95.",
            "Prometheus? Só prometeu.",
            "InfraView detecta falhas antes do cliente reclamar.",
            "Mais uptime que a energia da sua cidade.",
            "100% local, sem nuvem e sem desculpas.",
            "Latency hunter desde 2024.",
            "Sinta-se em casa, até o log tem design.",
            "Se isso aqui travar, é porque você arrancou o cabo.",
            "Monitoramento sexy e funcional.",
            "Não requer treinamento. Apenas bom gosto.",
            "Status: rodando. Concorrência: chorando.",
            "Beleza, eficiência, e sem licença Enterprise.",
        ]

        self.current_phrase_index = 0
        self.title_update_counter = 0
        print("MainWindow: início do __init__")
        self.setWindowTitle("InfraView - Monitor de Servidores")
        self.resize(1460, 930)

        db_rows = get_all_servers()
        self.servers = {row[1]: row[0] for row in db_rows}  # ip: name

                # Inicializa conexão e engine de ping
        # Inicializa conexão com o banco e vincula à engine
        db_conn = get_db_connection()
        
        # ------------------------------------------------------------------
        # Cria tabelas da engine (ip_profiles / engine_events) se não existirem
        # ------------------------------------------------------------------
        try:
            from ping_engine import database_access
            database_access.create_profile_and_event_tables()
        except Exception as e:
            logging.getLogger(__name__).error("Falha ao criar tabelas da engine: %s", e)


        def gui_callback(update_dict):
            print("[GUI] Update recebido:", update_dict)  # para depuração
            self.ping_update_signal.emit(update_dict)

        self.offline_count = {ip: 0 for ip in self.servers}
        self.failure_history = {ip: [] for ip in self.servers}
        self.dashboard_windows = []

        self.blink_timer = QTimer(self)
        self.blink_timer.setInterval(500)
        self.blink_timer.timeout.connect(self.toggleBlink)

        self.sound_timer = QTimer(self)
        self.sound_timer.setSingleShot(True)
        self.sound_timer.timeout.connect(self.handleSoundLoop)
        self.beep_active = False
        self.beep_phase = 0
        self.BEEP_LENGTH = 2000
        self.beepCount = 1
        self.beepWait = 7000
        self.loading_overlay = None


        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.title_timer = QTimer(self)
        self.title_timer.timeout.connect(self.update_window_title)
        self.title_timer.start(7000)  # Atualiza a cada 7 segundos

        # 🖤 MODO ESCURO APLICADO
        central_widget.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                color: #CCCCCC;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10pt;
            }
            QGroupBox {
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background-color: #252526;
            }                                     
            QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 4px 12px;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #3A3A3A, stop:1 #2D2D30);
            color: white;
            border-radius: 5px;
        }
            QLineEdit, QComboBox, QListWidget {
                background-color: #2D2D30;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                padding: 6px;
                color: #FFFFFF;
            }
            QPushButton {
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton#add {
                background-color: #27AE60;
                color: white;
            }
            QPushButton#add:hover {
                background-color: #1E8449;
            }
            QPushButton#remove {
                background-color: #C0392B;
                color: white;
            }
            QPushButton#remove:hover {
                background-color: #922B21;
            }
            QPushButton#edit {
                background-color: #F39C12;
                color: white;
            }
            QPushButton#edit:hover {
                background-color: #D68910;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 4px;
            }
            QScrollBar::handle:vertical {
                background: #5C5C5C;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                background: #3C3C3C;
                height: 12px;
            }
            QScrollBar::handle:vertical:hover {
                background: #888;
            }
        """)

        self.nav_bar = NavigationBar(self)
        self.nav_bar.addServerClicked.connect(self.showEditServers)
        #self.nav_bar.btn_add.clicked.connect(self.showEditServers)
        self.nav_bar.homeClicked.connect(self.showHomePage)
        main_layout.addWidget(self.nav_bar, 0)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        self.main_content = self.createMainPage()
        self.stack.addWidget(self.main_content)            # página Home
        self.stack.setCurrentWidget(self.main_content)  

        # ── inicia monitor da SEFAZ ─────────────────────────────── #
        if CONSULTA_SEFAZ_ATIVA:
            from core.sefaz_monitor import SefazConfig, SefazMonitor
            import asyncio
            import threading

            cfg = SefazConfig(
                uf="mt",
                certificado_path=r"C:\Users\Pedro Américo\Documents\Certificado Serpal\Serpal_Certificado.pfx",
                certificado_senha="19841607",
                doc_type="nfe",
                homologacao=True,
            )

            self.sefaz_monitor = SefazMonitor(cfg, on_update=self.sefaz_update_signal.emit)
            threading.Thread(
                target=lambda: asyncio.run(self.sefaz_monitor.start()),
                daemon=True
            ).start()
        else:
            logging.info("Consulta SEFAZ desativada pela configuração.")

        # ────────────────────────────────────────────────────────── #


        self.update_window_title()

        self.edit_servers_widget = EditServersWidget(self)
        self.last_db_hash = hashlib.md5(str(get_all_servers()).encode("utf-8")).hexdigest()
        self.stack.addWidget(self.edit_servers_widget)
        print("MainWindow: __init__ finalizado")
        interface.start_engine(gui_callback)


        #self.last_servers_json_hash = self.get_servers_json_hash()

    def handleCardDoubleClick(self, ip):
        for row, (srv_ip, name) in enumerate(self.servers.items()):
            if srv_ip == ip:
                self.open_dashboard(row, 0)
                break

    def reload_servers_data(self):
        db_rows = get_all_servers()
        self.servers = {row[1]: row[0] for row in db_rows}
        self.offline_count = {ip: 0 for ip in self.servers}
        self.failure_history = {ip: [] for ip in self.servers}
        self.rebuild_hive_view()

        # Remove visualmente os cards de servidores que não existem mais
        if hasattr(self, "server_list") and hasattr(self.server_list, "cards"):
            current_ips = set(self.servers.keys())
            obsolete = set(self.server_list.cards.keys()) - current_ips
            for ip in obsolete:
                card = self.server_list.cards.pop(ip, None)
                if card:
                    self.server_list.layout.removeWidget(card)
                    card.deleteLater()

        # 🧠 Espera meio segundo para evitar conflito entre atualização visual e thread de ping


    def createMainPage(self):
        """Cria layout principal (esquerda: lista/erros -- direita: card SEFAZ + Hive)."""
        main_content = QWidget()
        main_content_layout = QHBoxLayout(main_content)
        main_content_layout.setContentsMargins(10, 10, 10, 10)
        main_content_layout.setSpacing(10)

        # ───────────────────────── WIDGET ESQUERDO ───────────────────────── #
        left_widget = QWidget()
        left_vbox = QVBoxLayout(left_widget)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(10)

        # Servidores monitorados
        group_servers = QGroupBox("Servidores Monitorados")
        group_servers_layout = QVBoxLayout(group_servers)

        self.server_list = ServerListWidget(self, self.handleCardDoubleClick)
        self.server_scroll = QScrollArea()
        self.server_scroll.setWidgetResizable(True)
        self.server_scroll.setFrameShape(QFrame.NoFrame)
        self.server_scroll.setStyleSheet("background-color: transparent;")
        self.server_scroll.setWidget(self.server_list)
        group_servers_layout.addWidget(self.server_scroll)
        left_vbox.addWidget(group_servers)

        # Falhas offline
        group_falhas = QGroupBox("Registro de Falhas Offline")
        group_falhas_layout = QVBoxLayout(group_falhas)
        self.offline_log_area = QScrollArea()
        self.offline_log_area.setWidgetResizable(True)
        self.offline_log_area.setStyleSheet("background-color: #1E1E1E; border: none;")
        self.offline_log_area.setMaximumHeight(400)
        self.offline_log_container = QWidget()
        self.offline_log_layout = QVBoxLayout(self.offline_log_container)
        self.offline_log_container.setStyleSheet("background-color: #252526;")
        self.offline_log_layout.setContentsMargins(10, 10, 10, 10)
        self.offline_log_layout.setSpacing(10)
        self.offline_log_area.setWidget(self.offline_log_container)
        group_falhas_layout.addWidget(self.offline_log_area)
        left_vbox.addWidget(group_falhas)

        main_content_layout.addWidget(left_widget, 1)

        # ───────────────────────── WIDGET DIREITO ───────────────────────── #
        # 1. Card SEFAZ
        self.sefaz_card = SefazStatusCard()
        self.sefaz_update_signal.connect(self.sefaz_card.update_status)

        # 2. HiveView (já existia)
        self.group_hive = QGroupBox("Visão Colmeia")
        group_hive_layout = QVBoxLayout(self.group_hive)

        db_rows = get_all_servers()
        servers_data = [
            (name, ip, 0, folder or "", color or "#000000")
            for name, ip, status, folder, color in db_rows
        ]
        servers_data.sort(key=lambda x: (x[3] == '', x[3].lower(), x[0].lower()))
        self.hive_view = HiveView(servers_data, columns=4)
        group_hive_layout.addWidget(self.hive_view)

        # 3. Sobrepõe o card na colmeia (canto inferior-direito)
        overlay = HiveOverlay(self.group_hive, self.sefaz_card)
        main_content_layout.addWidget(overlay, 1)

        return main_content


    def showEditServers(self):
        # Alterna para a tela de edição de servidores
        self.stack.setCurrentWidget(self.edit_servers_widget)

    def add_server(self):
        ip, ok = QInputDialog.getText(self, "Adicionar Servidor", "IP do Servidor:")
        if ok and ip:
            if not validate_ip(ip):
                QMessageBox.critical(self, "Erro", "Endereço IP inválido!")
                return
            name, ok_name = QInputDialog.getText(self, "Adicionar Servidor", "Nome do Servidor:")
            if ok_name and name:
                self.servers[ip] = name
                self.offline_count[ip] = 0
                self.failure_history[ip] = []
                self.rebuild_hive_view()

    def open_dashboard(self, row, column=0):
        try:
            ip = list(self.servers.keys())[row]
            name = self.servers[ip]
            history = self.failure_history.get(ip, [])
            dashboard = ServerDashboard(name, ip, history)
            dashboard.show()
            self.dashboard_windows.append(dashboard)
        except IndexError:
            print("Erro ao abrir dashboard: índice fora do intervalo.")



    def rebuild_hive_view(self):
        if self.group_hive is not None:
            layout = self.group_hive.layout()
            if layout is not None and self.hive_view is not None:
                layout.removeWidget(self.hive_view)
                self.hive_view.deleteLater()

            db_rows = get_all_servers()
            servers_data = [
                (name, ip, 0, folder or "", color or "#000000")
                for name, ip, status, folder, color in db_rows
            ]
            servers_data.sort(key=lambda x: (x[3] == '', x[3].lower(), x[0].lower()))

            self.hive_view = HiveView(servers_data, columns=4)
            layout.addWidget(self.hive_view)

    def update_table(self, status_dict):
        # ✅ Protege a GUI contra sinais atrasados da thread contendo IPs já removidos
        if set(status_dict.keys()) - set(self.servers.keys()):
            return

        log_lines = []
        updated_hive_data = []
        offline_count = 0
        self.server_list.update_servers(status_dict, self.servers)

        for ip, name in self.servers.items():
            status = status_dict.get(ip, {})
            online = status.get("online", False)
            latency = status.get("latency", 0)

            if not online:
                self.offline_count[ip] = self.offline_count.get(ip, 0) + 1
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                entry = f"[{timestamp}] Falha: {self.offline_count[ip]} consecutivas"
                self.failure_history[ip].append(entry)
                log_lines.append(f"[{timestamp}] {name} ({ip}): {self.offline_count[ip]} falha(s)")
                offline_count += 1
            else:
                self.offline_count[ip] = 0

        from core.database import get_all_servers

        db_rows = get_all_servers()
        servers_lookup = {
                ip: (name, ip, folder or "", color or "#000000")
                for name, ip, status, folder, color in db_rows
            }

        updated_hive_data.clear()
        for ip, (name, ip, folder, color) in servers_lookup.items():
            latency = status_dict.get(ip, {}).get("latency", 0)
            updated_hive_data.append((name, ip, latency, folder, color))

        for i in reversed(range(self.offline_log_layout.count())):
            widget_to_remove = self.offline_log_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        if log_lines:
            for entry in log_lines:
                match = re.search(r"\[(.*?)\]", entry)
                if match:
                    raw_timestamp = match.group(1)
                    try:
                        dt = datetime.strptime(raw_timestamp, "%Y-%m-%d %H:%M:%S")
                        date_str = dt.strftime("%d/%m/%Y")
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        date_str = "Data inválida"
                        time_str = ""
                else:
                    raw_timestamp = ""
                    date_str = "Desconhecida"
                    time_str = ""

                body = entry.replace(f"[{raw_timestamp}]", "").strip()
                server_info = body.split(":")[0].strip()
                fail_info = body.split(":")[1].strip() if ":" in body else "Falha desconhecida"

                frame = QFrame()
                frame.setStyleSheet("""
                QFrame {
                    background-color: #2D2D30;
                    border: 1px solid #3C3C3C;
                    border-radius: 12px;
                }
                """)
                layout = QVBoxLayout(frame)
                layout.setContentsMargins(14, 12, 14, 12)
                layout.setSpacing(8)

                title = QLabel(server_info)
                title.setStyleSheet("""
                    font-size: 17px;
                    font-weight: bold;
                    background-color: #2C3E50;
                    color: white;
                    padding: 6px 12px;
                    border-radius: 6px;
                """)

                info_container = QWidget()
                info_layout = QHBoxLayout(info_container)
                info_container.setStyleSheet("background-color: #2D2D30;")
                info_layout.setContentsMargins(0, 0, 0, 0)
                info_layout.setSpacing(10)

                def styled_info(text, icon, color, bold=False):
                    label = QLabel(f"{icon} {text}")
                    weight = "bold" if bold else "600"
                    label.setStyleSheet(f"""
                        font-size: 12px;
                        font-weight: {weight};
                        color: {color};
                        border: 1px solid #3C3C3C;
                        border-radius: 6px;
                        padding: 3px 8px;
                        background-color: #1E1E1E;
                    """)
                    return label

                fail_label = styled_info(fail_info, "❗", "#E74C3C")
                date_label = styled_info(date_str, "📅", "#FFFFFF", bold=True)
                time_label = styled_info(time_str, "🕒", "#FFFFFF", bold=True)


                info_layout.addWidget(fail_label)
                info_layout.addWidget(date_label)
                info_layout.addWidget(time_label)
                info_layout.addStretch()

                layout.addWidget(title)
                layout.addWidget(info_container)

                self.offline_log_layout.addWidget(frame)
        else:
            placeholder = QLabel("Nenhuma falha registrada")
            placeholder.setStyleSheet("color: gray; font-style: italic; padding: 8px;")
            self.offline_log_layout.addWidget(placeholder)

        if len(updated_hive_data) == len(self.hive_view.cells):
            self.hive_view.update_all(updated_hive_data)

        if offline_count > 0 and not self.blink_timer.isActive():
            self.blink_timer.start()
        elif offline_count == 0 and self.blink_timer.isActive():
            self.blink_timer.stop()

        if self.isMinimized() and offline_count > 0:
            self.startBeepLoop(offline_count)
        else:
            self.stopBeepLoop()

    
    # ------------------------------------------------------------------ #
    def toggleBlink(self):
        """
        Percorre todos os cards e pede para piscarem se estiverem offline.
        """
        for card in self.server_list.cards.values():
            card.blink()



    def startBeepLoop(self, offline_count):
        if not self.beep_active:
            self.beep_active = True
            self.beep_phase = 0
            if offline_count == 1:
                self.beepCount = 1
                self.beepWait = 9000
            else:
                self.beepCount = 2
                self.beepWait = 7000
            self.sound_timer.start(0)

    def stopBeepLoop(self):
        if self.beep_active:
            self.beep_active = False
            self.beep_phase = 0
            self.beepCount = 0
            self.sound_timer.stop()

    def handleSoundLoop(self):
        if not self.beep_active:
            return
        if not self.isMinimized():
            self.stopBeepLoop()
            return

        if self.beep_phase < self.beepCount:
            self.playSound()
            self.beep_phase += 1
            self.sound_timer.start(self.BEEP_LENGTH)
        else:
            self.beep_phase = 0
            self.sound_timer.start(self.beepWait)

    def playSound(self):
        if os.path.exists(OFFLINE_SOUND_PATH):
            QSound.play(OFFLINE_SOUND_PATH)
        else:
            print("Arquivo de som não encontrado:", OFFLINE_SOUND_PATH)

    def showHomePage(self):
        """
        Quando o botão Home é clicado, verificamos se houve alterações no banco.
        Se sim, recarregamos os dados e reconstruímos a interface.
        """
        db_rows = get_all_servers()
        new_hash = hashlib.md5(str(db_rows).encode("utf-8")).hexdigest()

        if not hasattr(self, "last_db_hash") or self.last_db_hash != new_hash:
            self.last_db_hash = new_hash
            self.reload_servers_data()

        self.stack.setCurrentWidget(self.main_content)

    def update_window_title(self):
        phrase = self.sarcasm_phrases[self.current_phrase_index]

        # Avança para a próxima frase sempre
        self.current_phrase_index = (self.current_phrase_index + 1) % len(self.sarcasm_phrases)

        # Define o título simplificado
        title = f"InfraView Monitoring – {phrase}"

        self.setWindowTitle(title)

# As classes ServerDashboard permanecem inalteradas
class ServerDashboard(QMainWindow):
    def __init__(self, server_name, ip, failure_history):
        super().__init__()
        self.server_name = server_name
        self.ip = ip
        self.failure_history = failure_history
        self.setWindowTitle(f"Dashboard - {server_name} ({ip})")
        self.resize(900, 600)
        self._x_sorted = []
        self._y_sorted = []
        self._tooltips_sorted = []
        self.last_bucket = None
        self.last_y_max = None
        self.initUI()
        self.start_clock()
        self.start_graph_update()

    def initUI(self):
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #D3D3D3;")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.clock_label = QLabel()
        self.clock_label.setAlignment(Qt.AlignCenter)
        self.clock_label.setStyleSheet("font-size: 24px; background-color: #D3D3D3;")
        main_layout.addWidget(self.clock_label)
        hbox = QHBoxLayout()
        main_layout.addLayout(hbox)
        left_widget = QWidget()
        left_widget.setStyleSheet("background-color: #D3D3D3;")
        left_layout = QVBoxLayout(left_widget)
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.canvas)
        hbox.addWidget(left_widget)
        right_widget = QWidget()
        right_widget.setStyleSheet("background-color: #D3D3D3;")
        right_layout = QVBoxLayout(right_widget)
        self.console_view = QPlainTextEdit()
        self.console_view.setReadOnly(True)
        self.console_view.setPlaceholderText("Clique em uma bolinha para ver os detalhes do intervalo.")
        self.console_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.console_view)
        hbox.addWidget(right_widget)
        self.canvas.mpl_connect("pick_event", self.on_pick)

    def start_clock(self):
        self.timer_clock = QTimer(self)
        self.timer_clock.timeout.connect(self.update_clock)
        self.timer_clock.start(1000)
        self.update_clock()

    def update_clock(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.clock_label.setText(current_time)

    def start_graph_update(self):
        self.timer_graph = QTimer(self)
        self.timer_graph.timeout.connect(self.update_graph)
        self.timer_graph.start(3000)
        self.update_graph()

    def update_graph(self):
        self.ax.clear()
        now = datetime.now()
        cutoff_time = now - timedelta(minutes=10)
        filtered_history = []
        pattern_dt = r'\[(.*?)\]'
        for entry in self.failure_history:
            match_dt = re.search(pattern_dt, entry)
            if match_dt:
                try:
                    dt_event = datetime.strptime(match_dt.group(1), "%Y-%m-%d %H:%M:%S")
                    if dt_event >= cutoff_time:
                        filtered_history.append(entry)
                except:
                    continue
        groups = {}
        pattern_fail = r'Falha: (\d+) consecutivas'
        for entry in filtered_history:
            match_dt = re.search(pattern_dt, entry)
            match_fail = re.search(pattern_fail, entry)
            if match_dt and match_fail:
                try:
                    dt_event = datetime.strptime(match_dt.group(1), "%Y-%m-%d %H:%M:%S")
                    bucket = int(dt_event.timestamp() // 60)
                    groups.setdefault(bucket, {"times": [], "entries": []})
                    groups[bucket]["times"].append(dt_event)
                    groups[bucket]["entries"].append(entry)
                except Exception:
                    continue
        xs, ys, tooltips = [], [], []
        for bucket in sorted(groups.keys()):
            bucket_time = datetime.fromtimestamp(bucket * 60)
            xs.append(bucket_time)
            failure_values = []
            for msg in groups[bucket]["entries"]:
                m = re.search(pattern_fail, msg)
                if m:
                    failure_values.append(int(m.group(1)))
            max_failure = max(failure_values) if failure_values else 0
            ys.append(max_failure)
            tooltip_text = "\n".join(groups[bucket]["entries"])
            tooltips.append(tooltip_text)
        if xs and ys:
            data = sorted(zip(xs, ys, tooltips), key=lambda x: x[0])
            x_sorted = [d[0] for d in data]
            y_sorted = [d[1] for d in data]
            tooltips_sorted = [d[2] for d in data]
            self._x_sorted = x_sorted
            self._y_sorted = y_sorted
            self._tooltips_sorted = tooltips_sorted
            new_last_bucket = x_sorted[-1]
            new_y_max = max(y_sorted)
            if self.last_bucket is None or new_last_bucket != self.last_bucket:
                self.last_bucket = new_last_bucket
                self.last_y_max = new_y_max
            if self.last_y_max is None:
                self.last_y_max = new_y_max
            if new_y_max > self.last_y_max:
                self.last_y_max = new_y_max
            self.ax.fill_between(x_sorted, 0, y_sorted, color='salmon', alpha=0.2)
            self.ax.plot(x_sorted, y_sorted, '-o', color='red')
            self.scatter = self.ax.scatter(x_sorted, y_sorted, marker='o', facecolor='yellow', edgecolor='black', picker=True)
            self.ax.set_ylim(0, self.last_y_max + 1)
            self.ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            self.ax.set_title("Histórico de Falhas")
            self.ax.set_xlabel("Exibindo últimos 10 minutos\n(Agrupados em 1 minuto)")
            self.ax.set_ylabel("Máximo de Falhas Consecutivas")
            self.ax.tick_params(axis='x', which='both', length=0)
            self.ax.set_xticklabels([])
        else:
            self.ax.text(0.5, 0.5, "Sem falhas", horizontalalignment='center',
                         verticalalignment='center', transform=self.ax.transAxes, fontsize=12)
        self.figure.tight_layout()
        self.canvas.draw()

    def on_pick(self, event):
        if event.artist is not self.scatter:
            return
        if len(event.ind) == 0:
            return
        ind = event.ind[0]
        interval_time = self._x_sorted[ind].strftime("%H:%M")
        details = self._tooltips_sorted[ind]
        self.console_view.setPlainText(f"Intervalo: {interval_time}\n{details}")

class ServerCard(QWidget):
    card_clicked = pyqtSignal(str)
    """
    Card único de servidor:
      • Colunas com largura fixa (IP, latência);
      • Nome se expande (ou elide) sem reduzir fonte;
      • Duplo‑clique em QUALQUER parte do card abre o dashboard;
      • Guarda estado online/offline – usado pelo pisca‑pisca.
    """
    def __init__(self, name, ip, parent=None):
        super().__init__(parent)
        self.name = name
        self.ip = ip
        self.online = True          # ← novo
        self.blink_state = False    # ← novo

        self.setFixedHeight(46)
        self.setStyleSheet("""
            QWidget { background-color:#2D2D30;
                      border:1px solid #3C3C3C;
                      border-radius:8px; }
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(16)

        # • status dot
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(12, 12)
        self.status_dot.setStyleSheet("border-radius:6px; background-color:gray;")
        lay.addWidget(self.status_dot)

        # • nome (expansível + elide)
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("font-weight:bold; color:white;")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self.name_label, 1)
        # permite ao ServerCard interceptar o double‑click do label


        # • IP (fixo)
        self.ip_label = QLabel(ip)
        self.ip_label.setStyleSheet("color:#BBBBBB;")
        self.ip_label.setAlignment(Qt.AlignCenter)  # Centralizar visualmente
        self.ip_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)  # Expansível como os outros
        lay.addWidget(self.ip_label, 1)  # Adicione peso proporcional como nos outros

        # • latência (fixo, alinhado à direita)
        self.latency_label = QLabel("-- ms")
        self.latency_label.setStyleSheet("color:#AAAAAA;")
        self.latency_label.setFixedWidth(64)
        self.latency_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.latency_label)

        # • status textual (fixo)
        self.status_label = QLabel("...")
        self.status_label.setStyleSheet("color:#CCCCCC;")
        self.status_label.setFixedWidth(100)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lay.addWidget(self.status_label)

    # ------------------------------------------------------------ #
    def set_status(self, online: bool, latency: int, status_text: str = ""):
        self.online = online
        color = "#2ECC71" if online else "#E74C3C"
        self.status_dot.setStyleSheet(f"border-radius:6px; background-color:{color};")
        self.latency_label.setText(f"{latency} ms" if latency > 0 else "N/A")
        self.status_label.setText(status_text or ("Desconhecido" if not online else "estável"))

    # --- piscar: alterna ponto entre vermelho e transparente ---- #
    def blink(self):
        if self.online:
            return
        self.blink_state = not self.blink_state
        color = "#E74C3C" if self.blink_state else "transparent"
        self.status_dot.setStyleSheet(f"border-radius:6px; background-color:{color};")

    # --- duplo‑clique em QUALQUER lugar do card ----------------- #
    def mouseDoubleClickEvent(self, ev):
        self.card_clicked.emit(self.ip)


class ServerListWidget(QWidget):
    def __init__(self, parent=None, on_card_double_click=None):
        super().__init__(parent)
        self.cards: dict[str, ServerCard] = {}
        self.on_card_double_click = on_card_double_click
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(0, 0, 0, 0)

    # ------------------------------------------------------------------ #
    def update_servers(self, status_dict: dict, known_servers: dict):
        obsolete = set(self.cards) - set(known_servers)
        for ip in obsolete:
            card = self.cards.pop(ip, None)
            if card:
                self.layout.removeWidget(card)
                card.deleteLater()

        # Garante que todos os conhecidos tenham card
        for ip, name in known_servers.items():
            if ip not in self.cards:
                card = ServerCard(name, ip)
                if self.on_card_double_click:
                    card.card_clicked.connect(self.on_card_double_click)
                self.cards[ip] = card
                self.layout.addWidget(card)

            # Aplica status se disponível
            status = status_dict.get(ip)
            if status:
                self.cards[ip].set_status(
                    status.get("online", False),
                    status.get("latency", 0)
                )
            else:
                self.cards[ip].set_status(False, 0)  # padrão: offline e latência 0

        # Reordena visualmente pelo status
        def sort_key(ip):
            status = status_dict.get(ip, {})
            return (status.get("online", True), ip)

        sorted_ips = sorted(known_servers, key=sort_key)

        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                self.layout.removeWidget(widget)

        for ip in sorted_ips:
            self.layout.addWidget(self.cards[ip])



        # ---- 2. ATUALIZA EXISTENTES ou CRIA NOVOS -------------------- #
        def sort_key(ip):
            status = status_dict.get(ip, {})
            return (status.get("online", True), ip)

        for ip in sorted(known_servers, key=sort_key):
            name = known_servers[ip]

            # cria se ainda não existir
            if ip not in self.cards:
                # ⛔️ Pula a criação de card se ainda não foi pingado
                if ip not in status_dict:
                    continue

                card = ServerCard(name, ip)
                if self.on_card_double_click:
                    card.card_clicked.connect(self.on_card_double_click)

                self.layout.addWidget(card)
                self.cards[ip] = card

            else:
                card = self.cards[ip]

            # aplica status / latência
            status = status_dict.get(ip, {})
            card.set_status(
                status.get("online", False),
                status.get("latency", 0),
                status.get("status", "")
            )
            
            # --- Reordena visualmente os widgets no layout ---
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                self.layout.removeWidget(widget)

        # Ordena pelo status atual
        sorted_ips = sorted(known_servers, key=sort_key)
        for ip in sorted_ips:
            card = self.cards[ip]
            self.layout.addWidget(card)
class HiveOverlay(QWidget):
    """
    Contêiner que exibe o HiveView em tela cheia e sobrepõe
    um widget (card) no canto inferior-direito.
    """
    def __init__(self, hive_widget: QWidget, overlay_widget: QWidget, margin: int = 12):
        super().__init__()
        self._margin = margin
        self._hive = hive_widget
        self._overlay = overlay_widget

        # Hive preenche tudo
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._hive)

        # overlay é filho direto para ficar por cima
        self._overlay.setParent(self)
        self._overlay.installEventFilter(self)

    # reposiciona o overlay sempre que redimensionar
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._reposition()

    # ---------------- posicionamento --------------- #
    def _reposition(self):
        """Move o overlay p/ canto inf-dir respeitando margem."""
        sz = self._overlay.size()
        x  = max(self._margin, self.width()  - sz.width()  - self._margin)
        y  = max(self._margin, self.height() - sz.height() - self._margin)
        self._overlay.move(x, y)


    def eventFilter(self, obj, event):
        if obj is self._overlay and event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(obj, event)


class SefazStatusCard(QFrame):
    """
    Card de status da SEFAZ, minimalista contraído e completo expandido.
    """

    _COLLAPSED = QSize(200, 86)
    _EXPANDED  = QSize(360, 136)

    def __init__(self, parent=None):
        super().__init__(parent)

        # ---- sombra (QGraphicsDropShadowEffect) ----
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        # ---- dimensões/estilo base ----
        self.setMinimumSize(self._COLLAPSED)
        self.setMaximumSize(self._EXPANDED)
        self.resize(self._COLLAPSED)
        self.setStyleSheet("""
            QFrame        { background-color:#2D2D30; border:none; border-radius:14px; }
            QLabel#title  { font-size:20px; font-weight:700; color:#FFFFFF;
                            padding:2px 10px; border-radius:8px; }
            QLabel#status { font-size:15px; }
            QLabel#count  { font-size:13px; color:#BBBBBB; }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(6)

        self.title_lbl  = QLabel("Sefaz - MT", objectName="title")
        self.status_lbl = QLabel("--",         objectName="status")
        self.count_lbl  = QLabel("",           objectName="count")
        lay.addWidget(self.title_lbl)
        lay.addWidget(self.status_lbl)
        lay.addWidget(self.count_lbl)

        # animação tamanho
        self._anim = QPropertyAnimation(self, b"size", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setDuration(200)

        # timer contagem
        self._cd_timer = QTimer(self)
        self._cd_timer.timeout.connect(self._tick)
        self._remaining = 0

        # estado
        self._is_expanded   = False
        self._simple_status = "--"
        self._full_status   = "--"
        self._current_grad  = "green"
        self.count_lbl.hide()

    # ---------- animação de hover ----------
    def enterEvent(self, ev):
        self._toggle(True)
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._toggle(False)
        super().leaveEvent(ev)

    # ---------- API pública ----------
    def update_status(self, payload: dict):
        cstat      = payload.get("status", "")
        motivo     = payload.get("motivo", "--")
        self._remaining = payload.get("next_in", 60)
        self._full_status = f"{cstat} – {motivo}"

        if cstat in {"107", "108"}:
            self._simple_status = "OK"
            color = "#2ECC71"
            grad  = "green"
        elif cstat in {"109", "110"}:
            self._simple_status = "Lento"
            color = "#F1C40F"
            grad  = "green"
        else:
            self._simple_status = "Erro"
            color = "#E74C3C"
            grad  = "red"

        # pinta texto do status
        self.status_lbl.setStyleSheet(f"font-size:15px; color:{color};")

        # aplica gradiente se mudou
        if grad != self._current_grad:
            if grad == "green":
                g_css = ("background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                         "stop:0 #27AE60, stop:1 #1E8449);")
            else:  # red
                g_css = ("background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                         "stop:0 #C0392B, stop:1 #922B21);")
            self.title_lbl.setStyleSheet(
                "font-size:20px; font-weight:700; color:#FFFFFF; "
                "padding:2px 10px; border-radius:8px;" + g_css
            )
            self._current_grad = grad

        self._apply_mode()

        if self._cd_timer.isActive():
            self._cd_timer.stop()
        self._cd_timer.start(1000)

    # ---------- helpers ----------
    def _toggle(self, expand: bool):
        if self._is_expanded == expand:
            return
        self._is_expanded = expand
        self._anim.stop()
        self._anim.setStartValue(self.size())
        self._anim.setEndValue(self._EXPANDED if expand else self._COLLAPSED)
        self._anim.start()
        self._apply_mode()

    def _apply_mode(self):
        if self._is_expanded:
            self.status_lbl.setText(self._full_status)
            self.count_lbl.show()
        else:
            self.status_lbl.setText(self._simple_status)
            self.count_lbl.hide()

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self._cd_timer.stop()
            self.count_lbl.setText("consultando…")
        else:
            self.count_lbl.setText(f"🔄 próxima em {self._remaining:02d}s")



if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
