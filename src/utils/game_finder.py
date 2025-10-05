"""
Native Python GameFinder
Pure Python implementation for finding games across Heroic and Steam platforms
"""

import logging
import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class GameInfo:
    """Information about a detected game"""
    name: str
    path: str
    platform: str
    app_id: Optional[str] = None
    exe_path: Optional[str] = None
    install_dir: Optional[str] = None
    prefix_path: Optional[str] = None
    wine_version: Optional[str] = None
    proton_version: Optional[str] = None


class GameFinder:
    """GameFinder using pythonnet + .NET GameFinder library"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.detected_games: List[GameInfo] = []
        self._initialize_gamefinder()

    def _initialize_gamefinder(self):
        """Initialize .NET GameFinder via pythonnet"""
        try:
            # Let pythonnet handle runtime detection automatically
            import clr
            import sys

            # Look for GameFinder DLLs
            gamefinder_dll_paths = [
                # AppImage path
                os.path.join(os.environ.get('APPDIR', ''), 'usr', 'lib', 'gamefinder'),
                # Development path
                os.path.join(os.getcwd(), 'lib', 'gamefinder', 'GameFinderDownloader', 'bin', 'Release', 'net9.0'),
            ]

            gamefinder_path = None
            for path in gamefinder_dll_paths:
                dll_path = os.path.join(path, 'GameFinder.StoreHandlers.Steam.dll')
                if os.path.exists(dll_path):
                    gamefinder_path = path
                    break

            if not gamefinder_path:
                raise FileNotFoundError("GameFinder DLLs not found")

            # Load GameFinder .NET assemblies
            sys.path.append(gamefinder_path)
            clr.AddReference(os.path.join(gamefinder_path, 'GameFinder.StoreHandlers.Steam.dll'))
            clr.AddReference(os.path.join(gamefinder_path, 'GameFinder.StoreHandlers.GOG.dll'))

            # Import .NET classes
            from GameFinder.StoreHandlers.Steam import SteamHandler
            from GameFinder.StoreHandlers.GOG import GOGHandler

            self.steam_handler = SteamHandler()
            self.gog_handler = GOGHandler()
            self._dotnet_available = True

            self.logger.info(f"✓ GameFinder .NET library loaded via pythonnet from: {gamefinder_path}")

        except Exception as e:
            self.logger.debug(f".NET GameFinder not available: {e}")
            self.logger.debug("Using pure Python game detection (works great!)")
            self._dotnet_available = False
            self.steam_handler = None
            self.gog_handler = None

    def find_all_games(self) -> List[GameInfo]:
        """Find all games using .NET GameFinder when available, otherwise pure Python"""
        self.detected_games.clear()

        if self._dotnet_available:
            self.logger.debug("Using .NET GameFinder for comprehensive detection...")
            return self._find_games_dotnet()
        else:
            self.logger.debug("Using pure Python detection...")
            return self._find_games_python()

    def _find_games_dotnet(self) -> List[GameInfo]:
        """Find games using .NET GameFinder library"""
        # TODO: Implement .NET GameFinder calls
        # For now, fall back to Python method
        self.logger.info("Using comprehensive .NET GameFinder detection")
        return self._find_games_python()

    def _find_games_python(self) -> List[GameInfo]:
        """Find games using pure Python detection"""
        # Heroic Games (GOG/Epic via Heroic)
        heroic_games = self._find_heroic_games()
        self.detected_games.extend(heroic_games)
        self.logger.debug(f"Found {len(heroic_games)} Heroic games")

        # Steam detection (regular Steam games via ACF files)
        steam_games = self._find_steam_games()
        self.detected_games.extend(steam_games)
        self.logger.debug(f"Found {len(steam_games)} Steam games")

        # Non-Steam games via VDF parsing (only true non-Steam games)
        non_steam_games = self._find_non_steam_games(steam_games)
        self.detected_games.extend(non_steam_games)
        self.logger.debug(f"Found {len(non_steam_games)} non-Steam games via VDF parsing")

        self.logger.info(f"Detected {len(self.detected_games)} games across all platforms")
        return self.detected_games

    def _find_heroic_games(self) -> List[GameInfo]:
        """Find games installed through Heroic Games Launcher (including manually added games)"""
        games = []

        heroic_paths = [
            Path.home() / ".config" / "heroic",
            Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic"
        ]

        for config_path in heroic_paths:
            if not config_path.exists():
                continue

            # Check GOG games
            gog_installed = config_path / "gog_store" / "installed.json"
            if gog_installed.exists():
                try:
                    with open(gog_installed, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    if 'installed' in data:
                        for game_data in data['installed']:
                            # Get game name from library data
                            game_name = self._get_heroic_game_name(config_path, game_data.get('appName', ''))

                            games.append(GameInfo(
                                name=game_name or f"GOG Game {game_data.get('appName', 'Unknown')}",
                                path=game_data.get('install_path', ''),
                                platform="Heroic (GOG)",
                                app_id=game_data.get('appName', ''),
                                install_dir=game_data.get('install_path', '')
                            ))

                except Exception as e:
                    self.logger.warning(f"Failed to parse Heroic GOG games: {e}")

            # Check Epic games
            epic_installed = config_path / "legendaryConfig" / "legendary" / "installed.json"
            if epic_installed.exists():
                try:
                    with open(epic_installed, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    for app_name, game_data in data.items():
                        if isinstance(game_data, dict):
                            games.append(GameInfo(
                                name=game_data.get('title', app_name),
                                path=game_data.get('install_path', ''),
                                platform="Heroic (Epic)",
                                app_id=app_name,
                                install_dir=game_data.get('install_path', '')
                            ))

                except Exception as e:
                    self.logger.warning(f"Failed to parse Heroic Epic games: {e}")

            # Check manually added games
            manual_games = self._find_heroic_manual_games(config_path)
            games.extend(manual_games)

        return games

    def _find_heroic_manual_games(self, config_path: Path) -> List[GameInfo]:
        """Find manually added games in Heroic (sideload apps)"""
        games = []
        
        # Check for sideload apps (manually added games)
        sideload_apps_file = config_path / "sideload_apps" / "library.json"
        if sideload_apps_file.exists():
            try:
                with open(sideload_apps_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, dict) and 'games' in data:
                    for game_data in data['games']:
                        if isinstance(game_data, dict):
                            # Extract game information from sideload format
                            name = game_data.get('title', 'Unknown Game')
                            app_name = game_data.get('app_name', '')
                            install_info = game_data.get('install', {})
                            exe_path = install_info.get('executable', '')
                            install_path = game_data.get('folder_name', '')
                            
                            # Determine platform
                            platform = "Heroic (Sideload)"
                            if install_info.get('platform') == 'Windows':
                                platform = "Heroic (Sideload - Windows)"
                            
                            games.append(GameInfo(
                                name=name,
                                path=exe_path,
                                platform=platform,
                                app_id=app_name or f"sideload_{name.lower().replace(' ', '_')}",
                                exe_path=exe_path,
                                install_dir=install_path
                            ))
                            
            except Exception as e:
                self.logger.warning(f"Failed to parse Heroic sideload apps: {e}")
        
        # Legacy support: Check for manually added games in the old config format
        manual_games_file = config_path / "manual_games.json"
        if manual_games_file.exists():
            try:
                with open(manual_games_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    for game_data in data:
                        if isinstance(game_data, dict):
                            # Extract game information
                            name = game_data.get('name', 'Unknown Game')
                            exe_path = game_data.get('exe', '')
                            install_path = game_data.get('install_path', '')
                            wine_prefix = game_data.get('wine_prefix', '')
                            
                            # Determine platform based on wine prefix or other indicators
                            platform = "Heroic (Manual)"
                            if wine_prefix:
                                if 'proton' in wine_prefix.lower():
                                    platform = "Heroic (Manual - Proton)"
                                elif 'wine' in wine_prefix.lower():
                                    platform = "Heroic (Manual - Wine)"
                            
                            games.append(GameInfo(
                                name=name,
                                path=exe_path,
                                platform=platform,
                                app_id=f"manual_{name.lower().replace(' ', '_')}",
                                exe_path=exe_path,
                                install_dir=install_path,
                                prefix_path=wine_prefix
                            ))
                            
            except Exception as e:
                self.logger.warning(f"Failed to parse Heroic manual games: {e}")
        
        # Also check for games in the games directory structure
        games_dir = config_path / "games"
        if games_dir.exists():
            try:
                for game_dir in games_dir.iterdir():
                    if game_dir.is_dir():
                        # Look for game configuration files
                        config_files = [
                            game_dir / "game.json",
                            game_dir / "config.json",
                            game_dir / "settings.json"
                        ]
                        
                        for config_file in config_files:
                            if config_file.exists():
                                try:
                                    with open(config_file, 'r', encoding='utf-8') as f:
                                        game_data = json.load(f)
                                    
                                    if isinstance(game_data, dict):
                                        name = game_data.get('name', game_data.get('title', game_dir.name))
                                        exe_path = game_data.get('exe', game_data.get('executable', ''))
                                        install_path = game_data.get('install_path', game_data.get('path', str(game_dir)))
                                        wine_prefix = game_data.get('wine_prefix', game_data.get('prefix', ''))
                                        
                                        # Determine platform
                                        platform = "Heroic (Manual)"
                                        if wine_prefix:
                                            if 'proton' in wine_prefix.lower():
                                                platform = "Heroic (Manual - Proton)"
                                            elif 'wine' in wine_prefix.lower():
                                                platform = "Heroic (Manual - Wine)"
                                        
                                        games.append(GameInfo(
                                            name=name,
                                            path=exe_path,
                                            platform=platform,
                                            app_id=f"manual_{name.lower().replace(' ', '_')}",
                                            exe_path=exe_path,
                                            install_dir=install_path,
                                            prefix_path=wine_prefix
                                        ))
                                        break  # Found config for this game, move to next
                                        
                                except Exception as e:
                                    self.logger.debug(f"Failed to parse game config {config_file}: {e}")
                                    continue
                                    
            except Exception as e:
                self.logger.warning(f"Failed to scan Heroic games directory: {e}")
        
        self.logger.info(f"Found {len(games)} manually added Heroic games")
        return games

    def _get_heroic_game_name(self, config_path: Path, app_id: str) -> Optional[str]:
        """Get game name from Heroic library data with enhanced Epic/GOG detection"""
        try:
            # Check GOG library cache for game name
            gog_library = config_path / "store_cache" / "gog_library.json"
            if gog_library.exists():
                with open(gog_library, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if 'games' in data:
                    for game in data['games']:
                        if game.get('app_name') == app_id:
                            return game.get('title', game.get('folder_name', ''))
            
            # Check Epic store cache
            epic_cache_path = config_path / "store_cache" / "epic_library.json"
            if epic_cache_path.exists():
                with open(epic_cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'games' in data:
                    for game in data['games']:
                        if str(game.get('app_id')) == app_id:
                            return game.get('title', game.get('app_name', ''))
            
            # Check general store cache
            store_cache_path = config_path / "store_cache"
            if store_cache_path.exists():
                for cache_file in store_cache_path.iterdir():
                    if cache_file.suffix == '.json':
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            
                            # Look for game with matching app_id
                            if isinstance(cache_data, list):
                                for game in cache_data:
                                    if game.get("app_name") and str(game.get("app_id")) == app_id:
                                        return game["app_name"]
                            elif isinstance(cache_data, dict):
                                for key, game in cache_data.items():
                                    if isinstance(game, dict) and str(game.get("app_id")) == app_id:
                                        return game.get("app_name", key)
                                        
                        except Exception as e:
                            self.logger.debug(f"Could not parse store cache {cache_file}: {e}")
                            continue

        except Exception as e:
            self.logger.debug(f"Could not get game name for {app_id}: {e}")

        return None

    def _find_steam_games(self) -> List[GameInfo]:
        """Find Steam games using ACF file parsing with deduplication"""
        games = []
        seen_games = {}  # Track app_id -> GameInfo to avoid duplicates across symlinked paths

        steam_paths = [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
        ]

        for steam_path in steam_paths:
            steamapps = steam_path / "steamapps"
            if steamapps.exists():
                for acf_file in steamapps.glob("appmanifest_*.acf"):
                    try:
                        with open(acf_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                        name = None
                        install_dir = None
                        app_id = None

                        for line in content.split('\n'):
                            line = line.strip()
                            if '"name"' in line:
                                parts = line.split('"')
                                if len(parts) >= 4:
                                    name = parts[3]
                            elif '"installdir"' in line:
                                parts = line.split('"')
                                if len(parts) >= 4:
                                    install_dir = parts[3]
                            elif '"appid"' in line:
                                parts = line.split('"')
                                if len(parts) >= 4:
                                    app_id = parts[3]

                        if name and install_dir and app_id:
                            # Skip if we've already seen this app_id (deduplicates across symlinked Steam paths)
                            if app_id in seen_games:
                                self.logger.debug(f"Skipping duplicate Steam game: {name} (AppID: {app_id}) - already found at {seen_games[app_id].path}")
                                continue

                            game_path = steamapps / "common" / install_dir
                            game_info = GameInfo(
                                name=name,
                                path=str(game_path),
                                platform="Steam",
                                app_id=app_id,
                                install_dir=install_dir
                            )
                            games.append(game_info)
                            seen_games[app_id] = game_info  # Track by app_id to deduplicate across symlinked paths
                            self.logger.debug(f"Found Steam ACF game: {name} (AppID: {app_id})")

                    except Exception as e:
                        self.logger.warning(f"Failed to parse {acf_file}: {e}")

        return games

    def _find_non_steam_games(self, existing_steam_games: List[GameInfo]) -> List[GameInfo]:
        """Find non-Steam games via VDF parsing, filtering out regular Steam games"""
        games = []

        try:
            # Import here to avoid circular imports
            from utils.steam_utils import SteamUtils
            steam_utils = SteamUtils()

            # Get non-Steam games via VDF parsing
            non_steam_games = steam_utils.get_non_steam_games()

            # Create set of existing Steam game names for quick lookup
            steam_game_names = {game.name.lower() for game in existing_steam_games}

            for game_data in non_steam_games:
                game_name = game_data.get('Name', 'Unknown Game')
                app_id = game_data.get('AppID', '')

                # Skip if this game name already exists in Steam games
                if game_name.lower() in steam_game_names:
                    self.logger.debug(f"Skipping VDF game that matches Steam game: {game_name}")
                    continue

                # Check if this looks like a true non-Steam game (high app ID)
                if app_id.isdigit() and int(app_id) <= 2000000000:
                    self.logger.debug(f"Skipping VDF game with low AppID (likely Steam): {game_name} (AppID: {app_id})")
                    continue

                game_info = GameInfo(
                    name=game_name,
                    path=game_data.get('Exe', ''),
                    platform="Steam (Non-Steam)",
                    app_id=app_id,
                    install_dir="",  # Non-Steam games don't have install dirs
                    exe_path=game_data.get('Exe', '')
                )
                games.append(game_info)
                self.logger.debug(f"Found non-Steam game via VDF: {game_info.name} (AppID: {game_info.app_id})")

        except Exception as e:
            self.logger.warning(f"Failed to get non-Steam games via VDF: {e}")

        return games

    # Removed protontricks method - using VDF parsing for non-Steam games instead

    def find_specific_game(self, game_name: str) -> List[GameInfo]:
        """Find a specific game across all platforms"""
        all_games = self.find_all_games()
        
        # Filter for the specific game
        matching_games = []
        game_name_lower = game_name.lower()
        
        for game in all_games:
            if game_name_lower in game.name.lower():
                matching_games.append(game)
        
        return matching_games

    def find_fnv_installations(self) -> List[GameInfo]:
        """Find all Fallout New Vegas installations across platforms"""
        fnv_variants = [
            "Fallout New Vegas",
            "Fallout: New Vegas", 
            "Fallout: New Vegas Ultimate Edition",
            "FNV",
            "New Vegas"
        ]
        
        all_games = self.find_all_games()
        fnv_games = []
        
        self.logger.debug(f"Searching for FNV in {len(all_games)} games...")
        for game in all_games:
            game_name_lower = game.name.lower()
            self.logger.debug(f"Checking game: '{game.name}' -> '{game_name_lower}'")
            for variant in fnv_variants:
                if variant.lower() in game_name_lower:
                    self.logger.debug(f"Found FNV match: '{game.name}' matches variant '{variant}'")
                    fnv_games.append(game)
                    break
        
        self.logger.info(f"Found {len(fnv_games)} FNV installations")
        return fnv_games

    def find_enderal_installations(self) -> List[GameInfo]:
        """Find all Enderal installations across platforms"""
        enderal_variants = [
            "Enderal",
            "Enderal: Forgotten Stories",
            "Enderal SE"
        ]
        
        all_games = self.find_all_games()
        enderal_games = []
        
        for game in all_games:
            game_name_lower = game.name.lower()
            for variant in enderal_variants:
                if variant.lower() in game_name_lower:
                    enderal_games.append(game)
                    break
        
        return enderal_games

    def find_skyrim_installations(self) -> List[GameInfo]:
        """Find all Skyrim installations across platforms"""
        skyrim_variants = [
            "Skyrim",
            "The Elder Scrolls V: Skyrim",
            "Skyrim Special Edition",
            "Skyrim SE"
        ]
        
        all_games = self.find_all_games()
        skyrim_games = []
        
        for game in all_games:
            game_name_lower = game.name.lower()
            for variant in skyrim_variants:
                if variant.lower() in game_name_lower:
                    skyrim_games.append(game)
                    break
        
        return skyrim_games