"""
Progress Dialog Component

Reusable installation progress dialog with terminal output and progress bar.
Used by all mod manager installation workflows (MO2, Vortex).
"""

import flet as ft
from typing import Callable, Optional


class ProgressDialog:
    """
    Reusable progress dialog for installation workflows

    Features:
    - Terminal-style output with scrolling
    - Progress bar with percentage
    - Close button (disabled during operation)
    - Thread-safe UI updates
    - Customizable colors and title
    """

    def __init__(
        self,
        page: ft.Page,
        title: str,
        initial_message: str = "Starting...\n",
        color: str = ft.Colors.BLUE,
        width: int = 600
    ):
        """
        Initialize progress dialog

        Args:
            page: Flet page instance
            title: Dialog title
            initial_message: Initial terminal message
            color: Progress bar color (ft.Colors.*)
            width: Dialog width in pixels
        """
        self.page = page
        self.title = title
        self.initial_message = initial_message
        self.color = color
        self.width = width

        # Create UI components
        self.terminal_output = ft.TextField(
            value=initial_message,
            multiline=True,
            read_only=True,
            min_lines=15,
            max_lines=15,
            text_style=ft.TextStyle(font_family="monospace", size=12),
            bgcolor=ft.Colors.BLACK,
            color=ft.Colors.GREEN_300,
            border_color=ft.Colors.GREY_800,
        )

        self.progress_bar = ft.ProgressBar(
            width=500,
            value=0,
            bgcolor=ft.Colors.GREY_800,
            color=color
        )

        self.progress_text = ft.Text(
            "0%",
            size=14,
            weight=ft.FontWeight.BOLD
        )

        self.close_button = ft.ElevatedButton(
            "Close",
            disabled=True,
            on_click=lambda e: self.close()
        )

        # Create dialog
        self.dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column([
                self.terminal_output,
                ft.Row([
                    self.progress_bar,
                    self.progress_text
                ], alignment=ft.MainAxisAlignment.CENTER),
            ], tight=True, width=self.width, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            actions=[self.close_button],
            modal=True,
        )

    def show(self):
        """Open the progress dialog"""
        self.dialog.open = True
        self.page.open(self.dialog)
        self.page.update()

    def close(self):
        """Close the progress dialog"""
        self.dialog.open = False
        self.page.update()

    def append_log(self, message: str):
        """
        Append message to terminal output

        Args:
            message: Message to append (will add newline if not present)
        """
        if not message.endswith('\n'):
            message += '\n'
        self.terminal_output.value += message

        # Auto-scroll to bottom by setting focus
        self.terminal_output.focus()
        self.page.update()

    def update_progress(self, percent: float):
        """
        Update progress bar and percentage text

        Args:
            percent: Progress percentage (0-100)
        """
        # Clamp to 0-100 range
        percent = max(0, min(100, percent))

        self.progress_bar.value = percent / 100.0
        self.progress_text.value = f"{int(percent)}%"
        self.page.update()

    def enable_close(self):
        """Enable close button (call when operation completes)"""
        self.close_button.disabled = False
        self.page.update()

    def set_title(self, title: str):
        """Update dialog title"""
        self.dialog.title = ft.Text(title)
        self.page.update()

    def clear_log(self):
        """Clear terminal output"""
        self.terminal_output.value = self.initial_message
        self.page.update()

    def reset(self):
        """Reset dialog to initial state"""
        self.clear_log()
        self.update_progress(0)
        self.close_button.disabled = True
        self.page.update()


def create_progress_dialog(
    page: ft.Page,
    title: str,
    initial_message: str = "Starting...\n",
    color: str = ft.Colors.BLUE,
    on_close: Optional[Callable] = None
) -> ProgressDialog:
    """
    Factory function to create a progress dialog with custom close handler

    Args:
        page: Flet page instance
        title: Dialog title
        initial_message: Initial terminal message
        color: Progress bar color
        on_close: Optional callback when dialog is closed

    Returns:
        ProgressDialog instance
    """
    dialog = ProgressDialog(page, title, initial_message, color)

    # Wrap close method if callback provided
    if on_close:
        original_close = dialog.close
        def close_with_callback():
            original_close()
            on_close()
        dialog.close = close_with_callback

    return dialog
