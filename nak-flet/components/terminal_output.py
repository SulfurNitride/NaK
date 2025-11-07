"""
Terminal Output Component

Provides a reusable terminal-style output widget for logging and displaying command output.
Extracted from main.py to improve code organization and reusability.
"""

import flet as ft


class TerminalOutput:
    """Terminal-style output widget for displaying logs and command output"""

    def __init__(self, initial_text="", min_lines=20, max_lines=20, width=None, height=None):
        """
        Initialize terminal output widget

        Args:
            initial_text: Initial text to display in the terminal
            min_lines: Minimum number of visible lines
            max_lines: Maximum number of visible lines
            width: Optional fixed width
            height: Optional fixed height
        """
        self.terminal = ft.TextField(
            value=initial_text,
            multiline=True,
            read_only=True,
            min_lines=min_lines,
            max_lines=max_lines,
            text_style=ft.TextStyle(font_family="monospace", size=12),
            bgcolor=ft.Colors.BLACK,
            color=ft.Colors.GREEN_300,
            border_color=ft.Colors.GREY_800,
            width=width,
            height=height,
        )

    def append_log(self, message):
        """
        Append a message to the terminal output

        Args:
            message: Message to append (newline will be added automatically)
        """
        self.terminal.value += f"{message}\n"

    def set_text(self, text):
        """
        Replace all terminal content with new text

        Args:
            text: New text to display
        """
        self.terminal.value = text

    def clear(self):
        """Clear all terminal content"""
        self.terminal.value = ""

    def get_control(self):
        """
        Get the underlying Flet control

        Returns:
            ft.TextField: The terminal text field control
        """
        return self.terminal


def create_terminal_output(initial_text="", min_lines=20, max_lines=20, width=None, height=None):
    """
    Factory function to create a terminal output widget

    Args:
        initial_text: Initial text to display in the terminal
        min_lines: Minimum number of visible lines
        max_lines: Maximum number of visible lines
        width: Optional fixed width
        height: Optional fixed height

    Returns:
        TerminalOutput: Terminal output widget instance
    """
    return TerminalOutput(
        initial_text=initial_text,
        min_lines=min_lines,
        max_lines=max_lines,
        width=width,
        height=height
    )
