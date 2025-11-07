"""
General utilities module
Handles common utility operations
"""

import os
import subprocess
from pathlib import Path
from typing import Optional
from src.utils.logger import get_logger

class Utils:
    """General utility functions"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run([command, "--version"], 
                         capture_output=True, check=True, timeout=30)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
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
                , timeout=30)
                if "found" in result.stdout:
                    self.logger.info("Using flatpak protontricks")
                    return "flatpak run com.github.Matoking.protontricks"
            except subprocess.CalledProcessError:
                pass
        
        raise RuntimeError("protontricks is not installed")
    
    def get_steam_root(self) -> str:
        """Find the Steam installation directory"""
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
    
    def find_game_compatdata(self, app_id: str, steam_root: str) -> Optional[str]:
        """Find the compatibility data path for a specific game"""
        try:
            steam_root_path = Path(steam_root)
            
            # Check main Steam library first
            compatdata_path = steam_root_path / "steamapps" / "compatdata" / app_id
            if compatdata_path.exists():
                return str(compatdata_path)
            
            # Check additional Steam libraries from libraryfolders.vdf
            libraryfolders_path = steam_root_path / "steamapps" / "libraryfolders.vdf"
            if libraryfolders_path.exists():
                content = libraryfolders_path.read_text()
                lines = content.split("\n")
                for line in lines:
                    if '"path"' in line:
                        # Extract path from the line
                        parts = line.split('"')
                        if len(parts) >= 4:
                            library_path = parts[3]
                            compatdata_path = Path(library_path) / "steamapps" / "compatdata" / app_id
                            if compatdata_path.exists():
                                return str(compatdata_path)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to find compatdata for game {app_id}: {e}")
            return None
