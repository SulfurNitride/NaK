"""
NXM Handler Remove Dialog

Shows confirmation dialog for removing NXM handler configuration.
Extracted from main.py to improve code organization.
"""

import flet as ft
from src.utils.logger import get_logger

logger = get_logger(__name__)


def show_nxm_remove_dialog(page: ft.Page, core, show_error_callback):
    """
    Show dialog for removing NXM handler

    Args:
        page: Flet page instance
        core: Core backend instance
        show_error_callback: Callback for showing error dialogs
    """
    logger.info("Remove NXM Handler button clicked")

    def close_dlg(e=None):
        dlg.open = False
        page.update()

    def perform_removal(e=None):
        """Actually remove the NXM handler"""
        close_dlg()

        # Show progress
        progress_dlg = ft.AlertDialog(
            title=ft.Text("Removing NXM Handler..."),
            content=ft.Column([
                ft.ProgressRing(),
                ft.Text("Removing Nexus Mods handler configuration...")
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )
        page.open(progress_dlg)

        try:
            # Remove NXM handlers
            logger.info("Removing NXM handlers...")
            result = core.remove_nxm_handlers()

            progress_dlg.open = False
            page.dialog = None

            if result.get("success"):
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("NXM handler removed successfully!"),
                    bgcolor=ft.Colors.GREEN,
                )
                page.snack_bar.open = True
                page.update()
            else:
                show_error_callback("Removal Failed", result.get("error", "Failed to remove NXM handler"))

        except Exception as e:
            progress_dlg.open = False
            show_error_callback("Removal Failed", str(e))

    # Simple confirmation dialog
    dlg = ft.AlertDialog(
        title=ft.Text("Remove NXM Handler"),
        content=ft.Column([
            ft.Icon("link_off", size=48, color=ft.Colors.ORANGE),
            ft.Divider(),
            ft.Text("Remove Nexus Mods Handler Configuration", size=16, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text("This will remove the NXM handler configuration from your system.", size=12),
            ft.Text("Your MO2 installation and mods will not be affected.", size=12, color=ft.Colors.GREEN),
        ], tight=True, width=400, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: close_dlg(e)),
            ft.ElevatedButton(
                "Remove Handler",
                on_click=lambda e: perform_removal(e),
                bgcolor=ft.Colors.ORANGE
            ),
        ],
        on_dismiss=lambda e: close_dlg(e),
    )
    page.open(dlg)
