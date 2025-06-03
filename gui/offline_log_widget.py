# offline_log_panel.py
# ═════════════════════════════════════════════════════════════════════════════
"""
Painel de Falhas Offline:
─────────────────────────
• Lista virtualizada (QListView + QAbstractListModel) ─ aguenta milhares de itens
• Agrupamento visual por servidor (header pintado pelo delegate)
• Busca instantânea (QSortFilterProxyModel) – filtra por servidor e descrição
• Botões: Limpar histórico  |  Exportar CSV
• API pública idêntica à anterior ⇒  set_entries  /  append_entries
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from PyQt5.QtCore import (
    Qt,
    QAbstractListModel,
    QModelIndex,
    QVariant,
    QSortFilterProxyModel,
)
from PyQt5.QtGui import QPainter, QFont, QColor, QPen
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListView,
    QFileDialog,
    QMessageBox,
)

# ═══ Constantes de Estilo ════════════════════════════════════════════════════
BACKGROUND       = "#1E1E1E"
CARD_BG          = "#2D2D30"
CARD_BORDER      = "#3C3C3C"
HEADER_BG        = "#2C3E50"
TEXT_PRIMARY     = "#FFFFFF"
TEXT_ALERT       = "#E74C3C"
FONT_FAMILY      = "Segoe UI"

TS_REGEX = re.compile(r"\[(.*?)\]")

# ═══ Modelo de dados ═════════════════════════════════════════════════════════
@dataclass(slots=True)
class LogEntry:
    server: str
    fail_info: str
    date_str: str
    time_str: str
    raw: str


def _parse_line(line: str) -> LogEntry | None:
    if not line.strip():
        return None
    match = TS_REGEX.search(line)
    raw_ts = match.group(1) if match else ""
    try:
        dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
        date_str = dt.strftime("%d/%m/%Y")
        time_str = dt.strftime("%H:%M:%S")
    except ValueError:
        date_str, time_str = "Data inválida", ""
    body = line.replace(f"[{raw_ts}]", "").strip()
    server, _, fail = body.partition(":")
    server, fail = server.strip(), fail.strip()
    if not server or not fail:
        return None
    return LogEntry(server, fail, date_str, time_str, line)


# ═══ QAbstractListModel ==================================================================
class OfflineLogModel(QAbstractListModel):
    """Modelo enxuto, exportável para CSV."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: List[LogEntry] = []

    # ― API pública ―
    def set_entries(self, raw_lines: Iterable[str]) -> None:
        self.beginResetModel()
        self._entries = [e for line in raw_lines if (e := _parse_line(line))]
        self.endResetModel()

    def append_entries(self, raw_lines: Iterable[str]) -> None:
        new_items = [e for line in raw_lines if (e := _parse_line(line))]
        if not new_items:
            return
        start = len(self._entries)
        self.beginInsertRows(QModelIndex(), start, start + len(new_items) - 1)
        self._entries.extend(new_items)
        self.endInsertRows()

    def export_csv(self, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f, delimiter=";")
            wr.writerow(["Servidor", "Falha", "Data", "Hora"])
            for e in self._entries:
                wr.writerow([e.server, e.fail_info, e.date_str, e.time_str])

    # ― Métodos do modelo ―
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._entries)

    def data(self, idx: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not idx.isValid():
            return QVariant()
        entry = self._entries[idx.row()]
        if role == Qt.DisplayRole:
            return entry  # passamos o objeto inteiro ao delegate
        return QVariant()


# ═══ Delegate personalizado ==================================================================
class OfflineLogDelegate(QListView):
    """Simplifica: herda QListView → paintEvent custom para header/group."""

    CARD_MARGIN_Y = 6
    CARD_HEIGHT   = 64
    HEADER_HEIGHT = 24

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setUniformItemSizes(True)
        self.setSpacing(self.CARD_MARGIN_Y)
        self.setStyleSheet(f"background:{BACKGROUND}; border:none;")
        self.setVerticalScrollMode(self.ScrollPerPixel)

    # ― Renderização ―
    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), QColor(BACKGROUND))
        fm = QFont(FONT_FAMILY, 10)
        painter.setFont(fm)

        # Loop pelos itens visíveis
        option = self.viewOptions()
        y = -self.verticalOffset()
        prev_server = None

        for row in range(self.model().rowCount()):  # type: ignore[attr-defined]
            idx = self.model().index(row, 0)
            entry: LogEntry = idx.data(Qt.DisplayRole)
            if not entry:
                continue

            # Header de grupo?
            if row == 0 or entry.server != prev_server:
                painter.fillRect(
                    0,
                    y,
                    self.viewport().width(),
                    self.HEADER_HEIGHT,
                    QColor(HEADER_BG),
                )
                painter.setPen(QColor(TEXT_PRIMARY))
                painter.drawText(
                    12, y + 16, entry.server
                )  # 16 ≈ baseline font-size 10
                y += self.HEADER_HEIGHT
            prev_server = entry.server

            # Cartão
            rect_y = y
            painter.fillRect(
                12,
                rect_y,
                self.viewport().width() - 24,
                self.CARD_HEIGHT,
                QColor(CARD_BG),
            )
            painter.setPen(QColor(CARD_BORDER))
            painter.drawRect(
                12,
                rect_y,
                self.viewport().width() - 24,
                self.CARD_HEIGHT,
            )

            # Conteúdo
            painter.setPen(QColor(TEXT_ALERT))
            painter.drawText(24, rect_y + 22, f"❗ {entry.fail_info}")

            painter.setPen(QColor(TEXT_PRIMARY))
            painter.drawText(
                24,
                rect_y + 40,
                f"📅 {entry.date_str}   🕒 {entry.time_str}",
            )

            # Próximo
            y += self.CARD_HEIGHT + self.CARD_MARGIN_Y
        painter.end()

    # ― Tamanho do item para o layout ―
    def sizeHintForRow(self, row: int) -> int:  # type: ignore[override]
        return self.CARD_HEIGHT + self.CARD_MARGIN_Y


