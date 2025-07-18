import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QFileSystemModel, QVBoxLayout, QWidget, QSplitter, QToolBar, QLineEdit, QMessageBox, QListWidget, QListWidgetItem, QMenuBar, QMenu, QHeaderView, QStyledItemDelegate, QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QCheckBox, QFileDialog, QInputDialog, QPushButton, QHBoxLayout, QProgressBar, QStackedWidget, QAbstractItemView, QTabWidget, QScrollArea, QTextEdit, QFormLayout, QTableWidget, QTableWidgetItem, QSizePolicy, QComboBox, QProgressDialog
)
from PySide6.QtCore import Qt, QDir, QThread, Signal, QObject, QFileSystemWatcher, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QPalette, QColor, QAction, QIcon, QKeySequence, QShortcut, QPixmap
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import random
import shutil
import subprocess
import difflib
import json
import stat
import platform
import mimetypes
import zipfile
import tarfile
try:
    import py7zr
    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False
try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False
try:
    import pycdlib
    HAS_ISO = True
except ImportError:
    HAS_ISO = False

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

class FolderSizeDelegate(QStyledItemDelegate):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.folder_size_cache = {}

    def displayText(self, value, locale):
        # value is the default file size (for files), or blank for folders
        index = self.parent().currentIndex()
        if not index.isValid():
            return value
        model = index.model()
        if hasattr(model, 'isDir') and model.isDir(index):
            folder_path = model.filePath(index)
            if folder_path in self.folder_size_cache:
                size = self.folder_size_cache[folder_path]
            else:
                size = self.get_folder_size(folder_path)
                self.folder_size_cache[folder_path] = size
            return self.human_readable_size(size)
        else:
            # For files, use the default value
            try:
                size = int(value)
                return self.human_readable_size(size)
            except Exception:
                return value

    def get_folder_size(self, folder):
        total = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except Exception:
                    pass
        return total

    def human_readable_size(self, size, decimal_places=2):
        for unit in ['B','KB','MB','GB','TB']:
            if size < 1024.0:
                return f"{size:.{decimal_places}f} {unit}"
            size /= 1024.0
        return f"{size:.{decimal_places}f} PB"
class RecentHistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Full Recent History')
        self.setMinimumSize(600, 400)
        layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.populate()
        layout.addWidget(self.list_widget)
        btn_layout = QHBoxLayout()
        open_btn = QPushButton('Open')
        remove_btn = QPushButton('Remove')
        close_btn = QPushButton('Close')
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
        open_btn.clicked.connect(self.open_selected)
        remove_btn.clicked.connect(self.remove_selected)
        close_btn.clicked.connect(self.close)
    def populate(self):
        self.list_widget.clear()
        for path in get_recent():
            self.list_widget.addItem(path)
    def open_selected(self):
        items = self.list_widget.selectedItems()
        if items:
            path = items[0].text()
            if os.path.exists(path):
                if os.path.isdir(path):
                    if hasattr(self.parent(), 'on_path_selected'):
                        self.parent().on_path_selected(path)
                else:
                    parent_dir = os.path.dirname(path)
                    if hasattr(self.parent(), 'on_path_selected'):
                        self.parent().on_path_selected(parent_dir)
            self.close()
    def remove_selected(self):
        items = self.list_widget.selectedItems()
        if items:
            path = items[0].text()
            recent = get_recent()
            if path in recent:
                recent.remove(path)
                recent_file = os.path.join(os.path.dirname(__file__), 'recent.json')
                with open(recent_file, 'w', encoding='utf-8') as f:
                    json.dump(recent, f)
                self.populate()
class OptionsDialog(QDialog):
    def __init__(self, parent=None, show_folder_sizes=False, current_theme=None, current_style=None):
        super().__init__(parent)
        self.setWindowTitle('Options')
        self.setMinimumWidth(300)
        layout = QVBoxLayout()
        self.folder_size_checkbox = QCheckBox('Show total size of folders')
        self.folder_size_checkbox.setChecked(show_folder_sizes)
        layout.addWidget(self.folder_size_checkbox)
        # Theme toggle
        layout.addWidget(QLabel('Theme:'))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['System', 'Light', 'Dark'])
        if current_theme in ['System', 'Light', 'Dark']:
            self.theme_combo.setCurrentText(current_theme)
        layout.addWidget(self.theme_combo)
        # Style selector
        layout.addWidget(QLabel('Widget Style:'))
        self.style_combo = QComboBox()
        # Expanded Qt styles
        self.style_combo.addItems(['Fusion', 'Windows', 'WindowsVista', 'macOS', 'Aqua', 'gtk', 'Material'])
        if current_style in ['Fusion', 'Windows', 'WindowsVista', 'macOS', 'Aqua', 'gtk', 'Material']:
            self.style_combo.setCurrentText(current_style)
        layout.addWidget(self.style_combo)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        # Add Show Full History button
        show_history_btn = QPushButton('Show Full History...')
        show_history_btn.clicked.connect(self.show_full_history)
        layout.addWidget(show_history_btn)
        self.setLayout(layout)
    def show_full_history(self):
        dlg = RecentHistoryDialog(self)
        dlg.exec()
    def get_selected_theme(self):
        return self.theme_combo.currentText()
    def get_selected_style(self):
        return self.style_combo.currentText()

class VideoPeekDialog(QDialog):
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Peek Video')
        self.setMinimumSize(480, 320)
        layout = QVBoxLayout()
        self.video_widget = QVideoWidget()
        layout.addWidget(self.video_widget)
        self.setLayout(layout)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.setSource(video_path)
        self.player.setLoops(1)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.player.positionChanged.connect(self.on_position_changed)
        self.random_start = 0
        self.duration = 0
        self.peek_length = 5000  # 5 seconds in ms
        self.has_peeked = False
        self.show()

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and not self.has_peeked:
            self.duration = self.player.duration()
            if self.duration > self.peek_length:
                self.random_start = random.randint(0, self.duration - self.peek_length)
            else:
                self.random_start = 0
            self.player.setPosition(self.random_start)
            self.player.play()
            self.has_peeked = True

    def on_position_changed(self, pos):
        if self.has_peeked and pos >= self.random_start + self.peek_length:
            self.player.pause()

class AppPickerDialog(QDialog):
    def __init__(self, parent=None, start_path=None):
        super().__init__(parent)
        self.setWindowTitle('Select Application')
        self.setMinimumSize(700, 500)
        self.history = []
        self.history_index = -1
        layout = QVBoxLayout()
        # Path bar and navigation
        nav_layout = QHBoxLayout()
        self.back_btn = QPushButton('<')
        self.forward_btn = QPushButton('>')
        self.path_bar = QLineEdit()
        self.path_bar.setMinimumWidth(300)
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.path_bar)
        layout.addLayout(nav_layout)
        self.back_btn.clicked.connect(self.go_back)
        self.forward_btn.clicked.connect(self.go_forward)
        self.path_bar.returnPressed.connect(self.go_to_path)
        # Sidebar
        self.sidebar = SidebarListWidget(self, on_path_selected=self.set_path)
        layout.addWidget(self.sidebar)
        self.sidebar.itemClicked.connect(self.on_sidebar_clicked)
        # File view
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self.model.setNameFilters(['*.exe', '*.bat', '*.cmd', '*.sh', '*.app'])
        self.model.setNameFilterDisables(False)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIsDecorated(False)
        self.tree.setSortingEnabled(True)
        self.tree.doubleClicked.connect(self.on_double_click)
        # Start at root of current drive
        if start_path:
            start = start_path
        else:
            start = os.path.splitdrive(os.getcwd())[0] + os.sep
        self.model.setRootPath(start)
        self.set_path(start)
        # Layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.tree)
        splitter.setSizes([160, 540])
        layout.addWidget(splitter)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.setLayout(layout)
        self.selected_path = None
        self.tree.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.shortcut_favorite = QShortcut(QKeySequence('Ctrl+X,L'), self)
        self.shortcut_favorite.activated.connect(self.favorite_current_path)
    def get_quick_folders(self):
        home = os.path.expanduser("~")
        folders = {
            "Desktop": os.path.join(home, "Desktop"),
            "Documents": os.path.join(home, "Documents"),
            "Downloads": os.path.join(home, "Downloads"),
            "Pictures": os.path.join(home, "Pictures"),
            "Music": os.path.join(home, "Music"),
            "Videos": os.path.join(home, "Videos"),
            "Home": home
        }
        return {k: v for k, v in folders.items() if os.path.exists(v)}
    def set_path(self, path):
        if not os.path.exists(path):
            return
        idx = self.model.index(path)
        self.tree.setRootIndex(idx)
        self.path_bar.setText(path)
        # Update history
        if self.history_index == -1 or self.history[self.history_index] != path:
            self.history = self.history[:self.history_index+1]
            self.history.append(path)
            self.history_index += 1
        self.update_nav_buttons()
    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.set_path(self.history[self.history_index])
    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.set_path(self.history[self.history_index])
    def go_to_path(self):
        path = self.path_bar.text()
        self.set_path(path)
    def on_sidebar_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.set_path(path)
    def on_selection_changed(self):
        indexes = self.tree.selectionModel().selectedIndexes()
        if indexes:
            idx = indexes[0]
            if self.model.isDir(idx):
                self.selected_path = None
            else:
                self.selected_path = self.model.filePath(idx)
        else:
            self.selected_path = None
    def on_double_click(self, index):
        if self.model.isDir(index):
            self.set_path(self.model.filePath(index))
        else:
            self.selected_path = self.model.filePath(index)
            self.accept()
    def get_selected_path(self):
        return self.selected_path
    def update_nav_buttons(self):
        self.back_btn.setEnabled(self.history_index > 0)
        self.forward_btn.setEnabled(self.history_index < len(self.history) - 1)
    def favorite_current_path(self):
        path = self.path_bar.text()
        if path and hasattr(self.sidebar, 'add_to_favorites'):
            self.sidebar.add_to_favorites(path)
            QMessageBox.information(self, 'Favorites', f'Added to Favorites: {path}')

