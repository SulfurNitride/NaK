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

        # Explicitly enable window controls
        self.page.window.minimizable = True
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

        # Check for first run and show cache config dialog
        self.check_and_show_cache_prompt()

        # Scan games in background on startup and every 30 seconds
        import threading
        threading.Thread(target=self.scan_games_background, daemon=True).start()
        threading.Thread(target=self.periodic_game_scan, daemon=True).start()

    def check_and_show_cache_prompt(self):
        """Check if this is first run and show cache configuration prompt"""
        try:
            from src.utils.cache_config import CacheConfig

            cache_config = CacheConfig()

            # Only show prompt on first run
            if cache_config.should_show_cache_prompt():
                # Show cache configuration dialog
                import time
                time.sleep(0.5)  # Brief delay to let UI initialize
                self.show_cache_config_dialog(cache_config)

        except Exception as e:
            logger.error(f"Failed to check cache config: {e}")

    def show_cache_config_dialog(self, cache_config):
        """Show first-run cache configuration dialog with granular options"""
        # Create checkboxes for different cache types
        cache_dependencies_checkbox = ft.Checkbox(
            label="Cache dependencies (DirectX, .NET, VCRedist, etc.) - ~1.7GB",
            value=True,
        )
        cache_mo2_checkbox = ft.Checkbox(
            label="Cache MO2 - ~200MB",
            value=True,
        )

        def close_dlg(save: bool = True):
            """Close dialog and save preferences"""
            if save:
                # Save granular preferences based on checkboxes
                cache_deps = cache_dependencies_checkbox.value
                cache_mo2 = cache_mo2_checkbox.value
                enable_any = cache_deps or cache_mo2

                cache_config.set_cache_preferences(
                    enable_cache=enable_any,
                    cache_dependencies=cache_deps,
                    cache_mo2=cache_mo2
                )

                # Show confirmation
                if enable_any:
                    enabled_items = []
                    if cache_deps:
                        enabled_items.append("dependencies")
                    if cache_mo2:
                        enabled_items.append("MO2 files")

                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Cache enabled for: {', '.join(enabled_items)}"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text("Cache disabled. Files will be re-downloaded each time."),
                        bgcolor=ft.Colors.ORANGE,
                    )
                self.page.snack_bar.open = True
            else:
                # User cancelled - disable all caching
                cache_config.set_cache_preferences(
                    enable_cache=False,
                    cache_dependencies=False,
                    cache_mo2=False
                )

            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Cache Configuration", size=20, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Icon("storage", size=64, color=ft.Colors.BLUE),
                    ft.Divider(),
                    ft.Text("Welcome to NaK!", size=18, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Text(
                        "NaK can cache downloaded files to make future installations much faster.",
                        size=14
                    ),
                    ft.Text(
                        "Choose what you want to cache:",
                        size=14,
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Divider(),
                    cache_dependencies_checkbox,
                    cache_mo2_checkbox,
                    ft.Divider(),
                    ft.Text(
                        "Files will be stored in: ~/NaK/cache",
                        size=12,
                        color=ft.Colors.GREY_500,
                        italic=True
                    ),
                    ft.Text(
                        "You can change these settings later in the Settings menu",
                        size=11,
                        color=ft.Colors.GREY_600,
                        italic=True
                    ),
                ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.START),
                width=550,
            ),
            actions=[
                ft.TextButton(
                    "Don't Cache Anything",
                    on_click=lambda _: close_dlg(False)
                ),
                ft.ElevatedButton(
                    "Save Preferences",
                    on_click=lambda _: close_dlg(True),
                    bgcolor=ft.Colors.BLUE,
                    color=ft.Colors.WHITE
                ),
            ],
            modal=True,
        )

        self.page.open(dlg)

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

        # Custom app bar with full-width drag area
        custom_appbar = ft.Container(
            content=ft.Row(
                [
                    # Icon (not draggable)
                    ft.Container(
                        content=ft.Icon("games", color=ft.Colors.WHITE),
                        padding=ft.padding.only(left=10, right=5),
                    ),
                    # Draggable area (fills remaining space)
                    ft.WindowDragArea(
                        content=ft.Container(
                            content=ft.Text("NaK Linux Modding Helper", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            padding=10,
                        ),
                        expand=True,
                    ),
                    # Window control buttons (not draggable)
                    ft.IconButton(
                        icon="minimize",
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: self.minimize_window(),
                        tooltip="Minimize"
                    ),
                    ft.IconButton(
                        icon="settings",
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: self.show_settings(),
                        tooltip="Settings"
                    ),
                    ft.IconButton(
                        icon="close",
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: self.close_app(),
                        tooltip="Exit"
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.BLUE_GREY_900,
            height=56,  # Standard AppBar height
        )

        self.page.appbar = custom_appbar

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
                    icon="category_outlined",
                    selected_icon="category",
                    label="Simple Game Modding",
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
        views = ["home", "games", "simple_game_modding", "mod_managers", "dependencies"]
        self.current_view = views[index]

        # Update content
        if self.current_view == "home":
            self.content_area.content = self.get_home_view()
        elif self.current_view == "games":
            self.content_area.content = self.get_games_view()
        elif self.current_view == "simple_game_modding":
            self.content_area.content = self.get_simple_game_modding_view()
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
                                    subtitle=ft.Text("MO2, Vortex\nClick to manage mod managers"),
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
                        subtitle=ft.Text("Multi-game mod manager", size=14),
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
            # Vortex Management Options
            content.append(ft.Text("Management Options", size=20, weight=ft.FontWeight.BOLD))
            content.append(ft.Divider(height=10))

            # Install New Vortex
            content.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon("download", size=40, color=ft.Colors.PURPLE),
                            title=ft.Text("Install New Vortex", size=18, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text("Download and install the latest version"),
                            trailing=ft.Icon("chevron_right"),
                            on_click=lambda _: self.install_vortex_dialog(),
                        ),
                        padding=5,
                    ),
                )
            )

            # Setup Existing Vortex
            content.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon("folder_open", size=40, color=ft.Colors.ORANGE),
                            title=ft.Text("Setup Existing Vortex", size=18, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text("Add an already installed Vortex"),
                            trailing=ft.Icon("chevron_right"),
                            on_click=lambda _: self.setup_existing_vortex_dialog(),
                        ),
                        padding=5,
                    ),
                )
            )

            # Show Staging Folder Path
            content.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon("info", size=40, color=ft.Colors.LIGHT_BLUE),
                            title=ft.Text("Show Staging Folder Path", size=18, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text("View and copy the staging folder configuration"),
                            trailing=ft.Icon("chevron_right"),
                            on_click=lambda _: self.show_vortex_staging_info(),
                        ),
                        padding=5,
                    ),
                )
            )

        return ft.Column(content, scroll=ft.ScrollMode.AUTO, expand=True)

    def back_to_manager_types(self):
        """Go back to mod manager types list"""
        self.selected_manager_type = None
        self.content_area.content = self.get_mod_managers_view()
        self.page.update()


    def get_simple_game_modding_view(self):
        """Simple Game Modding view - direct prefix modding without MO2"""
        content = [
            ft.Text("Simple Game Modding", size=32, weight=ft.FontWeight.BOLD),
            ft.Text("Apply dependencies and fixes directly to game prefixes", color=ft.Colors.GREY_500),
            ft.Divider(height=20),
        ]

        # Description card
        content.append(
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("What is Simple Game Modding?", weight=ft.FontWeight.BOLD, size=16),
                        ft.Divider(),
                        ft.Text(
                            "Simple game modding without MO2! Apply dependencies, registry edits, and fixes "
                            "directly to your game prefixes. Perfect for ReShade, OptiScaler, ENB, and other modifications.\n\n"
                            "Automatically detects games from Steam, Heroic, and non-Steam sources.",
                            size=14
                        ),
                    ]),
                    padding=15,
                ),
            )
        )

        content.append(ft.Divider(height=20))

        # Quick action buttons
        content.append(ft.Text("Quick Actions", weight=ft.FontWeight.BOLD, size=18))

        # Scan and apply dependencies button
        content.append(
            ft.ElevatedButton(
                "Scan Games & Apply Dependencies",
                icon="search",
                on_click=lambda _: self.apply_dependencies_to_games()
            )
        )

        content.append(ft.Divider(height=20))

        # Show detected games if available
        if self.games_list and len(self.games_list) > 0:
            content.append(ft.Text(f"Detected {len(self.games_list)} games", weight=ft.FontWeight.BOLD))
            content.append(ft.Text("Use the button above to apply dependencies to your games", color=ft.Colors.GREY_500))
        else:
            content.append(ft.Text("No games detected yet. Click the button above to scan.", color=ft.Colors.ORANGE))

        return ft.Column(
            content,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

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
        """Show dialog to select games for dependency installation"""
        # Create checkboxes for ALL games (no deduplication)
        all_game_checkboxes = []
        for game in self.games_list:  # Show ALL games, not just first 30
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
            self.page.update()

        search_field.on_change = filter_games

        def close_dlg(e=None):
            dlg.open = False
            self.page.update()

        def apply_to_selected(e=None):
            # Get selected games from ALL checkboxes (not just filtered)
            selected_games = [game for checkbox, game in all_game_checkboxes if checkbox.value]

            if not selected_games:
                self.show_error("No Selection", "Please select at least one game")
                return

            close_dlg()
            self.install_dependencies_to_games(selected_games)

        def select_all(e):
            # Select all VISIBLE (filtered) games
            for checkbox, game in all_game_checkboxes:
                if checkbox in checkbox_container.controls:
                    checkbox.value = True
            self.page.update()

        def select_none(e):
            # Deselect all games
            for checkbox, _ in all_game_checkboxes:
                checkbox.value = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Select Games for Dependencies"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(f"Select games to apply dependencies ({len(self.games_list)} total)", weight=ft.FontWeight.BOLD),
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
        self.page.open(dlg)

    def install_dependencies_to_games(self, selected_games):
        """Install dependencies to selected games with progress"""
        import threading

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
            self.page.update()

        def append_log(message):
            terminal_output.value += f"{message}\n"
            self.page.update()

        def update_progress(percent):
            progress_bar.value = percent / 100
            progress_text.value = f"{percent}%"
            self.page.update()

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
                            append_log(f"✓ {game_name}: Dependencies applied successfully")
                            successful += 1
                        else:
                            append_log(f"✗ {game_name}: Failed - {result.error}")

                    except Exception as e:
                        append_log(f"✗ {game_name}: Error - {str(e)}")
                        logger.error(f"Error installing dependencies for {game_name}: {e}", exc_info=True)

                    # Ensure progress shows completion for this game
                    current_step = (i + 1) * steps_per_game
                    update_progress(int((current_step / total_steps) * 100))

                # Final summary
                append_log(f"\n{'='*50}")
                append_log(f"Installation Complete!")
                append_log(f"{'='*50}")
                append_log(f"✓ Successful: {successful}/{total_games}")
                append_log(f"✗ Failed: {total_games - successful}/{total_games}")

                close_button.disabled = False
                self.page.update()

            except Exception as e:
                append_log(f"\n✗ Fatal Error: {str(e)}")
                logger.error(f"Fatal error in dependency installation: {e}", exc_info=True)
                close_button.disabled = False
                self.page.update()

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
        self.page.open(install_dlg)

        # Start installation in background thread
        threading.Thread(target=run_installation, daemon=True).start()

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
            label="Steam Shortcut Name",
            hint_text="e.g., Vortex - Skyrim",
            value="Vortex",
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
                     '--title=Select Vortex Installation Directory'],
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
            """Handle folder picker for Vortex path using zenity directly"""
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
                     '--title=Select Vortex Installation Folder'],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env=env
                )

                logger.info(f"Zenity returned: returncode={result.returncode}, stdout={result.stdout.strip()}, stderr={result.stderr.strip()}")

                if result.returncode == 0 and result.stdout.strip():
                    selected_path = result.stdout.strip()
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

            # Show terminal dialog
            import threading

            # Create terminal output text field
            terminal_output = ft.TextField(
                value="Starting Vortex setup...\n",
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
            progress_bar = ft.ProgressBar(width=500, value=0, bgcolor=ft.Colors.GREY_800, color=ft.Colors.PURPLE)
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
                    append_log(f"Vortex folder: {path_field.value}")
                    append_log(f"Installation name: {name_field.value}\n")
                    append_log("="*50)

                    # Set up callbacks for logging and progress
                    def log_callback(message):
                        append_log(message)

                    def progress_callback(percent, downloaded_bytes, total_bytes):
                        """Update progress bar based on backend updates"""
                        update_progress(int(percent))

                    # Setup Vortex with callbacks
                    self.core.vortex.set_log_callback(log_callback)
                    self.core.vortex.set_progress_callback(progress_callback)

                    # Start with some initial progress
                    update_progress(5)

                    # Run the actual setup - backend will send progress updates
                    result = self.core.vortex.setup_existing(path_field.value, name_field.value)

                    # Setup complete
                    if result.get("success"):
                        update_progress(100)
                        append_log("\n" + "="*50)
                        append_log("✓ Setup completed successfully!")
                        append_log(f"✓ Vortex '{name_field.value}' configured")
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
                title=ft.Text("Vortex Setup Progress", size=18, weight=ft.FontWeight.BOLD),
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

            # Run setup in a background thread
            setup_thread = threading.Thread(target=run_setup, daemon=True)
            setup_thread.start()

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

        def pick_handler_path(e):
            """Handle folder picker for MO2 installation (manual override) using zenity"""
            logger.info("Browse button clicked - opening folder picker with zenity")
            try:
                import subprocess
                import shutil
                from pathlib import Path

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
                     '--title=Select MO2 Installation Folder (Manual Override)'],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env=env
                )

                logger.info(f"Zenity returned: returncode={result.returncode}, stdout={result.stdout.strip()}")

                if result.returncode == 0 and result.stdout.strip():
                    selected_path = result.stdout.strip()
                    logger.info(f"User selected MO2 folder: {selected_path}")

                    # Validate that nxmhandler.exe exists in the selected folder
                    mo2_folder = Path(selected_path)
                    nxmhandler_path = mo2_folder / "nxmhandler.exe"

                    if nxmhandler_path.exists():
                        handler_path_field.value = selected_path
                        handler_path_field.read_only = False  # Allow manual editing
                        self.page.update()
                        logger.info(f"Valid MO2 folder selected with nxmhandler.exe: {selected_path}")
                    else:
                        self.show_error("NXM Handler Not Found",
                                       f"nxmhandler.exe not found in selected folder.\n\n"
                                       f"Expected: {nxmhandler_path}\n\n"
                                       f"Please select a valid MO2 installation folder.")
                        logger.warning(f"nxmhandler.exe not found in selected folder: {selected_path}")
                else:
                    logger.info("User cancelled folder selection or zenity returned error")

            except FileNotFoundError:
                logger.warning("Zenity not found - file picker not available")
                self.show_error("File Browser Not Available",
                               "The file browser (zenity) is not installed.\n\n"
                               "Please install zenity: sudo pacman -S zenity\n\n"
                               "Or enter the MO2 folder path manually in the text field.")
                # Make the field editable so user can type the path
                handler_path_field.read_only = False
                self.page.update()
            except Exception as e:
                logger.error(f"Error opening folder browser: {e}", exc_info=True)
                self.show_error("Error", f"Could not open folder browser: {e}\n\nPlease enter the path manually.")
                # Make the field editable so user can type the path
                handler_path_field.read_only = False
                self.page.update()

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

    def install_vortex(self, install_dir=None, custom_name=None):
        """Install Vortex with terminal output"""
        import threading

        # Create terminal output text field
        terminal_output = ft.TextField(
            value="Starting Vortex installation...\n",
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
        progress_bar = ft.ProgressBar(width=500, value=0, bgcolor=ft.Colors.GREY_800, color=ft.Colors.PURPLE)
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

                # Install Vortex
                self.core.vortex.set_log_callback(log_callback)
                self.core.vortex.set_progress_callback(progress_callback)

                result = self.core.vortex.download_vortex(install_dir=install_dir, custom_name=custom_name)

                if result.get("success"):
                    update_progress(100)
                    append_log("\n" + "="*50)
                    append_log("✓ Installation completed successfully!")
                    append_log(f"✓ Vortex installed to: {result.get('install_dir', 'N/A')}")
                    append_log(f"✓ Steam App ID: {result.get('app_id', 'N/A')}")
                    append_log(f"✓ Version: {result.get('version', 'N/A')}")

                    # Enable close button
                    close_button.disabled = False
                    self.page.update()

                    # Show staging folder configuration popup if paths are available
                    linux_fixes = result.get("linux_fixes", {})
                    vortex_paths = linux_fixes.get("results", {}).get("vortex_paths", {})

                    if vortex_paths:
                        self.show_vortex_staging_folder_popup(vortex_paths)

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
            title=ft.Text("Vortex Installation Progress", size=18, weight=ft.FontWeight.BOLD),
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
        """Test the save game symlinker with real MO2 installation"""
        logger.info("Test Save Symlinker button clicked")

        # Import save_symlinker
        try:
            from src.utils.save_symlinker import SaveSymlinker
        except Exception as e:
            self.show_error("Import Error", f"Failed to load save_symlinker module: {e}")
            return

        def close_dlg(e=None):
            dlg.open = False
            self.page.update()

        # Create terminal output
        terminal_output = ft.TextField(
            value="Initializing Save Symlinker Test...\n",
            multiline=True,
            read_only=True,
            min_lines=20,
            max_lines=20,
            text_style=ft.TextStyle(font_family="monospace", size=12),
            bgcolor=ft.Colors.BLACK,
            color=ft.Colors.GREEN_300,
            border_color=ft.Colors.GREY_800,
        )

        close_button = ft.ElevatedButton(
            "Close",
            on_click=close_dlg
        )

        def append_log(message):
            terminal_output.value += f"{message}\n"
            self.page.update()

        def run_test():
            """Run the save symlinker test"""
            import threading
            import time

            try:
                append_log("="*60)
                append_log("SAVE GAME SYMLINKER TEST")
                append_log("="*60)

                # Initialize SaveSymlinker
                symlinker = SaveSymlinker()
                append_log("\n✓ SaveSymlinker initialized")

                # List available Bethesda games
                append_log("\nScanning for Bethesda game save locations...")
                append_log("-"*60)

                available_games = symlinker.list_available_games()

                if not available_games:
                    append_log("✗ No Bethesda games found")
                    append_log("\nInstall a Bethesda game (Skyrim, Fallout, etc.) through Steam")
                    return

                installed_count = sum(1 for g in available_games if g.get('installed', False))
                with_saves_count = sum(1 for g in available_games if g['found'])

                append_log(f"\n✓ Found {installed_count} installed Bethesda game(s)")
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
                append_log(f"✓ Created: {game_saves_folder}")

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
                            append_log(f"  ✓ Symlink created successfully!")
                            append_log(f"    Target: {game_saves_folder / game_name.replace(':', '').replace('/', '-')}")
                            append_log(f"    Points to: {original_save_path}")
                            success_count += 1
                        else:
                            append_log(f"  ✗ Failed to create symlink")

                    except Exception as e:
                        append_log(f"  ✗ Error: {e}")
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

                append_log("\n✓ Test completed successfully!")

            except Exception as e:
                append_log(f"\n✗ Test failed: {e}")
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
                    terminal_output,
                ], tight=True),
                width=700,
                height=500,
            ),
            actions=[close_button],
            modal=True,
        )
        self.page.open(dlg)

        # Run test in background thread
        import threading
        threading.Thread(target=run_test, daemon=True).start()

    def show_settings(self):
        """Show settings dialog"""
        logger.info("Settings button clicked")

        # Get current settings
        current_settings = self.core.settings.settings

        # Get installed Proton versions
        installed_protons = self.get_installed_proton_versions()
        current_proton = current_settings.get("preferred_proton_version", installed_protons[0] if installed_protons else "Proton - Experimental")

        # Get cache configuration
        try:
            from src.utils.cache_config import CacheConfig
            cache_config = CacheConfig()
            cache_info = cache_config.get_cache_info()
        except Exception as e:
            logger.error(f"Failed to load cache config: {e}")
            cache_config = None
            cache_info = {"size_mb": 0}

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

        # Cache settings switches
        cache_deps_switch = ft.Switch(
            label="Cache dependencies (~1.7GB)",
            value=cache_config.should_cache_dependencies() if cache_config else True,
            tooltip="Cache DirectX, .NET, VCRedist, etc."
        )

        cache_mo2_switch = ft.Switch(
            label="Cache MO2 (~200MB)",
            value=cache_config.should_cache_mo2() if cache_config else True,
            tooltip="Cache MO2 installation archives"
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

                # Save cache settings
                if cache_config:
                    cache_deps = cache_deps_switch.value
                    cache_mo2 = cache_mo2_switch.value
                    enable_any = cache_deps or cache_mo2
                    cache_config.set_cache_preferences(
                        enable_cache=enable_any,
                        cache_dependencies=cache_deps,
                        cache_mo2=cache_mo2
                    )

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

        def clear_cache(e=None):
            """Clear the cache"""
            if not cache_config:
                self.show_error("Cache Error", "Cache configuration not available")
                return

            # Confirmation dialog
            def confirm_clear(e):
                confirm_dlg.open = False
                self.page.update()

                try:
                    import shutil
                    from pathlib import Path
                    cache_dir = Path(cache_config.get_cache_location())
                    if cache_dir.exists():
                        shutil.rmtree(cache_dir)
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        self.page.snack_bar = ft.SnackBar(
                            content=ft.Text(f"Cache cleared! ({cache_info['size_mb']}MB freed)"),
                            bgcolor=ft.Colors.GREEN,
                        )
                    else:
                        self.page.snack_bar = ft.SnackBar(
                            content=ft.Text("Cache is already empty"),
                            bgcolor=ft.Colors.ORANGE,
                        )
                    self.page.snack_bar.open = True
                    self.page.update()
                except Exception as ex:
                    self.show_error("Clear Failed", str(ex))

            def cancel_clear(e):
                confirm_dlg.open = False
                self.page.update()

            confirm_dlg = ft.AlertDialog(
                title=ft.Text("Clear Cache?"),
                content=ft.Text(
                    f"This will delete {cache_info['size_mb']}MB of cached files.\n\n"
                    "Cached files will need to be re-downloaded for future installations."
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=cancel_clear),
                    ft.ElevatedButton("Clear Cache", on_click=confirm_clear, bgcolor=ft.Colors.RED),
                ],
            )
            self.page.open(confirm_dlg)

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

                # Cache Settings
                ft.Text("Cache Configuration", weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"Current cache size: {cache_info['size_mb']}MB",
                    size=12,
                    color=ft.Colors.GREY_500
                ),
                cache_deps_switch,
                cache_mo2_switch,
                ft.ElevatedButton(
                    "Clear Cache",
                    icon="delete",
                    on_click=clear_cache,
                    bgcolor=ft.Colors.RED_400
                ) if cache_info['size_mb'] > 0 else ft.Container(),

                ft.Divider(),

                # Advanced Settings
                ft.Text("Advanced", weight=ft.FontWeight.BOLD),
                log_level_dropdown,

                ft.Divider(),

                # Save Symlinker Test (Beta Feature)
                ft.Text("Save Game Management (Beta)", weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Test save game symlinker for Bethesda games",
                    size=12,
                    color=ft.Colors.GREY_500
                ),
                ft.ElevatedButton(
                    "Test Game Saves Symlinker",
                    icon="folder_shared",
                    on_click=lambda e: self.test_save_symlinker(),
                    bgcolor=ft.Colors.PURPLE_400
                ),

            ], tight=True, width=500, scroll=ft.ScrollMode.AUTO, height=550),
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

    def show_vortex_staging_info(self):
        """Show Vortex staging folder information (called from button)"""
        try:
            logger.info("Show Vortex Staging Info button clicked")

            # Use the VortexLinuxFixes to detect games and get paths
            from src.utils.vortex_linux_fixes import VortexLinuxFixes
            from src.utils.steam_utils import SteamUtils

            fixer = VortexLinuxFixes()
            steam_utils = SteamUtils()
            steam_root = steam_utils.get_steam_root()

            if not steam_root:
                self.show_error("Error", "Could not find Steam installation")
                return

            # Detect installed games
            results = fixer.detect_and_fix_installed_games(steam_root)
            vortex_paths = results.get("vortex_paths", {})

            if not vortex_paths:
                self.show_info(
                    "No Games Found",
                    "No Bethesda games detected. Install a Bethesda game (Skyrim, Fallout, etc.) to see staging folder paths."
                )
                return

            # Show the popup with paths
            self.show_vortex_staging_folder_popup(vortex_paths)

        except Exception as e:
            logger.error(f"Failed to show staging info: {e}")
            self.show_error("Error", f"Failed to load staging folder information: {str(e)}")

    def show_vortex_staging_folder_popup(self, vortex_paths):
        """Show Vortex staging folder configuration popup with copy button"""
        def close_dlg(e=None):
            dlg.open = False
            self.page.update()

        def copy_to_clipboard(path):
            """Copy path to clipboard"""
            self.page.set_clipboard(path)
            self.show_info("Copied!", f"Path copied to clipboard:\n{path}")

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
                "⚠️  IMPORTANT: Configure Vortex Staging Folder",
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
