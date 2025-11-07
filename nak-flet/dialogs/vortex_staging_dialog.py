"""
Vortex staging folder configuration dialogs
Helps users configure Vortex to use the correct staging folder paths
"""

import flet as ft
from src.utils.logger import get_logger

logger = get_logger(__name__)


def show_vortex_staging_info(page: ft.Page, show_error_callback, show_info_callback):
    """
    Show Vortex staging folder information
    Detects installed games and displays staging folder configuration dialog

    Args:
        page: Flet page object
        show_error_callback: Function to show error dialogs
        show_info_callback: Function to show info dialogs
    """
    try:
        logger.info("Show Vortex Staging Info button clicked")

        # Use the VortexLinuxFixes to detect games and get paths
        from src.utils.vortex_linux_fixes import VortexLinuxFixes
        from src.utils.steam_utils import SteamUtils

        fixer = VortexLinuxFixes()
        steam_utils = SteamUtils()
        steam_root = steam_utils.get_steam_root()

        if not steam_root:
            show_error_callback("Error", "Could not find Steam installation")
            return

        # Detect installed games
        results = fixer.detect_and_fix_installed_games(steam_root)
        vortex_paths = results.get("vortex_paths", {})

        if not vortex_paths:
            show_info_callback(
                "No Games Found",
                "No Bethesda games detected. Install a Bethesda game (Skyrim, Fallout, etc.) to see staging folder paths."
            )
            return

        # Show the popup with paths
        show_vortex_staging_folder_popup(page, vortex_paths, show_info_callback)

    except Exception as e:
        logger.error(f"Failed to show staging info: {e}")
        show_error_callback("Error", f"Failed to load staging folder information: {str(e)}")


def show_vortex_staging_folder_popup(page: ft.Page, vortex_paths: dict, show_info_callback):
    """
    Show Vortex staging folder configuration popup with copy button

    Args:
        page: Flet page object
        vortex_paths: Dictionary of detected game paths
        show_info_callback: Function to show info dialogs
    """
    def close_dlg(e=None):
        dlg.open = False
        page.update()

    def copy_to_clipboard(path):
        """Copy path to clipboard"""
        page.set_clipboard(path)
        show_info_callback("Copied!", f"Path copied to clipboard:\n{path}")

    # Get the base path from the first game and replace the game ID with {game}
    # Vortex will automatically expand {game} for each game
    if vortex_paths:
        first_game_id = next(iter(vortex_paths.keys()))
        first_path_info = vortex_paths[first_game_id]
        vortex_base_path = first_path_info.get("vortex_path", "")

        # Replace the specific game ID with {game} placeholder
        # e.g., Z:\...\VortexStaging\skyrimse -> Z:\...\VortexStaging\{game}
        if first_game_id in vortex_base_path:
            unified_path = vortex_base_path.replace(first_game_id, "{game}")
        else:
            # Fallback: just append {game}
            unified_path = vortex_base_path.rsplit("\\", 1)[0] + "\\{game}"
    else:
        unified_path = ""

    # Get list of detected games for display
    detected_games = [info.get("game_name", game_id) for game_id, info in vortex_paths.items()]
    games_text = ", ".join(detected_games) if detected_games else "No games detected"

    # Create content
    content_items = [
        ft.Text(
            "WARNING  IMPORTANT: Configure Vortex Staging Folder",
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.ORANGE_400
        ),
        ft.Divider(),
        ft.Text(
            "In Vortex, go to:",
            size=14,
            color=ft.Colors.WHITE70
        ),
        ft.Text(
            "Settings → Mods → Mod Staging Folder",
            size=13,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.LIGHT_BLUE_300
        ),
        ft.Divider(),
        ft.Text("Paste this path:", size=14, weight=ft.FontWeight.BOLD),
        ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text(unified_path, size=13, selectable=True, weight=ft.FontWeight.BOLD),
                    bgcolor=ft.Colors.GREY_900,
                    padding=12,
                    border_radius=6,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.COPY,
                    tooltip="Copy to clipboard",
                    on_click=lambda e: copy_to_clipboard(unified_path),
                    bgcolor=ft.Colors.BLUE_700,
                    icon_size=24,
                ),
            ], spacing=10),
            padding=ft.padding.symmetric(vertical=10),
        ),
        ft.Divider(),
        ft.Text("Note:", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_300),
        ft.Text(
            f"Vortex will automatically create separate folders for each game using the {{game}} placeholder.",
            size=12,
            color=ft.Colors.WHITE60,
        ),
        ft.Container(height=10),
        ft.Text(f"Detected games: {games_text}", size=12, color=ft.Colors.GREEN_300, italic=True),
    ]

    # Create container
    content = ft.Container(
        content=ft.Column(
            content_items,
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
        ),
        width=650,
        height=350,
    )

    dlg = ft.AlertDialog(
        title=ft.Text("Vortex Staging Folder Configuration", size=18, weight=ft.FontWeight.BOLD),
        content=content,
        actions=[
            ft.TextButton("Close", on_click=close_dlg)
        ],
        modal=True,
        on_dismiss=close_dlg,
    )
    page.open(dlg)
