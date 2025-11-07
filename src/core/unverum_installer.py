"""
Unverum Installer module for downloading and installing Unverum Mod Manager
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import requests

from src.core.installers.base.base_installer import BaseInstaller, GitHubRelease


class UnverumInstaller(BaseInstaller):
    """Handles downloading and installing Unverum Mod Manager"""

    def __init__(self, core=None):
        """Initialize Unverum installer"""
        super().__init__(core=core, installer_name="UnverumInstaller")

        # Initialize GitHub downloader for Unverum
        from src.core.installers.utils.github_downloader import GitHubDownloader
        self.github_downloader = GitHubDownloader(
            repo_owner="TekkaGB",
            repo_name="Unverum",
            cache_prefix="unverum"
        )

        # Initialize dependency installer for managing dependencies
        from src.core.dependency_installer import DependencyInstaller
        self.dependency_installer = DependencyInstaller()

    def _cleanup_old_cache(self, current_filename: str):
        """
        Clean up old cached Unverum files

        Wrapper for base class method with Unverum-specific prefix and .7z extension
        """
        super()._cleanup_old_cache(current_filename, prefix="Unverum", extension=".7z")

    def _get_latest_release(self) -> Optional[GitHubRelease]:
        """
        Get the latest Unverum release from GitHub

        Delegates to GitHubDownloader for consistent GitHub API access.
        """
        return self.github_downloader.get_latest_release()

    def _find_unverum_asset(self, release: GitHubRelease) -> Tuple[Optional[str], Optional[str]]:
        """
        Find the Unverum .7z asset

        Delegates to GitHubDownloader with pattern for Unverum .7z files.
        """
        # Look for .7z file with "Unverum" in name
        return self.github_downloader.find_asset(release, r"(?i)Unverum.*\.7z$")

    def download(self, selected_game_name: str = None) -> Dict[str, Any]:
        """Download the latest Unverum release"""
        try:
            self._log_progress("Fetching latest Unverum release...")
            self._send_progress_update(5)

            # Get latest release
            release = self._get_latest_release()
            if not release:
                return {"success": False, "error": "Failed to fetch latest release"}

            # Find 7z asset
            download_url, filename = self._find_unverum_asset(release)
            if not download_url or not filename:
                return {"success": False, "error": "No Unverum .7z file found in release"}

            # Setup cache directory
            cache_dir = Path.home() / "NaK" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / filename

            # Check if already cached
            if cache_file.exists():
                self._log_progress(f"Using cached Unverum: {filename}")
                self._send_progress_update(100)
                return {
                    "success": True,
                    "file_path": str(cache_file),
                    "version": release.tag_name
                }

            # Download file
            self._log_progress(f"Downloading {filename}...")
            self._send_progress_update(10)

            response = requests.get(download_url, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(cache_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = 10 + int((downloaded_size / total_size) * 80)
                            self._send_progress_update(progress)

            self._log_progress(f"Downloaded Unverum {release.tag_name}")
            self._send_progress_update(100)

            # Cleanup old cached versions
            self._cleanup_old_cache(filename)

            return {
                "success": True,
                "file_path": str(cache_file),
                "version": release.tag_name
            }

        except Exception as e:
            self.logger.error(f"Failed to download Unverum: {e}")
            return {"success": False, "error": str(e)}

    def install(self, install_path: str, game_name: str = None) -> Dict[str, Any]:
        """Install Unverum from the downloaded archive"""
        try:
            self._log_progress("Starting Unverum installation...")
            self._send_progress_update(5)

            # Download if needed
            download_result = self.download(game_name)
            if not download_result.get("success"):
                return download_result

            archive_path = download_result["file_path"]
            version = download_result["version"]

            # Extract archive using base class method
            self._log_progress(f"Extracting Unverum {version}...")
            self._send_progress_update(20)

            install_dir = Path(install_path)
            install_dir.mkdir(parents=True, exist_ok=True)

            # Use base class extraction (handles AppImage environment properly)
            extracted_path = self._extract_archive(archive_path, install_path)

            if not extracted_path:
                return {"success": False, "error": "Failed to extract Unverum archive"}

            self._send_progress_update(50)

            # Find the executable
            unverum_exe = None
            for root, dirs, files in os.walk(install_path):
                for file in files:
                    if file.lower() == "unverum.exe":
                        unverum_exe = os.path.join(root, file)
                        break
                if unverum_exe:
                    break

            if not unverum_exe:
                return {"success": False, "error": "Unverum.exe not found after extraction"}

            self._log_progress(f"Unverum installed successfully")
            self._send_progress_update(100)

            return {
                "success": True,
                "version": version,
                "exe_path": unverum_exe,
                "install_path": install_path
            }

        except Exception as e:
            self.logger.error(f"Failed to install Unverum: {e}")
            return {"success": False, "error": str(e)}


    def download_unverum(self, install_dir: Optional[str] = None, custom_name: Optional[str] = None) -> Dict[str, Any]:
        """Download and install Unverum using standalone Proton-GE"""
        try:
            from pathlib import Path
            from src.utils.proton_ge_manager import ProtonGEManager
            from src.utils.launch_script_generator import LaunchScriptGenerator
            import subprocess
            import re

            self.logger.info("Starting Unverum download and installation with Proton-GE")

            # Generate prefix name from instance name
            unverum_name = custom_name if custom_name else "Unverum"
            safe_instance_name = re.sub(r'[^a-zA-Z0-9\s]', '', unverum_name)
            safe_instance_name = safe_instance_name.replace(' ', '_').lower()
            prefix_name = f"unverum_{safe_instance_name}"

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

            # Download Unverum
            download_result = self.download()
            if not download_result.get("success"):
                return download_result

            archive_path = download_result["file_path"]
            version = download_result["version"]

            # Get installation directory
            if not install_dir:
                install_dir = str(Path.home() / "Games" / "Unverum")

            os.makedirs(install_dir, exist_ok=True)
            actual_install_dir = Path(install_dir)
            self.logger.info(f"Installation directory: {actual_install_dir}")

            # Create prefix directory structure
            prefix_path = Path.home() / "NaK" / "Prefixes" / prefix_name / "pfx"
            prefix_path.parent.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Prefix path: {prefix_path}")

            # Extract Unverum using base class method
            self._log_progress(f"Extracting Unverum {version}...")
            extracted_path = self._extract_archive(archive_path, install_dir)

            if not extracted_path:
                return {"success": False, "error": "Failed to extract Unverum archive"}

            # Find Unverum.exe
            unverum_exe = None
            for root, dirs, files in os.walk(install_dir):
                for file in files:
                    if file.lower() == "unverum.exe":
                        unverum_exe = os.path.join(root, file)
                        break
                if unverum_exe:
                    break

            if not unverum_exe:
                return {"success": False, "error": "Unverum.exe not found after extraction"}

            # Install dependencies
            self._log_progress("Installing Windows dependencies...")
            self.logger.info(f"Installing dependencies for prefix: {prefix_path}")

            dependency_result = self._install_dependencies_proton_ge(prefix_path, proton_ge_path)

            if not dependency_result["success"]:
                return {
                    "success": False,
                    "error": f"Dependency installation failed: {dependency_result.get('error', 'Unknown error')}"
                }

            self._log_progress("Dependencies installed successfully!")

            # Convert exe path to Wine format
            unverum_exe_path = Path(unverum_exe)
            unverum_exe_wine_path = str(unverum_exe_path).replace('/', '\\')
            if not unverum_exe_wine_path.startswith("Z:"):
                unverum_exe_wine_path = f"Z:{unverum_exe_wine_path}"

            self.logger.info(f"Unverum exe: {unverum_exe}")
            self.logger.info(f"Wine path: {unverum_exe_wine_path}")

            # Generate launch script
            self._log_progress("Generating launch script...")
            launch_script_path = script_gen.generate_unverum_launch_script(
                prefix_path=prefix_path,
                unverum_exe_wine_path=unverum_exe_wine_path,
                instance_name=unverum_name,
                proton_ge_path=proton_ge_path
            )

            # Generate game registry fix script
            self._log_progress("Generating game registry fixer script...")
            registry_script_path = script_gen.generate_fix_game_registry_script(
                prefix_path=prefix_path,
                instance_name=unverum_name,
                proton_ge_path=proton_ge_path
            )

            # Create symlink in Unverum installation directory
            self._log_progress("Creating launch symlink...")
            symlink_path = script_gen.create_symlink(
                script_path=launch_script_path,
                target_dir=actual_install_dir,
                link_name="Launch Unverum"
            )

            # Create registry fix symlink
            registry_symlink_path = script_gen.create_symlink(
                script_path=registry_script_path,
                target_dir=actual_install_dir,
                link_name="Fix Game Registry"
            )

            self._log_progress("Unverum installation completed successfully!")

            return {
                "success": True,
                "install_dir": str(actual_install_dir),
                "unverum_exe": unverum_exe,
                "version": version,
                "unverum_name": unverum_name,
                "prefix_path": str(prefix_path),
                "launch_script": str(launch_script_path),
                "launch_symlink": str(symlink_path),
                "proton_ge_version": active_version,
                "message": f"Unverum {version} installed successfully with Proton-GE!",
                "dependency_installation": dependency_result
            }

        except Exception as e:
            self.logger.error(f"Unverum installation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def setup_existing(self, unverum_dir: str, custom_name: str = "Unverum") -> Dict[str, Any]:
        """Setup existing Unverum installation from directory"""
        try:
            from pathlib import Path
            from src.utils.proton_ge_manager import ProtonGEManager
            from src.utils.launch_script_generator import LaunchScriptGenerator
            import subprocess
            import re

            self._log_progress(f"Setting up existing Unverum installation from: {unverum_dir}")
            self._send_progress_update(5)

            # Verify the directory exists
            self._log_progress("Verifying Unverum directory...")
            if not os.path.exists(unverum_dir):
                return {"success": False, "error": f"Directory does not exist: {unverum_dir}"}
            self._send_progress_update(10)

            # Find Unverum.exe in the directory
            self._log_progress("Finding Unverum.exe...")
            unverum_exe = None
            for root, dirs, files in os.walk(unverum_dir):
                for file in files:
                    if file.lower() == "unverum.exe":
                        unverum_exe = os.path.join(root, file)
                        break
                if unverum_exe:
                    break

            if not unverum_exe:
                return {"success": False, "error": f"Could not find Unverum.exe in: {unverum_dir}"}

            self._log_progress(f"Found Unverum.exe at: {unverum_exe}")
            self._send_progress_update(20)

            # Generate prefix name from instance name
            safe_instance_name = re.sub(r'[^a-zA-Z0-9\s]', '', custom_name)
            safe_instance_name = safe_instance_name.replace(' ', '_').lower()
            prefix_name = f"unverum_{safe_instance_name}"

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

            dependency_result = self._install_dependencies_proton_ge(prefix_path, proton_ge_path)

            if not dependency_result["success"]:
                return {
                    "success": False,
                    "error": f"Dependency installation failed: {dependency_result.get('error', 'Unknown error')}"
                }

            self._log_progress("Dependencies installed successfully!")
            self._send_progress_update(75)

            # Convert exe path to Wine format
            unverum_exe_path = Path(unverum_exe)
            unverum_exe_wine_path = str(unverum_exe_path).replace('/', '\\')
            if not unverum_exe_wine_path.startswith("Z:"):
                unverum_exe_wine_path = f"Z:{unverum_exe_wine_path}"

            self.logger.info(f"Unverum exe: {unverum_exe}")
            self.logger.info(f"Wine path: {unverum_exe_wine_path}")

            # Generate launch script
            self._log_progress("Generating launch script...")
            launch_script_path = script_gen.generate_unverum_launch_script(
                prefix_path=prefix_path,
                unverum_exe_wine_path=unverum_exe_wine_path,
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

            # Create symlink in Unverum installation directory
            self._log_progress("Creating launch symlink...")
            unverum_install_dir = Path(unverum_dir)
            symlink_path = script_gen.create_symlink(
                script_path=launch_script_path,
                target_dir=unverum_install_dir,
                link_name="Launch Unverum"
            )

            # Create registry fix symlink
            registry_symlink_path = script_gen.create_symlink(
                script_path=registry_script_path,
                target_dir=unverum_install_dir,
                link_name="Fix Game Registry"
            )
            self._send_progress_update(95)

            self._log_progress("Unverum setup completed successfully!")
            self._send_progress_update(100)

            return {
                "success": True,
                "install_dir": unverum_dir,
                "unverum_exe": unverum_exe,
                "unverum_name": custom_name,
                "prefix_path": str(prefix_path),
                "launch_script": str(launch_script_path),
                "launch_symlink": str(symlink_path),
                "proton_ge_version": active_version,
                "message": f"Existing Unverum installation configured successfully with Proton-GE!",
                "dependency_installation": dependency_result
            }

        except Exception as e:
            self.logger.error(f"Unverum setup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

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

    def _install_dependencies_proton_ge(self, prefix_path: Path, proton_ge_path: Path) -> Dict[str, Any]:
        """
        Install Unverum dependencies using Proton-GE (no Steam required)

        Args:
            prefix_path: Path to the Wine prefix (e.g., ~/NaK/Prefixes/unverum_unverum/pfx)
            proton_ge_path: Path to Proton-GE (should be the /active symlink)

        Returns:
            Dictionary with success status
        """
        try:
            import subprocess

            self.logger.info("===============================================================")
            self.logger.info("INSTALLING DEPENDENCIES WITH PROTON-GE")
            self.logger.info("===============================================================")
            self.logger.info(f"Prefix: {prefix_path}")
            self.logger.info(f"Proton-GE: {proton_ge_path}")

            # Determine wine and wineserver paths from Proton-GE
            wine_path = proton_ge_path / "files" / "bin" / "wine64"
            wineserver_path = proton_ge_path / "files" / "bin" / "wineserver"

            if not wine_path.exists():
                return {"success": False, "error": f"Wine not found at {wine_path}"}

            # IMPORTANT: Don't manually run wineboot! Proton-GE handles prefix initialization
            # automatically when running winetricks or any wine command. Manual wineboot can cause hangs.

            # Install dependencies with winetricks using DependencyInstaller (Proton will auto-init prefix on first run)
            self._log_progress("Installing Windows dependencies...")

            dependencies = [
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

            # Set callbacks for DependencyInstaller
            if self.log_callback:
                self.dependency_installer.set_log_callback(self.log_callback)
            if self.progress_callback:
                self.dependency_installer.set_progress_callback(self.progress_callback)

            # Delegate to DependencyInstaller for unified dependency installation
            game_dict = {"Name": "Unverum", "AppID": "unverum"}
            result = self.dependency_installer._install_dependencies_unified(
                game=game_dict,
                dependencies=dependencies,
                wine_binary=str(wine_path),
                wineserver_binary=str(wineserver_path),
                wine_prefix=str(prefix_path),
                method_name="Proton-GE"
            )

            if not result.get("success"):
                return result

            # Apply registry settings
            self._log_progress("Applying Wine registry settings...")
            self.logger.info("Applying Wine registry settings...")

            # Find wine_settings.reg file
            wine_settings_path = Path(__file__).parent.parent / "utils" / "wine_settings.reg"
            if wine_settings_path.exists():
                import tempfile

                # Create temporary copy
                with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False) as temp_file:
                    with open(wine_settings_path, 'r') as f:
                        temp_file.write(f.read())
                    temp_reg_path = temp_file.name

                try:
                    # Run wine regedit with the reg file
                    result = subprocess.run(
                        [str(wine_path), "regedit", temp_reg_path],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )

                    if result.returncode == 0:
                        self.logger.info("[OK] Registry settings applied successfully")
                        self._log_progress("[OK] Registry settings applied")
                    else:
                        self.logger.warning(f"Registry application failed: {result.stderr}")

                finally:
                    # Cleanup temp file
                    Path(temp_reg_path).unlink(missing_ok=True)
            else:
                self.logger.warning(f"wine_settings.reg not found at {wine_settings_path}")

            # Set Windows version to Windows 11
            self._log_progress("Setting Windows version to Windows 11...")
            self.logger.info("Setting Windows version to Windows 11...")

            try:
                result = subprocess.run(
                    [str(winetricks_path), "win11"],
                    env=env,
                    capture_output=True,
                    timeout=120
                )
                if result.returncode == 0:
                    self.logger.info("[OK] Windows version set to Windows 11")
                    self._log_progress("[OK] Windows version set to Windows 11")
                else:
                    self.logger.warning(f"Failed to set Windows 11: {result.stderr.decode() if result.stderr else 'N/A'}")
            except Exception as e:
                self.logger.warning(f"Failed to set Windows version: {e}")

            return {
                "success": True,
                "message": "Dependencies installed with Proton-GE"
            }

        except subprocess.TimeoutExpired:
            self.logger.error("Dependency installation timed out")
            return {"success": False, "error": "Installation timed out"}
        except Exception as e:
            self.logger.error(f"Failed to install dependencies: {e}")
            return {"success": False, "error": str(e)}


def createPlugin():
    """Plugin entry point for compatibility"""
    return UnverumInstaller()
