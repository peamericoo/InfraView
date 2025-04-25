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
from PyQt5.QtCore import Qt


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
        
        # obtém o QTabBar e desliga o “base” que ele desenha por baixo das abas
        tabbar = self.tabs.tabBar()
        tabbar.setDrawBase(False)                          # não desenha o fundo padrão
        tabbar.setAutoFillBackground(False)                # não preenche o fundo
        tabbar.setAttribute(Qt.WA_TranslucentBackground)   # torna a área realmente transparente

        # ✅ Layout direto aplicado ao self
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # Opcional: garante bordas zeradas
        layout.setSpacing(0)
        layout.addWidget(self.tabs)
        self.setLayout(layout)
        self.tabs.setDocumentMode(True)


        # ✅ Preenche corretamente o fundo
        self.setAutoFillBackground(True)

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

                /* garante que todo o QTabWidget pinte seu fundo */
                QTabWidget {
                    background-color: #1E1E1E;
                }
                /* configura o painel de páginas */
                QTabWidget::pane {
                    border: 1px solid #3C3C3C;
                    background-color: #1E1E1E;
                }

                /* faz a área antes da primeira aba casar com as abas não-selecionadas */
                QTabWidget::tab-bar {
                    background-color: #2D2D30;
                }
                /* desliga qualquer base padrão do próprio QTabBar */
                QTabBar {
                    qproperty-drawBase: false;
                }

                /* estilo dos próprios botões de aba */
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
            self.refreshEditCombo()
            self.refreshRemoveList()
            self.refreshFolderList()
            self.refreshServerListUnified()
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
        main_layout.setContentsMargins(15, 15, 15, 15)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)


        logger.info("ServersPage: Layout configurado")

        # Layout horizontal para adicionar e remover


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
        self.serverList_remove.setSelectionMode(QListWidget.MultiSelection)
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
        try:
            page = QWidget()
            main_layout = QHBoxLayout(page)
            main_layout.setSpacing(20)
            main_layout.setContentsMargins(15, 15, 15, 15)

            # ========== Adicionar Pasta ==========
            group_add = QGroupBox("Adicionar Pasta")
            layout_add = QVBoxLayout(group_add)
            layout_add.setSpacing(10)

            self.folderNameInput_add = QLineEdit(self)
            self.folderColor_add = "#000000" # Não exibe o 'Cor:' bugado

            self.folderColorButton_add = QPushButton("Escolher Cor", self)
            self.folderColorButton_add.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4e54c8, stop:1 #8f94fb); color: white")
            self.folderColorButton_add.clicked.connect(self.onPickColorAdd)

            btn_add_folder = QPushButton("Criar Pasta", self)
            btn_add_folder.setStyleSheet("background-color: #28a745; color: white")
            btn_add_folder.clicked.connect(self.onAddFolder)

            row_actions_add = QHBoxLayout()
            row_actions_add.addWidget(self.folderColorButton_add)
            row_actions_add.addWidget(btn_add_folder)

            self.serverList_all = QListWidget(self)
            self.serverList_all.setSelectionMode(QListWidget.MultiSelection)
            self.refreshServerListUnified()

            layout_add.addWidget(QLabel("Nome da pasta:", self))
            layout_add.addWidget(self.folderNameInput_add)
            layout_add.addLayout(row_actions_add)
            layout_add.addWidget(QLabel("Servidores:", self))
            layout_add.addWidget(self.serverList_all)

            # ========== Editar/Remover Pasta ==========
            group_edit = QGroupBox("Editar/Remover Pasta")
            layout_edit = QVBoxLayout(group_edit)
            layout_edit.setSpacing(10)

            row_folder_meta = QHBoxLayout()
            column_left = QVBoxLayout()
            column_right = QVBoxLayout()

            # Lado esquerdo (Novo nome + Cor)
            column_left.addWidget(QLabel("Novo nome:", self))
            self.folderNameInput_edit = QLineEdit(self)
            column_left.addWidget(self.folderNameInput_edit)

            self.folderColor_edit = ""
            self.folderColorLabel_edit = QLabel("", self)  # Corrigido: Label invisível
            # NÃO adiciona self.folderColorLabel_edit no layout

            # Lado direito (Selecionar pasta)
            column_right.addWidget(QLabel("Selecione a pasta:", self))
            self.folderSelect_edit = QComboBox(self)
            self.refreshFolderSelectCombo()
            column_right.addWidget(self.folderSelect_edit)

            row_folder_meta.addLayout(column_left)
            row_folder_meta.addLayout(column_right)

            layout_edit.addLayout(row_folder_meta)

            row_actions_edit = QHBoxLayout()
            self.folderColorButton_edit = QPushButton("Escolher Nova Cor", self)
            self.folderColorButton_edit.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4e54c8, stop:1 #8f94fb); color: white")
            self.folderColorButton_edit.clicked.connect(self.onPickColorEdit)

            btn_edit_folder = QPushButton("Editar Pasta", self)
            btn_edit_folder.setStyleSheet("background-color: #ffc107; color: black")
            btn_edit_folder.clicked.connect(self.onEditFolder)

            btn_remove_folder = QPushButton("Remover Pasta", self)
            btn_remove_folder.setStyleSheet("background-color: #dc3545; color: white")
            btn_remove_folder.clicked.connect(self.onRemoveFolder)

            row_actions_edit.addWidget(self.folderColorButton_edit)
            row_actions_edit.addWidget(btn_edit_folder)
            row_actions_edit.addWidget(btn_remove_folder)

            layout_edit.addLayout(row_actions_edit)

            self.serverList_info = QListWidget(self)
            self.serverList_info.setSelectionMode(QListWidget.MultiSelection)  # <--- Aqui corrigido
            self.refreshServerListUnified(target=self.serverList_info)

            layout_edit.addWidget(QLabel("Servidores:", self))
            layout_edit.addWidget(self.serverList_info)

            main_layout.addWidget(group_add)
            main_layout.addWidget(group_edit)

            return page

        except Exception as e:
            logger.exception("Erro dentro de createFoldersPage")
            raise


    
    def refreshFolderSelectCombo(self):
        self.folderSelect_edit.clear()
        for folder in self.folders_data:
            self.folderSelect_edit.addItem(folder["name"])

    def refreshServerListUnified(self, target=None):
        if target is None:
            target = self.serverList_all
        target.clear()
        color_dict = {folder["name"]: folder["color"] for folder in self.folders_data}
        # Agrupar manualmente os servidores com pasta atribuída juntos por pasta
        grouped = {}
        for srv in self.servers_data:
            name = srv[0]
            folder = srv[3]
            if folder not in grouped:
                grouped[folder] = []
            grouped[folder].append(srv)

        # Ordena: pastas nomeadas primeiro (agrupadas), depois os sem pasta
        ordered_servers = []
        for folder in sorted([f for f in grouped if f is not None]):
            ordered_servers.extend(grouped[folder])
        if None in grouped:
            ordered_servers.extend(grouped[None])

        server_dict = {srv[0]: srv[3] for srv in ordered_servers}

        for server_name, folder_name in server_dict.items():
            item = QListWidgetItem(server_name)
            if folder_name:
                color = color_dict.get(folder_name, "#999999")
                circle = "\u2B24"  # bolinha Unicode
                item.setText(f"{server_name.ljust(24)}   {circle} {folder_name}")
                item.setForeground(QColor(color))
            else:
                item.setText(f"{server_name}   \u25CB (não atribuído)")
                item.setForeground(QColor("gray"))
            target.addItem(item)

    def refreshFolderList(self):
        self.folderSelect_edit.clear()
        for f in self.folders_data:
            try:
                name = f[0] if isinstance(f, (tuple, list)) else f.get("name", "??")
                self.folderSelect_edit.addItem(name)
            except Exception as e:
                logger.exception(f"Erro ao carregar pasta na lista de edição: {e}")


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

        selected_items = self.serverList_all.selectedItems()


        selected_names = [item.text() for item in selected_items]

        insert_folder(folder_name, self.folderColor_add)

        for name in selected_names:
            update_server_folder(name, folder_name)

        self.saveData()
        self.folderNameInput_add.clear()
        self.folderColor_add = "#000000"
        self.refreshFolderList()

    def onPickColorEdit(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.folderColor_edit = color.name()
            self.folderColorLabel_edit.setText(f"Cor selecionada: {self.folderColor_edit}")

    def onEditFolder(self):
        current_folder = self.folderSelect_edit.currentText()
        if not current_folder:
            QMessageBox.warning(self, "Atenção", "Selecione uma pasta para editar!")
            return

        new_name = self.folderNameInput_edit.text().strip()
        new_color = self.folderColor_edit if self.folderColor_edit else None

        update_folder_name_and_color(current_folder, new_name, new_color)

        self.saveData()
        self.folderNameInput_edit.clear()

        self.folderColor_edit = ""
        self.refreshFolderList()


    def onRemoveFolder(self):
        folder_to_remove = self.folderSelect_edit.currentText()
        if not folder_to_remove:
            QMessageBox.warning(self, "Atenção", "Selecione uma pasta para remover!")
            return

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