"""
Mod Managers view for NaK application
Selection screen for different mod manager types (MO2, Vortex)
"""
import flet as ft


def get_mod_managers_view(show_instance_management_callback, select_manager_type_callback):
    """
    Create and return the mod managers view

    Args:
        show_instance_management_callback: Callback to show instance management view
        select_manager_type_callback: Callback to select a manager type (mo2/vortex)

    Returns:
        ft.Column: The mod managers view content
    """
    content = [
        ft.Text("Mod Managers", size=32, weight=ft.FontWeight.BOLD),
        ft.Text("Select a mod manager to configure", color=ft.Colors.GREY_500),
        ft.Divider(height=20),
    ]

    # Manage Instances Card (tools for managing instances)
    content.append(
        ft.Card(
            content=ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon("settings", size=48, color=ft.Colors.PURPLE),
                    title=ft.Text("Manage Instances", size=20, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text("NXM handlers, Wine prefixes, and other instance tools", size=14),
                    trailing=ft.Icon("chevron_right"),
                    on_click=lambda _: show_instance_management_callback(),
                ),
                padding=10,
            ),
        )
    )

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
                    on_click=lambda _: select_manager_type_callback("mo2"),
                ),
                padding=10,
            ),
        )
    )

    # Vortex Card with official icon
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
                    on_click=lambda _: select_manager_type_callback("vortex"),
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
