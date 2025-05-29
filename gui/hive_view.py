import math
import json
import os
import logging
from PyQt5.QtCore import QPropertyAnimation, pyqtProperty
from core.status_logic import get_logical_status
from PyQt5.QtWidgets import QWidget, QLayout, QSizePolicy, QLayoutItem, QScrollArea, QFrame
from PyQt5.QtCore import Qt, QRect, QSize, QPointF, QPoint
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPolygonF, QFontDatabase, QCursor, QColor
from core.utils import get_data_path
from core.pause_manager import is_paused

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
    # ---------- HELPERS ----------
    @staticmethod
    def _to_int(val) -> int:
        """
        Converte qualquer entrada (str/float/None/''/'N/A') para int.
        • valores inválidos → -1  ⇒  tratado como OFF-line/desconhecido.
        """
        if val in (None, '', 'N/A'):
            return -1
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return -1
    # --------------------------------

    def __init__(self, server_name, latency_ms=0.0, folder_color="#000000", parent=None):
        super().__init__(parent)
        self.server_name  = server_name
        self.latency_ms   = self._to_int(latency_ms)       # ← usa o helper
        self.folder_color = QColor(folder_color)

        #———— UI / fonte ————
        self.setMinimumSize(QSize(80, 80))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        font_db = QFontDatabase()
        font_ok = "Open Sans" if "Open Sans" in font_db.families() else "Arial"
        self.font_name    = QFont(font_ok, 8,  QFont.Bold)
        self.font_latency = QFont(font_ok, 16, QFont.Bold)

        #———— animação de cor ————
        self.current_color = self.calculate_color(self.latency_ms)
        self.target_color  = self.current_color

        self.color_anim = QPropertyAnimation(self, b"bgColor")
        self.color_anim.setDuration(400)

        
        

    # propriedade animável -------------------------------------------------
    def get_bg_color(self): return self.current_color
    def set_bg_color(self, c): self.current_color = c; self.update()
    bgColor = pyqtProperty(QColor, fget=get_bg_color, fset=set_bg_color)

    # atualização em tempo-real -------------------------------------------
    def set_data(self, server_name, latency_ms, logical_status="online", folder_color=None):
        new_latency = self._to_int(latency_ms)

        # Verifica se houve mudança real
        is_same = (
            server_name == self.server_name and
            new_latency == self.latency_ms and
            logical_status == getattr(self, "logical_status", None) and
            (folder_color is None or QColor(folder_color) == self.folder_color)
        )

        if is_same:
            return  # ← evita redraw desnecessário

        self.server_name = server_name
        self.latency_ms = new_latency
        self.logical_status = logical_status

        if folder_color is not None:
            self.folder_color = QColor(folder_color)

        if self.logical_status != "pausado":
            nova_cor = self.calculate_color(self.latency_ms)
            if nova_cor != self.current_color:
                self.target_color = nova_cor
                self.color_anim.stop()
                self.color_anim.setStartValue(self.current_color)
                self.color_anim.setEndValue(self.target_color)
                self.color_anim.start()
        else:
            if self.current_color != QColor("black"):
                self.current_color = QColor("black")
                self.update()


    # paleta de cores ------------------------------------------------------
    def calculate_color(self, latency):
        if latency < 0:
            return QColor(255, 0, 0)                                   # offline
        elif latency <= 100:
            return lerp_color(latency, 0, 100,
                              QColor(144, 238, 144), QColor(0, 128, 0))
        elif latency <= 300:
            return lerp_color(latency, 100, 300,
                              QColor(0, 128, 0), QColor(255, 255, 0))
        elif latency <= 600:
            return lerp_color(latency, 300, 600,
                              QColor(255, 255, 0), QColor(255, 165, 0))
        elif latency <= 1000:
            return lerp_color(latency, 600, 1000,
                              QColor(255, 165, 0), QColor(255, 0, 0))
        else:
            return QColor(255, 0, 0)

    # desenho --------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        if w <= 2 or h <= 2:
            return

        side = min(w, h) * 0.49
        cx, cy = w / 2, h / 2
        poly = QPolygonF([
            QPointF(cx + side * math.cos(math.radians(60 * i - 30)),
                    cy + side * math.sin(math.radians(60 * i - 30)))
            for i in range(6)
        ])

        from PyQt5.QtGui import QPainterPath, QLinearGradient

        is_paused = getattr(self, "logical_status", "") == "pausado"

        # --- fundo ---
        if is_paused:
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0.0, QColor("#e0e0e0"))  # cinza alumínio
            grad.setColorAt(1.0, QColor("#555555"))  # cinza chumbo
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawPolygon(poly)
        else:
            p.setBrush(QBrush(self.current_color))
            pen_color = QColor("#FFFFFF") if self.folder_color == QColor("#000000") else self.folder_color
            p.setPen(QPen(pen_color, 4))
            p.drawPolygon(poly)

        # --- contorno zebrado somente se pausado ---
        if is_paused:
            border_thickness = 6
            stripe_spacing = 7

            for i in range(6):
                start = poly[i]
                end = poly[(i + 1) % 6]

                # Vetor da aresta
                dx = end.x() - start.x()
                dy = end.y() - start.y()
                length = math.hypot(dx, dy)
                steps = int(length // stripe_spacing)

                for s in range(steps):
                    t1 = s / steps
                    t2 = (s + 0.5) / steps  # metade da faixa

                    # ponto inicial e final da mini-faixa
                    x1 = start.x() + t1 * dx
                    y1 = start.y() + t1 * dy
                    x2 = start.x() + t2 * dx
                    y2 = start.y() + t2 * dy

                    color = QColor("yellow") if s % 2 == 0 else QColor("black")
                    p.setPen(QPen(color, border_thickness))
                    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


        # (Removido deliberadamente para que não sobreponha o zebrado)
        pass


        # --- nome do servidor ---
        p.setFont(self.font_name)
        p.setPen(QColor("black"))
        rect_name = QRect(0, 0, w, int(h * 0.65))
        name_txt = self.server_name if len(self.server_name) <= 13 else self.server_name[:13] + "..."
        p.drawText(rect_name, Qt.AlignCenter | Qt.AlignVCenter, name_txt)

        # --- latência ou status ---
        if is_paused:
            txt = "Pausado"
        elif self.latency_ms < 0:
            txt = "Offline"
        else:
            txt = f"{self.latency_ms} ms"

        ms_color = QColor("white") if (
            self.latency_ms < 120 or self.latency_ms >= 800 or self.latency_ms < 0
        ) else QColor("black")

        p.setFont(self.font_latency)
        p.setPen(ms_color)
        rect_ms = QRect(0, int(h * 0.28), w, int(h * 0.55))
        p.drawText(rect_ms, Qt.AlignCenter | Qt.AlignTop, txt)

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
        self.cells_by_ip = {}
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
            self.cells_by_ip[ip] = cell  # ← adiciona ao dicionário
            self.layout.addWidget(cell)


    def update_latency_by_ip(self, ip, new_ms):
        if hasattr(self, "cells_by_ip") and ip in self.cells_by_ip:
            cell = self.cells_by_ip[ip]
            logical_status = getattr(cell, "logical_status", "online")
            folder_color = getattr(cell, "folder_color", QColor("#000000")).name()
            cell.set_data(cell.server_name, new_ms, logical_status, folder_color)

    def update_latency(self, idx, new_ms):
        if 0 <= idx < len(self.cells):
            cell = self.cells[idx]
            self.update_latency_by_ip(cell.server_name, new_ms)

    def update_all(self, new_servers_info):
        # Separa servidores ativos e pausados
        ativos = []
        pausados = []

        for (server_name, ip, ms, folder, folder_color) in new_servers_info:
            status_dict = {"latency": ms} if ms >= 0 else {}
            logical_status = get_logical_status(ip, status_dict)
            entrada = (server_name, ip, ms, folder, folder_color, logical_status)

            if logical_status == "pausado":
                pausados.append(entrada)
            else:
                ativos.append(entrada)

        ordenado = ativos + pausados

        # Reconstrói toda a grade se a quantidade mudou
        if len(ordenado) != len(self.cells):
            for cell in self.cells:
                cell.setParent(None)
            self.cells = []
            while self.layout.count():
                item = self.layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            for (server_name, ip, ms, folder, folder_color, logical_status) in ordenado:
                cell = HexCellWidget(server_name, ms, folder_color)
                cell.set_data(server_name, ms, logical_status)
                self.cells.append(cell)
                self.layout.addWidget(cell)
        else:
            # Reusa células existentes: atualiza COR DA PASTA antes de set_data
            for i, (server_name, ip, ms, folder, folder_color, logical_status) in enumerate(ordenado):
                self.cells[i].folder_color = QColor(folder_color)
                self.cells[i].set_data(server_name, ms, logical_status)

        # Mantém o estado para referência futura
        self.servers_info = new_servers_info

    def clear_cells(self):
        for cell in self.cells:
            cell.setParent(None)
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

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
        # Separa servidores ativos e pausados
        ativos = []
        pausados = []

        for (server_name, ip, ms, folder, folder_color) in new_servers_info:
            status_dict = {"latency": ms} if ms >= 0 else {}
            logical_status = get_logical_status(ip, status_dict)
            entrada = (server_name, ip, ms, folder, folder_color, logical_status)

            if logical_status == "pausado":
                pausados.append(entrada)
            else:
                ativos.append(entrada)

        ordenado = ativos + pausados

        # Reconstrói toda a grade se a quantidade mudou
        if len(ordenado) != len(self.cells):
            for cell in self.cells:
                cell.setParent(None)
            self.cells = []
            while self.layout.count():
                item = self.layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            for (server_name, ip, ms, folder, folder_color, logical_status) in ordenado:
                cell = HexCellWidget(server_name, ms, folder_color)
                cell.set_data(server_name, ms, logical_status)
                self.cells.append(cell)
                self.layout.addWidget(cell)
        else:
            # Reusa células existentes: atualiza COR DA PASTA antes de set_data
            for i, (server_name, ip, ms, folder, folder_color, logical_status) in enumerate(ordenado):
                self.cells[i].folder_color = QColor(folder_color)
                self.cells[i].set_data(server_name, ms, logical_status)

        # Mantém o estado para referência futura
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
