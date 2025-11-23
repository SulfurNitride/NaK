"""
Steam installation picker dialog
Allows user to choose which Steam installation to use when multiple are detected
"""

import flet as ft
from src.utils.logger import get_logger
from src.constants import UILimits

logger = get_logger(__name__)


def show_steam_picker(page: ft.Page, installations: list):
    """
    Show dialog allowing user to pick which Steam installation to use

    Args:
        page: Flet page object
        installations: List of tuples (path, activity_score) for each Steam installation
    """
    selected_path = [installations[0][0]]  # Default to most active (first in list)

    def close_dlg(save: bool = True):
        """Close dialog and save preference"""
        if save:
            from src.utils.settings_manager import SettingsManager
            settings = SettingsManager()
            settings.set_steam_path(selected_path[0])

            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Steam installation set to: {selected_path[0]}"),
                bgcolor=ft.Colors.GREEN,
            )
            page.snack_bar.open = True
            logger.info(f"User selected Steam installation: {selected_path[0]}")

        dlg.open = False
        page.update()

    def on_radio_change(e):
        """Handle radio button selection"""
        selected_path[0] = e.control.value
        logger.debug(f"User selected: {selected_path[0]}")

    # Create radio buttons for each Steam installation
    radio_group = ft.RadioGroup(
        content=ft.Column([
            ft.Radio(
                value=path,
                label=f"{path}\n  Activity score: {score}" + (" (Most active)" if i == 0 else ""),
                label_style=ft.TextStyle(size=13)
            ) for i, (path, score) in enumerate(installations)
        ]),
        value=installations[0][0],  # Default to most active
        on_change=on_radio_change
    )

    dlg = ft.AlertDialog(
        title=ft.Text("Multiple Steam Installations Detected", size=20, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column([
                ft.Icon("folder_special", size=64, color=ft.Colors.BLUE),
                ft.Divider(),
                ft.Text(
                    f"NaK detected {len(installations)} Steam installations on your system.",
                    size=16,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Divider(),
                ft.Text(
                    "Please select which one to use:",
                    size=14
                ),
                ft.Divider(),
                radio_group,
                ft.Divider(),
                ft.Text(
                    "The most active installation (based on recent login) is pre-selected.",
                    size=12,
                    color=ft.Colors.GREY_500,
                    italic=True
                ),
                ft.Text(
                    "You can change this later in Settings.",
                    size=11,
                    color=ft.Colors.GREY_600,
                    italic=True
                ),
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.START, scroll=ft.ScrollMode.AUTO),
            width=650,
            height=min(
                UILimits.STEAM_PICKER_MAX_HEIGHT,
                UILimits.STEAM_PICKER_HEIGHT_BASE + len(installations) * UILimits.STEAM_PICKER_HEIGHT_PER_INSTALL
            ),
        ),
        actions=[
            ft.TextButton(
                "Cancel",
                on_click=lambda _: close_dlg(False)
            ),
            ft.ElevatedButton(
                "Use Selected Installation",
                icon="check",
                on_click=lambda _: close_dlg(True),
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE
            ),
        ],
        modal=True,
    )

    page.open(dlg)
