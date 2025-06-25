"""Helper utilities for GUI components."""
"""Utility helpers used across GUI modules."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPixmap, QPainter, QBrush, QPen


def normalize_server_row(row):
    """Return a sanitized tuple (name, ip, status, folder, color)."""
    if not row:
        row = ()
    data = list(row)
    while len(data) < 5:
        data.append(None)
    name, ip, status, folder, color = data[:5]
    name = name or "<sem nome>"
    ip = ip or "<sem ip>"
    status = status if isinstance(status, int) else 0
    folder = folder or ""
    color = color or "#000000"
    return name, ip, status, folder, color


def create_circle_pixmap(color: QColor, diameter: int = 12) -> QPixmap:
    """Return a circular pixmap filled with *color*."""
    pixmap = QPixmap(diameter, diameter)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QBrush(color))
    painter.setPen(QPen(Qt.NoPen))
    painter.drawEllipse(0, 0, diameter, diameter)
    painter.end()
    return pixmap