"""
Game utilities module
Handles game-related operations
"""

import os
import logging
from pathlib import Path
from typing import Optional

class GameUtils:
    """Utilities for game operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def find_game_compatdata(self, app_id: str, steam_root: str) -> Optional[str]:
        """Find the compatdata directory for a game"""
        try:
            steam_root_path = Path(steam_root)
            compatdata_dir = steam_root_path / "steamapps" / "compatdata"
            
            if not compatdata_dir.exists():
                return None
            
            # Look for the game's compatdata directory
            game_compatdata = compatdata_dir / app_id
            if game_compatdata.exists():
                self.logger.info(f"Found compatdata for game {app_id}: {game_compatdata}")
                return str(game_compatdata)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to find compatdata for game {app_id}: {e}")
            return None
