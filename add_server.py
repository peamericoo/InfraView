# add_server.py
import socket
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QColorDialog
from config import save_servers
from utils import validate_ip

def add_server_dialog(parent):
    """
    Abre um diálogo para adicionar um servidor.
    Solicita ao usuário:
      - IP ou domínio do servidor (se for domínio, resolve para IP via socket.gethostbyname)
      - Nome do servidor
      - Nome da pasta (grupo) para agrupar o servidor
      - Cor da pasta, que será usada como cor da borda do hexágono
    Após validação, atualiza os dados do parent e recria a HiveView.
    """
    # Solicita IP ou domínio
    ip_or_domain, ok = QInputDialog.getText(
        parent, "Adicionar Servidor", "Digite o IP ou domínio do Servidor:"
    )
    if not ok or not ip_or_domain.strip():
        return

    ip_candidate = ip_or_domain.strip()
    # Se não for um IP válido, tenta resolver como domínio
    if not validate_ip(ip_candidate):
        try:
            ip_candidate = socket.gethostbyname(ip_candidate)
        except Exception:
            QMessageBox.critical(parent, "Erro", "Domínio inválido ou não resolvido!")
            return
        if not validate_ip(ip_candidate):
            QMessageBox.critical(parent, "Erro", "Endereço IP resolvido é inválido!")
            return

    # Solicita o nome do servidor
    name, ok = QInputDialog.getText(
        parent, "Adicionar Servidor", "Digite o Nome do Servidor:"
    )
    if not ok or not name.strip():
        return
    name = name.strip()

    # Solicita o nome da pasta para agrupar o servidor
    folder_name, ok = QInputDialog.getText(
        parent, "Adicionar Servidor - Pasta", "Digite o Nome da Pasta para agrupar o servidor:"
    )
    if not ok or not folder_name.strip():
        folder_name = ""
    else:
        folder_name = folder_name.strip()

    # Solicita a cor da pasta
    folder_color = QColorDialog.getColor(parent=parent, title="Selecionar Cor da Pasta")
    if not folder_color.isValid():
        # Define uma cor padrão, se o usuário cancelar
        from PyQt5.QtGui import QColor
        folder_color = QColor("black")

    # Atualiza os dados no parent (sem modificar as funcionalidades existentes)
    parent.servers[ip_candidate] = name
    parent.offline_count[ip_candidate] = 0
    parent.failure_history[ip_candidate] = []
    save_servers(parent.servers)

    # Armazena informações adicionais de agrupamento se ainda não existir esse atributo
    if not hasattr(parent, "server_folder_info"):
        parent.server_folder_info = {}
    parent.server_folder_info[ip_candidate] = (folder_name, folder_color.name())

    parent.refresh_table()
    parent.rebuild_hive_view()
