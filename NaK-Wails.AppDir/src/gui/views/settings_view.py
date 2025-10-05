"""
Settings view for NaK
Allows users to configure Wine/Proton paths and preferences
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QCheckBox,
    QComboBox, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from pathlib import Path

from utils.settings_manager import SettingsManager


class SettingsView(QWidget):
    """Settings view for configuring Wine/Proton paths"""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.logger = logging.getLogger(__name__)

        self._create_widgets()
        self._load_current_settings()
        self.logger.info("Settings view created")

    def _create_widgets(self):
        """Create the settings widgets"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Header
        self._create_header(main_layout)

        # Scroll area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #555555;
                border-radius: 8px;
                background-color: #2d2d2d;
            }
        """)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(20)

        # Settings sections
        self._create_proton_settings(scroll_layout)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # Buttons
        self._create_buttons(main_layout)

    def _create_header(self, parent_layout):
        """Create the header section"""
        # Title
        title_label = QLabel("Settings")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 8px;")
        parent_layout.addWidget(title_label)

        # Subtitle
        subtitle_label = QLabel("Configure Wine/Proton paths and preferences")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #90caf9; margin-bottom: 20px;")
        parent_layout.addWidget(subtitle_label)

    def _create_proton_settings(self, parent_layout):
        """Create Wine/Proton configuration section"""
        proton_group = QGroupBox("Wine/Proton Configuration")
        proton_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #ffffff;
                border: 2px solid #555555;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        layout = QFormLayout(proton_group)
        layout.setSpacing(15)

        # Wine/Proton selection (single dropdown with all detected options)
        self.wine_proton_combo = QComboBox()
        self._populate_all_wine_proton_options()
        self.wine_proton_combo.setStyleSheet("""
            QComboBox {
                background-color: #424242;
                border: 2px solid #555555;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 12px;
            }
            QComboBox:focus {
                border-color: #4fc3f7;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
        """)
        self.wine_proton_combo.currentTextChanged.connect(self._on_wine_proton_changed)

        layout.addRow("Wine/Proton:", self.wine_proton_combo)

        # Wine path (read-only, auto-detected)
        self.wine_path_edit = QLineEdit()
        self.wine_path_edit.setReadOnly(True)
        self.wine_path_edit.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                border: 2px solid #555555;
                border-radius: 6px;
                padding: 8px 12px;
                color: #cccccc;
                font-size: 12px;
            }
        """)

        layout.addRow("Path:", self.wine_path_edit)

        # Heroic games option
        self.show_heroic_games_checkbox = QCheckBox("Show Heroic games/prefixes in NXM handler setup")
        self.show_heroic_games_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #424242;
            }
            QCheckBox::indicator:checked {
                background-color: #4fc3f7;
                border-color: #4fc3f7;
            }
            QCheckBox::indicator:checked:after {
                content: "✓";
                color: white;
                font-weight: bold;
            }
        """)
        layout.addRow("", self.show_heroic_games_checkbox)

        parent_layout.addWidget(proton_group)



    def _create_buttons(self, parent_layout):
        """Create action buttons"""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        # Back button
        self.back_button = QPushButton("← Back to Main Menu")
        self.back_button.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
            QPushButton:pressed {
                background-color: #1565c0;
            }
        """)
        self.back_button.clicked.connect(self._go_back)
        button_layout.addWidget(self.back_button)

        # Save button
        self.save_button = QPushButton("Save Settings")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                min-width: 120px;
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
        self.save_button.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_button)

        # Reset button
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:pressed {
                background-color: #ef6c00;
            }
        """)
        self.reset_button.clicked.connect(self._reset_settings)
        button_layout.addWidget(self.reset_button)

        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
            QPushButton:pressed {
                background-color: #424242;
            }
        """)
        cancel_button.clicked.connect(self._cancel)
        button_layout.addWidget(cancel_button)

        button_layout.addStretch()
        parent_layout.addLayout(button_layout)

    def _populate_all_wine_proton_options(self):
        """Populate the main dropdown with all detected Wine/Proton options"""
        try:
            options = []
            
            # Get Wine options
            wine_path = self.controller.core.settings.get_wine_path()
            if wine_path:
                if "wine-tkg" in wine_path.lower():
                    options.append("Wine-TKG")
                else:
                    options.append("Wine")
            
            from utils.steam_shortcut_manager import SteamShortcutManager
            steam_manager = SteamShortcutManager()
            proton_versions = steam_manager._get_all_available_proton_versions()
            
            if proton_versions:
                options.extend(proton_versions)
            
            if options:
                self.wine_proton_combo.addItems(options)
                self.logger.info(f"Found {len(options)} Wine/Proton options: {options}")
            else:
                # Fallback options if nothing detected
                self.wine_proton_combo.addItems(["Wine", "Proton - Experimental"])
                self.logger.warning("No Wine/Proton installations detected - using fallback options")
                
        except Exception as e:
            self.logger.error(f"Failed to populate Wine/Proton options: {e}")
            # Fallback options
            self.wine_proton_combo.addItems(["Wine", "Proton - Experimental"])

    def _load_current_settings(self):
        """Load current settings into the UI"""
        try:
            settings = self.controller.core.settings.get_all_settings()

            # Determine if user has Wine or Proton configured
            proton_path = settings.get("proton_path", "")
            wine_path = settings.get("wine_path", "")
            preferred_version = settings.get("preferred_proton_version", "Proton - Experimental")
            
            # Set the current selection based on saved settings
            if proton_path:
                # Use the preferred version if it exists in the dropdown
                index = self.wine_proton_combo.findText(preferred_version)
                if index >= 0:
                    self.wine_proton_combo.setCurrentIndex(index)
                else:
                    # Fallback to first Proton option
                    for i in range(self.wine_proton_combo.count()):
                        item_text = self.wine_proton_combo.itemText(i)
                        if not item_text in ["Wine", "Wine-TKG"]:
                            self.wine_proton_combo.setCurrentIndex(i)
                            break
                self.wine_path_edit.setText(proton_path)
            elif wine_path:
                # Check if it's Wine-TKG
                if "wine-tkg" in wine_path.lower():
                    wine_option = "Wine-TKG"
                else:
                    wine_option = "Wine"
                
                index = self.wine_proton_combo.findText(wine_option)
                if index >= 0:
                    self.wine_proton_combo.setCurrentIndex(index)
                self.wine_path_edit.setText(wine_path)
            else:
                # Default to first available option
                if self.wine_proton_combo.count() > 0:
                    self.wine_proton_combo.setCurrentIndex(0)
                    self._on_wine_proton_changed(self.wine_proton_combo.currentText())

            # Load Heroic games option
            show_heroic = settings.get("show_heroic_games", False)
            self.show_heroic_games_checkbox.setChecked(show_heroic)

        except Exception as e:
            self.logger.error(f"Failed to load settings: {e}")


    def _on_wine_proton_changed(self, selection):
        """Handle Wine/Proton selection change"""
        if selection in ["Wine", "Wine-TKG"]:
            # Auto-detect Wine path
            auto_wine = self.controller.core.settings.get_wine_path()
            if auto_wine:
                self.wine_path_edit.setText(auto_wine)
            else:
                self.wine_path_edit.clear()
        else:
            # Handle Proton versions (including Heroic)
            self._update_proton_path(selection)

    def _update_proton_path(self, selected_version):
        """Update path for selected Proton version"""
        if selected_version.startswith("Heroic - "):
            # Handle Heroic Proton versions
            actual_version = selected_version.replace("Heroic - ", "")
            # Find Heroic Proton path
            from pathlib import Path
            home_dir = Path.home()
            heroic_proton_paths = [
                home_dir / ".config" / "heroic" / "tools" / "proton" / actual_version,
                home_dir / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic" / "tools" / "proton" / actual_version,
                home_dir / "Games" / "Heroic" / "tools" / "proton" / actual_version
            ]
            
            for heroic_path in heroic_proton_paths:
                if heroic_path.exists():
                    self.wine_path_edit.setText(str(heroic_path))
                    return
            
            # If not found, clear the path
            self.wine_path_edit.clear()
        else:
            # Handle regular Proton versions
            from utils.steam_shortcut_manager import SteamShortcutManager
            steam_manager = SteamShortcutManager()
            proton_path = steam_manager._find_proton_installation(selected_version)
            if proton_path:
                self.wine_path_edit.setText(proton_path)
            else:
                self.wine_path_edit.clear()



    def _save_settings(self):
        """Save the current settings"""
        try:
            # Get current selection
            selection = self.wine_proton_combo.currentText()
            
            if selection in ["Wine", "Wine-TKG"]:
                # Set preferred version to Wine and clear proton path
                self.controller.core.settings.set_preferred_proton_version(selection)
                self.controller.core.settings.set_proton_path("")
            else:
                # Set preferred Proton version (including Heroic)
                self.controller.core.settings.set_preferred_proton_version(selection)
                # Clear wine path since we're using Proton
                self.controller.core.settings.set_wine_path("")

            # Save Heroic games option
            self.controller.core.settings.set_show_heroic_games(self.show_heroic_games_checkbox.isChecked())

            # Auto-detection is always enabled
            self.controller.core.settings.set_auto_detect(True)

            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved successfully!"
            )

        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {str(e)}"
            )

    def _reset_settings(self):
        """Reset settings to defaults"""
        try:
            reply = QMessageBox.question(
                self,
                "Reset Settings",
                "Are you sure you want to reset all settings to defaults?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.controller.core.settings.reset_to_defaults()
                self._load_current_settings()

                QMessageBox.information(
                    self,
                    "Settings Reset",
                    "Settings have been reset to defaults!"
                )

        except Exception as e:
            self.logger.error(f"Failed to reset settings: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to reset settings: {str(e)}"
            )

    def _go_back(self):
        """Go back to main menu"""
        self.controller.show_main_menu()

    def _cancel(self):
        """Cancel and return to main menu"""
        self.controller.show_main_menu()

    def on_show(self):
        """Called when this view is shown"""
        self.logger.info("Settings view shown")
        self._load_current_settings()
