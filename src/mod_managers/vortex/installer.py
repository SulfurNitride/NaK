"""
Vortex Installer (Proton-GE Standalone Only)

Main orchestration class for Vortex installation with standalone Proton-GE.
NO Steam integration - uses ~/NaK/Prefixes for Wine prefixes.

Inherits functionality from focused mixin classes for better maintainability.
"""
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

from src.core.installers.base.base_installer import BaseInstaller
from src.mod_managers.shared import ProtonGEDependencyMixin
from .download import VortexDownloadMixin


class VortexInstaller(BaseInstaller, VortexDownloadMixin, ProtonGEDependencyMixin):
    """Handles downloading and installing Vortex with standalone Proton-GE

    NO Steam integration - uses ~/NaK/Prefixes for Wine prefixes.
    """

    def __init__(self, core=None):
        """Initialize Vortex installer"""
        super().__init__(core=core, installer_name="VortexInstaller")

        # Initialize GitHub downloader for Vortex
        from src.core.installers.utils.github_downloader import GitHubDownloader
        self.github_downloader = GitHubDownloader(
            repo_owner="Nexus-Mods",
            repo_name="Vortex",
            cache_prefix="vortex"
        )

        # Initialize dependency installer for managing dependencies
        from src.core.dependency_installer import DependencyInstaller
        self.dependency_installer = DependencyInstaller()

    def _cleanup_old_cache(self, current_filename: str):
        """
        Clean up old cached Vortex files

        Wrapper for base class method with Vortex-specific prefix
        """
        super()._cleanup_old_cache(current_filename, prefix="Vortex")

    def _find_vortex_executable(self, install_dir: str) -> Optional[str]:
        """Find Vortex.exe in the installation directory"""
        try:
            self.logger.info(f"Searching for Vortex.exe in {install_dir}")

            # Look for Vortex.exe
            for root, dirs, files in os.walk(install_dir):
                for file in files:
                    if file.lower() == "vortex.exe":
                        exe_path = os.path.join(root, file)
                        self.logger.info(f"Found Vortex.exe: {exe_path}")
                        return exe_path

            self.logger.error("Vortex.exe not found")
            return None

        except Exception as e:
            self.logger.error(f"Failed to find Vortex executable: {e}")
            return None

    def _run_vortex_installer_proton_ge(self, installer_path: str, install_dir: str, prefix_path: str, proton_ge_path: str) -> Dict[str, Any]:
        """Run Vortex installer using Proton-GE"""
        try:
            self.logger.info("Running Vortex installer with Proton-GE...")

            proton_binary = Path(proton_ge_path) / "proton"
            if not proton_binary.exists():
                return {
                    "success": False,
                    "error": f"Proton binary not found at {proton_binary}"
                }

            # Create the install directory if it doesn't exist
            os.makedirs(install_dir, exist_ok=True)

            # Convert Linux path to Windows Z: drive path
            windows_install_path = install_dir.replace("/", "\\")
            if not windows_install_path.startswith("Z:"):
                windows_install_path = f"Z:{windows_install_path}"

            self.logger.info(f"Installing Vortex to: {windows_install_path}")

            # Set up environment for Proton
            env = os.environ.copy()
            env["WINEPREFIX"] = prefix_path
            env["STEAM_COMPAT_DATA_PATH"] = str(Path(prefix_path).parent)

            # CRITICAL: Reset LD_LIBRARY_PATH to system-only paths
            # This prevents AppImage libraries from breaking system binaries
            env["LD_LIBRARY_PATH"] = "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu"

            # Auto-detect Steam path for proper DRM support
            try:
                steam_path = self.steam_utils.get_steam_root()
                env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam_path
                self.logger.info(f"Using Steam path: {steam_path}")
            except Exception as e:
                self.logger.warning(f"Failed to detect Steam path, using /tmp: {e}")
                env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = "/tmp"

            self.logger.info(f"Running: {proton_binary} run {installer_path} /S /D={windows_install_path}")

            # Run the installer - pass args as list to preserve spaces in path
            process = subprocess.run(
                [str(proton_binary), "run", installer_path, "/S", f"/D={windows_install_path}"],
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if process.returncode != 0:
                self.logger.warning(f"Installer return code: {process.returncode}")
                self.logger.warning(f"Installer stderr: {process.stderr}")

            # Wait for files to settle
            time.sleep(2)

            # Verify installation
            if os.path.exists(os.path.join(install_dir, "Vortex.exe")):
                self.logger.info("Vortex installed successfully")
                return {"success": True}
            else:
                self.logger.error(f"Vortex.exe not found in {install_dir} after installation")
                return {
                    "success": False,
                    "error": "Vortex installation not found after running installer"
                }

        except subprocess.TimeoutExpired:
            self.logger.error("Vortex installer timed out")
            return {
                "success": False,
                "error": "Vortex installer timed out after 5 minutes"
            }
        except Exception as e:
            self.logger.error(f"Failed to run Vortex installer: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def download_vortex(self, install_dir: Optional[str] = None, custom_name: Optional[str] = None) -> Dict[str, Any]:
        """Download and install Vortex using standalone Proton-GE (no Steam integration)"""
        try:
            from src.utils.proton_ge_manager import ProtonGEManager
            from src.utils.launch_script_generator import LaunchScriptGenerator

            self.logger.info("Starting Vortex download and installation with Proton-GE")

            # Generate prefix name from instance name
            vortex_name = custom_name if custom_name else "Vortex"
            safe_instance_name = re.sub(r'[^a-zA-Z0-9\s]', '', vortex_name)
            safe_instance_name = safe_instance_name.replace(' ', '_').lower()
            prefix_name = f"vortex_{safe_instance_name}"

            # Check for name collision
            script_gen = LaunchScriptGenerator()
            prefix_name = script_gen.check_prefix_name_collision(prefix_name)

            self.logger.info(f"Using prefix name: {prefix_name}")
            self._log_progress(f"Using prefix: {prefix_name}")

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

            # Get latest release info
            self._log_progress("Fetching latest Vortex release information...")
            release = self._get_latest_release()
            if not release:
                return {
                    "success": False,
                    "error": "Failed to get latest release information"
                }

            self._log_progress(f"Found latest version: {release.tag_name}")

            # Find the correct asset
            self._log_progress("Finding download asset...")
            download_url, filename = self._find_vortex_asset(release)
            if not download_url or not filename:
                return {
                    "success": False,
                    "error": "Could not find appropriate Vortex installer"
                }

            # Clean up old cached files
            self._cleanup_old_cache(filename)
            self._log_progress(f"Found asset: {filename}")

            # Get installation directory
            if not install_dir:
                install_dir = os.path.join(os.path.expanduser("~"), "Games", "Vortex")

            actual_install_dir = Path(install_dir)
            actual_install_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Installation directory: {actual_install_dir}")

            # Download the installer
            self._log_progress("Downloading Vortex installer...")
            installer_path = self._download_file(download_url, filename, progress_callback=getattr(self, 'progress_callback', None))
            if not installer_path:
                return {
                    "success": False,
                    "error": "Failed to download Vortex installer"
                }

            # Setup prefix structure
            nak_prefixes_dir = Path.home() / "NaK" / "Prefixes"
            prefix_base_dir = nak_prefixes_dir / prefix_name
            prefix_path = prefix_base_dir / "pfx"

            # Create prefix directory
            self.logger.info(f"Creating prefix at: {prefix_path}")
            prefix_path.mkdir(parents=True, exist_ok=True)

            # Run Vortex installer
            self._log_progress("Running Vortex installer...")
            install_result = self._run_vortex_installer_proton_ge(
                installer_path,
                str(actual_install_dir),
                str(prefix_path),
                str(proton_ge_path)
            )

            if not install_result["success"]:
                return install_result

            # Install Windows dependencies using shared mixin
            self._log_progress("Installing Windows dependencies...")
            self.logger.info(f"Installing dependencies for prefix: {prefix_path}")

            # Vortex dependencies list (same as MO2)
            vortex_dependencies = [
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
                dependencies=vortex_dependencies,
                app_name="Vortex"
            )

            if not dependency_result["success"]:
                return {
                    "success": False,
                    "error": f"Dependency installation failed: {dependency_result.get('error', 'Unknown error')}"
                }

            self._log_progress("Dependencies installed successfully!")

            # Find the actual Vortex executable
            self._log_progress("Locating Vortex executable...")
            vortex_exe = self._find_vortex_executable(str(actual_install_dir))
            if not vortex_exe:
                return {
                    "success": False,
                    "error": "Could not find Vortex.exe after installation"
                }

            # Convert Vortex exe path to Wine format
            vortex_exe_path = Path(vortex_exe)
            vortex_exe_wine_path = str(vortex_exe_path).replace('/', '\\')
            if not vortex_exe_wine_path.startswith("Z:"):
                vortex_exe_wine_path = f"Z:{vortex_exe_wine_path}"

            self.logger.info(f"Vortex exe: {vortex_exe}")
            self.logger.info(f"Wine path: {vortex_exe_wine_path}")

            # Generate launch script
            self._log_progress("Generating launch script...")
            launch_script_path = script_gen.generate_vortex_launch_script(
                prefix_path=prefix_path,
                vortex_exe_wine_path=vortex_exe_wine_path,
                instance_name=vortex_name,
                proton_ge_path=proton_ge_path
            )

            # Generate kill prefix script
            self._log_progress("Generating kill prefix script...")
            kill_script_path = script_gen.generate_kill_prefix_script(
                prefix_path=prefix_path,
                instance_name=vortex_name,
                proton_ge_path=proton_ge_path
            )

            # Generate fix game registry script
            self._log_progress("Generating game registry fixer script...")
            registry_script_path = script_gen.generate_fix_game_registry_script(
                prefix_path=prefix_path,
                instance_name=vortex_name,
                proton_ge_path=proton_ge_path
            )

            # Create symlink in Vortex installation directory
            self._log_progress("Creating launch symlink...")
            symlink_path = script_gen.create_symlink(
                script_path=launch_script_path,
                target_dir=actual_install_dir,
                link_name="Launch Vortex"
            )

            # Create kill symlink
            kill_symlink_path = script_gen.create_symlink(
                script_path=kill_script_path,
                target_dir=actual_install_dir,
                link_name="Kill Vortex Prefix"
            )

            # Create registry fix symlink
            registry_symlink_path = script_gen.create_symlink(
                script_path=registry_script_path,
                target_dir=actual_install_dir,
                link_name="Fix Game Registry"
            )

            # Setup NXM handler
            self._log_progress("Setting up NXM link handler...")
            from src.utils.nxm_handler_manager import NXMHandlerManager
            nxm_manager = NXMHandlerManager()
            nxm_setup_success = nxm_manager.setup_instance(
                prefix_path=str(prefix_path),
                instance_name=vortex_name,
                instance_type="Vortex",
                exe_path=vortex_exe_wine_path,
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

            self._log_progress("Vortex installation completed successfully!")

            return {
                "success": True,
                "install_dir": str(actual_install_dir),
                "vortex_exe": vortex_exe,
                "version": release.tag_name,
                "vortex_name": vortex_name,
                "prefix_path": str(prefix_path),
                "launch_script": str(launch_script_path),
                "launch_symlink": str(symlink_path),
                "proton_ge_version": active_version,
                "message": f"Vortex {release.tag_name} installed successfully with Proton-GE {active_version}!",
                "dependency_installation": dependency_result,
            }

        except Exception as e:
            self.logger.error(f"Vortex installation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def setup_existing(self, vortex_dir: str, custom_name: str = "Vortex") -> Dict[str, Any]:
        """Setup existing Vortex installation from directory with standalone Proton-GE"""
        try:
            from pathlib import Path
            from src.utils.proton_ge_manager import ProtonGEManager
            from src.utils.launch_script_generator import LaunchScriptGenerator
            import re

            self._log_progress(f"Setting up existing Vortex installation from: {vortex_dir}")
            self._send_progress_update(5)

            # Verify the directory exists
            self._log_progress("Verifying Vortex directory...")
            if not os.path.exists(vortex_dir):
                return {"success": False, "error": f"Directory does not exist: {vortex_dir}"}
            self._send_progress_update(10)

            # Find Vortex.exe in the directory
            self._log_progress("Finding Vortex.exe...")
            vortex_exe = self._find_vortex_executable(vortex_dir)
            if not vortex_exe:
                return {"success": False, "error": f"Could not find Vortex.exe in: {vortex_dir}"}

            self._log_progress(f"Found Vortex.exe at: {vortex_exe}")
            self._send_progress_update(20)

            # Generate prefix name from instance name
            safe_instance_name = re.sub(r'[^a-zA-Z0-9\s]', '', custom_name)
            safe_instance_name = safe_instance_name.replace(' ', '_').lower()
            prefix_name = f"vortex_{safe_instance_name}"

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

            # Vortex dependencies list (same as MO2)
            vortex_dependencies = [
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
                dependencies=vortex_dependencies,
                app_name="Vortex"
            )

            if not dependency_result["success"]:
                return {
                    "success": False,
                    "error": f"Dependency installation failed: {dependency_result.get('error', 'Unknown error')}"
                }

            self._log_progress("Dependencies installed successfully!")
            self._send_progress_update(75)

            # Convert exe path to Wine format
            vortex_exe_path = Path(vortex_exe)
            vortex_exe_wine_path = str(vortex_exe_path).replace('/', '\\')
            if not vortex_exe_wine_path.startswith("Z:"):
                vortex_exe_wine_path = f"Z:{vortex_exe_wine_path}"

            self.logger.info(f"Vortex exe: {vortex_exe}")
            self.logger.info(f"Wine path: {vortex_exe_wine_path}")

            # Generate launch script
            self._log_progress("Generating launch script...")
            launch_script_path = script_gen.generate_vortex_launch_script(
                prefix_path=prefix_path,
                vortex_exe_wine_path=vortex_exe_wine_path,
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

            # Create symlinks in Vortex installation directory
            self._log_progress("Creating launch symlink...")
            vortex_install_dir = Path(vortex_dir)
            symlink_path = script_gen.create_symlink(
                script_path=launch_script_path,
                target_dir=vortex_install_dir,
                link_name="Launch Vortex"
            )

            # Create kill symlink
            kill_symlink_path = script_gen.create_symlink(
                script_path=kill_script_path,
                target_dir=vortex_install_dir,
                link_name="Kill Vortex Prefix"
            )

            # Create registry fix symlink
            registry_symlink_path = script_gen.create_symlink(
                script_path=registry_script_path,
                target_dir=vortex_install_dir,
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
                instance_type="Vortex",
                exe_path=vortex_exe_wine_path,
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
                    manager_install_dir=vortex_dir
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

            self._log_progress("Vortex setup completed successfully!")
            self._send_progress_update(100)

            return {
                "success": True,
                "install_dir": vortex_dir,
                "vortex_exe": vortex_exe,
                "vortex_name": custom_name,
                "prefix_path": str(prefix_path),
                "launch_script": str(launch_script_path),
                "launch_symlink": str(symlink_path),
                "proton_ge_version": active_version,
                "message": f"Existing Vortex installation configured successfully with Proton-GE!",
                "dependency_installation": dependency_result
            }

        except Exception as e:
            self.logger.error(f"Vortex setup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
