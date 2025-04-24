from core.database import remove_server_by_name
from PyQt5.QtWidgets import QInputDialog, QMessageBox

def remove_server(main_window):
    server_name, ok = QInputDialog.getText(main_window, "Remover Servidor", "Digite o Nome do servidor a remover:")
    if not ok or not server_name.strip():
        return

    server_name = server_name.strip()

    if len(server_name) > 50:
        QMessageBox.warning(main_window, "Aviso", "O nome do servidor é muito longo (máximo 50 caracteres).")
        return
    if not server_name.isalnum():
        QMessageBox.warning(main_window, "Aviso", "O nome do servidor deve conter apenas caracteres alfanuméricos.")
        return

    try:
        removed = remove_server_by_name(server_name)
        if not removed:
            QMessageBox.critical(main_window, "Erro", f"Servidor '{server_name}' não encontrado no banco de dados.")
            return
    except Exception as e:
        QMessageBox.critical(main_window, "Erro", f"Erro ao remover o servidor: {e}")
        return

    if hasattr(main_window, "refresh_table"):
        main_window.refresh_table()
    if hasattr(main_window, "rebuild_hive_view"):
        main_window.rebuild_hive_view()
