from __future__ import annotations

"""Scrollable panel showing grouped offline failures."""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QLineEdit,
)
from PyQt5.QtCore import Qt

from core.failure_tracker import list_servers_with_failures
from core.database import get_all_servers
from .failure_group import FailureGroup
from .failure_exporter import export_all_history
from core.status_logic import get_logical_status
from ping_engine import interface


class FailurePanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._servers = {ip: name for name, ip, *_ in get_all_servers()}
        self._groups: dict[str, FailureGroup] = {}

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._scroll.setWidget(self._content)
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filtrar servidores...")
        self._filter.textChanged.connect(self._apply_filter)

        self._btn_export_all = QPushButton("Exportar tudo")
        self._btn_export_all.clicked.connect(self._export_all)

        root = QVBoxLayout(self)
        root.addWidget(self._filter)
        root.addWidget(self._scroll)
        root.addWidget(self._btn_export_all, alignment=Qt.AlignRight)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        snapshot = interface.get_full_snapshot()
        servers = list_servers_with_failures()
        for ip in list(self._groups):
            if ip not in servers:
                grp = self._groups.pop(ip)
                grp.setParent(None)
                grp.deleteLater()

        ordered = []
        for ip in servers:
            status = snapshot.get(ip)
            offline_now = get_logical_status(ip, status) == "offline"
            ordered.append((not offline_now, ip, offline_now))
        ordered.sort()

        for index, (_, ip, offline_now) in enumerate(ordered):
            name = self._servers.get(ip, ip)
            grp = self._groups.get(ip)
            if grp is None:
                grp = FailureGroup(name, ip, self._content, offline_now=offline_now)
                self._groups[ip] = grp
                self._layout.insertWidget(index, grp)
            else:
                grp.set_offline_now(offline_now)
                grp.refresh()
                current_index = self._layout.indexOf(grp)
                if current_index != index:
                    self._layout.removeWidget(grp)
                    self._layout.insertWidget(index, grp)
        self._apply_filter()

    # ------------------------------------------------------------------
    def _apply_filter(self) -> None:
        text = self._filter.text().lower().strip()
        for ip, grp in self._groups.items():
            visible = text in ip.lower() or text in grp.server_name.lower()
            grp.setVisible(visible)

    # ------------------------------------------------------------------
    def _export_all(self) -> None:
        path, selected = QFileDialog.getSaveFileName(
            self, "Exportar falhas", "failures.pdf", "PDF (*.pdf);;PNG (*.png)"
        )
        if path:
            fmt = (
                "pdf"
                if selected.startswith("PDF") or path.lower().endswith(".pdf")
                else "png"
            )
            export_all_history(path, fmt)
            QMessageBox.information(
                self, "Exportação", f"Histórico exportado para:\n{path}"
            )