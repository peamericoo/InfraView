from PyQt5.QtWidgets import QInputDialog, QMessageBox
from config import save_servers

def remove_server(main_window):
    ip, ok = QInputDialog.getText(main_window, "Remover Servidor", "Digite o IP do servidor a remover:")
    if ok and ip in main_window.servers:
        del main_window.servers[ip]
        if ip in main_window.offline_count:
            del main_window.offline_count[ip]
        if ip in main_window.failure_history:
            del main_window.failure_history[ip]
        save_servers(main_window.servers)
        main_window.refresh_table()
        if not main_window.monitor_paused and main_window.monitor_thread is not None:
            main_window.monitor_thread.servers = list(main_window.servers.keys())
        main_window.rebuild_hive_view()
    elif ok:
        QMessageBox.critical(main_window, "Erro", "Servidor não encontrado!")
