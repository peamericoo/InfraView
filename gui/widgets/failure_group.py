from __future__ import annotations

"""Collapsible panel grouping failures of a single server."""

from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt

from core.failure_tracker import list_failures
from .failure_entry import FailureEntry
from .failure_exporter import export_server_history


class FailureGroup(QFrame):
    def __init__(self, server_name: str, ip: str, parent=None) -> None:
        super().__init__(parent)
        self.server_name = server_name
        self.ip = ip
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("background-color:#2D2D30; border:1px solid #3C3C3C; border-radius:8px;")

        self._header = QLabel(f"{server_name} ({ip})")
        self._header.setStyleSheet("font-weight:600; padding:4px;")
        self._header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._header.mousePressEvent = lambda e: self.toggle()

        self._btn_export = QPushButton("Exportar histórico")
        self._btn_export.clicked.connect(self._export)

        self._entries_layout = QVBoxLayout()
        self._entries_layout.setContentsMargins(8, 4, 8, 4)
        self._entries_layout.setSpacing(2)

        box = QVBoxLayout(self)
        box.addWidget(self._header)
        box.addLayout(self._entries_layout)
        box.addWidget(self._btn_export, alignment=Qt.AlignmentFlag.AlignRight)

        self._expanded = True
        self.refresh()

    # ------------------------------------------------------------------
    def toggle(self) -> None:
        self._expanded = not self._expanded
        for i in range(self._entries_layout.count()):
            w = self._entries_layout.itemAt(i).widget()
            if w:
                w.setVisible(self._expanded)
        self._btn_export.setVisible(self._expanded)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        for i in reversed(range(self._entries_layout.count())):
            item = self._entries_layout.takeAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        for row in list_failures(self.ip):
            entry = FailureEntry(row[2], row[3], self)
            self._entries_layout.addWidget(entry)

    # ------------------------------------------------------------------
    def _export(self) -> None:
        rows = list_failures(self.ip)
        export_server_history(self.server_name, rows)