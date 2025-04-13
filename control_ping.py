from monitor import MonitorThread

def toggle_pause(main_window):
    pause_button = main_window.nav_bar.btn_pause  # Utiliza o botão presente na NavigationBar
    if main_window.monitor_paused:
        main_window.monitor_thread = MonitorThread(list(main_window.servers.keys()))
        main_window.monitor_thread.update_signal.connect(main_window.update_table)
        main_window.monitor_thread.start()
        main_window.monitor_paused = False
        pause_button.setToolTip("Pausar Pings")
        pause_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #444;
                border-radius: 5px;
                padding: 5px;
                background-color: lightgreen;
            }
            QPushButton:hover {
                background-color: #b2fab4;
            }
        """)
    else:
        if main_window.monitor_thread is not None:
            main_window.monitor_thread.stop()
            main_window.monitor_thread.wait()
            main_window.monitor_thread = None
        main_window.monitor_paused = True
        pause_button.setToolTip("Despausar Pings")
        pause_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #444;
                border-radius: 5px;
                padding: 5px;
                background-color: lightcoral;
            }
            QPushButton:hover {
                background-color: #f4a8a8;
            }
        """)
