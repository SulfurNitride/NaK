"""
Simple Game Modding view for NaK application
Direct prefix modding without MO2 - apply dependencies and fixes to games
"""
import flet as ft


def get_simple_game_modding_view(games_list, apply_dependencies_callback):
    """
    Create and return the simple game modding view

    Args:
        games_list: List of detected games (or None if not scanned yet)
        apply_dependencies_callback: Callback to trigger dependency application

    Returns:
        ft.Column: The simple game modding view content
    """
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
            on_click=lambda _: apply_dependencies_callback()
        )
    )

    content.append(ft.Divider(height=20))

    # Show detected games if available
    if games_list and len(games_list) > 0:
        content.append(ft.Text(f"Detected {len(games_list)} games", weight=ft.FontWeight.BOLD))
        content.append(ft.Text("Use the button above to apply dependencies to your games", color=ft.Colors.GREY_500))
    else:
        content.append(ft.Text("No games detected yet. Click the button above to scan.", color=ft.Colors.ORANGE))

    return ft.Column(
        content,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
