import json
import os
from datetime import datetime, timedelta
import re
import logging
import hashlib
from hive_view import HiveView
import mplcursors
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QTableWidget, QTableWidgetItem,
    QInputDialog, QMessageBox, QPlainTextEdit, QLabel, QGroupBox, QAbstractItemView, QSizePolicy
)
from PyQt5.QtMultimedia import QSound
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QColor, QFont, QPainter, QBrush, QPen
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from monitor import MonitorThread
from config import load_servers, save_servers
from utils import validate_ip
from navigation_bar import NavigationBar

# Importa a tela de edição de servidores
from edit_servers import EditServersWidget

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
OFFLINE_SOUND_PATH = "notification-2-269292.wav"

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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("InfraView - Monitor de Servidores")
        self.resize(1460, 930)
        # Carrega os dados e converte o JSON para o formato {ip: nome}
        loaded = load_servers()
        if isinstance(loaded, dict) and "servers" in loaded:
            self.servers = {server["ip"]: server["name"] for server in loaded["servers"]}
        else:
            self.servers = loaded  # fallback se não estiver no novo formato

        self.offline_count = {ip: 0 for ip in self.servers}
        self.failure_history = {ip: [] for ip in self.servers}
        self.dashboard_windows = []
        self.monitor_paused = True
        self.monitor_thread = None

        self.blink_timer = QTimer(self)
        self.blink_timer.setInterval(500)
        self.blink_timer.timeout.connect(self.toggleBlink)
        self.blink_state = False

        self.sound_timer = QTimer(self)
        self.sound_timer.setSingleShot(True)
        self.sound_timer.timeout.connect(self.handleSoundLoop)
        self.beep_active = False
        self.beep_phase = 0
        self.BEEP_LENGTH = 2000
        self.beepCount = 1
        self.beepWait = 7000

        # Layout principal: cria um HBox com a sidebar à esquerda
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Instancia a NavigationBar
        self.nav_bar = NavigationBar(self)
        self.nav_bar.addServerClicked.connect(self.add_server)
        self.nav_bar.btn_add.clicked.connect(self.showEditServers)  # Conecta o botão de adicionar à tela de edição

        # Conectar o sinal homeClicked ao método showHomePage
        self.nav_bar.homeClicked.connect(self.showHomePage)

        main_layout.addWidget(self.nav_bar, 0)

        # Cria o QStackedWidget para alternar entre as telas
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        # Página inicial
        self.main_content = self.createMainPage()
        self.stack.addWidget(self.main_content)

        # Tela de edição de servidores
        self.edit_servers_widget = EditServersWidget(self)
        self.stack.addWidget(self.edit_servers_widget)

        self.table.cellDoubleClicked.connect(self.open_dashboard)
        self.populate_table()

        self.last_servers_json_hash = self.get_servers_json_hash()

    def reload_servers_data(self):
        loaded = load_servers()
        if isinstance(loaded, dict) and "servers" in loaded:
            self.servers = {server["ip"]: server["name"] for server in loaded["servers"]}
        else:
            self.servers = loaded
        self.offline_count = {ip: 0 for ip in self.servers}
        self.failure_history = {ip: [] for ip in self.servers}
        self.refresh_table()
        self.rebuild_hive_view()

    def get_servers_json_hash(self):
        try:
            with open("servers.json", "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def createMainPage(self):
        main_content = QWidget()
        main_content_layout = QHBoxLayout(main_content)
        main_content_layout.setContentsMargins(10, 10, 10, 10)
        main_content_layout.setSpacing(10)

        # Widget esquerdo: tabela e registro de falhas
        left_widget = QWidget()
        left_vbox = QVBoxLayout(left_widget)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(10)
        group_servers = QGroupBox("Servidores Monitorados")
        group_servers_layout = QVBoxLayout(group_servers)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Nome", "IP", "Status", "Latência (ms)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        group_servers_layout.addWidget(self.table)
        left_vbox.addWidget(group_servers)
        group_falhas = QGroupBox("Registro de Falhas Offline")
        group_falhas_layout = QVBoxLayout(group_falhas)
        self.offline_log = QPlainTextEdit()
        self.offline_log.setReadOnly(True)
        self.offline_log.setStyleSheet("background-color: #F0F0F0; padding: 5px;")
        self.offline_log.setPlaceholderText("Nenhuma falha registrada")
        group_falhas_layout.addWidget(self.offline_log)
        left_vbox.addWidget(group_falhas)
        main_content_layout.addWidget(left_widget, 1)

        # Widget direito: HiveView
        self.group_hive = QGroupBox("Visão Colmeia")
        self.group_hive.setObjectName("group_hive")
        group_hive_layout = QVBoxLayout(self.group_hive)
        servers_data = [(self.servers[ip], 0) for ip in self.servers]
        self.hive_view = HiveView(servers_data, columns=4)
        group_hive_layout.addWidget(self.hive_view)
        main_content_layout.addWidget(self.group_hive, 1)

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
                save_servers(self.servers)
                self.refresh_table()
                if not self.monitor_paused and self.monitor_thread is not None:
                    self.monitor_thread.servers = list(self.servers.keys())
                self.rebuild_hive_view()

    def open_dashboard(self, row, column):
        if column != 0:
            return
        name = self.table.item(row, 0).text()
        ip = self.table.item(row, 1).text()
        history = self.failure_history.get(ip, [])
        dashboard = ServerDashboard(name, ip, history)
        dashboard.show()
        self.dashboard_windows.append(dashboard)

    def populate_table(self):
        self.table.setRowCount(len(self.servers))
        for row, (ip, name) in enumerate(self.servers.items()):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(ip))
            self.table.setItem(row, 2, QTableWidgetItem("Desconhecido"))
            self.table.setItem(row, 3, QTableWidgetItem("N/A"))

    def rebuild_hive_view(self):
        if self.group_hive is not None:
            layout = self.group_hive.layout()
            if layout is not None and self.hive_view is not None:
                layout.removeWidget(self.hive_view)
                self.hive_view.deleteLater()
            servers_data = [(self.servers[ip], 0) for ip in self.servers]
            self.hive_view = HiveView(servers_data, columns=4)
            layout.addWidget(self.hive_view)

    def setupMonitor(self):
        if not self.monitor_paused:
            self.monitor_thread = MonitorThread(list(self.servers.keys()))
            self.monitor_thread.update_signal.connect(self.update_table)
            self.monitor_thread.start()

    def update_table(self, status_dict):
        log_lines = []
        updated_hive_data = []
        offline_count = 0
        for row in range(self.table.rowCount()):
            ip_item = self.table.item(row, 1)
            ip = ip_item.text()
            server_name = self.table.item(row, 0).text()
            status = status_dict.get(ip, {})
            latency = 0
            if status:
                online = status.get('online', False)
                latency = status.get('latency', 0)
                if not online and latency == 0:
                    latency = -1
                if online:
                    status_text = "Online"
                    status_color = QColor("green")
                else:
                    status_text = "Offline"
                    status_color = QColor("red")
                    offline_count += 1
                pixmap = create_circle_pixmap(status_color, diameter=12)
                item = QTableWidgetItem(status_text)
                item.setIcon(QIcon(pixmap))
                item.setForeground(status_color)
                self.table.setItem(row, 2, item)
                lat_text = str(latency) if latency > 0 else "N/A"
                self.table.setItem(row, 3, QTableWidgetItem(lat_text))
                if not online:
                    self.offline_count[ip] = self.offline_count.get(ip, 0) + 1
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    entry = f"[{timestamp}] Falha: {self.offline_count[ip]} consecutivas"
                    self.failure_history[ip].append(entry)
                    log_lines.append(f"[{timestamp}] {server_name} ({ip}): {self.offline_count[ip]} falha(s)")
                else:
                    self.offline_count[ip] = 0
            updated_hive_data.append((server_name, latency))
        self.offline_log.setPlainText("\n".join(log_lines) if log_lines else "Nenhuma falha registrada")
        if len(updated_hive_data) == len(self.hive_view.cells):
            self.hive_view.update_all(updated_hive_data)
        if offline_count > 0:
            if not self.blink_timer.isActive():
                self.blink_timer.start()
        else:
            if self.blink_timer.isActive():
                self.blink_timer.stop()
                self.restoreOfflineColors()
        if self.isMinimized() and offline_count > 0:
            self.startBeepLoop(offline_count)
        else:
            self.stopBeepLoop()

    def toggleBlink(self):
        self.blink_state = not self.blink_state
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 2)
            if status_item and status_item.text() == "Offline":
                if self.blink_state:
                    status_item.setForeground(QColor("red"))
                    status_item.setIcon(QIcon(create_circle_pixmap(QColor("red"), 12)))
                else:
                    transparent = QColor(255, 0, 0, 0)
                    status_item.setForeground(transparent)
                    status_item.setIcon(QIcon(create_circle_pixmap(transparent, 12)))

    def restoreOfflineColors(self):
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 2)
            if status_item and status_item.text() == "Offline":
                status_item.setForeground(QColor("red"))
                status_item.setIcon(QIcon(create_circle_pixmap(QColor("red"), 12)))

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
        if not self.isMinimized() or not self.anyOffline():
            self.stopBeepLoop()
            return
        if self.beep_phase < self.beepCount:
            self.playSound()
            self.beep_phase += 1
            self.sound_timer.start(self.BEEP_LENGTH)
        else:
            self.beep_phase = 0
            self.sound_timer.start(self.beepWait)

    def anyOffline(self) -> bool:
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 2)
            if status_item and status_item.text() == "Offline":
                return True
        return False

    def playSound(self):
        if os.path.exists(OFFLINE_SOUND_PATH):
            QSound.play(OFFLINE_SOUND_PATH)
        else:
            print("Arquivo de som não encontrado:", OFFLINE_SOUND_PATH)

    def refresh_table(self):
        self.table.setRowCount(0)
        self.populate_table()

    def showHomePage(self):
        current_hash = self.get_servers_json_hash()
        if current_hash != self.last_servers_json_hash:
            self.reload_servers_data()
            self.last_servers_json_hash = current_hash
        self.stack.setCurrentWidget(self.main_content)


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

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
