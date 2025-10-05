"""
Heroic Games Launcher Utilities
Handles all interactions with the Heroic Games Launcher, including finding games,
locating prefixes, and constructing launch commands.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import subprocess

# Assuming GameInfo dataclass is defined in a shared location
# If not, we should define it here or import from its actual location.
# For now, let's assume a simple structure based on game_finder.py
from utils.game_finder import GameInfo

class HeroicUtils:
    """Utilities for Heroic Games Launcher operations"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.heroic_config_paths = self._find_heroic_config_paths()

    def _find_heroic_config_paths(self) -> List[Path]:
        """Find potential Heroic configuration directories."""
        paths = [
            Path.home() / ".config" / "heroic",
            Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic"
        ]
        return [p for p in paths if p.exists()]

    def get_heroic_games(self) -> List[GameInfo]:
        """
        Find all games installed via Heroic.
        This is a simplified version of the logic in game_finder.py.
        """
        # In a real implementation, we would reuse the GameFinder logic.
        # For this utility, we'll just use a placeholder call.
        # This function's purpose is to provide a list of games for other
        # utils to query against.
        try:
            from utils.game_finder import GameFinder
            finder = GameFinder()
            # The _find_heroic_games is private, so we access it this way for the utility
            return finder._find_heroic_games()
        except Exception as e:
            self.logger.error(f"Failed to import or use GameFinder to find Heroic games: {e}")
            return []

    def find_game_by_name(self, game_name_query: str) -> Optional[GameInfo]:
        """Find a Heroic game by its name or common aliases."""
        heroic_games = self.get_heroic_games()
        query = game_name_query.lower().replace(" ", "")

        for game in heroic_games:
            # Simple matching logic, can be expanded
            if query in game.name.lower().replace(" ", ""):
                return game
        return None

    def get_prefix_for_game(self, game: GameInfo) -> Optional[str]:
        """
        Get the Wine prefix path for a specific Heroic game.
        Reuses logic from prefix_locator.py.
        """
        try:
            from utils.prefix_locator import PrefixLocator
            locator = PrefixLocator()
            # _find_heroic_game_prefix is private, access directly for this utility
            prefix_info = locator._find_heroic_game_prefix(game)
            return prefix_info.path if prefix_info else None
        except Exception as e:
            self.logger.error(f"Failed to import or use PrefixLocator to find Heroic prefix: {e}")
            return None

    def get_launch_command(self, game: GameInfo, executable_path: str) -> Optional[List[str]]:
        """
        Construct the command to launch an executable within a Heroic game's prefix.
        """
        prefix_path = self.get_prefix_for_game(game)
        if not prefix_path:
            self.logger.error(f"Could not find prefix for Heroic game: {game.name}")
            return None

        # We need to find the correct Wine/Proton binary associated with the game.
        # This logic is complex and exists in SmartPrefixManager/DependencyInstaller.
        # For now, we'll assume a 'wine' command is available and WINEPREFIX is sufficient.
        # A more robust solution would find the exact Proton version Heroic uses for the game.
        
        self.logger.info(f"Constructing launch command for {executable_path} in prefix {prefix_path}")

        # This is a simplified approach. A better one would parse Heroic's game-specific
        # config to find the exact Wine/Proton binary it's configured to use.
        command = [
            "wine",
            executable_path
        ]
        
        # The environment needs to be set by the calling process (e.g., in main.py)
        # os.environ['WINEPREFIX'] = prefix_path
        # subprocess.run(command, env=os.environ.copy())
        
        return command
        
    def launch_executable_in_prefix(self, game: GameInfo, executable_path: str) -> bool:
        """
        Directly launches an executable in the game's prefix.
        Returns True on success.
        """
        prefix_path = self.get_prefix_for_game(game)
        if not prefix_path:
            self.logger.error(f"Cannot launch, no prefix found for Heroic game: {game.name}")
            return False

        # This is a simplified placeholder. A real implementation needs to find the
        # specific Wine/Proton runner configured for the game in Heroic's settings.
        wine_binary = "wine" # Placeholder

        try:
            env = os.environ.copy()
            env["WINEPREFIX"] = prefix_path
            
            command = [wine_binary, executable_path]
            
            self.logger.info(f"Executing Heroic launch: WINEPREFIX={prefix_path} {' '.join(command)}")
            
            # Use Popen to launch in the background
            subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            return True
        except FileNotFoundError:
            self.logger.error(f"'{wine_binary}' command not found. Please ensure Wine is installed and in your system's PATH.")
            return False
        except Exception as e:
            self.logger.error(f"Failed to launch executable in Heroic prefix: {e}")
            return False

