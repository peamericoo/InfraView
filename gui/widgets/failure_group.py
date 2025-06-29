from __future__ import annotations

"""Collapsible panel grouping failures of a single server."""

from PyQt5.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QPropertyAnimation
from PyQt5.QtGui import QFont

from core.failure_tracker import list_failures
from .failure_entry import FailureEntry
from .failure_exporter import export_server_history


class FailureGroup(QFrame):
    def __init__(
        self, server_name: str, ip: str, parent=None, *, offline_now: bool = False
    ) -> None:
        super().__init__(parent)
        self.server_name = server_name
        self.ip = ip
        self._offline_now = offline_now
        self.setFrameShape(QFrame.StyledPanel)
        self._apply_style()

        self._header = QLabel(f"{server_name} ({ip})")
        self._header.setStyleSheet("font-weight:600; padding:4px;")
        self._header.setFont(QFont("Segoe UI", 10))
        self._header.setAlignment(Qt.AlignLeft)
        self._header.mousePressEvent = lambda e: self.toggle()

        self._btn_export = QPushButton("Exportar histórico")
        self._btn_export.clicked.connect(self._export)
        self._btn_clear = QPushButton("Limpar lista")
        self._btn_clear.clicked.connect(self.clear_entries)

        self._entries_widget = QFrame()
        self._entries_layout = QVBoxLayout(self._entries_widget)
        self._entries_layout.setContentsMargins(8, 4, 8, 4)
        self._entries_layout.setSpacing(2)
        self._anim = QPropertyAnimation(self._entries_widget, b"maximumHeight")
        self._anim.setDuration(250)

        box = QVBoxLayout(self)
        box.addWidget(self._header)
        box.addWidget(self._entries_widget)
        btns = QVBoxLayout()
        btns.addWidget(self._btn_export)
        btns.addWidget(self._btn_clear)
        box.addLayout(btns, stretch=0)

        self._expanded = True
        self.refresh()

    # ------------------------------------------------------------------
    def _apply_style(self) -> None:
        bg = "#3C1C1C" if self._offline_now else "#1F1F1F"
        self.setStyleSheet(f"background-color:{bg}; border:none; border-radius:8px;")

    # ------------------------------------------------------------------
    def set_offline_now(self, offline: bool) -> None:
        if self._offline_now != offline:
            self._offline_now = offline
            self._apply_style()

    # ------------------------------------------------------------------
    def toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            start, end = 0, self._entries_widget.sizeHint().height()
        else:
            start, end = self._entries_widget.height(), 0
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()
        self._btn_export.setVisible(self._expanded)
        self._btn_clear.setVisible(self._expanded)

    def enterEvent(self, event):
        if not self._expanded:
            self.toggle()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._expanded:
            self.toggle()
        super().leaveEvent(event)

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
    def clear_entries(self) -> None:
        while self._entries_layout.count():
            item = self._entries_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    # ------------------------------------------------------------------
    def _export(self) -> None:
        rows = list_failures(self.ip)
        path, selected = QFileDialog.getSaveFileName(
            self,
            "Exportar histórico",
            f"{self.server_name}.pdf",
            "PDF (*.pdf);;PNG (*.png)",
        )
        if path:
            fmt = (
                "pdf"
                if selected.startswith("PDF") or path.lower().endswith(".pdf")
                else "png"
            )
            export_server_history(self.server_name, rows, path, fmt)
            QMessageBox.information(
                self, "Exportação", f"Histórico exportado para:\n{path}"
            )