# add_server.py
import socket
import json
import os
import ipaddress
from PyQt5.QtCore import pyqtSignal
import logging
from core.utils import validate_ip, resolve_and_ping
from core.database import insert_server, insert_folder
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QColorDialog


def is_valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

from core.database import insert_server, insert_folder

def refresh_from_external_change(self):
    print("[MainWindow] Detecção de nova entrada via add_server_dialog.")
    self.reload_servers_data()
    if not self.monitor_paused:
        from ping_engine.interface import get_orchestrator
        get_orchestrator().reload_servers([{"ip": ip} for ip in self.servers])

def add_server_dialog(parent):
    ip_or_domain, ok = QInputDialog.getText(
        parent, "Adicionar Servidor", "Digite o IP ou domínio do Servidor:"
    )
    if not ok or not ip_or_domain.strip():
        return

    ip_candidate = ip_or_domain.strip()
    if not validate_ip(ip_candidate):
        ip_candidate = resolve_and_ping(ip_candidate)
        if not ip_candidate:
            QMessageBox.critical(parent, "Erro", f"{ip_or_domain} não respondeu ao ping ou não foi resolvido.")
            return

    name, ok = QInputDialog.getText(
        parent, "Adicionar Servidor", "Digite o Nome do Servidor:"
    )
    if not ok or not name.strip():
        return
    name = name.strip()

    folder_name, ok = QInputDialog.getText(
        parent, "Adicionar Servidor - Pasta", "Digite o Nome da Pasta para agrupar o servidor:"
    )
    folder_name = folder_name.strip() if ok and folder_name.strip() else ""

    folder_color = QColorDialog.getColor(parent=parent, title="Selecionar Cor da Pasta")
    if not folder_color.isValid():
        from PyQt5.QtGui import QColor
        folder_color = QColor("black")

    if folder_name:
        insert_folder(folder_name, folder_color.name())

    insert_server(name, ip_candidate, folder_name)

    from ping_engine import interface
    interface.reload_servers()


    if hasattr(parent, "refresh_from_external_change"):
        parent.refresh_from_external_change()



