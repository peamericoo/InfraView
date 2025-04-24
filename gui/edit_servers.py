import os
import json
import socket
import ipaddress
import logging
from core.logger import logger
from core.utils import resolve_and_ping
from core.database import (
    get_all_servers,
    get_all_folders,
    insert_server,
    insert_folder,
    update_server_info,
    update_server_folder,
    remove_server_by_name,
    update_folder_name_and_color,
    remove_folder_by_name,
)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QLineEdit, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QColorDialog, QCheckBox, QGroupBox, QMessageBox, QSizePolicy
)
from PyQt5.QtGui import QColor

#logging.basicConfig(level=logging.INFO,
                    #format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#logger = logging.getLogger(__name__)

class EditServersWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("EditServersWidget: início do __init__")
        self.servers_data = []
        self.folders_data = []
        self.loadData()
        logger.info("Checkpoint 1: Dados carregados")

        self.tabs = QTabWidget()
        logger.info("Checkpoint 2: TabWidget criado")

        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self) 
         # Create a layout for the widget
        layout.addWidget(self.tabs)
        self.setLayout(layout)  # Set the layout as the main layout for the widget

        try:
            self.servers_page = self.createServersPage()
            logger.info("Checkpoint 3: Página de servidores criada")
        except Exception as e:
            logger.exception("Erro ao criar a página de servidores")
            raise

        logger.info("Checkpoint 3: Página de servidores criada")

        self.folders_page = self.createFoldersPage()
        logger.info("Checkpoint 4: Página de pastas criada")

        self.tabs.addTab(self.servers_page, "Editar Servidores")
        self.tabs.addTab(self.folders_page, "Editar Pastas")
        logger.info("EditServersWidget: __init__ finalizado")

        self.setStyleSheet("""
        QWidget {
            background-color: #1E1E1E;
            color: #CCCCCC;
            font-family: 'Segoe UI', sans-serif;
            font-size: 9pt;
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
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #3A3A3A, stop:1 #2D2D30);
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
        QTabWidget::pane {
            border: 1px solid #3C3C3C;
            background-color: #1E1E1E;
        }
        QTabBar::tab {
            background: #2D2D30;
            color: #CCCCCC;
            border: 1px solid #3C3C3C;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            padding: 4px 14px;
            margin-right: 2px;
            min-height: 28px;
            min-width: 100px;
        }
        QTabBar::tab:selected {
            background: #3A3A3A;
            color: white;
            font-weight: bold;
        }
        QTabBar::tab:hover {
            background: #444;
        }
                  
    """)


    def loadData(self):
        self.servers_data = get_all_servers()
        self.folders_data = get_all_folders()


    def saveData(self):
        try:
            self.loadData()
            self.refreshAll()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao atualizar a interface: {e}")


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
        logger.info("ServersPage: Início")
        page = QWidget()
        logger.info("ServersPage: QWidget criado")

        main_layout = QVBoxLayout(page)
        main_layout.setSpacing(20)
        logger.info("ServersPage: Layout configurado")

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
            try:
                name = folder[0] if isinstance(folder, (tuple, list)) else folder.get("name", "??")
                self.folderSelect_add.addItem(name)
            except Exception as e:
                logger.exception("Erro ao carregar pasta na combo de pastas")

                # folder[0] = nome
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

        logger.info("ServersPage: Página de servidores finalizada")
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
            resolved_ip = resolve_and_ping(ip_or_url)
            if not resolved_ip:
                QMessageBox.critical(self, "Erro", f"{ip_or_url} não respondeu ao ping ou não foi resolvido.")
                return
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"O IP ou domínio '{ip_or_url}' não é válido: {e}")
            return

        insert_server(name, resolved_ip, selected_folder)
        self.saveData()
        self.serverNameInput_add.clear()
        self.serverIPInput_add.clear()
        self.folderSelect_add.setCurrentIndex(0)
        self.refreshEditCombo()
        self.refreshRemoveList()


    def refreshEditCombo(self):
        self.serverSelect_edit.clear()
        for s in self.servers_data:
            self.serverSelect_edit.addItem(s[0])  # s[0] = name

    def refreshRemoveList(self):
        self.serverList_remove.clear()
        for s in self.servers_data:
            item = QListWidgetItem(s[0])  # s[0] = name
            self.serverList_remove.addItem(item)

    def onEditServer(self):
        current_name = self.serverSelect_edit.currentText()
        if not current_name:
            QMessageBox.warning(self, "Atenção", "Selecione um servidor para editar!")
            return

        new_name = self.serverNameInput_edit.text().strip()
        new_ip_or_url = self.serverIPInput_edit.text().strip()
        resolved_ip = None

        if new_ip_or_url:
            try:
                resolved_ip = resolve_and_ping(new_ip_or_url)
                if not resolved_ip:
                    QMessageBox.critical(self, "Erro", f"{new_ip_or_url} não respondeu ao ping ou não foi resolvido.")
                    return
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao resolver IP: {e}")
                return

        pause = self.pauseCheck_edit.isChecked()
        new_status = "Pausado pelo usuário" if pause else "running"

        update_server_info(current_name, new_name or None, resolved_ip, new_status)

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
        for name in names_to_remove:
            remove_server_by_name(name)

        self.saveData()
        self.refreshEditCombo()
        self.refreshRemoveList()


    # =================== Página Editar Pastas ===================
    def createFoldersPage(self):

        logger.info("FoldersPage: Iniciando criação da página")
        try:
            page = QWidget()
            logger.info("FoldersPage: QWidget criado")

            layout = QVBoxLayout(page)
            logger.info("FoldersPage: Layout configurado")

            # Grupo para adicionar pasta
            logger.info("FoldersPage: Criando grupo de adição")
            group_add = QGroupBox("Adicionar Pasta")
            layout_add = QVBoxLayout(group_add)
            self.folderNameInput_add = QLineEdit(self)
            self.folderColor_add = "#000000"
            self.folderColorLabel_add = QLabel("Cor: #000000", self)
            self.folderColorLabel_add.setStyleSheet("color: #FFFFFF")
            self.folderColorButton_add = QPushButton("Escolher Cor", self)
            self.folderColorButton_add.clicked.connect(lambda: self.chooseFolderColor("add"))
            self.serverList_all = QListWidget(self)
            self.serverList_unassigned = QListWidget(self)
            self.refreshServerListForFolder()
            btn_add_folder = QPushButton("Criar Pasta", self)
            btn_add_folder.clicked.connect(self.onAddFolder)

            layout_add.addWidget(QLabel("Nome da pasta:", self))
            layout_add.addWidget(self.folderNameInput_add)
            layout_add.addWidget(self.folderColorLabel_add)
            layout_add.addWidget(self.folderColorButton_add)
            layout_add.addWidget(QLabel("Servidores disponíveis:", self))
            layout_add.addWidget(self.serverList_unassigned)
            layout_add.addWidget(QLabel("Todos os servidores:", self))
            layout_add.addWidget(self.serverList_all)
            layout_add.addWidget(btn_add_folder)
            layout.addWidget(group_add)
            logger.info("FoldersPage: Grupo de adição criado")

            # Grupo para editar/remover pasta
            logger.info("FoldersPage: Criando grupo de edição")
            group_edit = QGroupBox("Editar/Remover Pasta")
            layout_edit = QVBoxLayout(group_edit)
            self.folderList_edit = QListWidget(self)
            self.refreshFolderList()
            self.folderNameInput_edit = QLineEdit(self)
            self.folderColorLabel_edit = QLabel("Nova cor: ", self)
            self.folderColorButton_edit = QPushButton("Escolher nova cor", self)
            self.folderColorButton_edit.clicked.connect(lambda: self.chooseFolderColor("edit"))
            self.folderColor_edit = ""
            btn_edit_folder = QPushButton("Editar Pasta", self)
            btn_edit_folder.clicked.connect(self.onEditFolder)
            btn_remove_folder = QPushButton("Remover Pasta", self)
            btn_remove_folder.clicked.connect(self.onRemoveFolder)

            layout_edit.addWidget(self.folderList_edit)
            layout_edit.addWidget(QLabel("Novo nome:", self))
            layout_edit.addWidget(self.folderNameInput_edit)
            layout_edit.addWidget(self.folderColorLabel_edit)
            layout_edit.addWidget(self.folderColorButton_edit)
            layout_edit.addWidget(btn_edit_folder)
            layout_edit.addWidget(btn_remove_folder)
            layout.addWidget(group_edit)
            logger.info("FoldersPage: Grupo de edição criado")

            return page
        except Exception as e:
            logger.exception("Erro dentro de createFoldersPage")
            raise

    def refreshFolderList(self):
        self.folderList_edit.clear()
        for f in self.folders_data:
            try:
                name = f[0] if isinstance(f, (tuple, list)) else f.get("name", "??")
                item = QListWidgetItem(name)
                self.folderList_edit.addItem(item)
            except Exception as e:
                logger.exception(f"Erro ao carregar pasta na lista de edição: {e}")

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

        insert_folder(folder_name, self.folderColor_add)

        for name in selected_names:
            update_server_folder(name, folder_name)

        self.saveData()
        self.folderNameInput_add.clear()
        self.folderColorLabel_add.setText("Cor: #000000")
        self.folderColor_add = "#000000"
        self.refreshServerListForFolder()
        self.refreshFolderList()

    def refreshServerListForFolder(self):
        self.serverList_all.clear()
        self.serverList_unassigned.clear()
        for s in self.servers_data:
            try:
                name = s[0] if isinstance(s, (tuple, list)) else s.get("name", "??")
                folder = s[3] if isinstance(s, (tuple, list)) else s.get("folder", "")
                item_all = QListWidgetItem(name)
                self.serverList_all.addItem(item_all)
                if not folder:
                    item_unassigned = QListWidgetItem(name)
                    self.serverList_unassigned.addItem(item_unassigned)
            except Exception as e:
                logger.exception(f"Erro ao atualizar listas de servidores por pasta: {e}")

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
        new_name = self.folderNameInput_edit.text().strip()
        new_color = self.folderColor_edit if self.folderColor_edit else None

        update_folder_name_and_color(current_folder, new_name, new_color)

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
        remove_folder_by_name(folder_to_remove)
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