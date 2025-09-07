"""
Game-specific information view
Shows game-specific fixes and dependency installation
"""

import logging
import subprocess
import tempfile
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QTextEdit, QProgressBar,
    QMessageBox, QScrollArea, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

class DependencyInstallThread(QThread):
    """Thread for installing dependencies"""
    progress_updated = Signal(int)
    log_updated = Signal(str)
    finished = Signal(bool, str)
    
    def __init__(self, app_id, dependencies):
        super().__init__()
        self.app_id = app_id
        self.dependencies = dependencies
        
    def run(self):
        try:
            # Load wine registry settings first
            if self._load_wine_registry_settings(self.app_id):
                self.log_updated.emit("Wine registry settings loaded successfully")
            else:
                self.log_updated.emit("Warning: Failed to load wine registry settings")
            
            # Install dependencies
            total_deps = len(self.dependencies)
            for i, dep in enumerate(self.dependencies):
                self.log_updated.emit(f"Installing {dep}...")
                self.progress_updated.emit(int((i / total_deps) * 100))
                
                # Install dependency using protontricks
                result = subprocess.run([
                    "protontricks", self.app_id, dep
                ], capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    self.log_updated.emit(f"✓ {dep} installed successfully")
                else:
                    self.log_updated.emit(f"✗ Failed to install {dep}: {result.stderr}")
            
            self.progress_updated.emit(100)
            self.finished.emit(True, "Dependencies installed successfully")
            
        except Exception as e:
            self.log_updated.emit(f"Error: {str(e)}")
            self.finished.emit(False, str(e))
    
    def _load_wine_registry_settings(self, app_id: str) -> bool:
        """Load wine registry settings using Proton's regedit"""
        try:
            # Find Steam root
            steam_root = self._find_steam_root()
            if not steam_root:
                self.log_updated.emit("Error: Could not find Steam root")
                return False
            
            # Find game compatdata path
            compatdata_path = self._find_game_compatdata(steam_root, app_id)
            if not compatdata_path:
                self.log_updated.emit(f"Error: Could not find compatdata for app {app_id}")
                return False
            
            # Find Proton installation
            proton_path = self._find_proton_installation(steam_root)
            if not proton_path:
                self.log_updated.emit("Error: Could not find Proton installation")
                return False
            
            # Copy wine_settings.reg to temp directory
            wine_settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "utils", "wine_settings.reg")
            if not os.path.exists(wine_settings_path):
                self.log_updated.emit("Error: wine_settings.reg not found")
                return False
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False) as temp_file:
                temp_reg_path = temp_file.name
                with open(wine_settings_path, 'r') as src_file:
                    temp_file.write(src_file.read())
            
            # Execute regedit command
            env = os.environ.copy()
            env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = steam_root
            env['STEAM_COMPAT_DATA_PATH'] = compatdata_path
            
            result = subprocess.run([
                proton_path, "run", "regedit", temp_reg_path
            ], env=env, capture_output=True, text=True, timeout=60)
            
            # Clean up temp file
            os.unlink(temp_reg_path)
            
            if result.returncode == 0:
                return True
            else:
                self.log_updated.emit(f"Regedit failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.log_updated.emit(f"Error loading wine registry: {str(e)}")
            return False
    
    def _find_steam_root(self) -> str:
        """Find Steam root directory"""
        possible_paths = [
            os.path.expanduser("~/.steam/steam"),
            os.path.expanduser("~/.local/share/steam"),
            "/usr/share/steam"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    def _find_game_compatdata(self, steam_root: str, app_id: str) -> str:
        """Find game compatdata path"""
        compatdata_path = os.path.join(steam_root, "steamapps", "compatdata", app_id)
        if os.path.exists(compatdata_path):
            return compatdata_path
        return None
    
    def _find_proton_installation(self, steam_root: str) -> str:
        """Find Proton installation path"""
        # Look for Proton Experimental first
        proton_paths = [
            os.path.join(steam_root, "steamapps", "common", "Proton - Experimental", "proton"),
            os.path.join(steam_root, "steamapps", "common", "Proton 8.0", "proton"),
            os.path.join(steam_root, "steamapps", "common", "Proton 7.0", "proton")
        ]
        
        for path in proton_paths:
            if os.path.exists(path):
                return path
        
        # Look for any Proton version
        common_path = os.path.join(steam_root, "steamapps", "common")
        if os.path.exists(common_path):
            for item in os.listdir(common_path):
                if item.startswith("Proton"):
                    proton_path = os.path.join(common_path, item, "proton")
                    if os.path.exists(proton_path):
                        return proton_path
        
        return None

class GameInfoView(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.logger = logging.getLogger(__name__)
        
        self.current_game_view = None
        self.install_thread = None
        
        self._create_widgets()
        self.logger.info("Game info view created")
        
    def _create_widgets(self):
        """Create the game info widgets"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(30)
        
        # Content area for dynamic content
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setSpacing(20)
        main_layout.addWidget(self.content_area)
        
        # Game buttons
        self._create_game_buttons(self.content_layout)
        
        # Back button
        self._create_back_button(main_layout)
        
        # Store reference to main layout for dynamic content
        self.main_layout = main_layout
        
    def _create_header(self, parent_layout):
        """Create the header section"""
        # Title
        title_label = QLabel("Game-Specific Information")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 10px;")
        parent_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Fixes and information for certain games")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #90caf9; margin-bottom: 20px;")
        parent_layout.addWidget(subtitle_label)
        
    def _create_game_buttons(self, parent_layout):
        """Create the game selection buttons"""
        # Create a frame for the game buttons
        game_buttons_frame = QFrame()
        game_layout = QHBoxLayout(game_buttons_frame)
        game_layout.setSpacing(30)
        
        # Add spacer to center the buttons
        game_layout.addStretch()
        
        # FNV button
        fnv_button = QPushButton("FNV Modding Fixes")
        fnv_button.setStyleSheet("""
            QPushButton {
                background-color: #4fc3f7;
                border: none;
                border-radius: 4px;
                padding: 15px 30px;
                color: #ffffff;
                font-weight: bold;
                font-size: 16px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #29b6f6;
            }
            QPushButton:pressed {
                background-color: #0288d1;
            }
        """)
        fnv_button.clicked.connect(self._show_fnv_info)
        game_layout.addWidget(fnv_button)
        
        # Enderal button
        enderal_button = QPushButton("Enderal Modding Fixes")
        enderal_button.setStyleSheet("""
            QPushButton {
                background-color: #4fc3f7;
                border: none;
                border-radius: 4px;
                padding: 15px 30px;
                color: #ffffff;
                font-weight: bold;
                font-size: 16px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #29b6f6;
            }
            QPushButton:pressed {
                background-color: #0288d1;
            }
        """)
        enderal_button.clicked.connect(self._show_enderal_info)
        game_layout.addWidget(enderal_button)
        
        # Add spacer to center the buttons
        game_layout.addStretch()
        
        parent_layout.addWidget(game_buttons_frame)
        
        # Store reference to game buttons frame
        self.game_buttons_frame = game_buttons_frame
        
    def _create_back_button(self, parent_layout):
        """Create the back button"""
        back_button = QPushButton("← Back to Main Menu")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                border-radius: 4px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                max-width: 200px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        back_button.clicked.connect(self.controller.show_main_menu)
        
        # Center the button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(back_button)
        button_layout.addStretch()
        parent_layout.addLayout(button_layout)
        
    def _show_fnv_info(self):
        """Show FNV-specific information and setup"""
        self._clear_content()
        # Hide game buttons frame
        if self.game_buttons_frame:
            self.game_buttons_frame.hide()
        self._create_fnv_view()
        
    def _show_enderal_info(self):
        """Show Enderal-specific information and setup"""
        self._clear_content()
        # Hide game buttons frame
        if self.game_buttons_frame:
            self.game_buttons_frame.hide()
        self._create_enderal_view()
        
    def _create_fnv_view(self):
        """Create FNV-specific view"""
        # Title
        title_label = QLabel("Fallout: New Vegas Modding Fixes")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 20px;")
        self.content_layout.insertWidget(0, title_label)
        
        # Check if FNV is detected
        fnv_detected = self._check_game_detection("22380")  # FNV Steam App ID
        
        if fnv_detected:
            # Show launch options
            launch_label = QLabel("FNV detected! Launch options available.")
            launch_label.setStyleSheet("color: #4caf50; font-size: 16px; margin-bottom: 20px;")
            launch_label.setAlignment(Qt.AlignCenter)
            self.content_layout.insertWidget(1, launch_label)
            
            # Show launch option
            steam_root = self._find_steam_root()
            self.logger.info(f"Steam root found: {steam_root}")
            if steam_root:
                compatdata_path = os.path.join(steam_root, "steamapps", "compatdata", "22380")
                self.logger.info(f"Compatdata path: {compatdata_path}")
                self.logger.info(f"Creating launch options section...")
                
                # Launch option section
                launch_option_label = QLabel("Add to MO2 Launch Options:")
                launch_option_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px; margin-bottom: 10px;")
                self.content_layout.insertWidget(2, launch_option_label)
                
                # Launch option command (simplified - just the command first)
                launch_command = f'STEAM_COMPAT_DATA_PATH="{compatdata_path}" %command%'
                launch_command_label = QLabel(launch_command)
                launch_command_label.setStyleSheet("color: #90caf9; font-family: monospace; font-size: 12px; padding: 10px; background-color: #2d2d2d; border: 1px solid #555555; border-radius: 4px;")
                launch_command_label.setWordWrap(True)
                launch_command_label.setMinimumHeight(50)
                self.content_layout.insertWidget(3, launch_command_label)
                
                # Instructions
                instructions_label = QLabel("Copy this command and paste it into Mod Organizer 2's launch options in Steam.")
                instructions_label.setStyleSheet("color: #b0bec5; font-size: 12px; margin-bottom: 20px; font-style: italic;")
                instructions_label.setWordWrap(True)
                self.content_layout.insertWidget(4, instructions_label)
                
                # Copy button (moved here for better UX)
                copy_button = QPushButton("Copy Command")
                copy_button.setStyleSheet("""
                    QPushButton {
                        background-color: #2196f3;
                        border: none;
                        border-radius: 4px;
                        padding: 8px 16px;
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 12px;
                        min-width: 100px;
                    }
                    QPushButton:hover {
                        background-color: #1976d2;
                    }
                    QPushButton:pressed {
                        background-color: #1565c0;
                    }
                """)
                copy_button.clicked.connect(lambda: self._copy_to_clipboard(launch_command))
                self.content_layout.insertWidget(5, copy_button)
                
                # Dependencies section
                deps_label = QLabel("Install Dependencies:")
                deps_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px; margin-bottom: 10px;")
                self.content_layout.insertWidget(6, deps_label)
                
                # Dependencies list in scrollable area
                deps_text = QTextEdit()
                deps_text.setPlainText("• fontsmooth=rgb\n• xact\n• xact_x64\n• d3dx9_43\n• d3dx9\n• vcrun2022")
                deps_text.setStyleSheet("""
                    QTextEdit {
                        color: #b0bec5;
                        background-color: #2d2d2d;
                        border: 1px solid #555555;
                        border-radius: 4px;
                        padding: 10px;
                        font-size: 12px;
                    }
                """)
                deps_text.setMaximumHeight(100)
                deps_text.setReadOnly(True)
                self.content_layout.insertWidget(7, deps_text)
                
                # Install button
                install_button = QPushButton("Install Dependencies")
                install_button.setStyleSheet("""
                    QPushButton {
                        background-color: #4caf50;
                        border: none;
                        border-radius: 4px;
                        padding: 12px 24px;
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                    QPushButton:pressed {
                        background-color: #3d8b40;
                    }
                """)
                install_button.clicked.connect(lambda: self._setup_fnv_dependencies())
                self.content_layout.insertWidget(8, install_button)
            
        else:
            # Show not detected message
            not_detected_label = QLabel("FNV not detected. Please install and run the game first.")
            not_detected_label.setStyleSheet("color: #f44336; font-size: 16px; margin-bottom: 20px;")
            not_detected_label.setAlignment(Qt.AlignCenter)
            self.content_layout.insertWidget(1, not_detected_label)
        
        # Store current view
        self.current_game_view = "fnv"
        
    def _create_enderal_view(self):
        """Create Enderal-specific view"""
        # Title
        title_label = QLabel("Enderal Modding Fixes")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 20px;")
        self.content_layout.insertWidget(0, title_label)
        
        # Check if Enderal is detected
        enderal_detected = self._check_game_detection("976620")  # Enderal Steam App ID
        
        if enderal_detected:
            # Show detection status
            launch_label = QLabel("Enderal detected! Launch options available.")
            launch_label.setStyleSheet("color: #4caf50; font-size: 16px; margin-bottom: 20px;")
            launch_label.setAlignment(Qt.AlignCenter)
            self.content_layout.insertWidget(1, launch_label)
            
            # Show launch option
            steam_root = self._find_steam_root()
            self.logger.info(f"Steam root found: {steam_root}")
            if steam_root:
                compatdata_path = os.path.join(steam_root, "steamapps", "compatdata", "976620")
                self.logger.info(f"Compatdata path: {compatdata_path}")
                
                # Launch option section
                launch_option_label = QLabel("Add to MO2 Launch Options:")
                launch_option_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px; margin-bottom: 10px;")
                self.content_layout.insertWidget(2, launch_option_label)
                
                # Launch option command with copy button
                launch_command = f'STEAM_COMPAT_DATA_PATH="{compatdata_path}" %command%'
                
                # Create horizontal layout for command and copy button
                launch_layout = QHBoxLayout()
                
                # Launch command label
                launch_command_label = QLabel(launch_command)
                launch_command_label.setStyleSheet("color: #90caf9; font-family: monospace; font-size: 12px; padding: 10px; background-color: #2d2d2d; border: 1px solid #555555; border-radius: 4px;")
                launch_command_label.setWordWrap(True)
                launch_command_label.setMinimumHeight(50)
                launch_layout.addWidget(launch_command_label, 1)
                
                # Copy button
                copy_button = QPushButton("Copy")
                copy_button.setStyleSheet("""
                    QPushButton {
                        background-color: #2196f3;
                        border: none;
                        border-radius: 4px;
                        padding: 8px 16px;
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 12px;
                        min-width: 60px;
                    }
                    QPushButton:hover {
                        background-color: #1976d2;
                    }
                    QPushButton:pressed {
                        background-color: #1565c0;
                    }
                """)
                copy_button.clicked.connect(lambda: self._copy_to_clipboard(launch_command))
                launch_layout.addWidget(copy_button)
                
                self.content_layout.insertWidget(3, launch_layout)
                
                # Instructions
                instructions_label = QLabel("Copy this command and paste it into Mod Organizer 2's launch options in Steam.")
                instructions_label.setStyleSheet("color: #b0bec5; font-size: 12px; margin-bottom: 20px; font-style: italic;")
                instructions_label.setWordWrap(True)
                self.content_layout.insertWidget(4, instructions_label)
                
                # Dependencies section
                deps_label = QLabel("Install Dependencies:")
                deps_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px; margin-bottom: 10px;")
                self.content_layout.insertWidget(5, deps_label)
                
                # Dependencies list in scrollable text area
                deps_text = QTextEdit()
                deps_text.setPlainText("• fontsmooth=rgb\n• xact\n• xact_x64\n• d3dx11_43\n• d3dcompiler_43\n• d3dcompiler_47\n• vcrun2022\n• dotnet6\n• dotnet7\n• dotnet8")
                deps_text.setStyleSheet("""
                    QTextEdit {
                        color: #b0bec5;
                        background-color: #2d2d2d;
                        border: 1px solid #555555;
                        border-radius: 4px;
                        padding: 10px;
                        font-size: 12px;
                    }
                """)
                deps_text.setMaximumHeight(120)
                deps_text.setReadOnly(True)
                self.content_layout.insertWidget(6, deps_text)
                
                # Install button
                install_button = QPushButton("Install Dependencies")
                install_button.setStyleSheet("""
                    QPushButton {
                        background-color: #4caf50;
                        border: none;
                        border-radius: 4px;
                        padding: 12px 24px;
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                    QPushButton:pressed {
                        background-color: #3d8b40;
                    }
                """)
                install_button.clicked.connect(lambda: self._setup_enderal_dependencies())
                self.content_layout.insertWidget(7, install_button)
            
        else:
            # Show not detected message
            not_detected_label = QLabel("Enderal not detected. Please install and run the game first.")
            not_detected_label.setStyleSheet("color: #f44336; font-size: 16px; margin-bottom: 20px;")
            not_detected_label.setAlignment(Qt.AlignCenter)
            self.content_layout.insertWidget(1, not_detected_label)
        
        # Store current view
        self.current_game_view = "enderal"
        
    def _check_game_detection(self, app_id: str) -> bool:
        """Check if a game is detected by looking for its compatdata"""
        try:
            steam_root = self._find_steam_root()
            if not steam_root:
                return False
                
            compatdata_path = os.path.join(steam_root, "steamapps", "compatdata", app_id)
            return os.path.exists(compatdata_path)
            
        except Exception as e:
            self.logger.error(f"Error checking game detection: {e}")
            return False
    
    def _find_steam_root(self) -> str:
        """Find Steam root directory"""
        possible_paths = [
            os.path.expanduser("~/.steam/steam"),
            os.path.expanduser("~/.local/share/steam"),
            "/usr/share/steam"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
        
    def _setup_fnv_dependencies(self):
        """Setup FNV dependencies"""
        self._setup_dependencies("22380", ["fontsmooth=rgb", "xact", "xact_x64", "d3dx9_43", "d3dx9", "vcrun2022"])
        
    def _setup_enderal_dependencies(self):
        """Setup Enderal dependencies"""
        self._setup_dependencies("976620", ["fontsmooth=rgb", "xact", "xact_x64", "d3dx11_43", "d3dcompiler_43", "d3dcompiler_47", "vcrun2022", "dotnet6", "dotnet7", "dotnet8"])
        
    def _setup_dependencies(self, app_id: str, dependencies: list):
        """Setup dependencies for a specific game"""
        # Show dependency progress view
        self._show_dependency_progress(app_id, dependencies)
        
    def _show_dependency_progress(self, app_id: str, dependencies: list):
        """Show dependency installation progress"""
        # Clear current content
        self._clear_content()
        
        # Title
        title_label = QLabel("Installing Dependencies...")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 20px;")
        self.main_layout.insertWidget(1, title_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                background-color: #2d2d2d;
                height: 30px;
            }
            QProgressBar::chunk {
                background-color: #4fc3f7;
                border-radius: 3px;
            }
        """)
        self.main_layout.insertWidget(2, self.progress_bar)
        
        # Log area
        log_label = QLabel("Installation Log:")
        log_label.setStyleSheet("color: #ffffff; font-weight: bold; margin-top: 20px;")
        self.main_layout.insertWidget(3, log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(300)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                padding: 8px;
            }
        """)
        self.main_layout.insertWidget(4, self.log_text)
        
        # Back button
        back_button = QPushButton("← Back")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                border-radius: 4px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                max-width: 200px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        back_button.clicked.connect(self._go_back)
        
        # Center the button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(back_button)
        button_layout.addStretch()
        self.main_layout.insertLayout(5, button_layout)
        
        # Start installation
        self._install_dependencies_thread(app_id, dependencies)
        
    def _install_dependencies_thread(self, app_id: str, dependencies: list):
        """Install dependencies in a background thread"""
        self.install_thread = DependencyInstallThread(app_id, dependencies)
        self.install_thread.progress_updated.connect(self._update_progress)
        self.install_thread.log_updated.connect(self._log_output)
        self.install_thread.finished.connect(self._installation_finished)
        self.install_thread.start()
        
    def _update_progress(self, value: int):
        """Update progress bar"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(value)
            
    def _log_output(self, message: str):
        """Add message to log"""
        if hasattr(self, 'log_text'):
            self.log_text.append(message)
            
    def _installation_finished(self, success: bool, message: str):
        """Handle installation completion"""
        if success:
            self._log_output("✓ Installation completed successfully!")
            QMessageBox.information(self, "Success", message)
        else:
            self._log_output(f"✗ Installation failed: {message}")
            QMessageBox.critical(self, "Error", f"Installation failed: {message}")
            
    def _clear_content(self):
        """Clear the current content"""
        # Clear the content area, preserving the game buttons frame
        if hasattr(self, 'content_layout'):
            # Remove all widgets from content layout except the game buttons frame
            items_to_remove = []
            for i in range(self.content_layout.count()):
                item = self.content_layout.itemAt(i)
                if item.widget() != self.game_buttons_frame:
                    items_to_remove.append(i)
            
            # Remove items in reverse order to avoid index shifting
            for i in reversed(items_to_remove):
                item = self.content_layout.takeAt(i)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    # Clear layout items
                    while item.layout().count():
                        sub_item = item.layout().takeAt(0)
                        if sub_item.widget():
                            sub_item.widget().deleteLater()
                    item.layout().deleteLater()
                
    def _go_back(self):
        """Go back to the previous view"""
        if self.current_game_view:
            # Clear content and show game buttons again
            self._clear_content()
            if self.game_buttons_frame:
                self.game_buttons_frame.show()
            self.current_game_view = None
        else:
            # Go back to main menu
            self.controller.show_main_menu()
            
    def on_show(self):
        """Called when this view is shown"""
        self.logger.info("Game info view shown")
        # Always reset to game selection view
        self._clear_content()
        if self.game_buttons_frame:
            self.game_buttons_frame.show()
        self.current_game_view = None
        
    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.logger.info(f"Copied to clipboard: {text}")
