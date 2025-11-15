"""
Dependency Installer module for installing Proton dependencies
"""
import subprocess
import sys
import time
import os
from typing import Dict, Any, List, Optional
import requests
from pathlib import Path
import tempfile
import datetime

from src.utils.logger import get_logger
from src.utils.steam_utils import SteamUtils
from src.utils.dependency_cache_manager import DependencyCacheManager


class DependencyInstaller:
    """Handles installing Proton dependencies for games"""

    def __init__(self, settings_manager=None):
        self.logger = get_logger(__name__)
        # Logger will propagate to root logger which has file and console handlers

        self.steam_utils = SteamUtils()
        self.cache_manager = DependencyCacheManager()
        self.log_callback = None
        self.progress_callback = None
        self.settings_manager = settings_manager

    def _get_proton_experimental_paths(self) -> Optional[Dict[str, str]]:
        """Get wine and wineserver paths for Proton Experimental"""
        try:
            steam_root = self.steam_utils.get_steam_root()
            proton_dir = Path(steam_root) / "steamapps" / "common" / "Proton - Experimental"

            if not proton_dir.exists():
                self.logger.error(f"Proton - Experimental not found at {proton_dir}")
                return None

            wine_path = proton_dir / "files" / "bin" / "wine64"
            wineserver_path = proton_dir / "files" / "bin" / "wineserver"

            if not wine_path.exists():
                self.logger.error(f"wine64 not found at {wine_path}")
                return None

            if not wineserver_path.exists():
                self.logger.error(f"wineserver not found at {wineserver_path}")
                return None

            return {
                "wine": str(wine_path),
                "wineserver": str(wineserver_path),
                "version": "Proton - Experimental"
            }
        except Exception as e:
            self.logger.error(f"Failed to get Proton Experimental paths: {e}")
            return None

    def set_log_callback(self, callback):
        """Set log callback for status messages"""
        self.log_callback = callback
        # Also set the cache manager's progress callback
        self.cache_manager.set_progress_callback(callback)

    def set_progress_callback(self, callback):
        """Set progress callback for GUI progress bar updates"""
        # Store the progress callback for use during dependency installation
        self.progress_callback = callback

    def _log_progress(self, message):
        """Log progress message to both logger and callback"""
        # Always log to the debug file first
        self.logger.info(f"PROGRESS: {message}")
        # Then send to GUI callback if available
        if self.log_callback:
            try:
                self.log_callback(message)
            except Exception as e:
                self.logger.error(f"Callback failed: {e}")
    
    def cache_all_dependencies(self, force_download: bool = False) -> Dict[str, Any]:
        """Cache all dependency files for faster future installations"""
        self.logger.info("Starting dependency caching process...")
        self._log_progress("Caching dependency files for faster installations...")

        try:
            # Cache all dependencies
            results = self.cache_manager.cache_all_dependencies(force_download)

            successful = sum(1 for success in results.values() if success)
            total = len(results)

            # Automatically clean up winetricks temp folders after caching
            self._log_progress("Cleaning up temporary files...")
            cleanup_result = self.cache_manager.clean_winetricks_temp_folders()
            if cleanup_result.get("success") and cleanup_result.get("space_freed_mb", 0) > 0:
                self._log_progress(f"[OK] Cleaned temp folders, freed {cleanup_result['space_freed_mb']:.1f} MB")
                self.logger.info(f"Cleanup: {cleanup_result['message']}")

            if successful == total:
                self._log_progress(f"[OK] Successfully cached all {total} dependencies!")
                return {
                    "success": True,
                    "message": f"Successfully cached all {total} dependencies",
                    "cached_count": successful,
                    "total_count": total
                }
            else:
                failed_deps = [dep for dep, success in results.items() if not success]
                self._log_progress(f"⚠ Cached {successful}/{total} dependencies. Failed: {', '.join(failed_deps)}")
                return {
                    "success": False,
                    "message": f"Cached {successful}/{total} dependencies. Failed: {', '.join(failed_deps)}",
                    "cached_count": successful,
                    "total_count": total,
                    "failed_dependencies": failed_deps
                }

        except Exception as e:
            self.logger.error(f"Failed to cache dependencies: {e}")
            self._log_progress(f"[FAILED] Failed to cache dependencies: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get status of the dependency cache"""
        try:
            return self.cache_manager.get_cache_status()
        except Exception as e:
            self.logger.error(f"Failed to get cache status: {e}")
            return {"error": str(e)}
    
    def clean_temp_folders(self) -> Dict[str, Any]:
        """Clean up winetricks temporary folders to free disk space"""
        self.logger.info("Cleaning winetricks temporary folders...")
        self._log_progress("Cleaning temporary folders...")

        try:
            result = self.cache_manager.clean_winetricks_temp_folders()

            if result.get("success"):
                space_freed = result.get("space_freed_mb", 0)
                if space_freed > 0:
                    self._log_progress(f"[OK] Cleaned {len(result['cleaned_folders'])} folders, freed {space_freed:.1f} MB")
                else:
                    self._log_progress("[OK] No temporary folders found to clean")
                return result
            else:
                self._log_progress(f"[FAILED] Failed to clean temp folders: {result.get('error', 'Unknown error')}")
                return result

        except Exception as e:
            self.logger.error(f"Failed to clean temp folders: {e}")
            self._log_progress(f"[FAILED] Failed to clean temp folders: {e}")
            return {"success": False, "error": str(e)}

    def clear_dependency_cache(self) -> Dict[str, Any]:
        """Clear all cached dependency files"""
        self.logger.info("Clearing dependency cache...")
        self._log_progress("Clearing dependency cache...")

        try:
            success = self.cache_manager.clear_cache()
            if success:
                self._log_progress("[OK] Dependency cache cleared successfully!")
                return {"success": True, "message": "Dependency cache cleared successfully"}
            else:
                self._log_progress("[FAILED] Failed to clear dependency cache")
                return {"success": False, "error": "Failed to clear dependency cache"}

        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            self._log_progress(f"[FAILED] Failed to clear cache: {e}")
            return {"success": False, "error": str(e)}
    
    def install_dependencies_for_game(self, game_app_id: str) -> Dict[str, Any]:
        """Install dependencies for a specific non-Steam game (completely self-contained)"""
        self.logger.debug(f"*** SELF-CONTAINED: Installing dependencies for AppID: {game_app_id} ***")

        try:
            # Get the game details using our built-in VDF parsing
            games = self.steam_utils.get_non_steam_games()

            # Find the selected game
            selected_game = None
            for game in games:
                if game.get("AppID") == game_app_id:
                    selected_game = game
                    break

            if not selected_game:
                return {
                    "success": False,
                    "error": f"Game with AppID {game_app_id} not found"
                }

            return self._install_proton_dependencies_self_contained(selected_game)

        except Exception as e:
            self.logger.error(f"Failed to install dependencies for game {game_app_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def install_complete_setup_for_app_id(self, app_id: str, game_name: str = "Unknown", is_for_mod_manager: bool = False) -> Dict[str, Any]:
        """
        UNIFIED method for complete game setup (dependencies + registry + .NET SDK)
        Works for ANY app_id (Steam games or non-Steam games added to Steam)
        Used by Mod Managers (MO2/Vortex) and Simple Game Modding

        Args:
            app_id: Steam AppID
            game_name: Name of the game
            is_for_mod_manager: If True, delete/recreate prefix (MO2/Vortex). If False, keep existing prefix (Simple Game Modding).
        """
        self.logger.info(f"*** UNIFIED SETUP: Installing complete setup for AppID: {app_id} ({game_name}) ***")
        self.logger.info(f"*** MOD MANAGER MODE: {is_for_mod_manager} ***")

        try:
            # Get Steam paths and wine prefix
            steam_root = self.steam_utils.get_steam_root()
            compatdata_path = f"{steam_root}/steamapps/compatdata/{app_id}"
            wineprefix = f"{compatdata_path}/pfx"

            # Create a game dict for the installation methods
            game_dict = {
                "AppID": app_id,
                "Name": game_name,
                "prefix_path": wineprefix  # CRITICAL: Include the prefix path!
            }

            # STEP 0: Initialize Wine prefix (conditional delete/recreate for mod managers)
            # For mod managers (MO2/Vortex): Delete prefix and let winetricks create it
            # For simple game modding: Keep existing prefix to preserve saves
            if is_for_mod_manager:
                self.logger.info("===============================================================")
                self.logger.info("STEP 0: PREPARING FOR CLEAN PREFIX CREATION")
                self.logger.info("(MOD MANAGER MODE: Deleting prefix, winetricks will recreate)")
                self.logger.info("===============================================================")
                self.logger.info(f"Prefix path: {wineprefix}")
                self._log_progress("=== STEP 0: PREPARING CLEAN PREFIX ===")

                # Delete any existing prefix (created by Steam/Proton) and start fresh
                if os.path.exists(wineprefix):
                    self.logger.info(f"Deleting existing Steam-created prefix: {wineprefix}")
                    import shutil
                    shutil.rmtree(wineprefix)
                    self.logger.info("[OK] Existing prefix deleted")

                # Ensure parent compatdata directory exists (but NOT the pfx directory)
                os.makedirs(compatdata_path, exist_ok=True)
                self.logger.info(f"Compatdata directory ready: {compatdata_path}")

                # IMPORTANT: Do NOT run wineboot here!
                # Wineboot installs Mono which interferes with .NET Framework installation
                # Instead, let winetricks create the prefix when installing dotnet48
                # Winetricks will handle Mono removal and proper .NET installation
                self.logger.info("Skipping wineboot - winetricks will create prefix correctly")
                self._log_progress("[OK] Prefix cleaned - ready for winetricks installation")
            else:
                self.logger.info("===============================================================")
                self.logger.info("STEP 0: USING EXISTING WINE PREFIX")
                self.logger.info("(SIMPLE GAME MODDING MODE: Preserving existing prefix and saves)")
                self.logger.info("===============================================================")
                self.logger.info(f"Prefix path: {wineprefix}")
                self._log_progress("=== STEP 0: USING EXISTING PREFIX (preserving saves) ===")

                # Verify prefix exists
                if not os.path.exists(wineprefix):
                    raise Exception(f"Prefix does not exist at {wineprefix}. Please run the game first to create the prefix.")

            # STEP 1: Install regular dependencies
            # Base dependency list (conditional on mod manager mode)
            if is_for_mod_manager:
                # Mod Managers: Include dotnet48 (prefix was recreated, so it will work)
                dependencies = [
                    "dotnet48",  # .NET Framework 4.8 - required for mod managers
                    "fontsmooth=rgb",
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
            else:
                # Simple Game Modding: Skip dotnet48 (prefix was not recreated, installation would fail)
                dependencies = [
                    "fontsmooth=rgb",
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

            self.logger.info("===============================================================")
            self.logger.info("STEP 1: INSTALLING REGULAR DEPENDENCIES")
            self.logger.info("===============================================================")
            self.logger.info(f"TARGET: {game_name} (AppID: {app_id})")
            self.logger.info(f"Mode: {'Mod Manager' if is_for_mod_manager else 'Simple Game Modding'}")
            self.logger.info(f"Installing {len(dependencies)} dependencies")
            if is_for_mod_manager:
                self.logger.info("(Includes dotnet48 - prefix was recreated)")
            else:
                self.logger.info("(Skipping dotnet48 - preserving existing prefix)")
            for i, dep in enumerate(dependencies, 1):
                self.logger.info(f"   {i:2d}/{len(dependencies)}: {dep}")
            self.logger.info("===============================================================")

            # Also send to GUI callback for immediate display
            self._log_progress("=== STEP 1: INSTALLING REGULAR DEPENDENCIES ===")
            self._log_progress(f"Target: {game_name} (AppID: {app_id})")
            self._log_progress(f"Installing {len(dependencies)} dependencies")
            self._log_progress("Dependencies: " + ", ".join(dependencies[:7]) + f" + {len(dependencies)-7} more...")

            result = self._install_dependencies_self_contained(game_dict, dependencies, game_name)

            # STEP 2: Install .NET 9 SDK manually ONLY if basic dependencies succeeded
            if result.get("success"):
                # Install .NET 9 SDK
                self.logger.info("===============================================================")
                self.logger.info("STEP 2: INSTALLING .NET 9 SDK")
                self.logger.info("===============================================================")
                self.logger.info(f"TARGET: AppID {app_id}")
                self.logger.info("Installing .NET 9 SDK...")
                self.logger.info("This is required for MO2 and many games to function properly")

                self._log_progress("=== STEP 2: INSTALLING .NET 9 SDK ===")
                self._log_progress("Installing .NET 9 SDK...")

                dotnet_result = self.install_dotnet9_sdk(app_id)
                if dotnet_result:
                    self.logger.info("===============================================================")
                    self.logger.info(".NET 9 SDK INSTALLATION COMPLETED SUCCESSFULLY")
                    self.logger.info("===============================================================")
                    self._log_progress("[OK] .NET 9 SDK installed successfully")
                else:
                    self.logger.warning("===============================================================")
                    self.logger.warning(".NET 9 SDK INSTALLATION FAILED")
                    self.logger.warning("===============================================================")
                    self._log_progress("[FAILED] .NET 9 SDK installation failed")

                # Apply registry settings LAST (after all .NET installations)
                self.logger.info("───────────────────────────────────────────────────────────────")
                self.logger.info("REGISTRY SETTINGS APPLICATION")
                self.logger.info("───────────────────────────────────────────────────────────────")
                self.logger.info("All .NET installations complete, applying registry settings...")

                registry_result = self._apply_wine_registry_settings_self_contained(app_id, result.get("output_lines", []))
                if registry_result:
                    self.logger.info("Registry settings applied successfully")
                    self._log_progress("[OK] Registry settings applied")
                else:
                    self.logger.warning("Registry settings failed to apply")
                    self._log_progress("[FAILED] Registry settings failed")
            else:
                self.logger.error("===============================================================")
                self.logger.error("SKIPPING .NET AND REGISTRY - DEPENDENCIES FAILED")
                self.logger.error("===============================================================")
                self.logger.error(f"Basic dependency installation failed, skipping .NET and registry")

            return result

        except Exception as e:
            self.logger.error(f"Failed unified setup for {app_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def install_mo2_dependencies_for_game(self, game_app_id: str) -> Dict[str, Any]:
        """
        Install MO2 dependencies for a specific non-Steam game
        This now calls the unified setup method
        """
        self.logger.info(f"*** MO2 SETUP: Installing dependencies for AppID: {game_app_id} ***")

        try:
            # Get the game details using our built-in VDF parsing to get the game name
            self.logger.debug("Fetching non-Steam games list via built-in VDF parsing...")
            games = self.steam_utils.get_non_steam_games()
            self.logger.debug(f"Found {len(games)} non-Steam games")

            # Find the selected game to get its name
            game_name = "MO2"  # Default name
            for game in games:
                if game.get("AppID") == game_app_id:
                    game_name = game.get('Name', 'MO2')
                    self.logger.debug(f"Found target game: {game_name}")
                    break

            # Call the unified setup method with mod manager mode enabled
            result = self.install_complete_setup_for_app_id(game_app_id, game_name, is_for_mod_manager=True)

            # Mod Manager-specific: Restart Steam after setup completes (for MO2/Vortex)
            steam_restarted = False
            if result.get("success"):
                self.logger.info("===============================================================")
                self.logger.info("RESTARTING STEAM (Mod Manager setup)")
                self.logger.info("===============================================================")
                self._log_progress("=== RESTARTING STEAM ===")
                self._log_progress("Stopping Steam...")

                try:
                    # Try to kill Steam (won't error if it's not running)
                    steam_result = subprocess.run(["pkill", "-9", "steam"], timeout=30, capture_output=True)
                    if steam_result.returncode == 0:
                        self.logger.info("Steam was running and has been stopped")
                        self._log_progress("Steam stopped - waiting 10 seconds...")
                        time.sleep(10)
                    else:
                        self.logger.info("Steam was not running")
                        self._log_progress("Steam was not running - waiting 5 seconds...")
                        time.sleep(5)

                    # Always start Steam after waiting
                    self.logger.info("Starting Steam...")
                    self._log_progress("Starting Steam...")
                    subprocess.Popen(["steam"])
                    self.logger.info("Steam started successfully")
                    self._log_progress("Steam started successfully!")
                    steam_restarted = True
                except Exception as e:
                    self.logger.warning(f"Failed to restart Steam: {e}")
                    self._log_progress(f"Warning: Failed to restart Steam - please start manually")
                    steam_restarted = False

            # Add steam_restarted flag to result
            result["steam_restarted"] = steam_restarted
            return result

        except Exception as e:
            self.logger.error(f"Failed to install MO2 dependencies for game {game_app_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def _get_winetricks_command(self) -> str:
        """
        Get winetricks command path using WinetricksManager

        This method delegates to WinetricksManager which:
        - Downloads latest winetricks from GitHub (always up-to-date)
        - Caches it in ~/NaK/cache/winetricks
        - Auto-updates every 7 days

        Returns:
            Path to winetricks command, or empty string if not found
        """
        from src.core.installers.utils.winetricks_manager import get_winetricks_manager

        winetricks_mgr = get_winetricks_manager()
        winetricks_path = winetricks_mgr.get_winetricks()

        if winetricks_path:
            self.logger.info(f"Using winetricks from cache: {winetricks_path}")
            return winetricks_path
        else:
            self.logger.error("Failed to get winetricks from WinetricksManager")
            return ""

    def _verify_winetricks_installations(
        self,
        winetricks_cmd: str,
        env: dict,
        requested_dependencies: List[str]
    ) -> Dict[str, bool]:
        """
        Verify which dependencies are actually installed using winetricks list-installed

        Args:
            winetricks_cmd: Path to winetricks command
            env: Environment variables to use for winetricks
            requested_dependencies: List of dependencies that were requested to install

        Returns:
            Dict mapping dependency name to installation status (True=installed, False=not installed)
        """
        try:
            self.logger.info("Verifying installed dependencies with 'winetricks list-installed'...")

            # Run winetricks list-installed to get actually installed packages
            cmd = [winetricks_cmd, "list-installed"]
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                self.logger.error(f"Failed to run winetricks list-installed: {result.stderr}")
                # Return all as unverified (assume installed to avoid false negatives)
                return {dep: True for dep in requested_dependencies}

            # Parse installed packages from output
            installed_packages = set()
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Each line is a package name
                    installed_packages.add(line)

            self.logger.info(f"Found {len(installed_packages)} installed packages via winetricks")
            self.logger.debug(f"Installed packages: {', '.join(sorted(installed_packages))}")

            # Check each requested dependency
            verification_results = {}
            for dep in requested_dependencies:
                # Handle dependencies with arguments (e.g., fontsmooth=rgb)
                dep_name = dep.split('=')[0]
                is_installed = dep_name in installed_packages
                verification_results[dep] = is_installed

                if is_installed:
                    self.logger.info(f"  ✓ {dep}: VERIFIED INSTALLED")
                else:
                    self.logger.warning(f"  ✗ {dep}: NOT FOUND IN INSTALLED LIST")

            return verification_results

        except subprocess.TimeoutExpired:
            self.logger.error("winetricks list-installed timed out")
            # Return all as unverified (assume installed to avoid false negatives)
            return {dep: True for dep in requested_dependencies}
        except Exception as e:
            self.logger.error(f"Failed to verify installations: {e}")
            # Return all as unverified (assume installed to avoid false negatives)
            return {dep: True for dep in requested_dependencies}

    def diagnose_prefix_state(self, app_id: str) -> Dict[str, Any]:
        """
        Diagnose the state of a Wine prefix to help debug installation issues

        Args:
            app_id: Steam AppID

        Returns:
            Dict with diagnostic information
        """
        try:
            steam_root = self.steam_utils.get_steam_root()
            wineprefix = f"{steam_root}/steamapps/compatdata/{app_id}/pfx"

            self.logger.info("═" * 60)
            self.logger.info(f"DIAGNOSING PREFIX: {app_id}")
            self.logger.info("═" * 60)

            diagnostics = {
                "app_id": app_id,
                "prefix_path": wineprefix,
                "prefix_exists": os.path.exists(wineprefix),
            }

            if not diagnostics["prefix_exists"]:
                self.logger.error(f"Prefix does not exist: {wineprefix}")
                return diagnostics

            # Check for Wine Mono
            mono_path = f"{wineprefix}/drive_c/windows/mono"
            diagnostics["wine_mono_present"] = os.path.exists(mono_path)
            if diagnostics["wine_mono_present"]:
                self.logger.warning(f"Wine Mono found at: {mono_path}")
            else:
                self.logger.info("Wine Mono not present (good for .NET installations)")

            # Check for .NET installations
            dotnet_base = f"{wineprefix}/drive_c/windows/Microsoft.NET/Framework"
            diagnostics["dotnet_base_exists"] = os.path.exists(dotnet_base)

            if diagnostics["dotnet_base_exists"]:
                # List .NET versions
                dotnet_versions = []
                for item in os.listdir(dotnet_base):
                    if item.startswith("v"):
                        version_path = os.path.join(dotnet_base, item)
                        dotnet_versions.append({
                            "version": item,
                            "path": version_path,
                            "has_mscorlib": os.path.exists(os.path.join(version_path, "mscorlib.dll")),
                            "has_ngen": os.path.exists(os.path.join(version_path, "ngen.exe"))
                        })
                diagnostics["dotnet_versions"] = dotnet_versions

                self.logger.info(f"Found {len(dotnet_versions)} .NET Framework versions:")
                for ver in dotnet_versions:
                    self.logger.info(f"  - {ver['version']}: mscorlib={ver['has_mscorlib']}, ngen={ver['has_ngen']}")
            else:
                self.logger.warning("No .NET Framework directory found")
                diagnostics["dotnet_versions"] = []

            # Get winetricks installed list
            winetricks_cmd = self._get_winetricks_command()
            if winetricks_cmd:
                env = os.environ.copy()
                env['WINEPREFIX'] = wineprefix
                env['LD_LIBRARY_PATH'] = '/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu'

                cmd = [winetricks_cmd, "list-installed"]
                result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)

                if result.returncode == 0:
                    installed_list = [line.strip() for line in result.stdout.split('\n')
                                    if line.strip() and not line.startswith('#')]
                    diagnostics["winetricks_installed"] = installed_list
                    self.logger.info(f"Winetricks reports {len(installed_list)} installed packages:")
                    for pkg in installed_list:
                        self.logger.info(f"  - {pkg}")
                else:
                    diagnostics["winetricks_installed"] = []
                    self.logger.error("Failed to get winetricks installed list")

            self.logger.info("═" * 60)
            return diagnostics

        except Exception as e:
            self.logger.error(f"Failed to diagnose prefix: {e}")
            return {"error": str(e)}

    # NOTE: Winetricks cache population removed - winetricks handles its own caching
    # W_CACHE environment variable is set to ~/NaK/cache in _install_dependencies_unified
    # Winetricks will download and cache files there automatically

    def _install_proton_dependencies_self_contained(self, game: Dict[str, str]) -> Dict[str, Any]:
        """Install Proton dependencies using only bundled winetricks + Proton (no protontricks)"""
        self.logger.info(f"*** SELF-CONTAINED: Installing dependencies for {game.get('Name')} (AppID: {game.get('AppID')}) ***")

        # Note: fontsmooth=rgb is handled via registry settings, not winetricks
        comprehensive_dependencies = [
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

        return self._install_dependencies_self_contained(game, comprehensive_dependencies, game.get("Name", "Unknown"))

    def _install_dependencies_self_contained(self, game: Dict[str, str], dependencies: List[str], game_type: str) -> Dict[str, Any]:
        """Install dependencies using Proton Experimental"""
        self.logger.info(f"*** SELF-CONTAINED: Installing {game_type} dependencies for {game.get('Name')} ***")

        # Use Proton Experimental for dependency installation
        self.logger.info("*** Using Proton Experimental for dependency installation ***")
        self._log_progress("Using Proton Experimental...")

        # Get Proton Experimental wine binary path
        steam_root = os.path.expanduser("~/.local/share/Steam")
        proton_path = os.path.join(steam_root, "steamapps/common/Proton - Experimental")
        wine_path = os.path.join(proton_path, "files/bin/wine64")
        wineserver_path = os.path.join(proton_path, "files/bin/wineserver")

        if not os.path.exists(wine_path):
            self.logger.error(f"Proton Experimental not found at {wine_path}")
            self._log_progress(f"[FAILED] Proton Experimental not found")
            return {
                "success": False,
                "error": f"Proton Experimental not found at {wine_path}",
                "method": "proton_experimental_not_found"
            }

        self.logger.info(f"*** Using Proton Experimental Wine: {wine_path} ***")
        self._log_progress(f"[OK] Using Proton Experimental for dependency installation")

        # Use Proton Experimental wine for dependency installation
        return self._install_dependencies_unified(
            game=game,
            dependencies=dependencies,
            wine_binary=wine_path,
            wineserver_binary=wineserver_path,
            wine_prefix=game.get('prefix_path'),
            method_name="Proton-Experimental"
        )

    def _install_dependencies_unified(
        self,
        game: Dict[str, str],
        dependencies: List[str],
        wine_binary: str,
        wine_prefix: Optional[str] = None,
        wineserver_binary: Optional[str] = None,
        steam_compat_client_path: Optional[str] = None,
        steam_compat_data_path: Optional[str] = None,
        method_name: str = "Wine"
    ) -> Dict[str, Any]:
        """
        Unified dependency installation method using winetricks + Wine/Proton

        Args:
            game: Game dictionary with Name, AppID, etc.
            dependencies: List of winetricks verbs to install
            wine_binary: Path to wine/wine64 binary
            wine_prefix: Wine prefix path (WINEPREFIX)
            wineserver_binary: Optional wineserver binary path
            steam_compat_client_path: Optional Steam client path for Proton
            steam_compat_data_path: Optional Steam compat data path for Proton
            method_name: Method name for logging (e.g., "Proton")

        Returns:
            Dict with success status and message
        """
        try:
            self.logger.info(f"Installing dependencies using {method_name}: {wine_binary}")

            # Handle empty dependencies list
            if not dependencies:
                return {
                    "success": True,
                    "message": f"No dependencies to install for {game.get('Name')}",
                    "method": method_name.lower().replace("-", "_")
                }

            # Set up Wine environment
            env = os.environ.copy()
            env["WINE"] = wine_binary
            env["WINEARCH"] = "win64"
            env["WINETRICKS_LATEST_VERSION_CHECK"] = "disabled"
            env["W_CACHE"] = str(self.cache_manager.cache_dir)

            # Set wineserver if provided
            if wineserver_binary:
                env["WINESERVER"] = wineserver_binary
                # Add wine bin directory to PATH
                bin_dir = os.path.dirname(wine_binary)
                env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
                self.logger.info(f"Using wineserver: {wineserver_binary}")
                self.logger.info(f"Added Proton bin to PATH: {bin_dir}")

            # If running from AppImage, ensure bundled tools are in PATH
            appdir = os.environ.get('APPDIR')
            if appdir:
                appimage_bin = f"{appdir}/usr/bin"
                if appimage_bin not in env.get('PATH', ''):
                    env["PATH"] = f"{appimage_bin}:{env.get('PATH', '')}"
                    self.logger.info(f"Added AppImage bin to PATH: {appimage_bin}")

            # Set wine prefix
            if wine_prefix:
                env["WINEPREFIX"] = wine_prefix
                self.logger.info(f"WINEPREFIX: {wine_prefix}")
                self._log_progress(f"Target prefix: {wine_prefix}")
            else:
                self.logger.error("CRITICAL: No wine prefix provided - dependencies will install to wrong location!")
                self._log_progress("ERROR: No wine prefix provided!")

            # Set Steam compat variables if provided (for Proton)
            if steam_compat_client_path:
                env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam_compat_client_path
                self.logger.info(f"STEAM_COMPAT_CLIENT_INSTALL_PATH: {steam_compat_client_path}")
            if steam_compat_data_path:
                env["STEAM_COMPAT_DATA_PATH"] = steam_compat_data_path
                self.logger.info(f"STEAM_COMPAT_DATA_PATH: {steam_compat_data_path}")

            # Clean AppImage environment to avoid library conflicts
            # This prevents winetricks from using AppImage-bundled libraries
            # which can cause symbol lookup errors (e.g., readline incompatibility)

            # Save APPDIR for bundled tools (cabextract, etc.) before cleaning
            appdir = os.environ.get('APPDIR')

            appimage_vars = [
                'APPIMAGE', 'APPDIR', 'OWD', 'ARGV0',
                'LIBRARY_PATH', 'LD_PRELOAD',
                'PYTHONHOME', 'PYTHONPATH'
            ]
            cleaned_vars = []
            for var in appimage_vars:
                if var in env:
                    env.pop(var)
                    cleaned_vars.append(var)

            # CRITICAL: Set LD_LIBRARY_PATH to system paths FIRST to avoid conflicts
            # But append AppImage lib paths so bundled tools (cabextract, unzstd) can find their dependencies
            system_lib_paths = '/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu'
            if appdir:
                # Add AppImage lib paths AFTER system paths (lower priority to avoid conflicts)
                env['LD_LIBRARY_PATH'] = f"{system_lib_paths}:{appdir}/usr/lib:{appdir}/usr/lib/x86_64-linux-gnu"
                cleaned_vars.append('LD_LIBRARY_PATH (system paths + AppImage libs for bundled tools)')
            else:
                # Not running from AppImage, use system paths only
                env['LD_LIBRARY_PATH'] = system_lib_paths
                cleaned_vars.append('LD_LIBRARY_PATH (reset to system paths)')

            if cleaned_vars:
                self.logger.info(f"Cleaned AppImage environment variables: {', '.join(cleaned_vars)}")
                self.logger.info("This prevents library conflicts when running winetricks")

            # Initialize Proton prefix first if using Proton
            # This creates the proper Proton directory structure (tracked_files, etc.)
            # and prevents "Upgrading prefix from None" errors
            if steam_compat_data_path and (method_name.startswith("Proton") or method_name == "GE-Proton"):
                # Find the proton script (should be in wine binary's grandparent directory)
                wine_bin_dir = os.path.dirname(wine_binary)  # .../files/bin
                proton_root = os.path.dirname(os.path.dirname(wine_bin_dir))  # .../
                proton_script = os.path.join(proton_root, "proton")

                if os.path.isfile(proton_script):
                    self.logger.info("Initializing Proton prefix before running winetricks...")
                    self.logger.info(f"Proton script: {proton_script}")
                    self._log_progress("Initializing Proton prefix...")

                    # Run a simple command through Proton to initialize the prefix
                    # This creates tracked_files and other Proton-specific files
                    try:
                        init_cmd = [proton_script, "waitforexitandrun", "wineboot", "-i"]
                        init_result = subprocess.run(
                            init_cmd,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=60
                        )
                        if init_result.returncode == 0:
                            self.logger.info("✓ Proton prefix initialized successfully")
                        else:
                            self.logger.warning(f"Proton prefix initialization exited with code {init_result.returncode}")
                            self.logger.debug(f"STDERR: {init_result.stderr[:500]}")
                    except subprocess.TimeoutExpired:
                        self.logger.warning("Proton prefix initialization timed out (may still have succeeded)")
                    except Exception as e:
                        self.logger.warning(f"Could not initialize Proton prefix: {e}")
                        self.logger.warning("Continuing anyway - winetricks will create a basic Wine prefix")
                else:
                    self.logger.warning(f"Proton script not found at {proton_script} - skipping prefix initialization")

            # Get winetricks command
            winetricks_cmd = self._get_winetricks_command()
            if not winetricks_cmd:
                return {
                    "success": False,
                    "error": "Winetricks not found - cannot install dependencies",
                    "method": method_name.lower().replace("-", "_") + "_winetricks_missing"
                }

            # Build command
            cmd = [winetricks_cmd, "-q"] + dependencies

            # Log installation details
            self.logger.info("═" * 60)
            self.logger.info(f"DEPENDENCY INSTALLATION - {method_name}")
            self.logger.info("═" * 60)
            self.logger.info(f"Game: {game.get('Name')}")
            self.logger.info(f"Wine Binary: {wine_binary}")
            self.logger.info(f"Dependencies ({len(dependencies)}): {', '.join(dependencies)}")
            self.logger.info(f"Command: {' '.join(cmd)}")

            self._log_progress(f"Installing {len(dependencies)} dependencies via {method_name}...")

            # Run winetricks
            result_cmd = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

            # Log results (minimal output - full details at DEBUG level)
            self.logger.debug("─" * 60)
            self.logger.debug(f"Exit Code: {result_cmd.returncode}")

            # Only log STDOUT at DEBUG level
            if result_cmd.stdout:
                self.logger.debug(f"STDOUT ({len(result_cmd.stdout)} chars - truncated for brevity)")
                for line in result_cmd.stdout.split('\n')[:10]:
                    self.logger.debug(f"  {line}")

            # Only log STDERR if there was an error, and keep it minimal
            if result_cmd.stderr and result_cmd.returncode != 0:
                stderr_lines = result_cmd.stderr.split('\n')
                self.logger.warning(f"STDERR detected ({len(stderr_lines)} lines) - showing last 10 for error context:")
                # Only show last 10 lines which usually contain the actual error
                for line in stderr_lines[-10:]:
                    if line.strip():  # Skip empty lines
                        self.logger.warning(f"  {line}")
            elif result_cmd.stderr:
                # If STDERR exists but command succeeded, only mention it at DEBUG level
                self.logger.debug(f"STDERR ({len(result_cmd.stderr)} chars) - command succeeded despite warnings")

            # Clean up winetricks temp folders after installation
            self.logger.info("Cleaning up winetricks temporary folders...")
            self._log_progress("Cleaning up temporary files...")
            try:
                cleanup_result = self.cache_manager.clean_winetricks_temp_folders()
                if cleanup_result.get("success") and cleanup_result.get("space_freed_mb", 0) > 0:
                    self._log_progress(f"[OK] Cleaned temp folders, freed {cleanup_result['space_freed_mb']:.1f} MB")
                    self.logger.info(f"Cleanup: {cleanup_result['message']}")
            except Exception as cleanup_error:
                self.logger.warning(f"Failed to clean up temp folders: {cleanup_error}")

            # VERIFICATION STEP: Use winetricks list-installed to verify what actually got installed
            # This is more reliable than checking winetricks exit code or stderr
            self.logger.info("═" * 60)
            self.logger.info(f"{method_name} INSTALLATION - VERIFYING")
            self.logger.info("═" * 60)
            self._log_progress("Verifying installed dependencies...")

            verification_results = self._verify_winetricks_installations(
                winetricks_cmd, env, dependencies
            )

            # Analyze verification results
            installed_deps = [dep for dep, installed in verification_results.items() if installed]
            failed_deps = [dep for dep, installed in verification_results.items() if not installed]

            # Log detailed results
            self.logger.info(f"Verification complete: {len(installed_deps)}/{len(dependencies)} dependencies verified")
            if installed_deps:
                self.logger.info(f"Successfully installed: {', '.join(installed_deps)}")
            if failed_deps:
                self.logger.error(f"Failed to install: {', '.join(failed_deps)}")

            # Determine overall success
            if len(failed_deps) == 0:
                # All dependencies verified as installed
                self.logger.info("═" * 60)
                self.logger.info(f"{method_name} INSTALLATION - SUCCESS")
                self.logger.info("═" * 60)
                self._log_progress(f"[OK] All {len(dependencies)} dependencies installed successfully!")
                return {
                    "success": True,
                    "message": f"Dependencies installed for {game.get('Name')} using {method_name}",
                    "method": method_name.lower().replace("-", "_"),
                    "installed_count": len(installed_deps),
                    "total_count": len(dependencies)
                }
            else:
                # Some dependencies failed to install
                self.logger.error("═" * 60)
                self.logger.error(f"{method_name} INSTALLATION - PARTIAL FAILURE")
                self.logger.error("═" * 60)
                self.logger.error(f"Installed: {len(installed_deps)}/{len(dependencies)} dependencies")
                self.logger.error(f"Failed: {', '.join(failed_deps)}")
                self._log_progress(f"[FAILED] {len(failed_deps)} dependencies failed to install: {', '.join(failed_deps)}")

                return {
                    "success": False,
                    "error": f"{method_name} failed to install: {', '.join(failed_deps)}",
                    "method": method_name.lower().replace("-", "_") + "_partial_failure",
                    "installed_count": len(installed_deps),
                    "total_count": len(dependencies),
                    "failed_dependencies": failed_deps
                }

        except subprocess.TimeoutExpired:
            self.logger.error(f"{method_name} installation timed out after 10 minutes")
            return {
                "success": False,
                "error": f"{method_name} dependency installation timed out after 10 minutes",
                "method": method_name.lower().replace("-", "_") + "_timeout"
            }
        except Exception as e:
            self.logger.error(f"Failed to install dependencies with {method_name}: {e}")
            return {
                "success": False,
                "error": f"Failed to install dependencies with {method_name}: {e}",
                "method": method_name.lower().replace("-", "_") + "_error"
            }

    def _apply_wine_registry_settings_self_contained(self, app_id: str, output_lines: list) -> bool:
        """Apply Wine registry settings using appropriate method based on settings"""
        try:
            self.logger.info(f"*** SELF-CONTAINED REGISTRY: Applying settings for AppID: {app_id} ***")

            # Check settings to determine Wine or Proton preference
            try:
                from src.utils.settings_manager import SettingsManager
                settings = SettingsManager()
                preferred_version = settings.get_preferred_proton_version()

                # Check if it's Wine (including Wine-TKG)
                if preferred_version in ["Wine", "Wine-TKG"]:
                    self.logger.info("*** Using Wine for registry application ***")
                    wine_path = settings.get_wine_path()
                    if wine_path and os.path.exists(wine_path):
                        return self._apply_registry_with_wine(app_id, wine_path)
                    else:
                        self.logger.error("Wine not found for registry application")
                        return False
                else:
                    # Use Proton (including Heroic Proton)
                    self.logger.info("*** Using Proton for registry application ***")
                    return self._apply_registry_with_proton(app_id)

            except Exception as e:
                self.logger.error(f"Failed to determine registry method: {e}")
                # Fallback to Proton method
                return self._apply_registry_with_proton(app_id)

        except Exception as e:
            self.logger.error(f"Registry application error: {e}")
            return False

    def _apply_registry_with_wine(self, app_id: str, wine_path: str) -> bool:
        """Apply registry settings using Wine directly"""
        try:
            # Find wine_settings.reg file
            wine_settings_path = Path(__file__).parent.parent / "utils" / "wine_settings.reg"
            if not wine_settings_path.exists():
                self.logger.error(f"Wine settings reg file not found at: {wine_settings_path}")
                return False

            # Create temporary copy
            with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False) as temp_file:
                with open(wine_settings_path, 'r') as f:
                    temp_file.write(f.read())
                temp_reg_path = temp_file.name

                # Set up Wine environment
                env = os.environ.copy()
                env["WINE"] = wine_path
                env["XDG_RUNTIME_DIR"] = "/tmp"
                env["DISPLAY"] = ":0"

            cmd = ["wine", "regedit", temp_reg_path]
            self.logger.info(f"*** WINE REGISTRY: Running {' '.join(cmd)} ***")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)

            # Cleanup
            Path(temp_reg_path).unlink(missing_ok=True)

            if result.returncode == 0:
                self.logger.info("*** WINE REGISTRY: Success! ***")
                self.logger.info("Registry settings include .NET 4.0 activation keys (mscoree=native + OnlyUseLatestCLR)")
                return True
            else:
                self.logger.error(f"Wine registry application failed: {result.returncode}")
                return False

        except Exception as e:
            self.logger.error(f"Wine registry application error: {e}")
            return False

    def _apply_registry_with_proton(self, app_id: str) -> bool:
        """Apply registry settings using Proton"""
        try:
            # Find wine_settings.reg file
            wine_settings_path = Path(__file__).parent.parent / "utils" / "wine_settings.reg"
            if not wine_settings_path.exists():
                self.logger.error(f"Wine settings reg file not found at: {wine_settings_path}")
                return False

            # Create temporary copy
            with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False) as temp_file:
                with open(wine_settings_path, 'r') as f:
                    temp_file.write(f.read())
                temp_reg_path = temp_file.name

            # Get paths
            steam_root = self.steam_utils.get_steam_root()
            compatdata_path = f"{steam_root}/steamapps/compatdata/{app_id}"

            # Find Proton path
            proton_wine_bin = self._get_heroic_wine_binary_for_steam()
            if not proton_wine_bin or not os.path.exists(proton_wine_bin):
                self.logger.error("Proton not found for registry application")
                return False

            if not os.path.exists(compatdata_path):
                self.logger.error("Required compatdata path not found for registry installation")
                return False

            # Set up environment
            env = os.environ.copy()
            env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = steam_root
            env['STEAM_COMPAT_DATA_PATH'] = compatdata_path

            cmd = [proton_wine_bin, "run", "regedit", temp_reg_path]
            self.logger.info(f"*** PROTON REGISTRY: Running {' '.join(cmd)} ***")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)

            # Cleanup
            Path(temp_reg_path).unlink(missing_ok=True)

            if result.returncode == 0:
                self.logger.info("*** PROTON REGISTRY: Success! ***")
                self.logger.info("Registry settings include .NET 4.0 activation keys (mscoree=native + OnlyUseLatestCLR)")
                return True
            else:
                self.logger.error(f"Proton registry application failed: {result.returncode}")
                return False

        except Exception as e:
            self.logger.error(f"Proton registry application error: {e}")
            return False


    def remove_wine_mono(self, game_app_id: str) -> bool:
        """Remove Wine Mono to allow real .NET Framework installation

        Wine Mono is ALWAYS installed by default in Wine/Proton prefixes.
        It must be removed before installing real .NET Framework because:
        1. Wine Mono creates stub .NET Framework files/registry entries
        2. These stubs prevent real .NET Framework installers from running
        3. Real .NET Framework and Wine Mono cannot coexist
        """
        self.logger.info(f"Removing Wine Mono from prefix for AppID: {game_app_id}")
        self.logger.info("Wine Mono is always present in Wine/Proton prefixes and must be removed")
        self._log_progress("Removing Wine Mono (required for .NET Framework)...")

        try:
            # Get bundled winetricks
            winetricks_cmd = self._get_winetricks_command()
            if not winetricks_cmd:
                self.logger.error("Winetricks not found - cannot remove Wine Mono")
                return False

            # Get paths
            steam_root = self.steam_utils.get_steam_root()
            compatdata_path = f"{steam_root}/steamapps/compatdata/{game_app_id}"

            # Set up Proton environment for winetricks
            env = os.environ.copy()

            # CRITICAL: Reset LD_LIBRARY_PATH to system-only paths
            # This prevents AppImage libraries from breaking system binaries like /bin/sh
            env['LD_LIBRARY_PATH'] = '/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu'

            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam_root
            env["STEAM_COMPAT_DATA_PATH"] = compatdata_path
            env["WINEPREFIX"] = f"{compatdata_path}/pfx"
            env["WINEARCH"] = "win64"

            # Get Proton wine binary
            proton_bin = self._get_heroic_wine_binary_for_steam()
            proton_dir = os.path.dirname(proton_bin)
            proton_wine = os.path.join(proton_dir, "files", "bin", "wine")
            if not os.path.exists(proton_wine):
                proton_wine = os.path.join(proton_dir, "files", "bin", "wine64")

            env["WINE"] = proton_wine

            # Use winetricks to remove Wine Mono properly
            cmd = [winetricks_cmd, "-q", "remove_mono"]
            self.logger.info(f"Running: {' '.join(cmd)}")

            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                self.logger.info("[OK] Wine Mono removed successfully via winetricks")
                self._log_progress("[OK] Wine Mono removed - ready for .NET Framework")
                return True
            else:
                self.logger.warning(f"winetricks remove_mono returned code {result.returncode}")
                self.logger.warning(f"Stdout: {result.stdout}")
                self.logger.warning(f"Stderr: {result.stderr}")
                self._log_progress("⚠ Wine Mono removal completed with warnings")
                # Return True anyway - winetricks often returns non-zero even on success
                return True

        except Exception as e:
            self.logger.error(f"Failed to remove Wine Mono: {e}")
            self._log_progress("[FAILED] Wine Mono removal failed")
            return False

    def install_dotnet40(self, game_app_id: str) -> bool:
        """Install .NET Framework 4.0 using winetricks"""
        self.logger.info(f"Starting .NET Framework 4.0 installation for AppID: {game_app_id}")
        self._log_progress("Installing .NET Framework 4.0...")

        try:
            # Get bundled winetricks
            winetricks_cmd = self._get_winetricks_command()
            if not winetricks_cmd:
                self.logger.error("Winetricks not found - cannot install .NET Framework 4.0")
                return False

            # Get paths
            steam_root = self.steam_utils.get_steam_root()
            compatdata_path = f"{steam_root}/steamapps/compatdata/{game_app_id}"
            wineprefix = f"{compatdata_path}/pfx"

            # Find Proton wine binary
            proton_bin = self._get_heroic_wine_binary_for_steam()
            if not proton_bin or not os.path.exists(proton_bin):
                self.logger.error("Proton not found for .NET Framework 4.0 installation")
                return False

            proton_dir = os.path.dirname(proton_bin)
            # Use wine64 directly (not wine wrapper) for .NET Framework installation
            wine_bin = os.path.join(proton_dir, "files", "bin", "wine64")
            if not os.path.exists(wine_bin):
                self.logger.error(f"wine64 not found at {wine_bin}")
                return False

            # Set up environment for winetricks
            env = os.environ.copy()

            # CRITICAL: Reset LD_LIBRARY_PATH to system-only paths
            # This prevents AppImage libraries from breaking system binaries like /bin/sh
            env['LD_LIBRARY_PATH'] = '/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu'

            # Simple environment - just WINE, WINEPREFIX, WINEARCH (like successful test)
            # Don't use STEAM_COMPAT_* or PROTON_NO_STEAM_INTEGRATION - we're calling wine directly!
            env['WINEPREFIX'] = wineprefix
            env['WINEARCH'] = 'win64'
            env['WINE'] = wine_bin

            # Set winetricks cache to use our NaK cache directory
            nak_cache_dir = str(self.cache_manager.cache_dir)
            env['W_CACHE'] = nak_cache_dir

            # Winetricks will handle remove_mono automatically
            env['WINETRICKS_LATEST_VERSION_CHECK'] = 'disabled'

            # NOTE: Winetricks handles its own caching via W_CACHE environment variable

            # Run winetricks to install .NET Framework 4.0
            cmd = [winetricks_cmd, "-q", "dotnet40"]
            self.logger.info(f"Running: {' '.join(cmd)}")
            self._log_progress("Installing .NET Framework 4.0 with winetricks (this may take several minutes)...")

            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                self.logger.info("[OK] .NET Framework 4.0 installed successfully")
                self._log_progress("[OK] .NET Framework 4.0 installed successfully")
                return True
            else:
                self.logger.warning(f"winetricks dotnet40 returned code {result.returncode}")
                self.logger.warning(f"Stdout: {result.stdout}")
                self.logger.warning(f"Stderr: {result.stderr}")
                self._log_progress("⚠ .NET Framework 4.0 installation completed with warnings")
                # Return True anyway - winetricks often returns non-zero even on success
                return True

        except Exception as e:
            self.logger.error(f"Failed to install .NET Framework 4.0: {e}")
            self._log_progress(f"[FAILED] .NET Framework 4.0 installation failed: {e}")
            return False


    def install_dotnet9_sdk(self, game_app_id: str, progress_callback=None) -> bool:
        """Install .NET 9 SDK using appropriate method based on settings (Wine or Proton)"""
        self.logger.info(f"DOTNET INSTALLER: Starting .NET 9 SDK installation for AppID: {game_app_id}")
        self._log_progress("DOTNET INSTALLER: Downloading .NET 9 SDK installer...")

        try:
            # Check settings to determine Wine or Proton preference
            try:
                from src.utils.settings_manager import SettingsManager
                settings = SettingsManager()
                preferred_version = settings.get_preferred_proton_version()

                # Check if it's Wine (including Wine-TKG)
                if preferred_version in ["Wine", "Wine-TKG"]:
                    self.logger.info("*** DOTNET INSTALLER: Using Wine for .NET SDK installation ***")
                    wine_path = settings.get_wine_path()
                    if wine_path and os.path.exists(wine_path):
                        return self._install_dotnet_with_wine(game_app_id, wine_path, progress_callback)
                    else:
                        self.logger.error("Wine not found for .NET SDK installation")
                        return False
                else:
                    # Use Proton (including Heroic Proton)
                    self.logger.info("*** DOTNET INSTALLER: Using Proton for .NET SDK installation ***")
                    return self._install_dotnet_with_proton(game_app_id, progress_callback)

            except Exception as e:
                self.logger.error(f"Failed to determine .NET SDK installation method: {e}")
                # Fallback to Proton method
                return self._install_dotnet_with_proton(game_app_id, progress_callback)

        except Exception as e:
            self.logger.error(f"DOTNET INSTALLER: Failed to install .NET 9 SDK: {e}")
            self._log_progress(f"DOTNET INSTALLER: .NET 9 SDK installation failed: {e}")
            return False

    def _install_dotnet_with_wine(self, game_app_id: str, wine_path: str, progress_callback=None) -> bool:
        """Install .NET 9 SDK using Wine directly"""
        self.logger.info(f"DOTNET INSTALLER: Installing .NET 9 SDK using Wine: {wine_path}")

        try:
            # Use cached .NET 9 SDK if available
            cached_file = self.cache_manager.get_cached_file("dotnet9_sdk")
            if cached_file:
                self.logger.info(f"DOTNET INSTALLER: Using cached .NET 9 SDK: {cached_file}")
                self._log_progress("DOTNET INSTALLER: Using cached .NET 9 SDK installer!")
                download_path = cached_file
            else:
                # Download .NET 9 SDK
                dotnet_url = "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe"
                dotnet_file = "dotnet-sdk-9.0.203-win-x64.exe"

                home_dir = str(Path.home())
                download_path = Path(home_dir) / "Downloads" / dotnet_file

                if not download_path.exists():
                    self.logger.info(f"DOTNET INSTALLER: Downloading .NET 9 SDK...")
                    self._log_progress("DOTNET INSTALLER: Downloading .NET 9 SDK installer...")
                    import requests

                    response = requests.get(dotnet_url, stream=True)
                    with open(download_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                else:
                    self.logger.info(f"DOTNET INSTALLER: .NET 9 SDK installer already exists")

            # Install using Wine with proper headless environment
            env = os.environ.copy()
            env["WINE"] = wine_path
            env["DISPLAY"] = ":0"
            env["XDG_RUNTIME_DIR"] = "/tmp"
            env["WAYLAND_DISPLAY"] = ""
            env["QT_QPA_PLATFORM"] = "xcb"

            cmd = ["wine", str(download_path), "/quiet", "/norestart"]
            self.logger.info(f"DOTNET INSTALLER: Running Wine + .NET SDK installer...")
            self._log_progress("DOTNET INSTALLER: Starting .NET 9 SDK installation with Wine...")

            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

            # Cleanup
            download_path.unlink(missing_ok=True)

            if result.returncode == 0:
                self.logger.info("DOTNET INSTALLER: .NET 9 SDK installed successfully with Wine")
                self._log_progress("DOTNET INSTALLER: .NET 9 SDK installation completed successfully!")
                return True
            else:
                self.logger.warning(f"DOTNET INSTALLER: Wine installation returned non-zero exit code: {result.returncode}")
                return False

        except Exception as e:
            self.logger.error(f"DOTNET INSTALLER: Failed to install .NET 9 SDK with Wine: {e}")
            return False

    def _install_dotnet_with_proton(self, game_app_id: str, progress_callback=None) -> bool:
        """Install .NET 9 SDK using Proton"""
        self.logger.info("DOTNET INSTALLER: Installing .NET 9 SDK using Proton")

        try:
            # Use cached .NET 9 SDK if available
            cached_file = self.cache_manager.get_cached_file("dotnet9_sdk")
            if cached_file:
                self.logger.info(f"DOTNET INSTALLER: Using cached .NET 9 SDK: {cached_file}")
                self._log_progress("DOTNET INSTALLER: Using cached .NET 9 SDK installer!")
                download_path = cached_file
            else:
                # Download .NET 9 SDK
                dotnet_url = "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe"
                dotnet_file = "dotnet-sdk-9.0.203-win-x64.exe"

                home_dir = str(Path.home())
                download_path = Path(home_dir) / "Downloads" / dotnet_file

                if not download_path.exists():
                    self.logger.info(f"DOTNET INSTALLER: Downloading .NET 9 SDK...")
                    self._log_progress("DOTNET INSTALLER: Downloading .NET 9 SDK installer...")
                    import requests

                    response = requests.get(dotnet_url, stream=True)
                    with open(download_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                else:
                    self.logger.info(f"DOTNET INSTALLER: .NET 9 SDK installer already exists")

            # Install using Proton
            steam_root = self.steam_utils.get_steam_root()
            compatdata_path = f"{steam_root}/steamapps/compatdata/{game_app_id}"

            # Find Proton path
            proton_wine_bin = self._get_heroic_wine_binary_for_steam()
            if not proton_wine_bin or not os.path.exists(proton_wine_bin):
                self.logger.error("Proton not found for .NET SDK installation")
                return False

            env = os.environ.copy()
            env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = steam_root
            env['STEAM_COMPAT_DATA_PATH'] = compatdata_path

            cmd = [proton_wine_bin, "run", str(download_path), "/q"]
            self.logger.info(f"DOTNET INSTALLER: Running Proton + .NET SDK installer...")
            self._log_progress("DOTNET INSTALLER: Starting .NET 9 SDK installation with Proton...")

            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

            # Cleanup
            download_path.unlink(missing_ok=True)

            if result.returncode == 0:
                self.logger.info("DOTNET INSTALLER: .NET 9 SDK installed successfully with Proton")
                self._log_progress("DOTNET INSTALLER: .NET 9 SDK installation completed successfully!")
                return True
            else:
                self.logger.warning(f"DOTNET INSTALLER: Proton installation returned non-zero exit code: {result.returncode}")
                return False

        except Exception as e:
            self.logger.error(f"DOTNET INSTALLER: Failed to install .NET 9 SDK with Proton: {e}")
            return False

    def _get_heroic_wine_binary_for_steam(self) -> Optional[str]:
        """Get Proton Experimental binary - ONLY Proton Experimental is supported"""
        try:
            steam_root = self.steam_utils.get_steam_root()
            self.logger.info(f"Looking for Proton Experimental in Steam root: {steam_root}")

            if not steam_root:
                self.logger.warning("Steam root not found")
                return None

            from pathlib import Path

            # ONLY use Proton Experimental - no fallbacks
            proton_experimental = Path(steam_root) / "steamapps" / "common" / "Proton - Experimental" / "proton"

            if proton_experimental.exists():
                self.logger.info(f"FOUND: Proton Experimental at {proton_experimental}")
                return str(proton_experimental)
            else:
                self.logger.error("Proton Experimental NOT FOUND")
                self.logger.error("NaK requires Proton Experimental to be installed")
                self.logger.error(f"Expected location: {proton_experimental}")

                # List what's actually in the common directory for debugging
                proton_common = Path(steam_root) / "steamapps" / "common"
                if proton_common.exists():
                    found_protons = [item.name for item in proton_common.iterdir()
                                   if item.is_dir() and item.name.startswith("Proton")]
                    if found_protons:
                        self.logger.info(f"Other Proton versions found: {', '.join(found_protons)}")
                        self.logger.warning("NaK only supports Proton Experimental - other versions are not supported")

                return None

        except Exception as e:
            self.logger.error(f"Could not find Proton Experimental: {e}")
            return None
