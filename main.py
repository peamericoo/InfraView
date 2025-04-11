import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QFontDatabase
from gui import MainWindow

def main():
    app = QApplication(sys.argv)
    # Define o caminho da fonte
    font_path = r"C:\font\Inter_24pt-Regular.tff"  # Verifique se a extensão está correta; se for .ttf, ajuste para: "Inter_24pt-Regular.ttf"
    font_id = QFontDatabase.addApplicationFont(font_path)
    if font_id != -1:
        font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
    else:
        # Se não conseguir carregar, use um fallback
        font_family = "Arial"
    app.setFont(QFont(font_family, 10))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
