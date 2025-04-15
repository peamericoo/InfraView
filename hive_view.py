import math
import json
import os
import logging
from PyQt5.QtWidgets import QWidget, QLayout, QSizePolicy, QLayoutItem
from PyQt5.QtCore import Qt, QRect, QSize, QPointF
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPolygonF, QFontDatabase

# Definindo nível de log para INFO em produção (pode ser alterado para DEBUG quando necessário)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def lerp_color(value, min_val, max_val, color_min, color_max):
    """
    Interpola linearmente entre duas cores conforme 'value' em [min_val, max_val].
    Evita divisão por zero caso min_val seja igual a max_val.
    """
    if value < min_val:
        value = min_val
    if value > max_val:
        value = max_val
    if max_val - min_val == 0:
        return color_min
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
      - Nome do servidor (truncado se longo) sempre em negrito.
      - Latência (ms) em destaque com cores diferenciadas:
          * 0 a 120 ms: texto em branco.
          * 120 a 800 ms: texto em preto.
          * Acima de 800 ms: texto em branco.
      Se o servidor estiver offline (latency_ms negativa), exibe 0 ms.
      A cor do hexágono é interpolada de verde (latência baixa) a vermelho (latência alta).
    """
    def __init__(self, server_name, latency_ms=0.0, parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self.latency_ms = latency_ms
        self.min_ms = 0
        self.max_ms = 1000  # Valor máximo de latência para mapeamento
        self.setMinimumSize(QSize(80, 80))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Verificação de fonte feita apenas uma vez na inicialização
        self.font_db = QFontDatabase()
        self.has_open_sans = "Open Sans" in self.font_db.families()
        
        # Pré-configuração das fontes
        if self.has_open_sans:
            self.font_name = QFont("Open Sans", 8, QFont.Bold)
            self.font_latency = QFont("Open Sans", 16, QFont.Bold)
        else:
            self.font_name = QFont("Arial", 8, QFont.Bold)
            self.font_latency = QFont("Arial", 16, QFont.Bold)

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

        # Calcula o "side" para o hexágono – 45% do menor lado, com valor mínimo de 1.
        side = max(1.0, min(w, h) * 0.45)
        cx = w / 2
        cy = h / 2

        # Gera os seis pontos do hexágono (ângulos de -30, 30, 90, 150, 210 e 270 graus)
        points = []
        for i in range(6):
            angle_deg = 60 * i - 30
            angle_rad = math.radians(angle_deg)
            x = cx + side * math.cos(angle_rad)
            y = cy + side * math.sin(angle_rad)
            points.append((x, y))
        poly = QPolygonF([QPointF(px, py) for (px, py) in points])

        # Define a cor de fundo do hex
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
        painter.setFont(self.font_name)
        fm = QFontMetrics(self.font_name)
        
        max_server_chars = 13  # Quantidade máxima de caracteres exibidos antes de truncar
        display_name = self.server_name if len(self.server_name) <= max_server_chars else self.server_name[:max_server_chars] + "..."
        rect_name = QRect(0, 0, w, int(h * 0.65))
        painter.setPen(QColor("black"))
        painter.drawText(rect_name, Qt.AlignCenter | Qt.AlignVCenter, display_name)

        # -------------------------------
        # Desenha a latência em ms
        # -------------------------------
        # Definição de cores de texto de latência claramente delimitadas
        if self.latency_ms < 0:
            ms_text_color = QColor("white")
        elif self.latency_ms < 120:
            ms_text_color = QColor("white")
        elif self.latency_ms < 800:
            ms_text_color = QColor("black")
        else:
            ms_text_color = QColor("white")

        painter.setFont(self.font_latency)
        painter.setPen(ms_text_color)
        ms_text = f"{int(self.latency_ms) if self.latency_ms >= 0 else 0} ms"
        rect_ms = QRect(0, int(h * 0.28), w, int(h * 0.55))
        painter.drawText(rect_ms, Qt.AlignCenter | Qt.AlignTop, ms_text)

class HoneycombLayout(QLayout):
    """
    Layout customizado para dispor os widgets em estilo honeycomb (colmeia).
    Em linhas ímpares, as células são deslocadas horizontalmente.
    
    Método setGeometry:
      - Divide a largura total disponível pelo (cell_size + spacing) para calcular o número de colunas.
      - Desloca horizontalmente as linhas ímpares (metade do cell_size) para criar o efeito de colmeia.
      - Gera mensagens (opcionalmente via logging) para depuração do posicionamento dos widgets.
    """
    def __init__(self, parent=None, cell_size=100, spacing=5, columns=None):
        super().__init__(parent)
        self.itemList = []
        self.cell_size = cell_size
        self.spacing = spacing
        self.fixed_columns = columns  # Armazena o número fixo de colunas, se especificado

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
        # Calcula o sizeHint com base no número de itens e tamanho da célula
        if not self.itemList:
            return QSize(600, 400)
            
        # Determina o número de colunas
        cols = self.fixed_columns if self.fixed_columns else max(1, int(math.sqrt(len(self.itemList)) * 1.5))
        rows_needed = math.ceil(len(self.itemList) / cols)
        
        # Calcula a largura considerando o deslocamento das linhas ímpares
        width = cols * (self.cell_size + self.spacing) + self.spacing
        
        # Calcula a altura total
        height = int(rows_needed * (self.cell_size * 0.75 + self.spacing) + self.cell_size * 0.25 + self.spacing)
        
        return QSize(width, height)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        if not self.itemList:
            return
            
        total_width = rect.width()
        
        # Usa o número fixo de colunas se especificado, caso contrário calcula dinamicamente
        if self.fixed_columns:
            cols = self.fixed_columns
        else:
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
    utilizando o HoneycombLayout para dispor cada HexCellWidget.
    """
    def __init__(self, servers_info, columns=5, parent=None):
        super().__init__(parent)
        self.servers_info = servers_info  # Lista de tuplas (server_name, latência_ms)
        self.columns = columns  # Armazenando o número de colunas
        self.cells = []
        self.layout = HoneycombLayout(cell_size=128, spacing=5, columns=columns)
        self.setLayout(self.layout)
        self.buildUI()

    def buildUI(self):
        for (server_name, ms) in self.servers_info:
            cell = HexCellWidget(server_name, ms)
            self.cells.append(cell)
            self.layout.addWidget(cell)

    def update_latency(self, idx, new_ms):
        if 0 <= idx < len(self.cells):
            self.cells[idx].set_data(self.cells[idx].server_name, new_ms)

    def update_all(self, new_servers_info):
        """
        Atualiza os dados dos servidores.
        Se a quantidade de servidores for a mesma, reutiliza os widgets existentes;
        caso contrário, remove todos os widgets e reconstrói a interface.
        """
        if len(new_servers_info) != len(self.cells):
            # Remove os widgets antigos e limpa o layout
            for cell in self.cells:
                cell.setParent(None)
            self.cells = []
            
            # Limpa o layout
            while self.layout.count():
                item = self.layout.takeAt(0)
                if item:
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
                        
            # Adiciona novos widgets
            for (server_name, ms) in new_servers_info:
                cell = HexCellWidget(server_name, ms)
                self.cells.append(cell)
                self.layout.addWidget(cell)
        else:
            # Apenas atualiza os dados sem recriar os widgets
            for i, (server_name, ms) in enumerate(new_servers_info):
                self.cells[i].set_data(server_name, ms)
        
        # Atualiza os servidores armazenados
        self.servers_info = new_servers_info

    def resizeEvent(self, event):
        """
        Trata eventos de redimensionamento garantindo que o layout seja atualizado
        """
        super().resizeEvent(event)
        self.layout.invalidate()  # Força o recálculo do layout

    def sizeHint(self):
        return self.layout.sizeHint()

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication([])
    
    # Tenta carregar dados de um arquivo JSON; se não existir, usa dados de exemplo
    data_file = "servers_data.json"
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            sample_data = json.load(f)
    else:
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
    
    hive_view = HiveView(sample_data, columns=4)
    hive_view.setWindowTitle("Exemplo HiveView - Honeycomb Layout")
    hive_view.show()
    app.exec_()