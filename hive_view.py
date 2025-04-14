import math
import json
import os
from PyQt5.QtWidgets import QWidget, QLayout, QSizePolicy, QLayoutItem
from PyQt5.QtCore import Qt, QRect, QSize, QPointF
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPolygonF
from PyQt5.QtCore import QPointF

def lerp_color(value, min_val, max_val, color_min, color_max):
    """
    Interpola linearmente entre duas cores conforme 'value' em [min_val, max_val].
    """
    if value < min_val:
        value = min_val
    if value > max_val:
        value = max_val
    t = (value - min_val) / (max_val - min_val)
    r = int(color_min.red() + t * (color_max.red() - color_min.red()))
    g = int(color_min.green() + t * (color_max.green() - color_min.green()))
    b = int(color_min.blue() + t * (color_max.blue() - color_min.blue()))
    return QColor(r, g, b)

def get_contrasting_text_color(bg_color):
    """
    Retorna branco ou preto, de modo a ter bom contraste com o fundo.
    """
    luminance = (0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()) / 255
    return QColor(255, 255, 255) if luminance < 0.5 else QColor(0, 0, 0)

class HexCellWidget(QWidget):
    """
    Widget que desenha um hexágono com:
      - Nome do servidor (truncado se longo) sempre em preto e em negrito.
      - Latência (ms) em destaque, cujo texto segue:
          * De 0 a 120 ms: texto em branco.
          * De 120 a 800 ms: texto em preto.
          * Acima de 800 ms: texto em branco.
        Se o servidor estiver offline (latency_ms negativa), a latência exibida será 0 ms.
    A cor do hex é interpolada de verde (latência baixa) a vermelho (latência alta).
    """
    def __init__(self, server_name, latency_ms=0.0, parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self.latency_ms = latency_ms
        self.min_ms = 0
        self.max_ms = 1000  # Valor máximo de latência para mapeamento
        self.setMinimumSize(QSize(80, 80))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, server_name, latency_ms):
        self.server_name = server_name
        self.latency_ms = latency_ms
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()
        if w <= 2 or h <= 2:
            return

        # Calcula um "side" mínimo; usamos 0.45 do menor lado, mas garantimos que seja pelo menos 1.
        side = max(1.0, min(w, h) * 0.45)
        cx = w / 2
        cy = h / 2

        # Gere os seis pontos do hexágono (ângulos de -30, 30, 90, 150, 210, 270 graus)
        points = []
        for i in range(6):
            angle_deg = 60 * i - 30
            angle_rad = math.radians(angle_deg)
            x = cx + side * math.cos(angle_rad)
            y = cy + side * math.sin(angle_rad)
            points.append((x, y))
        poly = QPolygonF([QPointF(px, py) for (px, py) in points])

        # Define a cor de fundo do hex.
        color_min = QColor(0, 200, 0)
        color_max = QColor(255, 0, 0)
        # Se latency_ms for negativa, indica que o servidor está offline: forçamos vermelho.
        if self.latency_ms < 0:
            bg_color = QColor(255, 0, 0)
        else:
            if self.latency_ms <= 100:
                color_min_level = QColor(144, 238, 144)  # LightGreen
                color_max_level = QColor(0, 128, 0)       # DarkGreen
                bg_color = lerp_color(self.latency_ms, 0, 100, color_min_level, color_max_level)
            elif self.latency_ms <= 300:
                color_min_level = QColor(0, 128, 0)
                color_max_level = QColor(255, 255, 0)       # Yellow
                bg_color = lerp_color(self.latency_ms, 100, 300, color_min_level, color_max_level)
            elif self.latency_ms <= 600:
                color_min_level = QColor(255, 255, 0)       # Yellow
                color_max_level = QColor(255, 165, 0)         # Orange
                bg_color = lerp_color(self.latency_ms, 300, 600, color_min_level, color_max_level)
            elif self.latency_ms <= 1000:
                color_min_level = QColor(255, 165, 0)         # Orange
                color_max_level = QColor(255, 0, 0)           # Red
                bg_color = lerp_color(self.latency_ms, 600, 1000, color_min_level, color_max_level)
            else:
                bg_color = QColor(255, 0, 0)

        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(QBrush(bg_color))
        painter.drawPolygon(poly)

        # ---------------------------
        # Desenha o nome do servidor
        # ---------------------------
        font_name = QFont("Open Sans", 8, QFont.Bold)
        painter.setFont(font_name)
        fm = QFontMetrics(font_name)
        
        max_server_chars = 13  # Altere este valor para controlar quantos caracteres serão exibidos
        if len(self.server_name) > max_server_chars:
            display_name = self.server_name[:max_server_chars] + "..."
        else:
            display_name = self.server_name
        
        rect_name = QRect(0, 0, w, int(h * 0.65))
        painter.setPen(QColor("black"))
        painter.drawText(rect_name, Qt.AlignCenter | Qt.AlignVCenter, display_name)

        # -------------------------------
        # Desenha a latência em ms
        # -------------------------------
        if self.latency_ms < 0:
            ms_text_color = QColor("white")
        elif self.latency_ms < 120:
            ms_text_color = QColor("white")
        elif self.latency_ms < 800:
            ms_text_color = QColor("black")
        else:
            ms_text_color = QColor("white")

        font_latency = QFont("Open Sans", 16, QFont.Bold)
        painter.setFont(font_latency)
        painter.setPen(ms_text_color)
        ms_text = f"{int(self.latency_ms) if self.latency_ms >= 0 else 0} ms"
        rect_ms = QRect(0, int(h * 0.28), w, int(h * 0.55))
        painter.drawText(rect_ms, Qt.AlignCenter | Qt.AlignTop, ms_text)

