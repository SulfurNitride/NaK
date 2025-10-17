"""
Save Game Symlinker
Manages symlinks between game save locations for seamless save sharing between
original games and MO2-launched modded versions
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional, List
import shutil


class SaveSymlinker:
    """Manages save game symlinks for Bethesda games"""

    # Bethesda game configurations
    # Format: Game Name: (Steam AppID, Save Identifier, Save Location Type, Game Install Path, Custom Save Subdir)
    # Save Location Types:
    #   - "my_games": Uses My Documents/My Games/<folder>
    #   - "install_dir_saves": Saves in game install directory/Saves/
    #   - "install_dir_data": Saves in game install directory/data/savegame/
    #   - "install_dir_custom": Saves in game install directory/<custom_subdir>/
    #   - "virtualstore": Uses VirtualStore location
    BETHESDA_GAMES = {
        # Classic games (DOS/early Windows)
        "Fallout 1": (38400, "Fallout", "install_dir_data", "Fallout", None),
        "Fallout 2": (38410, "Fallout 2", "install_dir_data", "Fallout 2", None),
        "The Elder Scrolls: Arena": (1812290, "Arena", "install_dir_custom", "The Elder Scrolls Arena", "ARENA"),
        "The Elder Scrolls II: Daggerfall": (1812390, "Daggerfall", "install_dir_custom", "The Elder Scrolls Daggerfall", "DF/DAGGER"),

        # Modern games using My Games
        "Morrowind": (22320, "Morrowind", "install_dir_saves", "Morrowind", None),  # Special case: multiple locations
        "Oblivion": (22330, "Oblivion", "my_games", "Oblivion", None),
        "Fallout 3": (22370, "Fallout3", "my_games", "Fallout 3 goty", None),
        "Fallout: New Vegas": (22380, "FalloutNV", "my_games", "Fallout New Vegas", None),
        "Skyrim": (72850, "Skyrim", "my_games", None, None),
        "Skyrim Special Edition": (489830, "Skyrim Special Edition", "my_games", "Skyrim Special Edition", None),
        "Fallout 4": (377160, "Fallout4", "my_games", "Fallout 4", None),
        "Starfield": (1716740, "Starfield", "my_games", None, None),
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.steam_paths = [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
        ]

    def get_compatdata_path(self, appid: str) -> Optional[Path]:
        """Get the compatdata path for a given Steam AppID"""
        for steam_path in self.steam_paths:
            compatdata = steam_path / "steamapps" / "compatdata" / str(appid)
            if compatdata.exists():
                return compatdata
        return None

    def get_game_install_path(self, appid: str, game_install_folder: str) -> Optional[Path]:
        """
        Get the game installation directory inside the Proton prefix

        Args:
            appid: Steam AppID
            game_install_folder: Expected game folder name (e.g., "Fallout", "Morrowind")

        Returns:
            Path to game installation or None if not found
        """
        compatdata = self.get_compatdata_path(appid)
        if not compatdata:
            return None

        # Common Steam installation paths within Proton prefix
        possible_paths = [
            compatdata / "pfx" / "drive_c" / "Program Files (x86)" / "Steam" / "steamapps" / "common" / game_install_folder,
            compatdata / "pfx" / "drive_c" / "Program Files" / "Steam" / "steamapps" / "common" / game_install_folder,
            compatdata / "pfx" / "drive_c" / "GOG Games" / game_install_folder,
            compatdata / "pfx" / "drive_c" / "Program Files (x86)" / "GOG.com" / game_install_folder,
        ]

        # Also check the actual Steam common directory (symlinked or directly accessible)
        for steam_path in self.steam_paths:
            real_install = steam_path / "steamapps" / "common" / game_install_folder
            if real_install.exists():
                return real_install

        for path in possible_paths:
            if path.exists():
                return path

        return None

    def get_save_location(self, appid: str, save_identifier: str, location_type: str, game_install_folder: Optional[str] = None, custom_save_subdir: Optional[str] = None) -> Optional[Path]:
        """
        Get the save game location for a given game

        Args:
            appid: Steam AppID
            save_identifier: Identifier for saves (folder name or game name)
            location_type: Type of save location ("my_games", "install_dir_saves", "install_dir_data", "install_dir_custom", "virtualstore")
            game_install_folder: Game installation folder name (for install_dir types)
            custom_save_subdir: Custom subdirectory path for saves (used with install_dir_custom)

        Returns:
            Path to save location or None if not found
        """
        compatdata = self.get_compatdata_path(appid)
        if not compatdata:
            return None

        if location_type == "my_games":
            # Modern Bethesda games: compatdata/<appid>/pfx/drive_c/users/steamuser/My Documents/My Games/<GameFolder>
            save_path = compatdata / "pfx" / "drive_c" / "users" / "steamuser" / "My Documents" / "My Games" / save_identifier
            return save_path if save_path.exists() else None

        elif location_type == "install_dir_saves":
            # Games that store saves in installation directory /Saves/ (Morrowind)
            # First check the real Steam common directory
            for steam_path in self.steam_paths:
                real_install = steam_path / "steamapps" / "common" / game_install_folder / "Saves"
                if real_install.exists():
                    self.logger.info(f"Found saves in real Steam directory: {real_install}")
                    return real_install

            # Then check inside Proton prefix
            game_install = self.get_game_install_path(appid, game_install_folder) if game_install_folder else None
            if game_install:
                save_path = game_install / "Saves"
                if save_path.exists():
                    return save_path

            # For Morrowind, also check VirtualStore as fallback
            if save_identifier == "Morrowind":
                virtualstore_path = compatdata / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "VirtualStore" / "Program Files (x86)" / "Bethesda Softworks" / "Morrowind" / "Saves"
                if virtualstore_path.exists():
                    self.logger.info(f"Found Morrowind saves in VirtualStore: {virtualstore_path}")
                    return virtualstore_path

            return None

        elif location_type == "install_dir_data":
            # Classic games (Fallout 1/2): stores saves in installation directory /data/savegame/ or /DATA/SAVEGAME/
            # First check the real Steam common directory
            for steam_path in self.steam_paths:
                real_install = steam_path / "steamapps" / "common" / game_install_folder
                if real_install.exists():
                    # Try both lowercase and uppercase (DOS games often use uppercase)
                    for data_path in ["data/savegame", "DATA/SAVEGAME", "Data/Savegame"]:
                        save_path = real_install / data_path
                        if save_path.exists():
                            self.logger.info(f"Found saves in real Steam directory: {save_path}")
                            return save_path

            # Then check inside Proton prefix (less common for classic games)
            game_install = self.get_game_install_path(appid, game_install_folder) if game_install_folder else None
            if game_install:
                for data_path in ["data/savegame", "DATA/SAVEGAME", "Data/Savegame"]:
                    save_path = game_install / data_path
                    if save_path.exists():
                        return save_path
            return None

        elif location_type == "install_dir_custom":
            # Classic games with custom save subdirectories (Arena: ARENA, Daggerfall: DF/DAGGER)
            if not custom_save_subdir or not game_install_folder:
                return None

            # First check the real Steam common directory
            for steam_path in self.steam_paths:
                real_install = steam_path / "steamapps" / "common" / game_install_folder / custom_save_subdir
                if real_install.exists():
                    self.logger.info(f"Found saves in real Steam directory: {real_install}")
                    return real_install

            # Then check inside Proton prefix
            game_install = self.get_game_install_path(appid, game_install_folder)
            if game_install:
                save_path = game_install / custom_save_subdir
                if save_path.exists():
                    return save_path
            return None

        elif location_type == "virtualstore":
            # VirtualStore location (for games not running as admin)
            virtualstore_path = compatdata / "pfx" / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "VirtualStore" / "Program Files (x86)" / "Bethesda Softworks" / save_identifier / "Saves"
            return virtualstore_path if virtualstore_path.exists() else None

        return None

    def create_mo2_game_saves_folder(self, mo2_install_path: Path) -> Path:
        """
        Create a Game Saves folder inside the MO2 installation

        Args:
            mo2_install_path: Path to MO2 installation (e.g., prefix/drive_c/Modding/MO2)

        Returns:
            Path to the Game Saves folder
        """
        game_saves_path = mo2_install_path / "Game Saves"
        game_saves_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Created Game Saves folder at: {game_saves_path}")
        return game_saves_path

    def symlink_save_to_mo2_folder(
        self,
        game_name: str,
        original_save_path: Path,
        mo2_game_saves_folder: Path
    ) -> bool:
        """
        Create a symlink from the game's save location to the MO2 Game Saves folder

        Args:
            game_name: Name of the game (e.g., "Skyrim Special Edition")
            original_save_path: Path to the original game's save location
            mo2_game_saves_folder: Path to MO2's Game Saves folder

        Returns:
            True if symlink created successfully, False otherwise
        """
        # Create a sanitized folder name
        safe_game_name = game_name.replace(":", "").replace("/", "-")
        symlink_path = mo2_game_saves_folder / safe_game_name

        # If symlink already exists and points to the correct location, skip
        if symlink_path.exists() or symlink_path.is_symlink():
            if symlink_path.is_symlink() and symlink_path.resolve() == original_save_path.resolve():
                self.logger.info(f"Symlink already exists for {game_name}: {symlink_path} -> {original_save_path}")
                return True
            else:
                self.logger.warning(f"Removing old/broken symlink for {game_name}: {symlink_path}")
                try:
                    symlink_path.unlink()
                except Exception as e:
                    self.logger.error(f"Failed to remove old symlink: {e}")
                    return False

        # Create the symlink
        try:
            symlink_path.symlink_to(original_save_path, target_is_directory=True)
            self.logger.info(f"Created symlink: {symlink_path} -> {original_save_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create symlink for {game_name}: {e}")
            return False

    def sync_saves_between_prefixes(
        self,
        source_appid: str,
        target_appid: str,
        save_identifier: str,
        location_type: str,
        game_install_folder: Optional[str] = None,
        custom_save_subdir: Optional[str] = None
    ) -> bool:
        """
        Create a symlink between two game prefixes (e.g., original game and MO2 non-Steam shortcut)

        Args:
            source_appid: Source game's Steam AppID (the original game)
            target_appid: Target game's Steam AppID (the MO2 non-Steam shortcut)
            save_identifier: Identifier for saves (folder name or game name)
            location_type: Type of save location
            game_install_folder: Game installation folder name (for install_dir types)
            custom_save_subdir: Custom subdirectory path for saves (used with install_dir_custom)

        Returns:
            True if symlink created successfully, False otherwise
        """
        source_save_path = self.get_save_location(source_appid, save_identifier, location_type, game_install_folder, custom_save_subdir)
        target_compatdata = self.get_compatdata_path(target_appid)

        if not source_save_path:
            self.logger.warning(f"Source save location not found for AppID {source_appid}")
            return False

        if not target_compatdata:
            self.logger.warning(f"Target compatdata not found for AppID {target_appid}")
            return False

        # Build the target path based on location type
        if location_type == "my_games":
            target_save_path = target_compatdata / "pfx" / "drive_c" / "users" / "steamuser" / "My Documents" / "My Games" / save_identifier
        elif location_type == "install_dir_saves":
            # For install_dir types, symlink at the same level in target prefix
            game_install = self.get_game_install_path(target_appid, game_install_folder) if game_install_folder else None
            if not game_install:
                self.logger.warning(f"Could not find game installation in target prefix")
                return False
            target_save_path = game_install / "Saves"
        elif location_type == "install_dir_data":
            game_install = self.get_game_install_path(target_appid, game_install_folder) if game_install_folder else None
            if not game_install:
                self.logger.warning(f"Could not find game installation in target prefix")
                return False
            target_save_path = game_install / "data" / "savegame"
        elif location_type == "install_dir_custom":
            if not custom_save_subdir or not game_install_folder:
                self.logger.error(f"Missing custom_save_subdir or game_install_folder for install_dir_custom type")
                return False
            game_install = self.get_game_install_path(target_appid, game_install_folder)
            if not game_install:
                self.logger.warning(f"Could not find game installation in target prefix")
                return False
            target_save_path = game_install / custom_save_subdir
        else:
            self.logger.error(f"Unsupported location type for prefix sync: {location_type}")
            return False

        # Create parent directories if they don't exist
        target_save_path.parent.mkdir(parents=True, exist_ok=True)

        # If target already exists and is a symlink pointing to source, we're done
        if target_save_path.exists() or target_save_path.is_symlink():
            if target_save_path.is_symlink() and target_save_path.resolve() == source_save_path.resolve():
                self.logger.info(f"Symlink already exists: {target_save_path} -> {source_save_path}")
                return True
            else:
                # If it's a real directory with saves, we should back it up first
                if target_save_path.is_dir() and not target_save_path.is_symlink():
                    backup_path = target_save_path.parent / f"{save_identifier}_backup"
                    self.logger.warning(f"Target path exists as real directory, backing up to: {backup_path}")
                    try:
                        shutil.move(str(target_save_path), str(backup_path))
                    except Exception as e:
                        self.logger.error(f"Failed to backup existing save directory: {e}")
                        return False
                else:
                    # Remove broken symlink
                    try:
                        target_save_path.unlink()
                    except Exception as e:
                        self.logger.error(f"Failed to remove old symlink: {e}")
                        return False

        # Create the symlink
        try:
            target_save_path.symlink_to(source_save_path, target_is_directory=True)
            self.logger.info(f"Created symlink: {target_save_path} -> {source_save_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create symlink: {e}")
            return False

    def setup_game_save_symlinks(
        self,
        game_name: str,
        mo2_install_path: Path,
        original_appid: Optional[str] = None,
        mo2_shortcut_appid: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Set up all save symlinks for a game

        Args:
            game_name: Name of the game (must match BETHESDA_GAMES key)
            mo2_install_path: Path to MO2 installation
            original_appid: Original game's AppID (if None, uses default from BETHESDA_GAMES)
            mo2_shortcut_appid: MO2 non-Steam shortcut's AppID

        Returns:
            Dict with status of each operation
        """
        results = {
            "mo2_folder_created": False,
            "mo2_symlink_created": False,
            "prefix_sync_created": False
        }

        # Get game configuration
        if game_name not in self.BETHESDA_GAMES:
            self.logger.error(f"Unknown game: {game_name}")
            return results

        game_appid, save_identifier, location_type, game_install_folder, custom_save_subdir = self.BETHESDA_GAMES[game_name]
        if original_appid is None:
            original_appid = str(game_appid)

        # Step 1: Create MO2 Game Saves folder
        try:
            game_saves_folder = self.create_mo2_game_saves_folder(mo2_install_path)
            results["mo2_folder_created"] = True
        except Exception as e:
            self.logger.error(f"Failed to create MO2 Game Saves folder: {e}")
            return results

        # Step 2: Get original game save location
        original_save_path = self.get_save_location(original_appid, save_identifier, location_type, game_install_folder, custom_save_subdir)
        if not original_save_path:
            self.logger.warning(f"Could not find save location for {game_name} (AppID: {original_appid})")
            return results

        # Step 3: Create symlink to MO2 Game Saves folder
        results["mo2_symlink_created"] = self.symlink_save_to_mo2_folder(
            game_name,
            original_save_path,
            game_saves_folder
        )

        # Step 4: Sync saves between original game and MO2 non-Steam shortcut (if provided)
        if mo2_shortcut_appid:
            results["prefix_sync_created"] = self.sync_saves_between_prefixes(
                original_appid,
                mo2_shortcut_appid,
                save_identifier,
                location_type,
                game_install_folder,
                custom_save_subdir
            )

        return results

    def is_game_installed(self, appid: str, game_install_folder: Optional[str] = None) -> bool:
        """
        Check if a game is installed (has compatdata or installation directory)

        Args:
            appid: Steam AppID
            game_install_folder: Game installation folder name

        Returns:
            True if game is installed, False otherwise
        """
        # Check if compatdata exists (game has been run at least once)
        compatdata = self.get_compatdata_path(appid)
        if compatdata and compatdata.exists():
            return True

        # For games in installation directory, check if the game folder exists
        if game_install_folder:
            game_install = self.get_game_install_path(appid, game_install_folder)
            if game_install and game_install.exists():
                return True

        return False

    def get_or_create_save_location(self, appid: str, save_identifier: str, location_type: str, game_install_folder: Optional[str] = None, custom_save_subdir: Optional[str] = None) -> Optional[Path]:
        """
        Get the save location for a game, creating the directory structure if needed

        Args:
            appid: Steam AppID
            save_identifier: Identifier for saves (folder name or game name)
            location_type: Type of save location
            game_install_folder: Game installation folder name (for install_dir types)
            custom_save_subdir: Custom subdirectory path for saves (used with install_dir_custom)

        Returns:
            Path to save location (created if necessary) or None if game not installed
        """
        # First check if the save location already exists
        existing_path = self.get_save_location(appid, save_identifier, location_type, game_install_folder, custom_save_subdir)
        if existing_path:
            return existing_path

        # Game doesn't have saves yet - check if it's installed
        if not self.is_game_installed(appid, game_install_folder):
            return None

        # Game is installed but hasn't created saves yet - create the directory structure
        compatdata = self.get_compatdata_path(appid)
        if not compatdata:
            return None

        try:
            if location_type == "my_games":
                save_path = compatdata / "pfx" / "drive_c" / "users" / "steamuser" / "My Documents" / "My Games" / save_identifier
                save_path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created save directory for {save_identifier}: {save_path}")
                return save_path

            elif location_type == "install_dir_saves":
                # Check real Steam directory first
                for steam_path in self.steam_paths:
                    real_install = steam_path / "steamapps" / "common" / game_install_folder
                    if real_install.exists():
                        save_path = real_install / "Saves"
                        save_path.mkdir(parents=True, exist_ok=True)
                        self.logger.info(f"Created save directory: {save_path}")
                        return save_path

                # Then try in Proton prefix
                game_install = self.get_game_install_path(appid, game_install_folder) if game_install_folder else None
                if game_install:
                    save_path = game_install / "Saves"
                    save_path.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"Created save directory: {save_path}")
                    return save_path

            elif location_type == "install_dir_data":
                # Check real Steam directory first
                for steam_path in self.steam_paths:
                    real_install = steam_path / "steamapps" / "common" / game_install_folder
                    if real_install.exists():
                        # Try both lowercase and uppercase (DOS games often use uppercase)
                        for data_path in ["DATA/SAVEGAME", "data/savegame", "Data/Savegame"]:
                            save_path = real_install / data_path
                            if save_path.exists():
                                self.logger.info(f"Found existing save directory: {save_path}")
                                return save_path
                        # If none exist, create using uppercase (DOS convention)
                        save_path = real_install / "DATA" / "SAVEGAME"
                        save_path.mkdir(parents=True, exist_ok=True)
                        self.logger.info(f"Created save directory: {save_path}")
                        return save_path

                # Then try in Proton prefix
                game_install = self.get_game_install_path(appid, game_install_folder) if game_install_folder else None
                if game_install:
                    save_path = game_install / "data" / "savegame"
                    save_path.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"Created save directory: {save_path}")
                    return save_path

            elif location_type == "install_dir_custom":
                # Check real Steam directory first
                if custom_save_subdir and game_install_folder:
                    for steam_path in self.steam_paths:
                        real_install = steam_path / "steamapps" / "common" / game_install_folder
                        if real_install.exists():
                            save_path = real_install / custom_save_subdir
                            if save_path.exists():
                                self.logger.info(f"Found existing save directory: {save_path}")
                                return save_path
                            # Create the custom save directory
                            save_path.mkdir(parents=True, exist_ok=True)
                            self.logger.info(f"Created save directory: {save_path}")
                            return save_path

                    # Then try in Proton prefix
                    game_install = self.get_game_install_path(appid, game_install_folder)
                    if game_install:
                        save_path = game_install / custom_save_subdir
                        save_path.mkdir(parents=True, exist_ok=True)
                        self.logger.info(f"Created save directory: {save_path}")
                        return save_path

        except Exception as e:
            self.logger.error(f"Failed to create save directory: {e}")

        return None

    def list_available_games(self) -> List[Dict[str, any]]:
        """
        List all Bethesda games that are installed on this system

        Returns:
            List of dicts with game info: {name, appid, save_path, found, installed, location_type}
        """
        available_games = []

        for game_name, (appid, save_identifier, location_type, game_install_folder, custom_save_subdir) in self.BETHESDA_GAMES.items():
            # Check if game is installed
            installed = self.is_game_installed(str(appid), game_install_folder)

            # Try to get existing save location
            save_path = self.get_save_location(str(appid), save_identifier, location_type, game_install_folder, custom_save_subdir)

            # Get the expected save path (will create if game is installed but no saves yet)
            expected_save_path = self.get_or_create_save_location(str(appid), save_identifier, location_type, game_install_folder, custom_save_subdir) if installed else None

            available_games.append({
                "name": game_name,
                "appid": appid,
                "save_folder": save_identifier,
                "location_type": location_type,
                "save_path": str(expected_save_path) if expected_save_path else None,
                "found": save_path is not None,
                "installed": installed
            })

        return available_games