# ═══ Painel completo (barra de busca + botões) ===============================================
class OfflineLogPanel(QWidget):
    """Widget de alto-nível pronto para integrar na GUI principal."""

    # API pública (retrocompatível)
    def set_entries(self, lines: Iterable[str]) -> None:
        self._model.set_entries(lines)

    def append_entries(self, lines: Iterable[str]) -> None:
        self._model.append_entries(lines)

    # ― Init ―
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = OfflineLogModel(self)

        # Proxy de busca
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # todos: delegate cuida

        # Lista / delegate
        self._list = OfflineLogDelegate()
        self._list.setModel(self._proxy)

        # Barra de controles
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar servidor ou descrição...")
        self._search.textChanged.connect(self._proxy.setFilterFixedString)

        self._btn_clear = QPushButton("Limpar")
        self._btn_clear.clicked.connect(self._clear)

        self._btn_export = QPushButton("Exportar CSV")
        self._btn_export.clicked.connect(self._export)

        bar = QHBoxLayout()
        bar.addWidget(self._search)
        bar.addWidget(self._btn_clear)
        bar.addWidget(self._btn_export)

        # Layout raiz
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addLayout(bar)
        root.addWidget(self._list)

    # ― Slots auxiliares ―
    def _clear(self) -> None:
        if (self._model.rowCount() == 0):
            return
        if (
            QMessageBox.question(
                self,
                "Limpar Log",
                "Deseja realmente apagar todo o histórico?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self._model.set_entries([])

    def _export(self) -> None:
        path, ok = QFileDialog.getSaveFileName(
            self,
            "Exportar como CSV",
            "offline_logs.csv",
            "CSV Files (*.csv)",
        )
        if ok:
            self._model.export_csv(Path(path))
            QMessageBox.information(
                self,
                "Exportação concluída",
                f"Log exportado para:\n{path}",
            )
