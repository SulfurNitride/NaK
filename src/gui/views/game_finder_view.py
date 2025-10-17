"""
Game Finder view for displaying detected games
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QMessageBox, QFrame,
    QDialog, QTextEdit, QScrollArea, QGroupBox,
    QLineEdit, QCheckBox, QListWidget, QListWidgetItem,
    QApplication, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from src.utils.game_finder import GameFinder, GameInfo
from src.utils.prefix_locator import PrefixLocator, PrefixInfo
from typing import List


class GameFinderThread(QThread):
    """Thread for running game detection in background"""
    games_found = Signal(list)
    progress_update = Signal(str)
    finished_signal = Signal()

    def run(self):
        """Run game detection"""
        self.progress_update.emit("Initializing GameFinder...")

        try:
            finder = GameFinder()
            self.progress_update.emit("Searching for games...")

            games = finder.find_all_games()
            self.games_found.emit(games)

        except Exception as e:
            logging.getLogger(__name__).error(f"Game detection failed: {e}")
            self.games_found.emit([])

        self.finished_signal.emit()


class GameFinderView(QWidget):
    """View for displaying game detection results"""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.logger = logging.getLogger(__name__)
        self.finder_thread = None
        self.games_list: List[GameInfo] = []

        self._create_widgets()
        self.logger.info("Game finder view created")

    def _create_widgets(self):
        """Create the game finder widgets"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        # Header section
        header_layout = QHBoxLayout()

        # Title
        title_label = QLabel("Simple Game Modding")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #66bb6a; margin-bottom: 10px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Action buttons in header
        # Rescan button (initially hidden, shown after auto-scan)
        self.rescan_button = QPushButton("Rescan Games")
        self.rescan_button.setStyleSheet("""
            QPushButton {
                background-color: #66bb6a;
                border: 2px solid #555555;
                border-radius: 8px;
                padding: 10px 20px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                margin-right: 10px;
            }
            QPushButton:hover {
                background-color: #4caf50;
                border-color: #66bb6a;
            }
            QPushButton:pressed {
                background-color: #388e3c;
            }
        """)
        self.rescan_button.clicked.connect(self._start_game_scan)
        self.rescan_button.setVisible(False)  # Hidden initially
        header_layout.addWidget(self.rescan_button)

        # Dependencies button
        self.dependencies_button = QPushButton("Apply Dependencies")
        self.dependencies_button.setStyleSheet("""
            QPushButton {
                background-color: #9c27b0;
                border: 2px solid #555555;
                border-radius: 8px;
                padding: 10px 20px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                margin-right: 10px;
            }
            QPushButton:hover {
                background-color: #7b1fa2;
                border-color: #9c27b0;
            }
            QPushButton:pressed {
                background-color: #4a148c;
            }
            QPushButton:disabled {
                background-color: #424242;
                color: #888888;
            }
        """)
        self.dependencies_button.clicked.connect(self._apply_dependencies)
        self.dependencies_button.setEnabled(False)  # Disabled until games are found
        header_layout.addWidget(self.dependencies_button)

        main_layout.addLayout(header_layout)

        # Description
        desc_text = """Simple game modding without MO2! Apply dependencies, registry edits, and fixes directly to your game prefixes. Perfect for ReShade, OptiScaler, ENB, and other mods.

Automatically detects games from Steam, Heroic, and non-Steam sources. Your games will be scanned automatically."""

        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #b0bec5; font-size: 14px; margin-bottom: 20px;")
        main_layout.addWidget(desc_label)


        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555555;
                border-radius: 8px;
                background-color: #2d2d2d;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #66bb6a;
                border-radius: 6px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #b0bec5; font-size: 12px;")
        self.status_label.setVisible(False)
        main_layout.addWidget(self.status_label)

        # Results table
        self.games_table = QTableWidget()
        self.games_table.setColumnCount(4)
        self.games_table.setHorizontalHeaderLabels(["Game Name", "Platform", "Install Path", "App ID"])

        # Style the table
        self.games_table.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                border: 2px solid #555555;
                border-radius: 8px;
                color: #ffffff;
                selection-background-color: #4fc3f7;
                gridline-color: #555555;
            }
            QHeaderView::section {
                background-color: #424242;
                color: #ffffff;
                padding: 8px;
                border: 1px solid #555555;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #555555;
            }
            QTableWidget::item:selected {
                background-color: #4fc3f7;
            }
        """)

        # Configure table
        header = self.games_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Game Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Platform
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Path
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # App ID

        self.games_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.games_table.setAlternatingRowColors(True)

        main_layout.addWidget(self.games_table)

        # Results summary
        self.results_label = QLabel("Click 'Scan for Games' to detect installed games")
        self.results_label.setStyleSheet("color: #b0bec5; font-size: 14px; font-weight: bold;")
        self.results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.results_label)

    def _start_game_scan(self):
        """Start the game scanning process"""
        if self.finder_thread and self.finder_thread.isRunning():
            return

        self.logger.info("Starting game scan")

        # Update UI for scanning
        self.rescan_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setVisible(True)
        self.status_label.setText("Preparing to scan...")
        self.results_label.setText("Scanning for games...")

        # Clear existing results
        self.games_table.setRowCount(0)
        self.games_list.clear()

        # Start background thread
        self.finder_thread = GameFinderThread()
        self.finder_thread.games_found.connect(self._on_games_found)
        self.finder_thread.progress_update.connect(self._on_progress_update)
        self.finder_thread.finished_signal.connect(self._on_scan_finished)
        self.finder_thread.start()

    def _on_progress_update(self, message: str):
        """Handle progress updates"""
        self.status_label.setText(message)

    def _on_games_found(self, games: List[GameInfo]):
        """Handle detected games"""
        self.games_list = games
        self._populate_games_table()

    def _populate_games_table(self):
        """Populate the games table with detected games"""
        self.games_table.setRowCount(len(self.games_list))

        for row, game in enumerate(self.games_list):
            # Game Name
            name_item = QTableWidgetItem(game.name)
            name_item.setToolTip(game.name)
            self.games_table.setItem(row, 0, name_item)

            # Platform
            platform_item = QTableWidgetItem(game.platform)
            self.games_table.setItem(row, 1, platform_item)

            # Install Path
            path_item = QTableWidgetItem(game.path)
            path_item.setToolTip(game.path)
            self.games_table.setItem(row, 2, path_item)

            # App ID
            app_id = game.app_id if game.app_id else "N/A"
            app_id_item = QTableWidgetItem(app_id)
            self.games_table.setItem(row, 3, app_id_item)

    def _on_scan_finished(self):
        """Handle scan completion"""
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        # Show and enable rescan button, enable dependencies button if games were found
        game_count = len(self.games_list)
        self.rescan_button.setVisible(True)
        self.rescan_button.setEnabled(True)
        self.dependencies_button.setEnabled(game_count > 0)

        # Update results summary
        if game_count == 0:
            self.results_label.setText("No games found. Make sure you have games installed from supported platforms.")
        elif game_count == 1:
            self.results_label.setText("Found 1 game")
        else:
            self.results_label.setText(f"Found {game_count} games")

        # Show summary by platform
        platform_counts = {}
        for game in self.games_list:
            platform_counts[game.platform] = platform_counts.get(game.platform, 0) + 1

        if platform_counts:
            platform_summary = ", ".join([f"{platform}: {count}" for platform, count in platform_counts.items()])
            self.results_label.setText(f"Found {game_count} games ({platform_summary})")

        self.logger.info(f"Game scan completed. Found {game_count} games")

    def _apply_dependencies(self):
        """Apply comprehensive dependencies to detected games"""
        if not self.games_list:
            QMessageBox.information(self, "No Games", "Please scan for games first.")
            return

        self.logger.info("Applying comprehensive dependencies to detected games")
        
        try:
            from utils.comprehensive_game_manager import ComprehensiveGameManager
            
            # Create comprehensive game manager
            game_manager = ComprehensiveGameManager()
            
            # Show game selection dialog
            dialog = GameDependenciesDialog(self.games_list, game_manager, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                QMessageBox.information(self, "Success", "Dependencies applied successfully!")
            
        except Exception as e:
            self.logger.error(f"Error applying dependencies: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply dependencies: {e}")

    def on_show(self):
        """Called when this view is shown"""
        self.logger.info("Simple Game Modding view shown")
        # Auto-scan for games when the view is first shown
        if not self.games_list:  # Only auto-scan if we haven't scanned yet
            self._start_game_scan()
        else:
            # If we already have games, just show the rescan button
            self.rescan_button.setVisible(True)


class PrefixLocationsDialog(QDialog):
    """Dialog for displaying Wine/Proton prefix locations with search functionality"""
    
    def __init__(self, game_prefixes: dict, system_prefixes: List[PrefixInfo], parent=None):
        super().__init__(parent)
        self.game_prefixes = game_prefixes
        self.system_prefixes = system_prefixes
        self.all_prefixes = list(game_prefixes.values()) + system_prefixes
        self.filtered_prefixes = self.all_prefixes.copy()
        self.logger = logging.getLogger(__name__)
        
        self.setWindowTitle("Wine/Proton Prefix Locations")
        self.setModal(True)
        self.resize(900, 700)
        
        self._create_widgets()
        
    def _create_widgets(self):
        """Create dialog widgets"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title_label = QLabel("Wine/Proton Prefix Locations")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #66bb6a; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel("Prefix locations for your detected games and all Wine/Proton prefixes on your system")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #b0bec5; font-size: 12px; margin-bottom: 15px;")
        layout.addWidget(desc_label)
        
        # Search and filter controls
        controls_layout = QHBoxLayout()
        
        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by game name, prefix type, or path...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #424242;
                border: 2px solid #555555;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #66bb6a;
            }
        """)
        self.search_box.textChanged.connect(self._filter_prefixes)
        controls_layout.addWidget(self.search_box)
        
        # Show only detected games checkbox
        self.show_detected_only = QCheckBox("Show only detected games")
        self.show_detected_only.setStyleSheet("""
            QCheckBox {
                color: #b0bec5;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #424242;
                border: 2px solid #555555;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #66bb6a;
                border: 2px solid #66bb6a;
                border-radius: 3px;
            }
        """)
        self.show_detected_only.toggled.connect(self._filter_prefixes)
        controls_layout.addWidget(self.show_detected_only)
        
        layout.addLayout(controls_layout)
        
        # Results count
        self.results_label = QLabel(f"Showing {len(self.filtered_prefixes)} prefixes")
        self.results_label.setStyleSheet("color: #b0bec5; font-size: 11px;")
        layout.addWidget(self.results_label)
        
        # Scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 2px solid #555555;
                border-radius: 8px;
                background-color: #2d2d2d;
            }
        """)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(10)
        
        self._populate_prefixes()
        
        self.scroll_layout.addStretch()
        scroll_area.setWidget(self.scroll_content)
        layout.addWidget(scroll_area)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                border: 2px solid #555555;
                border-radius: 8px;
                padding: 10px 30px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #616161;
                border-color: #757575;
            }
            QPushButton:pressed {
                background-color: #424242;
            }
        """)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
    
    def _filter_prefixes(self):
        """Filter prefixes based on search text and checkbox"""
        search_text = self.search_box.text().lower()
        show_detected_only = self.show_detected_only.isChecked()
        
        self.filtered_prefixes = []
        
        for prefix in self.all_prefixes:
            # Check if we should show only detected games
            if show_detected_only:
                if not hasattr(prefix, 'game_name') or prefix.game_name.startswith("Unknown Game"):
                    continue
            
            # Check search text
            if search_text:
                game_name = getattr(prefix, 'game_name', '').lower()
                prefix_type = prefix.prefix_type.lower()
                path_str = str(prefix.path).lower()
                
                if not (search_text in game_name or 
                       search_text in prefix_type or 
                       search_text in path_str):
                    continue
            
            self.filtered_prefixes.append(prefix)
        
        # Update results count
        self.results_label.setText(f"Showing {len(self.filtered_prefixes)} prefixes")
        
        # Repopulate the display
        self._populate_prefixes()
    
    def _populate_prefixes(self):
        """Populate the scroll area with filtered prefixes"""
        # Clear existing widgets
        for i in reversed(range(self.scroll_layout.count())):
            child = self.scroll_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        if not self.filtered_prefixes:
            no_results_label = QLabel("No prefixes match your search criteria.")
            no_results_label.setStyleSheet("color: #b0bec5; font-size: 14px; padding: 20px;")
            no_results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(no_results_label)
            return
        
        # Group prefixes by type
        prefixes_by_type = {}
        for prefix in self.filtered_prefixes:
            prefix_type = prefix.prefix_type.title()
            if prefix_type not in prefixes_by_type:
                prefixes_by_type[prefix_type] = []
            prefixes_by_type[prefix_type].append(prefix)
        
        # Create groups
        for prefix_type, prefixes in prefixes_by_type.items():
            group = QGroupBox(f"{prefix_type} Prefixes ({len(prefixes)})")
            group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    font-size: 14px;
                    color: #ffffff;
                    border: 2px solid #555555;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
            """)
            
            group_layout = QVBoxLayout(group)
            
            for prefix in prefixes:
                prefix_widget = self._create_prefix_widget(prefix)
                group_layout.addWidget(prefix_widget)
            
            self.scroll_layout.addWidget(group)
    
    def _create_prefix_widget(self, prefix_info: PrefixInfo) -> QWidget:
        """Create a widget for displaying prefix information"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.Box)
        widget.setStyleSheet("""
            QFrame {
                background-color: #424242;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)
        
        # Game name (prominent)
        game_name = getattr(prefix_info, 'game_name', 'Unknown Game')
        name_label = QLabel(f"{game_name}")
        name_label.setStyleSheet("color: #66bb6a; font-weight: bold; font-size: 14px;")
        layout.addWidget(name_label)
        
        # Prefix type and version
        type_text = f"Type: {prefix_info.prefix_type.title()}"
        if prefix_info.proton_version:
            type_text += f" ({prefix_info.proton_version})"
        elif prefix_info.wine_version:
            type_text += f" ({prefix_info.wine_version})"
        
        type_label = QLabel(type_text)
        type_label.setStyleSheet("color: #ff7043; font-weight: bold; font-size: 12px;")
        layout.addWidget(type_label)
        
        # Path
        path_label = QLabel(f"Path: {prefix_info.path}")
        path_label.setStyleSheet("color: #b0bec5; font-size: 11px; font-family: monospace;")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)
        
        # Apply regedit button
        apply_button = QPushButton("Apply Wine Registry Settings")
        apply_button.setStyleSheet("""
            QPushButton {
                background-color: #4fc3f7;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #29b6f6;
            }
            QPushButton:pressed {
                background-color: #0288d1;
            }
        """)
        apply_button.clicked.connect(lambda: self._apply_regedit(prefix_info))
        layout.addWidget(apply_button)
        
        return widget
    
    def _apply_regedit(self, prefix_info: PrefixInfo):
        """Apply Wine registry settings to a prefix"""
        try:
            from utils.prefix_locator import PrefixLocator
            from pathlib import Path
            
            # Find the wine_settings.reg file
            
            if not reg_file_path.exists():
                QMessageBox.warning(self, "Registry File Not Found", 
                                  f"Could not find wine_settings.reg at:\n{reg_file_path}")
                return
            
            # Apply the registry settings
            locator = PrefixLocator()
            success = locator.apply_regedit_to_prefix(prefix_info, str(reg_file_path))
            
            game_name = getattr(prefix_info, 'game_name', 'Unknown Game')
            
            if success:
                QMessageBox.information(self, "Success", 
                                      f"Successfully applied registry settings to:\n{game_name}\n{prefix_info.path}")
                self.logger.info(f"Applied registry settings to {game_name} at {prefix_info.path}")
            else:
                QMessageBox.warning(self, "Failed", 
                                  f"Failed to apply registry settings to:\n{game_name}\n{prefix_info.path}")
                
        except Exception as e:
            self.logger.error(f"Error applying regedit: {e}")
            QMessageBox.critical(self, "Error", f"Error applying registry settings:\n{str(e)}")


