from __future__ import annotations

"""PDF export utilities for failure history."""

from typing import Iterable, Sequence

from PyQt5.QtGui import QTextDocument
from PyQt5.QtPrintSupport import QPrinter

from core.failure_tracker import list_servers_with_failures, list_failures


def _build_html(server_name: str, rows: Sequence[tuple]) -> str:
    html = [f"<h2>{server_name}</h2>", "<table border='1' cellspacing='0' cellpadding='4'>"]
    html.append("<tr><th>Data/Hora</th><th>Motivo</th><th>Resolvido</th></tr>")
    for _id, _server, ts, reason, resolved in rows:
        res_str = "Sim" if resolved else "Não"
        html.append(f"<tr><td>{ts}</td><td>{reason}</td><td>{res_str}</td></tr>")
    html.append("</table>")
    return "".join(html)


def export_server_history(server_name: str, rows: Sequence[tuple]) -> None:
    doc = QTextDocument()
    doc.setHtml(_build_html(server_name, rows))
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(f"{server_name}_failures.pdf")
    doc.print(printer)


def export_all_history() -> None:
    doc = QTextDocument()
    parts = []
    for ip in list_servers_with_failures():
        rows = list_failures(ip)
        parts.append(_build_html(ip, rows))
    doc.setHtml("<br/>".join(parts))
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName("all_failures.pdf")
    doc.print(printer)