class OpenWithDialog(QDialog):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Open with...')
        self.setMinimumWidth(400)
        self.file_path = file_path
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'File: {file_path}'))
        self.app_path_edit = QLineEdit()
        self.app_path_edit.setPlaceholderText('Application path (e.g. C:/Windows/System32/notepad.exe)')
        layout.addWidget(self.app_path_edit)
        browse_btn = QPushButton('Browse...')
        browse_btn.clicked.connect(self.browse_app)
        layout.addWidget(browse_btn)
        self.command_label = QLabel('')
        layout.addWidget(self.command_label)
        self.app_path_edit.textChanged.connect(self.update_command_label)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.setLayout(layout)
        self.update_command_label()

    def browse_app(self):
        dlg = AppPickerDialog(self)
        if dlg.exec() == QDialog.Accepted:
            app_path = dlg.get_selected_path()
            if app_path:
                self.app_path_edit.setText(app_path)

    def update_command_label(self):
        app = self.app_path_edit.text().strip()
        if app:
            self.command_label.setText(f'Command: {app} -{self.file_path}')
        else:
            self.command_label.setText('')

    def get_app_path(self):
        return self.app_path_edit.text().strip()

# --- AboutDialog for About box ---
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('About Dolphy File Manager')
        self.setMinimumSize(500, 250)
        layout = QHBoxLayout()
        # Image paths
        self.sierra_path = os.path.join(os.path.dirname(__file__), 'src', 'sierra.png')
        self.icon_path = os.path.join(os.path.dirname(__file__), 'src', 'icon.png')
        self.current_img = 'sierra' if os.path.exists(self.sierra_path) else 'icon'
        # Image label
        self.img_label = QLabel()
        self.img_label.setCursor(Qt.PointingHandCursor)
        self.img_label.mousePressEvent = self.toggle_image
        self.update_image()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.img_label)
        # About text
        about_text = QLabel(
            '<h2>Dolphy File Manager</h2>'
            '<p>A modern, user-friendly file manager for Windows, macOS, and Linux.<br>'
            'Features include:<ul>'
            '<li>Tabbed browsing</li>'
            '<li>Sidebar with favorites, libraries, and network</li>'
            '<li>Archive support (zip, 7z, rar, etc.)</li>'
            '<li>Search, preview, and more</li>'
            '</ul>'
            '<p>Copyright © 2024 Dolphy Team</p>'
        )
        about_text.setWordWrap(True)
        about_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(about_text)
        self.setLayout(layout)

    def update_image(self):
        if self.current_img == 'sierra' and os.path.exists(self.sierra_path):
            pixmap = QPixmap(self.sierra_path)
        else:
            pixmap = QPixmap(self.icon_path)
        self.img_label.setPixmap(pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def toggle_image(self, event):
        if self.current_img == 'sierra' and os.path.exists(self.icon_path):
            self.current_img = 'icon'
        elif os.path.exists(self.sierra_path):
            self.current_img = 'sierra'
        self.update_image()

class SidebarSection:
    FAVORITES = 'Favorites'
    LIBRARIES = 'Libraries'
    COMPUTER = 'Computer'
    RECENT = 'Recent'
    NETWORK = 'Network'

class SidebarListWidget(QListWidget):
    def __init__(self, parent=None, on_path_selected=None):
        super().__init__(parent)
        self.setMaximumWidth(180)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)
        self.favorites = self.load_favorites()
        self.on_path_selected = on_path_selected
        self.refresh()
        self.itemClicked.connect(self.handle_item_clicked)
    def favorites_file(self):
        return os.path.join(os.path.dirname(__file__), 'favorites.json')
    def load_favorites(self):
        try:
            with open(self.favorites_file(), 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    def save_favorites(self):
        try:
            with open(self.favorites_file(), 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f)
        except Exception:
            pass
    def refresh(self):
        self.clear()
        # Recent (limit to 5)
        self.addItem(self._section_item(SidebarSection.RECENT))
        for recent in get_recent(limit=5):
            item = QListWidgetItem(QIcon.fromTheme('document-open-recent'), recent)
            item.setData(Qt.ItemDataRole.UserRole, recent)
            item.setData(Qt.ItemDataRole.UserRole + 1, SidebarSection.RECENT)
            self.addItem(item)
        # Add 'Show Full History' button
        show_all_item = QListWidgetItem('Show Full History...')
        show_all_item.setData(Qt.ItemDataRole.UserRole, '::show_full_history::')
        show_all_item.setData(Qt.ItemDataRole.UserRole + 1, SidebarSection.RECENT)
        self.addItem(show_all_item)
        self.addItem(self._hr_item())
        # Favorites
        self.addItem(self._section_item(SidebarSection.FAVORITES))
        for fav in self.favorites:
            item = QListWidgetItem(QIcon.fromTheme('folder'), fav)
            item.setData(Qt.ItemDataRole.UserRole, fav)
            item.setData(Qt.ItemDataRole.UserRole + 1, SidebarSection.FAVORITES)
            self.addItem(item)
        self.addItem(self._hr_item())
        # Libraries
        self.addItem(self._section_item(SidebarSection.LIBRARIES))
        for name, path in self.get_libraries().items():
            item = QListWidgetItem(QIcon.fromTheme('folder'), name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(Qt.ItemDataRole.UserRole + 1, SidebarSection.LIBRARIES)
            self.addItem(item)
        self.addItem(self._hr_item())
        # Computer (drives)
        self.addItem(self._section_item(SidebarSection.COMPUTER))
        for drive in self.get_drives():
            item = QListWidgetItem(QIcon.fromTheme('drive-harddisk'), drive)
            item.setData(Qt.ItemDataRole.UserRole, drive)
            item.setData(Qt.ItemDataRole.UserRole + 1, SidebarSection.COMPUTER)
            self.addItem(item)
        # Network section header with icon
        net_header = QListWidgetItem(QIcon.fromTheme('network-workgroup'), SidebarSection.NETWORK)
        font = net_header.font()
        font.setBold(True)
        net_header.setFont(font)
        net_header.setFlags(Qt.ItemFlag.NoItemFlags)
        self.addItem(net_header)
        # Network locations
        for net in getattr(self, 'network_locations', []):
            icon = QIcon.fromTheme('network-server')
            if isinstance(net, dict):
                proto = net.get('type', '').lower()
                if proto == 'ftp':
                    icon = QIcon.fromTheme('network-server-ftp')
                elif proto == 'sftp':
                    icon = QIcon.fromTheme('network-server-ssh')
                elif proto == 'smb':
                    icon = QIcon.fromTheme('network-server-samba')
                elif proto == 'webdav':
                    icon = QIcon.fromTheme('network-server-webdav')
                elif proto == 'nfs':
                    icon = QIcon.fromTheme('network-server-nfs')
                elif proto == 'rtsp':
                    icon = QIcon.fromTheme('media-playback-start')
                elif proto == 'mjpeg/http':
                    icon = QIcon.fromTheme('camera-web')
                name = net.get('name') or net.get('address')
                item = QListWidgetItem(icon, name)
                item.setData(Qt.ItemDataRole.UserRole, net)
                item.setData(Qt.ItemDataRole.UserRole + 1, SidebarSection.NETWORK)
            else:
                item = QListWidgetItem(icon, str(net))
                item.setData(Qt.ItemDataRole.UserRole, net)
                item.setData(Qt.ItemDataRole.UserRole + 1, SidebarSection.NETWORK)
            self.addItem(item)
        # Add 'Add' button
        add_item = QListWidgetItem(QIcon.fromTheme('list-add'), 'Add')
        add_item.setData(Qt.ItemDataRole.UserRole, '::add::')
        add_item.setData(Qt.ItemDataRole.UserRole + 1, SidebarSection.NETWORK)
        self.addItem(add_item)
    def _section_item(self, name):
        item = QListWidgetItem(name)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        return item
    def _hr_item(self):
        item = QListWidgetItem('────────────────────────────')
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        return item
    def get_libraries(self):
        home = os.path.expanduser("~")
        folders = {
            "Desktop": os.path.join(home, "Desktop"),
            "Documents": os.path.join(home, "Documents"),
            "Downloads": os.path.join(home, "Downloads"),
            "Pictures": os.path.join(home, "Pictures"),
            "Music": os.path.join(home, "Music"),
            "Videos": os.path.join(home, "Videos"),
            "Home": home
        }
        return {k: v for k, v in folders.items() if os.path.exists(v)}
    def get_drives(self):
        import string
        drives = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
        return drives
    def on_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        section = item.data(Qt.ItemDataRole.UserRole + 1)
        path = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        if section == SidebarSection.LIBRARIES or section == SidebarSection.COMPUTER:
            fav_action = QAction('Add to Favorites', self)
            fav_action.triggered.connect(lambda: self.add_to_favorites(path))
            menu.addAction(fav_action)
        elif section == SidebarSection.FAVORITES:
            rm_action = QAction('Remove from Favorites', self)
            rm_action.triggered.connect(lambda: self.remove_from_favorites(path))
            menu.addAction(rm_action)
        elif section == SidebarSection.NETWORK:
            if path == '::add::':
                net_path, ok = QInputDialog.getText(self, 'Add Network Location', 'Enter network path (e.g. smb://server/share):')
                if ok and net_path:
                    if not hasattr(self, 'network_locations'):
                        self.network_locations = []
                    self.network_locations.append(net_path)
                    self.refresh()
            else:
                # For existing network locations, we can't add them to favorites or remove them
                # This context menu is primarily for adding new ones.
                pass
        menu.exec(self.viewport().mapToGlobal(pos))
    def add_to_favorites(self, path):
        if path and path not in self.favorites:
            self.favorites.insert(0, path)
            self.save_favorites()
            self.refresh()
    def remove_from_favorites(self, path):
        if path in self.favorites:
            self.favorites.remove(path)
            self.save_favorites()
            self.refresh()
    def handle_item_clicked(self, item):
        section = item.data(Qt.ItemDataRole.UserRole + 1)
        path = item.data(Qt.ItemDataRole.UserRole)
        # Handle the Show Full History button
        if section == SidebarSection.RECENT and path == '::show_full_history::':
            dlg = RecentHistoryDialog(self)
            dlg.exec()
            return
        # Only respond to real paths, not section headers or separators
        if section == SidebarSection.RECENT and path:
            # Open recent file/folder
            if os.path.isdir(path):
                self.on_path_selected(path)
            elif os.path.isfile(path):
                parent_dir = os.path.dirname(path)
                self.on_path_selected(parent_dir)
                main_window = self.parent() if hasattr(self, 'parent') else None
                if main_window and hasattr(main_window, 'file_view') and hasattr(main_window, 'model'):
                    model = main_window.model
                    file_view = main_window.file_view
                    for row in range(model.rowCount(model.index(parent_dir))):
                        idx = model.index(row, 0, model.index(parent_dir))
                        if model.filePath(idx) == path:
                            file_view.setCurrentIndex(idx)
                            break
            return
        # RTSP support: if network location is RTSP, open in video preview
        if section == SidebarSection.NETWORK and isinstance(path, dict) and path.get('type', '').lower() == 'rtsp':
            rtsp_url = path.get('address')
            if rtsp_url:
                dlg = VideoPeekDialog(rtsp_url, self)
                dlg.exec()
            return
        # MJPEG/HTTP support: open MJPEG stream viewer
        if section == SidebarSection.NETWORK and isinstance(path, dict) and path.get('type', '').lower() == 'mjpeg/http':
            mjpeg_url = path.get('address')
            if mjpeg_url:
                dlg = MJPEGViewerDialog(mjpeg_url, self)
                dlg.exec()
            return
        if section == SidebarSection.NETWORK and path == '::add::':
            # Rich Add Network dialog
            dlg = QDialog(self)
            dlg.setWindowTitle('Add Network Location')
            vbox = QVBoxLayout()
            vbox.addWidget(QLabel('Type:'))
            type_combo = QComboBox()
            type_combo.addItems(['FTP', 'SFTP', 'SMB/CIFS', 'WebDAV', 'NFS', 'RTSP', 'MJPEG/HTTP', 'Custom'])
            vbox.addWidget(type_combo)
            vbox.addWidget(QLabel('Address/Host:'))
            address_edit = QLineEdit()
            vbox.addWidget(address_edit)
            vbox.addWidget(QLabel('Port (optional):'))
            port_edit = QLineEdit()
            vbox.addWidget(port_edit)
            vbox.addWidget(QLabel('Username:'))
            user_edit = QLineEdit()
            vbox.addWidget(user_edit)
            vbox.addWidget(QLabel('Password:'))
            pass_edit = QLineEdit()
            pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
            vbox.addWidget(pass_edit)
            vbox.addWidget(QLabel('Share/Path:'))
            share_edit = QLineEdit()
            vbox.addWidget(share_edit)
            vbox.addWidget(QLabel('Bookmark Name (optional):'))
            name_edit = QLineEdit()
            vbox.addWidget(name_edit)
            anon_box = QCheckBox('Anonymous')
            savepw_box = QCheckBox('Save password')
            vbox.addWidget(anon_box)
            vbox.addWidget(savepw_box)
            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            vbox.addWidget(btns)
            dlg.setLayout(vbox)
            if dlg.exec() == QDialog.Accepted:
                net = {
                    'type': type_combo.currentText(),
                    'address': address_edit.text().strip(),
                    'port': port_edit.text().strip(),
                    'username': user_edit.text().strip(),
                    'password': pass_edit.text() if savepw_box.isChecked() else '',
                    'share': share_edit.text().strip(),
                    'name': name_edit.text().strip() or address_edit.text().strip(),
                    'anonymous': anon_box.isChecked(),
                }
                if not hasattr(self, 'network_locations'):
                    self.network_locations = []
                self.network_locations.append(net)
                self.refresh()
            return
        if section in (SidebarSection.FAVORITES, SidebarSection.LIBRARIES, SidebarSection.COMPUTER) and path and self.on_path_selected:
            if os.path.isfile(path):
                parent_dir = os.path.dirname(path)
                # Call parent's set_path, then select the file
                self.on_path_selected(parent_dir)
                # Select the file in the file view after navigation
                main_window = self.parent() if hasattr(self, 'parent') else None
                if main_window and hasattr(main_window, 'file_view') and hasattr(main_window, 'model'):
                    model = main_window.model
                    file_view = main_window.file_view
                    for row in range(model.rowCount(model.index(parent_dir))):
                        idx = model.index(row, 0, model.index(parent_dir))
                        if model.filePath(idx) == path:
                            file_view.setCurrentIndex(idx)
                            break
            else:
                self.on_path_selected(path)

class NotificationPopup(QWidget):
    def __init__(self, parent, message, duration=2000):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.ToolTip)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.label = QLabel(message, self)
        self.label.setStyleSheet('''
            background: #23272e;
            color: #fff;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 15px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.25);
        ''')
        self.label.adjustSize()
        self.resize(self.label.size())
        self.duration = duration
        self.opacity_anim = QPropertyAnimation(self, b'windowOpacity')
        self.opacity_anim.setDuration(350)
        self.opacity_anim.setStartValue(0)
        self.opacity_anim.setEndValue(1)
        self.opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.opacity_anim.finished.connect(self.start_hide_timer)
        self.hide_anim = QPropertyAnimation(self, b'windowOpacity')
        self.hide_anim.setDuration(350)
        self.hide_anim.setStartValue(1)
        self.hide_anim.setEndValue(0)
        self.hide_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.hide_anim.finished.connect(self.close)
    def showEvent(self, event):
        super().showEvent(event)
        parent_geom = self.parent().geometry()
        x = parent_geom.x() + parent_geom.width() - self.width() - 32
        y = parent_geom.y() + parent_geom.height() - self.height() - 32
        self.move(x, y)
        self.setWindowOpacity(0)
        self.opacity_anim.start()
    def start_hide_timer(self):
        QTimer.singleShot(self.duration, self.hide_with_animation)
    def hide_with_animation(self):
        self.hide_anim.start()

class FileManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.on_directory_changed)
        self.watcher.fileChanged.connect(self.on_file_changed)
        self.statusBar().showMessage('Ready')
        # Set app icon
        icon_path = os.path.join(os.path.dirname(__file__), "src/icon.png")
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowTitle('Dolphy File Manager')
        self.setGeometry(100, 100, 1200, 600)
        self.show_folder_sizes = False
        # Theme and style state
        self.selected_theme = 'System'
        self.selected_style = 'Fusion'
        # Navigation history
        self.history = []
        self.history_index = -1

        # File system model (only create once)
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self.root_path = os.path.expanduser("~")
        self.model.setRootPath(self.root_path)

        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.setMovable(True)
        self.toolbar.setFloatable(False)
        self.toolbar.setSizePolicy(self.toolbar.sizePolicy().horizontalPolicy(), self.toolbar.sizePolicy().verticalPolicy())
        self.addToolBar(self.toolbar)
        self.action_back = QAction('Back', self)
        self.action_forward = QAction('Forward', self)
        self.action_up = QAction('Up', self)
        self.action_refresh = QAction('Refresh', self)
        self.toolbar.addAction(self.action_back)
        self.toolbar.addAction(self.action_forward)
        self.toolbar.addAction(self.action_up)
        self.toolbar.addAction(self.action_refresh)

        # --- Address/Progress bar with progress ring ---
        self.address_bar = QLineEdit()
        self.address_bar.setMinimumWidth(400)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumWidth(400)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.address_stack = QStackedWidget()
        self.address_stack.addWidget(self.address_bar)
        self.address_stack.addWidget(self.progress_bar)
        self.toolbar.addWidget(self.address_stack)
        # Progress ring (placeholder: QLabel, to be replaced with spinner GIF or custom widget)
        self.progress_ring = QLabel()
        self.progress_ring.setVisible(False)
        self.progress_ring.setFixedSize(24, 24)
        self.toolbar.addWidget(self.progress_ring)

        # --- Search UI ---
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText('Search files...')
        self.search_bar.setMinimumWidth(200)
        self.toolbar.addWidget(self.search_bar)
        self.recursive_checkbox = QCheckBox('Recursive')
        self.toolbar.addWidget(self.recursive_checkbox)
        self.clear_search_btn = QPushButton('Clear Search')
        self.toolbar.addWidget(self.clear_search_btn)
        self.clear_search_btn.setVisible(False)
        # Connect search events
        self.search_bar.returnPressed.connect(self.on_search)
        self.clear_search_btn.clicked.connect(self.on_clear_search)

        self.action_back.triggered.connect(self.go_back)
        self.action_forward.triggered.connect(self.go_forward)
        self.action_up.triggered.connect(self.go_up)
        self.action_refresh.triggered.connect(self.refresh)
        self.address_bar.returnPressed.connect(self.go_to_path)

        # Sidebar for quick access
        self.sidebar = SidebarListWidget(self, on_path_selected=self.set_path)
        layout = QVBoxLayout()
        layout.addWidget(self.sidebar)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # File view (not a tree, just the contents of the selected folder)
        self.file_view = QTreeView()
        self.file_view.setModel(self.model)
        self.file_view.setRootIsDecorated(False)
        self.file_view.setSortingEnabled(True)
        self.file_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_view.doubleClicked.connect(self.on_file_double_clicked)
        self.set_path(self.root_path)
        self.file_view.setColumnWidth(0, 250)
        self.file_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_view.customContextMenuRequested.connect(self.on_file_view_context_menu)
        # Enable drag and drop
        self.file_view.setDragEnabled(True)
        self.file_view.setAcceptDrops(True)
        self.file_view.setDropIndicatorShown(True)
        self.file_view.setDragDropMode(QAbstractItemView.DragDrop)
        self.file_view.dropEvent = self.file_view_dropEvent

        # Menu bar and Options menu
        # Remove the old Options menu and folder size toggle
        # (Delete or comment out the following lines)
        menubar = QMenuBar(self)
        tools_menu = QMenu('Tools', self)
        self.action_options = QAction('Options', self)
        self.action_options.triggered.connect(self.show_options_dialog)
        tools_menu.addAction(self.action_options)
        menubar.addMenu(tools_menu)
        # Add Help menu with About
        help_menu = QMenu('Help', self)
        self.action_about = QAction('About', self)
        self.action_about.triggered.connect(self.show_about_dialog)
        help_menu.addAction(self.action_about)
        menubar.addMenu(help_menu)
        self.setMenuBar(menubar)

        # Splitter to separate sidebar and file view
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.file_view)
        splitter.setSizes([160, 740])

        # Main layout
        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Set up file view header
        resize_mode = getattr(QHeaderView, 'ResizeToContents', 0)
        self.file_view.header().setSectionResizeMode(0, resize_mode)
        self.file_view.header().setSectionResizeMode(1, resize_mode)
        self.file_view.header().setSectionResizeMode(2, resize_mode)
        self.file_view.header().setSectionResizeMode(3, resize_mode)
        self.file_view.setColumnWidth(0, 250)
        self.file_view.setColumnWidth(1, 120)
        self.file_view.setColumnWidth(2, 100)
        self.file_view.setColumnWidth(3, 120)

        self.folder_size_delegate = FolderSizeDelegate(self.model, self.file_view)
        self.clipboard_paths = []
        self.clipboard_mode = None
        self.shortcut_favorite = QShortcut(QKeySequence('Ctrl+X,L'), self)
        self.shortcut_favorite.activated.connect(self.favorite_current_path)
        # Add global shortcut Ctrl+X+L to go to Desktop
        self.shortcut_desktop = QShortcut(QKeySequence('Ctrl+X+L'), self)
        self.shortcut_desktop.activated.connect(self.go_to_desktop)

        # Set theme and style on startup
        theme = detect_system_theme()
        self.selected_theme = 'System'
        self.selected_style = 'Fusion'
        if theme == 'dark':
            set_dark_palette(QApplication.instance())
        else:
            set_light_palette(QApplication.instance())
        try:
            QApplication.instance().setStyle('Fusion')
        except Exception:
            pass

    def toggle_folder_size(self, checked):
        self.show_folder_sizes = checked
        if checked:
            self.file_view.setItemDelegateForColumn(1, self.folder_size_delegate)
        else:
            self.file_view.setItemDelegateForColumn(1, None)

    def update_folder_sizes(self):
        if not self.show_folder_sizes:
            self.file_view.reset()
            return
        root_index = self.file_view.rootIndex()
        model = self.file_view.model()
        if not isinstance(model, QFileSystemModel):
            return
        for row in range(model.rowCount(root_index)):
            idx = model.index(row, 0, root_index)
            if model.isDir(idx):
                folder_path = model.filePath(idx)
                size = self.get_folder_size(folder_path)
                size_str = self.human_readable_size(size)
                size_idx = model.index(row, 1, root_index)
                model.setData(size_idx, size_str)

    def get_folder_size(self, folder):
        total = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except Exception:
                    pass
        return total

    def human_readable_size(self, size, decimal_places=2):
        for unit in ['B','KB','MB','GB','TB']:
            if size < 1024.0:
                return f"{size:.{decimal_places}f} {unit}"
            size /= 1024.0
        return f"{size:.{decimal_places}f} PB"

    def set_path(self, path):
        if not os.path.exists(path):
            QMessageBox.warning(self, "Path not found", f"The path '{path}' does not exist.")
            return
        # Remove previous watches
        self.watcher.removePaths(self.watcher.directories())
        self.watcher.removePaths(self.watcher.files())
        # Add new watch
        if os.path.isdir(path):
            self.watcher.addPath(path)
        self.model.setRootPath(path)
        idx = self.model.index(path)
        self.file_view.setRootIndex(idx)
        self.address_bar.setText(path)
        # Update history
        if self.history_index == -1 or self.history[self.history_index] != path:
            self.history = self.history[:self.history_index+1]
            self.history.append(path)
            self.history_index += 1
        if self.show_folder_sizes:
            self.update_folder_sizes()

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.set_path(self.history[self.history_index])

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.set_path(self.history[self.history_index])

    def go_up(self):
        current_path = self.address_bar.text()
        parent_path = os.path.dirname(current_path)
        if parent_path and os.path.exists(parent_path):
            self.set_path(parent_path)

    def refresh(self):
        self.set_path(self.address_bar.text())

    def go_to_path(self):
        path = self.address_bar.text()
        self.set_path(path)

    def on_sidebar_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.set_path(path)

    def on_file_double_clicked(self, index):
        file_path = self.model.filePath(index)
        if os.path.isdir(file_path):
            self.set_path(file_path)
        else:
            try:
                if sys.platform.startswith('win'):
                    os.startfile(file_path)
                elif sys.platform.startswith('darwin'):
                    subprocess.Popen(['open', file_path])
                else:
                    subprocess.Popen(['xdg-open', file_path])
                add_recent(file_path)
            except Exception as e:
                QMessageBox.warning(self, 'Open', f'Could not open: {e}')

    def get_quick_folders(self):
        home = os.path.expanduser("~")
        folders = {
            "Desktop": os.path.join(home, "Desktop"),
            "Documents": os.path.join(home, "Documents"),
            "Downloads": os.path.join(home, "Downloads"),
            "Pictures": os.path.join(home, "Pictures"),
            "Music": os.path.join(home, "Music"),
            "Videos": os.path.join(home, "Videos"),
            "Home": home
        }
        # Only include folders that exist
        return {k: v for k, v in folders.items() if os.path.exists(v)}

    def show_options_dialog(self):
        dlg = OptionsDialog(self, self.show_folder_sizes, current_theme=self.selected_theme, current_style=self.selected_style)
        if dlg.exec() == QDialog.Accepted:
            checked = dlg.folder_size_checkbox.isChecked()
            self.show_folder_sizes = checked
            if checked:
                self.file_view.setItemDelegateForColumn(1, self.folder_size_delegate)
            else:
                self.file_view.setItemDelegateForColumn(1, None)
            # Theme
            selected_theme = dlg.get_selected_theme()
            self.selected_theme = selected_theme
            if selected_theme == 'System':
                theme = detect_system_theme()
                if theme == 'dark':
                    set_dark_palette(QApplication.instance())
                else:
                    set_light_palette(QApplication.instance())
            elif selected_theme == 'Dark':
                set_dark_palette(QApplication.instance())
            elif selected_theme == 'Light':
                set_light_palette(QApplication.instance())
            # Style
            selected_style = dlg.get_selected_style()
            self.selected_style = selected_style
            try:
                QApplication.instance().setStyle(selected_style)
                # Check if the style was actually applied
                current_style = QApplication.instance().style().objectName().lower()
                if current_style != selected_style.lower():
                    raise ValueError('Style not applied')
            except Exception:
                QMessageBox.warning(self, 'Style Not Available', f'The style "{selected_style}" is not available on this system.')

    def on_file_view_context_menu(self, pos):
        index = self.file_view.indexAt(pos)
        model = self.file_view.model()
        menu = QMenu(self)
        file_path = None
        is_file = False
        is_folder = False
        if index.isValid() and hasattr(model, 'filePath'):
            file_path = model.filePath(index)
            is_file = os.path.isfile(file_path)
            is_folder = os.path.isdir(file_path)
        else:
            idx = self.file_view.rootIndex()
            file_path = model.filePath(idx) if hasattr(model, 'filePath') else None
            is_folder = True if file_path and os.path.isdir(file_path) else False

        # Get all selected paths
        selected_indexes = self.file_view.selectionModel().selectedRows(0)
        selected_paths = [model.filePath(idx) for idx in selected_indexes if idx.isValid()]
        if not selected_paths and file_path:
            selected_paths = [file_path]

        if is_file or is_folder:
            open_action = QAction('Open', self)
            open_action.triggered.connect(lambda: self.open_item(file_path))
            menu.addAction(open_action)

            open_with_action = QAction('Open with...', self)
            open_with_action.triggered.connect(lambda: self.open_with(file_path))
            menu.addAction(open_with_action)

            copy_action = QAction('Copy', self)
            copy_action.triggered.connect(lambda: self.copy_item(selected_paths))
            menu.addAction(copy_action)

            cut_action = QAction('Cut', self)
            cut_action.triggered.connect(lambda: self.cut_item(selected_paths))
            menu.addAction(cut_action)

            paste_action = QAction('Paste', self)
            paste_action.triggered.connect(lambda: self.paste_item(file_path))
            menu.addAction(paste_action)

            rename_action = QAction('Rename', self)
            # Only enable rename if one item is selected
            rename_action.setEnabled(len(selected_paths) == 1)
            rename_action.triggered.connect(lambda: self.rename_item(file_path))
            menu.addAction(rename_action)

            delete_action = QAction('Delete', self)
            delete_action.triggered.connect(lambda: self.delete_item(selected_paths))
            menu.addAction(delete_action)

            properties_action = QAction('Properties', self)
            properties_action.triggered.connect(lambda: self.show_properties(file_path))
            menu.addAction(properties_action)

            copy_path_action = QAction('Copy Path', self)
            copy_path_action.triggered.connect(lambda: self.copy_path(file_path))
            menu.addAction(copy_path_action)

            # Add to Favorites
            add_fav_action = QAction('Add to Favorites', self)
            add_fav_action.triggered.connect(lambda: [self.sidebar.add_to_favorites(p) for p in selected_paths])
            menu.addAction(add_fav_action)

            if is_folder:
                new_folder_action = QAction('New Folder', self)
                new_folder_action.triggered.connect(lambda: self.new_folder(file_path))
                menu.addAction(new_folder_action)

            if is_file and self.is_video_file(file_path):
                peek_action = QAction('Peek', self)
                peek_action.triggered.connect(lambda: self.peek_video(file_path))
                menu.addAction(peek_action)

            # Compression/Extraction
            compress_action = QAction('Compress...', self)
            compress_action.triggered.connect(lambda: self.compress_items(selected_paths))
            menu.addAction(compress_action)
            # Only show Extract Here for supported archive files
            if is_file and self.is_supported_archive(file_path):
                extract_action = QAction('Extract Here', self)
                extract_action.triggered.connect(lambda: self.extract_item(file_path, os.path.dirname(file_path)))
                menu.addAction(extract_action)
        else:
            if is_folder:
                new_folder_action = QAction('New Folder', self)
                new_folder_action.triggered.connect(lambda: self.new_folder(file_path))
                menu.addAction(new_folder_action)
                paste_action = QAction('Paste', self)
                paste_action.triggered.connect(lambda: self.paste_item(file_path))
                menu.addAction(paste_action)

        menu.exec(self.file_view.viewport().mapToGlobal(pos))

    def open_item(self, file_path):
        if os.path.isdir(file_path):
            self.set_path(file_path)
        else:
            try:
                os.startfile(file_path)
            except Exception as e:
                QMessageBox.warning(self, 'Open', f'Could not open: {e}')

    def open_with(self, file_path):
        dlg = OpenWithDialog(file_path, self)
        if dlg.exec() == QDialog.Accepted:
            app_path = dlg.get_app_path()
            if app_path:
                try:
                    subprocess.Popen([app_path, f'-{file_path}'])
                except Exception as e:
                    QMessageBox.warning(self, 'Open with...', f'Could not open: {e}')

    def copy_item(self, file_paths):
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        self.clipboard_paths = file_paths
        self.clipboard_mode = 'copy'
        QMessageBox.information(self, 'Copy', f'{len(file_paths)} item(s) ready to paste.')

    def cut_item(self, file_paths):
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        self.clipboard_paths = file_paths
        self.clipboard_mode = 'cut'
        QMessageBox.information(self, 'Cut', f'{len(file_paths)} item(s) ready to paste.')

    def paste_item(self, folder_path):
        if not self.clipboard_paths or not self.clipboard_mode:
            QMessageBox.information(self, 'Paste', 'Nothing to paste.')
            return
        for src in self.clipboard_paths:
            dst = os.path.join(folder_path, os.path.basename(src))
            try:
                if self.clipboard_mode == 'copy':
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                elif self.clipboard_mode == 'cut':
                    shutil.move(src, dst)
            except Exception as e:
                QMessageBox.warning(self, 'Paste', f'Could not paste: {e}')
        self.clipboard_paths = []
        self.clipboard_mode = None
        self.refresh()

    def rename_item(self, file_path):
        new_name, ok = QInputDialog.getText(self, 'Rename', 'Enter new name:', text=os.path.basename(file_path))
        if ok and new_name:
            new_path = os.path.join(os.path.dirname(file_path), new_name)
            try:
                os.rename(file_path, new_path)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, 'Rename', f'Could not rename: {e}')

    def delete_item(self, file_paths):
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        reply = QMessageBox.question(self, 'Delete', f'Are you sure you want to delete {len(file_paths)} item(s)?', QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.progress_dialog = QProgressDialog('Deleting files...', 'Cancel', 0, 100, self)
        self.progress_dialog.setWindowTitle('Deleting')
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setValue(0)
        self.delete_worker = DeleteWorker(file_paths)
        self.delete_worker.progress.connect(self.progress_dialog.setValue)
        self.delete_worker.error.connect(lambda msg: QMessageBox.warning(self, 'Delete', msg))
        self.delete_worker.finished.connect(self.on_delete_finished)
        self.progress_dialog.canceled.connect(self.delete_worker.interrupt)
        self.delete_worker.start()
        self.progress_dialog.exec()
    def on_delete_finished(self):
        self.progress_dialog.close()
        self.refresh()
        self.show_notification('Delete operation completed.')

    def show_properties(self, file_path_or_paths):
        if isinstance(file_path_or_paths, str):
            file_paths = [file_path_or_paths]
        else:
            file_paths = file_path_or_paths
        preview_widget = None
        # --- Single selection ---
        if len(file_paths) == 1:
            file_path = file_paths[0]
            stat_result = None
            try:
                stat_result = os.stat(file_path)
            except Exception:
                pass
            # General tab with icon/thumbnail and QFormLayout
            general_widget = QWidget()
            general_layout = QVBoxLayout()
            general_layout.setContentsMargins(10, 10, 10, 10)
            icon_name_layout = QHBoxLayout()
            icon_name_layout.setContentsMargins(0, 0, 0, 0)
            # Icon/thumbnail
            icon_label = QLabel()
            icon_pixmap = None
            if os.path.isdir(file_path):
                icon_pixmap = QIcon.fromTheme('folder').pixmap(36, 36)
            else:
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp']:
                    from PySide6.QtGui import QPixmap
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        icon_pixmap = pixmap.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                if not icon_pixmap:
                    icon_pixmap = QIcon.fromTheme('text-x-generic').pixmap(36, 36)
            if icon_pixmap:
                icon_label.setPixmap(icon_pixmap)
            icon_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            icon_name_layout.addWidget(icon_label)
            # Name (smaller font, vertically centered)
            name_label = QLabel(os.path.basename(file_path))
            name_label.setStyleSheet('font-size: 13pt; font-weight: bold; margin-left: 10px;')
            name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            icon_name_layout.addWidget(name_label)
            icon_name_layout.addStretch()
            general_layout.addLayout(icon_name_layout)
            # Info fields
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            form.setContentsMargins(0, 8, 0, 0)
            # Type
            form.addRow('<b>Type:</b>', QLabel('Folder' if os.path.isdir(file_path) else 'File'))
            # Size
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)
                form.addRow('<b>Size:</b>', QLabel(f'{size} bytes ({self.human_readable_size(size)})'))
            elif os.path.isdir(file_path):
                size = self.get_folder_size(file_path)
                form.addRow('<b>Size:</b>', QLabel(f'{size} bytes ({self.human_readable_size(size)})'))
            # Location
            form.addRow('<b>Location:</b>', QLabel(os.path.dirname(file_path)))
            # Times
            if stat_result:
                import time
                form.addRow('<b>Created:</b>', QLabel(time.ctime(stat_result.st_ctime)))
                form.addRow('<b>Modified:</b>', QLabel(time.ctime(stat_result.st_mtime)))
                form.addRow('<b>Accessed:</b>', QLabel(time.ctime(stat_result.st_atime)))
            # Permissions string
            if stat_result:
                import stat
                perms = stat.filemode(stat_result.st_mode)
                form.addRow('<b>Permissions:</b>', QLabel(perms))
            general_layout.addLayout(form)
            general_layout.addStretch()
            general_widget.setLayout(general_layout)
            # Make General tab scrollable
            general_scroll = QScrollArea()
            general_scroll.setWidgetResizable(True)
            general_scroll.setWidget(general_widget)
            # Permissions tab (modern QTableWidget)
            perm_widget = QWidget()
            perm_layout = QVBoxLayout()
            perm_layout.setContentsMargins(10, 10, 10, 10)
            owner = group = '-'
            if stat_result:
                if platform.system() != 'Windows':
                    import pwd, grp
                    owner = pwd.getpwuid(stat_result.st_uid).pw_name
                    group = grp.getgrgid(stat_result.st_gid).gr_name
            owner_group_label = QLabel(f'<b>Owner:</b> {owner}   <b>Group:</b> {group}')
            owner_group_label.setStyleSheet('font-size: 10pt; margin: 0 0 4px 0;')
            perm_layout.addWidget(owner_group_label)
            # Modern table
            table = QTableWidget(3, 3)
            table.setHorizontalHeaderLabels(['Read', 'Write', 'Execute'])
            table.setVerticalHeaderLabels(['User', 'Group', 'Other'])
            table.horizontalHeader().setStyleSheet('font-weight: bold; font-size: 10.5pt; background: #333; color: #fff; border: none;')
            table.verticalHeader().setStyleSheet('font-weight: bold; font-size: 10.5pt; background: #333; color: #fff; border: none;')
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionMode(QTableWidget.NoSelection)
            table.setShowGrid(False)
            table.setStyleSheet('QTableWidget { background: #232323; color: #fff; border: none; } QTableWidget::item { color: #fff; } QHeaderView::section { background: #333; color: #fff; font-weight: bold; font-size: 10.5pt; border: none; }')
            if stat_result:
                import stat
                mode = stat_result.st_mode
                for row, (read, write, exec_) in enumerate([
                    (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
                    (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
                    (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH)
                ]):
                    for col, flag in enumerate([read, write, exec_]):
                        item = QTableWidgetItem('✔' if mode & flag else '')
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        table.setItem(row, col, item)
            table.resizeColumnsToContents()
            table.resizeRowsToContents()
            table.setMinimumHeight(90)
            table.setMinimumWidth(220)
            perm_layout.addWidget(table)
            perm_widget.setLayout(perm_layout)
            perm_scroll = QScrollArea()
            perm_scroll.setWidgetResizable(True)
            perm_scroll.setWidget(perm_widget)
            # MIME/Type tab
            mime_widget = QWidget()
            mime_form = QFormLayout()
            mime_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            mime_type, encoding = mimetypes.guess_type(file_path)
            mime_form.addRow('<b>MIME type:</b>', QLabel(mime_type or '-'))
            mime_form.addRow('<b>Extension:</b>', QLabel(os.path.splitext(file_path)[1] or '-'))
            # Application association (best effort)
            if platform.system() == 'Windows':
                assoc = os.popen(f'ftype {os.path.splitext(file_path)[1][1:]}').read().strip()
            elif platform.system() == 'Darwin':
                assoc = os.popen(f'mdls -name kMDItemCFBundleIdentifier "{file_path}"').read().strip()
            else:
                assoc = os.popen(f'xdg-mime query default {mime_type or "application/octet-stream"}').read().strip()
            mime_form.addRow('<b>Associated app:</b>', QLabel(assoc or '-'))
            mime_widget.setLayout(mime_form)
            mime_scroll = QScrollArea()
            mime_scroll.setWidgetResizable(True)
            mime_scroll.setWidget(mime_widget)
            # Attributes tab
            attr_widget = QWidget()
            attr_form = QFormLayout()
            attr_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            # Hidden, system, read-only, executable
            is_hidden = os.path.basename(file_path).startswith('.') or (platform.system() == 'Windows' and hasattr(os, 'stat') and hasattr(stat_result, 'st_file_attributes') and stat_result.st_file_attributes & 2)
            attr_form.addRow('<b>Hidden:</b>', QLabel('Yes' if is_hidden else 'No'))
            attr_form.addRow('<b>Read-only:</b>', QLabel('No' if os.access(file_path, os.W_OK) else 'Yes'))
            attr_form.addRow('<b>Executable:</b>', QLabel('Yes' if os.access(file_path, os.X_OK) else 'No'))
            attr_widget.setLayout(attr_form)
            attr_scroll = QScrollArea()
            attr_scroll.setWidgetResizable(True)
            attr_scroll.setWidget(attr_widget)
            # Advanced tab (as before, plus symlink target)
            advanced_info = ""
            if stat_result:
                advanced_info += f'<b>Inode:</b> {getattr(stat_result, "st_ino", "-")}<br>'
                advanced_info += f'<b>Device:</b> {getattr(stat_result, "st_dev", "-")}<br>'
                advanced_info += f'<b>Hard Links:</b> {getattr(stat_result, "st_nlink", "-")}<br>'
                if os.path.islink(file_path):
                    advanced_info += f'<b>Symlink target:</b> {os.readlink(file_path)}<br>'
                for field in dir(stat_result):
                    if field.startswith('st_'):
                        advanced_info += f'<b>{field}:</b> {getattr(stat_result, field)}<br>'
            adv_label = QLabel()
            adv_label.setTextFormat(Qt.TextFormat.RichText)
            adv_label.setText(advanced_info)
            adv_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            adv_scroll = QScrollArea()
            adv_scroll.setWidgetResizable(True)
            adv_scroll.setWidget(adv_label)
            # Preview tab (as before)
            preview_widget = None
            ext = os.path.splitext(file_path)[1].lower()
            if os.path.isfile(file_path):
                if ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp']:
                    from PySide6.QtGui import QPixmap
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        label = QLabel()
                        label.setPixmap(pixmap.scaledToWidth(350, Qt.TransformationMode.SmoothTransformation))
                        scroll = QScrollArea()
                        scroll.setWidget(label)
                        preview_widget = scroll
                elif ext in ['.txt', '.md', '.py', '.json', '.ini', '.log', '.csv', '.xml', '.html', '.js', '.css']:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            text = f.read(4096)
                        textedit = QTextEdit()
                        textedit.setReadOnly(True)
                        textedit.setPlainText(text)
                        preview_widget = textedit
                    except Exception:
                        pass
            # Build dialog
            dlg = QDialog(self)
            dlg.setWindowTitle('Properties')
            dlg.setMinimumSize(350, 400)
            layout = QVBoxLayout()
            tabs = QTabWidget()
            tabs.addTab(general_scroll, 'General')
            tabs.addTab(perm_scroll, 'Permissions')
            tabs.addTab(mime_scroll, 'MIME/Type')
            tabs.addTab(attr_scroll, 'Attributes')
            tabs.addTab(adv_scroll, 'Advanced')
            if preview_widget:
                tabs.addTab(preview_widget, 'Preview')
            layout.addWidget(tabs)
            btns = QDialogButtonBox(QDialogButtonBox.Ok)
            btns.accepted.connect(dlg.accept)
            layout.addWidget(btns)
            dlg.setLayout(layout)
            dlg.exec()
        # --- Multi-selection ---
        else:
            total_size = 0
            file_count = 0
            folder_count = 0
            for p in file_paths:
                if os.path.isfile(p):
                    total_size += os.path.getsize(p)
                    file_count += 1
                elif os.path.isdir(p):
                    total_size += self.get_folder_size(p)
                    folder_count += 1
            general_widget = QWidget()
            general_layout = QFormLayout()
            general_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            general_layout.addRow('<b>Selected items:</b>', QLabel(str(len(file_paths))))
            general_layout.addRow('<b>Files:</b>', QLabel(str(file_count)))
            general_layout.addRow('<b>Folders:</b>', QLabel(str(folder_count)))
            general_layout.addRow('<b>Total size:</b>', QLabel(f'{total_size} bytes ({self.human_readable_size(total_size)})'))
            general_widget.setLayout(general_layout)
            general_scroll = QScrollArea()
            general_scroll.setWidgetResizable(True)
            general_scroll.setWidget(general_widget)
            # Advanced: just list all paths
            adv_label = QLabel()
            adv_label.setTextFormat(Qt.TextFormat.RichText)
            adv_label.setText('<b>Paths:</b><br>' + '<br>'.join(file_paths))
            adv_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            adv_scroll = QScrollArea()
            adv_scroll.setWidgetResizable(True)
            adv_scroll.setWidget(adv_label)
            # Build dialog
            dlg = QDialog(self)
            dlg.setWindowTitle('Properties')
            dlg.setMinimumSize(350, 400)
            layout = QVBoxLayout()
            tabs = QTabWidget()
            tabs.addTab(general_scroll, 'General')
            tabs.addTab(adv_scroll, 'Advanced')
            layout.addWidget(tabs)
            btns = QDialogButtonBox(QDialogButtonBox.Ok)
            btns.accepted.connect(dlg.accept)
            layout.addWidget(btns)
            dlg.setLayout(layout)
            dlg.exec()

    def copy_path(self, file_path):
        QApplication.clipboard().setText(file_path)
        QMessageBox.information(self, 'Copy Path', 'Path copied to clipboard.')

    def new_folder(self, folder_path):
        name, ok = QInputDialog.getText(self, 'New Folder', 'Enter folder name:')
        if ok and name:
            new_path = os.path.join(folder_path, name)
            try:
                os.makedirs(new_path)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, 'New Folder', f'Could not create folder: {e}')

    def is_video_file(self, file_path):
        video_exts = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
        ext = os.path.splitext(file_path)[1].lower()
        return ext in video_exts

    def peek_video(self, file_path):
        dlg = VideoPeekDialog(file_path, self)
        dlg.exec()

    def go_to_desktop(self):
        self.set_path(r'C:/Users/fmjje/OneDrive/Desktop')

    def favorite_current_path(self):
        path = self.address_bar.text()
        if hasattr(self.sidebar, 'add_to_favorites'):
            self.sidebar.add_to_favorites(path)
            QMessageBox.information(self, 'Favorites', f'Added to Favorites: {path}')

    def on_search(self):
        query = self.search_bar.text().strip()
        recursive = self.recursive_checkbox.isChecked()
        if not query:
            return
        # Start search worker
        self.clear_search_btn.setVisible(True)
        self.address_stack.setCurrentWidget(self.progress_bar)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_ring.setVisible(True)
        self.progress_ring.setText('Searching...')
        self.search_results = []
        self.search_worker = SearchWorker(self.address_bar.text(), query, recursive)
        self.search_worker.progress.connect(self.on_search_progress)
        self.search_worker.found.connect(self.on_search_found)
        self.search_worker.started.connect(lambda: self.progress_ring.setText('Searching...'))
        self.search_worker.finished.connect(self.on_search_finished)
        self.search_worker.start()

    def on_search_progress(self, value):
        self.progress_bar.setValue(value)

    def on_search_found(self, results):
        self.search_results = results
        query = self.search_bar.text().strip()
        from PySide6.QtCore import QAbstractListModel, QModelIndex
        class SearchResultsModel(QAbstractListModel):
            def __init__(self, results, message=None):
                super().__init__()
                self.results = results
                self.message = message
            def rowCount(self, parent=QModelIndex()):
                return max(1, len(self.results))
            def data(self, index, role):
                if role == Qt.DisplayRole:
                    if self.results:
                        return self.results[index.row()]
                    elif self.message:
                        return self.message
                    else:
                        return 'No results.'
        if results:
            model = SearchResultsModel(results)
            self.file_view.setModel(model)
            # Install event filter for middle-click
            self.file_view.viewport().installEventFilter(self)
            self._search_results_model = model
            self._search_results_paths = results
        else:
            # No exact matches, try fuzzy search
            self.file_view.setModel(SearchResultsModel([], f"No results found for '{query}'. Trying similar names..."))
            QApplication.processEvents()
            # Gather all files/folders in search scope
            all_names = []
            for dirpath, dirnames, filenames in os.walk(self.address_bar.text()):
                for d in dirnames:
                    all_names.append(os.path.join(dirpath, d))
                for f in filenames:
                    all_names.append(os.path.join(dirpath, f))
                if not self.recursive_checkbox.isChecked():
                    break
            # Use difflib to find close matches
            base_query = os.path.basename(query).lower()
            similar = [p for p in all_names if difflib.get_close_matches(base_query, [os.path.basename(p).lower()], n=1, cutoff=0.6)]
            if similar:
                model = SearchResultsModel(similar, f"Showing similar results for '{query}'.")
                self.file_view.setModel(model)
                self.file_view.viewport().installEventFilter(self)
                self._search_results_model = model
                self._search_results_paths = similar
            else:
                self.file_view.setModel(SearchResultsModel([], "We couldn't find anything matching your search."))
                self.file_view.viewport().removeEventFilter(self)
                self._search_results_model = None
                self._search_results_paths = None

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent
        if obj == self.file_view.viewport() and event.type() == QEvent.MouseButtonPress:
            mouse_event = event
            if mouse_event.button() == Qt.MiddleButton:
                index = self.file_view.indexAt(mouse_event.pos())
                if index.isValid() and hasattr(self, '_search_results_paths') and self._search_results_paths:
                    path = self._search_results_paths[index.row()]
                    parent_dir = os.path.dirname(path)
                    # Restore normal file view for parent_dir
                    self.file_view.setModel(self.model)
                    self.set_path(parent_dir)
                    # Select the file/folder in the new view
                    model = self.model
                    for row in range(model.rowCount(model.index(parent_dir))):
                        idx = model.index(row, 0, model.index(parent_dir))
                        if model.filePath(idx) == path:
                            self.file_view.setCurrentIndex(idx)
                            break
                    # Remove event filter since we're back to normal view
                    self.file_view.viewport().removeEventFilter(self)
                    self._search_results_model = None
                    self._search_results_paths = None
                    return True
        return super().eventFilter(obj, event)

    def on_search_finished(self):
        self.progress_bar.setVisible(False)
        self.progress_ring.setVisible(False)
        self.address_stack.setCurrentWidget(self.address_bar)

    def on_clear_search(self):
        self.search_bar.clear()
        self.clear_search_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_ring.setVisible(False)
        self.address_stack.setCurrentWidget(self.address_bar)
        # Restore normal file view
        self.file_view.setModel(self.model)
        self.set_path(self.address_bar.text())
        # Remove event filter if present
        self.file_view.viewport().removeEventFilter(self)
        self._search_results_model = None
        self._search_results_paths = None

    def file_view_dropEvent(self, event):
        # Custom drop event to move/copy files/folders
        index = self.file_view.indexAt(event.position().toPoint()) if hasattr(event, 'position') else self.file_view.indexAt(event.pos())
        if not index.isValid():
            event.ignore()
            return
        model = self.file_view.model()
        target_path = model.filePath(index)
        if not os.path.isdir(target_path):
            target_path = os.path.dirname(target_path)
        mime = event.mimeData()
        if mime.hasUrls():
            paths = [url.toLocalFile() for url in mime.urls()]
        else:
            event.ignore()
            return
        # Determine operation: copy (default), move if Ctrl is held
        from PySide6.QtCore import Qt
        modifiers = event.keyboardModifiers() if hasattr(event, 'keyboardModifiers') else Qt.NoModifier
        if modifiers & Qt.ControlModifier:
            op = 'move'
            drop_action = Qt.MoveAction
        else:
            op = 'copy'
            drop_action = Qt.CopyAction
        # Confirm operation
        reply = QMessageBox.question(self, op.capitalize(), f'{op.capitalize()} {len(paths)} item(s) to {target_path}?', QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            event.ignore()
            return
        import shutil
        for src in paths:
            if src == target_path or os.path.dirname(src) == target_path:
                continue  # Don't move/copy into itself or same folder
            dst = os.path.join(target_path, os.path.basename(src))
            try:
                if op == 'move':
                    shutil.move(src, dst)
                else:
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
            except Exception as e:
                QMessageBox.warning(self, op.capitalize(), f'Could not {op} {src}: {e}')
        self.refresh()
        event.setDropAction(drop_action)
        event.accept()

    def is_supported_archive(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.iso', '.cab', '.lzma', '.zst', '.arj', '.ace', '.tar.lzma', '.tar.zst']:
            if ext == '.7z' and not HAS_PY7ZR:
                return False
            if ext == '.rar' and not HAS_RAR:
                return False
            if ext == '.iso' and not HAS_ISO:
                return False
            return True
        return False

    def compress_items(self, paths):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QComboBox, QDialogButtonBox, QLabel, QCheckBox, QSpinBox, QHBoxLayout, QFileDialog
        import shutil
        import fnmatch
        dlg = QDialog(self)
        dlg.setWindowTitle('Compress')
        layout = QVBoxLayout()
        layout.addWidget(QLabel('Archive name:'))
        name_edit = QLineEdit()
        if len(paths) == 1:
            name_edit.setText(os.path.basename(paths[0]) + '.zip')
        else:
            name_edit.setText('archive.zip')
        layout.addWidget(name_edit)
        layout.addWidget(QLabel('Format:'))
        format_combo = QComboBox()
        format_combo.addItem('ZIP (.zip)')
        format_combo.addItem('TAR (.tar)')
        format_combo.addItem('TAR.GZ (.tar.gz)')
        format_combo.addItem('TAR.BZ2 (.tar.bz2)')
        format_combo.addItem('TAR.XZ (.tar.xz)')
        if HAS_PY7ZR:
            format_combo.addItem('7z (.7z)')
        format_combo.addItem('GZ (.gz)')
        format_combo.addItem('BZ2 (.bz2)')
        format_combo.addItem('XZ (.xz)')
        if HAS_RAR:
            format_combo.addItem('RAR (.rar)')
        if HAS_ISO:
            format_combo.addItem('ISO (.iso)')
        layout.addWidget(format_combo)
        # Compression level
        layout.addWidget(QLabel('Compression level:'))
        level_combo = QComboBox()
        level_combo.addItems(['Store (no compression)', 'Fast', 'Normal', 'Best'])
        layout.addWidget(level_combo)
        # Password
        password_box = QLineEdit()
        password_box.setPlaceholderText('Password (optional)')
        password_box.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(password_box)
        # Split archive
        split_layout = QHBoxLayout()
        split_checkbox = QCheckBox('Split archive (MB):')
        split_size = QSpinBox()
        split_size.setRange(1, 10000)
        split_size.setValue(100)
        split_size.setEnabled(False)
        split_checkbox.toggled.connect(split_size.setEnabled)
        split_layout.addWidget(split_checkbox)
        split_layout.addWidget(split_size)
        layout.addLayout(split_layout)
        # Exclude patterns
        layout.addWidget(QLabel('Exclude patterns (comma separated, e.g. *.tmp,*.log):'))
        exclude_edit = QLineEdit()
        layout.addWidget(exclude_edit)
        # Add to existing
        add_to_existing = QCheckBox('Add to existing archive (if exists)')
        layout.addWidget(add_to_existing)
        # Archive comment
        layout.addWidget(QLabel('Archive comment:'))
        comment_edit = QLineEdit()
        layout.addWidget(comment_edit)
        # Store full paths
        store_full_paths = QCheckBox('Store full paths (not just file names)')
        store_full_paths.setChecked(True)
        layout.addWidget(store_full_paths)
        # Encrypt file names (if supported)
        encrypt_names = QCheckBox('Encrypt file names (7z only)')
        encrypt_names.setEnabled(False)
        if HAS_PY7ZR:
            encrypt_names.setEnabled(True)
        layout.addWidget(encrypt_names)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        dlg.setLayout(layout)
        if dlg.exec() != QDialog.Accepted:
            return
        archive_name = name_edit.text().strip()
        fmt = format_combo.currentText()
        level = level_combo.currentText()
        password = password_box.text()
        split = split_checkbox.isChecked()
        split_mb = split_size.value() if split else None
        exclude_patterns = [p.strip() for p in exclude_edit.text().split(',') if p.strip()]
        add_existing = add_to_existing.isChecked()
        comment = comment_edit.text().strip()
        store_paths = store_full_paths.isChecked()
        encrypt = encrypt_names.isChecked()
        # Actual compression logic
        try:
            ext = os.path.splitext(archive_name)[1].lower()
            if fmt.startswith('ZIP'):
                compression = zipfile.ZIP_DEFLATED if level != 'Store (no compression)' else zipfile.ZIP_STORED
                with zipfile.ZipFile(archive_name, 'a' if add_existing and os.path.exists(archive_name) else 'w', compression) as zf:
                    if comment:
                        zf.comment = comment.encode('utf-8')
                    for path in paths:
                        if os.path.isdir(path):
                            for root, dirs, files in os.walk(path):
                                for file in files:
                                    full_path = os.path.join(root, file)
                                    rel_path = os.path.relpath(full_path, os.path.dirname(path)) if store_paths else file
                                    if any(fnmatch.fnmatch(full_path, pat) for pat in exclude_patterns):
                                        continue
                                    zf.write(full_path, rel_path)
                        else:
                            if any(fnmatch.fnmatch(path, pat) for pat in exclude_patterns):
                                continue
                            arcname = os.path.basename(path) if not store_paths else os.path.relpath(path, os.path.dirname(paths[0]))
                            zf.write(path, arcname)
                QMessageBox.information(self, 'Compress', f'Created ZIP archive: {archive_name}')
            elif fmt.startswith('TAR'):
                mode = 'w'
                if fmt == 'TAR (.tar)':
                    mode = 'w'
                elif fmt == 'TAR.GZ (.tar.gz)':
                    mode = 'w:gz'
                elif fmt == 'TAR.BZ2 (.tar.bz2)':
                    mode = 'w:bz2'
                elif fmt == 'TAR.XZ (.tar.xz)':
                    mode = 'w:xz'
                with tarfile.open(archive_name, mode) as tf:
                    for path in paths:
                        if os.path.isdir(path):
                            tf.add(path, arcname=os.path.basename(path) if not store_paths else path, filter=lambda x: None if any(fnmatch.fnmatch(x.name, pat) for pat in exclude_patterns) else x)
                        else:
                            if any(fnmatch.fnmatch(path, pat) for pat in exclude_patterns):
                                continue
                            arcname = os.path.basename(path) if not store_paths else path
                            tf.add(path, arcname=arcname)
                QMessageBox.information(self, 'Compress', f'Created TAR archive: {archive_name}')
            elif fmt.startswith('7z') and HAS_PY7ZR:
                filters = {}
                if level == 'Store (no compression)':
                    filters['compression'] = 'copy'
                elif level == 'Fast':
                    filters['compression'] = 'fast'
                elif level == 'Normal':
                    filters['compression'] = 'normal'
                elif level == 'Best':
                    filters['compression'] = 'ultra'
                with py7zr.SevenZipFile(archive_name, 'w', password=password if password else None, filters=filters, encrypt_header=encrypt) as zf:
                    for path in paths:
                        if os.path.isdir(path):
                            zf.writeall(path, arcname=os.path.basename(path) if not store_paths else path)
                        else:
                            zf.write(path, arcname=os.path.basename(path) if not store_paths else path)
                QMessageBox.information(self, 'Compress', f'Created 7z archive: {archive_name}')
            elif fmt.startswith('GZ'):
                import gzip
                if len(paths) == 1 and os.path.isfile(paths[0]):
                    with open(paths[0], 'rb') as f_in, gzip.open(archive_name, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    QMessageBox.information(self, 'Compress', f'Created GZ archive: {archive_name}')
                else:
                    QMessageBox.warning(self, 'Compress', 'GZ only supports single files.')
            elif fmt.startswith('BZ2'):
                import bz2
                if len(paths) == 1 and os.path.isfile(paths[0]):
                    with open(paths[0], 'rb') as f_in, bz2.open(archive_name, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    QMessageBox.information(self, 'Compress', f'Created BZ2 archive: {archive_name}')
                else:
                    QMessageBox.warning(self, 'Compress', 'BZ2 only supports single files.')
            elif fmt.startswith('XZ'):
                import lzma
                if len(paths) == 1 and os.path.isfile(paths[0]):
                    with open(paths[0], 'rb') as f_in, lzma.open(archive_name, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    QMessageBox.information(self, 'Compress', f'Created XZ archive: {archive_name}')
                else:
                    QMessageBox.warning(self, 'Compress', 'XZ only supports single files.')
            elif fmt.startswith('RAR') and HAS_RAR:
                with rarfile.RarFile(archive_name, 'w') as rf:
                    for path in paths:
                        rf.write(path)
                QMessageBox.information(self, 'Compress', f'Created RAR archive: {archive_name}')
            elif fmt.startswith('ISO') and HAS_ISO:
                with pycdlib.PyCdlib() as iso:
                    iso.open(archive_name)
                    # Extract all files (stub: just show message)
                    QMessageBox.information(self, 'Compress', f'ISO compression not fully implemented.')
            else:
                QMessageBox.warning(self, 'Compress', 'Unsupported format or missing library.')
        except Exception as e:
            QMessageBox.critical(self, 'Compress', f'Error: {e}')

    def extract_item(self, archive_path, dest_dir):
        from PySide6.QtWidgets import QInputDialog, QFileDialog
        import fnmatch
        password = None
        ext = os.path.splitext(archive_path)[1].lower()
        # Ask for password if needed (always ask for now, can improve detection later)
        if ext in ['.zip', '.7z', '.rar', '.iso']:
            password, ok = QInputDialog.getText(self, 'Extract', 'Password (leave blank if none):', QLineEdit.EchoMode.Password)
            if not ok:
                return
            if not password:
                password = None
        # Ask for destination
        dest_dir = QFileDialog.getExistingDirectory(self, 'Extract to...', dest_dir)
        if not dest_dir:
            return
        try:
            if ext == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    if password:
                        zf.setpassword(password.encode('utf-8'))
                    zf.extractall(dest_dir)
                QMessageBox.information(self, 'Extract', f'Extracted ZIP archive to {dest_dir}')
            elif ext == '.tar':
                with tarfile.open(archive_path, 'r') as tf:
                    tf.extractall(dest_dir)
                QMessageBox.information(self, 'Extract', f'Extracted TAR archive to {dest_dir}')
            elif ext == '.gz':
                with gzip.open(archive_path, 'rb') as f_in, open(os.path.join(dest_dir, os.path.basename(archive_path)), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                QMessageBox.information(self, 'Extract', f'Extracted GZ archive to {dest_dir}')
            elif ext == '.bz2':
                with bz2.open(archive_path, 'rb') as f_in, open(os.path.join(dest_dir, os.path.basename(archive_path)), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                QMessageBox.information(self, 'Extract', f'Extracted BZ2 archive to {dest_dir}')
            elif ext == '.xz':
                with lzma.open(archive_path, 'rb') as f_in, open(os.path.join(dest_dir, os.path.basename(archive_path)), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                QMessageBox.information(self, 'Extract', f'Extracted XZ archive to {dest_dir}')
            elif ext == '.rar' and HAS_RAR:
                with rarfile.RarFile(archive_path) as rf:
                    rf.extractall(dest_dir, pwd=password if password else None)
                QMessageBox.information(self, 'Extract', f'Extracted RAR archive to {dest_dir}')
            elif ext == '.iso' and HAS_ISO:
                with pycdlib.PyCdlib() as iso:
                    iso.open(archive_path)
                    # Extract all files (stub: just show message)
                    QMessageBox.information(self, 'Extract', f'ISO extraction not fully implemented.')
            else:
                QMessageBox.warning(self, 'Extract', 'Unsupported archive format or missing library.')
        except Exception as e:
            QMessageBox.critical(self, 'Extract', f'Error: {e}')

    def on_directory_changed(self, path):
        # Refresh file view when directory changes
        self.refresh()
        self.show_notification(f'Directory changed: {path}', 2000)

    def on_file_changed(self, path):
        # Refresh file view when a file changes (optional, for watched files)
        self.refresh()
        self.show_notification(f'File changed: {path}', 2000)

    def show_notification(self, message, duration=2000):
        popup = NotificationPopup(self, message, duration)
        popup.show()

    def show_about_dialog(self):
        dlg = AboutDialog(self)
        dlg.exec()

def set_dark_palette(app):
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)

def set_light_palette(app):
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    app.setPalette(palette)

def detect_system_theme():
    import sys
    # Windows
    if sys.platform.startswith('win'):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize') as key:
                value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
                return 'light' if value == 1 else 'dark'
        except Exception:
            return 'light'
    # macOS
    elif sys.platform.startswith('darwin'):
        try:
            import subprocess
            result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'], capture_output=True, text=True)
            if 'Dark' in result.stdout:
                return 'dark'
            else:
                return 'light'
        except Exception:
            return 'light'
    # Linux (try GTK theme, fallback to light)
    else:
        try:
            import subprocess
            # Try gsettings (GNOME)
            result = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'], capture_output=True, text=True)
            if 'dark' in result.stdout.lower():
                return 'dark'
        except Exception:
            pass
        try:
            # Try KDE
            kdeglobals = os.path.expanduser('~/.config/kdeglobals')
            if os.path.exists(kdeglobals):
                with open(kdeglobals, 'r') as f:
                    if 'ColorScheme=Dark' in f.read():
                        return 'dark'
        except Exception:
            pass
        return 'light'

class SearchWorker(QThread):
    progress = Signal(int)
    found = Signal(list)
    started = Signal()
    finished = Signal()

    def __init__(self, root_path, query, recursive=True):
        super().__init__()
        self.root_path = root_path
        self.query = query.lower()
        self.recursive = recursive
        self._is_running = True

    def run(self):
        self.started.emit()
        results = []
        total = 0
        matches = 0
        # Count total files/folders for progress
        for dirpath, dirnames, filenames in os.walk(self.root_path):
            total += len(dirnames) + len(filenames)
            if not self.recursive:
                break
        if total == 0:
            total = 1
        processed = 0
        for dirpath, dirnames, filenames in os.walk(self.root_path):
            # Search folders
            for d in dirnames:
                if not self._is_running:
                    self.finished.emit()
                    return
                processed += 1
                if self.query in d.lower():
                    results.append(os.path.join(dirpath, d))
                self.progress.emit(int(processed * 100 / total))
            # Search files
            for f in filenames:
                if not self._is_running:
                    self.finished.emit()
                    return
                processed += 1
                if self.query in f.lower():
                    results.append(os.path.join(dirpath, f))
                self.progress.emit(int(processed * 100 / total))
            if not self.recursive:
                break
        self.found.emit(results)
        self.finished.emit()

    def stop(self):
        self._is_running = False

# --- Recent Files/History ---
import collections
RECENT_FILE = os.path.join(os.path.dirname(__file__), 'recent.json')
MAX_RECENT = 20

def add_recent(path):
    recent_file = os.path.join(os.path.dirname(__file__), 'recent.json')
    try:
        if os.path.exists(recent_file):
            with open(recent_file, 'r', encoding='utf-8') as f:
                recent = json.load(f)
        else:
            recent = []
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        recent = [p for p in recent if os.path.exists(p)]
        while len(recent) > 100:
            recent.pop()
        with open(recent_file, 'w', encoding='utf-8') as f:
            json.dump(recent, f)
    except Exception:
        pass

def get_recent(limit=None):
    recent_file = os.path.join(os.path.dirname(__file__), 'recent.json')
    try:
        with open(recent_file, 'r', encoding='utf-8') as f:
            recent = json.load(f)
        recent = [p for p in recent if os.path.exists(p)]
        if limit:
            return recent[:limit]
        return recent
    except Exception:
        return []

class DeleteWorker(QThread):
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)
    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths
        self._is_interrupted = False
    def run(self):
        total = len(self.file_paths)
        for i, file_path in enumerate(self.file_paths):
            if self._is_interrupted:
                break
            try:
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
            except Exception as e:
                self.error.emit(f'Could not delete {file_path}: {e}')
            self.progress.emit(int((i+1)/total*100))
        self.finished.emit()
    def interrupt(self):
        self._is_interrupted = True

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    theme = detect_system_theme()
    if theme == 'dark':
        set_dark_palette(app)
    else:
        set_light_palette(app)
    window = FileManager()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 