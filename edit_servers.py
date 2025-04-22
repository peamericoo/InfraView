import os
import json
import socket
import ipaddress
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QLineEdit, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QColorDialog, QCheckBox, QGroupBox, QMessageBox, QSizePolicy
)
from PyQt5.QtGui import QColor

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

        self.tabs = QTabWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self.servers_page = self.createServersPage()
        self.folders_page = self.createFoldersPage()

        self.tabs.addTab(self.servers_page, "Editar Servidores")
        self.tabs.addTab(self.folders_page, "Editar Pastas")

        self.setStyleSheet("""
        QWidget {
            background-color: #1E1E1E;
            color: #CCCCCC;
            font-family: 'Segoe UI', sans-serif;
            font-size: 10pt;
        }
        QGroupBox {
            border: 1px solid #3C3C3C;
            border-radius: 8px;
            margin-top: 10px;
            padding: 10px;
            background-color: #252526;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 4px 12px;
            background-color: #007ACC;
            color: white;
            border-radius: 5px;
        }
        QLineEdit, QComboBox, QListWidget {
            background-color: #2D2D30;
            border: 1px solid #3C3C3C;
            border-radius: 5px;
            padding: 6px;
            color: #FFFFFF;
        }
        QPushButton {
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: bold;
        }
        QPushButton#add {
            background-color: #27AE60;
            color: white;
        }
        QPushButton#add:hover {
            background-color: #1E8449;
        }
        QPushButton#remove {
            background-color: #C0392B;
            color: white;
        }
        QPushButton#remove:hover {
            background-color: #922B21;
        }
        QPushButton#edit {
            background-color: #F39C12;
            color: white;
        }
        QPushButton#edit:hover {
            background-color: #D68910;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 4px;
        }
        QScrollBar::handle:vertical {
            background: #5C5C5C;
            min-height: 20px;
            border-radius: 6px;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            background: #3C3C3C;
            height: 12px;
        }
        QScrollBar::handle:vertical:hover {
            background: #888;
        }
    """)


    def loadData(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
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
            try:
                self.refreshAll()
            except Exception as e:
                logger.error(f"Erro ao atualizar interface: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar os dados no arquivo '{self.data_file}': {e}")
            logger.error(f"Erro ao salvar dados: {e}")

    def refreshAll(self):
        parent = self.parent()
        if parent is None:
            logger.info("Widget pai não encontrado")
            return
        hive_view = getattr(parent, "hive_view", None)
        if hive_view and hasattr(hive_view, "updateView"):
            hive_view.updateView()

    # =================== Página Editar Servidores ===================
    def createServersPage(self):
        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setSpacing(20)

        # Layout horizontal para adicionar e remover
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)

        # --- Adicionar Servidor ---
        add_group = QGroupBox("Adicionar Servidor")
        add_layout = QVBoxLayout(add_group)
        add_layout.setSpacing(10)
        self.serverNameInput_add = QLineEdit(self)
        self.serverNameInput_add.setPlaceholderText("Nome do servidor")
        self.serverIPInput_add = QLineEdit(self)
        self.serverIPInput_add.setPlaceholderText("IP ou URL")
        self.folderSelect_add = QComboBox(self)
        self.folderSelect_add.addItem("Sem pasta")
        for folder in self.folders_data:
            self.folderSelect_add.addItem(folder["name"])
        add_btn = QPushButton("Adicionar Servidor", self)
        add_btn.setObjectName("add")
        add_btn.clicked.connect(self.onAddServer)
        add_layout.addWidget(self.serverNameInput_add)
        add_layout.addWidget(self.serverIPInput_add)
        add_layout.addWidget(QLabel("Pasta:", self))
        add_layout.addWidget(self.folderSelect_add)
        add_layout.addStretch()
        add_layout.addWidget(add_btn)
        top_layout.addWidget(add_group)

        # --- Remover Servidor ---
        remove_group = QGroupBox("Remover Servidor")
        remove_layout = QVBoxLayout(remove_group)
        remove_layout.setSpacing(10)
        self.serverList_remove = QListWidget(self)
        self.refreshRemoveList()
        rem_btn = QPushButton("Remover Servidor Selecionado", self)
        rem_btn.setObjectName("remove")
        rem_btn.clicked.connect(self.onRemoveServer)
        remove_layout.addWidget(self.serverList_remove)
        remove_layout.addStretch()
        remove_layout.addWidget(rem_btn)
        top_layout.addWidget(remove_group)

        # --- Editar Servidor ---
        edit_group = QGroupBox("Editar Servidor")
        edit_layout = QVBoxLayout(edit_group)
        edit_layout.setSpacing(10)
        self.serverSelect_edit = QComboBox(self)
        self.refreshEditCombo()
        self.serverNameInput_edit = QLineEdit(self)
        self.serverNameInput_edit.setPlaceholderText("Novo nome do servidor")
        self.serverIPInput_edit = QLineEdit(self)
        self.serverIPInput_edit.setPlaceholderText("Novo IP ou URL")
        self.pauseCheck_edit = QCheckBox("Pausar servidor (Pausado pelo usuário)", self)
        edit_btn = QPushButton("Editar Servidor", self)
        edit_btn.setObjectName("edit")
        edit_btn.clicked.connect(self.onEditServer)
        edit_layout.addWidget(self.serverSelect_edit)
        edit_layout.addWidget(self.serverNameInput_edit)
        edit_layout.addWidget(self.serverIPInput_edit)
        edit_layout.addWidget(self.pauseCheck_edit)
        edit_layout.addStretch()
        edit_layout.addWidget(edit_btn)

        # Adiciona tudo na página principal
        main_layout.addLayout(top_layout)
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
        main_layout.setSpacing(20)

        # Layout horizontal para Adicionar e Editar/Remover Pasta
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)

        # --- Adicionar Pasta ---
        add_folder_group = QGroupBox("Adicionar Pasta")
        add_folder_layout = QVBoxLayout(add_folder_group)
        add_folder_layout.setSpacing(10)

        self.folderNameInput_add = QLineEdit(self)
        self.folderNameInput_add.setPlaceholderText("Nome da Pasta")
        self.folderColorLabel_add = QLabel("Cor: #000000", self)
        self.folderColor_add = "#000000"
        color_btn = QPushButton("Escolher Cor", self)
        color_btn.clicked.connect(self.onPickColorAdd)

        color_layout = QHBoxLayout()
        color_layout.addWidget(self.folderNameInput_add)
        color_layout.addWidget(self.folderColorLabel_add)
        color_layout.addWidget(color_btn)
        add_folder_layout.addLayout(color_layout)

        self.serverList_all = QListWidget(self)
        self.serverList_all.setSelectionMode(QListWidget.MultiSelection)
        self.serverList_unassigned = QListWidget(self)
        self.serverList_unassigned.setSelectionMode(QListWidget.MultiSelection)
        self.refreshServerListForFolder()

        add_folder_layout.addWidget(QLabel("Todos os servidores:", self))
        add_folder_layout.addWidget(self.serverList_all)
        add_folder_layout.addWidget(QLabel("Servidores não atribuídos:", self))
        add_folder_layout.addWidget(self.serverList_unassigned)

        add_folder_btn = QPushButton("Criar Pasta", self)
        add_folder_btn.setObjectName("add")
        add_folder_btn.clicked.connect(self.onAddFolder)
        add_folder_layout.addStretch()
        add_folder_layout.addWidget(add_folder_btn)

        top_layout.addWidget(add_folder_group)

        # --- Editar / Remover Pasta ---
        edit_folder_group = QGroupBox("Editar / Remover Pasta")
        edit_folder_layout = QVBoxLayout(edit_folder_group)
        edit_folder_layout.setSpacing(10)

        self.folderList_edit = QListWidget(self)
        self.folderList_edit.setSelectionMode(self.folderList_edit.SingleSelection)
        self.refreshFolderList()

        edit_folder_layout.addWidget(QLabel("Selecione a Pasta:", self))
        edit_folder_layout.addWidget(self.folderList_edit)

        self.folderNameInput_edit = QLineEdit(self)
        self.folderNameInput_edit.setPlaceholderText("Novo nome da Pasta")
        self.folderColorLabel_edit = QLabel("Nova cor: ", self)
        self.folderColor_edit = ""
        color_btn_edit = QPushButton("Escolher Cor", self)
        color_btn_edit.clicked.connect(self.onPickColorEdit)

        color_edit_layout = QHBoxLayout()
        color_edit_layout.addWidget(self.folderNameInput_edit)
        color_edit_layout.addWidget(self.folderColorLabel_edit)
        color_edit_layout.addWidget(color_btn_edit)
        edit_folder_layout.addLayout(color_edit_layout)

        btns_layout = QHBoxLayout()
        edit_folder_btn = QPushButton("Editar Pasta", self)
        edit_folder_btn.setObjectName("edit")
        edit_folder_btn.clicked.connect(self.onEditFolder)
        remove_folder_btn = QPushButton("Remover Pasta", self)
        remove_folder_btn.setObjectName("remove")
        remove_folder_btn.clicked.connect(self.onRemoveFolder)
        btns_layout.addWidget(edit_folder_btn)
        btns_layout.addWidget(remove_folder_btn)

        edit_folder_layout.addStretch()
        edit_folder_layout.addLayout(btns_layout)
        top_layout.addWidget(edit_folder_group)

        main_layout.addLayout(top_layout)
        return page

    def refreshServerListForFolder(self):
        self.serverList_all.clear()
        self.serverList_unassigned.clear()
        for s in self.servers_data:
            item_all = QListWidgetItem(s["name"])
            self.serverList_all.addItem(item_all)
            if not s.get("folder"):
                item_unassigned = QListWidgetItem(s["name"])
                self.serverList_unassigned.addItem(item_unassigned)


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
        if not self.folderColor_add or self.folderColor_add == "#000000":
            QMessageBox.warning(self, "Atenção", "Você deve escolher uma cor para a pasta!")
            return

        selected_items = self.serverList_unassigned.selectedItems()
        if not selected_items:
            selected_items = self.serverList_all.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "Atenção", "Você deve selecionar pelo menos um servidor para vincular à pasta.")
                return


        selected_names = [item.text() for item in selected_items]

        new_folder = {
            "name": folder_name,
            "color": self.folderColor_add
        }
        self.folders_data.append(new_folder)

        for s in self.servers_data:
            if s["name"] in selected_names:
                if s.get("folder") and s["folder"] != folder_name:
                    resp = QMessageBox.question(self, "Aviso",
                        f"O servidor '{s['name']}' já pertence à pasta '{s['folder']}'. Deseja movê-lo para '{folder_name}'?",
                        QMessageBox.Yes | QMessageBox.No)
                    if resp != QMessageBox.Yes:
                        continue
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