"""
Mod Organizer 2 setup view
Shows MO2 setup options
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QSpacerItem, QSizePolicy,
    QMessageBox, QProgressDialog, QFileDialog, QInputDialog, QLineEdit,
    QProgressBar, QTextEdit, QScrollArea, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont
from pathlib import Path
import os

class MO2InstallThread(QThread):
    """Thread for MO2 installation with progress tracking"""
    progress_updated = Signal(int)
    log_updated = Signal(str)
    progress_line_updated = Signal(str)  # For updating the same line
    finished = Signal(dict)
    
    def __init__(self, core, install_dir, custom_name):
        super().__init__()
        self.core = core
        self.install_dir = install_dir
        self.custom_name = custom_name
        
    def run(self):
        try:
            self.log_updated.emit("Starting MO2 download and installation...")
            self.progress_updated.emit(5)
            
            # Call the MO2 download with detailed progress tracking
            result = self._run_mo2_download_with_progress()
            
            # The _run_mo2_download_with_progress method already handles all the logging and progress updates
            # Just emit the finished signal with the result
            self.finished.emit(result)
            
        except Exception as e:
            self.log_updated.emit(f"❌ Error: {str(e)}")
            self.finished.emit({"success": False, "error": str(e)})
    
    def _run_mo2_download_with_progress(self):
        """Run MO2 download with detailed progress tracking"""
        try:
            # Step 1: Check dependencies (5-10%)
            self.log_updated.emit("🔍 Checking dependencies...")
            self.progress_updated.emit(10)
            
            deps_result = self.core.mo2._check_dependencies()
            if not deps_result["success"]:
                return deps_result
            
            self.log_updated.emit("✅ Dependencies check passed")
            self.progress_updated.emit(15)
            
            # Step 2: Get latest release info (15-25%)
            self.log_updated.emit("🌐 Fetching latest MO2 release information...")
            self.progress_updated.emit(20)
            
            release = self.core.mo2._get_latest_release()
            if not release:
                return {"success": False, "error": "Failed to get latest release information"}
            
            self.log_updated.emit(f"✅ Found latest version: {release.tag_name}")
            self.progress_updated.emit(25)
            
            # Step 3: Find download asset (25-30%)
            self.log_updated.emit("🔍 Finding download asset...")
            self.progress_updated.emit(30)
            
            download_url, filename = self.core.mo2._find_mo2_asset(release)
            if not download_url or not filename:
                return {"success": False, "error": "Could not find appropriate MO2 asset"}
            
            self.log_updated.emit(f"✅ Found asset: {filename}")
            self.progress_updated.emit(35)
            
            # Step 4: Download the file (35-65%)
            self.log_updated.emit(f"⬇️ Downloading {filename}...")
            self.log_updated.emit("📁 This may take a few minutes depending on your connection...")
            self.progress_updated.emit(40)
            
            # Set up live progress callback for download
            self.log_updated.emit("🔧 Setting up progress callback...")
            temp_file = self.core.mo2._download_file(download_url, filename, progress_callback=self._download_progress_callback)
            if not temp_file:
                return {"success": False, "error": "Failed to download MO2"}
            
            self.log_updated.emit("✅ Download completed!")
            self.progress_updated.emit(65)
            
            # Step 5: Extract the archive (65-75%)
            self.log_updated.emit(f"📦 Extracting to {self.install_dir}...")
            self.progress_updated.emit(70)
            
            actual_install_dir = self.core.mo2._extract_archive(temp_file, self.install_dir)
            if not actual_install_dir:
                return {"success": False, "error": "Failed to extract MO2 archive"}
            
            self.log_updated.emit("✅ Extraction completed!")
            self.progress_updated.emit(75)
            
            # Step 6: Verify installation (75-80%)
            self.log_updated.emit("🔍 Verifying installation...")
            self.progress_updated.emit(78)
            
            verify_result = self.core.mo2._verify_installation(actual_install_dir)
            if not verify_result["success"]:
                return verify_result
            
            self.log_updated.emit("✅ Installation verified!")
            self.progress_updated.emit(80)
            
            # Step 7: Find MO2 executable (80-82%)
            mo2_exe = self.core.mo2._find_mo2_executable(actual_install_dir)
            if not mo2_exe:
                return {"success": False, "error": "Could not find ModOrganizer.exe"}
            
            self.log_updated.emit(f"✅ Found executable: {mo2_exe}")
            self.progress_updated.emit(82)
            
            # Step 8: Add to Steam (82-90%)
            self.log_updated.emit("🎮 Adding to Steam...")
            self.log_updated.emit("🔧 Creating Steam shortcut...")
            self.progress_updated.emit(85)
            
            steam_result = self.core.mo2._add_mo2_to_steam(mo2_exe, self.custom_name)
            if not steam_result["success"]:
                return steam_result
            
            app_id = steam_result["app_id"]
            compat_data_path = steam_result["compat_data_path"]
            
            self.log_updated.emit(f"✅ Steam shortcut created (AppID: {app_id})")
            self.log_updated.emit(f"📁 Compatdata folder: {compat_data_path}")
            self.progress_updated.emit(90)
            
            # Step 9: Install dependencies (90-98%)
            self.log_updated.emit("📦 Installing dependencies with protontricks...")
            self.log_updated.emit("🔄 This may take a few minutes...")
            self.progress_updated.emit(95)
            
            # Set up log callback for live dependency installation updates
            self.core.mo2.set_log_callback(self.log_updated.emit)
            
            dependency_result = self.core.mo2._auto_install_dependencies(app_id, self.custom_name)
            if not dependency_result["success"]:
                self.log_updated.emit(f"⚠️ Dependency installation failed: {dependency_result.get('error', 'Unknown error')}")
                # Don't fail the whole installation if dependencies fail
            else:
                self.log_updated.emit("✅ Dependencies installed successfully!")
            
            self.progress_updated.emit(98)
            
            # Clean up temporary file
            try:
                import os
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    self.log_updated.emit("🧹 Cleaned up temporary files")
            except Exception as e:
                self.log_updated.emit(f"⚠️ Failed to clean up temporary file: {e}")
            
            self.progress_updated.emit(100)
            
            # Return the complete result
            return {
                "success": True,
                "install_dir": actual_install_dir,
                "mo2_exe": mo2_exe,
                "version": release.tag_name,
                "mo2_name": self.custom_name,
                "app_id": app_id,
                "compat_data_path": compat_data_path,
                "message": f"Mod Organizer 2 {release.tag_name} installed and added to Steam successfully!",
                "steam_integration": steam_result,
                "dependency_installation": dependency_result
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _download_progress_callback(self, percent, downloaded_bytes, total_bytes):
        """Live progress callback for download updates - thread-safe"""
        import time
        from PySide6.QtCore import QTimer, QMetaObject, Qt
        
        # Store progress data as instance variables for thread-safe access
        self._current_percent = percent
        self._current_downloaded = downloaded_bytes  
        self._current_total = total_bytes
        
        # Use QMetaObject.invokeMethod for thread-safe signal emission
        QMetaObject.invokeMethod(self, "_emit_progress_signals", Qt.QueuedConnection)
    
    @Slot()
    def _emit_progress_signals(self):
        """Emit progress signals from main thread - this is thread-safe"""
        import time
        
        percent = getattr(self, '_current_percent', 0)
        downloaded_bytes = getattr(self, '_current_downloaded', 0)
        total_bytes = getattr(self, '_current_total', 0)
        
        # Scale the download progress to fit within our 40-65% range
        download_progress = 40 + (percent * 0.25)  # Maps 0-100% to 40-65%
        self.progress_updated.emit(int(download_progress))
        
        # Initialize timing for periodic updates
        if not hasattr(self, '_last_update_time'):
            self._last_update_time = 0
            self.log_updated.emit(f"📊 Starting download progress tracking...")
        
        # Format bytes for display
        def format_bytes(bytes_val):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f} TB"
        
        # Show progress every 2 seconds with single-line updates
        current_time = time.time()
        if current_time - self._last_update_time >= 2.0 and total_bytes > 0:
            downloaded_str = format_bytes(downloaded_bytes)
            total_str = format_bytes(total_bytes)
            
            # Create visual progress bar
            bar_width = 20
            filled = int((percent / 100) * bar_width)
            bar = '█' * filled + '░' * (bar_width - filled)
            
            # Use the special progress line signal for single-line updates
            progress_text = f"📥 [{bar}] {percent}% ({downloaded_str}/{total_str})"
            self.progress_line_updated.emit(progress_text)
            
            # Update the last update time
            self._last_update_time = current_time

class MO2SetupThread(QThread):
    """Thread for MO2 setup with progress tracking"""
    progress_updated = Signal(int)
    log_updated = Signal(str)
    finished = Signal(dict)
    
    def __init__(self, core, mo2_exe, custom_name):
        super().__init__()
        self.core = core
        self.mo2_exe = mo2_exe
        self.custom_name = custom_name
        
    def run(self):
        try:
            self.log_updated.emit("Starting MO2 setup...")
            self.progress_updated.emit(10)
            
            # Call the MO2 setup with detailed progress tracking
            result = self._run_mo2_setup_with_progress()
            
            # The _run_mo2_setup_with_progress method already handles all the logging and progress updates
            # Just emit the finished signal with the result
            self.finished.emit(result)
            
        except Exception as e:
            self.log_updated.emit(f"❌ Error: {str(e)}")
            self.finished.emit({"success": False, "error": str(e)})
    
    def _run_mo2_setup_with_progress(self):
        """Run MO2 setup with detailed progress tracking"""
        try:
            # Step 1: Verify executable (10-20%)
            self.log_updated.emit("🔍 Verifying ModOrganizer.exe...")
            self.progress_updated.emit(20)
            
            if not os.path.exists(self.mo2_exe):
                return {"success": False, "error": f"Executable does not exist: {self.mo2_exe}"}
            
            if not self.mo2_exe.lower().endswith("modorganizer.exe"):
                return {"success": False, "error": f"File is not ModOrganizer.exe: {self.mo2_exe}"}
            
            self.log_updated.emit(f"✅ Found: {self.mo2_exe}")
            self.progress_updated.emit(30)
            
            # Step 2: Add to Steam with prefix creation (30-70%)
            self.log_updated.emit("🎮 Adding to Steam...")
            self.log_updated.emit("🔧 Creating Steam shortcut...")
            self.progress_updated.emit(40)
            
            steam_result = self.core.steam_utils.add_game_to_steam(self.custom_name, self.mo2_exe)
            if not steam_result["success"]:
                return steam_result
            
            app_id = steam_result["app_id"]
            compat_data_path = steam_result["compat_data_path"]
            
            self.log_updated.emit(f"✅ Steam shortcut created (AppID: {app_id})")
            self.log_updated.emit(f"📁 Compatdata folder: {compat_data_path}")
            self.progress_updated.emit(60)
            
            # Step 3: Prefix creation (60-80%)
            self.log_updated.emit("🔧 Creating Wine prefix...")
            self.log_updated.emit("⚙️ Running .bat file with Proton...")
            self.progress_updated.emit(70)
            
            # The prefix creation is handled by add_game_to_steam, but let's show it
            self.log_updated.emit("⏳ Waiting for prefix initialization...")
            import time
            time.sleep(5)
            self.log_updated.emit("✅ Wine prefix created!")
            self.progress_updated.emit(80)
            
            # Step 4: Install dependencies (80-95%)
            self.log_updated.emit("📦 Installing dependencies with protontricks...")
            self.log_updated.emit("🔄 This may take a few minutes...")
            
            # Set up log callback for live dependency installation updates
            self.core.mo2.set_log_callback(self.log_updated.emit)
            
            dependency_result = self.core.mo2._auto_install_dependencies(app_id, self.custom_name)
            if not dependency_result["success"]:
                self.log_updated.emit(f"⚠️ Dependency installation failed: {dependency_result.get('error', 'Unknown error')}")
                # Don't fail the whole setup if dependencies fail
            else:
                self.log_updated.emit("✅ Dependencies installed successfully!")
            
            self.progress_updated.emit(95)
            
            self.progress_updated.emit(100)
            
            # Return the complete result
            return {
                "success": True,
                "mo2_exe": self.mo2_exe,
                "mo2_name": self.custom_name,
                "app_id": app_id,
                "compat_data_path": compat_data_path,
                "message": f"Existing MO2 installation configured successfully!",
                "steam_integration": steam_result,
                "dependency_installation": dependency_result
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

class MO2WorkerThread(QThread):
    """Worker thread for MO2 operations to prevent GUI freezing"""
    finished = Signal(dict)
    progress = Signal(str)
    
    def __init__(self, operation, *args, **kwargs):
        super().__init__()
        self.operation = operation
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        """Run the operation in the background"""
        try:
            if self.operation == "download_mo2":
                install_dir = self.kwargs.get('install_dir')
                custom_name = self.kwargs.get('custom_name')
                result = self.kwargs['core'].mo2.download_mo2(install_dir, custom_name)
            elif self.operation == "install_dependencies":
                result = self.kwargs['core'].deps.install_basic_dependencies()
            elif self.operation == "install_dependencies_for_game":
                app_id = self.kwargs.get('app_id')
                result = self.kwargs['core'].deps.install_mo2_dependencies_for_game(app_id)
            elif self.operation == "setup_existing":
                mo2_dir = self.kwargs.get('mo2_dir')
                result = self.kwargs['core'].mo2.setup_existing(mo2_dir)
            elif self.operation == "setup_existing_exe":
                mo2_exe = self.kwargs.get('mo2_exe')
                custom_name = self.kwargs.get('custom_name')
                result = self.kwargs['core'].mo2.setup_existing_exe(mo2_exe, custom_name)
            elif self.operation == "configure_nxm_handler":
                app_id = self.kwargs.get('app_id')
                nxm_handler_path = self.kwargs.get('nxm_handler_path')
                result = self.kwargs['core'].configure_nxm_handler(app_id, nxm_handler_path)
            elif self.operation == "remove_nxm":
                result = self.kwargs['core'].mo2.remove_nxm_handlers()
            else:
                result = {"success": False, "error": f"Unknown operation: {self.operation}"}
            
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"success": False, "error": str(e)})

class ModOrganizer2View(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.logger = logging.getLogger(__name__)
        
        self.current_subview = None
        self.install_thread = None
        
        self._create_widgets()
        self.logger.info("Mod Organizer 2 setup view created")
        
    def _create_widgets(self):
        """Create the MO2 setup widgets"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Content area for dynamic content
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setSpacing(20)
        main_layout.addWidget(self.content_area)
        
        # Header
        self._create_header(self.content_layout)
        
        # Options area
        self._create_options_area(self.content_layout)
        
        # Back button
        self._create_back_button(main_layout)
        
        # Store reference to main layout for dynamic content
        self.main_layout = main_layout
        
    def _create_header(self, parent_layout):
        """Create the header section"""
        # Title
        title_label = QLabel("Mod Organizer 2 Setup")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 8px;")
        parent_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Set up and configure Mod Organizer 2 for Linux gaming")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #90caf9; margin-bottom: 15px;")
        parent_layout.addWidget(subtitle_label)
        
    def _create_options_area(self, parent_layout):
        """Create the options area with simple 3+2 layout"""
        # Create the 3+2 layout directly on parent
        self._create_3_plus_2_layout(parent_layout)
        
    def _create_3_plus_2_layout(self, parent_layout):
        """Create a centered 2x2 grid layout"""
        # Create a grid layout for proper centering
        grid_layout = QHBoxLayout()
        grid_layout.addStretch()

        # Create the 2x2 grid container
        grid_container = QVBoxLayout()
        grid_container.setSpacing(15)

        # Top row (2 buttons)
        top_row = QHBoxLayout()
        top_row.setSpacing(15)

        # Download MO2 button
        download_button = self._create_option_button(
            "Download and install Mod Organizer 2",
            "Download MO2",
            self._show_mo2_install_view
        )
        top_row.addWidget(download_button)

        # Setup existing button
        setup_button = self._create_option_button(
            "Set up existing MO2 installation",
            "Set Up An Existing Installation",
            self._setup_existing
        )
        top_row.addWidget(setup_button)

        grid_container.addLayout(top_row)

        # Bottom row (2 buttons)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(15)

        # Configure NXM button
        nxm_button = self._create_option_button(
            "Set up NXM file handling",
            "Configure NXM Handler",
            self._configure_nxm
        )
        bottom_row.addWidget(nxm_button)

        # Remove NXM button
        remove_button = self._create_option_button(
            "Remove NXM handler configuration",
            "Remove NXM Handler",
            self._remove_nxm
        )
        bottom_row.addWidget(remove_button)

        grid_container.addLayout(bottom_row)

        # Add the grid container to the main layout with centering
        grid_layout.addLayout(grid_container)
        grid_layout.addStretch()

        parent_layout.addLayout(grid_layout)
        
    def _create_option_button(self, title, button_text, callback):
        """Create an option button with title and action"""
        # Create container frame
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 8px;
                padding: 15px;
                min-width: 450px;
                min-height: 140px;
                max-height: 140px;
            }
            QFrame:hover {
                border-color: #64b5f6;
                background-color: #3d3d3d;
            }
        """)

        # Create layout with more space for text
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(15, 15, 15, 15)

        # Title label with more height reserved
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                background-color: transparent;
                padding: 8px 2px;
                min-height: 40px;
            }
        """)
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Add fixed spacer to separate text from button
        layout.addStretch()

        # Button
        button = QPushButton(button_text)
        button.setStyleSheet("""
            QPushButton {
                background-color: #4fc3f7;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                min-height: 18px;
            }
            QPushButton:hover {
                background-color: #29b6f6;
            }
            QPushButton:pressed {
                background-color: #0288d1;
            }
        """)
        button.clicked.connect(callback)
        layout.addWidget(button)

        return container
        
    def _create_back_button(self, parent_layout):
        """Create the back button"""
        back_button = QPushButton("← Back to Main Menu")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
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
        
    def _show_mo2_install_view(self):
        """Show MO2 installation submenu with progress tracking"""
        self._clear_content()
        self._create_mo2_install_view()
        
    def _create_mo2_install_view(self):
        """Create MO2 installation submenu with progress tracking"""
        # Title
        title_label = QLabel("Mod Organizer 2 Installation")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 20px;")
        self.content_layout.addWidget(title_label)
        
        # Instructions
        instructions_label = QLabel("This will download and install Mod Organizer 2 with complete Steam integration.")
        instructions_label.setStyleSheet("color: #b0bec5; font-size: 14px; margin-bottom: 20px;")
        instructions_label.setWordWrap(True)
        instructions_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(instructions_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555555;
                border-radius: 5px;
                text-align: center;
                background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #4fc3f7;
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        self.content_layout.addWidget(self.progress_bar)
        
        # Log area
        self.log_area = QTextEdit()
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.log_area.setMaximumHeight(200)
        self.log_area.setReadOnly(True)
        self.content_layout.addWidget(self.log_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Start installation button
        self.start_button = QPushButton("Start Installation")
        self.start_button.setStyleSheet("""
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
        self.start_button.clicked.connect(self._start_mo2_installation)
        button_layout.addWidget(self.start_button)
        
        # Back button
        back_button = QPushButton("Back to MO2 Setup")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                border-radius: 4px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        back_button.clicked.connect(self._back_to_mo2_setup)
        button_layout.addWidget(back_button)
        
        self.content_layout.addLayout(button_layout)
        
    def _start_mo2_installation(self):
        """Start the MO2 installation process"""
        try:
            # Ask for installation directory
            install_dir = QFileDialog.getExistingDirectory(
                self,
                "Select MO2 Installation Directory",
                str(Path.home() / "ModOrganizer2")
            )
            
            if not install_dir:
                return
            
            # Ask for custom name for Steam
            custom_name, ok = QInputDialog.getText(
                self,
                "MO2 Steam Name",
                "Enter the name you want to use for MO2 in Steam:",
                QLineEdit.Normal,
                "Mod Organizer 2"
            )
            
            if not ok or not custom_name.strip():
                return
            
            # Disable start button
            self.start_button.setEnabled(False)
            self.start_button.setText("Installing...")
            
            # Show progress bar
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Clear log
            self.log_area.clear()
            self.log_area.append("Starting MO2 installation...\n")
            
            # Create and start installation thread
            self.install_thread = MO2InstallThread(
                self.controller.core,
                install_dir,
                custom_name
            )
            
            # Connect signals with QueuedConnection to ensure proper threading
            self.install_thread.progress_updated.connect(self.progress_bar.setValue, Qt.QueuedConnection)
            self.install_thread.log_updated.connect(self._update_log, Qt.QueuedConnection)
            self.install_thread.progress_line_updated.connect(self._update_progress_line, Qt.QueuedConnection)
            self.install_thread.finished.connect(self._on_installation_finished, Qt.QueuedConnection)
            
            # Start the thread
            self.install_thread.start()
            
        except Exception as e:
            self.log_area.append(f"❌ Error: {str(e)}")
            self.start_button.setEnabled(True)
            self.start_button.setText("Start Installation")
            
    def _update_log(self, message):
        """Update the log area with a message"""
        # Force GUI update by using QApplication.processEvents()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        self.log_area.append(message)
        
        # Force another process events to ensure the append is processed
        QApplication.processEvents()
        
        # Auto-scroll to bottom
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
        
        # Final process events to ensure scroll happens
        QApplication.processEvents()
    
    def _update_progress_line(self, progress_text):
        """Update the progress line (replace last line if it's a progress line)"""
        # Get current text content
        current_text = self.log_area.toPlainText()
        lines = current_text.split('\n')
        
        # Look for any existing progress line (with [█ or ░] characters) and replace it
        progress_line_found = False
        for i in range(len(lines) - 1, -1, -1):  # Search backwards
            if lines[i].startswith("📥 [") and ("█" in lines[i] or "░" in lines[i]):
                # Replace this progress line
                lines[i] = progress_text
                progress_line_found = True
                break
        
        if not progress_line_found:
            # No existing progress line found, add it
            lines.append(progress_text)
        
        # Set the updated text
        updated_text = '\n'.join(lines)
        self.log_area.setPlainText(updated_text)
            
        # Auto-scroll to bottom
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
        
    def _on_installation_finished(self, result):
        """Handle installation completion"""
        if result["success"]:
            self.log_area.append("✅ Installation completed successfully!")
            
            # Build detailed success message
            message = result.get("message", "Mod Organizer 2 installed successfully!")
            message += f"\n\nInstallation Directory: {result.get('install_dir', 'Unknown')}"
            message += f"\nMO2 Executable: {result.get('mo2_exe', 'Unknown')}"
            message += f"\nSteam Name: {result.get('mo2_name', 'Unknown')}"
            message += f"\nApp ID: {result.get('app_id', 'Unknown')}"
            message += f"\nVersion: {result.get('version', 'Unknown')}"
            
            # Add dependency installation info
            dep_result = result.get("dependency_installation", {})
            if dep_result.get("success"):
                message += f"\n\n✅ Dependencies installed successfully!"
                # Add debug log path if available
                debug_log = dep_result.get("debug_log", "")
                if debug_log:
                    message += f"\n\n🐛 Debug log: {debug_log}"
            else:
                dep_note = dep_result.get("note", "")
                if dep_note:
                    message += f"\n\nℹ️ {dep_note}"
                # Add debug log path even for failures
                debug_log = dep_result.get("debug_log", "")
                if debug_log:
                    message += f"\n\n🐛 Debug log: {debug_log}"
            
            # Show success dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Success")
            msg_box.setText(message)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()  # Use exec_() to make it modal
        else:
            self.log_area.append(f"❌ Installation failed: {result.get('error', 'Unknown error')}")
            
            # Show error dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"MO2 installation failed: {result.get('error', 'Unknown error')}")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()  # Use exec_() to make it modal
        
        # Re-enable start button
        self.start_button.setEnabled(True)
        self.start_button.setText("Start Installation")
        
    def _back_to_mo2_setup(self):
        """Go back to the main MO2 setup view"""
        self._clear_content()
        self._create_header(self.content_layout)
        self._create_options_area(self.content_layout)
        
    def _clear_content(self):
        """Clear the content area"""
        # Remove all items (widgets and layouts) from content layout
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                # Recursively clear nested layouts
                self._clear_layout(child.layout())
    
    def _clear_layout(self, layout):
        """Recursively clear a layout and its widgets"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout(child.layout())
        
    def _download_mo2(self):
        """Download MO2"""
        self.logger.info("Download MO2 clicked")
        
        # Ask user for installation directory
        install_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Mod Organizer 2 Installation Directory",
            str(Path.home() / "ModOrganizer2"),
            QFileDialog.Option.ShowDirsOnly
        )
        
        if not install_dir:
            return  # User cancelled
        
        # Show progress dialog
        progress = QProgressDialog("Downloading Mod Organizer 2...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(False)
        progress.show()
        
        # Create worker thread
        self.worker = MO2WorkerThread("download_mo2", core=self.controller.core, install_dir=install_dir)
        self.worker.finished.connect(lambda result: self._on_mo2_download_finished(result, progress))
        self.worker.start()
        
    def _on_mo2_download_finished(self, result, progress):
        """Handle MO2 download completion"""
        progress.close()
        
        if result.get("success"):
            QMessageBox.information(
                self, 
                "Success", 
                f"Mod Organizer 2 installed successfully!\n\n"
                f"Installation directory: {result.get('install_dir', 'Unknown')}\n"
                f"MO2 executable: {result.get('mo2_exe', 'Unknown')}\n"
                f"Version: {result.get('version', 'Unknown')}"
            )
        else:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to install Mod Organizer 2:\n{result.get('error', 'Unknown error')}"
            )
        
    def _setup_existing(self):
        """Show setup existing MO2 submenu"""
        self.logger.info("Setup existing MO2 clicked")
        
        # Show submenu for setup existing MO2
        self._show_setup_existing_view()
        
    def _show_setup_existing_view(self):
        """Show setup existing MO2 submenu"""
        self._clear_content()
        self._create_setup_existing_view()
    
    def _create_setup_existing_view(self):
        """Create setup existing MO2 submenu with NXM handler option"""
        # Title
        title_label = QLabel("Setup Existing MO2 Installation")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 20px;")
        self.content_layout.addWidget(title_label)
        
        # Instructions
        instructions_label = QLabel("Select your existing ModOrganizer.exe file to add it to Steam with complete integration.")
        instructions_label.setStyleSheet("color: #b0bec5; font-size: 14px; margin-bottom: 20px;")
        instructions_label.setWordWrap(True)
        instructions_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(instructions_label)
        
        
        # Progress bar
        self.setup_progress_bar = QProgressBar()
        self.setup_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555555;
                border-radius: 5px;
                text-align: center;
                background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #4fc3f7;
                border-radius: 3px;
            }
        """)
        self.setup_progress_bar.setVisible(False)
        self.content_layout.addWidget(self.setup_progress_bar)
        
        # Log area
        self.setup_log_area = QTextEdit()
        self.setup_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.setup_log_area.setMaximumHeight(200)
        self.setup_log_area.setReadOnly(True)
        self.content_layout.addWidget(self.setup_log_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Start setup button
        self.setup_start_button = QPushButton("Start Setup")
        self.setup_start_button.setStyleSheet("""
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
        self.setup_start_button.clicked.connect(self._start_setup_existing)
        button_layout.addWidget(self.setup_start_button)
        
        # Back button
        back_button = QPushButton("Back to MO2 Setup")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                border-radius: 4px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        back_button.clicked.connect(self._back_to_mo2_setup)
        button_layout.addWidget(back_button)
        
        self.content_layout.addLayout(button_layout)
    
    
    def _start_setup_existing(self):
        """Start the setup existing MO2 process"""
        try:
            # Ask user to select ModOrganizer.exe file
            mo2_exe = QFileDialog.getOpenFileName(
                self,
                "Select ModOrganizer.exe File",
                str(Path.home()),
                "Executable Files (*.exe);;All Files (*)"
            )[0]
            
            if not mo2_exe:
                return  # User cancelled
            
            # Ask for custom name for Steam
            custom_name, ok = QInputDialog.getText(
                self,
                "MO2 Steam Name",
                "Enter the name you want to use for MO2 in Steam:",
                QLineEdit.Normal,
                "Mod Organizer 2"
            )
            
            if not ok or not custom_name.strip():
                return
            
            # Disable start button
            self.setup_start_button.setEnabled(False)
            self.setup_start_button.setText("Setting up...")
            
            # Show progress bar
            self.setup_progress_bar.setVisible(True)
            self.setup_progress_bar.setValue(0)
            
            # Clear log
            self.setup_log_area.clear()
            self.setup_log_area.append("Starting MO2 setup...\n")
            
            # Create and start setup thread
            self.setup_thread = MO2SetupThread(
                self.controller.core,
                mo2_exe,
                custom_name
            )
            
            # Connect signals with QueuedConnection to ensure proper threading
            self.setup_thread.progress_updated.connect(self.setup_progress_bar.setValue, Qt.QueuedConnection)
            self.setup_thread.log_updated.connect(self._update_setup_log, Qt.QueuedConnection)
            self.setup_thread.finished.connect(self._on_setup_existing_finished, Qt.QueuedConnection)
            
            # Start the thread
            self.setup_thread.start()
            
        except Exception as e:
            self.setup_log_area.append(f"❌ Error: {str(e)}")
            self.setup_start_button.setEnabled(True)
            self.setup_start_button.setText("Start Setup")
    
    def _update_setup_log(self, message):
        """Update the setup log area with a message"""
        # Force GUI update by using QApplication.processEvents()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        self.setup_log_area.append(message)
        
        # Force another process events to ensure the append is processed
        QApplication.processEvents()
        
        # Auto-scroll to bottom
        self.setup_log_area.verticalScrollBar().setValue(
            self.setup_log_area.verticalScrollBar().maximum()
        )
        
        # Final process events to ensure scroll happens
        QApplication.processEvents()
    
    def _on_setup_existing_finished(self, result):
        """Handle setup existing completion"""
        if result["success"]:
            self.setup_log_area.append("✅ Setup completed successfully!")
            
            # Build detailed success message
            message = result.get("message", "Existing MO2 installation configured successfully!")
            message += f"\n\nMO2 Executable: {result.get('mo2_exe', 'Unknown')}"
            message += f"\nSteam Name: {result.get('mo2_name', 'Unknown')}"
            message += f"\nApp ID: {result.get('app_id', 'Unknown')}"
            
            # Add dependency installation info
            dep_result = result.get("dependency_installation", {})
            if dep_result.get("success"):
                message += f"\n\n✅ Dependencies installed successfully!"
            else:
                dep_note = dep_result.get("note", "")
                if dep_note:
                    message += f"\n\nℹ️ {dep_note}"
            
            # Show success dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Success")
            msg_box.setText(message)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()  # Use exec_() to make it modal
        else:
            self.setup_log_area.append(f"❌ Setup failed: {result.get('error', 'Unknown error')}")
            
            # Show error dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"MO2 setup failed: {result.get('error', 'Unknown error')}")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()  # Use exec_() to make it modal
        
        # Re-enable start button
        self.setup_start_button.setEnabled(True)
        self.setup_start_button.setText("Start Setup")
        
    def _configure_nxm(self):
        """Show NXM handler configuration submenu"""
        self.logger.info("Configure NXM clicked")
        
        # Get list of non-Steam games
        games = self.controller.core.steam_utils.get_non_steam_games()
        
        if not games:
            # Show error dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("No Games Found")
            msg_box.setText("No non-Steam games found. Add some games to Steam first.")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
            return
        
        # Show submenu with game selection and NXM handler file selection
        self._show_nxm_configure_view(games)
    
    def _show_nxm_configure_view(self, games):
        """Show NXM handler configuration submenu"""
        self._clear_content()
        self._create_nxm_configure_view(games)
    
    def _create_nxm_configure_view(self, games):
        """Create NXM handler configuration submenu"""
        # Title
        title_label = QLabel("Configure NXM Handler")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 20px;")
        self.content_layout.addWidget(title_label)
        
        # Instructions
        instructions_label = QLabel(f"Found {len(games)} non-Steam games. Please select one to configure NXM handler:")
        instructions_label.setStyleSheet("color: #b0bec5; font-size: 14px; margin-bottom: 20px;")
        instructions_label.setWordWrap(True)
        instructions_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(instructions_label)
        
        # Game selection list
        self.nxm_game_list = QListWidget()
        self.nxm_game_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                font-size: 14px;
                padding: 10px;
            }
            QListWidget::item {
                padding: 10px;
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
        self.nxm_game_list.setMaximumHeight(200)
        
        # Add games to list
        for game in games:
            item_text = f"{game.get('Name', 'Unknown')} (AppID: {game.get('AppID', 'Unknown')})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, game.get('AppID'))
            self.nxm_game_list.addItem(item)
        
        self.content_layout.addWidget(self.nxm_game_list)
        
        # Info about auto-detection
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        info_label = QLabel("ℹ️ NXM Handler Auto-Detection")
        info_label.setStyleSheet("color: #4caf50; font-size: 14px; font-weight: bold;")
        info_layout.addWidget(info_label)
        
        auto_info = QLabel("The tool will automatically find nxmhandler.exe from your Mod Organizer 2 installation.\nNo manual selection needed for MO2 games!")
        auto_info.setStyleSheet("color: #b0bec5; font-size: 12px;")
        auto_info.setWordWrap(True)
        info_layout.addWidget(auto_info)
        
        self.content_layout.addLayout(info_layout)
        
        # Optional manual override (initially hidden)
        self.manual_override_layout = QVBoxLayout()
        self.manual_override_layout.setSpacing(10)
        
        # NXM Handler path label
        self.nxm_handler_label = QLabel("Manual Override: Not selected")
        self.nxm_handler_label.setStyleSheet("color: #b0bec5; font-size: 12px;")
        self.manual_override_layout.addWidget(self.nxm_handler_label)
        
        # Button layout for manual selection options
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Select MO2 Folder button
        select_folder_button = QPushButton("Select MO2 Folder")
        select_folder_button.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #1565c0;
            }
        """)
        select_folder_button.clicked.connect(self._select_mo2_folder)
        button_layout.addWidget(select_folder_button)
        
        # Select NXM Handler button
        select_nxm_button = QPushButton("Manually Select nxmhandler.exe")
        select_nxm_button.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:pressed {
                background-color: #ef6c00;
            }
        """)
        select_nxm_button.clicked.connect(self._select_nxm_handler_file)
        button_layout.addWidget(select_nxm_button)
        
        self.manual_override_layout.addLayout(button_layout)
        
        self.content_layout.addLayout(self.manual_override_layout)
        
        # Store NXM handler path
        self.nxm_handler_path = None
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Configure button
        configure_button = QPushButton("Configure NXM Handler")
        configure_button.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        configure_button.clicked.connect(self._configure_nxm_handler)
        button_layout.addWidget(configure_button)
        
        # Back button
        back_button = QPushButton("Back to MO2 Setup")
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: none;
                border-radius: 4px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        back_button.clicked.connect(self._back_to_mo2_setup)
        button_layout.addWidget(back_button)
        
        self.content_layout.addLayout(button_layout)
    
    def _auto_detect_nxm_handler(self, game_name):
        """Auto-detect nxmhandler.exe from MO2 installation"""
        try:
            self.logger.info(f"Auto-detecting nxmhandler.exe for game: {game_name}")
            
            # Get the game's executable path from Steam shortcuts
            games = self.controller.core.steam_utils.get_non_steam_games()
            target_game = None
            
            for game in games:
                if game.get("Name", "").strip() == game_name.strip():
                    target_game = game
                    break
            
            if not target_game:
                self.logger.warning(f"Could not find game data for: {game_name}")
                return None
            
            exe_path = target_game.get("Exe", "")
            if not exe_path:
                self.logger.warning(f"No executable path found for: {game_name}")
                return None
            
            self.logger.info(f"Game executable path: {exe_path}")
            
            # Check if this looks like a ModOrganizer.exe path
            if not exe_path.lower().endswith("modorganizer.exe"):
                self.logger.info(f"Game executable is not ModOrganizer.exe: {exe_path}")
                return None
            
            # Look for nxmhandler.exe in the same directory
            mo2_dir = os.path.dirname(exe_path.strip('"'))
            nxm_handler_path = os.path.join(mo2_dir, "nxmhandler.exe")
            
            if os.path.exists(nxm_handler_path):
                self.logger.info(f"Found nxmhandler.exe at: {nxm_handler_path}")
                return nxm_handler_path
            else:
                self.logger.warning(f"nxmhandler.exe not found at: {nxm_handler_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error auto-detecting nxmhandler.exe: {e}")
            return None

    def _select_mo2_folder(self):
        """Select MO2 folder and auto-detect nxmhandler.exe"""
        mo2_folder = QFileDialog.getExistingDirectory(
            self,
            "Select Mod Organizer 2 Folder",
            str(Path.home())
        )
        
        if mo2_folder:
            # Look for nxmhandler.exe in the selected folder
            nxm_handler_path = os.path.join(mo2_folder, "nxmhandler.exe")
            
            if os.path.exists(nxm_handler_path):
                self.nxm_handler_path = nxm_handler_path
                self.nxm_handler_label.setText(f"NXM Handler Path: {nxm_handler_path}")
                self.nxm_handler_label.setStyleSheet("color: #4caf50; font-size: 12px;")
                
                # Show success message
                QMessageBox.information(
                    self,
                    "NXM Handler Found",
                    f"Successfully found nxmhandler.exe in the selected folder:\n{nxm_handler_path}"
                )
            else:
                # Show error message
                QMessageBox.warning(
                    self,
                    "NXM Handler Not Found",
                    f"Could not find nxmhandler.exe in the selected folder:\n{mo2_folder}\n\nPlease make sure you selected the correct Mod Organizer 2 installation folder."
                )

    def _select_nxm_handler_file(self):
        """Select nxmhandler.exe file"""
        nxm_handler_path = QFileDialog.getOpenFileName(
            self,
            "Select nxmhandler.exe File",
            str(Path.home()),
            "Executable Files (*.exe);;All Files (*)"
        )[0]
        
        if nxm_handler_path:
            self.nxm_handler_path = nxm_handler_path
            self.nxm_handler_label.setText(f"NXM Handler Path: {nxm_handler_path}")
            self.nxm_handler_label.setStyleSheet("color: #4caf50; font-size: 12px;")
    
    def _configure_nxm_handler(self):
        """Configure NXM handler for selected game with auto-detection"""
        current_item = self.nxm_game_list.currentItem()
        if not current_item:
            # Show error dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("No Game Selected")
            msg_box.setText("Please select a game from the list.")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
            return
        
        app_id = current_item.data(Qt.UserRole)
        game_name = current_item.text().split(" (AppID:")[0]
        
        # Try to auto-detect nxmhandler.exe from the MO2 installation
        nxm_handler_path = self._auto_detect_nxm_handler(game_name)
        
        if not nxm_handler_path and not self.nxm_handler_path:
            # Show error dialog with option to manually select
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("NXM Handler Not Found")
            msg_box.setText("Could not automatically find nxmhandler.exe.\n\nThis usually means the selected game is not a Mod Organizer 2 installation.\n\nWould you like to manually select the nxmhandler.exe file?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            
            if msg_box.exec_() == QMessageBox.Yes:
                self._select_nxm_handler_file()
                if not self.nxm_handler_path:
                    return  # User cancelled file selection
                nxm_handler_path = self.nxm_handler_path
            else:
                return
        
        # Use auto-detected path or previously selected path
        if not nxm_handler_path:
            nxm_handler_path = self.nxm_handler_path
        
        # Show progress dialog
        progress = QProgressDialog(f"Configuring smart NXM handler for {game_name}...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(False)
        progress.show()
        
        # Create worker thread
        self.worker = MO2WorkerThread("configure_nxm_handler", 
                                    core=self.controller.core, 
                                    app_id=app_id, 
                                    nxm_handler_path=nxm_handler_path)
        self.worker.finished.connect(lambda result: self._on_nxm_configure_finished(result, progress))
        self.worker.start()
        
    def _on_nxm_configure_finished(self, result, progress):
        """Handle NXM configuration completion"""
        progress.close()
        
        if result.get("success"):
            # Show success dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Success")
            msg_box.setText(result.get("message", "NXM handler configured successfully!"))
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()  # Use exec_() to make it modal
        else:
            # Show error dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Configuration failed:\n{result.get('error', 'Unknown error')}")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()  # Use exec_() to make it modal
        
    def _remove_nxm(self):
        """Remove NXM handler"""
        self.logger.info("Remove NXM clicked")
        
        # Show progress dialog
        progress = QProgressDialog("Removing NXM handler...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(False)
        progress.show()
        
        # Create worker thread
        self.worker = MO2WorkerThread("remove_nxm", core=self.controller.core)
        self.worker.finished.connect(lambda result: self._on_nxm_remove_finished(result, progress))
        self.worker.start()
        
    def _on_nxm_remove_finished(self, result, progress):
        """Handle NXM removal completion"""
        progress.close()
        
        if result.get("success"):
            # Show success dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Success")
            msg_box.setText(result.get("message", "NXM handler removed successfully!"))
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()  # Use exec_() to make it modal
        else:
            # Show error dialog and wait for user to close it
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Error")
            msg_box.setText(f"Removal failed:\n{result.get('error', 'Unknown error')}")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()  # Use exec_() to make it modal
        
    def on_show(self):
        """Called when this view is shown"""
        self.logger.info("Mod Organizer 2 setup view shown")
