"""
MO2 Workflow Module

Handles all MO2 (Mod Organizer 2) installation and setup workflows.
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
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MO2Workflow:
    """Handles MO2 installation and setup workflows"""

    def __init__(self, page: ft.Page, core, show_error_callback, show_info_callback, file_picker_mo2=None):
        """
        Initialize MO2 workflow

        Args:
            page: Flet page instance
            core: Core backend instance
            show_error_callback: Callback for showing error dialogs
            show_info_callback: Callback for showing info dialogs
            file_picker_mo2: MO2 file picker instance (optional)
        """
        self.page = page
        self.core = core
        self.show_error = show_error_callback
        self.show_info = show_info_callback
        self.file_picker_mo2 = file_picker_mo2

    def install_mo2_dialog(self):
        """Show install MO2 dialog"""
        logger.info("Install MO2 button clicked")

        # Create input fields
        install_path_field = ft.TextField(
            label="Installation Directory",
            hint_text="/home/user/modorganizer2",
            value=str(Path.home() / "modorganizer2"),
            width=400
        )

        steam_name_field = ft.TextField(
            label="Instance Name",
            hint_text="e.g., MO2 - Skyrim SE",
            value="Mod Organizer 2",
            width=400
        )

        def close_dlg(e=None):
            dlg.open = False
            self.page.update()

        def pick_install_path(e):
            """Pick installation path using zenity"""
            logger.info("Browse button clicked - opening folder picker")
            try:
                selected_path = pick_directory(title="Select MO2 Installation Directory")
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
            self.install_mo2(install_dir=install_path_field.value, custom_name=steam_name_field.value)

        dlg = ft.AlertDialog(
            title=ft.Text("Install MO2"),
            content=ft.Column([
                ft.Icon("download", size=48, color=ft.Colors.BLUE),
                ft.Divider(),
                ft.Text("Download and install Mod Organizer 2", size=16, weight=ft.FontWeight.BOLD),
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

    def setup_existing_mo2_dialog(self):
        """Show setup existing MO2 dialog"""
        logger.info("Setup existing MO2 button clicked")

        def close_dlg():
            dlg.open = False
            self.page.update()

        # Create text fields for path and name
        path_field = ft.TextField(
            label="MO2 Folder",
            hint_text="/path/to/modorganizer2",
            width=400,
            read_only=False  # Allow manual entry as fallback
        )
        name_field = ft.TextField(
            label="Installation Name",
            hint_text="e.g., MO2 Skyrim",
            width=400
        )

        # FilePicker handler - CORRECT pattern from Flet docs
        def handle_pick(e: ft.FilePickerResultEvent):
            logger.info(f"FilePicker result event received: {e}")
            # Check self.file_picker_mo2.result.path (not e.path!)
            if self.file_picker_mo2 and self.file_picker_mo2.result and self.file_picker_mo2.result.path:
                selected_path = self.file_picker_mo2.result.path
                logger.info(f"FilePicker selected path: {selected_path}")

                # Validate that ModOrganizer.exe exists in the folder
                mo2_folder = Path(selected_path)
                mo2_exe = mo2_folder / "ModOrganizer.exe"

                if mo2_exe.exists():
                    path_field.value = selected_path
                    # Auto-generate a name based on the folder name
                    name_field.value = f"MO2 - {mo2_folder.name}"
                    self.page.update()
                else:
                    self.show_error("Invalid MO2 Folder",
                                   f"ModOrganizer.exe not found in selected folder.\n\n"
                                   f"Expected: {mo2_exe}\n\n"
                                   f"Please select a valid MO2 installation folder.")
            else:
                logger.info("FilePicker returned no path - user likely cancelled")

        # Set the FilePicker result handler for this dialog
        if self.file_picker_mo2:
            self.file_picker_mo2.on_result = handle_pick

        def pick_mo2_path(e):
            """Handle folder picker for MO2 path"""
            logger.info("Browse button clicked - opening folder picker")
            try:
                selected_path = pick_directory(title="Select MO2 Installation Folder")
                if selected_path:
                    logger.info(f"Selected path: {selected_path}")

                    # Validate that ModOrganizer.exe exists
                    mo2_folder = Path(selected_path)
                    mo2_exe = mo2_folder / "ModOrganizer.exe"

                    if mo2_exe.exists():
                        path_field.value = selected_path
                        name_field.value = f"MO2 - {mo2_folder.name}"
                        self.page.update()
                        logger.info(f"Valid MO2 folder selected: {selected_path}")
                    else:
                        logger.warning(f"Invalid MO2 folder - ModOrganizer.exe not found: {mo2_exe}")
                        self.show_error("Invalid MO2 Folder",
                                       f"ModOrganizer.exe not found in selected folder.\n\n"
                                       f"Expected: {mo2_exe}\n\n"
                                       f"Please select a valid MO2 installation folder.")
                else:
                    logger.info("User cancelled folder selection")

            except FileNotFoundError:
                logger.error("Zenity not found on system")
                self.show_error("File Browser Not Available",
                               "The file browser (zenity) is not installed.\n\n"
                               "Please install it:\n"
                               "  sudo pacman -S zenity\n\n"
                               "Or manually enter the path to your MO2 folder.")
            except subprocess.TimeoutExpired:
                logger.warning("Zenity dialog timed out")
            except Exception as e:
                logger.error(f"Error opening folder picker: {e}", exc_info=True)
                self.show_error("Error", f"Could not open folder browser: {e}\n\nPlease enter the path manually.")

        def setup_mo2():
            """Setup the existing MO2 installation with terminal output"""
            if not path_field.value:
                self.show_error("Missing Path", "Please select the MO2 installation folder")
                return
            if not name_field.value:
                self.show_error("Missing Name", "Please provide a name for this installation")
                return

            close_dlg()

            # Show progress dialog
            progress = ProgressDialog(
                page=self.page,
                title="MO2 Setup Progress",
                initial_message="Starting MO2 setup...\n",
                color=ft.Colors.BLUE
            )
            progress.show()

            def run_setup():
                """Run setup in background thread"""
                try:
                    progress.append_log(f"MO2 folder: {path_field.value}")
                    progress.append_log(f"Installation name: {name_field.value}\n")
                    progress.append_log("="*50)

                    # Set up callbacks for logging and progress
                    self.core.mo2.set_log_callback(lambda msg: progress.append_log(msg))
                    self.core.mo2.set_progress_callback(lambda p, d, t: progress.update_progress(int(p)))

                    # Start with some initial progress
                    progress.update_progress(5)

                    # Run the actual setup - backend will send progress updates
                    result = self.core.setup_existing_mo2(path_field.value, name_field.value)

                    # Setup complete
                    if result.get("success"):
                        progress.update_progress(100)
                        progress.append_log("\n" + "="*50)
                        progress.append_log("[OK] Setup completed successfully!")
                        progress.append_log(f"[OK] MO2 '{name_field.value}' configured")
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

            # Start setup in background thread
            threading.Thread(target=run_setup, daemon=True).start()

        dlg = ft.AlertDialog(
            title=ft.Text("Setup Existing MO2"),
            content=ft.Column([
                ft.Icon("folder_open", size=48, color=ft.Colors.BLUE),
                ft.Divider(),
                ft.Text("Import an existing MO2 installation", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                path_field,
                ft.ElevatedButton(
                    "Browse for MO2 Folder",
                    icon="folder_open",
                    on_click=lambda e: pick_mo2_path(e)
                ),
                ft.Divider(),
                name_field,
                ft.Divider(),
                ft.Text("This will register your existing MO2 installation with NaK",
                       color=ft.Colors.GREY_500, size=12),
            ], tight=True, width=450, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: close_dlg()),
                ft.ElevatedButton("Setup", on_click=lambda _: setup_mo2()),
            ],
            on_dismiss=lambda _: close_dlg(),
        )
        self.page.open(dlg)

    def install_mo2(self, install_dir=None, custom_name=None):
        """Install MO2 with terminal output"""
        # Create progress dialog
        progress = ProgressDialog(
            page=self.page,
            title="MO2 Installation Progress",
            initial_message="Starting MO2 installation...\n",
            color=ft.Colors.BLUE
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

                # Install MO2
                self.core.mo2.set_log_callback(log_callback)
                self.core.mo2.set_progress_callback(progress_callback)

                result = self.core.mo2.download_mo2(install_dir=install_dir, custom_name=custom_name)

                if result.get("success"):
                    progress.update_progress(100)
                    progress.append_log("\n" + "="*50)
                    progress.append_log("[OK] Installation completed successfully!")
                    progress.append_log(f"[OK] MO2 installed to: {result.get('install_dir', 'N/A')}")
                    progress.append_log(f"[OK] Version: {result.get('version', 'N/A')}")

                    # Show Proton-GE info if available
                    if result.get('proton_ge_version'):
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
