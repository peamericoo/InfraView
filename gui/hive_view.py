import math
import json
import os
import logging
from PyQt5.QtWidgets import QWidget, QLayout, QSizePolicy, QLayoutItem, QScrollArea, QFrame
from PyQt5.QtCore import Qt, QRect, QSize, QPointF, QPoint
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPolygonF, QFontDatabase, QCursor
from core.utils import get_data_path

# Definindo nível de log para INFO em produção (pode ser alterado para DEBUG quando necessário)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def lerp_color(value, min_val, max_val, color_min, color_max):
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
    luminance = (0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()) / 255
    return QColor(255, 255, 255) if luminance < 0.5 else QColor(0, 0, 0)

class HexCellWidget(QWidget):
    def __init__(self, server_name, latency_ms=0.0, folder_color="#000000", parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self.latency_ms = latency_ms
        self.folder_color = QColor(folder_color)
        self.setMinimumSize(QSize(80, 80))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.font_db = QFontDatabase()
        self.has_open_sans = "Open Sans" in self.font_db.families()
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

        base_side = max(1.0, min(w, h) * 0.45)
        padding_factor = 1.09  # leve expansão das pontas, ajustável
        side = base_side * padding_factor

        cx = w / 2
        cy = h / 2
        points = []
        for i in range(6):
            angle_deg = 60 * i - 30
            angle_rad = math.radians(angle_deg)
            x = cx + side * math.cos(angle_rad)
            y = cy + side * math.sin(angle_rad)
            points.append((x, y))
        poly = QPolygonF([QPointF(px, py) for (px, py) in points])

        # --- Determina cor interna do hexágono ---
        if self.latency_ms < 0:
            bg_color = QColor(255, 0, 0)
        elif self.latency_ms <= 100:
            bg_color = lerp_color(self.latency_ms, 0, 100, QColor(144, 238, 144), QColor(0, 128, 0))
        elif self.latency_ms <= 300:
            bg_color = lerp_color(self.latency_ms, 100, 300, QColor(0, 128, 0), QColor(255, 255, 0))
        elif self.latency_ms <= 600:
            bg_color = lerp_color(self.latency_ms, 300, 600, QColor(255, 255, 0), QColor(255, 165, 0))
        elif self.latency_ms <= 1000:
            bg_color = lerp_color(self.latency_ms, 600, 1000, QColor(255, 165, 0), QColor(255, 0, 0))
        else:
            bg_color = QColor(255, 0, 0)

        # --- Contorno na cor da pasta ---
        pen_color = QColor("#FFFFFF") if self.folder_color.name() == "#000000" else self.folder_color
        painter.setPen(QPen(pen_color, 4))

        painter.setBrush(QBrush(bg_color))
        painter.drawPolygon(poly)

        # --- Nome do servidor ---
        painter.setFont(self.font_name)
        display_name = self.server_name if len(self.server_name) <= 13 else self.server_name[:13] + "..."
        rect_name = QRect(0, 0, w, int(h * 0.65))
        painter.setPen(QColor("black"))
        painter.drawText(rect_name, Qt.AlignCenter | Qt.AlignVCenter, display_name)

        # --- Latência ---
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
    def __init__(self, parent=None, cell_size=100, spacing=5, columns=None):
        super().__init__(parent)
        self.itemList = []
        self.cell_size = cell_size
        self.spacing = spacing
        self.fixed_columns = columns
        self.offset_x = 0
        self.offset_y = 0

    def setOffset(self, offset_x, offset_y):
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.update()

    def getOffset(self):
        return (self.offset_x, self.offset_y)

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
        if not self.itemList:
            return QSize(600, 400)
        cols = self.fixed_columns if self.fixed_columns else max(1, int(math.sqrt(len(self.itemList)) * 1.5))
        rows_needed = math.ceil(len(self.itemList) / cols)
        width = cols * (self.cell_size + self.spacing) + self.spacing
        height = int(rows_needed * (self.cell_size * 0.75 + self.spacing) + self.cell_size * 0.25 + self.spacing)
        return QSize(width, height)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        if not self.itemList:
            return
        total_width = rect.width()
        cols = self.fixed_columns if self.fixed_columns else max(1, total_width // (self.cell_size + self.spacing))
        x_offset = rect.x() + self.offset_x
        y_offset = rect.y() + self.offset_y
        row = 0
        col = 0
        for item in self.itemList:
            x = x_offset + col * (self.cell_size + self.spacing)
            if row % 2 == 1:
                x += (self.cell_size + self.spacing) // 2

            y = y_offset + row * (int(self.cell_size * 0.75) + self.spacing)
            item.widget().setGeometry(QRect(x, y, self.cell_size, self.cell_size))
            col += 1
            if col >= cols:
                col = 0
                row += 1

class HiveView(QWidget):
    def __init__(self, servers_info, columns=5, parent=None):
        super().__init__(parent)
        self.servers_info = servers_info
        self.columns = columns
        self.cells = []
        self.layout = HoneycombLayout(cell_size=128, spacing=5, columns=columns)
        self.setLayout(self.layout)
        self.panning = False
        self.start_point = QPoint()
        self.current_offset = QPoint(0, 0)
        self.start_offset = QPoint(0, 0)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.buildUI()

    def buildUI(self):
        for (server_name, ip, ms, folder, folder_color) in self.servers_info:
            cell = HexCellWidget(server_name, ms, folder_color)
            self.cells.append(cell)
            self.layout.addWidget(cell)


    def update_latency(self, idx, new_ms):
        if 0 <= idx < len(self.cells):
            self.cells[idx].set_data(self.cells[idx].server_name, new_ms)

    def update_all(self, new_servers_info):
        if len(new_servers_info) != len(self.cells):
            for cell in self.cells:
                cell.setParent(None)
            self.cells = []
            while self.layout.count():
                item = self.layout.takeAt(0)
                if item:
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
            for (server_name, ip, ms, folder, folder_color) in new_servers_info:
                cell = HexCellWidget(server_name, ms, folder_color)
                self.cells.append(cell)
                self.layout.addWidget(cell)
        else:
            for i, (server_name, ip, ms, folder, folder_color) in enumerate(new_servers_info):
                self.cells[i].set_data(server_name, ms)
        self.servers_info = new_servers_info

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.panning = True
            self.start_point = event.pos()
            self.start_offset = QPoint(self.current_offset)
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.panning:
            delta = event.pos() - self.start_point
            new_offset = self.start_offset + delta
            self.current_offset = new_offset
            self.layout.setOffset(self.current_offset.x(), self.current_offset.y())
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.panning:
            self.panning = False
            self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y() // 8
        self.current_offset = QPoint(self.current_offset.x(), self.current_offset.y() + delta)
        self.layout.setOffset(self.current_offset.x(), self.current_offset.y())
        self.update()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.layout.invalidate()

    def sizeHint(self):
        return self.layout.sizeHint()

class ScrollableHiveView(QScrollArea):
    def __init__(self, servers_info, columns=5, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.hive_view = HiveView(servers_info, columns)
        self.setWidget(self.hive_view)

    def update_all(self, new_servers_info):
        if len(new_servers_info) != len(self.cells):
            for cell in self.cells:
                cell.setParent(None)
            self.cells = []
            while self.layout.count():
                item = self.layout.takeAt(0)
                if item:
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
            for (server_name, ip, ms, folder, folder_color) in new_servers_info:
                cell = HexCellWidget(server_name, ms, folder_color)
                self.cells.append(cell)
                self.layout.addWidget(cell)
        else:
            for i, (server_name, ip, ms, folder, folder_color) in enumerate(new_servers_info):
                self.cells[i].set_data(server_name, ms)
        self.servers_info = new_servers_info


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication([])

    sample_data = [
        ("SER-MTZ-VEN19", 20),
        ("S2", 22),
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

    for i in range(12, 50):
        sample_data.append((f"Servidor-{i}", i * 20 % 1000))

    hive_view = HiveView(sample_data, columns=4)
    hive_view.setWindowTitle("Exemplo HiveView - Arrastar visualização")
    hive_view.show()
    app.exec_()
