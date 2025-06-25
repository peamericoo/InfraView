from __future__ import annotations

"""Window displaying the complete failure history."""

from PyQt5.QtWidgets import QWidget, QVBoxLayout

from .widgets.failure_panel import FailurePanel


class FailureDashboard(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Falhas Offline")
        layout = QVBoxLayout(self)
        self.panel = FailurePanel(self)
        layout.addWidget(self.panel)