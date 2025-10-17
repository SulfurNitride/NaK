"""
Main menu/home view for NaK application
Shows welcome message and quick start information
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSpacerItem, QSizePolicy, QGroupBox
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
        """Create the home view widgets"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 60, 60, 60)
        main_layout.setSpacing(40)

        # Welcome section
        title_label = QLabel("Welcome to NaK")
        title_font = QFont()
        title_font.setPointSize(32)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #4fc3f7; margin-bottom: 10px;")
        main_layout.addWidget(title_label)

        # Subtitle
        subtitle_label = QLabel("Your Linux Gaming Modding Companion")
        subtitle_font = QFont()
        subtitle_font.setPointSize(16)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #90caf9; margin-bottom: 40px;")
        main_layout.addWidget(subtitle_label)

        # Quick start cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(30)

        # Simple Game Modding card
        simple_card = self._create_feature_card(
            "🎮 Simple Game Modding",
            "Apply dependencies and fixes directly to your games without mod managers. Perfect for ReShade, ENB, OptiScaler, and more.",
            "#66bb6a",
            self.controller.show_game_finder
        )
        cards_layout.addWidget(simple_card)

        # MO2 card
        mo2_card = self._create_feature_card(
            "📦 Mod Organizer 2",
            "Set up and manage Mod Organizer 2 for advanced modding. Full support for Bethesda games and more.",
            "#4fc3f7",
            self.controller.show_mod_managers
        )
        cards_layout.addWidget(mo2_card)

        main_layout.addLayout(cards_layout)

        # About section
        about_frame = QFrame()
        about_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 2px solid #555555;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        about_layout = QVBoxLayout(about_frame)

        about_title = QLabel("About NaK")
        about_title.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold;")
        about_layout.addWidget(about_title)

        about_text = QLabel(
            "NaK automatically detects games from Steam, Heroic, and non-Steam sources. "
            "It provides comprehensive dependency management, registry fixes, and prefix configuration "
            "to give you the best modding experience on Linux."
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet("color: #b0bec5; font-size: 14px; line-height: 1.6;")
        about_layout.addWidget(about_text)

        main_layout.addWidget(about_frame)
        main_layout.addStretch()

    def _create_feature_card(self, title, description, color, action):
        """Create a feature card with title, description, and action"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #2d2d2d;
                border: 2px solid {color};
                border-radius: 12px;
                padding: 0px;
            }}
            QFrame:hover {{
                background-color: #353535;
                border-color: {color};
            }}
        """)
        card.setCursor(Qt.PointingHandCursor)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 25, 25, 25)
        card_layout.setSpacing(15)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold; border: none;")
        card_layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #b0bec5; font-size: 14px; line-height: 1.5; border: none;")
        card_layout.addWidget(desc_label)

        card_layout.addStretch()

        # Action button
        action_button = QPushButton("Get Started →")
        action_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {color};
                opacity: 0.8;
            }}
        """)
        action_button.clicked.connect(action)
        card_layout.addWidget(action_button)

        return card

    def on_show(self):
        """Called when this view is shown"""
        self.logger.info("Home view shown")
