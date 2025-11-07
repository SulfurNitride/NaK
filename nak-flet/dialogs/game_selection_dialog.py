"""
Game selection dialog with dependency installation
Allows users to select multiple games and install dependencies to them
"""

import flet as ft
import threading
from src.utils.logger import get_logger

logger = get_logger(__name__)


def show_game_selection_dialog(page: ft.Page, games_list, show_error_callback, core):
    """
    Show dialog to select games for dependency installation

    Args:
        page: Flet page object
        games_list: List of all detected games
        show_error_callback: Function to show error dialogs
        core: Core object for dependency installation
    """
    # Create checkboxes for ALL games (no deduplication)
    all_game_checkboxes = []
    for game in games_list:  # Show ALL games, not just first 30
        # Create unique label showing platform and app_id to differentiate duplicates
        app_id = game.get('app_id', 'N/A')
        platform = game.get('platform', 'Unknown')
        name = game.get('name', 'Unknown')

        # More detailed label to distinguish between Steam and non-Steam versions
        label = f"{name} ({platform} - {app_id})"

        checkbox = ft.Checkbox(
            label=label,
            value=False
        )
        all_game_checkboxes.append((checkbox, game))

    # Filtered checkboxes (initially all)
    filtered_checkboxes = all_game_checkboxes.copy()

    # Search field
    search_field = ft.TextField(
        label="Search games",
        hint_text="Type to filter...",
        prefix_icon="search",
        width=450,
    )

    # Container for checkboxes
    checkbox_container = ft.Column(
        [checkbox for checkbox, _ in filtered_checkboxes],
        scroll=ft.ScrollMode.AUTO,
        height=400,
    )

    def filter_games(e):
        """Filter games based on search text"""
        search_text = search_field.value.lower() if search_field.value else ""

        # Filter checkboxes
        filtered = []
        for checkbox, game in all_game_checkboxes:
            game_name = game.get('name', '').lower()
            platform = game.get('platform', '').lower()
            app_id = str(game.get('app_id', '')).lower()

            if (search_text in game_name or
                search_text in platform or
                search_text in app_id):
                filtered.append((checkbox, game))

        # Update container
        checkbox_container.controls = [checkbox for checkbox, _ in filtered]
        page.update()

    search_field.on_change = filter_games

    def close_dlg(e=None):
        dlg.open = False
        page.update()

    def apply_to_selected(e=None):
        # Get selected games from ALL checkboxes (not just filtered)
        selected_games = [game for checkbox, game in all_game_checkboxes if checkbox.value]

        if not selected_games:
            show_error_callback("No Selection", "Please select at least one game")
            return

        close_dlg()
        install_dependencies_to_games(page, selected_games)

    def select_all(e):
        # Select all VISIBLE (filtered) games
        for checkbox, game in all_game_checkboxes:
            if checkbox in checkbox_container.controls:
                checkbox.value = True
        page.update()

    def select_none(e):
        # Deselect all games
        for checkbox, _ in all_game_checkboxes:
            checkbox.value = False
        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text("Select Games for Dependencies"),
        content=ft.Container(
            content=ft.Column([
                ft.Text(f"Select games to apply dependencies ({len(games_list)} total)", weight=ft.FontWeight.BOLD),
                search_field,
                ft.Row([
                    ft.TextButton("Select All", on_click=select_all),
                    ft.TextButton("Select None", on_click=select_none),
                ]),
                ft.Divider(),
                checkbox_container,
            ], tight=True),
            width=550,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=close_dlg),
            ft.ElevatedButton("Apply Dependencies", on_click=apply_to_selected),
        ],
        on_dismiss=close_dlg,
    )
    page.open(dlg)


