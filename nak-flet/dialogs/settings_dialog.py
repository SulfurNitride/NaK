"""
Settings dialog
Allows users to configure Proton, cache, logging, and other application settings
"""

import flet as ft
import logging
from pathlib import Path
from src.utils.logger import get_logger
from src.utils.nak_storage_manager import NaKStorageManager

logger = get_logger(__name__)


def show_settings(page: ft.Page, core, file_picker_proton, show_error_callback, test_save_symlinker_callback, get_installed_proton_versions_func):
    """
    Show settings dialog

    Args:
        page: Flet page object
        core: Core object for settings access
        file_picker_proton: FilePicker for selecting Proton directory
        show_error_callback: Function to show error dialogs
        test_save_symlinker_callback: Callback to test save symlinker
        get_installed_proton_versions_func: Function to get installed Proton versions
    """
    logger.info("Settings button clicked")

    # Get current settings
    current_settings = core.settings.settings

    # Get installed Proton versions
    installed_protons = get_installed_proton_versions_func()
    current_proton = current_settings.get("preferred_proton_version", installed_protons[0] if installed_protons else "Proton - Experimental")

    # Get cache configuration
    try:
        from src.utils.cache_config import CacheConfig
        cache_config = CacheConfig()
        cache_info = cache_config.get_cache_info()
    except Exception as e:
        logger.error(f"Failed to load cache config: {e}")
        cache_config = None
        cache_info = {"size_mb": 0}

    # Get storage information
    storage_manager = NaKStorageManager()
    storage_info = storage_manager.get_storage_info()
    custom_storage_location = core.settings.get_nak_storage_location()

    # Create input fields
    proton_path_field = ft.TextField(
        label="Custom Proton Path",
        hint_text="/path/to/proton",
        value=current_settings.get("proton_path", ""),
        width=400,
        disabled=True  # Temporarily disabled
    )

    auto_detect_switch = ft.Switch(
        label="Auto-detect Proton",
        value=current_settings.get("auto_detect", True),
        tooltip="Automatically detect Proton installations"
    )

    preferred_proton_dropdown = ft.Dropdown(
        label="Preferred Proton Version",
        width=400,
        value=current_proton if current_proton in installed_protons else installed_protons[0],
        options=[ft.dropdown.Option(version) for version in installed_protons]
    )

    # Cache settings switches
    cache_deps_switch = ft.Switch(
        label="Cache dependencies (~1.7GB)",
        value=cache_config.should_cache_dependencies() if cache_config else True,
        tooltip="Cache DirectX, .NET, VCRedist, etc."
    )

    cache_mo2_switch = ft.Switch(
        label="Cache MO2 (~200MB)",
        value=cache_config.should_cache_mo2() if cache_config else True,
        tooltip="Cache MO2 installation archives"
    )

    cache_vortex_switch = ft.Switch(
        label="Cache Vortex (~200MB)",
        value=cache_config.should_cache_vortex() if cache_config else True,
        tooltip="Cache Vortex installation archives"
    )

    log_level_dropdown = ft.Dropdown(
        label="Log Level",
        width=400,
        value=current_settings.get("log_level", "DEBUG"),
        options=[
            ft.dropdown.Option("DEBUG"),
            ft.dropdown.Option("INFO"),
            ft.dropdown.Option("WARNING"),
            ft.dropdown.Option("ERROR"),
        ]
    )

    # Storage location field
    storage_location_field = ft.TextField(
        label="NaK Storage Location",
        hint_text="Leave empty for default (~/NaK)",
        value=custom_storage_location or "",
        width=400,
        read_only=True
    )

    # Storage status text
    used_space = storage_info.get('used_space_gb', 0)
    status_text_value = f"Current: {storage_info['real_path']}\n"
    if used_space > 0:
        status_text_value += f"Using {used_space:.2f}GB, {storage_info['free_space_gb']:.1f}GB free"
    else:
        status_text_value += f"{storage_info['free_space_gb']:.1f}GB free"

    storage_status_text = ft.Text(
        status_text_value,
        size=12,
        color=ft.Colors.GREEN if storage_info['exists'] else ft.Colors.ORANGE,
        italic=True
    )

    # FilePicker for storage location
    file_picker_storage = ft.FilePicker()

    # FilePicker handlers
    def handle_pick_proton(e: ft.FilePickerResultEvent):
        if e.path:
            proton_path_field.value = e.path
            page.update()

    def handle_pick_storage(e: ft.FilePickerResultEvent):
        if e.path:
            storage_location_field.value = e.path
            page.update()

    # Set the FilePicker result handlers for this dialog
    file_picker_proton.on_result = handle_pick_proton
    file_picker_storage.on_result = handle_pick_storage

    # Add storage file picker to page overlay
    if file_picker_storage not in page.overlay:
        page.overlay.append(file_picker_storage)
        page.update()

    def pick_proton_path(e):
        """Pick Proton path using file dialog"""
        file_picker_proton.get_directory_path(dialog_title="Select Proton Directory")

    def pick_storage_location(e):
        """Pick storage location using file dialog"""
        file_picker_storage.get_directory_path(dialog_title="Select NaK Storage Location")

    def preview_migration(e=None):
        """Show migration preview before applying"""
        new_location = storage_location_field.value

        if not new_location:
            show_error_callback("No Location Selected", "Please select a storage location first")
            return

        new_path = Path(new_location)

        # Get preview
        preview = storage_manager.preview_migration(new_path)

        if not preview["valid"]:
            show_error_callback("Migration Preview Failed", preview["error"] or "Unknown error")
            return

        # Build preview content
        installations = preview["installations"]
        preview_items = [
            ft.Text("Migration Preview", size=18, weight=ft.FontWeight.BOLD),
            ft.Divider(),
        ]

        # Source/Target info
        preview_items.extend([
            ft.Text("Storage Locations:", weight=ft.FontWeight.BOLD),
            ft.Text(f"From: {preview['source_path']}", size=12),
            ft.Text(f"To: {preview['target_path']}", size=12),
            ft.Divider(),
        ])

        # Space info
        preview_items.extend([
            ft.Text("Space Requirements:", weight=ft.FontWeight.BOLD),
            ft.Text(f"Data size: {preview['space_needed_gb']:.2f}GB", size=12),
            ft.Text(f"Available: {preview['space_available_gb']:.2f}GB", size=12),
            ft.Text(
                f"After migration: {preview['space_available_gb'] - preview['space_needed_gb']:.2f}GB free",
                size=12,
                color=ft.Colors.GREEN
            ),
            ft.Divider(),
        ])

        # Installations found
        if installations["total_count"] > 0:
            preview_items.append(ft.Text("Detected Installations:", weight=ft.FontWeight.BOLD))

            for prefix in installations["prefixes"]:
                preview_items.append(
                    ft.Row([
                        ft.Icon(
                            "folder_special",
                            color=ft.Colors.PURPLE_400 if prefix["type"] == "MO2" else ft.Colors.BLUE_400,
                            size=20
                        ),
                        ft.Text(f"{prefix['name']} ({prefix['type']})", size=12)
                    ])
                )

            summary_parts = []
            if installations["mo2_count"] > 0:
                summary_parts.append(f"{installations['mo2_count']} MO2")
            if installations["vortex_count"] > 0:
                summary_parts.append(f"{installations['vortex_count']} Vortex")

            preview_items.append(
                ft.Text(
                    f"Total: {', '.join(summary_parts)} installation(s)",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_500
                )
            )

            if installations["has_proton_ge"]:
                preview_items.append(ft.Text("✓ Proton-GE installations", size=11, color=ft.Colors.GREEN))
            if installations["has_cache"]:
                preview_items.append(ft.Text("✓ Cached dependencies", size=11, color=ft.Colors.GREEN))

            ft.Divider(),
        else:
            preview_items.append(ft.Text("No existing installations detected", size=12, italic=True))
            preview_items.append(ft.Divider())

        # Warnings
        if preview["warnings"]:
            preview_items.append(ft.Text("Warnings:", weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE))
            for warning in preview["warnings"]:
                preview_items.append(
                    ft.Row([
                        ft.Icon("warning", color=ft.Colors.ORANGE, size=16),
                        ft.Text(warning, size=11)
                    ])
                )
            preview_items.append(ft.Divider())

        # Info box
        preview_items.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon("info", color=ft.Colors.BLUE_400),
                    ft.Text(
                        "All paths work through symlinks - existing installations will continue working!",
                        size=11,
                        color=ft.Colors.BLUE_300,
                        expand=True
                    )
                ]),
                bgcolor=ft.Colors.BLUE_900,
                padding=10,
                border_radius=5
            )
        )

        def on_close_preview(e):
            preview_dlg.open = False
            page.update()

        preview_dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Icon("preview", color=ft.Colors.BLUE_400),
                ft.Text("Migration Preview"),
            ]),
            content=ft.Column(
                preview_items,
                tight=True,
                width=500,
                scroll=ft.ScrollMode.AUTO,
                height=400
            ),
            actions=[
                ft.TextButton("Close", on_click=on_close_preview),
            ],
        )
        page.open(preview_dlg)

    def apply_storage_location(e=None):
        """Apply new storage location with symlink"""
        new_location = storage_location_field.value

        if not new_location:
            # Reset to default (rollback)
            if storage_info['is_symlink']:
                def confirm_rollback(e):
                    rollback_dlg.open = False
                    page.update()

                    success, message = storage_manager.remove_symlink(restore_backup=True)
                    if success:
                        core.settings.set_nak_storage_location("")
                        page.snack_bar = ft.SnackBar(
                            content=ft.Text("Rolled back to default storage location"),
                            bgcolor=ft.Colors.GREEN,
                        )
                        # Update display
                        storage_info_updated = storage_manager.get_storage_info()
                        storage_status_text.value = f"Current: {storage_info_updated['real_path']} ({storage_info_updated['free_space_gb']:.1f}GB free)"
                        storage_status_text.color = ft.Colors.GREEN
                        storage_location_field.value = ""
                    else:
                        show_error_callback("Rollback Failed", message)

                    page.snack_bar.open = True
                    page.update()

                def cancel_rollback(e):
                    rollback_dlg.open = False
                    page.update()

                rollback_dlg = ft.AlertDialog(
                    title=ft.Text("Rollback to Default Location?"),
                    content=ft.Text(
                        f"This will remove the symlink and restore ~/NaK to its default location.\n\n"
                        f"Current location: {storage_info['real_path']}\n\n"
                        f"Your data will remain at the current location and can be manually moved if needed."
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=cancel_rollback),
                        ft.ElevatedButton("Rollback", icon="undo", on_click=confirm_rollback, bgcolor=ft.Colors.ORANGE),
                    ],
                )
                page.open(rollback_dlg)
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Already using default location"),
                    bgcolor=ft.Colors.ORANGE,
                )
                page.snack_bar.open = True
                page.update()
            return

        # Validate and apply new location
        new_path = Path(new_location)
        is_valid, error_msg = storage_manager.validate_storage_location(new_path)

        if not is_valid:
            show_error_callback("Invalid Location", error_msg)
            return

        # Ask user if they want to move existing data
        def confirm_setup(move_data: bool):
            confirm_storage_dlg.open = False
            page.update()

            # Show progress
            progress_dlg = ft.AlertDialog(
                title=ft.Text("Setting up storage..."),
                content=ft.Column([
                    ft.ProgressRing(),
                    ft.Text("Please wait while we set up the new storage location...", size=12)
                ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                modal=True
            )
            page.open(progress_dlg)
            page.update()

            success, message = storage_manager.setup_symlink(new_path, move_existing=move_data)

            progress_dlg.open = False
            page.update()

            if success:
                core.settings.set_nak_storage_location(str(new_path))
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(message),
                    bgcolor=ft.Colors.GREEN,
                )
                # Update storage info display
                storage_info_updated = storage_manager.get_storage_info()
                storage_status_text.value = f"Current: {storage_info_updated['real_path']} ({storage_info_updated['free_space_gb']:.1f}GB free, {storage_info_updated['used_space_gb']:.2f}GB used)"
                storage_status_text.color = ft.Colors.GREEN
            else:
                show_error_callback("Failed to Setup Storage", message)

            page.snack_bar.open = True
            page.update()

        def on_move_data(e):
            confirm_setup(move_data=True)

        def on_start_fresh(e):
            confirm_setup(move_data=False)

        def on_cancel_storage(e):
            confirm_storage_dlg.open = False
            page.update()

        # Show confirmation dialog
        confirm_storage_dlg = ft.AlertDialog(
            title=ft.Text("Setup Storage Location"),
            content=ft.Column([
                ft.Text(f"Set NaK storage to: {new_path / 'NaK'}"),
                ft.Divider(),
                ft.Text("What would you like to do with existing data?", weight=ft.FontWeight.BOLD),
                ft.Text("• Move Data: Transfer existing NaK folder to new location", size=12),
                ft.Text("  (Recommended - keeps everything intact)", size=11, color=ft.Colors.GREY_500),
                ft.Text("• Start Fresh: Keep existing data as backup, start clean", size=12),
                ft.Text("  (Creates backup as ~/NaK.backup)", size=11, color=ft.Colors.GREY_500),
            ], tight=True, height=180),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel_storage),
                ft.ElevatedButton("Start Fresh", icon="fiber_new", on_click=on_start_fresh),
                ft.ElevatedButton("Move Data", icon="drive_file_move", on_click=on_move_data, bgcolor=ft.Colors.BLUE_700),
            ],
        )
        page.open(confirm_storage_dlg)

    def close_dlg(e=None):
        """Close the dialog"""
        dlg.open = False
        page.update()

    def save_settings(e=None):
        """Save settings to file"""
        try:
            # Save Proton settings
            if proton_path_field.value:
                core.settings.set_proton_path(proton_path_field.value)

            core.settings.set_auto_detect(auto_detect_switch.value)
            core.settings.set_preferred_proton_version(preferred_proton_dropdown.value)

            # Save cache settings
            if cache_config:
                cache_deps = cache_deps_switch.value
                cache_mo2 = cache_mo2_switch.value
                cache_vortex = cache_vortex_switch.value
                enable_any = cache_deps or cache_mo2 or cache_vortex
                cache_config.set_cache_preferences(
                    enable_cache=enable_any,
                    cache_dependencies=cache_deps,
                    cache_mo2=cache_mo2,
                    cache_vortex=cache_vortex
                )

            # Save additional settings directly
            core.settings.settings["log_level"] = log_level_dropdown.value
            core.settings._save_settings()

            # Update logging level if changed
            if log_level_dropdown.value:
                logging.getLogger().setLevel(getattr(logging, log_level_dropdown.value))
                logger.info(f"Log level set to {log_level_dropdown.value}")

            close_dlg()
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Settings saved successfully!"),
                bgcolor=ft.Colors.GREEN,
            )
            page.snack_bar.open = True
            page.update()

        except Exception as e:
            show_error_callback("Save Failed", str(e))

    def reset_defaults(e=None):
        """Reset settings to defaults"""
        proton_path_field.value = ""
        auto_detect_switch.value = True
        preferred_proton_dropdown.value = installed_protons[0] if installed_protons else "Proton - Experimental"
        log_level_dropdown.value = "DEBUG"
        page.update()

    def clear_cache(e=None):
        """Clear the cache"""
        if not cache_config:
            show_error_callback("Cache Error", "Cache configuration not available")
            return

        # Confirmation dialog
        def confirm_clear(e):
            confirm_dlg.open = False
            page.update()

            try:
                import shutil
                from pathlib import Path
                cache_dir = Path(cache_config.get_cache_location())
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Cache cleared! ({cache_info['size_mb']}MB freed)"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Cache is already empty"),
                        bgcolor=ft.Colors.ORANGE,
                    )
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                show_error_callback("Clear Failed", str(ex))

        def cancel_clear(e):
            confirm_dlg.open = False
            page.update()

        confirm_dlg = ft.AlertDialog(
            title=ft.Text("Clear Cache?"),
            content=ft.Text(
                f"This will delete {cache_info['size_mb']}MB of cached files.\n\n"
                "Cached files will need to be re-downloaded for future installations."
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_clear),
                ft.ElevatedButton("Clear Cache", on_click=confirm_clear, bgcolor=ft.Colors.RED),
            ],
        )
        page.open(confirm_dlg)

    dlg = ft.AlertDialog(
        title=ft.Text("Settings"),
        content=ft.Column([
            ft.Icon("settings", size=48, color=ft.Colors.BLUE),
            ft.Divider(),
            ft.Text("Configuration", size=16, weight=ft.FontWeight.BOLD),
            ft.Divider(),

            # Storage Location Settings
            ft.Text("Storage Location", weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Row([
                    ft.Icon("info", color=ft.Colors.BLUE_400, size=16),
                    ft.Column([
                        ft.Text(
                            "Relocate NaK folder to a larger drive if needed",
                            size=12,
                            color=ft.Colors.GREY_400
                        ),
                        ft.Text(
                            "Leave empty to use default location (~/NaK)",
                            size=11,
                            color=ft.Colors.GREY_500,
                            italic=True
                        ),
                    ], spacing=2, expand=True),
                ]),
                bgcolor=ft.Colors.BLUE_900,
                padding=8,
                border_radius=5,
            ),
            storage_status_text,
            ft.Row([
                storage_location_field,
                ft.IconButton(
                    icon="folder_open",
                    tooltip="Browse",
                    on_click=pick_storage_location
                ),
            ], spacing=5),
            ft.Row([
                ft.ElevatedButton(
                    "Preview Migration",
                    icon="preview",
                    on_click=preview_migration,
                    bgcolor=ft.Colors.GREY_800
                ),
                ft.ElevatedButton(
                    "Apply",
                    icon="check",
                    on_click=apply_storage_location,
                    bgcolor=ft.Colors.BLUE_700
                ),
            ], spacing=10),
            ft.Text(
                "Tip: Clear the field and click Apply to rollback to default location",
                size=10,
                color=ft.Colors.GREY_600,
                italic=True
            ) if storage_info['is_symlink'] else ft.Container(),

            ft.Divider(),

            # Cache Settings
            ft.Text("Cache Configuration", weight=ft.FontWeight.BOLD),
            ft.Text(
                f"Current cache size: {cache_info['size_mb']}MB",
                size=12,
                color=ft.Colors.GREY_500
            ),
            cache_deps_switch,
            cache_mo2_switch,
            cache_vortex_switch,
            ft.ElevatedButton(
                "Clear Cache",
                icon="delete",
                on_click=clear_cache,
                bgcolor=ft.Colors.RED_400
            ) if cache_info['size_mb'] > 0 else ft.Container(),

            ft.Divider(),

            # Advanced Settings
            ft.Text("Advanced", weight=ft.FontWeight.BOLD),
            log_level_dropdown,

        ], tight=True, width=500, scroll=ft.ScrollMode.AUTO, height=650),
        actions=[
            ft.TextButton("Reset Defaults", on_click=reset_defaults),
            ft.TextButton("Cancel", on_click=close_dlg),
            ft.ElevatedButton("Save", on_click=save_settings),
        ],
        on_dismiss=close_dlg,
    )

    page.open(dlg)
