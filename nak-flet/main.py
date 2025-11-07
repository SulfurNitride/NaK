#!/usr/bin/env python3
"""
NaK Linux Modding Helper - Flet GUI
Modern, self-contained GUI using Flutter engine
"""

import sys
import os
import shutil
from pathlib import Path

# Clear Flet cache before loading Flet
# This ensures we always use the bundled flet-desktop-light
flet_cache_dir = Path.home() / ".flet" / "bin"
if flet_cache_dir.exists():
    try:
        shutil.rmtree(flet_cache_dir)
        print(f"Cleared Flet cache: {flet_cache_dir}")
    except Exception as e:
        print(f"Warning: Could not clear Flet cache: {e}")

# Now import Flet
import flet as ft
import logging

# Fix for FilePicker on Linux: unset GTK_PATH if it exists
# This prevents conflicts with snap/flatpak GTK installations
if 'GTK_PATH' in os.environ:
    del os.environ['GTK_PATH']

# Add parent directory to path to import backend
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.core import Core
from src.utils.logger import setup_comprehensive_logging, get_logger

# Import utilities
from utils.file_picker_helper import pick_directory
from utils.game_scanner import GameScanner
from utils.winetricks_launcher import launch_winetricks_gui as launch_winetricks

# Import components
from components.progress_dialog import ProgressDialog
from components.app_bar import create_custom_app_bar
from components.terminal_output import TerminalOutput

# Import workflows
from workflows.mo2_workflow import MO2Workflow
from workflows.vortex_workflow import VortexWorkflow
from workflows.unverum_workflow import UnverumWorkflow

# Import views
from views.getting_started_view import get_getting_started_view
from views.home_view import get_home_view
from views.games_view import get_games_view
from views.mod_managers_view import get_mod_managers_view
from views.manager_options_view import get_manager_options_view
from views.simple_game_modding_view import get_simple_game_modding_view
from views.instance_management_view import get_instance_management_view
from views.wineprefix_manager_view import get_wineprefix_manager_view

# Import dialogs
from dialogs.info_dialog import show_info as show_info_dialog
from dialogs.error_dialog import show_error as show_error_dialog
from dialogs.cache_config_dialog import show_cache_config_dialog as display_cache_config_dialog
from dialogs.about_dialog import show_about as show_about_dialog
from dialogs.steam_picker_dialog import show_steam_picker as show_steam_picker_dialog
from dialogs.proton_install_dialog import show_proton_install_prompt
from dialogs.vortex_staging_dialog import show_vortex_staging_info as show_vortex_staging_info_dialog
from dialogs.nxm_manager_dialog import show_nxm_manager as show_nxm_manager_dialog
from dialogs.game_selection_dialog import show_game_selection_dialog as show_game_selection_dialog_func
from dialogs.settings_dialog import show_settings as show_settings_dialog
from dialogs.proton_ge_dialog import show_proton_ge_manager as show_ge_manager_dialog
from dialogs.nxm_test_dialog import show_nxm_test_dialog
from dialogs.nxm_setup_dialog import show_nxm_setup_dialog
from dialogs.nxm_remove_dialog import show_nxm_remove_dialog
from dialogs.save_symlinker_test_dialog import show_save_symlinker_test_dialog

# Import constants
from constants import WindowDefaults, DialogDelays, ScanningConfig, UILimits, FeatureFlags

# Setup logging with INFO level (shows important events, errors, warnings)
# Users can change to DEBUG in Settings for detailed troubleshooting
setup_comprehensive_logging(level=logging.INFO)
logger = get_logger(__name__)


