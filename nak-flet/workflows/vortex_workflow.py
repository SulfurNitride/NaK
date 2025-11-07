"""
Vortex Workflow Module

Handles all Vortex Mod Manager installation and setup workflows.
Extracted from main.py to improve code organization and maintainability.
"""

import flet as ft
import threading
import subprocess
from pathlib import Path

# Use relative imports within nak-flet package
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.file_picker_helper import pick_directory
from components.progress_dialog import ProgressDialog
from dialogs.vortex_staging_dialog import show_vortex_staging_info as show_staging_info_dialog, show_vortex_staging_folder_popup as show_staging_popup
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VortexWorkflow:
    """Handles Vortex installation and setup workflows"""

    def __init__(self, page: ft.Page, core, show_error_callback, show_info_callback):
        """
        Initialize Vortex workflow

        Args:
            page: Flet page instance
            core: Core backend instance
            show_error_callback: Callback for showing error dialogs
            show_info_callback: Callback for showing info dialogs
        """
        self.page = page
        self.core = core
        self.show_error = show_error_callback
        self.show_info = show_info_callback

    def install_vortex_dialog(self):
        """Show install Vortex dialog"""
        logger.info("Install Vortex button clicked")

        # Create input fields
        install_path_field = ft.TextField(
            label="Installation Directory",
            hint_text="/home/user/Games/Vortex",
            value=str(Path.home() / "Games" / "Vortex"),
            width=400
        )

        steam_name_field = ft.TextField(
            label="Instance Name",
            hint_text="e.g., Vortex - Skyrim",
            value="Vortex",
            width=400
        )

        def close_dlg(e=None):
            dlg.open = False
            self.page.update()

        def pick_install_path(e):
            """Pick installation path using zenity"""
            logger.info("Browse button clicked - opening folder picker")
            try:
                selected_path = pick_directory(title="Select Vortex Installation Directory")
                if selected_path:
                    install_path_field.value = selected_path
                    self.page.update()
                else:
                    logger.info("User cancelled folder selection")

            except FileNotFoundError:
                logger.error("Zenity not found on system")
                self.show_error("File Browser Not Available",
                               "The file browser (zenity) is not installed.\n\n"
                               "Please install it:\n"
                               "  sudo pacman -S zenity\n\n"
                               "Or manually enter the path.")
            except subprocess.TimeoutExpired:
                logger.warning("Zenity dialog timed out")
            except Exception as e:
                logger.error(f"Error opening folder picker: {e}", exc_info=True)
                self.show_error("Error", f"Could not open folder browser: {e}\n\nPlease enter the path manually.")

        def start_install(e):
            if not install_path_field.value:
                self.show_error("Missing Path", "Please select an installation directory")
                return
            if not steam_name_field.value:
                self.show_error("Missing Name", "Please provide an instance name")
                return

            close_dlg(e)
            self.install_vortex(install_dir=install_path_field.value, custom_name=steam_name_field.value)

        dlg = ft.AlertDialog(
            title=ft.Text("Install Vortex"),
            content=ft.Column([
                ft.Icon("download", size=48, color=ft.Colors.PURPLE),
                ft.Divider(),
                ft.Text("Download and install Vortex Mod Manager", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row([
                    install_path_field,
                    ft.IconButton(icon="folder_open", on_click=pick_install_path, tooltip="Browse")
                ]),
                ft.Divider(),
                steam_name_field,
                ft.Divider(),
                ft.Text("The installation may take several minutes.", color=ft.Colors.GREY_500, size=12),
            ], tight=True, width=500, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            actions=[
                ft.TextButton("Cancel", on_click=close_dlg),
                ft.ElevatedButton("Install", on_click=start_install),
            ],
            on_dismiss=close_dlg,
        )
        self.page.open(dlg)

    def setup_existing_vortex_dialog(self):
        """Show setup existing Vortex dialog"""
        logger.info("Setup existing Vortex button clicked")

        def close_dlg():
            dlg.open = False
            self.page.update()

        # Create text fields for path and name
        path_field = ft.TextField(
            label="Vortex Folder",
            hint_text="/path/to/Vortex",
            width=400,
            read_only=False  # Allow manual entry as fallback
        )
        name_field = ft.TextField(
            label="Installation Name",
            hint_text="e.g., Vortex - Skyrim",
            width=400
        )

        def pick_vortex_path(e):
            """Handle folder picker for Vortex path"""
            logger.info("Browse button clicked - opening folder picker")
            try:
                selected_path = pick_directory(title="Select Vortex Installation Folder")
                if selected_path:
                    logger.info(f"Selected path: {selected_path}")

                    # Validate that Vortex.exe exists
                    vortex_folder = Path(selected_path)
                    vortex_exe = vortex_folder / "Vortex.exe"

                    if vortex_exe.exists():
                        path_field.value = selected_path
                        # Auto-generate a name based on the folder name
                        name_field.value = f"Vortex - {vortex_folder.name}"
                        self.page.update()
                    else:
                        self.show_error("Invalid Vortex Folder",
                                       f"Vortex.exe not found in selected folder.\n\n"
                                       f"Expected: {vortex_exe}\n\n"
                                       f"Please select a valid Vortex installation folder.")
                else:
                    logger.info("User cancelled folder selection")

            except FileNotFoundError:
                logger.error("Zenity not found on system")
                self.show_error("File Browser Not Available",
                               "The file browser (zenity) is not installed.\n\n"
                               "Please install it:\n"
                               "  sudo pacman -S zenity\n\n"
                               "Or manually enter the path to your Vortex folder.")
            except subprocess.TimeoutExpired:
                logger.warning("Zenity dialog timed out")
            except Exception as e:
                logger.error(f"Error opening folder picker: {e}", exc_info=True)
                self.show_error("Error", f"Could not open folder browser: {e}\n\nPlease enter the path manually.")

        def setup_vortex():
            """Setup the existing Vortex installation with terminal output"""
            if not path_field.value:
                self.show_error("Missing Path", "Please select the Vortex installation folder")
                return
            if not name_field.value:
                self.show_error("Missing Name", "Please provide a name for this installation")
                return

            close_dlg()

            # Show progress dialog
            progress = ProgressDialog(
                page=self.page,
                title="Vortex Setup Progress",
                initial_message="Starting Vortex setup...\n",
                color=ft.Colors.PURPLE
            )
            progress.show()

            def run_setup():
                """Run setup in background thread"""
                try:
                    progress.append_log(f"Vortex folder: {path_field.value}")
                    progress.append_log(f"Installation name: {name_field.value}\n")
                    progress.append_log("="*50)

                    # Set up callbacks for logging and progress
                    self.core.vortex.set_log_callback(lambda msg: progress.append_log(msg))
                    self.core.vortex.set_progress_callback(lambda p, d, t: progress.update_progress(int(p)))

                    # Start with some initial progress
                    progress.update_progress(5)

                    # Run the actual setup - backend will send progress updates
                    result = self.core.vortex.setup_existing(path_field.value, name_field.value)

                    # Setup complete
                    if result.get("success"):
                        progress.update_progress(100)
                        progress.append_log("\n" + "="*50)
                        progress.append_log("[OK] Setup completed successfully!")
                        progress.append_log(f"[OK] Vortex '{name_field.value}' configured")
                        progress.append_log(f"[OK] Steam App ID: {result.get('app_id', 'N/A')}")
                        progress.enable_close()
                    else:
                        progress.append_log("\n" + "="*50)
                        progress.append_log(f"[FAILED] Setup failed: {result.get('error', 'Unknown error')}")
                        progress.enable_close()

                except Exception as e:
                    progress.append_log(f"\n[FAILED] Error: {str(e)}")
                    logger.error(f"Setup error: {e}", exc_info=True)
                    progress.enable_close()

            # Run setup in a background thread
            threading.Thread(target=run_setup, daemon=True).start()

        # Create the dialog
        dlg = ft.AlertDialog(
            title=ft.Text("Setup Existing Vortex"),
            content=ft.Column([
                ft.Icon("folder_open", size=48, color=ft.Colors.ORANGE),
                ft.Divider(),
                ft.Text("Register your existing Vortex installation", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row([
                    path_field,
                    ft.IconButton(icon="folder_open", on_click=pick_vortex_path, tooltip="Browse")
                ]),
                ft.Divider(),
                name_field,
                ft.Divider(),
                ft.Text("This will register your existing Vortex installation with NaK",
                       color=ft.Colors.GREY_500, size=12),
            ], tight=True, width=450, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: close_dlg()),
                ft.ElevatedButton("Setup", on_click=lambda _: setup_vortex()),
            ],
            on_dismiss=lambda _: close_dlg(),
        )
        self.page.open(dlg)

    def install_vortex(self, install_dir=None, custom_name=None):
        """Install Vortex with terminal output"""
        # Create progress dialog
        progress = ProgressDialog(
            page=self.page,
            title="Vortex Installation Progress",
            initial_message="Starting Vortex installation...\n",
            color=ft.Colors.PURPLE
        )

        def run_installation():
            """Run installation in background thread"""
            try:
                progress.append_log(f"Installation directory: {install_dir}")
                progress.append_log(f"Instance name: {custom_name}\n")
                progress.append_log("="*50)

                # Set up callbacks for progress and logging
                def log_callback(message):
                    progress.append_log(message)

                def progress_callback(percent, downloaded_bytes, total_bytes):
                    progress.update_progress(int(percent))

                # Install Vortex
                self.core.vortex.set_log_callback(log_callback)
                self.core.vortex.set_progress_callback(progress_callback)

                result = self.core.vortex.download_vortex(install_dir=install_dir, custom_name=custom_name)

                if result.get("success"):
                    progress.update_progress(100)
                    progress.append_log("\n" + "="*50)
                    progress.append_log("[OK] Installation completed successfully!")
                    progress.append_log(f"[OK] Vortex installed to: {result.get('install_dir', 'N/A')}")
                    progress.append_log(f"[OK] Version: {result.get('version', 'N/A')}")

                    # Show Proton-GE info if using standalone mode
                    if result.get('proton_ge_version'):
                        progress.append_log(f"[OK] Proton-GE: {result.get('proton_ge_version')}")
                        progress.append_log(f"[OK] Prefix: {result.get('prefix_path', 'N/A')}")
                        progress.append_log(f"[OK] Launch script: {result.get('launch_script', 'N/A')}")
                    # Show Steam info if using Steam integration (legacy)
                    elif result.get('app_id'):
                        progress.append_log(f"[OK] Steam App ID: {result.get('app_id', 'N/A')}")

                    # Enable close button
                    progress.enable_close()

                    # Show staging folder configuration popup if paths are available
                    linux_fixes = result.get("linux_fixes", {})
                    vortex_paths = linux_fixes.get("results", {}).get("vortex_paths", {})

                    if vortex_paths:
                        self.show_vortex_staging_folder_popup(vortex_paths)

                else:
                    progress.append_log("\n" + "="*50)
                    progress.append_log(f"[FAILED] Installation failed: {result.get('error', 'Unknown error')}")
                    progress.enable_close()

            except Exception as e:
                progress.append_log(f"\n[FAILED] Error: {str(e)}")
                logger.error(f"Installation error: {e}", exc_info=True)
                progress.enable_close()

        # Show progress dialog and start installation
        progress.show()
        threading.Thread(target=run_installation, daemon=True).start()

    def show_vortex_staging_info(self):
        """Show Vortex staging folder information - delegated to dialogs/vortex_staging_dialog.py"""
        show_staging_info_dialog(self.page, self.show_error, self.show_info)

    def show_vortex_staging_folder_popup(self, vortex_paths):
        """Show Vortex staging folder configuration popup - delegated to dialogs/vortex_staging_dialog.py"""
        show_staging_popup(self.page, vortex_paths, self.show_info)
