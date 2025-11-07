"""
MO2 Installer (Proton-GE Standalone Only)

Main orchestration class for Mod Organizer 2 installation with standalone Proton-GE.
NO Steam integration - uses ~/NaK/Prefixes for Wine prefixes.

Inherits functionality from focused mixin classes for better maintainability.
"""
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional

from src.core.installers.base.base_installer import BaseInstaller
from src.mod_managers.shared import ProtonGEDependencyMixin
from .verification import MO2VerificationMixin
from .download import MO2DownloadMixin


class MO2Installer(BaseInstaller, MO2VerificationMixin, MO2DownloadMixin, ProtonGEDependencyMixin):
    """Handles downloading and installing Mod Organizer 2 with standalone Proton-GE

    NO Steam integration - uses ~/NaK/Prefixes for Wine prefixes.
    """

    def __init__(self, core=None):
        """Initialize MO2 installer"""
        super().__init__(core=core, installer_name="MO2Installer")

        # Initialize GitHub downloader for MO2
        from src.core.installers.utils.github_downloader import GitHubDownloader
        self.github_downloader = GitHubDownloader(
            repo_owner="ModOrganizer2",
            repo_name="modorganizer",
            cache_prefix="mo2"
        )

        # Initialize dependency installer for managing dependencies
        from src.core.dependency_installer import DependencyInstaller
        self.dependency_installer = DependencyInstaller()

    def _cleanup_old_cache(self, current_filename: str):
        """
        Clean up old cached MO2 files

        Wrapper for base class method with MO2-specific prefix
        """
        super()._cleanup_old_cache(current_filename, prefix="ModOrganizer")

    def _get_winetricks_command(self) -> str:
        """
        Get winetricks command path

        This method uses the shared WinetricksManager for consistent winetricks handling.

        Returns:
            Path to winetricks command, or empty string if not found
        """
        from src.core.installers.utils.winetricks_manager import get_winetricks_manager

        winetricks_mgr = get_winetricks_manager()
        winetricks_path = winetricks_mgr.get_winetricks()

        return winetricks_path if winetricks_path else ""

    def download_mo2(self, install_dir: Optional[str] = None, custom_name: Optional[str] = None) -> Dict[str, Any]:
        """Download and install MO2 with standalone Proton-GE (no Steam integration)"""
        try:
            from src.utils.launch_script_generator import LaunchScriptGenerator
            from src.utils.proton_ge_manager import ProtonGEManager

            self.logger.info("Starting MO2 download and installation (Standalone Proton-GE mode)")

            # Get latest release info
            self._log_progress("Fetching latest MO2 release information...")
            release = self._get_latest_release()
            if not release:
                return {"success": False, "error": "Failed to get latest release information"}

            self._log_progress(f"Found latest version: {release.tag_name}")

            # Find the correct asset
            self._log_progress("Finding download asset...")
            download_url, filename = self._find_mo2_asset(release)
            if not download_url or not filename:
                return {"success": False, "error": "Could not find appropriate MO2 asset"}

            # Clean up old cached files
            self._cleanup_old_cache(filename)
            self._log_progress(f"Found asset: {filename}")

            # Get installation directory
            if not install_dir:
                install_dir = self._get_install_directory()
            if not install_dir:
                return {"success": False, "error": "No installation directory specified"}

            # Download the file
            downloaded_file = self._download_file(download_url, filename, progress_callback=getattr(self, 'progress_callback', None))
            if not downloaded_file:
                return {"success": False, "error": "Failed to download MO2"}

            # Check if caching is enabled
            from src.utils.cache_config import CacheConfig
            cache_config = CacheConfig()
            should_cleanup = not cache_config.should_cache_mo2()

            try:
                # Extract the archive
                self._log_progress("Extracting MO2 archive...")
                actual_install_dir = self._extract_archive(downloaded_file, install_dir)
                if not actual_install_dir:
                    return {"success": False, "error": "Failed to extract MO2 archive"}

                # Verify installation
                self._log_progress("Verifying installation...")
                verify_result = self._verify_installation(actual_install_dir)
                if not verify_result["success"]:
                    return verify_result

                self._log_progress("MO2 installation verified successfully!")
                self._send_progress_update(10)

                # Find the MO2 executable
                self._log_progress("Finding MO2 executable...")
                mo2_exe = self._find_mo2_executable(actual_install_dir)
                if not mo2_exe:
                    return {"success": False, "error": "Could not find ModOrganizer.exe"}
                self._send_progress_update(12)

                # Use custom name or default
                mo2_name = custom_name if custom_name else "Mod Organizer 2"

                # Generate prefix name and paths based on instance name
                script_gen = LaunchScriptGenerator()
                # Sanitize instance name for use in prefix path
                safe_instance_name = re.sub(r'[^a-zA-Z0-9\s]', '', mo2_name)
                safe_instance_name = safe_instance_name.replace(' ', '_').lower()
                prefix_name = f"mo2_{safe_instance_name}"
                prefix_name = script_gen.check_prefix_name_collision(prefix_name)

                # Create prefix directory structure in ~/NaK/Prefixes
                prefix_base = Path.home() / "NaK" / "Prefixes" / prefix_name
                prefix_path = prefix_base / "pfx"
                prefix_base.mkdir(parents=True, exist_ok=True)

                self._log_progress(f"Creating standalone prefix: {prefix_name}")
                self._send_progress_update(15)

                # Check if Proton-GE is installed
                ge_manager = ProtonGEManager()
                active_version = ge_manager.get_active_version()
                if not active_version:
                    return {
                        "success": False,
                        "error": "No Proton-GE version installed. Please install Proton-GE using the Proton-GE Manager first."
                    }

                proton_ge_path = Path.home() / "NaK" / "ProtonGE" / "active"
                self._log_progress(f"Using Proton-GE: {active_version}")
                self._send_progress_update(20)

                # Install dependencies with Proton-GE
                self._log_progress("Installing MO2 dependencies with Proton-GE...")
                self._send_progress_update(30)

                # MO2 dependencies list
                mo2_dependencies = [
                    "dotnet48",
                    "xact",
                    "xact_x64",
                    "vcrun2022",
                    "dotnet6",
                    "dotnet7",
                    "dotnet8",
                    "dotnet9",
                    "dotnetdesktop6",
                    "d3dcompiler_47",
                    "d3dx11_43",
                    "d3dcompiler_43",
                    "d3dx9_43",
                    "d3dx9",
                    "vkd3d",
                ]

                dependency_result = self._install_dependencies_proton_ge(
                    prefix_path=prefix_path,
                    proton_ge_path=proton_ge_path,
                    dependencies=mo2_dependencies,
                    app_name="MO2"
                )
                self._send_progress_update(70)

                # Generate launch script
                self._log_progress("Generating launch script...")
                mo2_exe_wine_path = f"Z:{mo2_exe.replace('/', chr(92))}"  # Convert to Wine path
                launch_script_path = script_gen.generate_mo2_launch_script(
                    prefix_path=prefix_path,
                    mo2_exe_wine_path=mo2_exe_wine_path,
                    instance_name=mo2_name,
                    proton_ge_path=proton_ge_path
                )
                self._send_progress_update(75)

                # Generate kill prefix script
                self._log_progress("Generating kill prefix script...")
                kill_script_path = script_gen.generate_kill_prefix_script(
                    prefix_path=prefix_path,
                    instance_name=mo2_name,
                    proton_ge_path=proton_ge_path
                )
                self._send_progress_update(78)

                # Generate fix game registry script
                self._log_progress("Generating game registry fixer script...")
                registry_script_path = script_gen.generate_fix_game_registry_script(
                    prefix_path=prefix_path,
                    instance_name=mo2_name,
                    proton_ge_path=proton_ge_path
                )
                self._send_progress_update(80)

                # Create symlink in MO2 directory
                self._log_progress("Creating launch symlink...")
                mo2_install_path = Path(mo2_exe).parent
                symlink_path = script_gen.create_symlink(
                    script_path=launch_script_path,
                    target_dir=mo2_install_path,
                    link_name="Launch MO2"
                )

                # Create kill symlink
                kill_symlink_path = script_gen.create_symlink(
                    script_path=kill_script_path,
                    target_dir=mo2_install_path,
                    link_name="Kill MO2 Prefix"
                )

                # Create registry fix symlink
                registry_symlink_path = script_gen.create_symlink(
                    script_path=registry_script_path,
                    target_dir=mo2_install_path,
                    link_name="Fix Game Registry"
                )
                self._send_progress_update(90)

                # Setup NXM handler
                self._log_progress("Setting up NXM link handler...")
                from src.utils.nxm_handler_manager import NXMHandlerManager
                nxm_manager = NXMHandlerManager()
                nxm_setup_success = nxm_manager.setup_instance(
                    prefix_path=str(prefix_path),
                    instance_name=mo2_name,
                    instance_type="MO2",
                    exe_path=mo2_exe_wine_path,
                    prefix_name=prefix_name,
                    proton_ge_version=active_version,
                    game_name=""
                )

                if nxm_setup_success:
                    self.logger.info("NXM handler setup successfully")
                    # Set this instance as the active handler
                    instance_info = nxm_manager.read_instance_marker(str(prefix_path))
                    if instance_info:
                        nxm_manager.set_active_handler(instance_info)
                        self.logger.info("Set as active NXM handler")
                else:
                    self.logger.warning("NXM handler setup failed (non-critical)")
                self._send_progress_update(95)

                # Setup save symlinks for detected Bethesda games
                self._log_progress("Setting up save symlinks for Bethesda games...")
                try:
                    from src.utils.save_symlinker import SaveSymlinker
                    save_symlinker = SaveSymlinker()
                    save_result = save_symlinker.setup_saves_for_nak_prefix(
                        nak_prefix_path=str(prefix_path),
                        manager_install_dir=actual_install_dir
                    )

                    if save_result.get("success"):
                        linked_games = save_result.get("linked_games", [])
                        if linked_games:
                            self.logger.info(f"Save symlinks created for {len(linked_games)} games: {', '.join(linked_games)}")
                        else:
                            self.logger.info("No Bethesda games detected for save symlinking")
                    else:
                        self.logger.warning(f"Save symlink setup had issues: {save_result.get('error', 'Unknown error')}")
                except Exception as e:
                    self.logger.warning(f"Save symlink setup failed (non-critical): {e}")

                # Final completion
                self._send_progress_update(100)

                result = {
                    "success": True,
                    "install_dir": actual_install_dir,
                    "mo2_exe": mo2_exe,
                    "version": release.tag_name,
                    "mo2_name": mo2_name,
                    "prefix_path": str(prefix_path),
                    "launch_script": str(launch_script_path),
                    "launch_symlink": str(symlink_path),
                    "proton_ge_version": active_version,
                    "message": f"Mod Organizer 2 {release.tag_name} installed successfully with Proton-GE {active_version}!",
                    "dependency_installation": dependency_result,
                }

                return result

            finally:
                # Clean up temporary file (only if caching is disabled)
                if should_cleanup:
                    try:
                        if os.path.exists(downloaded_file):
                            os.remove(downloaded_file)
                            self.logger.info("Cleaned up temporary file (caching disabled)")
                    except Exception as e:
                        self.logger.warning(f"Failed to clean up temporary file: {e}")
                else:
                    self.logger.info(f"Keeping cached file for future use: {downloaded_file}")

        except Exception as e:
            self.logger.error(f"MO2 installation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def setup_existing(self, mo2_dir: str, custom_name: str = "Mod Organizer 2") -> Dict[str, Any]:
        """Setup existing MO2 installation from directory with standalone Proton-GE"""
        try:
            from pathlib import Path
            from src.utils.proton_ge_manager import ProtonGEManager
            from src.utils.launch_script_generator import LaunchScriptGenerator
            import re

            self._log_progress(f"Setting up existing MO2 installation from: {mo2_dir}")
            self._send_progress_update(5)

            # Verify the directory exists
            self._log_progress("Verifying MO2 directory...")
            if not os.path.exists(mo2_dir):
                return {"success": False, "error": f"Directory does not exist: {mo2_dir}"}
            self._send_progress_update(10)

            # Find ModOrganizer.exe in the directory
            self._log_progress("Finding ModOrganizer.exe...")
            mo2_exe = self._find_mo2_executable(mo2_dir)
            if not mo2_exe:
                return {"success": False, "error": f"Could not find ModOrganizer.exe in: {mo2_dir}"}

            self._log_progress(f"Found ModOrganizer.exe at: {mo2_exe}")
            self._send_progress_update(20)

            # Generate prefix name from instance name
            safe_instance_name = re.sub(r'[^a-zA-Z0-9\s]', '', custom_name)
            safe_instance_name = safe_instance_name.replace(' ', '_').lower()
            prefix_name = f"mo2_{safe_instance_name}"

            # Check for name collision
            script_gen = LaunchScriptGenerator()
            prefix_name = script_gen.check_prefix_name_collision(prefix_name)

            self.logger.info(f"Using prefix name: {prefix_name}")
            self._log_progress(f"Using prefix: {prefix_name}")
            self._send_progress_update(25)

            # Check if Proton-GE is installed
            self._log_progress("Checking Proton-GE installation...")
            ge_manager = ProtonGEManager()
            active_version = ge_manager.get_active_version()

            if not active_version:
                return {
                    "success": False,
                    "error": "No Proton-GE version installed. Please install Proton-GE using the Proton-GE Manager in Settings."
                }

            proton_ge_path = Path.home() / "NaK" / "ProtonGE" / "active"
            self.logger.info(f"Using Proton-GE: {active_version}")
            self._log_progress(f"Using Proton-GE: {active_version}")
            self._send_progress_update(30)

            # Create prefix directory structure
            prefix_path = Path.home() / "NaK" / "Prefixes" / prefix_name / "pfx"
            prefix_path.parent.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Prefix path: {prefix_path}")
            self._send_progress_update(35)

            # Install dependencies
            self._log_progress("Installing Windows dependencies...")
            self.logger.info(f"Installing dependencies for prefix: {prefix_path}")

            # MO2 dependencies list
            mo2_dependencies = [
                "dotnet48",
                "xact",
                "xact_x64",
                "vcrun2022",
                "dotnet6",
                "dotnet7",
                "dotnet8",
                "dotnet9",
                "dotnetdesktop6",
                "d3dcompiler_47",
                "d3dx11_43",
                "d3dcompiler_43",
                "d3dx9_43",
                "d3dx9",
                "vkd3d",
            ]

            dependency_result = self._install_dependencies_proton_ge(
                prefix_path=prefix_path,
                proton_ge_path=proton_ge_path,
                dependencies=mo2_dependencies,
                app_name="MO2"
            )

            if not dependency_result["success"]:
                return {
                    "success": False,
                    "error": f"Dependency installation failed: {dependency_result.get('error', 'Unknown error')}"
                }

            self._log_progress("Dependencies installed successfully!")
            self._send_progress_update(75)

            # Convert exe path to Wine format
            mo2_exe_path = Path(mo2_exe)
            mo2_exe_wine_path = str(mo2_exe_path).replace('/', '\\')
            if not mo2_exe_wine_path.startswith("Z:"):
                mo2_exe_wine_path = f"Z:{mo2_exe_wine_path}"

            self.logger.info(f"MO2 exe: {mo2_exe}")
            self.logger.info(f"Wine path: {mo2_exe_wine_path}")

            # Generate launch script
            self._log_progress("Generating launch script...")
            launch_script_path = script_gen.generate_mo2_launch_script(
                prefix_path=prefix_path,
                mo2_exe_wine_path=mo2_exe_wine_path,
                instance_name=custom_name,
                proton_ge_path=proton_ge_path
            )
            self._send_progress_update(80)

            # Generate kill prefix script
            self._log_progress("Generating kill prefix script...")
            kill_script_path = script_gen.generate_kill_prefix_script(
                prefix_path=prefix_path,
                instance_name=custom_name,
                proton_ge_path=proton_ge_path
            )
            self._send_progress_update(83)

            # Generate game registry fix script
            self._log_progress("Generating game registry fixer script...")
            registry_script_path = script_gen.generate_fix_game_registry_script(
                prefix_path=prefix_path,
                instance_name=custom_name,
                proton_ge_path=proton_ge_path
            )
            self._send_progress_update(85)

            # Create symlinks in MO2 installation directory
            self._log_progress("Creating launch symlink...")
            mo2_install_dir = Path(mo2_dir)
            symlink_path = script_gen.create_symlink(
                script_path=launch_script_path,
                target_dir=mo2_install_dir,
                link_name="Launch MO2"
            )

            # Create kill symlink
            kill_symlink_path = script_gen.create_symlink(
                script_path=kill_script_path,
                target_dir=mo2_install_dir,
                link_name="Kill MO2 Prefix"
            )

            # Create registry fix symlink
            registry_symlink_path = script_gen.create_symlink(
                script_path=registry_script_path,
                target_dir=mo2_install_dir,
                link_name="Fix Game Registry"
            )
            self._send_progress_update(90)

            # Setup NXM handler
            self._log_progress("Setting up NXM link handler...")
            from src.utils.nxm_handler_manager import NXMHandlerManager
            nxm_manager = NXMHandlerManager()
            nxm_setup_success = nxm_manager.setup_instance(
                prefix_path=str(prefix_path),
                instance_name=custom_name,
                instance_type="MO2",
                exe_path=mo2_exe_wine_path,
                prefix_name=prefix_name,
                proton_ge_version=active_version,
                game_name=""
            )

            if nxm_setup_success:
                self.logger.info("NXM handler setup successfully")
                # Set this instance as the active handler
                instance_info = nxm_manager.read_instance_marker(str(prefix_path))
                if instance_info:
                    nxm_manager.set_active_handler(instance_info)
                    self.logger.info("Set as active NXM handler")
            else:
                self.logger.warning("NXM handler setup failed (non-critical)")
            self._send_progress_update(93)

            # Setup save symlinks for detected Bethesda games
            self._log_progress("Setting up save symlinks for Bethesda games...")
            try:
                from src.utils.save_symlinker import SaveSymlinker
                save_symlinker = SaveSymlinker()
                save_result = save_symlinker.setup_saves_for_nak_prefix(
                    nak_prefix_path=str(prefix_path),
                    manager_install_dir=mo2_dir
                )

                if save_result.get("success"):
                    linked_games = save_result.get("linked_games", [])
                    if linked_games:
                        self.logger.info(f"Save symlinks created for {len(linked_games)} games: {', '.join(linked_games)}")
                    else:
                        self.logger.info("No Bethesda games detected for save symlinking")
                else:
                    self.logger.warning(f"Save symlink setup had issues: {save_result.get('error', 'Unknown error')}")
            except Exception as e:
                self.logger.warning(f"Save symlink setup failed (non-critical): {e}")

            self._log_progress("MO2 setup completed successfully!")
            self._send_progress_update(100)

            return {
                "success": True,
                "install_dir": mo2_dir,
                "mo2_exe": mo2_exe,
                "mo2_name": custom_name,
                "prefix_path": str(prefix_path),
                "launch_script": str(launch_script_path),
                "launch_symlink": str(symlink_path),
                "proton_ge_version": active_version,
                "message": f"Existing MO2 installation configured successfully with Proton-GE!",
                "dependency_installation": dependency_result
            }

        except Exception as e:
            self.logger.error(f"MO2 setup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def remove_nxm_handlers(self) -> Dict[str, Any]:
        """Remove all NXM handlers configured by NaK"""
        try:
            from src.utils.nxm_handler_manager import NXMHandlerManager

            self.logger.info("Removing all NXM handlers...")
            nxm_manager = NXMHandlerManager()

            # Get all instances
            instances = nxm_manager.list_all_instances()
            removed_count = 0

            # Remove each instance
            for instance in instances:
                prefix_path = instance.get('prefix_path')
                if prefix_path:
                    try:
                        # Remove the instance's NXM script
                        script_path = instance.get('NXM_SCRIPT')
                        if script_path and os.path.exists(script_path):
                            os.remove(script_path)
                            self.logger.info(f"Removed NXM script: {script_path}")
                            removed_count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to remove NXM script for {instance.get('INSTANCE_NAME')}: {e}")

            # Remove the desktop file
            desktop_file = Path.home() / ".local/share/applications/nxm-handler.desktop"
            if desktop_file.exists():
                try:
                    desktop_file.unlink()
                    self.logger.info(f"Removed NXM handler desktop file: {desktop_file}")
                    removed_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to remove desktop file: {e}")

            return {
                "success": True,
                "removed_count": removed_count,
                "message": f"Removed {removed_count} NXM handler file(s)"
            }

        except Exception as e:
            self.logger.error(f"Failed to remove NXM handlers: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def configure_nxm_handler(self, app_id: str, nxm_handler_path: str) -> Dict[str, Any]:
        """Configure NXM handler for a specific instance (deprecated - use NXMHandlerManager directly)

        This method is kept for backward compatibility but delegates to NXMHandlerManager.
        """
        try:
            from src.utils.nxm_handler_manager import NXMHandlerManager

            self.logger.info(f"Configuring NXM handler for app_id {app_id}")
            nxm_manager = NXMHandlerManager()

            # Find the instance by searching all instances
            instances = nxm_manager.list_all_instances()

            for instance in instances:
                # Match by prefix name or instance name
                if instance.get('PREFIX_NAME') == app_id or instance.get('INSTANCE_NAME') == app_id:
                    # Set this instance as active
                    nxm_manager.set_active_handler(instance)
                    return {
                        "success": True,
                        "message": f"NXM handler configured for {instance.get('INSTANCE_NAME')}"
                    }

            return {
                "success": False,
                "error": f"No instance found matching '{app_id}'"
            }

        except Exception as e:
            self.logger.error(f"Failed to configure NXM handler: {e}")
            return {
                "success": False,
                "error": str(e)
            }