class HoneycombLayout(QLayout):
    """
    Layout customizado para dispor os widgets em estilo honeycomb (colmeia).
    Em linhas ímpares, as células são deslocadas horizontalmente.
    """
    def __init__(self, parent=None, cell_size=100, spacing=5):
        super().__init__(parent)
        self.itemList = []
        self.cell_size = cell_size
        self.spacing = spacing

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def sizeHint(self):
        return QSize(600, 400)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        if not self.itemList:
            return
        total_width = rect.width()
        cols = max(1, total_width // (self.cell_size + self.spacing))
        x_offset = rect.x()
        y_offset = rect.y()
        row = 0
        col = 0
        for item in self.itemList:
            x = x_offset + col * (self.cell_size + self.spacing)
            if row % 2 == 1:
                x += self.cell_size // 2
            y = y_offset + row * (int(self.cell_size * 0.75) + self.spacing)
            item.widget().setGeometry(QRect(x, y, self.cell_size, self.cell_size))
            col += 1
            if col >= cols:
                col = 0
                row += 1

class HiveView(QWidget):
    """
    Widget que exibe uma lista de servidores em formato de colmeia,
    usando o HoneycombLayout para dispor cada HexCellWidget.
    Nesta implementação, os dados são carregados de um arquivo JSON "servers.json",
    que contém os servidores e as pastas.
    A cada chamada de updateView(), os dados são recarregados e a interface é reconstruída.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_file = os.path.join(os.path.dirname(__file__), "servers.json")
        self.servers_info = []  # Lista de tuplas (nome do servidor, latência)
        self.folders = []       # Lista de pastas (para futura utilização no desenho, se necessário)
        self.loadData()
        self.cells = []
        self.layout = HoneycombLayout(cell_size=128, spacing=5)
        self.setLayout(self.layout)
        self.buildUI()

    def loadData(self):
        """
        Carrega os dados do arquivo JSON "servers.json". Caso o arquivo exista, lê a lista de servidores
        e pastas. Os servidores são transformados em tuplas (nome, 0) sendo que a latência inicial é 0.
        """
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                servers = data.get("servers", [])
                self.folders = data.get("folders", [])
                self.servers_info = [(server.get("name", "Sem Nome"), 0) for server in servers]
            except Exception:
                self.servers_info = []
                self.folders = []
        else:
            self.servers_info = []
            self.folders = []

    def updateView(self):
        """
        Recarrega os dados do arquivo JSON e reconstrói a interface.
        """
        self.loadData()
        # Remove todos os widgets atuais do layout
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        self.cells = []
        self.buildUI()
        self.update()

    def buildUI(self):
        for (server_name, ms) in self.servers_info:
            cell = HexCellWidget(server_name, ms)
            self.cells.append(cell)
            self.layout.addWidget(cell)

    def update_latency(self, idx, new_ms):
        if 0 <= idx < len(self.cells):
            self.cells[idx].set_data(self.cells[idx].server_name, new_ms)

    def update_all(self, new_servers_info):
        if len(new_servers_info) != len(self.cells):
            return
        for i, (server_name, ms) in enumerate(new_servers_info):
            self.cells[i].set_data(server_name, ms)

    def sizeHint(self):
        return QSize(600, 400)

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Exemplo: Para teste, crie um JSON com alguns servidores ou utilize dados fictícios
    sample_data = [
        ("SER-MTZ-VEN19", 20),
        ("S2", 55),
        ("S3", 120),
        ("ServidorDemorado", 300),
        ("S5", 450),
        ("S6", 70),
        ("S7", 170),
        ("S8", 290),
        ("S9", 500),
        ("S10", 800),
        ("S11", 1000)
    ]
    # Se não houver arquivo JSON, é possível testar injetando temporariamente sample_data na propriedade
    hive_view = HiveView()
    hive_view.servers_info = sample_data  # Apenas para teste
    hive_view.buildUI()
    hive_view.setWindowTitle("Exemplo HiveView - Honeycomb Layout")
    hive_view.show()

    sys.exit(app.exec_())
