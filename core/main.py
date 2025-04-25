# main.py
import sys
import os
import platform
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QFontDatabase
from gui.gui import MainWindow  # ✅ Importação absoluta correta
from core.updater import verificar_atualizacao, aplicar_atualizacao

def main():
    try:
        print("Inicializando QApplication...")
        app = QApplication(sys.argv)

        print("Verificando atualizações...")
        atualizar, nova_versao = verificar_atualizacao()
        if atualizar:
            aplicar_atualizacao()

        print("Instanciando MainWindow...")
        window = MainWindow()
        print("MainWindow instanciado.")

        window.show()
        print("Janela exibida. Executando app...")
        app.exec_()

        print("Aplicação encerrada.")
    except Exception as e:
        print(f"Erro durante a execução: {e}")

if __name__ == "__main__":
    main()
