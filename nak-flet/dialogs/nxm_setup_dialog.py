"""
NXM Handler Setup Dialog

Shows dialog for setting up NXM handler for mod downloads.
Extracted from main.py to improve code organization.
"""

import flet as ft
from pathlib import Path
from src.utils.logger import get_logger
from utils.file_picker_helper import pick_directory

logger = get_logger(__name__)


def show_nxm_setup_dialog(page: ft.Page, core, games_list, show_error_callback, scan_games_callback):
    """
    Show dialog for setting up NXM handler

    Args:
        page: Flet page instance
        core: Core backend instance
        games_list: List of detected games
        show_error_callback: Callback for showing error dialogs
        scan_games_callback: Callback to rescan for games
    """
    logger.info("Setup NXM handler button clicked")

    def close_dlg(e=None):
        dlg.open = False
        page.update()

    # Get list of games for selection (non-Steam games only)
    all_games = games_list if games_list else []
    # Filter for non-Steam games (Heroic, GOG, EGS, etc.)
    games = [g for g in all_games if g.get('platform', '').lower() != 'steam']

    # Create text field for MO2 folder path (will be auto-populated)
    handler_path_field = ft.TextField(
        label="MO2 Installation Folder (auto-detected or manual)",
        hint_text="Select a game to auto-detect, use Browse, or type path manually",
        width=400,
        read_only=False  # Allow manual entry
    )

    def on_game_selected(e):
        """Auto-populate MO2 folder when game is selected"""
        selected_app_id = game_dropdown.value
        if not selected_app_id or selected_app_id == "none":
            handler_path_field.value = ""
            page.update()
            return

        # Find the selected game in the games list
        selected_game = None
        for game in games:
            if game.get("app_id") == selected_app_id:
                selected_game = game
                break

        if selected_game and selected_game.get("exe_path"):
            # Extract MO2 folder from exe_path
            exe_path = selected_game.get("exe_path", "")
            # Remove quotes if present
            exe_path = exe_path.strip('"')
            # Get parent directory
            mo2_folder = Path(exe_path).parent

            # Validate that nxmhandler.exe exists in this folder
            nxmhandler_path = mo2_folder / "nxmhandler.exe"
            if nxmhandler_path.exists():
                handler_path_field.value = str(mo2_folder)
                logger.info(f"Auto-detected MO2 folder with nxmhandler.exe: {mo2_folder}")
            else:
                handler_path_field.value = ""
                logger.warning(f"MO2 folder detected but nxmhandler.exe not found: {mo2_folder}")
                show_error_callback("NXM Handler Not Found",
                                   f"The selected game's folder does not contain nxmhandler.exe.\n\n"
                                   f"Expected: {nxmhandler_path}\n\n"
                                   f"Please use the Browse button to select the correct MO2 folder.")
        else:
            handler_path_field.value = ""
            logger.warning(f"No exe_path found for selected game: {selected_game}")

        page.update()

    # Create dropdown for game selection with on_change handler
    game_dropdown = ft.Dropdown(
        label="Select Game (Non-Steam only)",
        width=400,
        on_change=on_game_selected,
        options=[
            ft.dropdown.Option(
                key=game.get("app_id", "unknown"),
                text=f"{game.get('name', 'Unknown')} ({game.get('platform', 'Unknown')})"
            ) for game in games[:20]  # Limit to first 20 for UI
        ] if games else [ft.dropdown.Option(key="none", text="No non-Steam games found - scan first")]
    )

    def pick_handler_path(e):
        """Handle folder picker for MO2 installation (manual override)"""
        logger.info("Browse button clicked - opening folder picker")
        try:
            selected_path = pick_directory(title="Select MO2 Installation Folder (Manual Override)")
            if selected_path:
                logger.info(f"User selected MO2 folder: {selected_path}")

                # Validate that nxmhandler.exe exists in the selected folder
                mo2_folder = Path(selected_path)
                nxmhandler_path = mo2_folder / "nxmhandler.exe"

                if nxmhandler_path.exists():
                    handler_path_field.value = selected_path
                    handler_path_field.read_only = False  # Allow manual editing
                    page.update()
                    logger.info(f"Valid MO2 folder selected with nxmhandler.exe: {selected_path}")
                else:
                    show_error_callback("NXM Handler Not Found",
                                       f"nxmhandler.exe not found in selected folder.\n\n"
                                       f"Expected: {nxmhandler_path}\n\n"
                                       f"Please select a valid MO2 installation folder.")
                    logger.warning(f"nxmhandler.exe not found in selected folder: {selected_path}")
            else:
                logger.info("User cancelled folder selection")

        except FileNotFoundError:
            logger.warning("Zenity not found - file picker not available")
            show_error_callback("File Browser Not Available",
                               "The file browser (zenity) is not installed.\n\n"
                               "Please install zenity: sudo pacman -S zenity\n\n"
                               "Or enter the MO2 folder path manually in the text field.")
            # Make the field editable so user can type the path
            handler_path_field.read_only = False
            page.update()
        except Exception as e:
            logger.error(f"Error opening folder browser: {e}", exc_info=True)
            show_error_callback("Error", f"Could not open folder browser: {e}\n\nPlease enter the path manually.")
            # Make the field editable so user can type the path
            handler_path_field.read_only = False
            page.update()

    def configure_handler():
        """Configure the NXM handler"""
        if not game_dropdown.value or game_dropdown.value == "none":
            show_error_callback("No Game Selected", "Please select a non-Steam game or scan for games first")
            return
        if not handler_path_field.value:
            show_error_callback("Missing Path", "MO2 folder path could not be detected. Please use the Browse button to select it manually.")
            return

        # Validate that nxmhandler.exe exists in the selected folder
        mo2_folder = Path(handler_path_field.value)
        nxmhandler_path = mo2_folder / "nxmhandler.exe"
        if not nxmhandler_path.exists():
            show_error_callback("NXM Handler Not Found",
                               f"The selected folder does not contain nxmhandler.exe.\n\n"
                               f"Expected: {nxmhandler_path}\n\n"
                               f"Please select a valid MO2 installation folder.")
            return

        close_dlg()

        # Show progress
        progress_dlg = ft.AlertDialog(
            title=ft.Text("Configuring NXM Handler..."),
            content=ft.Column([
                ft.ProgressRing(),
                ft.Text("Setting up Nexus Mods integration...")
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )
        page.open(progress_dlg)

        try:
            result = core.configure_nxm_handler(game_dropdown.value, handler_path_field.value)
            progress_dlg.open = False
            page.dialog = None

            if result.get("success"):
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("NXM handler configured successfully!"),
                    bgcolor=ft.Colors.GREEN,
                )
                page.snack_bar.open = True
                page.update()
            else:
                show_error_callback("Configuration Failed", result.get("error", "Failed to configure NXM handler"))
        except Exception as e:
            progress_dlg.open = False
            show_error_callback("Configuration Error", str(e))

    def scan_and_refresh():
        """Scan for games and refresh the dropdown"""
        close_dlg()
        scan_games_callback()
        # Re-open the dialog after scan completes
        import threading
        def reopen_after_delay():
            import time
            time.sleep(2)
            show_nxm_setup_dialog(page, core, games_list, show_error_callback, scan_games_callback)
        threading.Thread(target=reopen_after_delay, daemon=True).start()

    dlg = ft.AlertDialog(
        title=ft.Text("Setup NXM Handler (Non-Steam Games)"),
        content=ft.Column([
            ft.Icon("link", size=48, color=ft.Colors.BLUE),
            ft.Divider(),
            ft.Text("Configure Nexus Mods Download Handler", size=16, weight=ft.FontWeight.BOLD),
            ft.Text("For non-Steam games only (Heroic, GOG, etc.)", size=12, color=ft.Colors.ORANGE),
            ft.Divider(),
            game_dropdown,
            ft.Row([
                ft.Text("No games found?"),
                ft.TextButton("Scan for games", on_click=lambda _: scan_and_refresh())
            ]) if not games else ft.Container(),
            ft.Divider(),
            handler_path_field,
            ft.ElevatedButton(
                "Browse Manually (Optional)",
                icon="folder_open",
                on_click=pick_handler_path
            ),
        ], tight=True, width=450, scroll=ft.ScrollMode.AUTO, height=350),
        actions=[
            ft.TextButton("Cancel", on_click=close_dlg),
            ft.ElevatedButton("Configure", on_click=lambda _: configure_handler()),
        ],
        on_dismiss=close_dlg,
    )
    page.open(dlg)
