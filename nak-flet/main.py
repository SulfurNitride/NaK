#!/usr/bin/env python3
"""
NaK Linux Modding Helper - Flet GUI
Modern, self-contained GUI using Flutter engine
"""

import flet as ft
import sys
import os
from pathlib import Path

# Fix for FilePicker on Linux: unset GTK_PATH if it exists
# This prevents conflicts with snap/flatpak GTK installations
if 'GTK_PATH' in os.environ:
    del os.environ['GTK_PATH']

# Add parent directory to path to import backend
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.core import Core
from src.utils.logger import setup_comprehensive_logging, get_logger

# Setup logging
setup_comprehensive_logging()
logger = get_logger(__name__)


class NaKApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.core = Core()

        # Page configuration
        self.page.title = "NaK Linux Modding Helper"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        self.page.window_width = 1200
        self.page.window_height = 800
        self.page.window_min_width = 800
        self.page.window_min_height = 600

        # Set assets directory
        assets_path = Path(__file__).parent / "assets"
        self.page.assets_dir = str(assets_path)
        logger.info(f"Assets path configured: {self.page.assets_dir}")

        # Current view
        self.current_view = "home"

        # Cached data
        self.games_list = None
        self.selected_manager_type = None  # Currently selected manager type (mo2, vortex)

        # Initialize FilePickers
        self.file_picker_mo2 = ft.FilePicker()
        self.file_picker_install = ft.FilePicker()
        self.file_picker_nxm = ft.FilePicker()
        self.file_picker_proton = ft.FilePicker()

        # Add FilePickers to overlay
        self.page.overlay.extend([
            self.file_picker_mo2,
            self.file_picker_install,
            self.file_picker_nxm,
            self.file_picker_proton
        ])

        # Build UI
        self.build_ui()

        # Scan games in background on startup and every 30 seconds
        import threading
        threading.Thread(target=self.scan_games_background, daemon=True).start()
        threading.Thread(target=self.periodic_game_scan, daemon=True).start()

    def get_installed_proton_versions(self):
        """Detect installed Proton versions from Steam"""
        proton_versions = []
        steam_path = Path.home() / ".local/share/Steam"

        # Check Steam compatibility tools directory (for GE-Proton, etc.)
        compat_dir = steam_path / "compatibilitytools.d"
        if compat_dir.exists():
            for item in compat_dir.iterdir():
                if item.is_dir():
                    # Verify it has a proton executable
                    if (item / "proton").exists() or (item / "compatibilitytool.vdf").exists():
                        proton_versions.append(item.name)

        # Check Steam common directory for official Proton versions
        common_dir = steam_path / "steamapps/common"
        if common_dir.exists():
            for item in common_dir.iterdir():
                if item.is_dir() and item.name.startswith("Proton"):
                    # Verify it has a proton executable
                    if (item / "proton").exists():
                        proton_versions.append(item.name)

        # Remove duplicates and sort
        proton_versions = sorted(set(proton_versions), reverse=True)

        logger.info(f"Detected Proton versions: {proton_versions}")
        return proton_versions if proton_versions else ["Proton - Experimental"]

    def build_ui(self):
        """Build the main UI"""

        # AppBar - set on page instead of adding to layout
        self.page.appbar = ft.AppBar(
            leading=ft.Icon("games"),
            leading_width=40,
            title=ft.Text("NaK Linux Modding Helper", size=20, weight=ft.FontWeight.BOLD),
            center_title=False,
            bgcolor=ft.Colors.BLUE_GREY_900,
            actions=[
                ft.IconButton(icon="settings", on_click=lambda _: self.show_settings(), tooltip="Settings"),
                ft.IconButton(icon="info", on_click=lambda _: self.show_about(), tooltip="About"),
            ],
        )

        # Navigation rail
        rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            destinations=[
                ft.NavigationRailDestination(
                    icon="home_outlined",
                    selected_icon="home",
                    label="Home",
                ),
                ft.NavigationRailDestination(
                    icon="videogame_asset_outlined",
                    selected_icon="videogame_asset",
                    label="Games",
                ),
                ft.NavigationRailDestination(
                    icon="extension_outlined",
                    selected_icon="extension",
                    label="Mod Managers",
                ),
                ft.NavigationRailDestination(
                    icon="build_outlined",
                    selected_icon="build",
                    label="Dependencies",
                ),
            ],
            on_change=self.navigation_changed,
        )

        # Main content area
        self.content_area = ft.Container(
            content=self.get_home_view(),
            expand=True,
            padding=20,
        )

        # Layout
        self.page.add(
            ft.Row(
                [
                    rail,
                    ft.VerticalDivider(width=1),
                    self.content_area,
                ],
                expand=True,
            )
        )

    def navigation_changed(self, e):
        """Handle navigation changes"""
        index = e.control.selected_index
        views = ["home", "games", "mod_managers", "dependencies"]
        self.current_view = views[index]

        # Update content
        if self.current_view == "home":
            self.content_area.content = self.get_home_view()
        elif self.current_view == "games":
            self.content_area.content = self.get_games_view()
        elif self.current_view == "mod_managers":
            self.content_area.content = self.get_mod_managers_view()
        elif self.current_view == "dependencies":
            self.content_area.content = self.get_dependencies_view()

        self.page.update()

    def navigate_to_mod_managers(self):
        """Navigate to mod managers view from home screen"""
        # Find the navigation rail and update its selected index
        for control in self.page.controls:
            if isinstance(control, ft.Row):
                for child in control.controls:
                    if isinstance(child, ft.NavigationRail):
                        child.selected_index = 2  # Mod Managers is at index 2
                        break

        # Update current view and content
        self.current_view = "mod_managers"
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()

    def get_home_view(self):
        """Home view"""
        version, date = self.core.get_version_info()

        # Get game count (cached to avoid slow scans on every view)
        try:
            games = self.core.get_all_games()
            game_count = len(games) if games else 0
        except:
            game_count = 0

        return ft.Column(
            [
                ft.Text("Welcome to NaK Linux Modding Helper", size=32, weight=ft.FontWeight.BOLD),
                ft.Text(f"Version {version} ({date})", size=16, color=ft.Colors.GREY_500),
                ft.Divider(height=40),

                ft.Row(
                    [
                        # Mod Managers card - clickable to go to submenu (keep puzzle piece icon)
                        ft.Card(
                            content=ft.Container(
                                content=ft.ListTile(
                                    leading=ft.Icon("extension", size=48, color=ft.Colors.BLUE_400),
                                    title=ft.Text("Mod Managers", size=20, weight=ft.FontWeight.BOLD),
                                    subtitle=ft.Text("MO2, Vortex (coming soon)\nClick to manage mod managers"),
                                    trailing=ft.Icon("chevron_right", size=30),
                                    on_click=lambda _: self.navigate_to_mod_managers(),
                                ),
                                padding=10,
                            ),
                            width=400,
                        ),

                        # Status card
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column(
                                    [
                                        ft.ListTile(
                                            leading=ft.Icon("info", size=40),
                                            title=ft.Text("System Status", size=20, weight=ft.FontWeight.BOLD),
                                        ),
                                        ft.Divider(),
                                        ft.Text("Dependencies: Ready", color=ft.Colors.GREEN),
                                        ft.Text(f"Games Detected: {game_count}", color=ft.Colors.BLUE),
                                    ],
                                ),
                                padding=10,
                            ),
                            width=400,
                        ),
                    ],
                    wrap=True,
                    spacing=20,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def get_games_view(self):
        """Games view"""
        content = [
            ft.Text("Games", size=32, weight=ft.FontWeight.BOLD),
            ft.Divider(height=20),
            ft.ElevatedButton("Scan for Games", icon="search", on_click=lambda _: self.scan_games()),
            ft.Divider(height=20),
        ]

        if self.games_list:
            # Show games list
            content.append(ft.Text(f"Found {len(self.games_list)} games:", weight=ft.FontWeight.BOLD))
            for game in self.games_list[:50]:  # Limit to first 50
                content.append(
                    ft.ListTile(
                        leading=ft.Icon("videogame_asset"),
                        title=ft.Text(game.get("name", "Unknown")),
                        subtitle=ft.Text(f"{game.get('platform', 'Unknown')} - {game.get('app_id', 'N/A')}"),
                    )
                )
            if len(self.games_list) > 50:
                content.append(ft.Text(f"...and {len(self.games_list) - 50} more", color=ft.Colors.GREY_500))
        else:
            content.append(ft.Text("No games found. Click 'Scan for Games' to search.", color=ft.Colors.GREY_500))

        return ft.Column(
            content,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def get_mod_managers_view(self):
        """Mod Managers view - shows different mod manager types and their actions"""
        if self.selected_manager_type:
            # Show management options for selected manager type
            return self.get_manager_options_view()

        # Show mod manager types grid
        content = [
            ft.Text("Mod Managers", size=32, weight=ft.FontWeight.BOLD),
            ft.Text("Select a mod manager to configure", color=ft.Colors.GREY_500),
            ft.Divider(height=20),
        ]

        # MO2 Card with official icon
        content.append(
            ft.Card(
                content=ft.Container(
                    content=ft.ListTile(
                        leading=ft.Image(
                            src="icons/mo2.png",
                            width=48,
                            height=48,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        title=ft.Text("Mod Organizer 2", size=20, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text("Manage MO2 installation and setup", size=14),
                        trailing=ft.Icon("chevron_right"),
                        on_click=lambda _: self.select_manager_type("mo2"),
                    ),
                    padding=10,
                ),
            )
        )

        # Vortex Card with official icon (placeholder)
        content.append(
            ft.Card(
                content=ft.Container(
                    content=ft.ListTile(
                        leading=ft.Image(
                            src="icons/vortex-official.svg",
                            width=48,
                            height=48,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        title=ft.Text("Vortex", size=20, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text("Coming soon", size=14, color=ft.Colors.GREY_500),
                        trailing=ft.Icon("chevron_right"),
                        on_click=lambda _: self.select_manager_type("vortex"),
                    ),
                    padding=10,
                ),
            )
        )

        return ft.Column(
            content,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def select_manager_type(self, manager_type):
        """Select a mod manager type to view options"""
        self.selected_manager_type = manager_type
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()

    def get_manager_options_view(self):
        """Show management options for selected manager type"""
        manager_type = self.selected_manager_type

        # Get title and details based on type
        if manager_type == "mo2":
            title = "Mod Organizer 2"
            icon = "extension"
            color = ft.Colors.BLUE
        elif manager_type == "vortex":
            title = "Vortex"
            icon = "cyclone"
            color = ft.Colors.PURPLE
        else:
            title = "Mod Manager"
            icon = "help"
            color = ft.Colors.GREY

        content = [
            ft.Row([
                ft.IconButton(
                    icon="arrow_back",
                    tooltip="Back to Mod Managers",
                    on_click=lambda _: self.back_to_manager_types()
                ),
                ft.Text(title, size=32, weight=ft.FontWeight.BOLD),
            ]),
            ft.Divider(height=20),
        ]

        # Show options based on manager type
        if manager_type == "mo2":
            # MO2 Management Options
            content.append(ft.Text("Management Options", size=20, weight=ft.FontWeight.BOLD))
            content.append(ft.Divider(height=10))

            # Install New MO2
            content.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon("download", size=40, color=ft.Colors.BLUE),
                            title=ft.Text("Install New MO2", size=18, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text("Download and install the latest version"),
                            trailing=ft.Icon("chevron_right"),
                            on_click=lambda _: self.install_mo2_dialog(),
                        ),
                        padding=5,
                    ),
                )
            )

            # Setup Existing MO2
            content.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon("folder_open", size=40, color=ft.Colors.ORANGE),
                            title=ft.Text("Setup Existing MO2", size=18, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text("Add an already installed MO2"),
                            trailing=ft.Icon("chevron_right"),
                            on_click=lambda _: self.setup_existing_mo2_dialog(),
                        ),
                        padding=5,
                    ),
                )
            )

            # Setup NXM Handler
            content.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon("link", size=40, color=ft.Colors.GREEN),
                            title=ft.Text("Setup NXM Handler", size=18, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text("Configure Nexus Mods download handler"),
                            trailing=ft.Icon("chevron_right"),
                            on_click=lambda _: self.setup_nxm_handler(),
                        ),
                        padding=5,
                    ),
                )
            )

            # Remove NXM Handler
            content.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon("link_off", size=40, color=ft.Colors.RED),
                            title=ft.Text("Remove NXM Handler", size=18, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text("Remove Nexus Mods handler configuration"),
                            trailing=ft.Icon("chevron_right"),
                            on_click=lambda _: self.remove_mo2_dialog(),
                        ),
                        padding=5,
                    ),
                )
            )

        elif manager_type == "vortex":
            # Vortex placeholder
            content.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(icon, size=64, color=color),
                        ft.Text("Vortex Support Coming Soon", size=20, weight=ft.FontWeight.BOLD),
                        ft.Text("Vortex mod manager support is planned for a future release",
                               color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    padding=40,
                    alignment=ft.alignment.center,
                )
            )

        return ft.Column(content, scroll=ft.ScrollMode.AUTO, expand=True)

    def back_to_manager_types(self):
        """Go back to mod manager types list"""
        self.selected_manager_type = None
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()


    def get_dependencies_view(self):
        """Dependencies view"""
        return ft.Column(
            [
                ft.Text("Dependencies", size=32, weight=ft.FontWeight.BOLD),
                ft.Divider(height=20),
                ft.ElevatedButton("Check Dependencies", icon="check_circle", on_click=lambda _: self.check_deps()),
                ft.Divider(height=20),

                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("System Dependencies:", weight=ft.FontWeight.BOLD),
                            ft.Divider(),
                            ft.ListTile(
                                leading=ft.Icon("check_circle", color=ft.Colors.GREEN),
                                title=ft.Text("Wine / Proton"),
                                subtitle=ft.Text("For running Windows games and tools"),
                            ),
                            ft.ListTile(
                                leading=ft.Icon("check_circle", color=ft.Colors.GREEN),
                                title=ft.Text("Python 3"),
                                subtitle=ft.Text("Runtime environment"),
                            ),
                            ft.ListTile(
                                leading=ft.Icon("check_circle", color=ft.Colors.GREEN),
                                title=ft.Text("Winetricks"),
                                subtitle=ft.Text("Bundled - for installing Windows dependencies"),
                            ),
                        ]),
                        padding=10,
                    ),
                ),

                ft.Divider(height=20),
                ft.Text("All required tools are included with NaK Linux Modding Helper.",
                       color=ft.Colors.GREEN, italic=True),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def scan_games_background(self):
        """Scan for games silently in the background"""
        try:
            games = self.core.get_all_games()
            self.games_list = games
            logger.info(f"Background scan found {len(games)} games")
        except Exception as e:
            logger.error(f"Background game scan failed: {e}")

    def periodic_game_scan(self):
        """Periodically scan for games every 30 seconds"""
        import time
        while True:
            time.sleep(30)  # Wait 30 seconds
            try:
                games = self.core.get_all_games()
                old_count = len(self.games_list) if self.games_list else 0
                self.games_list = games
                new_count = len(games)
                if new_count != old_count:
                    logger.info(f"Periodic scan: Game count changed from {old_count} to {new_count}")
            except Exception as e:
                logger.error(f"Periodic game scan failed: {e}")

    def scan_games(self):
        """Scan for games"""
        # Show progress dialog
        dlg = ft.AlertDialog(
            title=ft.Text("Scanning for games..."),
            content=ft.Column([
                ft.ProgressRing(),
                ft.Text("Please wait, this may take a moment...")
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )
        self.page.open(dlg)

        try:
            games = self.core.get_all_games()
            self.games_list = games  # Store games list
            dlg.open = False
            self.page.dialog = None

            # Refresh the games view
            self.content_area.content = self.get_games_view()
            self.page.update()

            # Show success snackbar
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Found {len(games)} games!"),
                bgcolor=ft.Colors.GREEN,
            )
            self.page.snack_bar.open = True
            self.page.update()
        except Exception as e:
            dlg.open = False
            self.show_error("Scan Failed", str(e))

    def check_deps(self):
        """Check dependencies"""
        # Show progress
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Checking dependencies..."),
            bgcolor=ft.Colors.BLUE,
        )
        self.page.snack_bar.open = True
        self.page.update()

        result = self.core.check_dependencies()

        if result:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("All required dependencies are available!"),
                bgcolor=ft.Colors.GREEN,
            )
            self.page.snack_bar.open = True
            self.page.update()
        else:
            self.show_error("Dependencies Check", "Some dependencies are missing. Check the logs for details.")

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
            label="Steam Shortcut Name",
            hint_text="e.g., MO2 - Skyrim",
            value="Mod Organizer 2",
            width=400
        )

        def close_dlg(e=None):
            dlg.open = False
            self.page.update()

        def pick_install_path(e):
            """Pick installation path using zenity"""
            logger.info("Browse button clicked - opening folder picker with zenity")
            try:
                import subprocess
                import shutil

                # Find zenity - check bundled first, then system
                zenity_path = None

                # Check if running from AppImage (bundled zenity in usr/bin)
                appdir = os.environ.get('APPDIR')
                if appdir:
                    bundled_zenity = Path(appdir) / 'usr' / 'bin' / 'zenity'
                    if bundled_zenity.exists():
                        zenity_path = str(bundled_zenity)
                        logger.info(f"Found bundled zenity in AppImage: {zenity_path}")

                # Fall back to system zenity
                if not zenity_path:
                    zenity_path = shutil.which('zenity')
                    if zenity_path:
                        logger.info(f"Using system zenity: {zenity_path}")

                if not zenity_path:
                    # Try common paths
                    for path in ['/usr/bin/zenity', '/bin/zenity', '/usr/local/bin/zenity']:
                        if Path(path).exists():
                            zenity_path = path
                            break

                if not zenity_path:
                    raise FileNotFoundError("zenity not found")

                logger.info(f"Using zenity at: {zenity_path}")

                # Use zenity with system library paths (escape AppImage isolation)
                env = os.environ.copy()
                env.pop('LD_LIBRARY_PATH', None)
                env.pop('APPIMAGE', None)
                env.pop('APPDIR', None)
                env['PATH'] = '/usr/bin:/bin:/usr/local/bin'

                result = subprocess.run(
                    [zenity_path, '--file-selection', '--directory',
                     '--title=Select MO2 Installation Directory'],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env=env
                )

                logger.info(f"Zenity returned: returncode={result.returncode}, stdout={result.stdout.strip()}, stderr={result.stderr.strip()}")

                if result.returncode == 0 and result.stdout.strip():
                    install_path_field.value = result.stdout.strip()
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
                self.show_error("Missing Name", "Please provide a Steam shortcut name")
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
            if self.file_picker_mo2.result and self.file_picker_mo2.result.path:
                selected_path = self.file_picker_mo2.result.path
                logger.info(f"FilePicker selected path: {selected_path}")

                # Validate that ModOrganizer.exe exists in the folder
                from pathlib import Path
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
        self.file_picker_mo2.on_result = handle_pick

        def pick_mo2_path(e):
            """Handle folder picker for MO2 path using zenity directly"""
            logger.info("Browse button clicked - opening folder picker with zenity")
            try:
                import subprocess
                import shutil

                # Find zenity - check bundled first, then system
                zenity_path = None

                # Check if running from AppImage (bundled zenity in usr/bin)
                appdir = os.environ.get('APPDIR')
                if appdir:
                    bundled_zenity = Path(appdir) / 'usr' / 'bin' / 'zenity'
                    if bundled_zenity.exists():
                        zenity_path = str(bundled_zenity)
                        logger.info(f"Found bundled zenity in AppImage: {zenity_path}")

                # Fall back to system zenity
                if not zenity_path:
                    zenity_path = shutil.which('zenity')
                    if zenity_path:
                        logger.info(f"Using system zenity: {zenity_path}")

                if not zenity_path:
                    # Try common paths
                    for path in ['/usr/bin/zenity', '/bin/zenity', '/usr/local/bin/zenity']:
                        if Path(path).exists():
                            zenity_path = path
                            break

                if not zenity_path:
                    raise FileNotFoundError("zenity not found")

                logger.info(f"Using zenity at: {zenity_path}")

                # Use zenity with system library paths (escape AppImage isolation)
                env = os.environ.copy()
                # Remove AppImage-specific environment variables that interfere with system binaries
                env.pop('LD_LIBRARY_PATH', None)
                env.pop('APPIMAGE', None)
                env.pop('APPDIR', None)
                # Ensure standard system paths
                env['PATH'] = '/usr/bin:/bin:/usr/local/bin'

                result = subprocess.run(
                    [zenity_path, '--file-selection', '--directory',
                     '--title=Select MO2 Installation Folder'],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env=env
                )

                logger.info(f"Zenity returned: returncode={result.returncode}, stdout={result.stdout.strip()}, stderr={result.stderr.strip()}")

                if result.returncode == 0 and result.stdout.strip():
                    selected_path = result.stdout.strip()
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

            # Show terminal dialog
            import threading

            # Create terminal output text field
            terminal_output = ft.TextField(
                value="Starting MO2 setup...\n",
                multiline=True,
                read_only=True,
                min_lines=15,
                max_lines=15,
                text_style=ft.TextStyle(font_family="monospace", size=12),
                bgcolor=ft.Colors.BLACK,
                color=ft.Colors.GREEN_300,
                border_color=ft.Colors.GREY_800,
            )

            # Progress bar
            progress_bar = ft.ProgressBar(width=500, value=0, bgcolor=ft.Colors.GREY_800, color=ft.Colors.BLUE)
            progress_text = ft.Text("0%", size=14, weight=ft.FontWeight.BOLD)

            # Close button (initially disabled)
            close_button = ft.ElevatedButton(
                "Close",
                disabled=True,
                on_click=lambda e: close_setup_dlg()
            )

            def close_setup_dlg():
                setup_dlg.open = False
                self.page.update()

            def append_log(message):
                """Append message to terminal output"""
                terminal_output.value += f"{message}\n"
                self.page.update()

            def update_progress(percent):
                """Update progress bar"""
                progress_bar.value = percent / 100
                progress_text.value = f"{percent}%"
                self.page.update()

            def run_setup():
                """Run setup in background thread"""
                try:
                    append_log(f"MO2 folder: {path_field.value}")
                    append_log(f"Installation name: {name_field.value}\n")
                    append_log("="*50)

                    # Set up callbacks for logging and progress
                    def log_callback(message):
                        append_log(message)

                    def progress_callback(percent, downloaded_bytes, total_bytes):
                        """Update progress bar based on backend updates"""
                        update_progress(int(percent))

                    # Setup MO2 with callbacks
                    self.core.mo2.set_log_callback(log_callback)
                    self.core.mo2.set_progress_callback(progress_callback)

                    # Start with some initial progress
                    update_progress(5)

                    # Run the actual setup - backend will send progress updates
                    result = self.core.setup_existing_mo2(path_field.value, name_field.value)

                    # Setup complete
                    if result.get("success"):
                        update_progress(100)
                        append_log("\n" + "="*50)
                        append_log("✓ Setup completed successfully!")
                        append_log(f"✓ MO2 '{name_field.value}' configured")
                        append_log(f"✓ Steam App ID: {result.get('app_id', 'N/A')}")

                        # Enable close button
                        close_button.disabled = False
                        self.page.update()
                    else:
                        append_log("\n" + "="*50)
                        append_log(f"✗ Setup failed: {result.get('error', 'Unknown error')}")
                        close_button.disabled = False
                        self.page.update()

                except Exception as e:
                    append_log(f"\n✗ Error: {str(e)}")
                    logger.error(f"Setup error: {e}", exc_info=True)
                    close_button.disabled = False
                    self.page.update()

            # Show terminal dialog
            setup_dlg = ft.AlertDialog(
                title=ft.Text("MO2 Setup Progress", size=18, weight=ft.FontWeight.BOLD),
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
            self.page.open(setup_dlg)

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

    def manage_mo2(self):
        """Manage existing MO2 installations"""
        self.show_info("Manage MO2", "MO2 management features coming soon! Use the MO2 tab for installation.")

    def setup_nxm_handler(self):
        """Setup NXM handler for mod downloads"""
        logger.info("Setup NXM handler button clicked")

        def close_dlg(e=None):
            dlg.open = False
            self.page.update()

        # Get list of games for selection (non-Steam games only)
        all_games = self.games_list if self.games_list else []
        # Filter for non-Steam games (Heroic, GOG, EGS, etc.)
        games = [g for g in all_games if g.get('platform', '').lower() != 'steam']

        # Create text field for MO2 folder path (will be auto-populated)
        handler_path_field = ft.TextField(
            label="MO2 Installation Folder (auto-detected)",
            hint_text="Select a game to auto-detect MO2 path",
            width=400,
            read_only=True
        )

        def on_game_selected(e):
            """Auto-populate MO2 folder when game is selected"""
            selected_app_id = game_dropdown.value
            if not selected_app_id or selected_app_id == "none":
                handler_path_field.value = ""
                self.page.update()
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
                from pathlib import Path
                mo2_folder = Path(exe_path).parent

                # Validate that nxmhandler.exe exists in this folder
                nxmhandler_path = mo2_folder / "nxmhandler.exe"
                if nxmhandler_path.exists():
                    handler_path_field.value = str(mo2_folder)
                    logger.info(f"Auto-detected MO2 folder with nxmhandler.exe: {mo2_folder}")
                else:
                    handler_path_field.value = ""
                    logger.warning(f"MO2 folder detected but nxmhandler.exe not found: {mo2_folder}")
                    self.show_error("NXM Handler Not Found",
                                   f"The selected game's folder does not contain nxmhandler.exe.\n\n"
                                   f"Expected: {nxmhandler_path}\n\n"
                                   f"Please use the Browse button to select the correct MO2 folder.")
            else:
                handler_path_field.value = ""
                logger.warning(f"No exe_path found for selected game: {selected_game}")

            self.page.update()

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

        # FilePicker handler
        def handle_pick_nxm(e: ft.FilePickerResultEvent):
            if e.path:
                handler_path_field.value = e.path
                self.page.update()

        # Set the FilePicker result handler for this dialog
        self.file_picker_nxm.on_result = handle_pick_nxm

        def pick_handler_path(e):
            """Handle folder picker for MO2 installation (manual override)"""
            self.file_picker_nxm.get_directory_path(
                dialog_title="Select MO2 Installation Folder (Manual Override)"
            )

        def configure_handler():
            """Configure the NXM handler"""
            if not game_dropdown.value or game_dropdown.value == "none":
                self.show_error("No Game Selected", "Please select a non-Steam game or scan for games first")
                return
            if not handler_path_field.value:
                self.show_error("Missing Path", "MO2 folder path could not be detected. Please use the Browse button to select it manually.")
                return

            # Validate that nxmhandler.exe exists in the selected folder
            from pathlib import Path
            mo2_folder = Path(handler_path_field.value)
            nxmhandler_path = mo2_folder / "nxmhandler.exe"
            if not nxmhandler_path.exists():
                self.show_error("NXM Handler Not Found",
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
            self.page.open(progress_dlg)

            try:
                result = self.core.configure_nxm_handler(game_dropdown.value, handler_path_field.value)
                progress_dlg.open = False
                self.page.dialog = None

                if result.get("success"):
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text("NXM handler configured successfully!"),
                        bgcolor=ft.Colors.GREEN,
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                else:
                    self.show_error("Configuration Failed", result.get("error", "Failed to configure NXM handler"))
            except Exception as e:
                progress_dlg.open = False
                self.show_error("Configuration Error", str(e))

        def scan_and_refresh():
            """Scan for games and refresh the dropdown"""
            close_dlg()
            self.scan_games()
            # Re-open the dialog after scan completes
            import threading
            def reopen_after_delay():
                import time
                time.sleep(2)
                self.setup_nxm_handler()
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
        self.page.open(dlg)

    def remove_mo2_dialog(self):
        """Show remove NXM handler confirmation dialog"""
        logger.info("Remove NXM Handler button clicked")

        def close_dlg(e=None):
            dlg.open = False
            self.page.update()

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
            self.page.open(progress_dlg)

            try:
                # Remove NXM handlers
                logger.info("Removing NXM handlers...")
                result = self.core.remove_nxm_handlers()

                progress_dlg.open = False
                self.page.dialog = None

                if result.get("success"):
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text("NXM handler removed successfully!"),
                        bgcolor=ft.Colors.GREEN,
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                else:
                    self.show_error("Removal Failed", result.get("error", "Failed to remove NXM handler"))

            except Exception as e:
                progress_dlg.open = False
                self.show_error("Removal Failed", str(e))

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
        self.page.open(dlg)

    def install_mo2(self, install_dir=None, custom_name=None):
        """Install MO2 with terminal output"""
        import threading

        # Create terminal output text field
        terminal_output = ft.TextField(
            value="Starting MO2 installation...\n",
            multiline=True,
            read_only=True,
            min_lines=15,
            max_lines=15,
            text_style=ft.TextStyle(font_family="monospace", size=12),
            bgcolor=ft.Colors.BLACK,
            color=ft.Colors.GREEN_300,
            border_color=ft.Colors.GREY_800,
        )

        # Progress bar
        progress_bar = ft.ProgressBar(width=500, value=0, bgcolor=ft.Colors.GREY_800, color=ft.Colors.BLUE)
        progress_text = ft.Text("0%", size=14, weight=ft.FontWeight.BOLD)

        # Close button (initially disabled)
        close_button = ft.ElevatedButton(
            "Close",
            disabled=True,
            on_click=lambda e: close_dlg()
        )

        def close_dlg():
            dlg.open = False
            self.page.update()

        def append_log(message):
            """Append message to terminal output"""
            terminal_output.value += f"{message}\n"
            # Auto-scroll to bottom by updating the control
            self.page.update()

        def update_progress(percent):
            """Update progress bar"""
            progress_bar.value = percent / 100
            progress_text.value = f"{percent}%"
            self.page.update()

        def run_installation():
            """Run installation in background thread"""
            try:
                append_log(f"Installation directory: {install_dir}")
                append_log(f"Steam shortcut name: {custom_name}\n")
                append_log("="*50)

                # Set up callbacks for progress and logging
                def log_callback(message):
                    append_log(message)

                def progress_callback(percent, downloaded_bytes, total_bytes):
                    update_progress(int(percent))

                # Install MO2
                self.core.mo2.set_log_callback(log_callback)
                self.core.mo2.set_progress_callback(progress_callback)

                result = self.core.mo2.download_mo2(install_dir=install_dir, custom_name=custom_name)

                if result.get("success"):
                    update_progress(100)
                    append_log("\n" + "="*50)
                    append_log("✓ Installation completed successfully!")
                    append_log(f"✓ MO2 installed to: {result.get('install_dir', 'N/A')}")
                    append_log(f"✓ Steam App ID: {result.get('app_id', 'N/A')}")
                    append_log(f"✓ Version: {result.get('version', 'N/A')}")

                    # Enable close button
                    close_button.disabled = False
                    self.page.update()
                else:
                    append_log("\n" + "="*50)
                    append_log(f"✗ Installation failed: {result.get('error', 'Unknown error')}")
                    close_button.disabled = False
                    self.page.update()

            except Exception as e:
                append_log(f"\n✗ Error: {str(e)}")
                logger.error(f"Installation error: {e}", exc_info=True)
                close_button.disabled = False
                self.page.update()

        # Show terminal dialog
        dlg = ft.AlertDialog(
            title=ft.Text("MO2 Installation Progress", size=18, weight=ft.FontWeight.BOLD),
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
        self.page.open(dlg)

        # Start installation in background thread
        threading.Thread(target=run_installation, daemon=True).start()

    def show_settings(self):
        """Show settings dialog"""
        logger.info("Settings button clicked")

        # Get current settings
        current_settings = self.core.settings.settings

        # Get installed Proton versions
        installed_protons = self.get_installed_proton_versions()
        current_proton = current_settings.get("preferred_proton_version", installed_protons[0] if installed_protons else "Proton - Experimental")

        # Create input fields
        proton_path_field = ft.TextField(
            label="Custom Proton Path",
            hint_text="/path/to/proton",
            value=current_settings.get("proton_path", ""),
            width=400
        )

        auto_detect_switch = ft.Switch(
            label="Auto-detect Proton",
            value=current_settings.get("auto_detect", True),
            tooltip="Automatically detect Proton installations"
        )

        preferred_proton_dropdown = ft.Dropdown(
            label="Preferred Proton Version",
            width=400,
            value=current_proton if current_proton in installed_protons else installed_protons[0],
            options=[ft.dropdown.Option(version) for version in installed_protons]
        )

        log_level_dropdown = ft.Dropdown(
            label="Log Level",
            width=400,
            value=current_settings.get("log_level", "INFO"),
            options=[
                ft.dropdown.Option("DEBUG"),
                ft.dropdown.Option("INFO"),
                ft.dropdown.Option("WARNING"),
                ft.dropdown.Option("ERROR"),
            ]
        )

        # FilePicker handler
        def handle_pick_proton(e: ft.FilePickerResultEvent):
            if e.path:
                proton_path_field.value = e.path
                self.page.update()

        # Set the FilePicker result handler for this dialog
        self.file_picker_proton.on_result = handle_pick_proton

        def pick_proton_path(e):
            """Pick Proton path using file dialog"""
            self.file_picker_proton.get_directory_path(dialog_title="Select Proton Directory")

        def close_dlg(e=None):
            """Close the dialog"""
            dlg.open = False
            self.page.update()

        def save_settings(e=None):
            """Save settings to file"""
            try:
                # Save Proton settings
                if proton_path_field.value:
                    self.core.settings.set_proton_path(proton_path_field.value)

                self.core.settings.set_auto_detect(auto_detect_switch.value)
                self.core.settings.set_preferred_proton_version(preferred_proton_dropdown.value)

                # Save additional settings directly
                self.core.settings.settings["log_level"] = log_level_dropdown.value
                self.core.settings._save_settings()

                # Update logging level if changed
                if log_level_dropdown.value:
                    import logging
                    logging.getLogger().setLevel(getattr(logging, log_level_dropdown.value))
                    logger.info(f"Log level set to {log_level_dropdown.value}")

                close_dlg()
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Settings saved successfully!"),
                    bgcolor=ft.Colors.GREEN,
                )
                self.page.snack_bar.open = True
                self.page.update()

            except Exception as e:
                self.show_error("Save Failed", str(e))

        def reset_defaults(e=None):
            """Reset settings to defaults"""
            proton_path_field.value = ""
            auto_detect_switch.value = True
            preferred_proton_dropdown.value = installed_protons[0] if installed_protons else "Proton - Experimental"
            log_level_dropdown.value = "INFO"
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Settings"),
            content=ft.Column([
                ft.Icon("settings", size=48, color=ft.Colors.BLUE),
                ft.Divider(),
                ft.Text("Configuration", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(),

                # Proton Settings
                ft.Text("Proton Configuration", weight=ft.FontWeight.BOLD),
                auto_detect_switch,
                ft.Row([
                    proton_path_field,
                    ft.IconButton(icon="folder_open", on_click=pick_proton_path, tooltip="Browse")
                ]),
                preferred_proton_dropdown,

                ft.Divider(),

                # Advanced Settings
                ft.Text("Advanced", weight=ft.FontWeight.BOLD),
                log_level_dropdown,

            ], tight=True, width=500, scroll=ft.ScrollMode.AUTO, height=400),
            actions=[
                ft.TextButton("Reset Defaults", on_click=reset_defaults),
                ft.TextButton("Cancel", on_click=close_dlg),
                ft.ElevatedButton("Save", on_click=save_settings),
            ],
            on_dismiss=close_dlg,
        )

        self.page.open(dlg)

    def show_about(self):
        """Show about dialog"""
        logger.info("About button clicked")
        version, date = self.core.get_version_info()

        def close_dlg(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("About NaK Linux Modding Helper"),
            content=ft.Column(
                [
                    ft.Icon("games", size=64, color=ft.Colors.BLUE),
                    ft.Divider(),
                    ft.Text(f"Version {version}", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Released: {date}", color=ft.Colors.GREY_500),
                    ft.Divider(),
                    ft.Text("A comprehensive tool for managing game mods on Linux"),
                    ft.Text("Built with Flet (Flutter for Python)", italic=True),
                    ft.Divider(),
                    ft.Text("Features:", weight=ft.FontWeight.BOLD),
                    ft.Text("• Game detection (Steam, Heroic, GOG)"),
                    ft.Text("• Mod Organizer 2 installation"),
                    ft.Text("• Automatic dependency management"),
                ],
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            actions=[ft.TextButton("Close", on_click=close_dlg)],
            on_dismiss=close_dlg,
        )
        self.page.open(dlg)

    def show_info(self, title: str, message: str):
        """Show info dialog"""
        def close_dlg(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
            on_dismiss=close_dlg,
        )
        self.page.open(dlg)

    def show_error(self, title: str, message: str):
        """Show error dialog"""
        def close_dlg(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(title, color=ft.Colors.ERROR),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
            on_dismiss=close_dlg,
        )
        self.page.open(dlg)

    def close_dialog(self):
        """Close current dialog"""
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()


def main(page: ft.Page):
    """Main entry point"""
    NaKApp(page)


if __name__ == "__main__":
    ft.app(target=main)
