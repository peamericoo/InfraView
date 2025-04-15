import os
import json
import socket
import ipaddress
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QLineEdit, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QColorDialog, QCheckBox, QGroupBox, QMessageBox
)
from PyQt5.QtGui import QColor

# Configuração de logging para depuração
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EditServersWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_file = os.path.join(os.path.dirname(__file__), "servers.json")
        self.servers_data = []
        self.folders_data = []
        self.loadData()

        # Cria um QTabWidget com duas abas: Editar Servidores e Editar Pastas
        self.tabs = QTabWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self.servers_page = self.createServersPage()
        self.folders_page = self.createFoldersPage()

        self.tabs.addTab(self.servers_page, "Editar Servidores")
        self.tabs.addTab(self.folders_page, "Editar Pastas")

        # Botão para retornar à página inicial
        back_button = QPushButton("Voltar")
        back_button.clicked.connect(self.goBack)
        layout.addWidget(back_button)

    def goBack(self):
        # Retorna à página inicial
        if self.parent() and hasattr(self.parent(), "stack"):
            self.parent().stack.setCurrentIndex(0)

    def loadData(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                # Valida a estrutura do arquivo JSON
                if not isinstance(data, dict) or "servers" not in data or "folders" not in data:
                    raise ValueError("Estrutura inválida. O JSON deve conter as chaves 'servers' e 'folders'.")
                self.servers_data = data.get("servers", [])
                self.folders_data = data.get("folders", [])
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"O arquivo JSON '{self.data_file}' está corrompido ou possui estrutura inválida: {e}")
                self.servers_data = []
                self.folders_data = []
        else:
            self.servers_data = []
            self.folders_data = []

    def saveData(self):
        data = {
            "servers": self.servers_data,
            "folders": self.folders_data
        }
        try:
            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=4)
            logger.info(f"Dados salvos com sucesso em {self.data_file}")
            
            # Chama refreshAll com try/except para evitar erros com objetos inválidos
            try:
                self.refreshAll()
            except Exception as e:
                logger.error(f"Erro ao atualizar interface: {e}")
                
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar os dados no arquivo '{self.data_file}': {e}")
            logger.error(f"Erro ao salvar dados: {e}")

    def refreshAll(self):
        """
        Atualiza a interface gráfica após alterações nos dados.
        Usa tratamento de exceções para evitar crashes por referências inválidas.
        """
        try:
            # Verifica se o widget pai existe
            parent = self.parent()
            if parent is None:
                logger.info("Widget pai não encontrado, atualizando apenas interface local")
                return
                
            # Verifica com segurança a existência do objeto hive_view
            hive_view = getattr(parent, "hive_view", None)
            if hive_view is None:
                logger.info("Objeto hive_view não encontrado no pai")
                return
                
            # Verifica se o método updateView existe e é chamável
            update_method = getattr(hive_view, "updateView", None)
            if callable(update_method):
                logger.info("Chamando método updateView")
                update_method()
            else:
                logger.info("Método updateView não é chamável ou não existe")
                
        except RuntimeError as e:
            # Captura erros de objetos C++ que foram destruídos
            logger.error(f"Erro de objeto C++ (possivelmente destruído): {e}")
        except Exception as e:
            logger.error(f"Erro ao atualizar interface: {e}")

    # =================== Página Editar Servidores ===================
    def createServersPage(self):
        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setSpacing(15)

        # Bloco Adicionar Servidor
        add_group = QGroupBox("Adicionar Servidor")
        add_layout = QVBoxLayout(add_group)
        self.serverNameInput_add = QLineEdit(self)
        self.serverNameInput_add.setPlaceholderText("Nome do servidor")
        self.serverIPInput_add = QLineEdit(self)
        self.serverIPInput_add.setPlaceholderText("IP ou URL")
        self.folderSelect_add = QComboBox(self)
        self.folderSelect_add.addItem("Sem pasta")
        for folder in self.folders_data:
            self.folderSelect_add.addItem(folder["name"])
        add_btn = QPushButton("Adicionar Servidor", self)
        add_btn.clicked.connect(self.onAddServer)
        add_layout.addWidget(self.serverNameInput_add)
        add_layout.addWidget(self.serverIPInput_add)
        add_layout.addWidget(QLabel("Pasta:", self))
        add_layout.addWidget(self.folderSelect_add)
        add_layout.addWidget(add_btn)

        # Bloco Remover Servidor
        remove_group = QGroupBox("Remover Servidor")
        remove_layout = QVBoxLayout(remove_group)
        self.serverList_remove = QListWidget(self)
        self.refreshRemoveList()
        rem_btn = QPushButton("Remover Servidor Selecionado", self)
        rem_btn.clicked.connect(self.onRemoveServer)
        remove_layout.addWidget(self.serverList_remove)
        remove_layout.addWidget(rem_btn)

        # Bloco Editar Servidor
        edit_group = QGroupBox("Editar Servidor")
        edit_layout = QVBoxLayout(edit_group)
        self.serverSelect_edit = QComboBox(self)
        self.refreshEditCombo()
        self.serverNameInput_edit = QLineEdit(self)
        self.serverNameInput_edit.setPlaceholderText("Novo nome do servidor")
        self.serverIPInput_edit = QLineEdit(self)
        self.serverIPInput_edit.setPlaceholderText("Novo IP ou URL")
        self.pauseCheck_edit = QCheckBox("Pausar servidor (Pausado pelo usuário)", self)
        edit_btn = QPushButton("Editar Servidor", self)
        edit_btn.clicked.connect(self.onEditServer)
        edit_layout.addWidget(self.serverSelect_edit)
        edit_layout.addWidget(self.serverNameInput_edit)
        edit_layout.addWidget(self.serverIPInput_edit)
        edit_layout.addWidget(self.pauseCheck_edit)
        edit_layout.addWidget(edit_btn)

        # Organiza os três blocos
        main_layout.addWidget(add_group)
        main_layout.addWidget(remove_group)
        main_layout.addWidget(edit_group)
        return page

    def onAddServer(self):
        name = self.serverNameInput_add.text().strip()
        ip_or_url = self.serverIPInput_add.text().strip()
        selected_folder = self.folderSelect_add.currentText()
        if selected_folder == "Sem pasta":
            selected_folder = ""
        if not name or not ip_or_url:
            QMessageBox.warning(self, "Atenção", "Os campos 'Nome do servidor' e 'IP ou URL' são obrigatórios!")
            return
        try:
            resolved_ip = socket.gethostbyname(ip_or_url)
            # Valida se o IP resolvido é válido
            ipaddress.ip_address(resolved_ip)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"O IP ou domínio '{ip_or_url}' não é válido: {e}")
            return
        new_server = {
            "name": name,
            "ip": resolved_ip,
            "folder": selected_folder,
            "status": "running"
        }
        self.servers_data.append(new_server)
        self.saveData()
        self.serverNameInput_add.clear()
        self.serverIPInput_add.clear()
        self.folderSelect_add.setCurrentIndex(0)
        self.refreshEditCombo()
        self.refreshRemoveList()

    def refreshEditCombo(self):
        self.serverSelect_edit.clear()
        for s in self.servers_data:
            self.serverSelect_edit.addItem(s["name"])

    def refreshRemoveList(self):
        self.serverList_remove.clear()
        for s in self.servers_data:
            item = QListWidgetItem(s["name"])
            self.serverList_remove.addItem(item)

    def onEditServer(self):
        current_name = self.serverSelect_edit.currentText()
        if not current_name:
            QMessageBox.warning(self, "Atenção", "Selecione um servidor para editar!")
            return
        for server in self.servers_data:
            if server["name"] == current_name:
                new_name = self.serverNameInput_edit.text().strip()
                new_ip_or_url = self.serverIPInput_edit.text().strip()
                if new_name:
                    server["name"] = new_name
                if new_ip_or_url:
                    try:
                        resolved_ip = socket.gethostbyname(new_ip_or_url)
                        ipaddress.ip_address(resolved_ip)
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", f"O IP ou domínio '{new_ip_or_url}' fornecido é inválido: {e}")
                        return
                    server["ip"] = resolved_ip
                if self.pauseCheck_edit.isChecked():
                    server["status"] = "Pausado pelo usuário"
                else:
                    if server["status"] == "Pausado pelo usuário":
                        server["status"] = "running"
                break
        self.saveData()
        self.refreshEditCombo()
        self.refreshRemoveList()
        self.serverNameInput_edit.clear()
        self.serverIPInput_edit.clear()
        self.pauseCheck_edit.setChecked(False)

    def onRemoveServer(self):
        selected_items = self.serverList_remove.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Atenção", "Selecione ao menos um servidor para remover.")
            return
        names_to_remove = [item.text() for item in selected_items]
        self.servers_data = [s for s in self.servers_data if s["name"] not in names_to_remove]
        self.saveData()
        self.refreshEditCombo()
        self.refreshRemoveList()

    # =================== Página Editar Pastas ===================
    def createFoldersPage(self):
        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setSpacing(15)

        # Bloco Adicionar Pasta
        add_folder_group = QGroupBox("Adicionar Pasta")
        add_folder_layout = QVBoxLayout(add_folder_group)
        self.folderNameInput_add = QLineEdit(self)
        self.folderNameInput_add.setPlaceholderText("Nome da Pasta")
        self.folderColorLabel_add = QLabel("Cor: #000000", self)
        self.folderColor_add = "#000000"
        color_btn = QPushButton("Escolher Cor", self)
        color_btn.clicked.connect(self.onPickColorAdd)
        # Organiza nome e cor horizontalmente
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.folderNameInput_add)
        top_layout.addWidget(self.folderColorLabel_add)
        top_layout.addWidget(color_btn)
        add_folder_layout.addLayout(top_layout)
        # Lista de servidores para associar à pasta
        self.serverList_addFolder = QListWidget(self)
        self.serverList_addFolder.setSelectionMode(self.serverList_addFolder.MultiSelection)
        self.refreshServerListForFolder()
        add_folder_layout.addWidget(QLabel("Selecione os servidores para esta pasta:", self))
        add_folder_layout.addWidget(self.serverList_addFolder)
        add_folder_btn = QPushButton("Criar Pasta", self)
        add_folder_btn.clicked.connect(self.onAddFolder)
        add_folder_layout.addWidget(add_folder_btn)

        # Bloco Editar/Remover Pasta
        edit_folder_group = QGroupBox("Editar / Remover Pasta")
        edit_folder_layout = QVBoxLayout(edit_folder_group)
        self.folderList_edit = QListWidget(self)
        self.folderList_edit.setSelectionMode(self.folderList_edit.SingleSelection)
        self.refreshFolderList()
        edit_folder_layout.addWidget(QLabel("Selecione a Pasta:", self))
        edit_folder_layout.addWidget(self.folderList_edit)
        # Campos para edição
        self.folderNameInput_edit = QLineEdit(self)
        self.folderNameInput_edit.setPlaceholderText("Novo nome da Pasta")
        self.folderColorLabel_edit = QLabel("Nova cor: ", self)
        self.folderColor_edit = ""
        color_btn_edit = QPushButton("Escolher Cor", self)
        color_btn_edit.clicked.connect(self.onPickColorEdit)
        edit_fields_layout = QHBoxLayout()
        edit_fields_layout.addWidget(self.folderNameInput_edit)
        edit_fields_layout.addWidget(self.folderColorLabel_edit)
        edit_fields_layout.addWidget(color_btn_edit)
        edit_folder_layout.addLayout(edit_fields_layout)
        # Botões de ação
        btns_layout = QHBoxLayout()
        edit_folder_btn = QPushButton("Editar Pasta", self)
        edit_folder_btn.clicked.connect(self.onEditFolder)
        remove_folder_btn = QPushButton("Remover Pasta", self)
        remove_folder_btn.clicked.connect(self.onRemoveFolder)
        btns_layout.addWidget(edit_folder_btn)
        btns_layout.addWidget(remove_folder_btn)
        edit_folder_layout.addLayout(btns_layout)

        main_layout.addWidget(add_folder_group)
        main_layout.addWidget(edit_folder_group)
        return page

    def refreshServerListForFolder(self):
        self.serverList_addFolder.clear()
        for s in self.servers_data:
            item = QListWidgetItem(s["name"])
            self.serverList_addFolder.addItem(item)

    def refreshFolderList(self):
        self.folderList_edit.clear()
        for f in self.folders_data:
            item = QListWidgetItem(f["name"])
            self.folderList_edit.addItem(item)

    def onPickColorAdd(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.folderColor_add = color.name()
            self.folderColorLabel_add.setText(f"Cor: {self.folderColor_add}")

    def onAddFolder(self):
        folder_name = self.folderNameInput_add.text().strip()
        if not folder_name:
            QMessageBox.warning(self, "Atenção", "O nome da pasta é obrigatório!")
            return
        new_folder = {
            "name": folder_name,
            "color": self.folderColor_add
        }
        self.folders_data.append(new_folder)
        # Atualiza os servidores selecionados para associar à pasta
        selected_items = self.serverList_addFolder.selectedItems()
        selected_names = [item.text() for item in selected_items]
        for s in self.servers_data:
            if s["name"] in selected_names:
                s["folder"] = folder_name
        self.saveData()
        self.folderNameInput_add.clear()
        self.folderColorLabel_add.setText("Cor: #000000")
        self.folderColor_add = "#000000"
        self.refreshServerListForFolder()
        self.refreshFolderList()

    def onPickColorEdit(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.folderColor_edit = color.name()
            self.folderColorLabel_edit.setText(f"Nova cor: {self.folderColor_edit}")

    def onEditFolder(self):
        selected_item = self.folderList_edit.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Atenção", "Selecione uma pasta para editar!")
            return
        current_folder = selected_item.text()
        for f in self.folders_data:
            if f["name"] == current_folder:
                new_name = self.folderNameInput_edit.text().strip()
                if new_name:
                    f["name"] = new_name
                if self.folderColor_edit:
                    f["color"] = self.folderColor_edit
                # Atualiza os servidores que possuem essa pasta
                for s in self.servers_data:
                    if s.get("folder") == current_folder:
                        s["folder"] = f["name"]
                break
        self.saveData()
        self.folderNameInput_edit.clear()
        self.folderColorLabel_edit.setText("Nova cor: ")
        self.folderColor_edit = ""
        self.refreshFolderList()

    def onRemoveFolder(self):
        selected_item = self.folderList_edit.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Atenção", "Selecione uma pasta para remover!")
            return
        folder_to_remove = selected_item.text()
        self.folders_data = [f for f in self.folders_data if f["name"] != folder_to_remove]
        # Remove a referência da pasta dos servidores que a usam
        for s in self.servers_data:
            if s.get("folder") == folder_to_remove:
                s["folder"] = ""
        self.saveData()
        self.refreshFolderList()

# Exemplo de teste (opcional):
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    widget = EditServersWidget()
    widget.setWindowTitle("Editor de Servidores e Pastas")
    widget.show()
    sys.exit(app.exec_())