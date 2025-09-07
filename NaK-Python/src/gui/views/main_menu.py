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
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(30)
        
        # Header section
        self._create_header(main_layout)
        
        # Menu cards section - horizontal layout
        self._create_menu_cards(main_layout)
        
        # Bottom spacer
        main_layout.addStretch()
        
    def _create_header(self, parent_layout):
        """Create the header section"""
        # Title
        title_label = QLabel("NaK - Linux Modding Helper")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #64b5f6; margin-bottom: 10px;")
        parent_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Your Linux gaming modding companion")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #90caf9; margin-bottom: 20px;")
        parent_layout.addWidget(subtitle_label)
        
    def _create_menu_cards(self, parent_layout):
        """Create the menu option cards in horizontal layout"""
        # Menu options
        options = [
            {
                "title": "Mod Organizer 2",
                "description": "Setup and configure Mod Organizer 2 for Linux gaming",
                "action": self.controller.show_mod_managers
            }
        ]
        
        # Create horizontal layout for cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(40)
        
        # Add spacer to center the cards
        cards_layout.addStretch()
        
        # Create cards
        for option in options:
            card = self._create_menu_card(option)
            cards_layout.addWidget(card)
        
        # Add spacer to center the cards
        cards_layout.addStretch()
        
        parent_layout.addLayout(cards_layout)
            
    def _create_menu_card(self, option):
        """Create a single menu card"""
        # Card container
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setLineWidth(1)
        card.setStyleSheet("""
            QFrame {
                border: 1px solid #555555;
                border-radius: 8px;
                background-color: #3d3d3d;
                padding: 20px;
                min-width: 250px;
                max-width: 300px;
            }
            QFrame:hover {
                border-color: #4fc3f7;
                background-color: #4d4d4d;
            }
        """)
        
        # Card layout
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(15)
        
        # Title
        title_label = QLabel(option["title"])
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #ffffff;")
        card_layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(option["description"])
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #b0bec5;")
        card_layout.addWidget(desc_label)
        
        # Button
        button = QPushButton(f"Open {option['title']}")
        button.setStyleSheet("""
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
        """)
        button.clicked.connect(option["action"])
        card_layout.addWidget(button)
        
        return card
        
    def on_show(self):
        """Called when this view is shown"""
        self.logger.info("Main menu view shown")
