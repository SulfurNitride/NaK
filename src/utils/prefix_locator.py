"""
Wine/Proton prefix locator system
Finds Wine prefixes for games to apply regedits and fixes
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, NamedTuple
from dataclasses import dataclass

from src.utils.game_finder import GameInfo
from src.utils.logger import get_logger


@dataclass
class PrefixInfo:
    """Information about a Wine/Proton prefix"""
    path: Path
    prefix_type: str  # "proton", "wine", "bottles", "heroic"
    game_info: Optional[GameInfo] = None
    proton_version: Optional[str] = None
    wine_version: Optional[str] = None


class PrefixLocator:
    """Locates Wine/Proton prefixes for games"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def find_game_prefix(self, game: GameInfo) -> Optional[PrefixInfo]:
        """Find the Wine/Proton prefix for a specific game"""
        self.logger.debug(f"Looking for prefix for game: {game.name} ({game.platform})")

        # Try different prefix detection methods based on platform
        if game.platform == "Steam" or game.platform == "Steam (Non-Steam)":
            return self._find_steam_game_prefix(game)
        elif "Heroic" in game.platform:
            return self._find_heroic_game_prefix(game)
        else:
            # Try generic wine prefix detection
            return self._find_wine_prefix_by_path(game)

    def _find_steam_game_prefix(self, game: GameInfo) -> Optional[PrefixInfo]:
        """Find Steam/Proton prefix for a game"""
        if not game.app_id:
            self.logger.debug(f"No app_id for game {game.name}")
            return None

        # Proton prefixes are in ~/.steam/steam/steamapps/compatdata/APPID/
        steam_paths = [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
        ]

        for steam_path in steam_paths:
            compatdata_path = steam_path / "steamapps" / "compatdata" / game.app_id
            if compatdata_path.exists():
                pfx_path = compatdata_path / "pfx"
                if pfx_path.exists():
                    # Try to detect Proton version
                    proton_version = self._detect_proton_version(compatdata_path)

                    self.logger.info(f"Found Proton prefix for {game.name}: {pfx_path}")
                    return PrefixInfo(
                        path=pfx_path,
                        prefix_type="proton",
                        game_info=game,
                        proton_version=proton_version
                    )

        self.logger.debug(f"No Proton prefix found for {game.name}")
        return None

    def _detect_proton_version(self, compatdata_path: Path) -> Optional[str]:
        """Detect which Proton version is being used"""
        try:
            # Check for version.txt or other version indicators
            version_file = compatdata_path / "version"
            if version_file.exists():
                return version_file.read_text().strip()

            # Check parent directory for proton installation
            # This might be in steam/steamapps/common/Proton X.X/
            return "Unknown Proton"

        except Exception as e:
            self.logger.debug(f"Could not detect Proton version: {e}")
            return None

    def _find_heroic_game_prefix(self, game: GameInfo) -> Optional[PrefixInfo]:
        """Find Heroic game prefix with enhanced detection"""
        if not game.app_id:
            return None

        heroic_paths = [
            Path.home() / ".config" / "heroic",
            Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic"
        ]
        
        # Also check common custom Heroic prefix locations
        custom_heroic_paths = [
            Path.home() / "Games" / "Heroic" / "Prefixes",
            Path.home() / ".local" / "share" / "heroic" / "prefixes",
            Path.home() / "Wine" / "prefixes"
        ]

        for config_path in heroic_paths:
            if not config_path.exists():
                continue

            self.logger.debug(f"Checking Heroic config path: {config_path}")

            # Method 1: Check game-specific config for prefix path
            game_config = config_path / "GamesConfig" / f"{game.app_id}.json"
            if game_config.exists():
                try:
                    with open(game_config, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)

                    # Heroic config structure: { "app_id": { "winePrefix": "...", ... }, "version": "v0" }
                    game_data = config_data.get(game.app_id, {})
                    wine_prefix = game_data.get("winePrefix", "")
                    
                    if wine_prefix and Path(wine_prefix).exists():
                        wine_version = game_data.get("wineVersion", {}).get("name", "Unknown")
                        wine_bin = game_data.get("wineVersion", {}).get("bin", "")

                        self.logger.info(f"Found Heroic prefix for {game.name}: {wine_prefix}")
                        return PrefixInfo(
                            path=Path(wine_prefix),
                            prefix_type="heroic",
                            game_info=game,
                            wine_version=wine_version
                        )

                except Exception as e:
                    self.logger.debug(f"Could not parse Heroic config for {game.app_id}: {e}")

            # Method 2: Check default heroic prefixes directory
            prefixes_path = config_path / "Prefixes"
            if prefixes_path.exists():
                # Try exact app_id match first
                game_prefix = prefixes_path / game.app_id
                if game_prefix.exists() and (game_prefix / "drive_c").exists():
                    self.logger.info(f"Found Heroic default prefix for {game.name}: {game_prefix}")
                    return PrefixInfo(
                        path=game_prefix,
                        prefix_type="heroic",
                        game_info=game
                    )
                
                # Try to find prefix by scanning all prefixes and matching game path
                for prefix_dir in prefixes_path.iterdir():
                    if prefix_dir.is_dir() and (prefix_dir / "drive_c").exists():
                        # Check if this prefix contains the game
                        if self._prefix_contains_game(prefix_dir, game):
                            self.logger.info(f"Found Heroic prefix containing {game.name}: {prefix_dir}")
                            return PrefixInfo(
                                path=prefix_dir,
                                prefix_type="heroic",
                                game_info=game
                            )

            # Method 3: Check for Wine bottles created by Heroic
            bottles_path = config_path / "bottles"
            if bottles_path.exists():
                for bottle_dir in bottles_path.iterdir():
                    if bottle_dir.is_dir() and (bottle_dir / "drive_c").exists():
                        if self._prefix_contains_game(bottle_dir, game):
                            self.logger.info(f"Found Heroic bottle containing {game.name}: {bottle_dir}")
                            return PrefixInfo(
                                path=bottle_dir,
                                prefix_type="heroic",
                                game_info=game
                            )

        # Method 4: Check custom Heroic prefix locations
        for custom_path in custom_heroic_paths:
            if not custom_path.exists():
                continue
                
            self.logger.debug(f"Checking custom Heroic prefix path: {custom_path}")
            
            # Look for game-specific prefix directories
            for prefix_dir in custom_path.rglob("*"):
                if prefix_dir.is_dir() and (prefix_dir / "drive_c").exists():
                    # Check if this prefix contains the game
                    if self._prefix_contains_game(prefix_dir, game):
                        self.logger.info(f"Found custom Heroic prefix containing {game.name}: {prefix_dir}")
                        return PrefixInfo(
                            path=prefix_dir,
                            prefix_type="heroic",
                            game_info=game
                        )

        return None

    def _prefix_contains_game(self, prefix_path: Path, game: GameInfo) -> bool:
        """Check if a Wine prefix contains the specified game"""
        try:
            if not game.path:
                return False
            
            # Convert game path to Wine path format
            game_path = Path(game.path)
            
            # Look for the game executable in the prefix
            drive_c = prefix_path / "drive_c"
            if not drive_c.exists():
                return False
            
            # Try to find the game executable in the prefix
            # This is a heuristic - we look for the game name in the path structure
            for file_path in drive_c.rglob("*"):
                if file_path.is_file():
                    # Check if the filename contains the game name
                    if game.name.lower() in file_path.name.lower():
                        return True
                    # Check if any part of the path contains the game name
                    if game.name.lower() in str(file_path).lower():
                        return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking if prefix contains game: {e}")
            return False

    def _find_wine_prefix_by_path(self, game: GameInfo) -> Optional[PrefixInfo]:
        """Try to find Wine prefix by looking at game installation path"""
        if not game.path:
            return None

        game_path = Path(game.path)

        # Look for drive_c in parent directories (indicates Wine prefix)
        current_path = game_path
        for _ in range(5):  # Don't go too far up
            current_path = current_path.parent

            drive_c = current_path / "drive_c"
            if drive_c.exists():
                # Check if this looks like a Wine prefix
                if (current_path / "system.reg").exists():
                    self.logger.info(f"Found Wine prefix for {game.name}: {current_path}")
                    return PrefixInfo(
                        path=current_path,
                        prefix_type="wine",
                        game_info=game
                    )

        return None

    def find_all_prefixes(self) -> List[PrefixInfo]:
        """Find all Wine/Proton prefixes on the system"""
        prefixes = []

        # Find Steam/Proton prefixes
        prefixes.extend(self._find_all_proton_prefixes())

        # Find Heroic prefixes
        prefixes.extend(self._find_all_heroic_prefixes())

        # Find standalone Wine prefixes
        prefixes.extend(self._find_all_wine_prefixes())

        # Find Bottles prefixes
        prefixes.extend(self._find_all_bottles_prefixes())

        return prefixes

    def _find_all_proton_prefixes(self) -> List[PrefixInfo]:
        """Find all Proton prefixes"""
        prefixes = []

        steam_paths = [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
        ]

        for steam_path in steam_paths:
            compatdata_path = steam_path / "steamapps" / "compatdata"
            if not compatdata_path.exists():
                continue

            for app_dir in compatdata_path.iterdir():
                if app_dir.is_dir() and app_dir.name.isdigit():
                    pfx_path = app_dir / "pfx"
                    if pfx_path.exists():
                        proton_version = self._detect_proton_version(app_dir)
                        prefixes.append(PrefixInfo(
                            path=pfx_path,
                            prefix_type="proton",
                            proton_version=proton_version
                        ))

        return prefixes

    def _find_all_heroic_prefixes(self) -> List[PrefixInfo]:
        """Find all Heroic prefixes with enhanced detection"""
        prefixes = []

        heroic_paths = [
            Path.home() / ".config" / "heroic",
            Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic"
        ]

        for config_path in heroic_paths:
            if not config_path.exists():
                continue

            self.logger.debug(f"Scanning Heroic config path: {config_path}")

            try:
                # Method 1: Check default prefixes directory
                prefixes_path = config_path / "Prefixes"
                if prefixes_path.exists():
                    for prefix_dir in prefixes_path.iterdir():
                        try:
                            if prefix_dir.is_dir() and (prefix_dir / "drive_c").exists():
                                prefixes.append(PrefixInfo(
                                    path=prefix_dir,
                                    prefix_type="heroic"
                                ))
                        except Exception as e:
                            self.logger.debug(f"Error checking prefix dir {prefix_dir}: {e}")
                            continue

                # Method 2: Check bottles directory
                bottles_path = config_path / "bottles"
                if bottles_path.exists():
                    for bottle_dir in bottles_path.iterdir():
                        try:
                            if bottle_dir.is_dir() and (bottle_dir / "drive_c").exists():
                                prefixes.append(PrefixInfo(
                                    path=bottle_dir,
                                    prefix_type="heroic"
                                ))
                        except Exception as e:
                            self.logger.debug(f"Error checking bottle dir {bottle_dir}: {e}")
                            continue

                # Method 3: Check GamesConfig for custom prefix paths (limit to avoid slowdown)
                games_config_path = config_path / "GamesConfig"
                if games_config_path.exists():
                    config_files = list(games_config_path.iterdir())
                    # Limit to first 50 config files to avoid performance issues
                    for config_file in config_files[:50]:
                        if config_file.suffix == '.json':
                            try:
                                with open(config_file, 'r', encoding='utf-8') as f:
                                    config_data = json.load(f)
                                
                                # Heroic config structure: { "app_id": { "winePrefix": "...", ... }, "version": "v0" }
                                # Look for winePrefix in any app_id key
                                for app_id, game_data in config_data.items():
                                    if app_id == "version" or app_id == "explicit":
                                        continue
                                    
                                    if isinstance(game_data, dict):
                                        wine_prefix = game_data.get("winePrefix", "")
                                        if wine_prefix and Path(wine_prefix).exists():
                                            # Check if we haven't already added this prefix
                                            if not any(p.path == Path(wine_prefix) for p in prefixes):
                                                wine_version = game_data.get("wineVersion", {}).get("name", "Unknown")
                                                prefixes.append(PrefixInfo(
                                                    path=Path(wine_prefix),
                                                    prefix_type="heroic",
                                                    wine_version=wine_version
                                                ))
                            except Exception as e:
                                self.logger.debug(f"Could not parse Heroic config {config_file}: {e}")
                                continue
            except Exception as e:
                self.logger.warning(f"Error scanning Heroic path {config_path}: {e}")
                continue

        return prefixes

    def _find_all_wine_prefixes(self) -> List[PrefixInfo]:
        """Find standalone Wine prefixes"""
        prefixes = []

        # Common Wine prefix locations
        wine_locations = [
            Path.home() / ".wine",
            Path.home() / ".local" / "share" / "wineprefixes",
            Path.home() / "Games",
        ]

        for location in wine_locations:
            if not location.exists():
                continue

            if location.name == ".wine":
                # Default Wine prefix
                if (location / "drive_c").exists():
                    prefixes.append(PrefixInfo(
                        path=location,
                        prefix_type="wine"
                    ))
            else:
                # Scan for subdirectories that are Wine prefixes
                for subdir in location.iterdir():
                    if subdir.is_dir() and (subdir / "drive_c").exists():
                        prefixes.append(PrefixInfo(
                            path=subdir,
                            prefix_type="wine"
                        ))

        return prefixes

    def _find_all_bottles_prefixes(self) -> List[PrefixInfo]:
        """Find Bottles prefixes"""
        prefixes = []

        bottles_path = Path.home() / ".local" / "share" / "bottles" / "bottles"
        if bottles_path.exists():
            for bottle_dir in bottles_path.iterdir():
                if bottle_dir.is_dir() and (bottle_dir / "drive_c").exists():
                    prefixes.append(PrefixInfo(
                        path=bottle_dir,
                        prefix_type="bottles"
                    ))

        return prefixes

    def apply_regedit_to_prefix(self, prefix_info: PrefixInfo, reg_file_path: str) -> bool:
        """Apply a .reg file to a Wine prefix"""
        try:
            import subprocess

            # Set WINEPREFIX environment
            env = os.environ.copy()
            env['WINEPREFIX'] = str(prefix_info.path)

            # Run regedit
            result = subprocess.run([
                'wine', 'regedit', '/S', reg_file_path
            ], env=env, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                self.logger.info(f"Successfully applied {reg_file_path} to {prefix_info.path}")
                return True
            else:
                self.logger.error(f"Failed to apply {reg_file_path}: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error applying regedit: {e}")
            return False