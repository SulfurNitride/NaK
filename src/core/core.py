"""
Core business logic for NaK application
This module contains all the business logic and is framework-agnostic
"""

import logging
from typing import Dict, List, Any, Optional
from src.core.mo2_installer import MO2Installer
from src.core.dependency_installer import DependencyInstaller
from src.utils.steam_utils import SteamUtils
from src.utils.game_utils import GameUtils
from src.utils.utils import Utils
from src.utils.comprehensive_game_manager import ComprehensiveGameManager
from src.utils.settings_manager import SettingsManager

class Core:
    """Core represents the main business logic of the NaK application"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.mo2 = MO2Installer()
        self.settings = SettingsManager()

        self.deps = DependencyInstaller()
        self.steam_utils = SteamUtils()
        self.game_utils = GameUtils()
        self.utils = Utils()
        self.game_manager = ComprehensiveGameManager()

        # Start background dependency caching
        self._start_background_caching()
    
    def get_version_info(self) -> tuple[str, str]:
        """Get version information"""
        return "3.0.0", "2025-09-07"
    
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are available"""
        self.logger.info("Checking dependencies...")
        
        try:
            self.logger.info("Starting dependency check...")
            # Check for protontricks (native or flatpak)
            protontricks_cmd = ""
            if self.steam_utils.command_exists("protontricks"):
                protontricks_cmd = "protontricks"
                self.logger.info("Using native protontricks")
            elif self.steam_utils.command_exists("flatpak"):
                # Check if protontricks flatpak is installed
                try:
                    output = self.steam_utils.run_command(
                        "sh", "-c", 
                        "flatpak list --app --columns=application | grep -q com.github.Matoking.protontricks && echo 'found'"
                    )
                    if "found" in output:
                        protontricks_cmd = "flatpak run com.github.Matoking.protontricks"
                        self.logger.info("Using flatpak protontricks")
                except Exception as e:
                    self.logger.warning(f"Could not check flatpak protontricks: {e}")
            
            self.logger.info(f"Protontricks command: {protontricks_cmd}")
            if not protontricks_cmd:
                self.logger.warning("protontricks is not installed (optional - some features may be limited)")
                # Don't return False - protontricks is optional
            
            # Check for Steam (not flatpak)
            self.logger.info("Checking Steam installation...")
            if self.steam_utils.command_exists("flatpak"):
                try:
                    output = self.steam_utils.run_command(
                        "flatpak", "list", "--app", "--columns=application"
                    )
                    if "com.valvesoftware.Steam" in output:
                        self.logger.error("steam is installed via flatpak, which is not supported")
                        return False
                except Exception as e:
                    self.logger.warning(f"Could not check flatpak steam: {e}")
            
            self.logger.info("All dependencies are available")
            self.logger.info("Dependency check returning True")
            return True
            
        except Exception as e:
            self.logger.error(f"Dependency check failed: {e}")
            return False
    
    def get_non_steam_games(self) -> List[Dict[str, str]]:
        """Get a list of non-Steam games"""
        return self.steam_utils.get_non_steam_games()

    def launch_protontricks(self, app_id: str) -> Dict[str, Any]:
        """Launch protontricks for a specific AppID"""
        try:
            protontricks_cmd = self.steam_utils.get_protontricks_command()
            cmd_list = protontricks_cmd.split() + [app_id]

            self.logger.info(f"Launching protontricks: {' '.join(cmd_list)}")

            # Launch protontricks in a new terminal or directly
            import subprocess
            result = subprocess.run(cmd_list, check=True, timeout=30)

            return {
                "success": True,
                "message": f"Protontricks launched successfully for AppID {app_id}"
            }

        except Exception as e:
            self.logger.error(f"Failed to launch protontricks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def install_mo2(self, install_dir: Optional[str] = None) -> Dict[str, Any]:
        """Download and install Mod Organizer 2"""
        try:
            result = self.mo2.download_mo2(install_dir=install_dir)
            # Return the result directly since MO2Installer already returns the proper format
            return result
        except Exception as e:
            self.logger.error(f"Failed to install MO2: {e}")
            return {"success": False, "error": str(e)}
    
    def setup_existing_mo2(self, mo2_path: str, custom_name: str) -> Dict[str, Any]:
        """Setup existing MO2 installation"""
        try:
            return self.mo2.setup_existing(mo2_path, custom_name)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def remove_nxm_handlers(self) -> Dict[str, Any]:
        """Remove NXM handlers"""
        try:
            return self.mo2.remove_nxm_handlers()
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def configure_nxm_handler(self, app_id: str, nxm_handler_path: str) -> Dict[str, Any]:
        """Configure NXM handler for a specific game"""
        try:
            return self.mo2.configure_nxm_handler(app_id, nxm_handler_path)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_game_info(self) -> Dict[str, Any]:
        """Get information about supported games"""
        result = {
            "supported_games": [
                "Skyrim Special Edition",
                "Fallout 4", 
                "Fallout 76",
                "Cyberpunk 2077",
                "And many more..."
            ],
            "launch_options": [
                "Proton with Wine",
                "Native Linux (if available)",
                "Steam Play"
            ]
        }
        
        # Try to detect installed games
        try:
            steam_root = self.steam_utils.get_steam_root()
            
            # Check for FNV (AppID: 22380)
            fnv_compatdata = self.game_utils.find_game_compatdata("22380", steam_root)
            if fnv_compatdata:
                result["fnv_compatdata"] = fnv_compatdata
            
            # Check for Enderal (AppID: 976620)
            enderal_compatdata = self.game_utils.find_game_compatdata("976620", steam_root)
            if enderal_compatdata:
                result["enderal_compatdata"] = enderal_compatdata
                
        except Exception as e:
            self.logger.warning(f"Could not find Steam installation: {e}")
        
        return result
    
    def check_for_updates(self) -> Dict[str, Any]:
        """Check if updates are available"""
        try:
            self.logger.info("Checking for updates...")
            # TODO: Implement actual update checking logic
            return {"success": True, "message": "No updates available"}
        except Exception as e:
            self.logger.error(f"Failed to check for updates: {e}")
            return {"success": False, "error": str(e)}
    
    def install_dependencies(self) -> Dict[str, Any]:
        """Install basic dependencies"""
        try:
            result = self.deps.install_basic_dependencies()
            return {"success": True, "result": result}
        except Exception as e:
            self.logger.error(f"Failed to install dependencies: {e}")
            return {"success": False, "error": str(e)}
    
    def install_dependencies_for_game(self, game_app_id: str) -> Dict[str, Any]:
        """Install dependencies for a specific game"""
        try:
            result = self.deps.install_proton_dependencies(game_app_id)
            return {"success": True, "result": result}
        except Exception as e:
            self.logger.error(f"Failed to install dependencies for game {game_app_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def setup_mo2_dependencies(self, mo2_name: str, mo2_exe: str) -> Dict[str, Any]:
        """Setup MO2 dependencies"""
        try:
            games = self.get_non_steam_games()
            if not games:
                return {"success": False, "error": "No non-Steam games found. Add some games to Steam first."}
            
            return {
                "success": True,
                "games": games,
                "message": f"Found {len(games)} non-Steam games. Please select one to install MO2 dependencies:"
            }
        except Exception as e:
            self.logger.error(f"Failed to setup MO2 dependencies: {e}")
            return {"success": False, "error": str(e)}
    
    def setup_fnv_dependencies(self) -> Dict[str, Any]:
        """Setup Fallout New Vegas dependencies"""
        try:
            result = self.deps.install_fnv_dependencies()
            return {"success": True, "result": result}
        except Exception as e:
            self.logger.error(f"Failed to setup FNV dependencies: {e}")
            return {"success": False, "error": str(e)}
    
    def setup_enderal_dependencies(self) -> Dict[str, Any]:
        """Setup Enderal dependencies"""
        try:
            result = self.deps.install_enderal_dependencies()
            return {"success": True, "result": result}
        except Exception as e:
            self.logger.error(f"Failed to setup Enderal dependencies: {e}")
            return {"success": False, "error": str(e)}

    def get_all_games(self) -> List[Dict[str, Any]]:
        """Get all games across all platforms"""
        try:
            games = self.game_manager.get_all_games()
            return [{
                "name": game.name,
                "path": game.path,
                "platform": game.platform,
                "app_id": game.app_id,
                "exe_path": game.exe_path,
                "prefix_path": game.prefix_path,
                "wine_version": game.wine_version,
                "proton_version": game.proton_version
            } for game in games]
        except Exception as e:
            self.logger.error(f"Failed to get all games: {e}")
            return []

    def get_fnv_installations(self) -> List[Dict[str, Any]]:
        """Get all Fallout New Vegas installations"""
        try:
            installations = self.game_manager.get_fnv_installations()
            return [{
                "game_name": result.game.name,
                "platform": result.platform,
                "confidence": result.confidence,
                "prefix_path": str(result.prefix.path),
                "reason": result.reason
            } for result in installations]
        except Exception as e:
            self.logger.error(f"Failed to get FNV installations: {e}")
            return []

    def get_enderal_installations(self) -> List[Dict[str, Any]]:
        """Get all Enderal installations"""
        try:
            installations = self.game_manager.get_enderal_installations()
            return [{
                "game_name": result.game.name,
                "platform": result.platform,
                "confidence": result.confidence,
                "prefix_path": str(result.prefix.path),
                "reason": result.reason
            } for result in installations]
        except Exception as e:
            self.logger.error(f"Failed to get Enderal installations: {e}")
            return []

    def get_skyrim_installations(self) -> List[Dict[str, Any]]:
        """Get all Skyrim installations"""
        try:
            installations = self.game_manager.get_skyrim_installations()
            return [{
                "game_name": result.game.name,
                "platform": result.platform,
                "confidence": result.confidence,
                "prefix_path": str(result.prefix.path),
                "reason": result.reason
            } for result in installations]
        except Exception as e:
            self.logger.error(f"Failed to get Skyrim installations: {e}")
            return []

    def setup_fnv_complete(self) -> Dict[str, Any]:
        """Complete Fallout New Vegas setup across all platforms"""
        try:
            result = self.game_manager.setup_fnv_complete()
            return {
                "success": result.success,
                "message": result.message,
                "game_name": result.game_name,
                "platform": result.platform,
                "prefix_path": result.prefix_path,
                "error": result.error
            }
        except Exception as e:
            self.logger.error(f"Failed to setup FNV complete: {e}")
            return {"success": False, "error": str(e)}

    def setup_enderal_complete(self) -> Dict[str, Any]:
        """Complete Enderal setup across all platforms"""
        try:
            result = self.game_manager.setup_enderal_complete()
            return {
                "success": result.success,
                "message": result.message,
                "game_name": result.game_name,
                "platform": result.platform,
                "prefix_path": result.prefix_path,
                "error": result.error
            }
        except Exception as e:
            self.logger.error(f"Failed to setup Enderal complete: {e}")
            return {"success": False, "error": str(e)}

    def setup_skyrim_complete(self) -> Dict[str, Any]:
        """Complete Skyrim setup across all platforms"""
        try:
            result = self.game_manager.setup_skyrim_complete()
            return {
                "success": result.success,
                "message": result.message,
                "game_name": result.game_name,
                "platform": result.platform,
                "prefix_path": result.prefix_path,
                "error": result.error
            }
        except Exception as e:
            self.logger.error(f"Failed to setup Skyrim complete: {e}")
            return {"success": False, "error": str(e)}

    def get_game_summary(self) -> Dict[str, Any]:
        """Get a summary of all detected games"""
        try:
            return self.game_manager.get_game_summary()
        except Exception as e:
            self.logger.error(f"Failed to get game summary: {e}")
            return {"error": str(e)}
    
    def cache_all_dependencies(self, force_download: bool = False) -> Dict[str, Any]:
        """Cache all dependency files for faster future installations"""
        try:
            return self.deps.cache_all_dependencies(force_download)
        except Exception as e:
            self.logger.error(f"Failed to cache dependencies: {e}")
            return {"success": False, "error": str(e)}
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get status of the dependency cache"""
        try:
            return self.deps.get_cache_status()
        except Exception as e:
            self.logger.error(f"Failed to get cache status: {e}")
            return {"error": str(e)}
    
    def clear_dependency_cache(self) -> Dict[str, Any]:
        """Clear all cached dependency files"""
        try:
            return self.deps.clear_dependency_cache()
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            return {"success": False, "error": str(e)}
    
    def _start_background_caching(self):
        """Start background dependency caching and MO2 caching in a separate thread"""
        try:
            import threading
            
            def cache_dependencies():
                try:
                    self.logger.info("Starting background dependency caching...")
                    result = self.deps.cache_all_dependencies(force_download=False)
                    cached_count = sum(1 for success in result.values() if success)
                    total_count = len(result)
                    self.logger.info(f"Background caching completed: {cached_count}/{total_count} dependencies cached")
                except Exception as e:
                    self.logger.error(f"Background caching failed: {e}")
            
            def cache_mo2():
                try:
                    self.logger.info("Starting background MO2 caching...")
                    
                    # Test if requests module is available
                    try:
                        import requests
                        self.logger.info("MO2 Cache: requests module is available")
                    except ImportError as e:
                        self.logger.error(f"MO2 Cache: requests module not available: {e}")
                        return
                    
                    # Set up a simple progress callback for logging
                    def progress_callback(message):
                        self.logger.info(f"MO2 Cache: {message}")
                    
                    self.mo2.set_progress_callback(progress_callback)
                    
                    # Try to get latest release and cache it
                    self.logger.info("MO2 Cache: Fetching latest release from GitHub...")
                    release = self.mo2._get_latest_release()
                    if release:
                        self.logger.info(f"MO2 Cache: Found release: {release.tag_name}")
                        self.logger.info("MO2 Cache: Finding download asset...")
                        download_url, filename = self.mo2._find_mo2_asset(release)
                        if download_url and filename:
                            self.logger.info(f"MO2 Cache: Found asset: {filename}")
                            self.logger.info(f"MO2 Cache: Download URL: {download_url}")
                            # This will cache the file if not already cached
                            cached_file = self.mo2._download_file(download_url, filename)
                            if cached_file:
                                self.logger.info(f"MO2 Cache: Successfully cached to: {cached_file}")
                                # Verify the file exists and show size
                                import os
                                if os.path.exists(cached_file):
                                    file_size = os.path.getsize(cached_file)
                                    self.logger.info(f"MO2 Cache: File size: {file_size / (1024*1024):.1f} MB")
                                else:
                                    self.logger.error("MO2 Cache: Cached file doesn't exist after download!")
                            else:
                                self.logger.error("MO2 Cache: Failed to cache MO2 - download_file returned None")
                        else:
                            self.logger.error(f"MO2 Cache: Could not find asset - URL: {download_url}, Filename: {filename}")
                    else:
                        self.logger.error("MO2 Cache: Could not get latest release from GitHub")
                except Exception as e:
                    self.logger.error(f"MO2 caching failed with exception: {e}")
                    import traceback
                    self.logger.error(f"MO2 caching traceback: {traceback.format_exc()}")
            
            # Start dependency caching in background thread
            cache_thread = threading.Thread(target=cache_dependencies, daemon=True)
            cache_thread.start()
            self.logger.info("Background dependency caching thread started")
            
            # Run MO2 caching synchronously (not in background thread) for debugging
            self.logger.info("Starting synchronous MO2 caching for debugging...")
            cache_mo2()
            self.logger.info("Synchronous MO2 caching completed")
            
        except Exception as e:
            self.logger.error(f"Failed to start background caching: {e}")