"""
Main menu view for NaK application
Shows the main menu options
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class MainMenuView(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.logger = logging.getLogger(__name__)
        
        self._create_widgets()
        self.logger.info("Main menu view created")
        
    def _create_widgets(self):
        """Create the main menu widgets"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 60, 60, 60)
        main_layout.setSpacing(40)
        
        # Title
        title_label = QLabel("NaK - Linux Modding Helper")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 10px;")
        main_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Your Linux gaming modding companion")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #90caf9; margin-bottom: 30px;")
        main_layout.addWidget(subtitle_label)
        
        # Introduction text
        intro_text = QLabel("NaK is a modding tool for linux, where it will set up MO2 and dependencies for you to provide the best modding experience on linux.")
        intro_text.setWordWrap(True)
        intro_text.setAlignment(Qt.AlignCenter)
        intro_text.setStyleSheet("""
            color: #b0bec5; 
            font-size: 16px;
            padding: 20px;
            background-color: #2d2d2d;
            border-radius: 8px;
            border: 1px solid #555555;
            margin-bottom: 30px;
        """)
        main_layout.addWidget(intro_text)
        
        # Create horizontal layout for the button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Create the Mod Organizer 2 button
        mo2_button = QPushButton("Setup Mod Organizer 2")
        mo2_button.setStyleSheet("""
            QPushButton {
                background-color: #4fc3f7;
                border: 2px solid #555555;
                border-radius: 12px;
                padding: 20px 40px;
                color: #ffffff;
                font-weight: bold;
                font-size: 16px;
                min-width: 300px;
                min-height: 60px;
            }
            QPushButton:hover {
                background-color: #29b6f6;
                border-color: #4fc3f7;
            }
            QPushButton:pressed {
                background-color: #0288d1;
            }
        """)
        mo2_button.clicked.connect(self.controller.show_mod_managers)
        
        button_layout.addWidget(mo2_button)
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        main_layout.addStretch()
        
    def on_show(self):
        """Called when this view is shown"""
        self.logger.info("Main menu view shown")
