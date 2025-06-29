from __future__ import annotations

"""Export utilities for failure history."""

from typing import Sequence

from PyQt5.QtGui import QTextDocument, QImage, QPainter
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtCore import Qt

from core.failure_tracker import list_servers_with_failures, list_failures


def _build_html(server_name: str, rows: Sequence[tuple]) -> str:
    html = [
        f"<h2>{server_name}</h2>",
        "<table border='1' cellspacing='0' cellpadding='4'>",
    ]
    html.append("<tr><th>Data/Hora</th><th>Motivo</th><th>Resolvido</th></tr>")
    for _id, _server, ts, reason, resolved in rows:
        res_str = "Sim" if resolved else "Não"
        html.append(f"<tr><td>{ts}</td><td>{reason}</td><td>{res_str}</td></tr>")
    html.append("</table>")
    return "".join(html)


def _export_doc(doc: QTextDocument, path: str, fmt: str) -> None:
    if fmt.lower() == "pdf":
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        doc.print(printer)
    else:
        size = doc.size().toSize()
        image = QImage(size, QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        doc.drawContents(painter)
        painter.end()
        image.save(path)


def export_server_history(
    server_name: str, rows: Sequence[tuple], path: str, fmt: str
) -> None:
    doc = QTextDocument()
    doc.setHtml(_build_html(server_name, rows))
    _export_doc(doc, path, fmt)


def export_all_history(path: str, fmt: str) -> None:
    doc = QTextDocument()
    parts = []
    for ip in list_servers_with_failures():
        rows = list_failures(ip)
        parts.append(_build_html(ip, rows))
    doc.setHtml("<br/>".join(parts))
    _export_doc(doc, path, fmt)