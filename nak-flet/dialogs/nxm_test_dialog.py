"""
NXM Handler Test Dialog

Shows dialog for testing the NXM handler configuration and functionality.
Extracted from main.py to improve code organization.
"""

import flet as ft
from src.utils.logger import get_logger

logger = get_logger(__name__)


def show_nxm_test_dialog(page: ft.Page, core, close_dialog_callback):
    """
    Show dialog for testing NXM handler

    Args:
        page: Flet page instance
        core: Core backend instance
        close_dialog_callback: Callback to close dialogs
    """
    logger.info("Test NXM Handler button clicked")

    # First, get the NXM handler status
    status = core.get_nxm_handler_status()

    # Build status display
    status_text = []

    if not status.get("desktop_file_exists"):
        dlg = ft.AlertDialog(
            title=ft.Text("NXM Handler Not Configured"),
            content=ft.Text(
                "The NXM handler has not been set up yet.\n\n"
                "Please set up MO2 or Vortex first, then try again."
            ),
            actions=[
                ft.TextButton("OK", on_click=lambda _: close_dialog_callback(dlg))
            ],
        )
        page.open(dlg)
        return

    # Show status and test button
    status_text.append(f"[OK] Desktop file exists")
    status_text.append(f"[OK] Handler {'registered' if status.get('handler_registered') else 'NOT registered'}")

    if status.get('active_script'):
        status_text.append(f"[OK] Active script configured")
    else:
        status_text.append(f"[FAILED] No active script")

    status_text.append(f"\nTotal instances: {status.get('total_instances', 0)}")

    # Test URL input
    test_url_field = ft.TextField(
        label="Test NXM URL",
        value="nxm://skyrimspecialedition/mods/12345/files/67890",
        hint_text="Enter any nxm:// URL to test",
        expand=True,
    )

    result_text = ft.Text("Click 'Run Test' to test the handler", italic=True)

    def run_test(_):
        result_text.value = "Testing... Please wait..."
        result_text.color = ft.Colors.BLUE
        page.update()

        test_url = test_url_field.value
        results = core.test_nxm_handler(test_url)

        if results.get("success"):
            result_text.value = "[OK] SUCCESS!\n\nThe NXM handler is working correctly.\nCheck your MO2/Vortex window - it should have received the download request."
            result_text.color = ft.Colors.GREEN
        else:
            error = results.get("error", "Unknown error")
            result_text.value = f"[FAILED] FAILED\n\nError: {error}"
            result_text.color = ft.Colors.RED

        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text("Test NXM Handler"),
        content=ft.Container(
            content=ft.Column([
                ft.Text("NXM Handler Status:", weight=ft.FontWeight.BOLD),
                ft.Text("\n".join(status_text)),
                ft.Divider(),
                ft.Text("Test Configuration:", weight=ft.FontWeight.BOLD),
                test_url_field,
                ft.Divider(),
                ft.Text("Test Results:", weight=ft.FontWeight.BOLD),
                result_text,
            ], tight=True, scroll=ft.ScrollMode.AUTO),
            width=500,
            height=400,
        ),
        actions=[
            ft.ElevatedButton("Run Test", icon="play_arrow", on_click=run_test),
            ft.TextButton("Close", on_click=lambda _: close_dialog_callback(dlg)),
        ],
    )
    page.open(dlg)
