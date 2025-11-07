"""
About dialog for NaK Linux Modding Helper
Shows version information and features
"""

import flet as ft
from src.utils.logger import get_logger

logger = get_logger(__name__)


def show_about(page: ft.Page, core):
    """Show about dialog with version information and features"""
    logger.info("About button clicked")
    version, date = core.get_version_info()

    def close_dlg(e):
        dlg.open = False
        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text("About NaK Linux Modding Helper"),
        content=ft.Column(
            [
                ft.Icon("games", size=64, color=ft.Colors.BLUE),
                ft.Divider(),
                ft.Text(f"Version {version}", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(f"Released: {date}", color=ft.Colors.GREY_500),
                ft.Divider(),
                ft.Text("A comprehensive tool for managing game mods on Linux"),
                ft.Text("Built with Flet (Flutter for Python)", italic=True),
                ft.Divider(),
                ft.Text("Features:", weight=ft.FontWeight.BOLD),
                ft.Text("• Game detection (Steam, Heroic, GOG)"),
                ft.Text("• Mod Organizer 2 installation"),
                ft.Text("• Automatic dependency management"),
            ],
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        actions=[ft.TextButton("Close", on_click=close_dlg)],
        on_dismiss=close_dlg,
    )
    page.open(dlg)
