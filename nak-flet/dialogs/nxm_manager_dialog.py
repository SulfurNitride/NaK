"""
NXM Handler Manager dialog
Allows users to select which MO2/Vortex instance handles NXM links from Nexus Mods
"""

import flet as ft
from src.utils.logger import get_logger

logger = get_logger(__name__)


def show_nxm_manager(page: ft.Page, show_error_callback, refresh_callback):
    """
    Show NXM Handler Manager dialog

    Args:
        page: Flet page object
        show_error_callback: Function to show error dialogs
        refresh_callback: Function to refresh the dialog (typically calls show_nxm_manager again)
    """
    logger.info("NXM Handler Manager opened")

    try:
        from src.utils.nxm_handler_manager import NXMHandlerManager
        nxm_manager = NXMHandlerManager()

        # Get all NaK-managed instances
        instances = nxm_manager.list_all_instances()
        active_handler = nxm_manager.get_active_handler()

        logger.info(f"Found {len(instances)} NaK-managed instances")
        logger.info(f"Active handler: {active_handler}")

    except Exception as e:
        logger.error(f"Failed to load NXM handler info: {e}")
        show_error_callback("Error", f"Failed to load NXM handler information:\n{e}")
        return

    def close_dlg(e=None):
        dlg.open = False
        page.update()

    def set_active(instance_info):
        """Set an instance as the active NXM handler"""
        try:
            instance_name = instance_info.get('INSTANCE_NAME', 'Unknown')
            logger.info(f"Setting active NXM handler to: {instance_name}")

            success = nxm_manager.set_active_handler(instance_info)

            if success:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"[OK] {instance_name} is now the active NXM handler"),
                    bgcolor=ft.Colors.GREEN,
                )
                page.snack_bar.open = True

                # Refresh the dialog
                close_dlg()
                refresh_callback()

            else:
                show_error_callback("Error", f"Failed to set {instance_name} as active handler")

        except Exception as e:
            logger.error(f"Failed to set active handler: {e}")
            show_error_callback("Error", str(e))

    # Build instance list
    instance_widgets = []

    if not instances:
        instance_widgets.append(
            ft.Container(
                content=ft.Column([
                    ft.Icon("info", size=48, color=ft.Colors.ORANGE),
                    ft.Text("No NaK-managed instances found", size=16, color=ft.Colors.GREY),
                    ft.Text(
                        "Set up MO2 or Vortex instances to use NXM handling",
                        size=12,
                        color=ft.Colors.GREY_600
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                alignment=ft.alignment.center,
            )
        )
    else:
        for instance in instances:
            instance_name = instance.get('INSTANCE_NAME', 'Unknown')
            instance_type = instance.get('INSTANCE_TYPE', 'Unknown')
            app_id = instance.get('STEAM_APP_ID', 'N/A')
            script_path = instance.get('NXM_SCRIPT', '')
            script_exists = instance.get('script_exists', False)

            # Check if this is the active handler
            is_active = active_handler and script_path and active_handler in script_path

            # Build status text
            status_parts = []
            if is_active:
                status_parts.append("Active")
            if not script_exists:
                status_parts.append("Script Missing")

            status_text = " • ".join(status_parts) if status_parts else ""

            # Color based on status
            if is_active:
                color = ft.Colors.GREEN
                icon = "check_circle"
            elif not script_exists:
                color = ft.Colors.ORANGE
                icon = "warning"
            else:
                color = ft.Colors.BLUE
                icon = "radio_button_unchecked"

            instance_widgets.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.ListTile(
                            leading=ft.Icon(icon, size=40, color=color),
                            title=ft.Text(instance_name, size=16, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Column([
                                ft.Text(f"{instance_type} • AppID: {app_id}", size=12),
                                ft.Text(status_text, size=11, color=color) if status_text else ft.Container(),
                            ], spacing=2),
                            trailing=ft.ElevatedButton(
                                "Set Active" if not is_active else "Active",
                                icon="check" if is_active else "radio_button_unchecked",
                                disabled=is_active,
                                on_click=lambda _, inst=instance: set_active(inst),
                            ),
                        ),
                        padding=10,
                    ),
                )
            )

    dlg = ft.AlertDialog(
        title=ft.Row([
            ft.Icon("link", size=32, color=ft.Colors.GREEN),
            ft.Text("NXM Handler Manager", size=20, weight=ft.FontWeight.BOLD),
        ]),
        content=ft.Container(
            content=ft.Column([
                ft.Text(
                    "Select which MO2/Vortex instance should handle NXM links from Nexus Mods",
                    size=14,
                    color=ft.Colors.GREY_600
                ),
                ft.Divider(),
                ft.Container(
                    content=ft.Column(
                        instance_widgets,
                        spacing=10,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    height=300,  # Fixed height for scrollable area
                ),
            ], spacing=10, tight=True),
            width=600,
        ),
        actions=[
            ft.TextButton("Close", on_click=close_dlg),
        ],
    )

    page.open(dlg)
