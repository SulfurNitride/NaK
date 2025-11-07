"""
Custom App Bar Component

Provides a custom title bar with drag area and window controls.
Extracted from main.py to improve code organization.
"""

import flet as ft
from constants import APP_VERSION


def create_custom_app_bar(page: ft.Page, show_proton_ge_manager_callback, show_settings_callback, close_app_callback):
    """
    Create custom app bar with drag area and window controls

    Args:
        page: Flet page instance
        show_proton_ge_manager_callback: Callback to show Proton-GE manager
        show_settings_callback: Callback to show settings dialog
        close_app_callback: Callback to close the application

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
                    on_click=lambda _: show_proton_ge_manager_callback(),
                    tooltip="Proton-GE Manager"
                ),
                ft.IconButton(
                    icon="settings",
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda _: show_settings_callback(),
                    tooltip="Settings"
                ),
                ft.IconButton(
                    icon="close",
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda _: close_app_callback(),
                    tooltip="Exit"
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.BLUE_GREY_900,
        height=56,  # Standard AppBar height
    )
