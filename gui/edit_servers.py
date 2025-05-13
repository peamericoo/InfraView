import os
import json
import socket
import ipaddress
import logging
from ping_engine.controller import add_server_live, remove_server_live, edit_server_live 
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
    QComboBox, QListWidget, QListWidgetItem, QColorDialog, QCheckBox, QGroupBox, QMessageBox, QSizePolicy, QGridLayout
)
from PyQt5.QtCore import Qt
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
        tabbar = self.tabs.tabBar()
        tabbar.setDrawBase(False)
        tabbar.setAutoFillBackground(False)
        tabbar.setAttribute(Qt.WA_TranslucentBackground)

        logger.info("Checkpoint 2: TabWidget criado")

        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs)
        self.setLayout(layout)

        try:
            self.servers_page = self.createServersPage()
            logger.info("Checkpoint 3: Página de servidores criada")
        except Exception as e:
            logger.exception("Erro ao criar a página de servidores")
            raise

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
            background-color: #3A3A3A;
            color: white;
        }
        QPushButton:hover {
            background-color: #505050;
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
        QTabWidget {
            background-color: #1E1E1E;
        }
        QTabWidget::pane {
            border: none;
            background-color: #1E1E1E;
            padding-top: 0px;
        }
        QTabWidget::tab-bar {
            background: transparent;
        }
        QTabBar {
            qproperty-drawBase: false;
        }
        QTabBar::tab {
            background: transparent;
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
            self.refreshServerListForFolder() #Atualiza a lista de servidores na aba de pastas
            self.refreshMoveServerWidgets() 
            self.notificar_gui_principal()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao atualizar a interface: {e}")

    def updateMoveServerList(self):
        if not hasattr(self, "serverList_move"):
            return

        selected_folder = self.folderSelect_origin.currentText()
        self.serverList_move.clear()

        if selected_folder == "Selecione uma pasta":
            return

        for s in self.servers_data:
            name = s[0] if isinstance(s, (tuple, list)) else s.get("name", "??")
            folder = s[3] if isinstance(s, (tuple, list)) else s.get("folder", "")
            if folder == selected_folder:
                item = QListWidgetItem(name)
                self.serverList_move.addItem(item)


    def refreshAll(self):
        parent = self.parent()
        if parent is None:
            logger.info("Widget pai não encontrado")
            return
        hive_view = getattr(parent, "hive_view", None)
        if hive_view and hasattr(hive_view, "updateView"):
            hive_view.updateView()

    def refreshAll(self):
        parent = self.parent()
        if parent is None:
            logger.info("Widget pai não encontrado")
            return
        hive_view = getattr(parent, "hive_view", None)
        if hive_view and hasattr(hive_view, "updateView"):
            hive_view.updateView()

    def createFoldersPage(self):
        try:
            page = QWidget()
            main_layout = QVBoxLayout(page)  # Corrigido para VBoxLayout
            main_layout.setSpacing(20)
            main_layout.setContentsMargins(15, 15, 15, 15)

            # Layout horizontal para dividir adicionar e editar
            content_layout = QHBoxLayout()
            content_layout.setSpacing(20)

            # ========== Grupo Adicionar Pasta ==========
            group_add = QGroupBox("Adicionar Pasta")
            layout_add = QVBoxLayout(group_add)
            layout_add.setSpacing(10)

            self.folderNameInput_add = QLineEdit(self)
            self.folderNameInput_add.setPlaceholderText("Nome da pasta")

            self.folderColor_add = "#000000"
            self.folderColorButton_add = QPushButton("Escolher Cor", self)
            self.folderColorButton_add.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #5A5A5A, stop:1 #2E3B40);
                    color: white;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #707070, stop:1 #47555A);
                }
            """)
            self.folderColorButton_add.clicked.connect(self.onPickColorAdd)

            btn_add_folder = QPushButton("Criar Pasta", self)
            btn_add_folder.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #27AE60, stop:1 #219150);
                    color: white;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #1E8449, stop:1 #1A6D3B);
                }
            """)

            btn_add_folder.clicked.connect(self.onAddFolder)

            # Listas dentro de GroupBoxes
            group_unassigned = QGroupBox("Servidores Disponíveis")
            layout_unassigned = QVBoxLayout(group_unassigned)
            self.serverList_unassigned = QListWidget(self)
            self.serverList_unassigned.setSelectionMode(QListWidget.MultiSelection)
            layout_unassigned.addWidget(self.serverList_unassigned)

            group_all = QGroupBox("Todos os Servidores")
            layout_all = QVBoxLayout(group_all)
            self.serverList_all = QListWidget(self)
            self.serverList_all.setSelectionMode(QListWidget.MultiSelection)
            layout_all.addWidget(self.serverList_all)

            self.refreshServerListForFolder()
            self.notificar_gui_principal()


            # Layout das duas listas lado a lado
            lists_layout_add = QHBoxLayout()
            lists_layout_add.addWidget(group_unassigned)
            lists_layout_add.addWidget(group_all)

            layout_add.addWidget(self.folderNameInput_add)
            layout_add.addWidget(self.folderColorButton_add)
            layout_add.addWidget(btn_add_folder)
            layout_add.addLayout(lists_layout_add)

            # ========== Grupo Editar/Remover Pasta ==========
            group_edit = QGroupBox("Editar/Remover Pasta")
            layout_edit = QVBoxLayout(group_edit)
            layout_edit.setSpacing(10)

            self.folderNameInput_edit = QLineEdit(self)
            self.folderNameInput_edit.setPlaceholderText("Novo nome da pasta")

            self.folderColor_edit = ""
            self.folderColorButton_edit = QPushButton("Escolher Nova Cor", self)
            self.folderColorButton_edit.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #5A5A5A, stop:1 #2E3B40);
                    color: white;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #707070, stop:1 #47555A);
                }
            """)
            self.folderColorButton_edit.clicked.connect(self.onPickColorEdit)

            btn_edit_folder = QPushButton("Editar Pasta", self)
            btn_edit_folder.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #F39C12, stop:1 #D68910);
                    color: white;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #D68910, stop:1 #B9770E);
                }
            """)

            btn_edit_folder.clicked.connect(self.onEditFolder)

            btn_remove_folder = QPushButton("Remover Pasta", self)
            btn_remove_folder.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #C0392B, stop:1 #A93226);
                    color: white;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #922B21, stop:1 #78281F);
                }
            """)

            btn_remove_folder.clicked.connect(self.onRemoveFolder)

            # Lista de pastas dentro de GroupBox
            group_pastas = QGroupBox("Pastas Existentes")
            layout_pastas = QVBoxLayout(group_pastas)
            self.folderList_edit = QListWidget(self)
            self.folderList_edit.setSelectionMode(QListWidget.MultiSelection)
            layout_pastas.addWidget(self.folderList_edit)

            self.refreshFolderList()

            # Botões de ação lado a lado
            buttons_edit_layout = QHBoxLayout()
            buttons_edit_layout.addWidget(btn_edit_folder)
            buttons_edit_layout.addWidget(btn_remove_folder)

            layout_edit.addWidget(self.folderNameInput_edit)
            layout_edit.addWidget(self.folderColorButton_edit)
            layout_edit.addLayout(buttons_edit_layout)
            layout_edit.addWidget(group_pastas)

            # ========== Junta tudo ==========
            content_layout.addWidget(group_add)
            content_layout.addWidget(group_edit)

            main_layout.addLayout(content_layout)

            return page

        except Exception as e:
            logger.exception("Erro dentro de createFoldersPage")
            raise



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
            resolved_ip = ip_or_url.strip()
            if not self.skip_validation_checkbox_add.isChecked():
                validated_ip = resolve_and_ping(ip_or_url)
                if not validated_ip:
                    QMessageBox.critical(self, "Erro", f"{ip_or_url} não respondeu ao ping ou não foi resolvido.")
                    return
                resolved_ip = validated_ip
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"O IP ou domínio '{ip_or_url}' não é válido: {e}")
            return

        insert_server(name, resolved_ip, selected_folder)
        add_server_live(resolved_ip)
        self.saveData()
        self.serverNameInput_add.clear()
        self.serverIPInput_add.clear()
        self.folderSelect_add.setCurrentIndex(0)
        self.skip_validation_checkbox_add.setChecked(False)
        self.refreshEditCombo()
        self.serverList_move = QListWidget(self)
        self.folderSelect_move = QComboBox(self)
        self.refreshRemoveList()
        self.refreshServerListForFolder()

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

        update_server_info(current_name, new_name or None, resolved_ip, None)

        if resolved_ip:
            edit_server_live(current_name, resolved_ip)

        self.saveData()
        self.refreshEditCombo()
        self.refreshRemoveList()
        self.serverNameInput_edit.clear()
        self.serverIPInput_edit.clear()
        self.notificar_gui_principal()


    def onMoveServersToFolder(self):
        selected_items = self.serverList_move.selectedItems()
        selected_folder_dest = self.folderSelect_move.currentText()

        if not selected_items:
            QMessageBox.warning(self, "Atenção", "Selecione pelo menos um servidor para mover!")
            return

        if not selected_folder_dest or selected_folder_dest == "Sem pasta":
            QMessageBox.warning(self, "Atenção", "Selecione uma pasta de destino!")
            return

        selected_names = [item.text() for item in selected_items]

        for name in selected_names:
            update_server_folder(name, selected_folder_dest)

        QMessageBox.information(self, "Sucesso", f"{len(selected_names)} servidor(es) movido(s) para a pasta '{selected_folder_dest}'.")

        self.saveData()
        self.refreshEditCombo()
        self.refreshRemoveList()
        self.notificar_gui_principal()
        self.refreshServerListForFolder()
        self.refreshMoveServerWidgets()


    def onRemoveServer(self):
        selected_items = self.serverList_remove.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Atenção", "Selecione pelo menos um servidor para remover!")
            return

        confirm = QMessageBox.question(
            self,
            "Confirmação",
            f"Tem certeza que deseja remover {len(selected_items)} servidor(es)?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        # Coleta os nomes de todos os selecionados primeiro
        names_to_remove = [item.text() for item in selected_items]

        # Remove todos de uma vez
        for name in names_to_remove:
            remove_server_by_name(name)
            remove_server_live(name)

        self.saveData()
        self.refreshEditCombo()
        self.refreshRemoveList()
        self.notificar_gui_principal()


    # =================== Página Editar Pastas ===================
    def createServersPage(self):
        logger.info("ServersPage: Início")
        page = QWidget()
        logger.info("ServersPage: QWidget criado")

        main_layout = QVBoxLayout(page)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(15, 15, 15, 15)

        main_h_layout = QHBoxLayout()
        main_h_layout.setSpacing(20)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(20)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(20)

        # ========== Widgets Comuns ==========
        self.serverNameInput_add = QLineEdit(self)
        self.serverNameInput_add.setPlaceholderText("Nome do servidor")

        self.serverIPInput_add = QLineEdit(self)
        self.serverIPInput_add.setPlaceholderText("IP ou URL")

        self.folderSelect_add = QComboBox(self)
        self.skip_validation_checkbox_add = QCheckBox("Desativar Verificação", self)

        self.serverList_remove = QListWidget(self)
        self.serverSelect_edit = QComboBox(self)

        self.serverNameInput_edit = QLineEdit(self)
        self.serverNameInput_edit.setPlaceholderText("Novo nome do servidor")

        self.serverIPInput_edit = QLineEdit(self)
        self.serverIPInput_edit.setPlaceholderText("Novo IP ou URL")

        self.serverList_move = QListWidget(self)
        self.folderSelect_move = QComboBox(self)
        self.folderSelect_origin = QComboBox(self)

        # ========== Adicionar Servidor ==========
        add_group = QGroupBox("Adicionar Servidor")
        add_layout = QVBoxLayout(add_group)

        self.folderSelect_add.addItem("Sem pasta")
        for folder in self.folders_data:
            name = folder[0] if isinstance(folder, (tuple, list)) else folder.get("name", "??")
            self.folderSelect_add.addItem(name)

        add_btn = QPushButton("Adicionar Servidor", self)
        add_btn.setObjectName("add")
        add_btn.clicked.connect(self.onAddServer)

        add_layout.addWidget(self.serverNameInput_add)
        add_layout.addWidget(self.serverIPInput_add)
        add_layout.addWidget(QLabel("Pasta:"))
        add_layout.addWidget(self.folderSelect_add)
        add_layout.addWidget(self.skip_validation_checkbox_add)
        add_layout.addStretch()
        add_layout.addWidget(add_btn)

        # ========== Editar Servidor ==========
        edit_group = QGroupBox("Editar Servidor")
        edit_layout = QVBoxLayout(edit_group)

        self.refreshEditCombo()

        edit_btn = QPushButton("Editar Servidor", self)
        edit_btn.setObjectName("edit")
        edit_btn.clicked.connect(self.onEditServer)

        edit_layout.addWidget(self.serverSelect_edit)
        edit_layout.addWidget(self.serverNameInput_edit)
        edit_layout.addWidget(self.serverIPInput_edit)
        edit_layout.addStretch()
        edit_layout.addWidget(edit_btn)

        # ========== Remover Servidor ==========
        remove_group = QGroupBox("Remover Servidor")
        remove_layout = QVBoxLayout(remove_group)

        self.serverList_remove.setSelectionMode(QListWidget.MultiSelection)
        self.refreshRemoveList()

        rem_btn = QPushButton("Remover Servidor Selecionado", self)
        rem_btn.setObjectName("remove")
        rem_btn.clicked.connect(self.onRemoveServer)

        remove_layout.addWidget(self.serverList_remove)
        remove_layout.addStretch()
        remove_layout.addWidget(rem_btn)

        # ========== Mover Servidor para Pasta ==========
        move_group = QGroupBox("Mover Servidor para Pasta")
        move_layout = QVBoxLayout(move_group)

        self.folderSelect_origin.currentIndexChanged.connect(self.updateMoveServerList)
        self.serverList_move.setSelectionMode(QListWidget.MultiSelection)

        move_btn = QPushButton("Mover para Pasta", self)
        move_btn.setObjectName("add")
        move_btn.clicked.connect(self.onMoveServersToFolder)

        move_layout.addWidget(QLabel("Pasta de Origem:"))
        move_layout.addWidget(self.folderSelect_origin)
        move_layout.addWidget(self.serverList_move)
        move_layout.addWidget(QLabel("Mover para Pasta:"))
        move_layout.addWidget(self.folderSelect_move)
        move_layout.addStretch()
        move_layout.addWidget(move_btn)

        # ========== Organização Final ==========
        left_layout.addWidget(add_group)
        left_layout.addWidget(edit_group)

        right_layout.addWidget(remove_group)
        right_layout.addWidget(move_group)

        main_h_layout.addLayout(left_layout)
        main_h_layout.addLayout(right_layout)

        main_layout.addLayout(main_h_layout)

        logger.info("ServersPage: Página de servidores finalizada")
        return page


    def refreshFolderList(self):
        self.folderList_edit.clear()
        for f in self.folders_data:
            try:
                name = f[0] if isinstance(f, (tuple, list)) else f.get("name", "??")
                item = QListWidgetItem(name)
                self.folderList_edit.addItem(item)
            except Exception as e:
                logger.exception(f"Erro ao carregar pasta na lista de edição: {e}")

    def refreshMoveServerWidgets(self):
        if not hasattr(self, "serverList_move"):
            return  # Widget ainda não existe

        self.folderSelect_origin.blockSignals(True)
        self.folderSelect_origin.clear()
        self.folderSelect_origin.addItem("Selecione uma pasta")

        self.folderSelect_move.clear()
        self.folderSelect_move.addItem("Sem pasta")

        for folder in self.folders_data:
            name = folder[0] if isinstance(folder, (tuple, list)) else folder.get("name", "??")
            self.folderSelect_origin.addItem(name)
            self.folderSelect_move.addItem(name)

        self.folderSelect_origin.blockSignals(False)

        self.serverList_move.clear()


    def onPickColorAdd(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.folderColor_add = color.name()


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

        # Novo: Verificar se algum servidor já está vinculado a outra pasta
        servers_in_folders = []
        for server in self.servers_data:
            name = server[0] if isinstance(server, (tuple, list)) else server.get("name", "??")
            folder = server[3] if isinstance(server, (tuple, list)) else server.get("folder", "")
            if name in selected_names and folder:
                servers_in_folders.append(name)

        if servers_in_folders:
            confirm = QMessageBox.question(
                self,
                "Atenção",
                f"Alguns servidores selecionados já pertencem a uma pasta existente.\n"
                f"Servidores: {', '.join(servers_in_folders)}\n\n"
                f"Deseja movê-los para a nova pasta?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return

        insert_folder(folder_name, self.folderColor_add)

        for name in selected_names:
            update_server_folder(name, folder_name)

        self.saveData()
        self.folderNameInput_add.clear()
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
        self.folderColor_edit = ""  # Apenas limpa a variável
        self.refreshFolderList()



    def onRemoveFolder(self):
        selected_items = self.folderList_edit.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Atenção", "Selecione pelo menos uma pasta para remover!")
            return

        confirm = QMessageBox.question(
            self,
            "Confirmação",
            f"Tem certeza que deseja remover {len(selected_items)} pasta(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        for item in selected_items:
            folder_to_remove = item.text()
            remove_folder_by_name(folder_to_remove)

        self.saveData()
        self.refreshFolderList()
        self.refreshServerListForFolder()  # <-- ADICIONADO para atualizar lista de servidores

    def notificar_gui_principal(self):
        parent = self.parent()
        if parent and hasattr(parent, "refresh_from_external_change"):
            parent.refresh_from_external_change()


# Exemplo de teste (opcional):
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    widget = EditServersWidget()
    widget.setWindowTitle("Editor de Servidores e Pastas")
    widget.show()
    sys.exit(app.exec_())