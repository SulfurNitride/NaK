"""
Proton Experimental installation dialog
Prompts user to install Proton Experimental via Steam if not found
"""

import flet as ft
import subprocess
from src.utils.logger import get_logger

logger = get_logger(__name__)


def show_proton_install_prompt(page: ft.Page):
    """
    Show dialog prompting user to install Proton Experimental
    Opens Steam to install Proton Experimental (App ID: 1493710)
    """
    def close_dlg(e=None):
        dlg.open = False
        page.update()

    def install_proton(e):
        """Open Steam to install Proton Experimental"""
        try:
            # Use steam://install URL to trigger installation
            subprocess.Popen(["xdg-open", "steam://install/1493710"])
            logger.info("Opened Steam to install Proton Experimental")
            close_dlg()
        except Exception as ex:
            logger.error(f"Failed to open Steam install URL: {ex}")
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Failed to open Steam. Please install Proton Experimental manually."),
                bgcolor=ft.Colors.RED,
            )
            page.snack_bar.open = True
            page.update()

    dlg = ft.AlertDialog(
        title=ft.Text("Proton Experimental Required", size=20, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column([
                ft.Icon("warning", size=64, color=ft.Colors.ORANGE),
                ft.Divider(),
                ft.Text(
                    "NaK requires Proton Experimental to function properly.",
                    size=16,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Divider(),
                ft.Text(
                    "Proton Experimental was not found on your system.",
                    size=14
                ),
                ft.Text(
                    "Click the button below to install it via Steam.",
                    size=14
                ),
                ft.Divider(),
                ft.Text(
                    "Steam will open and begin downloading Proton Experimental (~2GB).",
                    size=12,
                    color=ft.Colors.GREY_500,
                    italic=True
                ),
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=500,
        ),
        actions=[
            ft.ElevatedButton(
                "Install Proton Experimental",
                icon="download",
                on_click=install_proton,
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE
            ),
        ],
        modal=True,
    )

    page.open(dlg)
