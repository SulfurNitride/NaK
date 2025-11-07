"""
Wineprefix Manager view for NaK application
Shows buttons to open winetricks GUI for managing Wine prefixes
"""
import flet as ft
from pathlib import Path


def get_wineprefix_manager_view(back_callback, launch_winetricks_callback):
    """
    Create and return the wineprefix manager view

    Args:
        back_callback: Callback to go back to instance management
        launch_winetricks_callback: Callback to launch winetricks GUI for a prefix

    Returns:
        ft.Column: The wineprefix manager view content
    """
    # Scan for available prefixes
    prefixes = _scan_prefixes()

    content = [
        ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda _: back_callback(),
                tooltip="Back to Instance Management"
            ),
            ft.Text("Wineprefix Manager", size=32, weight=ft.FontWeight.BOLD),
        ]),
        ft.Text("Manage Wine prefixes with winetricks GUI", color=ft.Colors.GREY_500),
        ft.Divider(height=20),
    ]

    if not prefixes:
        content.append(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.FOLDER_OFF, size=64, color=ft.Colors.GREY_700),
                    ft.Text("No prefixes found", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("Install MO2 or Vortex to create prefixes", color=ft.Colors.GREY_500),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                padding=40,
            )
        )
    else:
        content.append(
            ft.Text(
                f"Found {len(prefixes)} prefix{'es' if len(prefixes) != 1 else ''}. "
                "Click the button to open winetricks GUI:",
                color=ft.Colors.BLUE_400,
                size=14,
                weight=ft.FontWeight.BOLD,
            )
        )

        # Add each prefix as a card
        for prefix in prefixes:
            content.append(_create_prefix_card(prefix, launch_winetricks_callback))

    return ft.Column(
        content,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


def _scan_prefixes():
    """Scan for available Wine prefixes"""
    prefixes = []
    nak_prefixes_dir = Path.home() / "NaK" / "Prefixes"

    if not nak_prefixes_dir.exists():
        return prefixes

    # Scan for MO2 and Vortex prefixes
    for prefix_dir in nak_prefixes_dir.iterdir():
        if not prefix_dir.is_dir():
            continue

        pfx_path = prefix_dir / "pfx"
        if not pfx_path.exists():
            continue

        # Determine prefix type and name
        prefix_name = prefix_dir.name
        if prefix_name.startswith("mo2_"):
            prefix_type = "MO2"
            display_name = prefix_name[4:].replace("_", " ").title()
        elif prefix_name.startswith("vortex_"):
            prefix_type = "Vortex"
            display_name = prefix_name[7:].replace("_", " ").title()
        else:
            prefix_type = "Unknown"
            display_name = prefix_name.replace("_", " ").title()

        prefixes.append({
            "name": display_name,
            "type": prefix_type,
            "path": str(pfx_path),
            "parent_path": str(prefix_dir),
        })

    return prefixes


def _create_prefix_card(prefix, launch_callback):
    """Create a card with button to launch winetricks GUI for a prefix"""
    # Create icon based on type
    if prefix["type"] == "MO2":
        icon = ft.Icons.FOLDER_SPECIAL
        color = ft.Colors.BLUE_400
    elif prefix["type"] == "Vortex":
        icon = ft.Icons.CYCLONE
        color = ft.Colors.ORANGE_400
    else:
        icon = ft.Icons.FOLDER
        color = ft.Colors.GREY_400

    return ft.Card(
        content=ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.Icon(icon, size=32, color=color),
                    ft.Column([
                        ft.Text(f"{prefix['name']}", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{prefix['type']} • {prefix['parent_path']}",
                               size=12, color=ft.Colors.GREY_500),
                    ], spacing=2, expand=True),
                ], spacing=10),

                ft.Divider(),

                # Launch button
                ft.ElevatedButton(
                    "Open Winetricks GUI",
                    icon=ft.Icons.SETTINGS,
                    on_click=lambda _: launch_callback(prefix),
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.GREEN_700,
                    ),
                ),

                # Info text
                ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.BLUE_400),
                    ft.Text(
                        "Opens winetricks GUI to install/manage Windows components",
                        size=11,
                        color=ft.Colors.BLUE_400,
                        italic=True,
                        expand=True,
                    ),
                ], spacing=5),
            ], spacing=10),
            padding=15,
        ),
    )
