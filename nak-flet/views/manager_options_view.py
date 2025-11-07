"""
Manager Options view for NaK application
Shows management options for a selected mod manager (MO2, Vortex, or Unverum)
"""
import flet as ft


def get_manager_options_view(
    manager_type,
    back_to_manager_types_callback,
    install_mo2_callback,
    setup_existing_mo2_callback,
    install_vortex_callback,
    setup_existing_vortex_callback,
    show_vortex_staging_info_callback,
    install_unverum_callback=None,
    setup_existing_unverum_callback=None
):
    """
    Create and return the manager options view

    Args:
        manager_type: Type of manager ("mo2" or "vortex")
        back_to_manager_types_callback: Callback to go back to manager selection
        install_mo2_callback: Callback to install new MO2
        setup_existing_mo2_callback: Callback to setup existing MO2
        install_vortex_callback: Callback to install new Vortex
        setup_existing_vortex_callback: Callback to setup existing Vortex
        show_vortex_staging_info_callback: Callback to show Vortex staging folder info

    Returns:
        ft.Column: The manager options view content
    """
    # Get title and details based on type
    if manager_type == "mo2":
        title = "Mod Organizer 2"
        icon = "extension"
        color = ft.Colors.BLUE
    elif manager_type == "vortex":
        title = "Vortex"
        icon = "cyclone"
        color = ft.Colors.PURPLE
    elif manager_type == "unverum":
        title = "Unverum"
        icon = "gamepad"
        color = ft.Colors.TEAL
    else:
        title = "Mod Manager"
        icon = "help"
        color = ft.Colors.GREY

    content = [
        ft.Row([
            ft.IconButton(
                icon="arrow_back",
                tooltip="Back to Mod Managers",
                on_click=lambda _: back_to_manager_types_callback()
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
                        on_click=lambda _: install_mo2_callback(),
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
                        on_click=lambda _: setup_existing_mo2_callback(),
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
                        on_click=lambda _: install_vortex_callback(),
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
                        on_click=lambda _: setup_existing_vortex_callback(),
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
                        on_click=lambda _: show_vortex_staging_info_callback(),
                    ),
                    padding=5,
                ),
            )
        )

    elif manager_type == "unverum":
        # Unverum Management Options
        content.append(ft.Text("Management Options", size=20, weight=ft.FontWeight.BOLD))
        content.append(ft.Divider(height=10))

        # Install New Unverum
        if install_unverum_callback:
            content.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon("download", size=40, color=ft.Colors.TEAL),
                            title=ft.Text("Install New Unverum", size=18, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text("Download and install the latest version"),
                            trailing=ft.Icon("chevron_right"),
                            on_click=lambda _: install_unverum_callback(),
                        ),
                        padding=5,
                    ),
                )
            )

        # Setup Existing Unverum
        if setup_existing_unverum_callback:
            content.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon("folder_open", size=40, color=ft.Colors.ORANGE),
                            title=ft.Text("Setup Existing Unverum", size=18, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text("Add an already installed Unverum"),
                            trailing=ft.Icon("chevron_right"),
                            on_click=lambda _: setup_existing_unverum_callback(),
                        ),
                        padding=5,
                    ),
                )
            )

    return ft.Column(content, scroll=ft.ScrollMode.AUTO, expand=True)
