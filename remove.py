import json
import os
from PyQt5.QtWidgets import QInputDialog, QMessageBox

def remove_server(main_window):
    # Solicita o nome do servidor a ser removido
    server_name, ok = QInputDialog.getText(main_window, "Remover Servidor", "Digite o Nome do servidor a remover:")
    if not ok or not server_name.strip():
        return
    server_name = server_name.strip()
    
    # Carrega os dados do arquivo "servers.json"
    data_file = os.path.join(os.path.dirname(__file__), "servers.json")
    if not os.path.exists(data_file):
        QMessageBox.critical(main_window, "Erro", "Arquivo de configuração não encontrado!")
        return
    try:
        with open(data_file, "r") as f:
            data = json.load(f)
    except Exception:
        QMessageBox.critical(main_window, "Erro", "Erro ao ler o arquivo de configuração!")
        return

    servers = data.get("servers", [])
    # Verifica se existe um servidor com o nome informado
    if not any(s.get("name") == server_name for s in servers):
        QMessageBox.critical(main_window, "Erro", "Servidor não encontrado!")
        return

    # Filtra a lista de servidores removendo os com o nome informado
    new_servers = [s for s in servers if s.get("name") != server_name]
    data["servers"] = new_servers

    # Salva os dados atualizados no arquivo JSON
    try:
        with open(data_file, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        QMessageBox.critical(main_window, "Erro", f"Não foi possível salvar os dados: {e}")
        return

    # Atualiza a interface: caso existam os métodos refresh_table() e rebuild_hive_view()
    if hasattr(main_window, "refresh_table"):
        main_window.refresh_table()
    if hasattr(main_window, "rebuild_hive_view"):
        main_window.rebuild_hive_view()
