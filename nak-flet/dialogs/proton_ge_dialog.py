"""
Proton Manager Dialog
Allows users to:
1. Browse, download, and manage Proton-GE versions
2. Select from any installed Proton version (system or GE)
"""

import flet as ft
import threading
from pathlib import Path
from src.utils.proton_ge_manager import ProtonGEManager
from src.utils.proton_finder import ProtonFinder
from src.utils.logger import get_logger

logger = get_logger(__name__)


def show_proton_ge_manager(page: ft.Page):
    """Show Proton Manager dialog with tabs for Download and Select modes"""

    try:
        logger.info("Initializing Proton Manager...")

        manager = ProtonGEManager()
        proton_finder = ProtonFinder()

        active_version = manager.get_active_version()
        installed_versions = manager.get_installed_versions()
        available_versions = []
        all_proton_versions = []

        logger.info(f"Active version: {active_version}")
        logger.info(f"Installed GE versions: {installed_versions}")

        # State variables
        is_loading = [False]
        current_download = [None]

        # Progress indicators
        progress_bar = ft.ProgressBar(width=400, visible=False)
        progress_text = ft.Text("", size=12, color=ft.Colors.GREY_500, visible=False)
    except Exception as e:
        logger.error(f"Failed to initialize Proton Manager: {e}", exc_info=True)
        raise

    def close_dialog(e=None):
        """Close the dialog"""
        dialog.open = False
        page.update()

    def refresh_versions():
        """Refresh the installed versions list"""
        nonlocal active_version, installed_versions
        active_version = manager.get_active_version()
        installed_versions = manager.get_installed_versions()
        update_installed_list()
        update_available_list()
        update_all_proton_list()
        page.update()

    def fetch_available():
        """Fetch available Proton-GE versions from GitHub"""
        nonlocal available_versions

        if is_loading[0]:
            return

        is_loading[0] = True
        status_text.value = "Fetching versions from GitHub..."
        status_text.color = ft.Colors.BLUE
        fetch_button.disabled = True
        page.update()

        def fetch_thread():
            nonlocal available_versions
            try:
                available_versions = manager.fetch_available_versions(limit=30)

                if available_versions:
                    status_text.value = f"Found {len(available_versions)} versions"
                    status_text.color = ft.Colors.GREEN
                    update_available_list()
                else:
                    status_text.value = "No versions found"
                    status_text.color = ft.Colors.RED

            except Exception as e:
                logger.error(f"Failed to fetch versions: {e}")
                status_text.value = f"Error: {str(e)}"
                status_text.color = ft.Colors.RED
            finally:
                is_loading[0] = False
                fetch_button.disabled = False
                page.update()

        threading.Thread(target=fetch_thread, daemon=True).start()

    def scan_all_proton():
        """Scan system for all installed Proton versions"""
        nonlocal all_proton_versions

        if is_loading[0]:
            return

        is_loading[0] = True
        select_status_text.value = "Scanning for Proton installations..."
        select_status_text.color = ft.Colors.BLUE
        scan_button.disabled = True
        page.update()

        def scan_thread():
            nonlocal all_proton_versions
            try:
                all_proton_versions = proton_finder.find_all_proton_versions()

                if all_proton_versions:
                    select_status_text.value = f"Found {len(all_proton_versions)} Proton installation(s)"
                    select_status_text.color = ft.Colors.GREEN
                    update_all_proton_list()
                else:
                    select_status_text.value = "No Proton installations found"
                    select_status_text.color = ft.Colors.ORANGE

            except Exception as e:
                logger.error(f"Failed to scan for Proton: {e}")
                select_status_text.value = f"Error: {str(e)}"
                select_status_text.color = ft.Colors.RED
            finally:
                is_loading[0] = False
                scan_button.disabled = False
                page.update()

        threading.Thread(target=scan_thread, daemon=True).start()

    def download_version(version):
        """Download and install a Proton-GE version"""
        logger.info(f"Download button clicked for {version.tag_name}")

        if is_loading[0]:
            logger.warning("Already downloading, ignoring request")
            return

        is_loading[0] = True
        current_download[0] = version.tag_name
        logger.info(f"Starting download of {version.tag_name}")

        # Show progress
        progress_container.visible = True
        progress_bar.visible = True
        progress_bar.value = 0
        progress_text.visible = True
        progress_text.value = f"Downloading {version.tag_name}..."

        status_text.value = f"Downloading {version.tag_name}..."
        status_text.color = ft.Colors.BLUE
        page.update()

        def progress_callback(percent, downloaded_mb, total_mb):
            """Update progress bar"""
            progress_bar.value = percent / 100
            progress_text.value = f"Downloading {version.tag_name}: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({percent}%)"
            page.update()

        def download_thread():
            try:
                result = manager.download_version(version, progress_callback=progress_callback, delete_archive=True)

                if result:
                    # Set as active if it's the first installation
                    if not manager.get_active_version():
                        manager.set_active_version(version.tag_name)

                    status_text.value = f"Successfully installed {version.tag_name}"
                    status_text.color = ft.Colors.GREEN
                    refresh_versions()
                else:
                    status_text.value = f"Failed to install {version.tag_name}"
                    status_text.color = ft.Colors.RED

            except Exception as e:
                logger.error(f"Failed to download version: {e}")
                status_text.value = f"Error: {str(e)}"
                status_text.color = ft.Colors.RED
            finally:
                is_loading[0] = False
                current_download[0] = None
                progress_container.visible = False
                progress_bar.visible = False
                progress_text.visible = False
                page.update()

        threading.Thread(target=download_thread, daemon=True).start()

    def set_active(tag_name):
        """Set a Proton-GE version as active"""
        if manager.set_active_version(tag_name):
            status_text.value = f"Set {tag_name} as active"
            status_text.color = ft.Colors.GREEN
            refresh_versions()
        else:
            status_text.value = f"Failed to set {tag_name} as active"
            status_text.color = ft.Colors.RED
        page.update()

    def set_active_proton(proton_info):
        """Set any Proton version as active (system or GE)"""
        if manager.set_active_proton_path(proton_info.path):
            select_status_text.value = f"Set {proton_info.name} as active Proton"
            select_status_text.color = ft.Colors.GREEN
            refresh_versions()
        else:
            select_status_text.value = f"Failed to set {proton_info.name} as active"
            select_status_text.color = ft.Colors.RED
        page.update()

    def delete_version(tag_name):
        """Delete a Proton-GE version"""
        if manager.delete_version(tag_name):
            status_text.value = f"Deleted {tag_name}"
            status_text.color = ft.Colors.GREEN
            refresh_versions()
        else:
            status_text.value = f"Failed to delete {tag_name} (might be active)"
            status_text.color = ft.Colors.RED
        page.update()

    def cleanup_old():
        """Cleanup old versions - keep only the active version"""
        active = manager.get_active_version()

        if not active:
            status_text.value = "No active version set - cannot cleanup"
            status_text.color = ft.Colors.RED
            page.update()
            return

        # Delete all versions except the active one
        deleted = []
        for version in installed_versions:
            if version != active:
                if manager.delete_version(version):
                    deleted.append(version)

        if deleted:
            status_text.value = f"Deleted {len(deleted)} old versions, kept active: {active}"
            status_text.color = ft.Colors.GREEN
            refresh_versions()
        else:
            status_text.value = f"No old versions to delete (only {active} is installed)"
            status_text.color = ft.Colors.BLUE
        page.update()

    def calculate_total_disk_usage():
        """Calculate total disk space used by installed versions"""
        try:
            import subprocess
            from pathlib import Path

            proton_ge_dir = Path.home() / "NaK" / "ProtonGE"

            if not proton_ge_dir.exists() or not installed_versions:
                return 0

            # Use du to get total size of all installed versions
            result = subprocess.run(
                ["du", "-sb"] + [str(proton_ge_dir / v) for v in installed_versions],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Sum up all the sizes (first column of each line)
                total_bytes = sum(int(line.split()[0]) for line in result.stdout.strip().split('\n') if line)
                total_gb = total_bytes / (1024 ** 3)
                return total_gb

            return 0
        except Exception as e:
            logger.error(f"Failed to calculate disk usage: {e}")
            return 0

    def update_installed_list():
        """Update the installed GE versions display"""
        installed_list.controls.clear()

        if not installed_versions:
            installed_list.controls.append(
                ft.Text("No Proton-GE versions installed", color=ft.Colors.GREY_500, italic=True)
            )
        else:
            # Add disk usage info at the top
            total_gb = calculate_total_disk_usage()
            disk_usage_text = ft.Text(
                f"Total disk usage: {total_gb:.2f} GB ({len(installed_versions)} version{'s' if len(installed_versions) != 1 else ''} × ~1.4 GB each)",
                size=12,
                color=ft.Colors.BLUE_400,
                italic=True
            )
            installed_list.controls.append(disk_usage_text)
            installed_list.controls.append(ft.Divider(height=10))
            for version in installed_versions:
                is_active = (version == active_version)

                row = ft.Row(
                    [
                        ft.IconButton(
                            icon="check_circle" if is_active else "radio_button_unchecked",
                            icon_color=ft.Colors.GREEN if is_active else ft.Colors.GREY_500,
                            icon_size=20,
                            tooltip="Click to set as active" if not is_active else "Active version",
                            on_click=lambda e, v=version: set_active(v) if v != active_version else None,
                        ),
                        ft.Text(version, weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL),
                        ft.Text("(Active)", color=ft.Colors.GREEN, italic=True) if is_active else ft.Container(),
                        ft.Container(expand=True),  # Spacer
                        ft.IconButton(
                            icon="delete",
                            tooltip="Delete",
                            icon_color=ft.Colors.RED_400,
                            on_click=lambda e, v=version: delete_version(v),
                            disabled=is_active
                        ),
                    ],
                    spacing=10,
                )
                installed_list.controls.append(row)

        page.update()

    def update_available_list():
        """Update the available Proton-GE versions display"""
        available_list.controls.clear()

        if not available_versions:
            available_list.controls.append(
                ft.Text("Click 'Fetch Versions' to load", color=ft.Colors.GREY_500, italic=True)
            )
        else:
            for version in available_versions:
                is_installed = manager.is_version_installed(version.tag_name)

                row = ft.Row(
                    [
                        ft.Icon(
                            "download_done" if is_installed else "download",
                            color=ft.Colors.GREEN if is_installed else ft.Colors.BLUE,
                            size=20
                        ),
                        ft.Column(
                            [
                                ft.Text(version.tag_name, weight=ft.FontWeight.BOLD),
                                ft.Text(
                                    f"{version.size / (1024 * 1024):.1f} MB • {version.published_at[:10]}",
                                    size=11,
                                    color=ft.Colors.GREY_500
                                ),
                            ],
                            spacing=2,
                        ),
                        ft.Container(expand=True),  # Spacer
                        ft.ElevatedButton(
                            "Installed" if is_installed else "Download",
                            icon="check" if is_installed else "download",
                            on_click=lambda e, v=version: download_version(v),
                            disabled=is_installed
                        ),
                    ],
                    spacing=10,
                )
                available_list.controls.append(row)

        page.update()

    def update_all_proton_list():
        """Update the all Proton versions display (system + GE)"""
        all_proton_list.controls.clear()

        if not all_proton_versions:
            all_proton_list.controls.append(
                ft.Text("Click 'Scan System' to find Proton installations", color=ft.Colors.GREY_500, italic=True)
            )
        else:
            # Get current active Proton directory
            active_dir = manager.get_active_proton_directory()

            # Group by type for better organization
            steam_protons = [p for p in all_proton_versions if p.proton_type == "steam"]
            ge_protons = [p for p in all_proton_versions if p.proton_type == "proton-ge"]
            custom_protons = [p for p in all_proton_versions if p.proton_type == "custom"]

            # Helper to create proton row
            def create_proton_row(proton):
                is_active = active_dir and active_dir.resolve() == proton.path.resolve()

                # Determine icon and color based on type
                if proton.proton_type == "steam":
                    icon = "sports_esports"
                    icon_color = ft.Colors.BLUE_400
                elif proton.proton_type == "proton-ge":
                    icon = "star"
                    icon_color = ft.Colors.PURPLE_400
                else:
                    icon = "extension"
                    icon_color = ft.Colors.ORANGE_400

                return ft.Row(
                    [
                        ft.IconButton(
                            icon="check_circle" if is_active else "radio_button_unchecked",
                            icon_color=ft.Colors.GREEN if is_active else ft.Colors.GREY_500,
                            icon_size=20,
                            tooltip="Click to set as active" if not is_active else "Active Proton",
                            on_click=lambda e, p=proton: set_active_proton(p) if not is_active else None,
                        ),
                        ft.Icon(icon, color=icon_color, size=20),
                        ft.Column(
                            [
                                ft.Row([
                                    ft.Text(proton.name, weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL),
                                    ft.Text("(Active)", color=ft.Colors.GREEN, italic=True, size=12) if is_active else ft.Container(),
                                ]),
                                ft.Text(
                                    f"{proton.proton_type.replace('-', ' ').title()} • {str(proton.path)[:60]}...",
                                    size=11,
                                    color=ft.Colors.GREY_500
                                ),
                            ],
                            spacing=2,
                        ),
                        ft.Container(expand=True),
                    ],
                    spacing=10,
                )

            # Add Steam Protons
            if steam_protons:
                all_proton_list.controls.append(ft.Text("Steam Proton", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400))
                for proton in steam_protons:
                    all_proton_list.controls.append(create_proton_row(proton))
                all_proton_list.controls.append(ft.Divider(height=10))

            # Add Proton-GE versions
            if ge_protons:
                all_proton_list.controls.append(ft.Text("Proton-GE", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_400))
                for proton in ge_protons:
                    all_proton_list.controls.append(create_proton_row(proton))
                all_proton_list.controls.append(ft.Divider(height=10))

            # Add custom Protons
            if custom_protons:
                all_proton_list.controls.append(ft.Text("Custom Proton", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400))
                for proton in custom_protons:
                    all_proton_list.controls.append(create_proton_row(proton))

        page.update()

    # ==================== UI Components ====================

    # Status texts
    status_text = ft.Text("", size=14)
    select_status_text = ft.Text("", size=14)

    # Buttons
    fetch_button = ft.ElevatedButton(
        "Fetch Versions from GitHub",
        icon="refresh",
        on_click=lambda e: fetch_available()
    )

    cleanup_button = ft.ElevatedButton(
        "Cleanup Old Versions",
        icon="cleaning_services",
        on_click=lambda e: cleanup_old(),
        tooltip="Delete all versions except the active one"
    )

    scan_button = ft.ElevatedButton(
        "Scan System",
        icon="search",
        on_click=lambda e: scan_all_proton(),
        tooltip="Scan for all installed Proton versions"
    )

    # Lists
    installed_list = ft.Column([], spacing=5, scroll=ft.ScrollMode.AUTO)
    available_list = ft.Column([], spacing=5, scroll=ft.ScrollMode.AUTO)
    all_proton_list = ft.Column([], spacing=5, scroll=ft.ScrollMode.AUTO)

    # Progress container
    progress_container = ft.Column([
        progress_text,
        progress_bar,
    ], visible=False, spacing=5)

    # ==================== Tab 1: Download Proton-GE ====================
    download_tab_content = ft.Container(
        content=ft.Column(
            [
                # Status
                ft.Row([status_text]),
                ft.Divider(),

                # Progress indicators
                progress_container,

                # Installed versions section
                ft.Text("Installed Proton-GE Versions", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=installed_list,
                    height=150,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    border_radius=5,
                    padding=10,
                ),

                ft.Divider(),

                # Available versions section
                ft.Row([
                    ft.Text("Available Versions", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    cleanup_button,
                    ft.VerticalDivider(width=10),
                    fetch_button,
                ]),
                ft.Container(
                    content=available_list,
                    height=250,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    border_radius=5,
                    padding=10,
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=10,
    )

    # ==================== Tab 2: Select Installed Proton ====================
    select_tab_content = ft.Container(
        content=ft.Column(
            [
                # Info box
                ft.Container(
                    content=ft.Row([
                        ft.Icon("info", color=ft.Colors.BLUE_400),
                        ft.Column([
                            ft.Text(
                                "Select from any Proton version installed on your system",
                                weight=ft.FontWeight.BOLD,
                                size=14
                            ),
                            ft.Text(
                                "This includes Steam's official Proton, Proton-GE, and custom compatibility tools",
                                size=12,
                                color=ft.Colors.GREY_500
                            ),
                        ], spacing=2, expand=True),
                    ]),
                    bgcolor=ft.Colors.BLUE_900,
                    padding=10,
                    border_radius=5,
                ),

                ft.Divider(),

                # Status
                ft.Row([select_status_text]),

                ft.Divider(),

                # All Proton versions section
                ft.Row([
                    ft.Text("All Installed Proton Versions", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    scan_button,
                ]),
                ft.Container(
                    content=all_proton_list,
                    height=450,
                    border=ft.border.all(1, ft.Colors.GREY_700),
                    border_radius=5,
                    padding=10,
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=10,
    )

    # ==================== Tabs ====================
    tabs = ft.Tabs(
        selected_index=0,
        tabs=[
            ft.Tab(
                text="Download Proton-GE",
                icon=ft.Icons.DOWNLOAD,
                content=download_tab_content,
            ),
            ft.Tab(
                text="Select Installed Proton",
                icon=ft.Icons.FOLDER_OPEN,
                content=select_tab_content,
            ),
        ],
        expand=True,
    )

    # ==================== Dialog ====================
    dialog = ft.AlertDialog(
        title=ft.Row([
            ft.Icon("science", color=ft.Colors.PURPLE_400),
            ft.Text("Proton Manager"),
        ]),
        content=ft.Container(
            content=tabs,
            width=800,
            height=650,
        ),
        actions=[
            ft.TextButton("Close", on_click=close_dialog),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    try:
        # Initialize lists
        update_installed_list()
        logger.info("Lists initialized successfully")

        # Add on_dismiss handler
        dialog.on_dismiss = close_dialog

        # Open dialog
        page.open(dialog)
        logger.info("Dialog opened successfully")

        # Auto-fetch versions from GitHub on open
        fetch_available()

        # Auto-scan system for all Proton installations (with small delay to let UI render)
        def delayed_scan():
            import time
            time.sleep(0.5)  # Wait 500ms for UI to render
            scan_all_proton()

        threading.Thread(target=delayed_scan, daemon=True).start()

    except Exception as e:
        logger.error(f"Failed to show dialog: {e}", exc_info=True)
        raise
