"""
Shared Proton-GE Dependency Installation Mixin

Provides dependency installation functionality using standalone Proton-GE.
Can be used by both MO2 and Vortex installers.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List


class ProtonGEDependencyMixin:
    """Mixin providing Proton-GE dependency installation for mod managers"""

    def _install_dependencies_proton_ge(
        self,
        prefix_path: Path,
        proton_ge_path: Path,
        dependencies: List[str],
        app_name: str = "ModManager"
    ) -> Dict[str, Any]:
        """
        Install dependencies using Proton-GE (no Steam required)

        Args:
            prefix_path: Path to the Wine prefix (e.g., ~/NaK/Prefixes/mo2_default_main/pfx)
            proton_ge_path: Path to Proton-GE (should be the /active symlink)
            dependencies: List of winetricks dependencies to install
            app_name: Name of the app for logging (e.g., "MO2", "Vortex")

        Returns:
            Dictionary with success status
        """
        try:
            self.logger.info("===============================================================")
            self.logger.info(f"INSTALLING {app_name.upper()} DEPENDENCIES WITH PROTON-GE")
            self.logger.info("===============================================================")
            self.logger.info(f"Prefix: {prefix_path}")
            self.logger.info(f"Proton-GE: {proton_ge_path}")

            # Determine wine and wineserver paths from Proton-GE
            wine_path = proton_ge_path / "files" / "bin" / "wine64"
            wineserver_path = proton_ge_path / "files" / "bin" / "wineserver"

            if not wine_path.exists():
                return {"success": False, "error": f"Wine not found at {wine_path}"}

            # Check Proton-GE version for dotnet48 support
            from src.utils.proton_ge_manager import ProtonGEManager
            ge_manager = ProtonGEManager()
            active_version = ge_manager.get_active_version()

            if not active_version:
                return {
                    "success": False,
                    "error": "No Proton-GE version is currently active. Please select a Proton-GE version first."
                }

            supports_dotnet = ge_manager.supports_dotnet48(active_version)

            # Remove dotnet48/dotnet40 if Proton-GE version doesn't support it
            if not supports_dotnet:
                self.logger.warning(f"Proton-GE {active_version} doesn't support .NET Framework 4.8 (requires GE-Proton 10-18+)")
                self._log_progress(f"[WARNING] {active_version} doesn't support .NET Framework 4.8 - skipping dotnet48/dotnet40")

                # Filter out dotnet48 and dotnet40 from dependencies
                original_count = len(dependencies)
                dependencies = [dep for dep in dependencies if dep not in ["dotnet48", "dotnet40"]]

                if len(dependencies) < original_count:
                    self.logger.info(f"Removed dotnet48/dotnet40 from dependencies (not supported by {active_version})")
            else:
                self.logger.info(f"Proton-GE {active_version} supports .NET Framework 4.8")

            # IMPORTANT: Don't manually run wineboot! Let winetricks create the prefix.
            # Wineboot installs Mono which interferes with .NET Framework installation.
            # Winetricks will create the prefix correctly without Mono when installing dotnet48.

            # Install dependencies with winetricks using DependencyInstaller
            self._log_progress("Installing Windows dependencies...")

            # Set callbacks for DependencyInstaller
            if self.log_callback:
                self.dependency_installer.set_log_callback(self.log_callback)
            if self.progress_callback:
                self.dependency_installer.set_progress_callback(self.progress_callback)

            # Delegate to DependencyInstaller for unified dependency installation
            game_dict = {"Name": app_name, "AppID": app_name.lower()}
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

            self._send_progress_update(60)

            # Apply registry settings
            self._log_progress("Applying Wine registry settings...")
            self.logger.info("Applying Wine registry settings...")

            # Find wine_settings.reg file
            wine_settings_path = Path(__file__).parent.parent.parent / "utils" / "wine_settings.reg"
            if wine_settings_path.exists():
                # Create temporary copy
                with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False) as temp_file:
                    with open(wine_settings_path, 'r') as f:
                        temp_file.write(f.read())
                    temp_reg_path = temp_file.name

                try:
                    # Set up environment for wine command
                    env = os.environ.copy()
                    env["WINEPREFIX"] = str(prefix_path)

                    # CRITICAL: Reset LD_LIBRARY_PATH to system-only paths
                    # This prevents AppImage libraries from breaking system binaries
                    env["LD_LIBRARY_PATH"] = "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu"

                    # Run wine regedit with the reg file
                    result_cmd = subprocess.run(
                        [str(wine_path), "regedit", temp_reg_path],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )

                    if result_cmd.returncode == 0:
                        self.logger.info("[OK] Registry settings applied successfully")
                        self._log_progress("[OK] Registry settings applied")
                    else:
                        self.logger.warning(f"Registry application failed: {result_cmd.stderr}")

                finally:
                    # Cleanup temp file
                    Path(temp_reg_path).unlink(missing_ok=True)
            else:
                self.logger.warning(f"wine_settings.reg not found at {wine_settings_path}")

            # Set Windows version to Windows 11
            self._log_progress("Setting Windows version to Windows 11...")
            self.logger.info("Setting Windows version to Windows 11...")

            try:
                # Get winetricks path
                winetricks_path = self._get_winetricks_command()
                if winetricks_path:
                    # Set up environment
                    env = os.environ.copy()
                    env["WINEPREFIX"] = str(prefix_path)
                    env["WINE"] = str(wine_path)
                    env["WINESERVER"] = str(wineserver_path)

                    # CRITICAL: Reset LD_LIBRARY_PATH to system-only paths
                    # This prevents AppImage libraries from breaking system binaries like /bin/sh
                    env["LD_LIBRARY_PATH"] = "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu"

                    result_cmd = subprocess.run(
                        [winetricks_path, "win11"],
                        env=env,
                        capture_output=True,
                        timeout=120
                    )
                    if result_cmd.returncode == 0:
                        self.logger.info("[OK] Windows version set to Windows 11")
                        self._log_progress("[OK] Windows version set to Windows 11")
                    else:
                        self.logger.warning(f"Failed to set Windows 11: {result_cmd.stderr.decode() if result_cmd.stderr else 'N/A'}")
                else:
                    self.logger.warning("Winetricks not found, skipping Windows version setting")
            except Exception as e:
                self.logger.warning(f"Failed to set Windows version: {e}")

            self._send_progress_update(70)

            # Install .NET 9 SDK (for Synthesis patcher support)
            self._log_progress("Installing .NET 9 SDK for Synthesis patcher...")
            self.logger.info("Installing .NET 9 SDK for Synthesis patcher...")

            try:
                from src.core.dotnet9sdk_installer import DotNet9SDKInstaller

                dotnet_installer = DotNet9SDKInstaller()

                # Check if already installed
                if dotnet_installer.is_dotnet9_installed(prefix_path):
                    self.logger.info(".NET 9 SDK already installed, skipping")
                    self._log_progress("[OK] .NET 9 SDK already installed")
                else:
                    # Install .NET 9 SDK
                    if dotnet_installer.install_dotnet9_sdk(prefix_path, wine_path):
                        self.logger.info("[OK] .NET 9 SDK installed successfully")
                        self._log_progress("[OK] .NET 9 SDK installed")
                    else:
                        self.logger.warning("Failed to install .NET 9 SDK (non-critical)")
                        self._log_progress("[WARNING] .NET 9 SDK installation failed")

            except Exception as e:
                self.logger.warning(f"Failed to install .NET 9 SDK: {e}")
                self._log_progress("[WARNING] .NET 9 SDK installation failed")

            self._send_progress_update(80)

            return {
                "success": True,
                "message": f"Dependencies installed with Proton-GE for {app_name}"
            }

        except subprocess.TimeoutExpired:
            self.logger.error("Dependency installation timed out")
            return {"success": False, "error": "Installation timed out"}
        except Exception as e:
            self.logger.error(f"Failed to install dependencies: {e}")
            return {"success": False, "error": str(e)}
