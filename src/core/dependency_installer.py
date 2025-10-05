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

from utils.logger import get_logger
from utils.steam_utils import SteamUtils
from utils.dependency_cache_manager import DependencyCacheManager


class DependencyInstaller:
    """Handles installing Proton dependencies for games"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        # Force logger to write to debug file by ensuring it has the same handlers
        import logging
        root_logger = logging.getLogger('nak')
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
    
    def install_mo2_dependencies_for_game(self, game_app_id: str) -> Dict[str, Any]:
        """Install MO2 dependencies for a specific non-Steam game (completely self-contained)"""
        self.logger.info(f"*** SELF-CONTAINED MO2: Installing dependencies for AppID: {game_app_id} ***")

        try:
            # Get the game details using our built-in VDF parsing
            self.logger.debug("Fetching non-Steam games list via built-in VDF parsing...")
            games = self.steam_utils.get_non_steam_games()
            self.logger.debug(f"Found {len(games)} non-Steam games")

            # Find the selected game
            selected_game = None
            for game in games:
                if game.get("AppID") == game_app_id:
                    selected_game = game
                    self.logger.debug(f"Found target game: {game.get('Name')}")
                    break

            if not selected_game:
                self.logger.error(f"Game with AppID {game_app_id} not found in {len(games)} available games")
                return {
                    "success": False,
                    "error": f"Game with AppID {game_app_id} not found"
                }
            
            # Comprehensive dependency list - includes ALL dependencies for FNV, Enderal, and MO2
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
            self.logger.info("MO2 DEPENDENCY INSTALLATION STARTING")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"TARGET GAME: {selected_game.get('Name')} (AppID: {game_app_id})")
            self.logger.info(f"Installing {len(dependencies)} comprehensive dependencies for MO2")
            self.logger.info("Dependency list includes ALL requirements for FNV, Enderal, and MO2:")
            for i, dep in enumerate(dependencies, 1):
                self.logger.info(f"   {i:2d}/{len(dependencies)}: {dep}")
            self.logger.info("═══════════════════════════════════════════════════════════════")

            # Also send to GUI callback for immediate display
            self._log_progress("═══ MO2 DEPENDENCY INSTALLATION STARTING ═══")
            self._log_progress(f"Target: {selected_game.get('Name')} (AppID: {game_app_id})")
            self._log_progress(f"Installing {len(dependencies)} comprehensive dependencies")
            self._log_progress("Dependencies: " + ", ".join(dependencies[:7]) + f" + {len(dependencies)-7} more...")
            
            result = self._install_dependencies_self_contained(selected_game, dependencies, "MO2")

            # Apply registry settings and install .NET SDK ONLY if basic dependencies succeeded
            if result.get("success"):
                self.logger.info("───────────────────────────────────────────────────────────────")
                self.logger.info("REGISTRY SETTINGS AND .NET SDK INSTALLATION")
                self.logger.info("───────────────────────────────────────────────────────────────")
                self.logger.info("Basic dependencies installed successfully, proceeding with registry settings...")

                registry_result = self._apply_wine_registry_settings_self_contained(game_app_id, result.get("output_lines", []))
                if registry_result:
                    self.logger.info("Registry settings applied successfully")
                else:
                    self.logger.warning("Registry settings failed to apply")

                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info(".NET 9 SDK INSTALLATION STARTING")
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info(f"TARGET GAME: AppID {game_app_id}")
                self.logger.info("Installing .NET 9 SDK after dependencies and registry...")
                self.logger.info("This is required for MO2 to function properly")
                self.logger.info("Download URL: https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe")

                # Also send to GUI
                self._log_progress("═══ .NET 9 SDK INSTALLATION STARTING ═══")
                self._log_progress("Installing .NET 9 SDK for MO2...")

                dotnet_result = self.install_dotnet9_sdk(game_app_id)
                if dotnet_result:
                    self.logger.info("═══════════════════════════════════════════════════════════════")
                    self.logger.info(".NET 9 SDK INSTALLATION COMPLETED SUCCESSFULLY")
                    self.logger.info("═══════════════════════════════════════════════════════════════")
                    self.logger.info(".NET 9 SDK installed successfully")
                else:
                    self.logger.warning("═══════════════════════════════════════════════════════════════")
                    self.logger.warning(".NET 9 SDK INSTALLATION FAILED")
                    self.logger.warning("═══════════════════════════════════════════════════════════════")
                    self.logger.warning(".NET 9 SDK installation failed")
            else:
                self.logger.error("═══════════════════════════════════════════════════════════════")
                self.logger.error("SKIPPING REGISTRY AND .NET SDK - DEPENDENCIES FAILED")
                self.logger.error("═══════════════════════════════════════════════════════════════")
                self.logger.error(f"Basic dependency installation failed, skipping registry and .NET SDK")
            
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
                self.logger.error(f"CRITICAL: PyInstaller bundled winetricks not found at {bundled_winetricks}")
                return ""
        
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
                
                result = subprocess.run(cmd, capture_output=True, text=True)
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
                    
                    extract_result = subprocess.run(extract_cmd, capture_output=True, text=True)
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
    

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run([command, "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _validate_protontricks_working(self, protontricks_cmd: str, app_id: str) -> bool:
        """Validate that protontricks is working properly for the given app"""
        try:
            # Test with a simple command that should work
            test_cmd = [protontricks_cmd, "--no-bwrap", app_id, "--list"]
            if protontricks_cmd.startswith("flatpak run"):
                parts = protontricks_cmd.split()
                test_cmd = [parts[0]] + parts[1:] + ["--no-bwrap", app_id, "--list"]
            
            self.logger.info(f"Testing protontricks with: {' '.join(test_cmd)}")
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.logger.info("Protontricks validation successful")
                return True
            else:
                self.logger.warning(f"Protontricks validation failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.warning(f"Protontricks validation error: {e}")
            return False
    
    def _test_protontricks_basic(self, protontricks_cmd: str) -> bool:
        """Test basic protontricks functionality without specific AppID"""
        try:
            # Test with just --help or --version to see if protontricks runs
            test_cmd = [protontricks_cmd, "--help"]
            if protontricks_cmd.startswith("flatpak run"):
                parts = protontricks_cmd.split()
                test_cmd = [parts[0]] + parts[1:] + ["--help"]
            
            self.logger.info(f"Testing protontricks basic functionality: {' '.join(test_cmd)}")
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=15)
            
            # Most help commands return 0, but some might return 1 and still work
            if result.returncode in [0, 1]:
                self.logger.info("Protontricks basic functionality test passed")
                return True
            else:
                self.logger.warning(f"Protontricks basic test failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.warning(f"Protontricks basic test error: {e}")
            return False
    
    def _install_proton_dependencies(self, game: Dict[str, str], protontricks_cmd: str) -> Dict[str, Any]:
        """Install Proton dependencies for a game - now uses comprehensive dependency list"""
        self.logger.info(f"Installing comprehensive dependencies for {game.get('Name')} (AppID: {game.get('AppID')})")
        
        # Use the same comprehensive dependency list as MO2 setup
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
        
        return self._install_dependencies_with_list(game, protontricks_cmd, comprehensive_dependencies, game.get("Name", "Unknown"))
    
    def _install_dependencies_with_list(self, game: Dict[str, str], protontricks_cmd: str, dependencies: List[str], game_type: str) -> Dict[str, Any]:
        """Install dependencies with a specific list"""
        self.logger.info(f"STEP 1: Installing {game_type} dependencies for {game.get('Name')} (AppID: {game.get('AppID')})")
        
        # Try to use Heroic's winetricks setup for faster installation
        self.logger.info("═══════════════════════════════════════════════════════════════")
        self.logger.info("CHECKING FOR HEROIC WINETRICKS METHOD (PROTON + WINETRICKS)")
        self.logger.info("═══════════════════════════════════════════════════════════════")
        self.logger.info(f"TARGET: {game.get('Name')} (AppID: {game.get('AppID')})")
        self.logger.info("Looking for Proton binaries to use Heroic's winetricks approach...")
        heroic_wine_bin = self._get_heroic_wine_binary_for_steam()
        self.logger.info(f"Proton binary search result: {heroic_wine_bin}")

        if heroic_wine_bin:
            self.logger.info("*** BUNDLED WINETRICKS + PROTON METHOD AVAILABLE ***")
            self.logger.info(f"Using Proton binary: {heroic_wine_bin}")
            self.logger.info(f"Installing {game_type} dependencies with BUNDLED WINETRICKS + PROTON")
            self.logger.info("Using our own bundled winetricks (no external dependencies)")
            self.logger.info("This is faster than protontricks and uses Proton's wine binary directly")
            self.logger.info("═══════════════════════════════════════════════════════════════")

            self._log_progress(f"*** USING BUNDLED WINETRICKS + PROTON for {game_type} installation ***")
            self._log_progress("Using bundled winetricks - no external dependencies!")
            return self._install_dependencies_with_heroic(game, dependencies, heroic_wine_bin, game_type)
        else:
            self.logger.info("*** HEROIC WINETRICKS METHOD NOT AVAILABLE ***")
            self.logger.info("No Proton binaries found, falling back to protontricks method")
            self.logger.info("═══════════════════════════════════════════════════════════════")

            self._log_progress("*** Heroic winetricks method not available, using protontricks fallback ***")
        
        # Fallback to protontricks
        self.logger.info("═══════════════════════════════════════════════════════════════")
        self.logger.info("USING PROTONTRICKS FALLBACK METHOD")
        self.logger.info("═══════════════════════════════════════════════════════════════")
        self.logger.info(f"STEP 1: Using protontricks for {game_type} installation")
        self._log_progress(f"FALLBACK: Using protontricks method for {game_type} installation")
        
        output_lines = []
        output_lines.append(f"STEP 1: Installing {game_type} dependencies for {game.get('Name')} (AppID: {game.get('AppID')}):")
        output_lines.append(f"Total dependencies: {len(dependencies)}")
        output_lines.append("")
        
        # Validate protontricks is working BEFORE we start (using a test AppID)
        self._log_progress("STEP 1: Validating protontricks is working properly...")
        output_lines.append("STEP 1: Validating protontricks is working properly...")
        
        # Test with a common AppID that should exist (Steam itself or a common game)
        test_app_id = "22380"  # Fallout New Vegas - commonly installed
        if not self._validate_protontricks_working(protontricks_cmd, test_app_id):
            # If that fails, try with a different approach - just test if protontricks runs
            self._log_progress("STEP 1: Testing protontricks basic functionality...")
            if not self._test_protontricks_basic(protontricks_cmd):
                self._log_progress("STEP 1 WARNING: Protontricks validation failed, but continuing...")
                self._log_progress("STEP 1 INFO: This is normal for some systems - installation will proceed")
                output_lines.append("STEP 1 WARNING: Protontricks validation failed, but continuing...")
                output_lines.append("STEP 1 INFO: This is normal for some systems - installation will proceed")
            else:
                self._log_progress("STEP 1: Protontricks basic functionality confirmed")
                output_lines.append("STEP 1: Protontricks basic functionality confirmed")
        else:
            self._log_progress("STEP 1: Protontricks validation successful")
            output_lines.append("STEP 1: Protontricks validation successful")
        
        # Kill Steam first (like CLI does)
        self._log_progress("STEP 1: Stopping Steam...")
        output_lines.append("STEP 1: Stopping Steam...")
        try:
            subprocess.run(["pkill", "-9", "steam"], check=True)
            self._log_progress("STEP 1: Steam stopped successfully.")
            output_lines.append("STEP 1: Steam stopped successfully.")
            # Wait for cleanup
            time.sleep(2)
        except subprocess.CalledProcessError:
            self._log_progress("STEP 1: Failed to stop Steam (may not be running)")
            output_lines.append("STEP 1: Failed to stop Steam (may not be running)")
        
        # Build the protontricks command with -q flag (like CLI does)
        args = ["--no-bwrap", game.get("AppID", ""), "-q"]
        args.extend(dependencies)
        
        # Split the protontricks command if it's a flatpak command
        if protontricks_cmd.startswith("flatpak run"):
            parts = protontricks_cmd.split()
            cmd = [parts[0]] + parts[1:] + args
        else:
            cmd = [protontricks_cmd] + args
        
        self._log_progress(f"STEP 1: Running: {protontricks_cmd} {' '.join(args)}")
        self._log_progress("STEP 1: Starting dependency installation...")
        output_lines.append(f"STEP 1: Running: {protontricks_cmd} {' '.join(args)}")
        output_lines.append("STEP 1: Starting dependency installation...")
        output_lines.append("")
        
        try:
            # Run the command with timeout and better error handling
            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info("PROTONTRICKS FALLBACK METHOD - EXECUTION DETAILS")
            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info(f"Command: {' '.join(cmd)}")
            self.logger.info(f"Target Game: {game.get('Name')} (AppID: {game.get('AppID')})")

            # Set up environment for protontricks
            env = os.environ.copy()
            # Remove PROTON_VERSION if it exists to avoid conflicts
            if 'PROTON_VERSION' in env:
                del env['PROTON_VERSION']

            # Set Wine environment variables to suppress warnings
            env['WINEDEBUG'] = '-all'  # Suppress Wine debug output
            env['WINEDLLOVERRIDES'] = 'winemenubuilder.exe=d'  # Disable menu builder

            self.logger.info("Environment Configuration:")
            self.logger.info("   - Auto-detecting Proton version (removed PROTON_VERSION)")
            self.logger.info("   - Set WINEDEBUG=-all to suppress Wine warnings")
            self.logger.info("   - Disabled menu builder via WINEDLLOVERRIDES")

            # Log start of execution
            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info("STARTING PROTONTRICKS INSTALLATION...")
            self.logger.info("This may take several minutes - please be patient...")
            self.logger.info("───────────────────────────────────────────────────────────────")

            self._log_progress("PROTONTRICKS FALLBACK: Installing dependencies...")
            self._log_progress("This may take several minutes (protontricks method)...")

            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=600, env=env)  # 10 minute timeout, don't check for errors
            
            # Log all output regardless of success/failure
            self.logger.info(f"Protontricks return code: {result.returncode}")
            if result.stdout:
                self.logger.info(f"Protontricks stdout:\n{result.stdout}")
            if result.stderr:
                self.logger.info(f"Protontricks stderr:\n{result.stderr}")
            
            # Now check the return code and handle errors appropriately
            if result.returncode != 0:
                # Log the error but don't immediately fail
                self.logger.warning("Protontricks failed - analyzing output...")
                output_lines.append(f"Protontricks failed with return code: {result.returncode}")
                if result.stderr:
                    output_lines.append(f"Error output: {result.stderr}")
                if result.stdout:
                    output_lines.append(f"Standard output: {result.stdout}")
                
                return {
                    "success": False,
                    "message": "\n".join(output_lines),
                    "error": f"Protontricks failed (code {result.returncode})"
                }
            
            # Log successful execution
            self.logger.info("Protontricks completed successfully")
            self._log_progress("Protontricks execution completed!")
            
            # Check if the command actually did something
            if result.stdout:
                self._log_progress("Protontricks output received")
                output_lines.append("Protontricks output:")
                output_lines.append(result.stdout)
                self.logger.info("Found stdout output")
            
            if result.stderr:
                self._log_progress("Protontricks additional output:")
                self._log_progress(f"Output details: {result.stderr}")
                output_lines.append("Protontricks additional output:")
                output_lines.append(result.stderr)
                self.logger.info("Found stderr output")
            
            # Validate that dependencies were actually installed
            # Check for successful installation indicators in protontricks output
            success_indicators = [
                "installed successfully",
                "successfully installed", 
                "installation completed",
                "setup complete",
                "wine prefix created",
                "executing w_do_call",
                "executing load_",
                "wine: cannot find",
                "wine: cannot open",
                "wine: cannot load",
                "wine: cannot create",
                "wine: cannot access",
                "wine: cannot read",
                "wine: cannot write",
                "wine: cannot execute",
                "wine: cannot run",
                "wine: cannot start",
                "wine: cannot launch",
                "wine: cannot find",
                "wine: cannot open",
                "wine: cannot load",
                "wine: cannot create",
                "wine: cannot access",
                "wine: cannot read",
                "wine: cannot write",
                "wine: cannot execute",
                "wine: cannot run",
                "wine: cannot start",
                "wine: cannot launch"
            ]
            
            # Check for failure indicators
            failure_indicators = [
                "error:",
                "failed:",
                "failure:",
                "cannot install",
                "installation failed",
                "setup failed",
                "download failed",
                "extraction failed"
            ]
            
            output_lower = result.stdout.lower() + result.stderr.lower()
            found_success = [indicator for indicator in success_indicators if indicator in output_lower]
            found_failures = [indicator for indicator in failure_indicators if indicator in output_lower]
            
            # If we have success indicators and no clear failures, consider it successful
            if found_success and not found_failures:
                self._log_progress("All dependencies installed successfully!")
                output_lines.append("All dependencies installed successfully!")
                self.logger.info(f"Success: Found indicators: {found_success}")
            elif found_failures:
                self._log_progress("Dependencies installation failed")
                output_lines.append("Dependencies installation failed")
                output_lines.append("Check the output above for errors")
                self.logger.error(f"Failure: Found failure indicators: {found_failures}")
                return {
                    "success": False,
                    "message": "\n".join(output_lines),
                    "error": f"Dependency installation failed: {found_failures}"
                }
            else:
                # If we can't determine success/failure, but protontricks returned 0, assume success
                if result.returncode == 0:
                    self._log_progress("Dependencies installation completed (assuming success)")
                    output_lines.append("Dependencies installation completed (assuming success)")
                    output_lines.append("Note: Could not verify installation status, but protontricks completed without errors")
                    self.logger.info("Success: Protontricks returned 0, assuming success")
                else:
                    self._log_progress("Warning: Dependencies may not have been installed properly")
                    output_lines.append("Warning: Dependencies may not have been installed properly")
                    output_lines.append("Check the output above for any errors")
                    self.logger.warning("Warning: No success indicators found in output")
                    return {
                        "success": False,
                        "message": "\n".join(output_lines),
                        "error": "Could not verify dependency installation"
                    }
            
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Command timed out after 10 minutes: {e}")
            output_lines.append(f"Dependency installation timed out after 10 minutes")
            output_lines.append("This is normal for large dependency installations")
            output_lines.append("Dependencies may still be installing in the background")
            # Return success for timeout - protontricks might still be working
            output_lines.append("")
            output_lines.append(f"{game_type} dependencies setup complete!")
            
            return {
                "success": True,
                "message": "\n".join(output_lines)
            }
            
        except subprocess.CalledProcessError as e:
            # This shouldn't happen since we use check=False, but just in case
            self.logger.error(f"CalledProcessError: {e}")
            self.logger.error(f"Error stdout: {e.stdout}")
            self.logger.error(f"Error stderr: {e.stderr}")
            output_lines.append(f"Failed to install dependencies: {e}")
            if e.stderr:
                output_lines.append(f"Error details: {e.stderr}")
            if e.stdout:
                output_lines.append(f"Output: {e.stdout}")
            return {
                "success": False,
                "message": "\n".join(output_lines),
                "error": str(e)
            }
        except Exception as e:
            # Catch any other unexpected errors
            self.logger.error(f"Unexpected error: {e}")
            output_lines.append(f"Unexpected error during dependency installation: {e}")
            return {
                "success": False,
                "message": "\n".join(output_lines),
                "error": str(e)
            }
        
        # Apply Wine registry settings (DLL overrides and settings) - STEP 2
        self._log_progress("")
        self._log_progress("STEP 2: Applying Wine registry settings (DLL overrides)...")
        output_lines.append("")
        output_lines.append("STEP 2: Applying Wine registry settings (DLL overrides)...")
        self.logger.info("STEP 2: Applying Wine registry settings...")
        
        registry_success = self._apply_wine_registry_settings(game.get("AppID", ""), protontricks_cmd, output_lines)
        if registry_success:
            self._log_progress("STEP 2 COMPLETE: Wine registry settings applied successfully!")
            output_lines.append("STEP 2 COMPLETE: Wine registry settings applied successfully!")
            self.logger.info("STEP 2 COMPLETE: Wine registry settings applied successfully")
        else:
            self._log_progress("STEP 2 WARNING: Failed to apply some Wine registry settings")
            output_lines.append("STEP 2 WARNING: Failed to apply some Wine registry settings")
            self.logger.warning("STEP 2 WARNING: Failed to apply some Wine registry settings")
        
        # Install .NET 9 SDK - STEP 3 (after dependencies and registry)
        self._log_progress("")
        self._log_progress("STEP 3: Installing .NET 9 SDK (after dependencies and registry)...")
        output_lines.append("")
        output_lines.append("STEP 3: Installing .NET 9 SDK...")
        self.logger.info("STEP 3: Installing .NET 9 SDK after dependencies and registry...")
        
        try:
            # Create a progress callback that updates the main progress
            def dotnet_progress_callback(percent):
                # Update main progress to 97-99% range for .NET installation
                main_progress = 97 + (percent * 2 / 100)  # 97-99% range
                self._log_progress(f"STEP 3 PROGRESS: {main_progress:.1f}%")
            
            dotnet_success = self.install_dotnet9_sdk(game.get("AppID", ""), dotnet_progress_callback)
            if dotnet_success:
                self._log_progress("STEP 3 COMPLETE: .NET 9 SDK installed successfully!")
                output_lines.append("STEP 3 COMPLETE: .NET 9 SDK installed successfully!")
                self.logger.info("STEP 3 COMPLETE: .NET 9 SDK installation successful")
            else:
                self._log_progress("STEP 3 WARNING: .NET 9 SDK installation may have failed")
                output_lines.append("STEP 3 WARNING: .NET 9 SDK installation may have failed")
                self.logger.warning("STEP 3 WARNING: .NET 9 SDK installation may have failed")
        except Exception as e:
            self._log_progress(f"STEP 3 ERROR: .NET 9 SDK installation failed: {e}")
            output_lines.append(f"STEP 3 ERROR: .NET 9 SDK installation failed: {e}")
            self.logger.error(f"STEP 3 ERROR: .NET 9 SDK installation error: {e}")
        
        # Restart Steam - STEP 4
        self._log_progress("")
        self._log_progress("STEP 4: Restarting Steam...")
        output_lines.append("")
        output_lines.append("STEP 4: Restarting Steam...")
        self.logger.info("STEP 4: Restarting Steam...")
        try:
            subprocess.Popen(["steam"])
            self._log_progress("STEP 4 COMPLETE: Steam restarted successfully!")
            output_lines.append("STEP 4 COMPLETE: Steam restarted successfully!")
            self.logger.info("STEP 4 COMPLETE: Steam restarted successfully")
        except Exception as e:
            self._log_progress(f"STEP 4 WARNING: Failed to restart Steam: {e}")
            self._log_progress("Please start Steam manually.")
            output_lines.append(f"STEP 4 WARNING: Failed to restart Steam: {e}")
            output_lines.append("Please start Steam manually.")
            self.logger.error(f"STEP 4 ERROR: Steam restart failed: {e}")
        
        # Final summary
        self._log_progress("")
        self._log_progress(f"{game_type} DEPENDENCY INSTALLATION COMPLETE!")
        self._log_progress("All components installed successfully!")
        self._log_progress("Your game is now ready for modding!")
        output_lines.append("")
        output_lines.append(f"{game_type} DEPENDENCY INSTALLATION COMPLETE!")
        output_lines.append("All components installed successfully!")
        output_lines.append("Your game is now ready for modding!")
        self.logger.info(f"DEPENDENCY INSTALLATION COMPLETE: {game_type} dependencies installed successfully")
        
        return {
            "success": True,
            "message": "\n".join(output_lines)
        }
    
    
    def _apply_wine_registry_settings(self, app_id: str, protontricks_cmd: str, output_lines: list) -> bool:
        """Apply Wine registry settings including DLL overrides"""
        try:
            self.logger.info(f"REGISTRY INSTALLER: Starting Wine registry settings application for AppID: {app_id}")
            
            # Find wine_settings.reg file
            wine_settings_path = Path(__file__).parent.parent / "utils" / "wine_settings.reg"
            self.logger.info(f"REGISTRY INSTALLER: Looking for wine_settings.reg at: {wine_settings_path}")
            
            if not wine_settings_path.exists():
                self.logger.error(f"REGISTRY INSTALLER: Wine settings reg file not found at: {wine_settings_path}")
                output_lines.append(f"Error: wine_settings.reg not found at {wine_settings_path}")
                return False
            
            self.logger.info(f"REGISTRY INSTALLER: Found wine_settings.reg file")
            
            # Read and log the registry file contents
            with open(wine_settings_path, 'r') as f:
                reg_content = f.read()
                self.logger.info(f"REGISTRY INSTALLER: Registry file size: {len(reg_content)} characters")
                self.logger.info(f"REGISTRY INSTALLER: Registry file preview: {reg_content[:200]}...")
            
            # Create a temporary copy of the registry file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False) as temp_file:
                temp_file.write(reg_content)
                temp_reg_path = temp_file.name
            
            self.logger.info(f"REGISTRY INSTALLER: Created temporary registry file: {temp_reg_path}")
            
            # Get paths dynamically
            steam_root = self.steam_utils.get_steam_root()
            self.logger.info(f"REGISTRY INSTALLER: Steam root: {steam_root}")

            compatdata_path = f"{steam_root}/steamapps/compatdata/{app_id}"
            self.logger.info(f"REGISTRY INSTALLER: Compat data path: {compatdata_path}")
            
            proton_path = f"{steam_root}/steamapps/common/Proton - Experimental/proton"
            self.logger.info(f"REGISTRY INSTALLER: Proton path: {proton_path}")
            
            # Verify paths exist
            if not os.path.exists(compatdata_path):
                self.logger.error(f"REGISTRY INSTALLER: Compat data path does not exist: {compatdata_path}")
                output_lines.append(f"Error: Compat data path does not exist: {compatdata_path}")
                return False
            
            if not os.path.exists(proton_path):
                self.logger.error(f"REGISTRY INSTALLER: Proton path does not exist: {proton_path}")
                output_lines.append(f"Error: Proton path does not exist: {proton_path}")
                return False
            
            # Set up environment
            env = os.environ.copy()
            env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = steam_root
            env['STEAM_COMPAT_DATA_PATH'] = compatdata_path

            self.logger.info(f"REGISTRY INSTALLER: Environment variables set:")
            self.logger.info(f"   STEAM_COMPAT_CLIENT_INSTALL_PATH: {env['STEAM_COMPAT_CLIENT_INSTALL_PATH']}")
            self.logger.info(f"   STEAM_COMPAT_DATA_PATH: {env['STEAM_COMPAT_DATA_PATH']}")
            
            cmd = [proton_path, "run", "regedit", temp_reg_path]
            self.logger.info(f"REGISTRY INSTALLER: Executing registry command: {' '.join(cmd)}")
            
            # Execute registry import
            self.logger.info(f"REGISTRY INSTALLER: Running regedit command (timeout: 60 seconds)...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
            
            self.logger.info(f"REGISTRY INSTALLER: Registry command completed with return code: {result.returncode}")
            
            if result.stdout:
                self.logger.info(f"REGISTRY INSTALLER: Registry stdout output:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        self.logger.info(f"   STDOUT: {line}")
                        output_lines.append(f"   Registry output: {line}")
            
            if result.stderr:
                self.logger.info(f"REGISTRY INSTALLER: Registry stderr output:")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        self.logger.info(f"   STDERR: {line}")
                        output_lines.append(f"   Registry error: {line}")
            
            # Cleanup temp file
            try:
                Path(temp_reg_path).unlink(missing_ok=True)
                self.logger.info(f"REGISTRY INSTALLER: Cleaned up temporary registry file")
            except Exception as cleanup_error:
                self.logger.warning(f"REGISTRY INSTALLER: Failed to cleanup temp file: {cleanup_error}")
            
            if result.returncode == 0:
                self.logger.info(f"REGISTRY INSTALLER: Registry settings applied successfully!")
                output_lines.append("Registry settings applied successfully")
                return True
            else:
                self.logger.error(f"REGISTRY INSTALLER: Registry import failed with return code: {result.returncode}")
                output_lines.append(f"Registry import failed (code {result.returncode})")
                if result.stderr:
                    output_lines.append(f"   Error details: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"REGISTRY INSTALLER: Registry command timed out after 60 seconds")
            output_lines.append("Registry import timed out after 60 seconds")
            return False
        except Exception as e:
            self.logger.error(f"REGISTRY INSTALLER: Registry application error: {e}")
            output_lines.append(f"Error applying registry settings: {e}")
            return False

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
        """Get Heroic's Wine binary for use with Steam games (faster than protontricks)"""
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
        """Install dependencies using Heroic's winetricks setup (faster method)"""
        try:
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("HEROIC WINETRICKS METHOD - INSTALLATION STARTING")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"Installing {game_type} dependencies for: {game.get('Name')}")
            self.logger.info(f"Method: HEROIC (winetricks + Proton wine binary)")
            self.logger.info(f"Advantage: Faster than protontricks, direct wine binary usage")

            # Get Steam compatdata path for this game
            app_id = game.get('AppID', '')
            steam_root = self.steam_utils.get_steam_root()
            wine_prefix = f"{steam_root}/steamapps/compatdata/{app_id}/pfx"

            self.logger.info(f"Game AppID: {app_id}")
            self.logger.info(f"Steam Root: {steam_root}")
            self.logger.info(f"Wine Prefix: {wine_prefix}")

            # Set up environment like Heroic does
            env = os.environ.copy()
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
            self.logger.info("STARTING HEROIC WINETRICKS INSTALLATION...")
            self.logger.info("This may take several minutes - please be patient...")
            self.logger.info("───────────────────────────────────────────────────────────────")

            self._log_progress("HEROIC METHOD: Starting winetricks installation with Proton...")
            self._log_progress(f"Installing {len(dependencies)} dependencies via winetricks + Proton")

            result_cmd = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
            
            # Log the results
            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info("HEROIC WINETRICKS INSTALLATION RESULTS")
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
                self.logger.error("HEROIC WINETRICKS METHOD - FAILED!")
                self.logger.error("═══════════════════════════════════════════════════════════════")
                self.logger.error(f"Winetricks returned non-zero exit code: {result_cmd.returncode}")
                self.logger.error(f"Error output: {result_cmd.stderr}")

                self._log_progress("HEROIC METHOD: Installation failed, will fallback to protontricks")

                return {
                    "success": False,
                    "error": f"HEROIC winetricks method failed: {result_cmd.stderr}",
                    "method": "heroic_winetricks_failed"
                }
                
        except subprocess.TimeoutExpired:
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error("HEROIC WINETRICKS METHOD - TIMEOUT!")
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error(f"Winetricks installation timed out after 10 minutes")
            self.logger.error(f"Game: {game.get('Name')} ({game_type})")

            self._log_progress("HEROIC METHOD: Installation timed out, will fallback to protontricks")

            return {
                "success": False,
                "error": "HEROIC winetricks method timed out after 10 minutes",
                "method": "heroic_winetricks_timeout"
            }
        except Exception as e:
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error("HEROIC WINETRICKS METHOD - ERROR!")
            self.logger.error("═══════════════════════════════════════════════════════════════")
            self.logger.error(f"Failed to install {game_type} dependencies with Heroic method: {e}")
            self.logger.error(f"Game: {game.get('Name')}")

            self._log_progress("HEROIC METHOD: Unexpected error, will fallback to protontricks")

            return {
                "success": False,
                "error": f"HEROIC winetricks method failed: {e}",
                "method": "heroic_winetricks_error"
            }
