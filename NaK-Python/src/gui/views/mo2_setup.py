"""
MO2 Setup view
Handles MO2 setup and configuration
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QTextEdit, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from ...core.mo2_installer import MO2Installer


class MO2InstallWorker(QThread):
    """Worker thread for MO2 installation with progress updates"""
    
    progress_updated = Signal(int, int, int)  # percent, downloaded_bytes, total_bytes
    log_updated = Signal(str)
    installation_finished = Signal(dict)
    
    def __init__(self, install_dir=None, custom_name=None):
        super().__init__()
        self.install_dir = install_dir
        self.custom_name = custom_name
        self.installer = MO2Installer()
        
    def run(self):
        """Run the MO2 installation in background thread"""
        try:
            self.log_updated.emit("Starting MO2 installation...")
            
            # Set up callbacks
            self.installer.set_progress_callback(self._progress_callback)
            self.installer.set_log_callback(self._log_callback)
            
            # Run the installation
            result = self.installer.download_mo2(
                install_dir=self.install_dir, 
                custom_name=self.custom_name
            )
            
            self.installation_finished.emit(result)
            
        except Exception as e:
            self.installation_finished.emit({
                "success": False,
                "error": str(e)
            })
    
    def _progress_callback(self, percent, downloaded_bytes, total_bytes):
        """Progress callback for download updates"""
        self.progress_updated.emit(percent, downloaded_bytes, total_bytes)
    
    def _log_callback(self, message):
        """Log callback for status updates"""
        self.log_updated.emit(message)


class MO2SetupView(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.logger = logging.getLogger(__name__)
        self.install_worker = None
        
        self._create_widgets()
        self.logger.info("MO2 Setup view created")
        
    def _create_widgets(self):
        """Create the MO2 setup widgets"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(30)
        
        # Header
        self._create_header(main_layout)
        
        # Content area
        self._create_content(main_layout)
        
        # Back button
        self._create_back_button(main_layout)
        
    def _create_header(self, parent_layout):
        """Create the header section"""
        # Title
        title_label = QLabel("MO2 Setup")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 10px;")
        parent_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Configure Mod Organizer 2 for your system")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #90caf9; margin-bottom: 20px;")
        parent_layout.addWidget(subtitle_label)
        
    def _create_content(self, parent_layout):
        """Create the content area"""
        content_frame = QFrame()
        content_frame.setFrameStyle(QFrame.Box)
        content_frame.setLineWidth(1)
        content_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #555555;
                border-radius: 8px;
                background-color: #3d3d3d;
                padding: 20px;
            }
        """)
        
        content_layout = QVBoxLayout(content_frame)
        content_layout.setSpacing(20)
        
        # Status label
        status_label = QLabel("MO2 Setup Status")
        status_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px;")
        content_layout.addWidget(status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready to start...")
        content_layout.addWidget(self.progress_bar)
        
        # Log area
        log_label = QLabel("Setup Log:")
        log_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        content_layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                padding: 8px;
            }
        """)
        content_layout.addWidget(self.log_text)
        
        # Setup button
        self.setup_button = QPushButton("Start MO2 Setup")
        self.setup_button.setStyleSheet("""
            QPushButton {
                background-color: #4fc3f7;
                border: none;
                border-radius: 4px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #29b6f6;
            }
            QPushButton:pressed {
                background-color: #0288d1;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        self.setup_button.clicked.connect(self._start_setup)
        content_layout.addWidget(self.setup_button)
        
        parent_layout.addWidget(content_frame)
        
    def _create_back_button(self, parent_layout):
        """Create the back button"""
        back_button = QPushButton("← Back to MO2 Options")
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
        back_button.clicked.connect(self.controller.show_mod_managers)
        
        # Center the button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(back_button)
        button_layout.addStretch()
        parent_layout.addLayout(button_layout)
        
    def _start_setup(self):
        """Start the MO2 setup process"""
        self.logger.info("Starting MO2 setup")
        
        # Disable setup button during installation
        self.setup_button.setEnabled(False)
        self.setup_button.setText("Installing...")
        
        # Reset progress and log
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Initializing...")
        self.log_text.clear()
        self.log_text.append("Starting MO2 setup process...")
        
        # Create and start worker thread
        self.install_worker = MO2InstallWorker()
        
        # Connect signals
        self.install_worker.progress_updated.connect(self._on_progress_updated)
        self.install_worker.log_updated.connect(self._on_log_updated)
        self.install_worker.installation_finished.connect(self._on_installation_finished)
        
        # Start installation
        self.install_worker.start()
    
    def _on_progress_updated(self, percent, downloaded_bytes, total_bytes):
        """Handle progress updates from worker thread"""
        self.progress_bar.setValue(percent)
        
        # Convert bytes to readable format
        def format_bytes(bytes_val):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f} TB"
        
        # Update progress bar text (only update every 10% to avoid spam)
        if total_bytes > 0 and percent % 10 == 0:
            downloaded_str = format_bytes(downloaded_bytes)
            total_str = format_bytes(total_bytes)
            # Update the progress bar with custom text if supported
            self.progress_bar.setFormat(f"{downloaded_str} / {total_str} ({percent}%)")
        elif total_bytes > 0:
            # Always show current percentage
            self.progress_bar.setFormat(f"{percent}%")
    
    def _on_log_updated(self, message):
        """Handle log updates from worker thread"""
        self.log_text.append(message)
    
    def _on_installation_finished(self, result):
        """Handle installation completion"""
        # Re-enable setup button
        self.setup_button.setEnabled(True)
        self.setup_button.setText("Start MO2 Setup")
        
        if result["success"]:
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("✅ Installation Complete!")
            self.log_text.append("✅ MO2 installation completed successfully!")
            self.log_text.append(f"Message: {result.get('message', 'Installation successful')}")
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("❌ Installation Failed")
            self.log_text.append(f"❌ Installation failed: {result.get('error', 'Unknown error')}")
        
        # Clean up worker
        if self.install_worker:
            self.install_worker.deleteLater()
            self.install_worker = None
        
    def on_show(self):
        """Called when this view is shown"""
        self.logger.info("MO2 Setup view shown")
