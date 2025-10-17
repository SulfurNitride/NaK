"""
Main window for NaK application
Handles view switching and main application logic with sidebar navigation
"""

import sys
import os
import logging
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QMessageBox, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPalette, QColor, QFont, QIcon

from gui.views.main_menu import MainMenuView
from gui.views.mod_managers import ModOrganizer2View
from gui.views.mo2_setup import MO2SetupView
from gui.views.game_finder_view import GameFinderView
from gui.views.settings_view import SettingsView
from src.core.core import Core

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

        # Main horizontal layout (sidebar + content)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create sidebar
        self._create_sidebar(main_layout)

        # Create content area with stacked widget
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Create stacked widget for view management
        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget, 1)

        # Initialize views
        self._create_views()

        # Add content layout to main layout
        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget, 1)

        # Show main menu by default
        self.show_main_menu()

        self.logger.info("Main window initialized successfully")

    def _create_sidebar(self, parent_layout):
        """Create left sidebar navigation"""
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(250)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-right: 2px solid #555555;
            }
        """)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # App title/logo section
        title_widget = QWidget()
        title_widget.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-bottom: 2px solid #4fc3f7;
                padding: 20px;
            }
        """)
        title_layout = QVBoxLayout(title_widget)

        app_title = QLabel("NaK")
        app_title_font = QFont()
        app_title_font.setPointSize(24)
        app_title_font.setBold(True)
        app_title.setFont(app_title_font)
        app_title.setStyleSheet("color: #4fc3f7; border: none; padding: 0;")
        app_title.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(app_title)

        app_subtitle = QLabel("Linux Modding Helper")
        app_subtitle.setStyleSheet("color: #90caf9; font-size: 12px; border: none; padding: 0;")
        app_subtitle.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(app_subtitle)

        sidebar_layout.addWidget(title_widget)

        # Navigation buttons
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(10, 20, 10, 10)
        nav_layout.setSpacing(8)

        # Home button
        self.home_button = self._create_nav_button("🏠 Home", self.show_main_menu)
        nav_layout.addWidget(self.home_button)

        # Simple Game Modding button
        self.simple_modding_button = self._create_nav_button("🎮 Simple Game Modding", self.show_game_finder)
        nav_layout.addWidget(self.simple_modding_button)

        # Mod Organizer 2 button
        self.mo2_button = self._create_nav_button("📦 Mod Organizer 2", self.show_mod_managers)
        nav_layout.addWidget(self.mo2_button)

        # Settings button
        self.settings_button = self._create_nav_button("⚙️ Settings", self.show_settings)
        nav_layout.addWidget(self.settings_button)

        nav_layout.addStretch()
        sidebar_layout.addWidget(nav_widget, 1)

        parent_layout.addWidget(self.sidebar)

    def _create_nav_button(self, text, callback):
        """Create a sidebar navigation button"""
        button = QPushButton(text)
        button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 15px 20px;
                color: #b0bec5;
                font-weight: bold;
                font-size: 14px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
        """)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def _set_active_nav_button(self, active_button):
        """Highlight the active navigation button"""
        # Reset all buttons
        for button in [self.home_button, self.simple_modding_button, self.mo2_button, self.settings_button]:
            button.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 8px;
                    padding: 15px 20px;
                    color: #b0bec5;
                    font-weight: bold;
                    font-size: 14px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #2d2d2d;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #3d3d3d;
                }
            """)

        # Highlight active button
        active_button.setStyleSheet("""
            QPushButton {
                background-color: #4fc3f7;
                border: none;
                border-radius: 8px;
                padding: 15px 20px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #29b6f6;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #0288d1;
            }
        """)

    def show_settings(self):
        """Show the settings view"""
        try:
            self.stacked_widget.setCurrentWidget(self.settings_view)
            self.settings_view.on_show()
            self._set_active_nav_button(self.settings_button)
            self.setWindowTitle("NaK - Settings")
            self.logger.info("Switched to view: settings")
        except Exception as e:
            self.logger.error(f"Failed to show settings: {e}")

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
            self.game_finder_view = GameFinderView(self)
            self.settings_view = SettingsView(self)

            # Add views to stacked widget
            self.stacked_widget.addWidget(self.main_menu_view)
            self.stacked_widget.addWidget(self.mod_managers_view)
            self.stacked_widget.addWidget(self.mo2_setup_view)
            self.stacked_widget.addWidget(self.game_finder_view)
            self.stacked_widget.addWidget(self.settings_view)
            
            self.logger.info("All views created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create views: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create views: {e}")
    
    def show_main_menu(self):
        """Show the main menu view"""
        try:
            self.stacked_widget.setCurrentWidget(self.main_menu_view)
            self.main_menu_view.on_show()
            self._set_active_nav_button(self.home_button)
            self.setWindowTitle("NaK - Home")
            self.logger.info("Switched to view: main_menu")
        except Exception as e:
            self.logger.error(f"Failed to show main menu: {e}")

    def show_mod_managers(self):
        """Show the mod managers view"""
        try:
            self.stacked_widget.setCurrentWidget(self.mod_managers_view)
            self.mod_managers_view.on_show()
            self._set_active_nav_button(self.mo2_button)
            self.setWindowTitle("NaK - Mod Organizer 2")
            self.logger.info("Switched to view: mod_managers")
        except Exception as e:
            self.logger.error(f"Failed to show mod managers: {e}")

    def show_mo2_setup(self):
        """Show the MO2 setup view"""
        try:
            self.stacked_widget.setCurrentWidget(self.mo2_setup_view)
            self.mo2_setup_view.on_show()
            self._set_active_nav_button(self.mo2_button)
            self.setWindowTitle("NaK - MO2 Setup")
            self.logger.info("Switched to view: mo2_setup")
        except Exception as e:
            self.logger.error(f"Failed to show MO2 setup: {e}")

    def show_game_finder(self):
        """Show the Simple Game Modding view"""
        try:
            self.stacked_widget.setCurrentWidget(self.game_finder_view)
            self.game_finder_view.on_show()
            self._set_active_nav_button(self.simple_modding_button)
            self.setWindowTitle("NaK - Simple Game Modding")
            self.logger.info("Switched to view: game_finder (Simple Game Modding)")
        except Exception as e:
            self.logger.error(f"Failed to show Simple Game Modding: {e}")

    def show_view(self, view_name):
        """Show a specific view by name"""
        view_methods = {
            "main_menu": self.show_main_menu,
            "mod_managers": self.show_mod_managers,
            "mo2_setup": self.show_mo2_setup,
            "game_finder": self.show_game_finder,
            "settings": self.show_settings
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
        from core.core import Core
        
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
