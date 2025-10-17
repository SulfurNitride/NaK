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
    
    def __init__(self):
        self.logger = get_logger(__name__)
        # Force logger to write to debug file by ensuring it has the same handlers
        import logging
        root_logger = logging.getLogger()  # Get the actual root logger, not 'nak'
        if root_logger.handlers:
            # Copy handlers from root logger to ensure debug file logging
            for handler in root_logger.handlers:
                if handler not in self.logger.handlers:
                    self.logger.addHandler(handler)
            # Ensure logger level allows all messages
            self.logger.setLevel(logging.DEBUG)

        self.steam_utils = SteamUtils()
        self.cache_manager = DependencyCacheManager()
        self.log_callback = None
    
    def set_log_callback(self, callback):
        """Set log callback for status messages"""
        self.log_callback = callback
        # Also set the cache manager's progress callback
        self.cache_manager.set_progress_callback(callback)
    
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
            results = self.cache_manager.cache_all_dependencies(force_download)
            
            successful = sum(1 for success in results.values() if success)
            total = len(results)
            
            if successful == total:
                self._log_progress(f"✓ Successfully cached all {total} dependencies!")
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
            self._log_progress(f"✗ Failed to cache dependencies: {e}")
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
    
    def clear_dependency_cache(self) -> Dict[str, Any]:
        """Clear all cached dependency files"""
        self.logger.info("Clearing dependency cache...")
        self._log_progress("Clearing dependency cache...")
        
        try:
            success = self.cache_manager.clear_cache()
            if success:
                self._log_progress("✓ Dependency cache cleared successfully!")
                return {"success": True, "message": "Dependency cache cleared successfully"}
            else:
                self._log_progress("✗ Failed to clear dependency cache")
                return {"success": False, "error": "Failed to clear dependency cache"}
                
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            self._log_progress(f"✗ Failed to clear cache: {e}")
            return {"success": False, "error": str(e)}
    
    def install_basic_dependencies(self) -> Dict[str, Any]:
        """Install common Proton components for any mod manager (completely self-contained)"""
        self.logger.info("*** SELF-CONTAINED DEPENDENCY INSTALLATION (no protontricks required) ***")

        try:
            # Get non-Steam games using our built-in VDF parsing
            games = self.steam_utils.get_non_steam_games()
            if not games:
                return {
                    "success": False,
                    "error": "No non-Steam games found. Add some games to Steam first."
                }

            # Auto-select if only one game found
            if len(games) == 1:
                selected_game = games[0]
                self.logger.info(f"Auto-selected game: {selected_game.get('Name')}")
                return self._install_proton_dependencies_self_contained(selected_game)

            # Return games list for selection
            return {
                "success": True,
                "games": games,
                "message": f"Found {len(games)} non-Steam games. Please select one to install dependencies:"
            }

        except Exception as e:
            self.logger.error(f"Failed to install basic dependencies: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
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
    
    def install_complete_setup_for_app_id(self, app_id: str, game_name: str = "Unknown") -> Dict[str, Any]:
        """
        UNIFIED method for complete game setup (dependencies + registry + .NET SDK)
        Works for ANY app_id (Steam games or non-Steam games added to Steam)
        Used by both "Setup Existing MO2" and "Simple Game Modding"
        """
        self.logger.info(f"*** UNIFIED SETUP: Installing complete setup for AppID: {app_id} ({game_name}) ***")

        try:
            # Create a game dict for the installation methods
            game_dict = {
                "AppID": app_id,
                "Name": game_name
            }

            # Comprehensive dependency list - includes ALL dependencies for games and MO2
            dependencies = [
                "fontsmooth=rgb",
                "xact",
                "xact_x64",
                "vcrun2022",
                "dotnet6",
                "dotnet7",
                "dotnet8",
                "dotnetdesktop6",
                "d3dcompiler_47",
                "d3dx11_43",
                "d3dcompiler_43",
                "d3dx9_43",
                "d3dx9",
                "vkd3d",
            ]

            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("UNIFIED COMPLETE SETUP STARTING")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"TARGET: {game_name} (AppID: {app_id})")
            self.logger.info(f"Installing {len(dependencies)} comprehensive dependencies")
            self.logger.info("This includes ALL requirements for games and MO2:")
            for i, dep in enumerate(dependencies, 1):
                self.logger.info(f"   {i:2d}/{len(dependencies)}: {dep}")
            self.logger.info("═══════════════════════════════════════════════════════════════")

            # Also send to GUI callback for immediate display
            self._log_progress("═══ UNIFIED COMPLETE SETUP STARTING ═══")
            self._log_progress(f"Target: {game_name} (AppID: {app_id})")
            self._log_progress(f"Installing {len(dependencies)} dependencies")
            self._log_progress("Dependencies: " + ", ".join(dependencies[:7]) + f" + {len(dependencies)-7} more...")

            result = self._install_dependencies_self_contained(game_dict, dependencies, game_name)

            # Apply registry settings and install .NET SDK ONLY if basic dependencies succeeded
            if result.get("success"):
                self.logger.info("───────────────────────────────────────────────────────────────")
                self.logger.info("REGISTRY SETTINGS AND .NET SDK INSTALLATION")
                self.logger.info("───────────────────────────────────────────────────────────────")
                self.logger.info("Basic dependencies installed successfully, proceeding with registry settings...")

                registry_result = self._apply_wine_registry_settings_self_contained(app_id, result.get("output_lines", []))
                if registry_result:
                    self.logger.info("Registry settings applied successfully")
                    self._log_progress("✓ Registry settings applied")
                else:
                    self.logger.warning("Registry settings failed to apply")
                    self._log_progress("✗ Registry settings failed")

                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info(".NET 9 SDK INSTALLATION STARTING")
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info(f"TARGET: AppID {app_id}")
                self.logger.info("Installing .NET 9 SDK after dependencies and registry...")
                self.logger.info("This is required for MO2 and many games to function properly")
                self.logger.info("Download URL: https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe")

                # Also send to GUI
                self._log_progress("═══ .NET 9 SDK INSTALLATION STARTING ═══")
                self._log_progress("Installing .NET 9 SDK...")

                dotnet_result = self.install_dotnet9_sdk(app_id)
                if dotnet_result:
                    self.logger.info("═══════════════════════════════════════════════════════════════")
                    self.logger.info(".NET 9 SDK INSTALLATION COMPLETED SUCCESSFULLY")
                    self.logger.info("═══════════════════════════════════════════════════════════════")
                    self.logger.info(".NET 9 SDK installed successfully")
                    self._log_progress("✓ .NET 9 SDK installed successfully")
                else:
                    self.logger.warning("═══════════════════════════════════════════════════════════════")
                    self.logger.warning(".NET 9 SDK INSTALLATION FAILED")
                    self.logger.warning("═══════════════════════════════════════════════════════════════")
                    self.logger.warning(".NET 9 SDK installation failed")
                    self._log_progress("✗ .NET 9 SDK installation failed")
            else:
                self.logger.error("═══════════════════════════════════════════════════════════════")
                self.logger.error("SKIPPING REGISTRY AND .NET SDK - DEPENDENCIES FAILED")
                self.logger.error("═══════════════════════════════════════════════════════════════")
                self.logger.error(f"Basic dependency installation failed, skipping registry and .NET SDK")

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

            # Call the unified setup method
            result = self.install_complete_setup_for_app_id(game_app_id, game_name)

            # MO2-specific: Restart Steam after setup completes (only for MO2)
            if result.get("success"):
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info("RESTARTING STEAM (MO2-specific)")
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self._log_progress("═══ RESTARTING STEAM ═══")
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
                except Exception as e:
                    self.logger.warning(f"Failed to restart Steam: {e}")
                    self._log_progress(f"Warning: Failed to restart Steam - please start manually")

            return result

        except Exception as e:
            self.logger.error(f"Failed to install MO2 dependencies for game {game_app_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def _get_winetricks_command(self) -> str:
        """Get the bundled winetricks command path - ONLY use bundled version"""
        # Check if we're running in PyInstaller
        if getattr(sys, 'frozen', False):
            # PyInstaller bundles files in sys._MEIPASS
            bundled_winetricks = os.path.join(sys._MEIPASS, "winetricks")
            if os.path.exists(bundled_winetricks):
                self.logger.info(f"*** USING PYINSTALLER BUNDLED WINETRICKS: {bundled_winetricks} ***")
                return bundled_winetricks
            else:
                self.logger.info(f"PyInstaller bundled winetricks not found at {bundled_winetricks}, checking AppImage location...")

        # Check if we're running in AppImage
        appdir = os.environ.get('APPDIR')
        self.logger.info(f"*** CHECKING APPIMAGE - APPDIR: {appdir} ***")
        if appdir:
            self.logger.info(f"*** APPIMAGE DETECTED - APPDIR: {appdir} ***")
            # Use ONLY bundled winetricks from AppImage
            bundled_winetricks = os.path.join(appdir, "usr", "bin", "winetricks")
            self.logger.info(f"*** LOOKING FOR WINETRICKS AT: {bundled_winetricks} ***")
            if os.path.exists(bundled_winetricks):
                self.logger.info(f"*** USING APPIMAGE BUNDLED WINETRICKS: {bundled_winetricks} ***")
                return bundled_winetricks
            else:
                self.logger.error(f"CRITICAL: AppImage bundled winetricks not found at {bundled_winetricks}")
                # List directory contents for debugging
                usr_bin_dir = os.path.join(appdir, "usr", "bin")
                if os.path.exists(usr_bin_dir):
                    files = os.listdir(usr_bin_dir)
                    self.logger.info(f"*** FILES IN {usr_bin_dir}: {files} ***")
                else:
                    self.logger.error(f"*** DIRECTORY {usr_bin_dir} DOES NOT EXIST ***")
                return ""

        # If not in AppImage or PyInstaller, this is a development environment - still prefer bundled
        local_winetricks = os.path.join(os.getcwd(), "winetricks")
        if os.path.exists(local_winetricks):
            self.logger.info(f"*** USING LOCAL BUNDLED WINETRICKS: {local_winetricks} ***")
            return local_winetricks

        self.logger.error("CRITICAL: No bundled winetricks found - this should not happen in production")
        return ""
    
    def _populate_winetricks_cache(self, dependencies: List[str]):
        """Pre-populate winetricks cache with our cached files"""
        self.logger.info("Pre-populating winetricks cache with NaK cached files...")
        
        # Mapping of winetricks dependency names to our cache keys
        dependency_mapping = {
            "vcrun2022": ["vcrun2022_x86", "vcrun2022_x64"],
            "dotnet6": ["dotnet6_x86", "dotnet6_x64"],
            "dotnet7": ["dotnet7_x86", "dotnet7_x64"],
            "dotnet8": ["dotnet8_x86", "dotnet8_x64"],
            "dotnetdesktop6": ["dotnetdesktop6_x86", "dotnetdesktop6_x64"],
            "dotnet9sdk": ["dotnet9_sdk"],
            "d3dcompiler_47": ["d3dcompiler_47_x86", "d3dcompiler_47_x64"],
            "d3dcompiler_43": ["d3dcompiler_43"],  # Extracted from DirectX
            "xact": ["directx_jun2010"],
            "xact_x64": ["directx_jun2010"],
            "d3dx11_43": ["directx_jun2010"],
            "d3dx9_43": ["directx_jun2010"],
            "d3dx9": ["directx_jun2010"],
            "vkd3d": ["vkd3d"]
        }
        
        for dep in dependencies:
            if dep in dependency_mapping:
                cache_keys = dependency_mapping[dep]
                for cache_key in cache_keys:
                    cached_file = self.cache_manager.get_cached_file(cache_key)
                    if cached_file:
                        self._organize_file_for_winetricks(cached_file, dep, cache_key)
                    else:
                        self.logger.warning(f"No cached file found for {cache_key}")
    
    def _organize_file_for_winetricks(self, cached_file: Path, winetricks_dep: str, cache_key: str):
        """Organize cached file into winetricks cache structure"""
        try:
            # Create winetricks cache directory for this dependency
            winetricks_cache_dir = self.cache_manager.cache_dir / winetricks_dep
            winetricks_cache_dir.mkdir(exist_ok=True)
            
            # Copy file to winetricks cache directory
            target_file = winetricks_cache_dir / cached_file.name
            
            if not target_file.exists():
                import shutil
                shutil.copy2(cached_file, target_file)
                self.logger.info(f"Copied {cached_file.name} to winetricks cache: {target_file}")
            else:
                self.logger.info(f"File already exists in winetricks cache: {target_file}")
            
            # Special handling for specific dependencies
            if winetricks_dep == "d3dcompiler_47":
                # d3dcompiler_47 needs specific directory structure
                if cache_key == "d3dcompiler_47_x86":
                    # Copy to system32 directory structure
                    system32_dir = winetricks_cache_dir / "d3dcompiler_47"
                    system32_dir.mkdir(exist_ok=True)
                    system32_target = system32_dir / "d3dcompiler_47_32.dll"
                    if not system32_target.exists():
                        shutil.copy2(cached_file, system32_target)
                        self.logger.info(f"Organized d3dcompiler_47_x86 for winetricks: {system32_target}")
                elif cache_key == "d3dcompiler_47_x64":
                    # Copy to system32 directory structure
                    system32_dir = winetricks_cache_dir / "d3dcompiler_47"
                    system32_dir.mkdir(exist_ok=True)
                    system32_target = system32_dir / "d3dcompiler_47.dll"
                    if not system32_target.exists():
                        shutil.copy2(cached_file, system32_target)
                        self.logger.info(f"Organized d3dcompiler_47_x64 for winetricks: {system32_target}")
            
            elif winetricks_dep == "d3dcompiler_43":
                # d3dcompiler_43 is extracted from DirectX June 2010
                if cache_key == "d3dcompiler_43":
                    # Extract d3dcompiler_43.dll from DirectX June 2010
                    self._extract_d3dcompiler_43_from_directx(winetricks_cache_dir)
            
            elif winetricks_dep in ["xact", "xact_x64", "d3dx11_43", "d3dx9_43", "d3dx9"]:
                # These all come from DirectX June 2010
                if cache_key == "directx_jun2010":
                    # Copy to each dependency's cache directory
                    for dx_dep in ["xact", "xact_x64", "d3dx11_43", "d3dx9_43", "d3dx9"]:
                        dx_cache_dir = self.cache_manager.cache_dir / dx_dep
                        dx_cache_dir.mkdir(exist_ok=True)
                        dx_target = dx_cache_dir / cached_file.name
                        if not dx_target.exists():
                            shutil.copy2(cached_file, dx_target)
                            self.logger.info(f"Organized DirectX for {dx_dep}: {dx_target}")
            
        except Exception as e:
            self.logger.error(f"Failed to organize {cached_file} for winetricks: {e}")
    
    def _extract_d3dcompiler_43_from_directx(self, winetricks_cache_dir: Path):
        """Extract d3dcompiler_43.dll from DirectX June 2010"""
        try:
            # Get the DirectX June 2010 file
            directx_file = self.cache_manager.get_cached_file("directx_jun2010")
            if not directx_file:
                self.logger.error("DirectX June 2010 not found in cache")
                return
            
            # Create temporary directory for extraction
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Use cabextract to extract d3dcompiler_43 files
                import subprocess
                cmd = [
                    "cabextract", "-d", str(temp_path), "-L", "-F", "*d3dcompiler_43*x86*", 
                    str(directx_file)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    self.logger.error(f"Failed to extract d3dcompiler_43 from DirectX: {result.stderr}")
                    return
                
                # Find extracted CAB files
                cab_files = list(temp_path.glob("*.cab"))
                if not cab_files:
                    self.logger.error("No CAB files found after extraction")
                    return
                
                # Extract d3dcompiler_43.dll from CAB files
                for cab_file in cab_files:
                    extract_cmd = [
                        "cabextract", "-d", str(winetricks_cache_dir), "-L", "-F", "d3dcompiler_43.dll", 
                        str(cab_file)
                    ]
                    
                    extract_result = subprocess.run(extract_cmd, capture_output=True, text=True, timeout=30)
                    if extract_result.returncode == 0:
                        self.logger.info(f"Extracted d3dcompiler_43.dll to {winetricks_cache_dir}")
                        break
                else:
                    self.logger.error("Failed to extract d3dcompiler_43.dll from any CAB file")
                    
        except Exception as e:
            self.logger.error(f"Failed to extract d3dcompiler_43 from DirectX: {e}")

    def _install_proton_dependencies_self_contained(self, game: Dict[str, str]) -> Dict[str, Any]:
        """Install Proton dependencies using only bundled winetricks + Proton (no protontricks)"""
        self.logger.info(f"*** SELF-CONTAINED: Installing dependencies for {game.get('Name')} (AppID: {game.get('AppID')}) ***")

        # Use the same comprehensive dependency list as before
        # Note: fontsmooth=rgb is handled via registry settings, not winetricks
        comprehensive_dependencies = [
            "xact",
            "xact_x64",
            "vcrun2022",
            "dotnet6",
            "dotnet7",
            "dotnet8",
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
        """Install dependencies using appropriate method based on settings (Wine or Proton)"""
        self.logger.info(f"*** SELF-CONTAINED: Installing {game_type} dependencies for {game.get('Name')} ***")

        # Check settings to determine Wine or Proton preference
        try:
            from utils.settings_manager import SettingsManager
            settings = SettingsManager()
            preferred_version = settings.get_preferred_proton_version()

            # Check if it's Wine (including Wine-TKG)
            if preferred_version in ["Wine", "Wine-TKG"]:
                self.logger.info(f"*** Using Wine for {game_type} installation ***")
                wine_path = settings.get_wine_path()
                if wine_path and os.path.exists(wine_path):
                    return self._install_dependencies_with_wine(game, dependencies, wine_path, game_type)
                else:
                    return {
                        "success": False,
                        "error": "Wine not found. Please install Wine or Proton.",
                        "method": "wine_not_found"
                    }
            else:
                # Use Proton (including Heroic Proton)
                self.logger.info(f"*** Using Proton for {game_type} installation ***")
                proton_wine_bin = self._get_heroic_wine_binary_for_steam()
                if not proton_wine_bin:
                    return {
                        "success": False,
                        "error": "No Proton installation found. Please install Proton through Steam first.",
                        "method": "self_contained_no_proton"
                    }

                self.logger.info(f"*** FOUND PROTON: {proton_wine_bin} ***")
                return self._install_dependencies_with_heroic(game, dependencies, proton_wine_bin, game_type)

        except Exception as e:
            self.logger.error(f"Failed to determine installation method: {e}")
            # Fallback to Proton method
            proton_wine_bin = self._get_heroic_wine_binary_for_steam()
            if proton_wine_bin:
                return self._install_dependencies_with_heroic(game, dependencies, proton_wine_bin, game_type)
            else:
                return {
                    "success": False,
                    "error": "Could not determine Wine or Proton installation method.",
                    "method": "method_detection_failed"
                }

    def _install_dependencies_with_wine(self, game: Dict[str, str], dependencies: List[str], wine_path: str, game_type: str) -> Dict[str, Any]:
        """Install dependencies using Wine directly (not through Proton)"""
        try:
            self.logger.info(f"Installing {game_type} dependencies using Wine: {wine_path}")

            # Set up Wine environment
            env = os.environ.copy()
            env["WINE"] = wine_path
            env["XDG_RUNTIME_DIR"] = "/tmp"
            env["DISPLAY"] = ":0"
            
            # Set Wine prefix to the game's prefix path
            if game.get('prefix_path'):
                env["WINEPREFIX"] = game['prefix_path']
                self.logger.info(f"Setting WINEPREFIX to: {game['prefix_path']}")
            else:
                self.logger.warning("No prefix path found for game, using default Wine prefix")

            # Get bundled winetricks command
            winetricks_cmd = self._get_winetricks_command()
            if not winetricks_cmd:
                return {
                    "success": False,
                    "error": "Winetricks not found - cannot install dependencies",
                    "method": "wine_winetricks_missing"
                }

            # Install dependencies using Wine + winetricks (quiet mode)
            cmd = [winetricks_cmd, "-q"] + dependencies

            self.logger.info(f"*** WINE INSTALL START ***")
            self.logger.info(f"*** WINEPREFIX: {env.get('WINEPREFIX')}")
            self.logger.info(f"*** WINE: {env.get('WINE')}")
            self.logger.info(f"*** Command: {' '.join(cmd)}")
            self.logger.info(f"*** Dependencies: {dependencies}")
            
            # Log full environment for debugging
            for key in ['WINE', 'WINEPREFIX', 'XDG_RUNTIME_DIR', 'DISPLAY']:
                self.logger.info(f"*** ENV {key}: {env.get(key, 'NOT SET')}")
            
            result_cmd = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
            
            self.logger.info(f"*** WINETRICKS FINISHED ***")
            self.logger.info(f"*** EXIT CODE: {result_cmd.returncode}")
            self.logger.info(f"*** STDOUT LENGTH: {len(result_cmd.stdout)} chars")
            self.logger.info(f"*** STDERR LENGTH: {len(result_cmd.stderr)} chars")

            # Log stdout/stderr in chunks to avoid truncation
            if result_cmd.stdout:
                stdout_lines = result_cmd.stdout.split('\n')
                self.logger.info(f"*** STDOUT ({len(stdout_lines)} lines):")
                for i, line in enumerate(stdout_lines[:50]):  # First 50 lines
                    self.logger.info(f"*** STDOUT[{i}]: {line}")
                if len(stdout_lines) > 50:
                    self.logger.info(f"*** (... {len(stdout_lines) - 50} more lines)")
            
            if result_cmd.stderr:
                stderr_lines = result_cmd.stderr.split('\n')
                self.logger.warning(f"*** STDERR ({len(stderr_lines)} lines):")
                for i, line in enumerate(stderr_lines[:50]):  # First 50 lines
                    self.logger.warning(f"*** STDERR[{i}]: {line}")
                if len(stderr_lines) > 50:
                    self.logger.warning(f"*** (... {len(stderr_lines) - 50} more lines)")

            if result_cmd.returncode == 0:
                self.logger.info(f"Dependencies installed successfully using Wine for {game.get('Name')}")
                return {
                    "success": True,
                    "message": f"Dependencies installed for {game.get('Name')} using Wine",
                    "method": "wine_direct"
                }
            else:
                self.logger.warning(f"Wine installation returned non-zero exit code: {result_cmd.returncode}")
                return {
                    "success": False,
                    "error": f"Wine dependency installation failed: {result_cmd.stderr}",
                    "method": "wine_failed"
                }

        except subprocess.TimeoutExpired:
            self.logger.error(f"Wine installation timed out after 10 minutes")
            return {
                "success": False,
                "error": "Wine dependency installation timed out after 10 minutes",
                "method": "wine_timeout"
            }
        except Exception as e:
            self.logger.error(f"Failed to install Wine dependencies: {e}")
            return {
                "success": False,
                "error": f"Failed to install Wine dependencies: {e}",
                "method": "wine_error"
            }

    def _apply_wine_registry_settings_self_contained(self, app_id: str, output_lines: list) -> bool:
        """Apply Wine registry settings using appropriate method based on settings"""
        try:
            self.logger.info(f"*** SELF-CONTAINED REGISTRY: Applying settings for AppID: {app_id} ***")

            # Check settings to determine Wine or Proton preference
            try:
                from utils.settings_manager import SettingsManager
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
                return True
            else:
                self.logger.error(f"Proton registry application failed: {result.returncode}")
                return False

        except Exception as e:
            self.logger.error(f"Proton registry application error: {e}")
            return False


    def _install_dependencies_with_list(self, game: Dict[str, str], protontricks_cmd: str, dependencies: List[str], game_type: str) -> Dict[str, Any]:
        """Install dependencies with bundled winetricks + Proton (the only supported method)"""
        self.logger.info(f"Installing {game_type} dependencies for {game.get('Name')} (AppID: {game.get('AppID')})")

        # Use bundled winetricks + Proton (the standard and only method)
        self.logger.info("═══════════════════════════════════════════════════════════════")
        self.logger.info("BUNDLED WINETRICKS + PROTON INSTALLATION")
        self.logger.info("═══════════════════════════════════════════════════════════════")
        self.logger.info(f"TARGET: {game.get('Name')} (AppID: {game.get('AppID')})")
        self.logger.info("Looking for Proton binaries for bundled winetricks installation...")
        heroic_wine_bin = self._get_heroic_wine_binary_for_steam()
        self.logger.info(f"Proton binary search result: {heroic_wine_bin}")

        if heroic_wine_bin:
            self.logger.info("*** BUNDLED WINETRICKS + PROTON METHOD AVAILABLE ***")
            self.logger.info(f"Using Proton binary: {heroic_wine_bin}")
            self.logger.info(f"Installing {game_type} dependencies with BUNDLED WINETRICKS + PROTON")
            self.logger.info("Using our own bundled winetricks (no external dependencies)")
            self.logger.info("This is the standard method - self-contained and reliable")
            self.logger.info("═══════════════════════════════════════════════════════════════")

            self._log_progress(f"*** USING BUNDLED WINETRICKS + PROTON for {game_type} installation ***")
            self._log_progress("Using bundled winetricks - no external dependencies!")
            return self._install_dependencies_with_heroic(game, dependencies, heroic_wine_bin, game_type)
        else:
            # No Proton found - this is an error, no fallback to protontricks
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error("BUNDLED WINETRICKS METHOD NOT AVAILABLE - NO PROTON FOUND")
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error("No Proton binaries found in Steam directory")
            self.logger.error("Please install Proton through Steam first")

            self._log_progress("*** ERROR: No Proton installation found ***")
            self._log_progress("Please install Proton through Steam and try again")

            return {
                "success": False,
                "error": "No Proton installation found. Please install Proton through Steam first.",
                "method": "no_proton_found"
            }
    

    def install_dotnet9_sdk(self, game_app_id: str, progress_callback=None) -> bool:
        """Install .NET 9 SDK using appropriate method based on settings (Wine or Proton)"""
        self.logger.info(f"DOTNET INSTALLER: Starting .NET 9 SDK installation for AppID: {game_app_id}")
        self._log_progress("DOTNET INSTALLER: Downloading .NET 9 SDK installer...")

        try:
            # Check settings to determine Wine or Proton preference
            try:
                from utils.settings_manager import SettingsManager
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
        """Get Proton's Wine binary for use with Steam games"""
        try:
            # Use Proton Experimental's proton file for Heroic games (more universal)
            steam_root = self.steam_utils.get_steam_root()
            self.logger.info(f"Looking for Proton binaries in Steam root: {steam_root}")
            
            if not steam_root:
                self.logger.warning("Steam root not found")
                return None
            
            from pathlib import Path
            proton_paths = [
                Path(steam_root) / "steamapps" / "common" / "Proton - Experimental" / "proton",
                Path(steam_root) / "steamapps" / "common" / "Proton 9.0" / "proton",
                Path(steam_root) / "steamapps" / "common" / "Proton 8.0" / "proton",
                Path(steam_root) / "steamapps" / "common" / "Proton 7.0" / "proton"
            ]
            
            self.logger.info(f"Checking {len(proton_paths)} Proton paths...")
            for i, proton_path in enumerate(proton_paths, 1):
                self.logger.info(f"   {i}/{len(proton_paths)}: Checking {proton_path}")
                if proton_path.exists():
                    self.logger.info(f"Found Heroic-style Wine binary for Steam: {proton_path}")
                    return str(proton_path)
                else:
                    self.logger.debug(f"Not found: {proton_path}")
            
            self.logger.warning("No Proton binaries found in Steam directory")
            return None
            
        except Exception as e:
            self.logger.error(f"Could not determine Heroic Wine binary for Steam: {e}")
            return None

    def _install_dependencies_with_heroic(self, game: Dict[str, str], dependencies: List[str], wine_bin: str, game_type: str) -> Dict[str, Any]:
        """Install dependencies using bundled winetricks + Proton (standard method)"""
        try:
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("BUNDLED WINETRICKS INSTALLATION STARTING")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"Installing {game_type} dependencies for: {game.get('Name')}")
            self.logger.info(f"Method: Bundled winetricks + Proton wine binary")
            self.logger.info(f"Advantage: Self-contained, no external dependencies required")

            # Get Steam compatdata path for this game
            app_id = game.get('AppID', '')
            steam_root = self.steam_utils.get_steam_root()
            wine_prefix = f"{steam_root}/steamapps/compatdata/{app_id}/pfx"

            self.logger.info(f"Game AppID: {app_id}")
            self.logger.info(f"Steam Root: {steam_root}")
            self.logger.info(f"Wine Prefix: {wine_prefix}")

            # Set up environment like Heroic does
            env = os.environ.copy()

            # Keep APPDIR and ensure bundled tools (cabextract, etc.) are in PATH with their libraries
            # This is fully self-contained - no system dependencies needed
            appdir = os.environ.get('APPDIR')
            if appdir:
                # Set up paths for bundled binaries and libraries
                bundled_bin = os.path.join(appdir, 'usr', 'bin')
                bundled_lib = os.path.join(appdir, 'usr', 'lib')
                bundled_lib64 = os.path.join(appdir, 'usr', 'lib64')

                # Put bundled tools first in PATH so cabextract is found
                current_path = env.get('PATH', '')
                env['PATH'] = f"{bundled_bin}:{current_path}"

                # Use ONLY bundled libraries - fully self-contained AppImage
                # This allows cabextract to find libmspack.so.0 from the bundled libs
                env['LD_LIBRARY_PATH'] = f"{bundled_lib}:{bundled_lib64}"

                self.logger.info(f"Added bundled tools to PATH: {bundled_bin}")
                self.logger.info(f"Set LD_LIBRARY_PATH to bundled libs only: {env['LD_LIBRARY_PATH']}")
            else:
                # Not running from AppImage - remove any existing LD_LIBRARY_PATH to use system libs
                env.pop('LD_LIBRARY_PATH', None)

            env["WINEPREFIX"] = wine_prefix
            env["WINEARCH"] = "win64"

            # Set Steam compatibility environment variables (like Proton does)
            env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = steam_root
            env['STEAM_COMPAT_DATA_PATH'] = f"{steam_root}/steamapps/compatdata/{app_id}"

            # Set WINE environment variable to Proton's Wine binary
            # Proton's Wine binary is inside the Proton directory
            proton_dir = os.path.dirname(wine_bin)
            proton_wine = os.path.join(proton_dir, "files", "bin", "wine")
            if not os.path.exists(proton_wine):
                # Fallback to wine64
                proton_wine = os.path.join(proton_dir, "files", "bin", "wine64")

            env["WINE"] = proton_wine

            # Set winetricks cache to use our NaK cache directory
            nak_cache_dir = str(self.cache_manager.cache_dir)
            env["W_CACHE"] = nak_cache_dir
            self.logger.info(f"Using NaK cache directory: {nak_cache_dir}")

            # Pre-populate winetricks cache with our cached files
            self._populate_winetricks_cache(dependencies)

            self.logger.info(f"Proton Directory: {proton_dir}")
            self.logger.info(f"Wine Binary: {proton_wine}")
            self.logger.info(f"Wine Arch: win64")

            # Get bundled winetricks command
            winetricks_cmd = self._get_winetricks_command()
            if not winetricks_cmd:
                self.logger.error("Winetricks not found - cannot install dependencies")
                return {
                    "success": False,
                    "error": "Winetricks not found",
                    "method": "heroic_winetricks_missing"
                }

            # Call winetricks directly (it will use the WINE environment variable)
            cmd = [winetricks_cmd, "-q"] + dependencies

            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info("DEPENDENCY INSTALLATION DETAILS")
            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info(f"Target Game: {game.get('Name')} ({game_type})")
            self.logger.info(f"Command: {' '.join(cmd)}")
            self.logger.info(f"Dependencies Count: {len(dependencies)}")

            # Log each dependency being installed
            self.logger.info("Dependencies to install:")
            for i, dep in enumerate(dependencies, 1):
                self.logger.info(f"   {i:2d}/{len(dependencies)}: {dep}")

            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info("STARTING BUNDLED WINETRICKS INSTALLATION...")
            self.logger.info("This may take several minutes - please be patient...")
            self.logger.info("───────────────────────────────────────────────────────────────")

            self._log_progress("Starting winetricks installation with Proton...")
            self._log_progress(f"Installing {len(dependencies)} dependencies via winetricks + Proton")

            result_cmd = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
            
            # Log the results
            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info("BUNDLED WINETRICKS INSTALLATION RESULTS")
            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info(f"Return Code: {result_cmd.returncode}")

            if result_cmd.stdout:
                self.logger.info("Winetricks Standard Output:")
                self.logger.info(result_cmd.stdout)
            if result_cmd.stderr:
                self.logger.info("Winetricks Warnings/Errors:")
                self.logger.info(result_cmd.stderr)

            if result_cmd.returncode == 0:
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info("BUNDLED WINETRICKS + PROTON METHOD - SUCCESS!")
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info(f"Dependencies successfully installed for {game.get('Name')}")
                self.logger.info(f"Method Used: BUNDLED WINETRICKS + PROTON (no external dependencies)")
                self.logger.info(f"Self-contained installation completed successfully!")

                self._log_progress("BUNDLED WINETRICKS: All dependencies installed successfully!")
                self._log_progress(f"{game.get('Name')} dependencies ready via bundled winetricks method")

                return {
                    "success": True,
                    "message": f"Dependencies installed for {game.get('Name')} (using BUNDLED winetricks method)",
                    "method": "bundled_winetricks",
                    "output_lines": [
                        "BUNDLED WINETRICKS + PROTON METHOD SUCCESS",
                        f"Game: {game.get('Name')}",
                        f"Dependencies: {len(dependencies)} packages",
                        "Method: bundled winetricks + Proton wine binary (self-contained)",
                        "Installation completed successfully!"
                    ]
                }
            else:
                self.logger.error("═══════════════════════════════════════════════════════════════")
                self.logger.error("BUNDLED WINETRICKS INSTALLATION - FAILED!")
                self.logger.error("═══════════════════════════════════════════════════════════════")
                self.logger.error(f"Winetricks returned non-zero exit code: {result_cmd.returncode}")
                self.logger.error(f"Error output: {result_cmd.stderr}")

                self._log_progress("Installation failed - bundled winetricks returned an error")

                return {
                    "success": False,
                    "error": f"Bundled winetricks installation failed: {result_cmd.stderr}",
                    "method": "bundled_winetricks_failed"
                }

        except subprocess.TimeoutExpired:
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error("BUNDLED WINETRICKS INSTALLATION - TIMEOUT!")
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error(f"Winetricks installation timed out after 10 minutes")
            self.logger.error(f"Game: {game.get('Name')} ({game_type})")

            self._log_progress("Installation timed out after 10 minutes")

            return {
                "success": False,
                "error": "Bundled winetricks installation timed out after 10 minutes",
                "method": "bundled_winetricks_timeout"
            }
        except Exception as e:
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error("BUNDLED WINETRICKS INSTALLATION - ERROR!")
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error(f"Failed to install {game_type} dependencies with bundled winetricks: {e}")
            self.logger.error(f"Game: {game.get('Name')}")

            self._log_progress("Installation failed due to unexpected error")

            return {
                "success": False,
                "error": f"Bundled winetricks installation failed: {e}",
                "method": "bundled_winetricks_error"
            }
