"""
Unverum Workflow Module

Handles all Unverum Mod Manager installation and setup workflows.
Extracted from main.py to improve code organization and maintainability.
"""

import flet as ft
import threading
import subprocess
import os
from pathlib import Path

# Use relative imports within nak-flet package
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.file_picker_helper import pick_directory
from components.progress_dialog import ProgressDialog
from src.utils.logger import get_logger

logger = get_logger(__name__)


class UnverumWorkflow:
    """Handles Unverum installation and setup workflows"""

    def __init__(self, page: ft.Page, core, show_error_callback, show_info_callback):
        """
        Initialize Unverum workflow

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

    def install_unverum_dialog(self):
        """Show install Unverum dialog"""
        logger.info("Install Unverum button clicked")

        # Create input fields
        install_path_field = ft.TextField(
            label="Installation Directory",
            hint_text="/home/user/Games/Unverum",
            value=str(Path.home() / "Games" / "Unverum"),
            width=400
        )

        instance_name_field = ft.TextField(
            label="Instance Name",
            hint_text="e.g., Unverum",
            value="Unverum",
            width=400
        )

        def close_dlg(e=None):
            dlg.open = False
            self.page.update()

        def pick_install_path(e):
            """Pick installation path"""
            logger.info("Browse button clicked - opening folder picker")
            try:
                selected_path = pick_directory(title="Select Unverum Installation Directory")
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
            if not instance_name_field.value:
                self.show_error("Missing Name", "Please provide an instance name")
                return

            close_dlg(e)
            self.install_unverum(install_dir=install_path_field.value, custom_name=instance_name_field.value)

        dlg = ft.AlertDialog(
            title=ft.Text("Install Unverum"),
            content=ft.Column([
                ft.Icon("download", size=48, color=ft.Colors.TEAL),
                ft.Divider(),
                ft.Text("Download and install Unverum Mod Manager", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row([
                    install_path_field,
                    ft.IconButton(icon="folder_open", on_click=pick_install_path, tooltip="Browse")
                ]),
                ft.Divider(),
                instance_name_field,
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

    def setup_existing_unverum_dialog(self):
        """Show setup existing Unverum dialog"""
        logger.info("Setup existing Unverum button clicked")

        def close_dlg():
            dlg.open = False
            self.page.update()

        # Create text fields for path and name
        path_field = ft.TextField(
            label="Unverum Folder",
            hint_text="/path/to/Unverum",
            width=400,
            read_only=False  # Allow manual entry as fallback
        )
        name_field = ft.TextField(
            label="Installation Name",
            hint_text="e.g., Unverum",
            value="Unverum",
            width=400
        )

        def pick_unverum_path(e):
            """Handle folder picker for Unverum path"""
            logger.info("Browse button clicked - opening folder picker")
            try:
                selected_path = pick_directory(title="Select Unverum Installation Folder")
                if selected_path:
                    logger.info(f"Selected path: {selected_path}")

                    # Validate that Unverum.exe exists
                    unverum_folder = Path(selected_path)
                    unverum_exe = None

                    # Search for Unverum.exe
                    for root, dirs, files in os.walk(selected_path):
                        for file in files:
                            if file.lower() == "unverum.exe":
                                unverum_exe = os.path.join(root, file)
                                break
                        if unverum_exe:
                            break

                    if unverum_exe:
                        path_field.value = selected_path
                        # Auto-generate a name based on the folder name
                        name_field.value = f"Unverum - {unverum_folder.name}"
                        self.page.update()
                    else:
                        self.show_error("Invalid Unverum Folder",
                                       f"Unverum.exe not found in selected folder or its subdirectories.\n\n"
                                       f"Please select a valid Unverum installation folder.")
                else:
                    logger.info("User cancelled folder selection")

            except FileNotFoundError:
                logger.error("Zenity not found on system")
                self.show_error("File Browser Not Available",
                               "The file browser (zenity) is not installed.\n\n"
                               "Please install it:\n"
                               "  sudo pacman -S zenity\n\n"
                               "Or manually enter the path to your Unverum folder.")
            except subprocess.TimeoutExpired:
                logger.warning("Zenity dialog timed out")
            except Exception as e:
                logger.error(f"Error opening folder picker: {e}", exc_info=True)
                self.show_error("Error", f"Could not open folder browser: {e}\n\nPlease enter the path manually.")

        def setup_unverum():
            """Setup the existing Unverum installation with terminal output"""
            if not path_field.value:
                self.show_error("Missing Path", "Please select the Unverum installation folder")
                return
            if not name_field.value:
                self.show_error("Missing Name", "Please provide a name for this installation")
                return

            close_dlg()

            # Show progress dialog
            progress = ProgressDialog(
                page=self.page,
                title="Unverum Setup Progress",
                initial_message="Starting Unverum setup...\n",
                color=ft.Colors.TEAL
            )
            progress.show()

            def run_setup():
                """Run setup in background thread"""
                try:
                    progress.append_log(f"Unverum folder: {path_field.value}")
                    progress.append_log(f"Installation name: {name_field.value}\n")
                    progress.append_log("="*50)

                    # Set up callbacks for logging and progress
                    self.core.unverum.set_log_callback(lambda msg: progress.append_log(msg))
                    self.core.unverum.set_progress_callback(lambda p, d, t: progress.update_progress(int(p)))

                    # Start with some initial progress
                    progress.update_progress(5)

                    # Run the actual setup - backend will send progress updates
                    result = self.core.unverum.setup_existing(path_field.value, name_field.value)

                    # Setup complete
                    if result.get("success"):
                        progress.update_progress(100)
                        progress.append_log("\n" + "="*50)
                        progress.append_log("[OK] Setup completed successfully!")
                        progress.append_log(f"[OK] Unverum '{name_field.value}' configured")
                        progress.append_log(f"[OK] Proton-GE: {result.get('proton_ge_version', 'N/A')}")
                        progress.append_log(f"[OK] Prefix: {result.get('prefix_path', 'N/A')}")
                        progress.append_log(f"[OK] Launch script: {result.get('launch_script', 'N/A')}")
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
            title=ft.Text("Setup Existing Unverum"),
            content=ft.Column([
                ft.Icon("folder_open", size=48, color=ft.Colors.ORANGE),
                ft.Divider(),
                ft.Text("Register your existing Unverum installation", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row([
                    path_field,
                    ft.IconButton(icon="folder_open", on_click=pick_unverum_path, tooltip="Browse")
                ]),
                ft.Divider(),
                name_field,
                ft.Divider(),
                ft.Text("This will create a new Wine prefix and configure Unverum with Proton-GE",
                       color=ft.Colors.GREY_500, size=12),
            ], tight=True, width=450, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: close_dlg()),
                ft.ElevatedButton("Setup", on_click=lambda _: setup_unverum()),
            ],
            on_dismiss=lambda _: close_dlg(),
        )
        self.page.open(dlg)

    def install_unverum(self, install_dir=None, custom_name=None):
        """Install Unverum with terminal output"""
        # Create progress dialog
        progress = ProgressDialog(
            page=self.page,
            title="Unverum Installation Progress",
            initial_message="Starting Unverum installation...\n",
            color=ft.Colors.TEAL
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

                # Install Unverum
                self.core.unverum.set_log_callback(log_callback)
                self.core.unverum.set_progress_callback(progress_callback)

                result = self.core.unverum.download_unverum(install_dir=install_dir, custom_name=custom_name)

                if result.get("success"):
                    progress.update_progress(100)
                    progress.append_log("\n" + "="*50)
                    progress.append_log("[OK] Installation completed successfully!")
                    progress.append_log(f"[OK] Unverum installed to: {result.get('install_dir', 'N/A')}")
                    progress.append_log(f"[OK] Version: {result.get('version', 'N/A')}")
                    progress.append_log(f"[OK] Proton-GE: {result.get('proton_ge_version')}")
                    progress.append_log(f"[OK] Prefix: {result.get('prefix_path', 'N/A')}")
                    progress.append_log(f"[OK] Launch script: {result.get('launch_script', 'N/A')}")

                    # Enable close button
                    progress.enable_close()

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
