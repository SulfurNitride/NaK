"""
Getting Started View
Persistent page for first-time users and quick reference
"""

import flet as ft
import subprocess
import os
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_getting_started_view(page: ft.Page, proton_manager_callback):
    """
    Create Getting Started view

    Args:
        page: Flet page instance
        proton_manager_callback: Callback to open Proton Manager

    Returns:
        ft.Column: Getting started view
    """

    def open_proton_manager(e):
        """Open Proton Manager"""
        proton_manager_callback()

    def open_faq(e):
        """Open GitHub FAQ in browser"""
        import webbrowser
        faq_url = "https://github.com/SulfurNitride/NaK/blob/main/docs/FAQ.md"
        logger.info(f"Opening FAQ in browser: {faq_url}")
        try:
            webbrowser.open(faq_url)
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Opening FAQ in browser..."),
                bgcolor=ft.Colors.BLUE,
            )
        except Exception as e:
            logger.error(f"Failed to open FAQ: {e}")
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Failed to open FAQ: {e}"),
                bgcolor=ft.Colors.RED,
            )
        page.snack_bar.open = True
        page.update()

    return ft.Column([
        # Header
        ft.Container(
            content=ft.Row([
                ft.Icon("celebration", color=ft.Colors.PURPLE_400, size=40),
                ft.Column([
                    ft.Text("Welcome to NaK!", size=28, weight=ft.FontWeight.BOLD),
                    ft.Text("Linux Modding Helper", size=16, color=ft.Colors.GREY_500),
                ], spacing=2),
            ], spacing=15),
            padding=20,
        ),

        ft.Divider(height=1),

        # Content
        ft.Container(
            content=ft.Column([
                # Intro
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "NaK makes it easy to run Windows modding tools on Linux using Proton.",
                            size=15,
                        ),
                        ft.Text(
                            "Get started by following these three simple steps:",
                            size=14,
                            color=ft.Colors.GREY_400,
                        ),
                    ], spacing=5),
                    padding=ft.padding.only(bottom=20),
                ),

                # Step 1: Proton
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text("1", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                width=50,
                                height=50,
                                bgcolor=ft.Colors.BLUE_700,
                                border_radius=25,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column([
                                ft.Text(
                                    "Pick a Proton Version",
                                    size=20,
                                    weight=ft.FontWeight.BOLD
                                ),
                                ft.Text(
                                    "NaK needs Proton to run Windows modding tools",
                                    size=13,
                                    color=ft.Colors.GREY_500
                                ),
                            ], spacing=2, expand=True),
                        ], spacing=15),

                        ft.Container(height=10),

                        ft.Row([
                            ft.Icon("check_circle", color=ft.Colors.GREEN, size=20),
                            ft.Text(
                                "Recommended: Download Proton-GE (best compatibility)",
                                size=13,
                            ),
                        ], spacing=8),

                        ft.Row([
                            ft.Icon("check_circle", color=ft.Colors.BLUE, size=20),
                            ft.Text(
                                "Alternative: Use system Proton if you prefer",
                                size=13,
                            ),
                        ], spacing=8),

                        ft.Container(height=10),

                        ft.ElevatedButton(
                            "Open Proton Manager",
                            icon="cloud_download",
                            on_click=open_proton_manager,
                            bgcolor=ft.Colors.BLUE_700,
                            color=ft.Colors.WHITE,
                            height=45,
                        ),
                    ], spacing=8),
                    padding=20,
                    bgcolor="#0a1929",  # Darker blue
                    border_radius=10,
                ),

                ft.Container(height=15),

                # Step 2: MO2 Setup
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text("2", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                width=50,
                                height=50,
                                bgcolor=ft.Colors.BLUE_700,
                                border_radius=25,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column([
                                ft.Text(
                                    "Always Use Portable Mode for MO2",
                                    size=20,
                                    weight=ft.FontWeight.BOLD
                                ),
                                ft.Text(
                                    "This is CRITICAL for proper operation on Linux",
                                    size=13,
                                    color=ft.Colors.BLUE_200,
                                    weight=ft.FontWeight.BOLD
                                ),
                            ], spacing=2, expand=True),
                        ], spacing=15),

                        ft.Container(height=10),

                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Icon("warning", color=ft.Colors.BLUE_300, size=24),
                                    ft.Text(
                                        "When MO2 asks during installation:",
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.BLUE_200
                                    ),
                                ]),
                                ft.Row([
                                    ft.Icon("check_box", color=ft.Colors.GREEN, size=20),
                                    ft.Text("SELECT: Portable", size=14, weight=ft.FontWeight.BOLD),
                                ], spacing=5),
                                ft.Row([
                                    ft.Icon("cancel", color=ft.Colors.RED, size=20),
                                    ft.Text("NEVER SELECT: Global", size=14, weight=ft.FontWeight.BOLD),
                                ], spacing=5),
                            ], spacing=8),
                            padding=15,
                            bgcolor="#0d2136",  # Darker blue for inner box
                            border_radius=8,
                        ),

                        ft.Container(height=10),

                        ft.Row([
                            ft.Icon("arrow_right", color=ft.Colors.BLUE_400, size=20),
                            ft.Text(
                                "Portable mode keeps all files in one place",
                                size=13,
                            ),
                        ], spacing=8),

                        ft.Row([
                            ft.Icon("arrow_right", color=ft.Colors.BLUE_400, size=20),
                            ft.Text(
                                "Makes backups and management much easier",
                                size=13,
                            ),
                        ], spacing=8),

                        ft.Row([
                            ft.Icon("arrow_right", color=ft.Colors.BLUE_400, size=20),
                            ft.Text(
                                "Avoids Wine registry issues",
                                size=13,
                            ),
                        ], spacing=8),
                    ], spacing=8),
                    padding=20,
                    bgcolor="#0a1929",  # Darker blue
                    border_radius=10,
                ),

                ft.Container(height=15),

                # Step 3: FAQ
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Text("3", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                width=50,
                                height=50,
                                bgcolor=ft.Colors.BLUE_700,
                                border_radius=25,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column([
                                ft.Text(
                                    "Check FAQ & Known Issues",
                                    size=20,
                                    weight=ft.FontWeight.BOLD
                                ),
                                ft.Text(
                                    "Solutions to common problems and setup tips",
                                    size=13,
                                    color=ft.Colors.GREY_500
                                ),
                            ], spacing=2, expand=True),
                        ], spacing=15),

                        ft.Container(height=10),

                        ft.Row([
                            ft.Icon("menu_book", color=ft.Colors.BLUE_400, size=20),
                            ft.Text(
                                "Comprehensive FAQ with troubleshooting guides",
                                size=13,
                            ),
                        ], spacing=8),

                        ft.Row([
                            ft.Icon("bug_report", color=ft.Colors.BLUE_400, size=20),
                            ft.Text(
                                "Known issues and their solutions",
                                size=13,
                            ),
                        ], spacing=8),

                        ft.Row([
                            ft.Icon("tips_and_updates", color=ft.Colors.BLUE_400, size=20),
                            ft.Text(
                                "Tips & best practices for Linux modding",
                                size=13,
                            ),
                        ], spacing=8),

                        ft.Container(height=10),

                        ft.ElevatedButton(
                            "View FAQ & Known Issues",
                            icon="menu_book",
                            on_click=open_faq,
                            bgcolor=ft.Colors.BLUE_700,
                            color=ft.Colors.WHITE,
                            height=45,
                        ),
                    ], spacing=8),
                    padding=20,
                    bgcolor="#0a1929",  # Darker blue
                    border_radius=10,
                ),

                ft.Container(height=20),

                # Footer tips
                ft.Divider(),
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "Quick Tips:",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Row([
                            ft.Icon("lightbulb", color=ft.Colors.YELLOW, size=18),
                            ft.Text("You can switch between pages using the tabs on the left", size=12),
                        ], spacing=8),
                        ft.Row([
                            ft.Icon("lightbulb", color=ft.Colors.YELLOW, size=18),
                            ft.Text("Use the cloud icon (top right) to manage Proton versions", size=12),
                        ], spacing=8),
                        ft.Row([
                            ft.Icon("lightbulb", color=ft.Colors.YELLOW, size=18),
                            ft.Text("Check Settings to configure auto-detection and caching", size=12),
                        ], spacing=8),
                    ], spacing=8),
                    padding=15,
                    bgcolor=ft.Colors.GREY_900,
                    border_radius=8,
                ),

            ], spacing=0, scroll=ft.ScrollMode.AUTO),
            padding=20,
            expand=True,
        ),
    ], spacing=0, expand=True)
