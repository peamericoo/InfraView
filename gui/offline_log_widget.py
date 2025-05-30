import re
from datetime import datetime

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame


class OfflineLogContainer(QWidget):
    """
    Widget para exibir o registro de falhas offline.
    Encapsula toda a lógica de construção e estilização dos frames de log.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

    def redraw(self, log_lines: list[str]):
        # Limpa todo o container
        for i in reversed(range(self.layout.count())):
            w = self.layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        if log_lines:
            for entry in log_lines:
                # Extração de timestamp
                match = re.search(r"\[(.*?)\]", entry)
                raw_ts = match.group(1) if match else ""
                try:
                    dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
                    date_str = dt.strftime("%d/%m/%Y")
                    time_str = dt.strftime("%H:%M:%S")
                except ValueError:
                    date_str, time_str = "Data inválida", ""

                body = entry.replace(f"[{raw_ts}]", "").strip()
                server_info, _, fail_info = body.partition(":")
                server_info, fail_info = server_info.strip(), fail_info.strip()

                frame = QFrame()
                frame.setStyleSheet("""
                    QFrame {background-color:#2D2D30;border:1px solid #3C3C3C;
                            border-radius:12px;}
                """)
                lay = QVBoxLayout(frame)
                lay.setContentsMargins(14, 12, 14, 12)
                lay.setSpacing(8)

                title = QLabel(server_info)
                title.setStyleSheet("""
                    font-size:17px;font-weight:bold;background-color:#2C3E50;
                    color:white;padding:6px 12px;border-radius:6px;
                """)

                info_c = QWidget()
                info_lay = QHBoxLayout(info_c)
                info_lay.setContentsMargins(0, 0, 0, 0)
                info_lay.setSpacing(10)
                info_c.setStyleSheet("background-color:#2D2D30;")

                def pill(txt, icon, color, bold=False):
                    w = QLabel(f"{icon} {txt}")
                    weight = "bold" if bold else "600"
                    w.setStyleSheet(f"""
                        font-size:12px;font-weight:{weight};color:{color};
                        border:1px solid #3C3C3C;border-radius:6px;
                        padding:3px 8px;background-color:#1E1E1E;
                    """)
                    return w

                info_lay.addWidget(pill(fail_info, "❗", "#E74C3C"))
                info_lay.addWidget(pill(date_str,   "📅", "#FFFFFF", True))
                info_lay.addWidget(pill(time_str,   "🕒", "#FFFFFF", True))
                info_lay.addStretch()

                lay.addWidget(title)
                lay.addWidget(info_c)
                self.layout.addWidget(frame)
        else:
            placeholder = QLabel("Nenhuma falha registrada")
            placeholder.setStyleSheet(
                "color: gray; font-style: italic; padding: 8px;"
            )
            self.layout.addWidget(placeholder)
