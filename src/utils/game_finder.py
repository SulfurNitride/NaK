"""
Native Python GameFinder
Pure Python implementation for finding games across Heroic and Steam platforms
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from src.utils.logger import get_logger


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
    """GameFinder using pure Python implementation"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.detected_games: List[GameInfo] = []
        self.logger.debug("GameFinder initialized (Pure Python mode)")

    def find_all_games(self) -> List[GameInfo]:
        """Find all games using pure Python detection"""
        self.detected_games.clear()
        self.logger.debug("Using pure Python detection...")
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

        self.logger.debug(f"Detected {len(self.detected_games)} games across all platforms")
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
        
        # Also scan common Heroic game directories for MO2 installations
        heroic_game_dirs = [
            Path.home() / "Games" / "Heroic",
            Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "Games",
        ]

        for games_dir in heroic_game_dirs:
            if not games_dir.exists():
                continue

            try:
                self.logger.debug(f"Scanning Heroic games directory for MO2: {games_dir}")
                for folder in games_dir.iterdir():
                    if not folder.is_dir():
                        continue

                    # Look for ModOrganizer.exe in this folder and its subdirectories
                    mo2_exe_paths = []

                    # Check root folder
                    root_mo2_exe = folder / "ModOrganizer.exe"
                    if root_mo2_exe.exists():
                        mo2_exe_paths.append(root_mo2_exe)

                    # Check one level deep (e.g., folder/modorganizer2/ModOrganizer.exe)
                    for subfolder in folder.glob("*/ModOrganizer.exe"):
                        if subfolder.exists():
                            mo2_exe_paths.append(subfolder)

                    # If we found MO2, add it as a detected game
                    for mo2_exe in mo2_exe_paths:
                        mo2_folder = mo2_exe.parent

                        # Check if we already added this MO2 installation
                        already_added = any(
                            g.exe_path == str(mo2_exe) for g in games
                        )

                        if not already_added:
                            # Try to infer a friendly name from the folder structure
                            folder_name = folder.name
                            if folder_name.startswith("mod-organizer"):
                                # Extract game name from folder like "mod-organizer-2-cyberpunk2077"
                                parts = folder_name.split("-")
                                if len(parts) > 3:
                                    game_hint = " ".join(parts[3:]).title()
                                    mo2_name = f"Mod Organizer 2 - {game_hint}"
                                else:
                                    mo2_name = f"Mod Organizer 2 ({folder_name})"
                            else:
                                mo2_name = f"Mod Organizer 2 ({folder_name})"

                            # Try to find the Heroic prefix for this MO2 installation
                            prefix_path = None
                            try:
                                # Look for prefix by checking if mo2_folder contains drive_c marker
                                for parent in mo2_folder.parents:
                                    if parent.name.lower() == "drive_c":
                                        prefix_path = str(parent.parent)
                                        self.logger.info(f"Found prefix from drive_c marker: {prefix_path}")
                                        break

                                # If no drive_c found, check common Heroic prefix locations
                                if not prefix_path:
                                    home_dir = Path.home()
                                    heroic_prefix_locations = [
                                        home_dir / "Games" / "Heroic" / "Prefixes",
                                        home_dir / ".config" / "heroic" / "prefixes",
                                        home_dir / ".local" / "share" / "heroic" / "prefixes",
                                        home_dir / ".var" / "app" / "com.heroicgameslauncher.hgl" / "data" / "heroic" / "prefixes"
                                    ]

                                    for prefix_dir in heroic_prefix_locations:
                                        if prefix_dir.exists():
                                            for prefix_path_candidate in prefix_dir.iterdir():
                                                if prefix_path_candidate.is_dir():
                                                    drive_c = prefix_path_candidate / "drive_c"
                                                    if drive_c.exists():
                                                        # Check if MO2 is under this prefix
                                                        try:
                                                            mo2_folder.relative_to(drive_c)
                                                            prefix_path = str(prefix_path_candidate)
                                                            self.logger.info(f"Found Heroic prefix containing MO2: {prefix_path}")
                                                            break
                                                        except ValueError:
                                                            continue
                                            if prefix_path:
                                                break
                            except Exception as e:
                                self.logger.debug(f"Failed to detect prefix for MO2: {e}")

                            games.append(GameInfo(
                                name=mo2_name,
                                path=str(mo2_folder),
                                platform="Heroic (MO2)",
                                app_id=f"mo2_{folder_name.lower().replace(' ', '_')}",
                                exe_path=str(mo2_exe),
                                install_dir=str(mo2_folder),
                                prefix_path=prefix_path
                            ))
                            self.logger.info(f"Found MO2 installation in Heroic games: {mo2_name} at {mo2_folder}")
                            if prefix_path:
                                self.logger.info(f"  Detected prefix: {prefix_path}")

            except Exception as e:
                self.logger.debug(f"Failed to scan Heroic games directory {games_dir}: {e}")

        self.logger.debug(f"Found {len(games)} manually added Heroic games")
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

    def _get_steam_compatdata_prefix(self, app_id: str) -> Optional[str]:
        """Get the Wine prefix path for a Steam game's compatdata (supports native and Flatpak Steam)

        Args:
            app_id: Steam AppID

        Returns:
            Path to the pfx directory, or None if not found
        """
        steam_paths = [
            # Native Steam locations
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
            # Flatpak Steam location
            Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
        ]

        for steam_path in steam_paths:
            compatdata_path = steam_path / "steamapps" / "compatdata" / str(app_id) / "pfx"
            if compatdata_path.exists():
                return str(compatdata_path)

        return None

    def _get_steam_library_folders(self) -> List[Path]:
        """Get all Steam library folders from libraryfolders.vdf"""
        library_folders = []
        home = Path.home()
        
        # Common Steam config paths
        steam_config_paths = [
            home / ".steam" / "steam" / "steamapps" / "libraryfolders.vdf",
            home / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf",
            home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam" / "steamapps" / "libraryfolders.vdf"
        ]

        # Also check for main steamapps folders directly as fallback
        main_steamapps_paths = [
            home / ".steam" / "steam" / "steamapps",
            home / ".local" / "share" / "Steam" / "steamapps",
            home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam" / "steamapps"
        ]
        
        # First, try to find and parse libraryfolders.vdf
        vdf_found = False
        for vdf_path in steam_config_paths:
            if vdf_path.exists():
                try:
                    self.logger.debug(f"Parsing library folders from: {vdf_path}")
                    with open(vdf_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Simple VDF parsing to find "path" keys
                    # Format is typically: "path" "/path/to/library"
                    import re
                    # Match "path" followed by whitespace and then a quoted string
                    matches = re.finditer(r'"path"\s+"([^"]+)"', content)
                    
                    for match in matches:
                        path_str = match.group(1)
                        # Clean up path (sometimes has double backslashes on Windows/Wine, but usually standard on Linux)
                        library_path = Path(path_str) / "steamapps"
                        if library_path.exists():
                            if library_path not in library_folders:
                                library_folders.append(library_path)
                                self.logger.debug(f"Found Steam library: {library_path}")
                                vdf_found = True
                                
                except Exception as e:
                    self.logger.warning(f"Failed to parse {vdf_path}: {e}")
        
        # Fallback: If no VDF parsed or to ensure main library is included
        for steamapps in main_steamapps_paths:
            if steamapps.exists() and steamapps not in library_folders:
                library_folders.append(steamapps)
                self.logger.debug(f"Found main Steam library (fallback): {steamapps}")

        return library_folders

    def _find_steam_games(self) -> List[GameInfo]:
        """Find Steam games using ACF file parsing with deduplication across all Steam library folders"""
        games = []
        seen_games = {}  # Track app_id -> GameInfo to avoid duplicates across symlinked paths

        # Get all Steam library folders (including additional libraries)
        library_folders = self._get_steam_library_folders()
        self.logger.debug(f"Scanning {len(library_folders)} Steam library folder(s) for games...")

        for steamapps in library_folders:
            self.logger.debug(f"Scanning library folder: {steamapps}")
            acf_count = 0

            for acf_file in steamapps.glob("appmanifest_*.acf"):
                acf_count += 1
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

                        # Get Steam compatdata prefix path
                        prefix_path = self._get_steam_compatdata_prefix(app_id)

                        game_info = GameInfo(
                            name=name,
                            path=str(game_path),
                            platform="Steam",
                            app_id=app_id,
                            install_dir=install_dir,
                            prefix_path=prefix_path
                        )
                        games.append(game_info)
                        seen_games[app_id] = game_info  # Track by app_id to deduplicate across symlinked paths
                        self.logger.debug(f"Found Steam game: {name} (AppID: {app_id})" + (f" with prefix: {prefix_path}" if prefix_path else ""))

                except Exception as e:
                    self.logger.warning(f"Failed to parse {acf_file}: {e}")

            self.logger.debug(f"Found {acf_count} ACF file(s) in {steamapps}")

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