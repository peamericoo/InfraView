# core/updater.py
import requests
import subprocess
from PyQt5.QtWidgets import QMessageBox

VERSAO_LOCAL = "core/versao.txt"
VERSAO_REMOTA = "https://raw.githubusercontent.com/seu-usuario/infraview/main/versao-remota.txt"

def verificar_atualizacao():
    try:
        with open(VERSAO_LOCAL, "r") as f:
            versao_atual = f.read().strip()

        resposta = requests.get(VERSAO_REMOTA, timeout=5)
        versao_disponivel = resposta.text.strip()

        return versao_atual != versao_disponivel, versao_disponivel

    except Exception as e:
        print(f"Erro ao verificar atualização: {e}")
        return False, None

def aplicar_atualizacao(parent=None):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle("Atualização disponível")
    msg.setText("Uma nova versão do InfraView está disponível.\nDeseja atualizar agora?")
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    resposta = msg.exec_()

    if resposta == QMessageBox.Yes:
        try:
            subprocess.run(["git", "pull"], check=True)
            QMessageBox.information(parent, "Atualizado", "Atualização concluída com sucesso!")
        except Exception as e:
            QMessageBox.critical(parent, "Erro", f"Falha ao atualizar: {e}")
