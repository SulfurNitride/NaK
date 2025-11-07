"""
Save Symlinker Test Dialog

Shows dialog for testing save game symlinker functionality.
Extracted from main.py to improve code organization.
"""

import flet as ft
import threading
from pathlib import Path
from src.utils.logger import get_logger
from components.terminal_output import TerminalOutput

logger = get_logger(__name__)


def show_save_symlinker_test_dialog(page: ft.Page, show_error_callback):
    """
    Show dialog for testing save symlinker

    Args:
        page: Flet page instance
        show_error_callback: Callback for showing error dialogs
    """
    logger.info("Test Save Symlinker button clicked")

    # Import save_symlinker
    try:
        from src.utils.save_symlinker import SaveSymlinker
    except Exception as e:
        show_error_callback("Import Error", f"Failed to load save_symlinker module: {e}")
        return

    def close_dlg(e=None):
        dlg.open = False
        page.update()

    # Create terminal output using component
    terminal = TerminalOutput(initial_text="Initializing Save Symlinker Test...\n")

    close_button = ft.ElevatedButton(
        "Close",
        on_click=close_dlg
    )

    def append_log(message):
        terminal.append_log(message)
        page.update()

    def run_test():
        """Run the save symlinker test"""
        try:
            append_log("="*60)
            append_log("SAVE GAME SYMLINKER TEST")
            append_log("="*60)

            # Initialize SaveSymlinker
            symlinker = SaveSymlinker()
            append_log("\n[OK] SaveSymlinker initialized")

            # List available Bethesda games
            append_log("\nScanning for Bethesda game save locations...")
            append_log("-"*60)

            available_games = symlinker.list_available_games()

            if not available_games:
                append_log("[FAILED] No Bethesda games found")
                append_log("\nInstall a Bethesda game (Skyrim, Fallout, etc.) through Steam")
                return

            installed_count = sum(1 for g in available_games if g.get('installed', False))
            with_saves_count = sum(1 for g in available_games if g['found'])

            append_log(f"\n[OK] Found {installed_count} installed Bethesda game(s)")
            append_log(f"  ({with_saves_count} with existing saves)\n")

            # Show games with existing saves first
            append_log("-"*60)
            append_log("GAMES WITH EXISTING SAVES:")
            append_log("-"*60)
            for game in available_games:
                if game['found']:
                    append_log(f"\n  • {game['name']}")
                    append_log(f"    AppID: {game['appid']}")
                    append_log(f"    Location Type: {game.get('location_type', 'unknown')}")
                    append_log(f"    Save Path: {game['save_path']}")

            # Show installed games without saves
            games_without_saves = [g for g in available_games if g.get('installed', False) and not g['found']]
            if games_without_saves:
                append_log("\n" + "-"*60)
                append_log("INSTALLED GAMES (no saves yet):")
                append_log("-"*60)
                for game in games_without_saves:
                    append_log(f"\n  • {game['name']}")
                    append_log(f"    AppID: {game['appid']}")
                    append_log(f"    Location Type: {game.get('location_type', 'unknown')}")
                    append_log(f"    Expected Save Path: {game['save_path']}")
                    append_log(f"    Status: Ready (will create saves on first game save)")

            # Test creating Game Saves folder
            append_log("\n" + "="*60)
            append_log("TESTING GAME SAVES FOLDER CREATION")
            append_log("="*60)

            # Use a test MO2 path
            test_mo2_path = Path.home() / "modorganizer2" / "instances" / "Default"
            append_log(f"\nTest MO2 path: {test_mo2_path}")

            # Create test directory structure
            test_mo2_path.mkdir(parents=True, exist_ok=True)

            # Create Game Saves folder
            append_log("\nCreating 'Game Saves' folder...")
            game_saves_folder = symlinker.create_mo2_game_saves_folder(test_mo2_path)
            append_log(f"[OK] Created: {game_saves_folder}")

            # Test symlinking for each found game
            append_log("\n" + "="*60)
            append_log("TESTING SAVE GAME SYMLINKS")
            append_log("="*60)

            success_count = 0
            skipped_count = 0

            for game in available_games:
                if not game.get('installed', False):
                    continue

                game_name = game['name']
                append_log(f"\n➤ Processing {game_name}...")

                try:
                    # Skip games without saves or save paths
                    if not game['save_path']:
                        append_log(f"  ⊘ Skipped (could not determine save location)")
                        skipped_count += 1
                        continue

                    original_save_path = Path(game['save_path'])

                    if not original_save_path.exists():
                        append_log(f"  ⊘ Skipped (save directory will be created on first save)")
                        skipped_count += 1
                        continue

                    # Create symlink to MO2 Game Saves folder
                    success = symlinker.symlink_save_to_mo2_folder(
                        game_name,
                        original_save_path,
                        game_saves_folder
                    )

                    if success:
                        append_log(f"  [OK] Symlink created successfully!")
                        append_log(f"    Target: {game_saves_folder / game_name.replace(':', '').replace('/', '-')}")
                        append_log(f"    Points to: {original_save_path}")
                        success_count += 1
                    else:
                        append_log(f"  [FAILED] Failed to create symlink")

                except Exception as e:
                    append_log(f"  [FAILED] Error: {e}")
                    logger.error(f"Error processing {game_name}: {e}", exc_info=True)

            # Summary
            append_log("\n" + "="*60)
            append_log("TEST SUMMARY")
            append_log("="*60)
            append_log(f"Installed games: {installed_count}")
            append_log(f"Symlinks created: {success_count}")
            append_log(f"Skipped (no saves yet): {skipped_count}")
            append_log(f"\nGame Saves folder: {game_saves_folder}")

            if success_count > 0:
                append_log("\nYou can now access your game saves from:")
                append_log(f"  {game_saves_folder}")

            if skipped_count > 0:
                append_log(f"\nNote: {skipped_count} game(s) don't have saves yet.")
                append_log("Play and save the game at least once, then run this test again.")

            append_log("\n[OK] Test completed successfully!")

        except Exception as e:
            append_log(f"\n[FAILED] Test failed: {e}")
            logger.error(f"Save symlinker test error: {e}", exc_info=True)

    dlg = ft.AlertDialog(
        title=ft.Text("Save Game Symlinker Test", size=18, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column([
                ft.Text(
                    "This will test creating symlinks for Bethesda game saves",
                    size=14,
                    color=ft.Colors.GREY_400
                ),
                ft.Divider(),
                terminal.get_control(),
            ], tight=True),
            width=700,
            height=500,
        ),
        actions=[close_button],
        modal=True,
    )
    page.open(dlg)

    # Run test in background thread
    threading.Thread(target=run_test, daemon=True).start()
