"""
Addons view for NaK application
Browse and install community addons for additional mod loader support
"""
import flet as ft
from src.addons import AddonManager


def get_addons_view(page: ft.Page, show_error_callback):
    """
    Create and return the addons view

    Args:
        page: Flet page instance
        show_error_callback: Callback to show error dialogs

    Returns:
        ft.Column: The addons view content
    """
    addon_manager = AddonManager()

    content = [
        ft.Text("Addons", size=32, weight=ft.FontWeight.BOLD),
        ft.Text("Additional mod loader support", color=ft.Colors.GREY_500),
        ft.Divider(height=20),
    ]

    # Container for addon cards (will be updated dynamically)
    addon_cards_container = ft.Column([], spacing=10)

    def refresh_addons():
        """Refresh the addon list"""
        addon_cards_container.controls.clear()

        # Show loading indicator
        loading = ft.ProgressRing()
        addon_cards_container.controls.append(
            ft.Container(
                content=loading,
                alignment=ft.alignment.center,
                padding=20,
            )
        )
        page.update()

        try:
            # Fetch available addons
            catalog = addon_manager.fetch_addon_catalog()

            # Remove loading indicator
            addon_cards_container.controls.clear()

            if catalog is None:
                addon_cards_container.controls.append(
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Icon("error_outline", size=48, color=ft.Colors.RED),
                                ft.Text("Failed to fetch addon catalog", size=16),
                                ft.Text("Check your internet connection or try again later",
                                       size=12, color=ft.Colors.GREY_500),
                                ft.ElevatedButton(
                                    "Retry",
                                    icon="refresh",
                                    on_click=lambda _: refresh_addons(),
                                ),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                            padding=20,
                            alignment=ft.alignment.center,
                        ),
                    )
                )
            elif len(catalog) == 0:
                addon_cards_container.controls.append(
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Icon("info_outline", size=48, color=ft.Colors.BLUE),
                                ft.Text("No addons available yet", size=16),
                                ft.Text("Check back later for new addon releases",
                                       size=12, color=ft.Colors.GREY_500),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                            padding=20,
                            alignment=ft.alignment.center,
                        ),
                    )
                )
            else:
                # Display each addon
                for addon in catalog:
                    is_installed = addon_manager.is_addon_installed(addon['id'])

                    # Build action button
                    if is_installed:
                        # For installed addons, just show status chip (uninstall from Installed Addons section)
                        action_button = None
                        status_chip = ft.Container(
                            content=ft.Text("Installed", size=14, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.GREEN,
                            padding=ft.padding.symmetric(horizontal=15, vertical=8),
                            border_radius=10,
                        )
                    else:
                        action_button = ft.ElevatedButton(
                            "Install",
                            icon="download",
                            on_click=lambda _, a=addon: install_addon(a),
                        )
                        status_chip = None

                    addon_card = ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.ListTile(
                                    leading=ft.Icon("extension", size=48, color=ft.Colors.BLUE),
                                    title=ft.Text(addon['name'], size=18, weight=ft.FontWeight.BOLD),
                                    subtitle=ft.Text(addon.get('description', 'No description'), size=14),
                                ),
                                ft.Container(
                                    content=ft.Row([
                                        ft.Text(f"v{addon['version']}", size=12, color=ft.Colors.GREY_500),
                                        ft.Text(f"by {addon.get('author', 'Unknown')}",
                                               size=12, color=ft.Colors.GREY_500),
                                    ], spacing=10),
                                    padding=ft.padding.only(left=10, right=10),
                                ),
                                ft.Container(
                                    content=ft.Row([
                                        item for item in [action_button, status_chip] if item is not None
                                    ], spacing=10),
                                    padding=ft.padding.only(left=10, right=10, bottom=10, top=5),
                                ),
                            ], spacing=5),
                            padding=10,
                        ),
                    )

                    addon_cards_container.controls.append(addon_card)

            page.update()

        except Exception as e:
            addon_cards_container.controls.clear()
            addon_cards_container.controls.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Icon("error_outline", size=48, color=ft.Colors.RED),
                            ft.Text("Error loading addons", size=16),
                            ft.Text(str(e), size=12, color=ft.Colors.GREY_500),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                        padding=20,
                        alignment=ft.alignment.center,
                    ),
                )
            )
            page.update()

        # Also refresh the installed addons section
        show_installed_addons()

    def install_addon(addon_info):
        """Install an addon (fast, no dialog needed)"""
        # Show loading notification
        page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Installing {addon_info['name']}..."),
            bgcolor=ft.Colors.BLUE,
        )
        page.snack_bar.open = True
        page.update()

        # Install addon (runs synchronously but is fast)
        try:
            success = addon_manager.install_addon(addon_info, progress_callback=None)
        except Exception as e:
            success = False
            print(f"Installation error: {e}")

        # Show result
        if success:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"{addon_info['name']} installed successfully!"),
                bgcolor=ft.Colors.GREEN,
            )
            page.snack_bar.open = True
            refresh_addons()  # Refresh to show "Installed" status
        else:
            show_error_callback(
                "Installation Failed",
                f"Failed to install {addon_info['name']}. Check logs for details."
            )

        page.update()

    def uninstall_addon(addon_info):
        """Uninstall an addon"""
        def confirm_uninstall(_):
            confirm_dlg.open = False
            page.update()

            success = addon_manager.uninstall_addon(addon_info['id'])

            if success:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"{addon_info['name']} uninstalled successfully!"),
                    bgcolor=ft.Colors.GREEN,
                )
                page.snack_bar.open = True
                refresh_addons()  # Refresh to remove "Installed" status
            else:
                show_error_callback(
                    "Uninstall Failed",
                    f"Failed to uninstall {addon_info['name']}."
                )

            page.update()

        def cancel_uninstall(_):
            confirm_dlg.open = False
            page.update()

        confirm_dlg = ft.AlertDialog(
            title=ft.Text("Confirm Uninstall"),
            content=ft.Text(f"Are you sure you want to uninstall {addon_info['name']}?"),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_uninstall),
                ft.TextButton("Uninstall", on_click=confirm_uninstall),
            ],
        )

        page.overlay.append(confirm_dlg)
        confirm_dlg.open = True
        page.update()

    # Info card about addons
    info_card = ft.Card(
        content=ft.Container(
            content=ft.Row([
                ft.Icon("info_outline", color=ft.Colors.BLUE),
                ft.Column([
                    ft.Text("About Addons", weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Addons provide support for additional mod loaders beyond MO2 and Vortex. "
                        "Install only the addons you need for your specific games.",
                        size=12,
                        color=ft.Colors.GREY_400,
                    ),
                ], expand=True, spacing=5),
            ], spacing=10),
            padding=15,
        ),
    )

    content.append(info_card)
    content.append(ft.Divider(height=10))

    # Installed addons section
    installed_section = ft.Column([], spacing=10)

    def show_installed_addons():
        """Show locally installed addons"""
        installed_section.controls.clear()

        # Get installed addons
        installed = addon_manager.get_installed_addons()

        if installed:
            installed_section.controls.append(
                ft.Text("Installed Addons", size=20, weight=ft.FontWeight.BOLD)
            )

            for addon in installed:
                def run_addon_installer(addon_info):
                    """Run the addon installer for testing"""
                    try:
                        addon_id = addon_info['id']
                        addon_name = addon_info['name']

                        # Load the addon installer
                        import sys
                        from pathlib import Path

                        addon_path = Path.home() / ".config" / "nak" / "addons" / addon_id

                        # Add addon path to Python path
                        if str(addon_path) not in sys.path:
                            sys.path.insert(0, str(addon_path))

                        # Import the installer
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(
                            f"addon_{addon_id}",
                            addon_path / "installer.py"
                        )
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Get the installer class
                        installer_class = getattr(module, "SporeModLoaderInstaller")
                        installer = installer_class()

                        def actually_run_installer():
                            """Run the installer after user confirms"""
                            # Show simple waiting message
                            page.snack_bar = ft.SnackBar(
                                content=ft.Text("Preparing installer... please wait"),
                                bgcolor=ft.Colors.BLUE,
                            )
                            page.snack_bar.open = True
                            page.update()

                            try:
                                # Run installer synchronously (UI will freeze briefly but won't break)
                                success = installer.install(
                                    progress_callback=None,
                                    log_callback=None
                                )

                                if success:
                                    # Show completion dialog to finish setup
                                    show_finish_setup_dialog()
                                else:
                                    show_error_callback(
                                        "Installation Failed",
                                        f"Failed to install {addon_name}. Check logs for details."
                                    )

                                page.update()

                            except Exception as e:
                                show_error_callback("Installation Error", str(e))
                                page.update()

                        def show_finish_setup_dialog():
                            """Show dialog to finish setup after user completes ModAPI installation"""
                            def on_finish_setup(_):
                                finish_dlg.open = False
                                page.update()
                                create_launch_scripts_flow()

                            def on_cancel_finish(_):
                                finish_dlg.open = False
                                page.update()

                            finish_dlg = ft.AlertDialog(
                                title=ft.Text("Complete ModAPI Installation"),
                                content=ft.Container(
                                    content=ft.Column([
                                        ft.Text("Instructions:", size=13, weight=ft.FontWeight.BOLD),
                                        ft.Text("1. Click 'I am installing...for the first time'", size=12),
                                        ft.Text("2. Use the DEFAULT path (required - do not change it)", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400),
                                        ft.Text("3. Complete installation and click 'Exit'", size=12),
                                        ft.Divider(height=10),
                                        ft.Text("After installation, you'll choose where to create launch scripts.", size=12, color=ft.Colors.BLUE_400, italic=True),
                                    ], spacing=5, tight=True),
                                    width=450,
                                    padding=15,
                                ),
                                actions=[
                                    ft.TextButton("Cancel", on_click=on_cancel_finish),
                                    ft.ElevatedButton("Finish Setup", on_click=on_finish_setup),
                                ],
                            )

                            page.overlay.append(finish_dlg)
                            finish_dlg.open = True
                            page.update()

                        def create_launch_scripts_flow():
                            """Ask where to create launch scripts and create them"""
                            from pathlib import Path

                            def create_scripts_at_location(base_dir):
                                """Helper to create scripts at specified location"""
                                try:
                                    # Find ModAPI installation
                                    from src.utils.nak_paths import get_prefixes_dir
                                    prefix_path = get_prefixes_dir() / "spore_modloader" / "pfx"

                                    # Search for ModAPI installation in Wine prefix
                                    install_dir = installer.find_modapi_installation(prefix_path)

                                    if not install_dir:
                                        show_error_callback(
                                            "ModAPI Not Found",
                                            "Could not find ModAPI installation. Did you complete the installer?"
                                        )
                                        return

                                    # Verify installation
                                    if not installer.verify_installation(install_dir):
                                        show_error_callback(
                                            "Incomplete Installation",
                                            "ModAPI installation appears incomplete. Please run the installer again."
                                        )
                                        return

                                    # Create launch scripts IN the install_dir (where .exe files are)
                                    success = installer.create_launch_scripts(install_dir, prefix_path, install_dir)

                                    if success:
                                        # Create symlink at user's chosen location → install_dir
                                        symlink_name = "SPORE_ModAPI_Launcher_Kit"
                                        symlink_path = base_dir / symlink_name

                                        # Remove existing symlink/folder if needed
                                        if symlink_path.exists() or symlink_path.is_symlink():
                                            if symlink_path.is_symlink():
                                                symlink_path.unlink()
                                            else:
                                                import shutil
                                                shutil.rmtree(symlink_path)

                                        # Create symlink: chosen_location/SPORE_ModAPI_Launcher_Kit → install_dir
                                        try:
                                            symlink_path.symlink_to(install_dir)
                                            page.snack_bar = ft.SnackBar(
                                                content=ft.Text(f"Symlink created at {symlink_path}!"),
                                                bgcolor=ft.Colors.GREEN,
                                            )
                                            page.snack_bar.open = True
                                        except Exception as e:
                                            show_error_callback("Symlink Error", f"Failed to create symlink: {e}")

                                    else:
                                        show_error_callback("Error", "Failed to create launch scripts")

                                    page.update()

                                except Exception as e:
                                    import traceback
                                    error_details = traceback.format_exc()
                                    print(error_details)  # Print to terminal for debugging
                                    show_error_callback("Setup Error", f"{str(e)}\n\nSee terminal for full traceback")

                            def on_location_selected(location):
                                location_dlg.open = False
                                page.update()

                                # Show progress
                                page.snack_bar = ft.SnackBar(
                                    content=ft.Text("Creating launch scripts..."),
                                    bgcolor=ft.Colors.BLUE,
                                )
                                page.snack_bar.open = True
                                page.update()

                                # Determine base directory
                                if location == "desktop":
                                    base_dir = Path.home() / "Desktop"
                                    create_scripts_at_location(base_dir)
                                elif location == "games":
                                    base_dir = Path.home() / "Games"
                                    create_scripts_at_location(base_dir)
                                elif location == "custom":
                                    # Open file picker for custom location
                                    def on_folder_picked(e: ft.FilePickerResultEvent):
                                        if e.path:
                                            custom_path = Path(e.path)
                                            create_scripts_at_location(custom_path)
                                        else:
                                            page.snack_bar = ft.SnackBar(
                                                content=ft.Text("No folder selected"),
                                                bgcolor=ft.Colors.ORANGE,
                                            )
                                            page.snack_bar.open = True
                                            page.update()

                                    file_picker = ft.FilePicker(on_result=on_folder_picked)
                                    page.overlay.append(file_picker)
                                    page.update()
                                    file_picker.get_directory_path(dialog_title="Choose SporeModloader Location")
                                else:
                                    show_error_callback("Error", "Invalid location selected")

                            def on_installation_dir(_):
                                on_location_selected("installation")

                            def on_desktop(_):
                                on_location_selected("desktop")

                            def on_games_folder(_):
                                on_location_selected("games")

                            def on_browse(_):
                                on_location_selected("custom")

                            def on_cancel_location(_):
                                location_dlg.open = False
                                page.update()

                            location_dlg = ft.AlertDialog(
                                title=ft.Text("Create Symlink"),
                                content=ft.Container(
                                    content=ft.Column([
                                        ft.Text("Where should the symlink be created?", size=14),
                                        ft.Divider(height=10),
                                        ft.Text("A symlink to 'SPORE ModAPI Launcher Kit' will be created", size=12, color=ft.Colors.GREY_400),
                                        ft.Text("containing the ModAPI files and launch scripts.", size=12, color=ft.Colors.GREY_400),
                                    ], spacing=5, tight=True),
                                    width=400,
                                    padding=15,
                                ),
                                actions=[
                                    ft.TextButton("Cancel", on_click=on_cancel_location),
                                    ft.ElevatedButton("Desktop", on_click=on_desktop),
                                    ft.ElevatedButton("~/Games", on_click=on_games_folder),
                                    ft.ElevatedButton("Browse...", on_click=on_browse, icon="folder_open"),
                                ],
                            )

                            page.overlay.append(location_dlg)
                            location_dlg.open = True
                            page.update()

                        # Simple confirmation before launching
                        def on_start_install(_):
                            """Start installation"""
                            confirm_dlg.open = False
                            page.update()
                            actually_run_installer()

                        def on_cancel(_):
                            confirm_dlg.open = False
                            page.update()

                        confirm_dlg = ft.AlertDialog(
                            title=ft.Text("Spore Mod Loader Installation"),
                            content=ft.Container(
                                content=ft.Column([
                                    ft.Text("The ModAPI installer will open.", size=14, weight=ft.FontWeight.BOLD),
                                    ft.Divider(height=10),
                                    ft.Text("Instructions:", size=13, weight=ft.FontWeight.BOLD),
                                    ft.Text("1. Click 'I am installing...for the first time'", size=12),
                                    ft.Text("2. Use the DEFAULT path (required - do not change it)", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400),
                                    ft.Text("3. Complete installation and click 'Exit'", size=12),
                                    ft.Divider(height=10),
                                    ft.Text("After installation, you'll choose where to create launch scripts.", size=12, color=ft.Colors.BLUE_400, italic=True),
                                ], spacing=5, tight=True),
                                width=450,
                                padding=15,
                            ),
                            actions=[
                                ft.TextButton("Cancel", on_click=on_cancel),
                                ft.ElevatedButton("Start", on_click=on_start_install),
                            ],
                        )

                        page.overlay.append(confirm_dlg)
                        confirm_dlg.open = True
                        page.update()

                    except Exception as e:
                        show_error_callback("Error", f"Failed to run installer: {e}")

                addon_card = ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.ListTile(
                                leading=ft.Icon("extension", size=48, color=ft.Colors.GREEN),
                                title=ft.Text(addon['name'], size=18, weight=ft.FontWeight.BOLD),
                                subtitle=ft.Text(f"v{addon['version']} - Installed locally", size=14),
                            ),
                            ft.Container(
                                content=ft.Row([
                                    ft.ElevatedButton(
                                        "Run Installer",
                                        icon="play_arrow",
                                        on_click=lambda _, a=addon: run_addon_installer(a),
                                    ),
                                    ft.ElevatedButton(
                                        "Uninstall",
                                        icon="delete_outline",
                                        on_click=lambda _, a=addon: uninstall_addon(a),
                                        color=ft.Colors.RED,
                                    ),
                                ], spacing=10),
                                padding=ft.padding.only(left=10, right=10, bottom=10, top=5),
                            ),
                        ], spacing=5),
                        padding=10,
                    ),
                )

                installed_section.controls.append(addon_card)

            installed_section.controls.append(ft.Divider(height=10))

        page.update()

    # Show installed addons first
    show_installed_addons()
    content.append(installed_section)

    # Marketplace addons
    content.append(ft.Text("Marketplace", size=20, weight=ft.FontWeight.BOLD))
    content.append(addon_cards_container)

    # Initial load
    refresh_addons()

    return ft.Column(
        content,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
