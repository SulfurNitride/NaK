"""
Core business logic for NaK application
This module contains all the business logic and is framework-agnostic
"""

import logging
from typing import Dict, List, Any, Optional
from .mo2_installer import MO2Installer

from .dependency_installer import DependencyInstaller
from ..utils.steam_utils import SteamUtils
from ..utils.game_utils import GameUtils
from ..utils.utils import Utils

class Core:
    """Core represents the main business logic of the NaK application"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.mo2 = MO2Installer()

        self.deps = DependencyInstaller()
        self.steam_utils = SteamUtils()
        self.game_utils = GameUtils()
        self.utils = Utils()
    
    def get_version_info(self) -> tuple[str, str]:
        """Get version information"""
        return "2.0.3", "2025-08-22"
    
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
                self.logger.error("protontricks is not installed")
                return False
            
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
    
    def install_mo2(self) -> Dict[str, Any]:
        """Download and install Mod Organizer 2"""
        try:
            result = self.mo2.download_mo2()
            return {"success": True, "result": result}
        except Exception as e:
            self.logger.error(f"Failed to install MO2: {e}")
            return {"success": False, "error": str(e)}
    
    def setup_existing_mo2(self) -> Dict[str, Any]:
        """Setup existing MO2 installation"""
        try:
            return self.mo2.setup_existing()
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
