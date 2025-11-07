"""
Home view for NaK application
Main landing page with quick access cards
"""
import flet as ft
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_home_view(core, navigate_to_mod_managers):
    """
    Create and return the home view

    Args:
        core: Core instance for version info and game detection
        navigate_to_mod_managers: Callback to navigate to mod managers view

    Returns:
        ft.Column: The home view content
    """
    # Import feature flags
    try:
        from constants import FeatureFlags
    except ImportError:
        class FeatureFlags:
            ENABLE_AUTO_GAME_DETECTION = False

    version, date = core.get_version_info()

    # Get game count only if auto-detection is enabled
    game_count = 0
    if FeatureFlags.ENABLE_AUTO_GAME_DETECTION:
        try:
            games = core.get_all_games()
            game_count = len(games) if games else 0
        except Exception as e:
            logger.warning(f"Failed to get game count: {e}")
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
                                on_click=lambda _: navigate_to_mod_managers(),
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
                                    ft.Text("Proton-GE: Using standalone mode", color=ft.Colors.BLUE),
                                ] + (
                                    [ft.Text(f"Games Detected: {game_count}", color=ft.Colors.BLUE)]
                                    if FeatureFlags.ENABLE_AUTO_GAME_DETECTION else []
                                ),
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
