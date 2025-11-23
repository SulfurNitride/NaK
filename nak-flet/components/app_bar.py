"""
Custom App Bar Component

Provides a custom title bar with drag area and window controls.
Extracted from main.py to improve code organization.
"""

import flet as ft
from src.constants import APP_VERSION

def create_custom_app_bar(page, on_proton_ge_click, on_settings_click, on_exit_click):
    """
    Create custom app bar with drag area and window controls

    Args:
        page: Flet page instance
        on_proton_ge_click: Callback to show Proton-GE manager
        on_settings_click: Callback to show settings dialog
        on_exit_click: Callback to close the application

    Returns:
        ft.Container: Custom app bar container
    """
    return ft.Container(
        content=ft.Row(
            [
                # Icon (not draggable)
                ft.Container(
                    content=ft.Icon("games", color=ft.Colors.WHITE),
                    padding=ft.padding.only(left=10, right=5),
                ),
                # Draggable area (fills remaining space)
                ft.WindowDragArea(
                    content=ft.Container(
                        content=ft.Text(f"NaK Linux Modding Helper v{APP_VERSION}", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        padding=10,
                    ),
                    expand=True,
                ),
                # Window control buttons (not draggable)
                ft.IconButton(
                    icon="cloud_download",
                    icon_color=ft.Colors.LIGHT_BLUE_300,
                    on_click=lambda _: on_proton_ge_click(),
                    tooltip="Proton-GE Manager"
                ),
                ft.IconButton(
                    icon="settings",
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda _: on_settings_click(),
                    tooltip="Settings"
                ),
                ft.IconButton(
                    icon="close",
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda _: on_exit_click(),
                    tooltip="Exit"
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.BLUE_GREY_900,
        height=56,  # Standard AppBar height
    )
