"""
Instance Management view for NaK application
Shows tools for managing mod manager instances (NXM handlers, wine prefixes, etc.)
"""
import flet as ft


def get_instance_management_view(
    back_callback,
    show_nxm_manager_callback,
    show_wineprefix_manager_callback
):
    """
    Create and return the instance management view

    Args:
        back_callback: Callback to go back to mod managers view
        show_nxm_manager_callback: Callback to show NXM handler manager
        show_wineprefix_manager_callback: Callback to show wineprefix manager

    Returns:
        ft.Column: The instance management view content
    """
    content = [
        ft.Row([
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=lambda _: back_callback(),
                tooltip="Back to Mod Managers"
            ),
            ft.Text("Manage Instances", size=32, weight=ft.FontWeight.BOLD),
        ]),
        ft.Text("Tools for managing your mod manager instances", color=ft.Colors.GREY_500),
        ft.Divider(height=20),
    ]

    # NXM Manager Card
    content.append(
        ft.Card(
            content=ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon("link", size=48, color=ft.Colors.GREEN),
                    title=ft.Text("NXM Handler Manager", size=20, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(
                        "Configure which instance handles Nexus Mods download links",
                        size=14
                    ),
                    trailing=ft.Icon("chevron_right"),
                    on_click=lambda _: show_nxm_manager_callback(),
                ),
                padding=10,
            ),
        )
    )

    # Wineprefix Manager Card
    content.append(
        ft.Card(
            content=ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon("terminal", size=48, color=ft.Colors.PURPLE),
                    title=ft.Text("Wineprefix Manager", size=20, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(
                        "Get winetricks commands to manage Wine prefixes",
                        size=14
                    ),
                    trailing=ft.Icon("chevron_right"),
                    on_click=lambda _: show_wineprefix_manager_callback(),
                ),
                padding=10,
            ),
        )
    )

    # Info box about future additions
    content.append(
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.INFO_OUTLINE, size=20, color=ft.Colors.BLUE_400),
                ft.Text(
                    "More instance management tools coming soon!",
                    size=12,
                    color=ft.Colors.BLUE_400,
                    italic=True,
                ),
            ], spacing=10),
            padding=15,
            margin=ft.margin.only(top=20),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
            border=ft.border.all(1, ft.Colors.BLUE_700),
            border_radius=5,
        )
    )

    return ft.Column(
        content,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
