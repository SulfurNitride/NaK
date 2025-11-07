"""
Info dialog for NaK application
Simple informational message dialog
"""
import flet as ft


def show_info(page, title: str, message: str):
    """
    Show an informational dialog

    Args:
        page: Flet page instance
        title: Dialog title
        message: Info message to display
    """
    def close_dlg(e):
        dlg.open = False
        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text(title),
        content=ft.Text(message),
        actions=[ft.TextButton("OK", on_click=close_dlg)],
        on_dismiss=close_dlg,
    )
    page.open(dlg)