def install_dependencies_to_games(page: ft.Page, selected_games):
    """
    Install dependencies to selected games with progress dialog

    Args:
        page: Flet page object
        selected_games: List of selected game dictionaries
    """
    # Create progress UI
    terminal_output = ft.TextField(
        value="Starting dependency installation...\n",
        multiline=True,
        read_only=True,
        min_lines=15,
        max_lines=15,
        text_style=ft.TextStyle(font_family="monospace", size=12),
        bgcolor=ft.Colors.BLACK,
        color=ft.Colors.GREEN_300,
        border_color=ft.Colors.GREY_800,
    )

    progress_bar = ft.ProgressBar(width=500, value=0, bgcolor=ft.Colors.GREY_800, color=ft.Colors.BLUE)
    progress_text = ft.Text("0%", size=14, weight=ft.FontWeight.BOLD)

    close_button = ft.ElevatedButton(
        "Close",
        disabled=True,
        on_click=lambda e: close_dlg()
    )

    def close_dlg():
        install_dlg.open = False
        page.update()

    def append_log(message):
        terminal_output.value += f"{message}\n"
        page.update()

    def update_progress(percent):
        progress_bar.value = percent / 100
        progress_text.value = f"{percent}%"
        page.update()

    def run_installation():
        try:
            total_games = len(selected_games)
            successful = 0

            # Calculate total steps: each game has ~15 dependencies + registry + dotnet
            steps_per_game = 17  # 15 dependencies + 1 registry + 1 dotnet
            total_steps = total_games * steps_per_game
            current_step = 0

            for i, game in enumerate(selected_games):
                game_name = game.get('name', 'Unknown')
                game_platform = game.get('platform', 'Unknown')

                append_log(f"\n{'='*50}")
                append_log(f"[{i+1}/{total_games}] Processing: {game_name} ({game_platform})")
                append_log(f"{'='*50}")

                try:
                    # Use comprehensive_game_manager to apply dependencies
                    from src.utils.comprehensive_game_manager import ComprehensiveGameManager
                    from src.utils.game_finder import GameInfo

                    game_manager = ComprehensiveGameManager()

                    # Convert dict to GameInfo object
                    game_info = GameInfo(
                        name=game.get('name', 'Unknown'),
                        path=game.get('path', ''),
                        platform=game.get('platform', 'Unknown'),
                        app_id=game.get('app_id'),
                        exe_path=game.get('exe_path'),
                        install_dir=game.get('install_dir'),
                    )

                    # Set up progress callback for real-time updates
                    def progress_callback(message):
                        nonlocal current_step
                        current_step += 1
                        percent = int((current_step / total_steps) * 100)
                        update_progress(min(percent, 99))  # Cap at 99% until all games done
                        append_log(f"  {message}")

                    # Set the callback on the game manager
                    game_manager.set_progress_callback(progress_callback)

                    result = game_manager.setup_specific_game_complete(game_info)

                    if result.success:
                        append_log(f"[OK] {game_name}: Dependencies applied successfully")
                        successful += 1
                    else:
                        append_log(f"[FAILED] {game_name}: Failed - {result.error}")

                except Exception as e:
                    append_log(f"[FAILED] {game_name}: Error - {str(e)}")
                    logger.error(f"Error installing dependencies for {game_name}: {e}", exc_info=True)

                # Ensure progress shows completion for this game
                current_step = (i + 1) * steps_per_game
                update_progress(int((current_step / total_steps) * 100))

            # Final summary
            append_log(f"\n{'='*50}")
            append_log(f"Installation Complete!")
            append_log(f"{'='*50}")
            append_log(f"[OK] Successful: {successful}/{total_games}")
            append_log(f"[FAILED] Failed: {total_games - successful}/{total_games}")

            close_button.disabled = False
            page.update()

        except Exception as e:
            append_log(f"\n[FAILED] Fatal Error: {str(e)}")
            logger.error(f"Fatal error in dependency installation: {e}", exc_info=True)
            close_button.disabled = False
            page.update()

    install_dlg = ft.AlertDialog(
        title=ft.Text("Installing Dependencies", size=18, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column([
                ft.Row([progress_bar, progress_text], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(),
                terminal_output,
            ], tight=True, scroll=ft.ScrollMode.AUTO),
            width=600,
            height=400,
        ),
        actions=[close_button],
        modal=True,
    )
    page.open(install_dlg)

    # Start installation in background thread
    threading.Thread(target=run_installation, daemon=True).start()
