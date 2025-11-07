"""
Error dialog for NaK application
Simple error message dialog with red styling
"""
import flet as ft


def show_error(page, title: str, message: str):
    """
    Show an error dialog

    Args:
        page: Flet page instance
        title: Dialog title
        message: Error message to display
    """
    def close_dlg(e):
        dlg.open = False
        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text(title, color=ft.Colors.ERROR),
        content=ft.Text(message),
        actions=[ft.TextButton("OK", on_click=close_dlg)],
        on_dismiss=close_dlg,
    )
    page.open(dlg)
