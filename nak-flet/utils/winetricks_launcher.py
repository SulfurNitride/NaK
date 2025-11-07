"""
Winetricks Launcher Utility

Handles launching winetricks GUI for Wine prefixes.
Extracted from main.py to improve code organization.
"""

import subprocess
import os
import flet as ft
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)


def launch_winetricks_gui(page: ft.Page, prefix):
    """
    Launch winetricks GUI for a specific prefix

    Args:
        page: Flet page instance
        prefix: Dictionary containing prefix info (name, path)
    """
    try:
        # Get paths
        proton_ge_active = Path.home() / "NaK" / "ProtonGE" / "active"
        cache_path = Path.home() / "NaK" / "cache"
        winetricks_path = cache_path / "winetricks"

        # Check if winetricks exists
        if not winetricks_path.exists():
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Winetricks not found in cache. Please run dependency installation first."),
                bgcolor=ft.Colors.RED,
            )
            page.snack_bar.open = True
            page.update()
            return

        # Check if DISPLAY is set (required for GUI)
        if not os.environ.get("DISPLAY"):
            logger.error("DISPLAY environment variable not set - winetricks GUI requires a display")
            page.snack_bar = ft.SnackBar(
                content=ft.Text("DISPLAY not set. Winetricks GUI requires a graphical display."),
                bgcolor=ft.Colors.RED,
            )
            page.snack_bar.open = True
            page.update()
            return

        # Note: zenity is bundled in the AppImage, so no need to check for it

        # Build environment
        env = os.environ.copy()
        env["WINEPREFIX"] = prefix["path"]
        env["WINE"] = str(proton_ge_active / "files" / "bin" / "wine64")
        env["WINESERVER"] = str(proton_ge_active / "files" / "bin" / "wineserver")
        env["W_CACHE"] = str(cache_path)
        env["WINETRICKS_LATEST_VERSION_CHECK"] = "disabled"

        # Ensure DISPLAY is passed through
        if "DISPLAY" in os.environ:
            env["DISPLAY"] = os.environ["DISPLAY"]

        # CRITICAL: Reset LD_LIBRARY_PATH to system-only paths
        # This prevents AppImage libraries from breaking system binaries like /bin/sh
        # See: https://github.com/AppImage/AppImageKit/wiki/Desktop-Linux-Platform-Issues
        env["LD_LIBRARY_PATH"] = "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu"

        # Show notification
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Launching winetricks GUI for {prefix['name']}..."),
            bgcolor=ft.Colors.GREEN,
        )
        page.snack_bar.open = True
        page.update()

        # Launch winetricks GUI in background
        # Don't redirect stderr so user can see errors in terminal
        logger.info(f"Launching winetricks GUI for prefix: {prefix['name']} ({prefix['path']})")
        logger.info(f"Command: {winetricks_path} --gui")
        logger.info(f"WINEPREFIX: {prefix['path']}")
        logger.info(f"WINE: {env['WINE']}")

        process = subprocess.Popen(
            [str(winetricks_path), "--gui"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait a moment to see if it fails immediately
        import time
        time.sleep(0.5)
        poll_result = process.poll()

        if poll_result is not None:
            # Process exited immediately - probably an error
            stdout, stderr = process.communicate()
            error_msg = stderr.decode('utf-8', errors='replace') if stderr else ""
            logger.error(f"Winetricks failed to start. Exit code: {poll_result}")
            if error_msg:
                logger.error(f"Error output: {error_msg}")

            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Winetricks failed to start. Check terminal for details."),
                bgcolor=ft.Colors.RED,
            )
            page.snack_bar.open = True
            page.update()
        else:
            logger.info(f"Winetricks GUI launched successfully (PID: {process.pid})")

    except Exception as e:
        logger.error(f"Failed to launch winetricks GUI: {e}")
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Failed to launch winetricks: {str(e)}"),
            bgcolor=ft.Colors.RED,
        )
        page.snack_bar.open = True
        page.update()
