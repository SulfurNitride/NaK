"""
Base dialog helper for NaK application
Reduces boilerplate code for creating dialogs
"""
import flet as ft


class DialogHelper:
    """Helper class for creating standardized dialogs"""

    @staticmethod
    def create_simple_dialog(page, title, content, on_close=None):
        """
        Create a simple dialog with title, content, and close button

        Args:
            page: Flet page instance
            title: Dialog title (string or ft.Control)
            content: Dialog content (ft.Control)
            on_close: Optional callback when dialog closes

        Returns:
            ft.AlertDialog: The created dialog
        """
        def close_handler(e):
            dlg.open = False
            page.update()
            if on_close:
                on_close(e)

        dlg = ft.AlertDialog(
            title=title if isinstance(title, ft.Control) else ft.Text(title),
            content=content,
            actions=[ft.TextButton("Close", on_click=close_handler)],
            on_dismiss=close_handler,
        )
        page.open(dlg)
        return dlg

    @staticmethod
    def create_dialog(page, title, content, actions, modal=True, on_dismiss=None):
        """
        Create a customizable dialog

        Args:
            page: Flet page instance
            title: Dialog title (string or ft.Control)
            content: Dialog content (ft.Control)
            actions: List of action buttons
            modal: Whether dialog is modal (default True)
            on_dismiss: Optional callback when dialog is dismissed

        Returns:
            ft.AlertDialog: The created dialog
        """
        def default_dismiss(e):
            dlg.open = False
            page.update()
            if on_dismiss:
                on_dismiss(e)

        dlg = ft.AlertDialog(
            title=title if isinstance(title, ft.Control) else ft.Text(title),
            content=content,
            actions=actions,
            modal=modal,
            on_dismiss=default_dismiss,
        )
        page.open(dlg)
        return dlg

    @staticmethod
    def create_error_dialog(page, title, message):
        """
        Create an error dialog with red styling

        Args:
            page: Flet page instance
            title: Error title
            message: Error message

        Returns:
            ft.AlertDialog: The created dialog
        """
        def close_handler(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(title, color=ft.Colors.ERROR),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_handler)],
            on_dismiss=close_handler,
        )
        page.open(dlg)
        return dlg

    @staticmethod
    def create_info_dialog(page, title, message):
        """
        Create an info dialog

        Args:
            page: Flet page instance
            title: Info title
            message: Info message

        Returns:
            ft.AlertDialog: The created dialog
        """
        def close_handler(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_handler)],
            on_dismiss=close_handler,
        )
        page.open(dlg)
        return dlg
