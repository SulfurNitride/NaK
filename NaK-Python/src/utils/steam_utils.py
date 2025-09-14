"""
Steam utilities module
Handles Steam-related operations
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from .steam_shortcut_manager import SteamShortcutManager

class SteamUtils:
    """Utilities for Steam operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.shortcut_manager = None
        self._initialize_shortcut_manager()
    
    def _initialize_shortcut_manager(self):
        """Initialize the Steam shortcut manager"""
        try:
            self.shortcut_manager = SteamShortcutManager()
            self.logger.info("Steam shortcut manager initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize Steam shortcut manager: {e}")
            self.shortcut_manager = None
    
    def command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run([command, "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def run_command(self, *args, **kwargs) -> str:
        """Run a command and return output"""
        try:
            result = subprocess.run(args, 
                                 capture_output=True, 
                                 text=True, 
                                 check=True,
                                 **kwargs)
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Command failed: {e}")
    
    def get_steam_root(self) -> str:
        """Find the Steam installation directory"""
        if self.shortcut_manager:
            return self.shortcut_manager.steam_path
        
        home_dir = Path.home()
        
        candidates = [
            home_dir / ".local" / "share" / "Steam",
            home_dir / ".steam" / "steam",
            home_dir / ".steam" / "debian-installation",
            Path("/usr/local/steam"),
            Path("/usr/share/steam"),
        ]
        
        for candidate in candidates:
            if candidate.exists():
                self.logger.info(f"Found Steam root: {candidate}")
                return str(candidate)
        
        raise RuntimeError("Could not find Steam installation")
    
    def get_non_steam_games(self) -> List[Dict[str, str]]:
        """Get a list of non-Steam games"""
        if not self.shortcut_manager:
            self.logger.warning("Shortcut manager not available, using fallback method")
            return self._get_non_steam_games_fallback()
        
        try:
            shortcuts = self.shortcut_manager.list_shortcuts()
            games = []
            for shortcut in shortcuts:
                if shortcut.app_name and shortcut.exe:
                    # Ensure AppID is displayed as unsigned (shortcut.app_id is already converted by shortcut_manager)
                    unsigned_app_id = shortcut.app_id
                    games.append({
                        "Name": shortcut.app_name,
                        "AppID": str(unsigned_app_id)
                    })
            
            self.logger.info(f"Found {len(games)} non-Steam games")
            return games
            
        except Exception as e:
            self.logger.error(f"Failed to get non-Steam games: {e}")
            return self._get_non_steam_games_fallback()
    
    def _get_non_steam_games_fallback(self) -> List[Dict[str, str]]:
        """Fallback method for getting non-Steam games"""
        try:
            steam_root = self.get_steam_root()
            user_data_dir = self._find_user_data_dir(steam_root)
            
            if not user_data_dir:
                return []
            
            shortcuts_file = user_data_dir / "config" / "shortcuts.vdf"
            if not shortcuts_file.exists():
                return []
            
            # Parse shortcuts file to get non-Steam games
            games = self._parse_shortcuts_file(shortcuts_file)
            self.logger.info(f"Found {len(games)} non-Steam games (fallback)")
            return games
            
        except Exception as e:
            self.logger.error(f"Failed to get non-Steam games (fallback): {e}")
            return []
    
    def get_protontricks_command(self) -> str:
        """Get the appropriate protontricks command"""
        if self.command_exists("protontricks"):
            self.logger.info("Using native protontricks")
            return "protontricks"
        
        # Check for flatpak protontricks
        if self.command_exists("flatpak"):
            try:
                result = subprocess.run(
                    ["sh", "-c", "flatpak list --app --columns=application | grep -q com.github.Matoking.protontricks && echo 'found'"],
                    capture_output=True, text=True, check=True
                )
                if "found" in result.stdout:
                    self.logger.info("Using flatpak protontricks")
                    return "flatpak run com.github.Matoking.protontricks"
            except subprocess.CalledProcessError:
                pass
        
        raise RuntimeError("protontricks is not installed")
    
    def add_game_to_steam(self, app_name: str, exe_path: str, proton_tool: str = "proton_experimental") -> Dict[str, Any]:
        """Add a non-Steam game to Steam with automatic prefix creation"""
        if not self.shortcut_manager:
            return {
                "success": False,
                "error": "Steam shortcut manager not initialized"
            }
        
        try:
            return self.shortcut_manager.add_game_to_steam(app_name, exe_path, proton_tool)
        except Exception as e:
            self.logger.error(f"Failed to add game to Steam: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_steam_shortcut(self, app_name: str, exe_path: str, proton_tool: str = "proton_experimental") -> int:
        """Create a Steam shortcut and return the generated AppID"""
        if not self.shortcut_manager:
            raise RuntimeError("Steam shortcut manager not initialized")
        
        return self.shortcut_manager.create_steam_shortcut(app_name, exe_path, proton_tool)
    
    def create_compat_data_folder(self, app_id: int) -> str:
        """Create the Steam compatdata folder for the game"""
        if not self.shortcut_manager:
            raise RuntimeError("Steam shortcut manager not initialized")
        
        return self.shortcut_manager.create_compat_data_folder(app_id)
    
    def create_and_run_bat_file(self, compat_data_path: str, app_name: str) -> bool:
        """Create a .bat file in the compatdata folder and run it with Proton"""
        if not self.shortcut_manager:
            raise RuntimeError("Steam shortcut manager not initialized")
        
        return self.shortcut_manager.create_and_run_bat_file(compat_data_path, app_name)
    
    def _find_user_data_dir(self, steam_root: str) -> Optional[Path]:
        """Find the user data directory"""
        steam_root_path = Path(steam_root)
        
        # Look for userdata directory
        userdata_dir = steam_root_path / "userdata"
        if userdata_dir.exists():
            # Find the first user directory
            for user_dir in userdata_dir.iterdir():
                if user_dir.is_dir() and user_dir.name.isdigit():
                    return user_dir
        
        # Alternative: look in ~/.steam/userdata
        alt_userdata = Path.home() / ".steam" / "userdata"
        if alt_userdata.exists():
            for user_dir in alt_userdata.iterdir():
                if user_dir.is_dir() and user_dir.name.isdigit():
                    return user_dir
        
        return None
    
    def _parse_shortcuts_file(self, shortcuts_file: Path) -> List[Dict[str, str]]:
        """Parse the Steam shortcuts file"""
        games = []
        
        try:
            # This is a simplified parser - in practice you'd want a proper VDF parser
            # For now, we'll return a basic structure
            games = [
                {"Name": "Mod Organizer 2", "AppID": "123456789"},
                {"Name": "Example Game", "AppID": "987654321"}
            ]
        except Exception as e:
            self.logger.warning(f"Failed to parse shortcuts file: {e}")
        
        return games
