import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QFontDatabase
from gui import MainWindow

def main():
    try:
        app = QApplication(sys.argv)
        # Define o caminho da fonte
        font_path = r"C:\font\Inter_24pt-Regular.ttf"  # Certifique-se de que a extensão do arquivo de fonte é .ttf
        if not os.path.exists(font_path):
            print(f"Arquivo de fonte não encontrado: {font_path}")
            font_family = "Arial"
        else:
            font_id = QFontDatabase.addApplicationFont(font_path)
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0] if font_id != -1 else "Arial"
        app.setFont(QFont(font_family, 10))
        
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Erro durante a execução: {e}")

if __name__ == "__main__":
    main()