def log_system_information():
    """Log system information on startup for debugging"""
    try:
        # Use a fresh logger instance to ensure it's available
        info_logger = get_logger("system_info")
        info_logger.info("=" * 80)
        info_logger.info("SYSTEM INFORMATION")
        info_logger.info("=" * 80)

        # Detect Linux distro
        distro_name = "Unknown"
        distro_version = ""
        try:
            if Path("/etc/os-release").exists():
                with open("/etc/os-release", "r") as f:
                    os_release = {}
                    for line in f:
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            os_release[key] = value.strip('"')
                    distro_name = os_release.get("NAME", "Unknown")
                    distro_version = os_release.get("VERSION", "")
        except Exception as e:
            info_logger.debug(f"Failed to read /etc/os-release: {e}")

        info_logger.info(f"Linux Distribution: {distro_name} {distro_version}".strip())

        # Detect Steam installation
        try:
            from src.utils.steam_utils import SteamUtils
            steam_utils = SteamUtils()
            steam_path = steam_utils.get_steam_root()

            # Determine Steam type (Flatpak or Native)
            steam_type = "Native"
            if ".var/app/com.valvesoftware.Steam" in steam_path:
                steam_type = "Flatpak"

            info_logger.info(f"Steam Type: {steam_type}")
            info_logger.info(f"Steam Path: {steam_path}")

            # Check Proton-GE location (NaK's primary Proton)
            try:
                from src.utils.proton_ge_manager import ProtonGEManager
                ge_manager = ProtonGEManager()
                active_version = ge_manager.get_active_version()
                if active_version:
                    active_path = ge_manager.get_active_proton_path()
                    info_logger.info(f"Proton-GE Active: {active_version}")
                    info_logger.info(f"Proton-GE Path: {active_path.parent if active_path else 'N/A'}")
                else:
                    info_logger.warning("Proton-GE not installed - install via Proton-GE Manager")

                # List installed versions
                installed = ge_manager.get_installed_versions()
                if installed:
                    info_logger.info(f"Proton-GE Versions: {', '.join(installed[:3])}{'...' if len(installed) > 3 else ''}")
            except Exception as ge_error:
                info_logger.warning(f"Failed to check Proton-GE: {ge_error}")

        except Exception as e:
            info_logger.error(f"Failed to detect Steam information: {e}")

        info_logger.info("=" * 80)

    except Exception as e:
        info_logger.error(f"Failed to log system information: {e}")


class NaKApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.core = Core()

        # Clean up orphaned NXM scripts and marker files on startup
        try:
            from src.utils.nxm_handler_manager import NXMHandlerManager
            nxm_manager = NXMHandlerManager()
            cleanup_result = nxm_manager.cleanup_orphaned_scripts()
            logger.info(f"NXM cleanup: Scripts ({cleanup_result['scripts_scanned']} scanned, "
                       f"{cleanup_result['scripts_removed']} removed), "
                       f"Markers ({cleanup_result['markers_scanned']} scanned, "
                       f"{cleanup_result['markers_removed']} removed)")
        except Exception as e:
            logger.warning(f"Failed to cleanup orphaned NXM items on startup: {e}")

        # Page configuration
        self.page.title = "NaK Linux Modding Helper"

        # Set window icon
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "doro.png")
        if os.path.exists(icon_path):
            self.page.window.icon = icon_path

        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        self.page.window_width = WindowDefaults.WIDTH
        self.page.window_height = WindowDefaults.HEIGHT
        self.page.window_min_width = WindowDefaults.MIN_WIDTH
        self.page.window_min_height = WindowDefaults.MIN_HEIGHT

        # Explicitly enable window controls
        self.page.window.minimizable = False
        self.page.window.maximizable = True
        self.page.window.resizable = True
        self.page.window.prevent_close = False

        # Hide the native title bar
        self.page.window.title_bar_hidden = True

        # Add close button handler
        self.page.on_window_event = self.handle_window_event

        # Set assets directory
        assets_path = Path(__file__).parent / "assets"
        self.page.assets_dir = str(assets_path)
        logger.info(f"Assets path configured: {self.page.assets_dir}")

        # Current view
        self.current_view = "home"

        # Cached data
        self.selected_manager_type = None  # Currently selected manager type (mo2, vortex)
        self.instance_management_view = None  # Currently selected instance management view (None, "wineprefix")

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

        # Initialize workflows
        self.mo2_workflow = MO2Workflow(self.page, self.core, self.show_error, self.show_info, self.file_picker_mo2)
        self.vortex_workflow = VortexWorkflow(self.page, self.core, self.show_error, self.show_info)
        self.unverum_workflow = UnverumWorkflow(self.page, self.core, self.show_error, self.show_info)

        # Initialize game scanner (only if auto-detection is enabled)
        self.game_scanner = None
        if FeatureFlags.ENABLE_AUTO_GAME_DETECTION:
            self.game_scanner = GameScanner(self.core, scan_interval=ScanningConfig.SCAN_INTERVAL)

        # Build UI
        self.build_ui()

        # Check for first run and show cache config dialog
        self.check_and_show_cache_prompt()

        # Note: Getting Started page is now permanently available as the first tab
        # No need for a one-time welcome dialog anymore

        # Only check Steam if Steam integration is enabled
        if FeatureFlags.ENABLE_STEAM_INTEGRATION:
            # Check for multiple Steam installations and let user pick
            self.check_and_show_steam_picker()

        # Only scan games if auto-detection is enabled
        if FeatureFlags.ENABLE_AUTO_GAME_DETECTION and self.game_scanner:
            # Start background and periodic game scanning
            self.game_scanner.start_all_scans()

    def check_and_show_cache_prompt(self):
        """Check if this is first run and show cache configuration prompt"""
        try:
            from src.utils.cache_config import CacheConfig

            cache_config = CacheConfig()

            # Only show prompt on first run
            if cache_config.should_show_cache_prompt():
                # Show cache configuration dialog
                import time
                time.sleep(DialogDelays.CACHE_DIALOG)  # Brief delay to let UI initialize
                self.show_cache_config_dialog(cache_config)

        except Exception as e:
            logger.error(f"Failed to check cache config: {e}")

    def show_cache_config_dialog(self, cache_config):
        """Show first-run cache configuration dialog - delegated to dialogs/cache_config_dialog.py"""
        display_cache_config_dialog(self.page, cache_config)

    # Removed: check_and_show_welcome()
    # Getting Started page is now permanently available as the first tab
    # No need for a one-time welcome dialog

    def check_and_show_steam_picker(self):
        """Check for multiple Steam installations and show picker dialog if needed

        NOTE: This feature is currently disabled (ENABLE_STEAM_INTEGRATION = False)
        The SteamShortcutManager module has been removed from the codebase.
        """
        try:
            import time
            time.sleep(DialogDelays.STEAM_PICKER)  # Brief delay after cache dialog

            # DISABLED: Steam integration feature is disabled, module deleted
            # from src.utils.steam_shortcut_manager import SteamShortcutManager
            # steam_manager = SteamShortcutManager()
            # installations = steam_manager.find_all_steam_installations()

            logger.warning("Steam picker feature is disabled (ENABLE_STEAM_INTEGRATION = False)")
            return

            # The following code is disabled but kept for reference:
            # # Only show picker if multiple installations found
            # if len(installations) > 1:
            #     logger.info(f"Found {len(installations)} Steam installations")
            #     self.show_steam_picker_dialog(installations)
            # else:
            #     logger.debug(f"Found {len(installations)} Steam installation(s), no picker needed")

        except Exception as e:
            logger.error(f"Failed to check Steam installations: {e}")

    def show_steam_picker_dialog(self, installations: list):
        """Show dialog allowing user to pick which Steam installation to use - delegated to dialogs/steam_picker_dialog.py"""
        show_steam_picker_dialog(self.page, installations)

    def get_installed_proton_versions(self):
        """Detect installed Proton versions from Steam"""
        proton_versions = []
        steam_path = Path.home() / ".local/share/Steam"

        # Check Steam compatibility tools directory (for custom Proton builds)
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

        logger.debug(f"Detected Proton versions: {proton_versions}")
        return proton_versions if proton_versions else ["Proton - Experimental"]

    def build_ui(self):
        """Build the main UI"""

        # Create custom app bar using component
        self.page.appbar = create_custom_app_bar(
            self.page,
            self.show_proton_ge_manager,
            self.show_settings,
            self.close_app
        )

        # Build navigation destinations based on feature flags
        nav_destinations = [
            ft.NavigationRailDestination(
                icon="celebration_outlined",
                selected_icon="celebration",
                label="Getting Started",
            ),
            ft.NavigationRailDestination(
                icon="home_outlined",
                selected_icon="home",
                label="Home",
            ),
        ]

        # Only add Games view if auto-detection is enabled
        if FeatureFlags.ENABLE_AUTO_GAME_DETECTION:
            nav_destinations.append(
                ft.NavigationRailDestination(
                    icon="videogame_asset_outlined",
                    selected_icon="videogame_asset",
                    label="Games",
                )
            )

        # Only add Simple Game Modding if enabled
        if FeatureFlags.ENABLE_SIMPLE_MODDING:
            nav_destinations.append(
                ft.NavigationRailDestination(
                    icon="category_outlined",
                    selected_icon="category",
                    label="Simple Game Modding",
                )
            )

        # Always show Mod Managers
        nav_destinations.append(
            ft.NavigationRailDestination(
                icon="extension_outlined",
                selected_icon="extension",
                label="Mod Managers",
            )
        )

        # Navigation rail
        rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            destinations=nav_destinations,
            on_change=self.navigation_changed,
        )

        # Main content area - show Getting Started by default
        self.content_area = ft.Container(
            content=self.get_getting_started_view(),
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

        # Build views list dynamically based on feature flags (must match nav_destinations order)
        views = ["getting_started", "home"]

        if FeatureFlags.ENABLE_AUTO_GAME_DETECTION:
            views.append("games")

        if FeatureFlags.ENABLE_SIMPLE_MODDING:
            views.append("simple_game_modding")

        views.append("mod_managers")

        self.current_view = views[index]

        # Update content
        if self.current_view == "getting_started":
            self.content_area.content = self.get_getting_started_view()
        elif self.current_view == "home":
            self.content_area.content = self.get_home_view()
        elif self.current_view == "games":
            self.content_area.content = self.get_games_view()
        elif self.current_view == "simple_game_modding":
            self.content_area.content = self.get_simple_game_modding_view()
        elif self.current_view == "mod_managers":
            self.content_area.content = self.get_mod_managers_view()

        self.page.update()

    def navigate_to_mod_managers(self):
        """Navigate to mod managers view from home screen"""
        # Calculate mod_managers index dynamically based on feature flags
        # Order: getting_started (0), home (1), [games], [simple_game_modding], mod_managers
        mod_managers_index = 2  # Start after "getting_started" (0) and "home" (1)

        if FeatureFlags.ENABLE_AUTO_GAME_DETECTION:
            mod_managers_index += 1  # "games" comes after home

        if FeatureFlags.ENABLE_SIMPLE_MODDING:
            mod_managers_index += 1  # "simple_game_modding" comes after games

        # Find the navigation rail and update its selected index
        for control in self.page.controls:
            if isinstance(control, ft.Row):
                for child in control.controls:
                    if isinstance(child, ft.NavigationRail):
                        child.selected_index = mod_managers_index
                        break

        # Update current view and content
        self.current_view = "mod_managers"
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()

    def get_getting_started_view(self):
        """Getting Started view - delegated to views/getting_started_view.py"""
        return get_getting_started_view(self.page, self.show_proton_ge_manager)

    def get_home_view(self):
        """Home view - delegated to views/home_view.py"""
        return get_home_view(self.core, self.navigate_to_mod_managers)

    def get_games_view(self):
        """Games view - delegated to views/games_view.py"""
        return get_games_view(self.games_list, self.scan_games)

    def get_mod_managers_view(self):
        """Mod Managers view - delegated to views/mod_managers_view.py"""
        # Check if showing instance management view
        if self.instance_management_view == "main":
            return self.get_instance_management_view()
        elif self.instance_management_view == "wineprefix":
            return self.get_wineprefix_manager_view()

        # Check if showing manager type options
        if self.selected_manager_type:
            # Show management options for selected manager type
            return self.get_manager_options_view()

        return get_mod_managers_view(self.show_instance_management, self.select_manager_type)

    def select_manager_type(self, manager_type):
        """Select a mod manager type to view options"""
        self.selected_manager_type = manager_type
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()

    def get_manager_options_view(self):
        """Show management options for selected manager type - delegated to views/manager_options_view.py"""
        return get_manager_options_view(
            self.selected_manager_type,
            self.back_to_manager_types,
            self.install_mo2_dialog,
            self.setup_existing_mo2_dialog,
            self.install_vortex_dialog,
            self.setup_existing_vortex_dialog,
            self.show_vortex_staging_info,
            self.install_unverum_dialog,
            self.setup_existing_unverum_dialog
        )

    def back_to_manager_types(self):
        """Go back to mod manager types list"""
        self.selected_manager_type = None
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()

    def show_instance_management(self):
        """Show instance management view"""
        self.instance_management_view = "main"
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()

    def get_instance_management_view(self):
        """Instance Management view - delegated to views/instance_management_view.py"""
        return get_instance_management_view(
            self.back_to_mod_managers_from_instance,
            self.show_nxm_manager,
            self.show_wineprefix_manager
        )

    def show_wineprefix_manager(self):
        """Show wineprefix manager view"""
        self.instance_management_view = "wineprefix"
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()

    def get_wineprefix_manager_view(self):
        """Wineprefix Manager view - delegated to views/wineprefix_manager_view.py"""
        return get_wineprefix_manager_view(self.back_to_instance_management, self.launch_winetricks_gui)

    def back_to_instance_management(self):
        """Go back to instance management view"""
        self.instance_management_view = "main"
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()

    def back_to_mod_managers_from_instance(self):
        """Go back to mod managers list from instance management"""
        self.instance_management_view = None
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()

    def launch_winetricks_gui(self, prefix):
        """Launch winetricks GUI - delegated to utils/winetricks_launcher.py"""
        launch_winetricks(self.page, prefix)

    def get_simple_game_modding_view(self):
        """Simple Game Modding view - delegated to views/simple_game_modding_view.py"""
        return get_simple_game_modding_view(self.games_list, self.apply_dependencies_to_games)

    def apply_dependencies_to_games(self):
        """Apply dependencies to detected games"""
        # First scan for games if not already done
        if not self.games_list:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Scanning for games first..."),
                bgcolor=ft.Colors.BLUE,
            )
            self.page.snack_bar.open = True
            self.page.update()

            try:
                games = self.core.get_all_games()
                self.games_list = games
            except Exception as e:
                self.show_error("Scan Failed", str(e))
                return

        if not self.games_list or len(self.games_list) == 0:
            self.show_error("No Games Found", "No games detected. Make sure you have games installed from Steam, Heroic, or other sources.")
            return

        # Show game selection dialog
        self.show_game_selection_dialog()

    def show_game_selection_dialog(self):
        """Show dialog to select games for dependency installation - delegated to dialogs/game_selection_dialog.py"""
        show_game_selection_dialog_func(self.page, self.games_list, self.show_error, self.core)

    def get_dependencies_view(self):
        """Dependencies view - dynamically shows dependency status"""
        # Get dependency details from core
        try:
            dep_details = self.core.get_dependency_details()
        except Exception as e:
            logger.error(f"Failed to get dependency details: {e}")
            dep_details = None

        # Build dependency list tiles
        dep_tiles = [
            ft.Text("System Dependencies:", weight=ft.FontWeight.BOLD),
            ft.Divider(),
        ]

        if dep_details:
            # Proton (Experimental or GE based on feature flag)
            if FeatureFlags.ENABLE_PROTON_GE:
                # Show Proton-GE status
                from src.utils.proton_ge_manager import ProtonGEManager
                ge_manager = ProtonGEManager()
                active_version = ge_manager.get_active_version()

                if active_version:
                    proton_icon_color = ft.Colors.GREEN
                    proton_icon = "check_circle"
                    proton_path = f"Active: {active_version}"
                else:
                    proton_icon_color = ft.Colors.AMBER
                    proton_icon = "warning"
                    proton_path = "No active version - Click cloud icon to download"

                dep_tiles.append(
                    ft.ListTile(
                        leading=ft.Icon(proton_icon, color=proton_icon_color),
                        title=ft.Text("Proton-GE"),
                        subtitle=ft.Text(proton_path),
                    )
                )

            # Steam Installation
            steam = dep_details.get("steam_installation", {})
            steam_type = steam.get("type", "unknown")
            steam_path = steam.get("path", "Not found")
            steam_status = steam.get("status", "error")

            # Color based on status: green for success, yellow for warning (flatpak), red for error
            if steam_status == "success":
                steam_icon_color = ft.Colors.GREEN
                steam_icon = "check_circle"
            elif steam_status == "warning":
                steam_icon_color = ft.Colors.AMBER
                steam_icon = "warning"
            else:
                steam_icon_color = ft.Colors.RED
                steam_icon = "error"

            dep_tiles.append(
                ft.ListTile(
                    leading=ft.Icon(steam_icon, color=steam_icon_color),
                    title=ft.Text(f"Steam Installation: {steam_type}"),
                    subtitle=ft.Text(steam_path),
                )
            )

            # Winetricks
            dep_tiles.append(
                ft.ListTile(
                    leading=ft.Icon("check_circle", color=ft.Colors.GREEN),
                    title=ft.Text("Winetricks"),
                    subtitle=ft.Text("Bundled - for installing Windows dependencies"),
                )
            )
        else:
            # Fallback static display if we can't get details
            dep_tiles.extend([
                ft.ListTile(
                    leading=ft.Icon("check_circle", color=ft.Colors.GREEN),
                    title=ft.Text("Proton-GE"),
                    subtitle=ft.Text("Click 'Check Dependencies' to verify"),
                ),
                ft.ListTile(
                    leading=ft.Icon("check_circle", color=ft.Colors.GREEN),
                    title=ft.Text("Steam Installation"),
                    subtitle=ft.Text("Click 'Check Dependencies' to verify"),
                ),
                ft.ListTile(
                    leading=ft.Icon("check_circle", color=ft.Colors.GREEN),
                    title=ft.Text("Winetricks"),
                    subtitle=ft.Text("Bundled - for installing Windows dependencies"),
                ),
            ])

        return ft.Column(
            [
                ft.Text("Dependencies", size=32, weight=ft.FontWeight.BOLD),
                ft.Divider(height=20),
                ft.Row([
                    ft.ElevatedButton("Check Dependencies", icon="check_circle", on_click=lambda _: self.check_deps()),
                    ft.ElevatedButton("Test NXM Handler", icon="link", on_click=lambda _: self.test_nxm_handler_dialog()),
                ]),
                ft.Divider(height=20),

                ft.Card(
                    content=ft.Container(
                        content=ft.Column(dep_tiles),
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

    @property
    def games_list(self):
        """Get games list from game scanner or return empty list"""
        if self.game_scanner:
            return self.game_scanner.get_games_list()
        return None

    @games_list.setter
    def games_list(self, value):
        """Set games list - updates game scanner if available"""
        if self.game_scanner:
            self.game_scanner.games_list = value

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
        """Check dependencies and refresh the view"""
        # Show progress
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Checking dependencies..."),
            bgcolor=ft.Colors.BLUE,
        )
        self.page.snack_bar.open = True
        self.page.update()

        result = self.core.check_dependencies()

        # Refresh dependencies view to show updated info
        self.content_area.content = self.get_dependencies_view()
        self.page.update()

        if result:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("All required dependencies are available!"),
                bgcolor=ft.Colors.GREEN,
            )
            self.page.snack_bar.open = True
            self.page.update()
        else:
            self.show_error("Dependencies Check", "Some dependencies are missing. Check the logs for details.")

    def test_nxm_handler_dialog(self):
        """Test the NXM handler - delegated to dialogs/nxm_test_dialog.py"""
        show_nxm_test_dialog(self.page, self.core, self.close_dialog)

    def install_mo2_dialog(self):
        """Show install MO2 dialog - delegated to workflow"""
        self.mo2_workflow.install_mo2_dialog()

    def setup_existing_mo2_dialog(self):
        """Show setup existing MO2 dialog - delegated to workflow"""
        self.mo2_workflow.setup_existing_mo2_dialog()

    def install_vortex_dialog(self):
        """Show install Vortex dialog - delegated to workflow"""
        self.vortex_workflow.install_vortex_dialog()


    def setup_existing_vortex_dialog(self):
        """Show setup existing Vortex dialog - delegated to workflow"""
        self.vortex_workflow.setup_existing_vortex_dialog()


    def manage_mo2(self):
        """Manage existing MO2 installations"""
        self.show_info("Manage MO2", "MO2 management features coming soon! Use the MO2 tab for installation.")

    def setup_nxm_handler(self):
        """Setup NXM handler - delegated to dialogs/nxm_setup_dialog.py"""
        show_nxm_setup_dialog(self.page, self.core, self.games_list, self.show_error, self.scan_games)

    def remove_mo2_dialog(self):
        """Remove NXM handler - delegated to dialogs/nxm_remove_dialog.py"""
        show_nxm_remove_dialog(self.page, self.core, self.show_error)

    def install_mo2(self, install_dir=None, custom_name=None):
        """Install MO2 - delegated to workflow"""
        self.mo2_workflow.install_mo2(install_dir, custom_name)


    def install_vortex(self, install_dir=None, custom_name=None):
        """Install Vortex - delegated to workflow"""
        self.vortex_workflow.install_vortex(install_dir, custom_name)


    def install_unverum(self, install_dir=None, custom_name=None):
        """Install Unverum - delegated to workflow"""
        self.unverum_workflow.install_unverum(install_dir, custom_name)


    def handle_window_event(self, e):
        """Handle window events (close, minimize, etc.)"""
        if e.data == "close":
            self.close_app()

    def minimize_window(self):
        """Minimize the window"""
        self.page.window.minimized = True
        self.page.update()

    def close_app(self):
        """Close the application"""
        # Hide window first to avoid showing loading spinner
        self.page.window.visible = False
        self.page.update()

        # Then force quit
        import subprocess
        import os
        subprocess.Popen(['kill', '-9', str(os.getpid())])

    def test_save_symlinker(self):
        """Test save symlinker - delegated to dialogs/save_symlinker_test_dialog.py"""
        show_save_symlinker_test_dialog(self.page, self.show_error)

    def show_settings(self):
        """Show settings dialog - delegated to dialogs/settings_dialog.py"""
        show_settings_dialog(self.page, self.core, self.file_picker_proton, self.show_error, self.test_save_symlinker, self.get_installed_proton_versions)

    def show_proton_ge_manager(self):
        """Show Proton-GE Manager dialog - delegated to dialogs/proton_ge_dialog.py"""
        try:
            logger.info("Opening Proton-GE Manager dialog...")
            show_ge_manager_dialog(self.page)
        except Exception as e:
            logger.error(f"Failed to open Proton-GE Manager: {e}", exc_info=True)
            self.show_error("Proton-GE Manager Error", f"Failed to open Proton-GE Manager: {str(e)}")

    def show_about(self):
        """Show about dialog - delegated to dialogs/about_dialog.py"""
        show_about_dialog(self.page, self.core)

    def show_vortex_staging_info(self):
        """Show Vortex staging folder information - delegated to workflow"""
        self.vortex_workflow.show_vortex_staging_info()


    def show_vortex_staging_folder_popup(self, vortex_paths):
        """Show Vortex staging folder configuration popup - delegated to workflow"""
        self.vortex_workflow.show_vortex_staging_folder_popup(vortex_paths)


    def install_unverum_dialog(self):
        """Show install Unverum dialog - delegated to workflow"""
        self.unverum_workflow.install_unverum_dialog()


    def setup_existing_unverum_dialog(self):
        """Show setup existing Unverum dialog - delegated to workflow"""
        self.unverum_workflow.setup_existing_unverum_dialog()


    def show_info(self, title: str, message: str):
        """Show info dialog - delegated to dialogs/info_dialog.py"""
        show_info_dialog(self.page, title, message)

    def show_error(self, title: str, message: str):
        """Show error dialog - delegated to dialogs/error_dialog.py"""
        show_error_dialog(self.page, title, message)

    def show_nxm_manager(self):
        """Show NXM Handler Manager dialog - delegated to dialogs/nxm_manager_dialog.py"""
        show_nxm_manager_dialog(self.page, self.show_error, self.show_nxm_manager)

    def close_dialog(self, dialog=None):
        """Close current dialog or specified dialog"""
        if dialog:
            dialog.open = False
            self.page.update()
        elif self.page.dialog:
            self.page.dialog.open = False
            self.page.update()


def main(page: ft.Page):
    """Main entry point"""
    # Log system information before creating the app
    log_system_information()
    NaKApp(page)


if __name__ == "__main__":
    # Default mode uses flet-desktop-light (no mpv dependency)
    ft.app(target=main)
