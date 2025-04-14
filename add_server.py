# add_server.py
import socket
import json
import os
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QColorDialog
from utils import validate_ip

def add_server_dialog(parent):
    """
    Abre um diálogo para adicionar um servidor.
    Solicita ao usuário:
      - IP ou domínio do servidor (se for domínio, resolve para IP via socket.gethostbyname)
      - Nome do servidor
      - Nome da pasta (grupo) para agrupar o servidor
      - Cor da pasta, que será usada (nota: na nova implementação esse valor não é persistido junto ao servidor,
        mas pode ser utilizado na configuração da pasta em outro gerenciamento)
    Após validação, adiciona o novo servidor ao arquivo "servers.json" utilizando a estrutura:
      {
          "servers": [ { "name": ..., "ip": ..., "folder": ..., "status": "running" }, ... ],
          "folders": [ ... ]
      }
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

    # Solicita a cor da pasta (na nova implementação essa cor não é armazenada junto ao servidor,
    # mas pode ser utilizada no gerenciamento de pastas)
    folder_color = QColorDialog.getColor(parent=parent, title="Selecionar Cor da Pasta")
    if not folder_color.isValid():
        from PyQt5.QtGui import QColor
        folder_color = QColor("black")
    # A cor não é utilizada na estrutura do servidor, apenas pode ser incorporada na lógica de pastas

    # Carrega ou inicializa os dados do arquivo JSON
    data_file = os.path.join(os.path.dirname(__file__), "servers.json")
    if os.path.exists(data_file):
        try:
            with open(data_file, "r") as f:
                data = json.load(f)
        except Exception:
            data = {"servers": [], "folders": []}
    else:
        data = {"servers": [], "folders": []}

    # Cria o novo servidor e o adiciona à lista de servidores
    new_server = {
        "name": name,
        "ip": ip_candidate,
        "folder": folder_name,
        "status": "running"
    }
    data["servers"].append(new_server)

    # Salva os dados atualizados no arquivo JSON
    try:
        with open(data_file, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        QMessageBox.critical(parent, "Erro", f"Não foi possível salvar os dados: {e}")
        return

    # Atualiza a interface do pai, se os métodos refresh_table() e rebuild_hive_view() estiverem disponíveis
    if hasattr(parent, "refresh_table"):
        parent.refresh_table()
    if hasattr(parent, "rebuild_hive_view"):
        parent.rebuild_hive_view()
