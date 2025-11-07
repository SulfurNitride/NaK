"""
Games view for NaK application
Shows detected games from Steam, Heroic, and other sources
"""
import flet as ft


def get_games_view(games_list, scan_games_callback):
    """
    Create and return the games view

    Args:
        games_list: List of detected games (or None if not scanned yet)
        scan_games_callback: Callback to trigger game scanning

    Returns:
        ft.Column: The games view content
    """
    content = [
        ft.Text("Games", size=32, weight=ft.FontWeight.BOLD),
        ft.Divider(height=20),
        ft.ElevatedButton("Scan for Games", icon="search", on_click=lambda _: scan_games_callback()),
        ft.Divider(height=20),
    ]

    if games_list:
        # Show games list
        content.append(ft.Text(f"Found {len(games_list)} games:", weight=ft.FontWeight.BOLD))
        for game in games_list[:50]:  # Limit to first 50
            content.append(
                ft.ListTile(
                    leading=ft.Icon("videogame_asset"),
                    title=ft.Text(game.get("name", "Unknown")),
                    subtitle=ft.Text(f"{game.get('platform', 'Unknown')} - {game.get('app_id', 'N/A')}"),
                )
            )
        if len(games_list) > 50:
            content.append(ft.Text(f"...and {len(games_list) - 50} more", color=ft.Colors.GREY_500))
    else:
        content.append(ft.Text("No games found. Click 'Scan for Games' to search.", color=ft.Colors.GREY_500))

    return ft.Column(
        content,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
