from __future__ import annotations

"""Small widget representing a single failure entry."""

from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QLabel, QHBoxLayout, QWidget


class FailureEntry(QWidget):
    """Visual representation of an offline failure."""

    def __init__(self, timestamp: str, reason: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._label = QLabel(self)
        dt = QDateTime.fromString(timestamp, Qt.ISODate)
        ts = dt.toString("dd/MM HH:mm:ss") if dt.isValid() else timestamp
        self._label.setText(f"{ts} – {reason}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._label)

        self._phase = False
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(500)
        self._flash_timer.timeout.connect(self._toggle)
        self._flash_timer.start()
        QTimer.singleShot(4000, self._flash_timer.stop)

    def _toggle(self):
        pal = self._label.palette()
        if self._phase:
            pal.setColor(QPalette.WindowText, QColor("#ff5555"))
        else:
            pal.setColor(QPalette.WindowText, QColor("white"))
        self._label.setPalette(pal)
        self._phase = not self._phase