class GameDependenciesDialog(QDialog):
    """Dialog for applying comprehensive dependencies to games"""
    
    def __init__(self, games_list, game_manager, parent=None):
        super().__init__(parent)
        self.games_list = games_list
        self.game_manager = game_manager
        self.logger = logging.getLogger(__name__)
        
        self.setWindowTitle("Apply Dependencies")
        self.setModal(True)
        self.resize(800, 600)
        
        self._create_widgets()
        
    def _create_widgets(self):
        """Create the dialog widgets"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Apply Comprehensive Dependencies")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #66bb6a; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel("Select games to apply dependencies, registry settings, and .NET 9 SDK:")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #b0bec5; font-size: 12px; margin-bottom: 15px;")
        layout.addWidget(desc_label)

        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        search_layout.addWidget(search_label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter games by name or platform...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #424242;
                border: 2px solid #555555;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #66bb6a;
            }
        """)
        self.search_box.textChanged.connect(self._filter_games)
        search_layout.addWidget(self.search_box)

        # Clear search button
        clear_button = QPushButton("Clear")
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                border: 2px solid #555555;
                border-radius: 6px;
                padding: 6px 12px;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        clear_button.clicked.connect(lambda: self.search_box.clear())
        search_layout.addWidget(clear_button)

        layout.addLayout(search_layout)

        # Game selection list
        self.games_list_widget = QListWidget()
        self.games_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.games_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                font-size: 13px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #4fc3f7;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #2d2d2d;
            }
        """)

        # Store all games for filtering
        self.all_games = []
        for game in self.games_list:
            item_text = f"{game.name} ({game.platform})"
            if game.prefix_path:
                item_text += f" - {game.prefix_path}"

            self.all_games.append((item_text, game))
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, game)
            self.games_list_widget.addItem(item)

        layout.addWidget(self.games_list_widget)


        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #b0bec5; font-size: 12px;")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("Apply Dependencies")
        self.apply_button.setStyleSheet("""
            QPushButton {
                background-color: #9c27b0;
                border: 2px solid #555555;
                border-radius: 8px;
                padding: 10px 20px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7b1fa2;
                border-color: #9c27b0;
            }
            QPushButton:pressed {
                background-color: #4a148c;
            }
            QPushButton:disabled {
                background-color: #424242;
                color: #888888;
            }
        """)
        self.apply_button.clicked.connect(self._apply_dependencies)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                border: 2px solid #555555;
                border-radius: 8px;
                padding: 10px 20px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #616161;
                border-color: #757575;
            }
            QPushButton:pressed {
                background-color: #424242;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)


    def _filter_games(self):
        """Filter games based on search text"""
        search_text = self.search_box.text().lower()

        # Clear current list
        self.games_list_widget.clear()

        # Add matching games
        for item_text, game in self.all_games:
            if search_text in item_text.lower():
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, game)
                self.games_list_widget.addItem(item)

    def _apply_dependencies(self):
        """Apply dependencies to selected games"""
        selected_items = self.games_list_widget.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select at least one game.")
            return
        
        # Disable apply button and show progress
        self.apply_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        
        try:
            total_games = len(selected_items)
            successful_applications = 0
            
            for i, item in enumerate(selected_items):
                game = item.data(Qt.ItemDataRole.UserRole)
                
                # Update progress
                progress = int((i / total_games) * 100)
                self.progress_bar.setValue(progress)
                self.status_label.setText(f"Processing {game.name}...")
                QApplication.processEvents()
                
                try:
                    # Apply comprehensive dependencies based on game type
                    if "fallout" in game.name.lower() and "vegas" in game.name.lower():
                        result = self.game_manager.setup_specific_game_complete(game)
                    elif "enderal" in game.name.lower():
                        result = self.game_manager.setup_specific_game_complete(game)
                    elif "skyrim" in game.name.lower():
                        result = self.game_manager.setup_specific_game_complete(game)
                    else:
                        # Generic game setup with Proton Experimental
                        result = self._apply_generic_dependencies(game)
                    
                    if result.success:
                        successful_applications += 1
                        self.logger.info(f"Successfully applied dependencies to {game.name}")
                    else:
                        self.logger.warning(f"Failed to apply dependencies to {game.name}: {result.error}")
                        
                except Exception as e:
                    self.logger.error(f"Error applying dependencies to {game.name}: {e}")
                    continue
            
            # Complete progress
            self.progress_bar.setValue(100)
            self.status_label.setText(f"Completed! {successful_applications}/{total_games} games processed successfully.")
            
            # Show results
            if successful_applications == total_games:
                QMessageBox.information(self, "Success", 
                                      f"Successfully applied dependencies to all {total_games} selected games!")
                self.accept()
            elif successful_applications > 0:
                QMessageBox.warning(self, "Partial Success", 
                                 f"Applied dependencies to {successful_applications} out of {total_games} games.\n"
                                 f"Check the logs for details about failed applications.")
                self.accept()
            else:
                QMessageBox.critical(self, "Failed", 
                                  "Failed to apply dependencies to any selected games.\n"
                                  "Check the logs for error details.")
                
        except Exception as e:
            self.logger.error(f"Error in dependency application: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply dependencies:\n{str(e)}")
            
        finally:
            # Re-enable apply button
            self.apply_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setVisible(False)
    
    def _apply_generic_dependencies(self, game):
        """Apply generic dependencies to a game using Proton Experimental"""
        try:
            from utils.smart_prefix_manager import SmartPrefixManager

            # Always use Proton Experimental for consistency
            self.logger.info(f"Using Proton Experimental for {game.name}")

            prefix_manager = SmartPrefixManager()
            
            # Comprehensive dependencies for all games (same as MO2)
            dependencies = [
                "fontsmooth=rgb",
                "xact",
                "xact_x64",
                "vcrun2022",
                "dotnet6",
                "dotnet7",
                "dotnet8",
                "dotnetdesktop6",
                "d3dcompiler_47",
                "d3dx11_43",
                "d3dcompiler_43",
                "d3dx9_43",
                "d3dx9",
                "vkd3d",
            ]
            
            # For Fallout New Vegas, use the specific method
            if "fallout" in game.name.lower() and "vegas" in game.name.lower():
                from utils.comprehensive_game_manager import ComprehensiveGameManager
                game_manager = ComprehensiveGameManager()
                result = game_manager.setup_fnv_complete()
                return result
            
            # For other games, use generic approach
            dep_result = prefix_manager.install_dependencies_smart(game.name, dependencies)
            if not dep_result["success"]:
                return type('Result', (), {
                    'success': False,
                    'error': dep_result["error"],
                    'message': f"Failed to install dependencies: {dep_result['error']}",
                    'game_name': game.name,
                    'platform': game.platform
                })()
            
            # Apply registry settings
            from pathlib import Path
            reg_file_path = Path(__file__).parent.parent.parent / "utils" / "wine_settings.reg"
            if reg_file_path.exists():
                reg_result = prefix_manager.apply_regedit_smart(game.name, str(reg_file_path))
                if not reg_result["success"]:
                    self.logger.warning(f"Registry settings failed for {game.name}: {reg_result['error']}")
            
            # Note: .NET SDK installation removed for light modifications (only needed for MO2)
            
            return type('Result', (), {
                'success': True,
                'message': f"Dependencies applied to {game.name}",
                'game_name': game.name,
                'platform': game.platform,
                'prefix_path': dep_result.get("prefix_path")
            })()
            
        except Exception as e:
            return type('Result', (), {
                'success': False,
                'error': str(e),
                'message': f"Failed to apply dependencies to {game.name}",
                'game_name': game.name,
                'platform': game.platform
            })()