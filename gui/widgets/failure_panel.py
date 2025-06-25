from __future__ import annotations

"""Scrollable panel showing grouped offline failures."""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QPushButton
from PyQt5.QtCore import Qt

from core.failure_tracker import list_servers_with_failures
from core.database import get_all_servers
from .failure_group import FailureGroup
from .failure_exporter import export_all_history


class FailurePanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._servers = {ip: name for name, ip, *_ in get_all_servers()}

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._scroll.setWidget(self._content)
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)

        self._btn_export_all = QPushButton("Exportar tudo")
        self._btn_export_all.clicked.connect(self._export_all)

        root = QVBoxLayout(self)
        root.addWidget(self._scroll)
        root.addWidget(self._btn_export_all, alignment=Qt.AlignRight)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        for i in reversed(range(self._layout.count())):
            item = self._layout.takeAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        for ip in list_servers_with_failures():
            name = self._servers.get(ip, ip)
            grp = FailureGroup(name, ip, self._content)
            self._layout.addWidget(grp)
        self._layout.addStretch()

    # ------------------------------------------------------------------
    def _export_all(self) -> None:
        export_all_history()