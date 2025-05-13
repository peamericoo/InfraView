# core/updater.py
import requests
import os
import sys
import shutil
import subprocess
from PyQt5.QtWidgets import QMessageBox

# ID do arquivo no Google Drive
ID_VERSAO_TXT = "1fqlN833glfl2tD9APxqS60XvZPTpZSx4"
ID_EXE_NOVO = "117zYvKTKK08ol-Agxj93v9BgZrQFgPJB"



# URLs diretas
URL_VERSAO_TXT = f"https://drive.google.com/uc?export=download&id=1fqlN833glfl2tD9APxqS60XvZPTpZSx4"
URL_EXE_NOVO = f"https://drive.google.com/uc?export=download&id=117zYvKTKK08ol-Agxj93v9BgZrQFgPJB"

# Arquivo local que guarda a versão atual
CAMINHO_VERSAO_LOCAL = os.path.join("core", "versao.txt")

def get_local_version():
    try:
        with open(CAMINHO_VERSAO_LOCAL, "r") as f:
            return f.read().strip()
    except:
        return "0.0.0"

def get_remote_version():
    try:
        resposta = requests.get(URL_VERSAO_TXT, timeout=5)
        if resposta.status_code == 200:
            return resposta.text.strip()
    except Exception as e:
        print(f"Erro ao buscar versão remota: {e}")
    return None

def baixar_novo_exe(destino):
    try:
        with requests.get(URL_EXE_NOVO, stream=True) as r:
            with open(destino, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
        return True
    except Exception as e:
        print(f"Erro ao baixar novo exe: {e}")
        return False

def verificar_e_atualizar(parent=None):
    versao_local = get_local_version()
    versao_remota = get_remote_version()

    if not versao_remota:
        return

    if versao_local == versao_remota:
        return

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle("Atualização disponível")
    msg.setText(f"Uma nova versão ({versao_remota}) do InfraView está disponível.\nDeseja atualizar agora?")
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    resposta = msg.exec_()

    if resposta == QMessageBox.Yes:
        temp_path = os.path.join(os.path.dirname(sys.executable), "InfraView_temp.exe")
        if baixar_novo_exe(temp_path):
            QMessageBox.information(parent, "Atualização", "Atualização baixada!\nInfraView será reiniciado.")
            # Executa novo exe e fecha atual
            subprocess.Popen([temp_path])
            sys.exit()
        else:
            QMessageBox.critical(parent, "Erro", "Erro ao baixar a nova versão.")
