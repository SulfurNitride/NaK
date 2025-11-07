"""
Cache Configuration dialog for NaK application
First-run dialog to configure caching preferences
"""
import flet as ft


def show_cache_config_dialog(page, cache_config):
    """
    Show first-run cache configuration dialog with granular options

    Args:
        page: Flet page instance
        cache_config: CacheConfig instance for saving preferences
    """
    # Create checkboxes for different cache types
    cache_dependencies_checkbox = ft.Checkbox(
        label="Cache dependencies (DirectX, .NET, VCRedist, etc.) - ~1.7GB",
        value=True,
    )
    cache_mo2_checkbox = ft.Checkbox(
        label="Cache MO2 - ~200MB",
        value=True,
    )
    cache_vortex_checkbox = ft.Checkbox(
        label="Cache Vortex - ~200MB",
        value=True,
    )

    def close_dlg(save: bool = True):
        """Close dialog and save preferences"""
        if save:
            # Save granular preferences based on checkboxes
            cache_deps = cache_dependencies_checkbox.value
            cache_mo2 = cache_mo2_checkbox.value
            cache_vortex = cache_vortex_checkbox.value
            enable_any = cache_deps or cache_mo2 or cache_vortex

            cache_config.set_cache_preferences(
                enable_cache=enable_any,
                cache_dependencies=cache_deps,
                cache_mo2=cache_mo2,
                cache_vortex=cache_vortex
            )

            # Show confirmation
            if enable_any:
                enabled_items = []
                if cache_deps:
                    enabled_items.append("dependencies")
                if cache_mo2:
                    enabled_items.append("MO2 files")
                if cache_vortex:
                    enabled_items.append("Vortex files")

                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Cache enabled for: {', '.join(enabled_items)}"),
                    bgcolor=ft.Colors.GREEN,
                )
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Cache disabled. Files will be re-downloaded each time."),
                    bgcolor=ft.Colors.ORANGE,
                )
            page.snack_bar.open = True
        else:
            # User cancelled - disable all caching
            cache_config.set_cache_preferences(
                enable_cache=False,
                cache_dependencies=False,
                cache_mo2=False,
                cache_vortex=False
            )

        dlg.open = False
        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text("Cache Configuration", size=20, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column([
                ft.Icon("storage", size=64, color=ft.Colors.BLUE),
                ft.Divider(),
                ft.Text("Welcome to NaK!", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text(
                    "NaK can cache downloaded files to make future installations much faster.",
                    size=14
                ),
                ft.Text(
                    "Choose what you want to cache:",
                    size=14,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Divider(),
                cache_dependencies_checkbox,
                cache_mo2_checkbox,
                cache_vortex_checkbox,
                ft.Divider(),
                ft.Text(
                    "Files will be stored in: ~/NaK/cache",
                    size=12,
                    color=ft.Colors.GREY_500,
                    italic=True
                ),
                ft.Text(
                    "You can change these settings later in the Settings menu",
                    size=11,
                    color=ft.Colors.GREY_600,
                    italic=True
                ),
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.START),
            width=550,
        ),
        actions=[
            ft.TextButton(
                "Don't Cache Anything",
                on_click=lambda _: close_dlg(False)
            ),
            ft.ElevatedButton(
                "Save Preferences",
                on_click=lambda _: close_dlg(True),
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE
            ),
        ],
        modal=True,
    )

    page.open(dlg)
