"""
Main window for NaK application
Handles view switching and main application logic
"""

import sys
import logging
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QStackedWidget, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPalette, QColor, QFont

from .views.main_menu import MainMenuView
from .views.mod_managers import ModOrganizer2View
from .views.mo2_setup import MO2SetupView

class MainWindow(QMainWindow):
    def __init__(self, core):
        super().__init__()
        self.core = core
        self.logger = logging.getLogger(__name__)
        
        # Set up the main window
        self.setWindowTitle("NaK - Linux Modding Helper")
        self.setMinimumSize(1280, 720)
        self.resize(1280, 720)
        
        # Apply dark theme
        self._apply_dark_theme()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create stacked widget for view management
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # Initialize views
        self._create_views()
        
        # Show main menu by default
        self.show_main_menu()
        
        self.logger.info("Main window initialized successfully")
        
    def _apply_dark_theme(self):
        """Apply dark theme to the application"""
        try:
            # Set application palette
            palette = QPalette()
            
            # Dark colors
            dark_bg = QColor(45, 45, 45)
            darker_bg = QColor(35, 35, 35)
            light_text = QColor(255, 255, 255)
            accent_color = QColor(79, 195, 247)  # Blue accent
            
            # Set color roles
            palette.setColor(QPalette.Window, dark_bg)
            palette.setColor(QPalette.WindowText, light_text)
            palette.setColor(QPalette.Base, darker_bg)
            palette.setColor(QPalette.AlternateBase, dark_bg)
            palette.setColor(QPalette.ToolTipBase, dark_bg)
            palette.setColor(QPalette.ToolTipText, light_text)
            palette.setColor(QPalette.Text, light_text)
            palette.setColor(QPalette.Button, dark_bg)
            palette.setColor(QPalette.ButtonText, light_text)
            palette.setColor(QPalette.BrightText, accent_color)
            palette.setColor(QPalette.Link, accent_color)
            palette.setColor(QPalette.Highlight, accent_color)
            palette.setColor(QPalette.HighlightedText, light_text)
            
            # Apply palette
            self.setPalette(palette)
            
            # Set application style sheet for additional styling
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2d2d2d;
                }
                QStackedWidget {
                    background-color: #2d2d2d;
                }
                QLabel {
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #3d3d3d;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 8px 16px;
                    color: #ffffff;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4d4d4d;
                    border-color: #666666;
                }
                QPushButton:pressed {
                    background-color: #2d2d2d;
                }
                QPushButton:disabled {
                    background-color: #2a2a2a;
                    color: #666666;
                }
                QProgressBar {
                    border: 1px solid #555555;
                    border-radius: 4px;
                    text-align: center;
                    background-color: #2d2d2d;
                }
                QProgressBar::chunk {
                    background-color: #4fc3f7;
                    border-radius: 3px;
                }
                QTextEdit {
                    background-color: #2d2d2d;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    color: #ffffff;
                    padding: 8px;
                }
                QFrame {
                    background-color: transparent;
                }
            """)
            
            self.logger.info("Dark theme applied successfully")
            
        except Exception as e:
            self.logger.warning(f"Failed to apply dark theme: {e}")
    
    def _create_views(self):
        """Create and initialize all views"""
        try:
            # Create views
            self.main_menu_view = MainMenuView(self)
            self.mod_managers_view = ModOrganizer2View(self)
            self.mo2_setup_view = MO2SetupView(self)
            
            # Add views to stacked widget
            self.stacked_widget.addWidget(self.main_menu_view)
            self.stacked_widget.addWidget(self.mod_managers_view)
            self.stacked_widget.addWidget(self.mo2_setup_view)
            
            self.logger.info("All views created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create views: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create views: {e}")
    
    def show_main_menu(self):
        """Show the main menu view"""
        try:
            self.stacked_widget.setCurrentWidget(self.main_menu_view)
            self.main_menu_view.on_show()
            self.setWindowTitle("NaK - Linux Modding Helper")
            self.logger.info("Switched to view: main_menu")
        except Exception as e:
            self.logger.error(f"Failed to show main menu: {e}")
    
    def show_mod_managers(self):
        """Show the mod managers view"""
        try:
            self.stacked_widget.setCurrentWidget(self.mod_managers_view)
            self.mod_managers_view.on_show()
            self.setWindowTitle("NaK - Linux Modding Helper - Mod Organizer 2")
            self.logger.info("Switched to view: mod_managers")
        except Exception as e:
            self.logger.error(f"Failed to show mod managers: {e}")
    
    def show_mo2_setup(self):
        """Show the MO2 setup view"""
        try:
            self.stacked_widget.setCurrentWidget(self.mo2_setup_view)
            self.mo2_setup_view.on_show()
            self.logger.info("Switched to view: mo2_setup")
        except Exception as e:
            self.logger.error(f"Failed to show MO2 setup: {e}")
    
    def show_view(self, view_name):
        """Show a specific view by name"""
        view_methods = {
            "main_menu": self.show_main_menu,
            "mod_managers": self.show_mod_managers,
            "mo2_setup": self.show_mo2_setup
        }
        
        if view_name in view_methods:
            view_methods[view_name]()
        else:
            self.logger.error(f"Unknown view: {view_name}")
    
    def closeEvent(self, event):
        """Handle application close event"""
        try:
            self.logger.info("Application closing...")
            event.accept()
        except Exception as e:
            self.logger.error(f"Error during close: {e}")
            event.accept()

def main():
    """Main entry point for the GUI application"""
    try:
        # Check if QApplication already exists
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance()
        if app is None:
            # Create Qt application
            app = QApplication(sys.argv)
            app.setApplicationName("NaK - Linux Modding Helper")
            app.setApplicationVersion("2.0.3")
        
        # Import core here to avoid circular imports
        from ..core.core import Core
        
        # Create core instance
        core = Core()
        
        # Create and show main window
        window = MainWindow(core)
        window.show()
        
        # Start event loop
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        sys.exit(1)
