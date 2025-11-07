"""
Base Installer Class

This module provides the base class for all mod manager installers.
It contains common functionality shared across MO2, Vortex, and Unverum installers.
"""

import os
from pathlib import Path
from typing import Optional, Callable

from src.utils.logger import get_logger
from src.utils.steam_utils import SteamUtils


class GitHubRelease:
    """GitHub release data structure"""

    def __init__(self, tag_name: str, assets: list):
        """
        Initialize a GitHub release

        Args:
            tag_name: Release tag name (e.g., "v2.5.0")
            assets: List of release assets
        """
        self.tag_name = tag_name
        self.assets = assets


class BaseInstaller:
    """
    Base class for mod manager installers

    Provides common functionality for:
    - Logging and progress callbacks
    - Cache management
    - Steam utilities integration

    All mod manager installers (MO2, Vortex, Unverum) should inherit from this class.
    """

    def __init__(self, core=None, installer_name: Optional[str] = None):
        """
        Initialize the base installer

        Args:
            core: Core instance (optional)
            installer_name: Name of the installer for logging (optional, uses class name if not provided)
        """
        # Setup logger - use provided name or class name
        logger_name = installer_name or self.__class__.__name__
        self.logger = get_logger(logger_name)

        # Initialize utilities
        self.steam_utils = SteamUtils()
        self.core = core

        # Initialize callbacks
        self.progress_callback: Optional[Callable] = None
        self.log_callback: Optional[Callable] = None

        # Log initialization
        self.logger.debug(f"{logger_name} initialized")

    def set_progress_callback(self, callback: Callable):
        """
        Set a callback function for progress updates

        Args:
            callback: Function to call with progress updates
                     Signature: callback(percent: float, current: int, total: int)
        """
        self.progress_callback = callback

    def set_log_callback(self, callback: Callable):
        """
        Set a callback function for log messages

        Args:
            callback: Function to call with log messages
                     Signature: callback(message: str)
        """
        self.log_callback = callback

    def _log_progress(self, message: str):
        """
        Log a progress message to both logger and callback

        Args:
            message: Progress message to log
        """
        self.logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def _send_progress_update(self, percent: float):
        """
        Send a progress percentage update to callback

        Args:
            percent: Progress percentage (0-100)
        """
        if self.progress_callback:
            # Call progress callback with percent, 0, 0 for non-download operations
            self.progress_callback(percent, 0, 0)

    def _cleanup_old_cache(self, current_filename: str, prefix: str, extension: Optional[str] = None):
        """
        Clean up old cached files that match the prefix

        This removes old cached files to save disk space, keeping only the current file.

        Args:
            current_filename: Current file to keep (don't delete this)
            prefix: Filename prefix to match (e.g., "ModOrganizer", "Vortex", "Unverum")
            extension: Optional file extension to require (e.g., ".7z")

        Example:
            self._cleanup_old_cache("ModOrganizer-2.5.0.7z", "ModOrganizer", ".7z")
            # This will remove: ModOrganizer-2.4.0.7z, ModOrganizer-2.3.0.7z, etc.
            # But keep: ModOrganizer-2.5.0.7z (current_filename)
        """
        try:
            cache_dir = Path.home() / "NaK" / "cache"
            if not cache_dir.exists():
                return

            # Remove old files that match the prefix
            for filepath in cache_dir.iterdir():
                filename = filepath.name

                # Check if this file matches our criteria
                matches_prefix = filename.startswith(prefix)
                is_not_current = filename != current_filename

                # Check extension if provided
                if extension:
                    matches_extension = filename.endswith(extension)
                else:
                    matches_extension = True

                # Remove if it matches all criteria
                if matches_prefix and is_not_current and matches_extension:
                    try:
                        filepath.unlink()
                        self.logger.info(f"Removed old cached file: {filename}")
                    except OSError as e:
                        self.logger.warning(f"Could not remove old cached file {filename}: {e}")

        except Exception as e:
            self.logger.warning(f"Error cleaning up old cache: {e}")

    def _get_cache_dir(self) -> Path:
        """
        Get the cache directory path

        Returns:
            Path to NaK cache directory
        """
        cache_dir = Path.home() / "NaK" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _setup_save_symlinks(self, install_dir: str, app_id: str, manager_name: str = "Mod Manager") -> dict:
        """
        Setup save game symlinks for all detected Bethesda games

        This method creates symlinks for game saves in two locations:
        1. "Save Games Folder" in the mod manager install directory
        2. Wine prefix compatdata directory

        Args:
            install_dir: Path to mod manager installation directory
            app_id: Steam AppID for the mod manager
            manager_name: Name of mod manager for logging (default: "Mod Manager")

        Returns:
            Dictionary with:
                - success: bool
                - message: str
                - games_symlinked: int
                - total_games: int (optional)
                - failed_games: list (optional)
        """
        try:
            self._log_progress("Setting up save game symlinks...")
            self.logger.info("===============================================================")
            self.logger.info(f"SETTING UP SAVE GAME SYMLINKS FOR {manager_name.upper()}")
            self.logger.info("===============================================================")
            self.logger.info(f"{manager_name} Install Directory: {install_dir}")
            self.logger.info(f"{manager_name} AppID: {app_id}")

            from src.utils.save_symlinker import SaveSymlinker
            symlinker = SaveSymlinker()

            # Create "Save Games Folder" in mod manager directory
            install_path = Path(install_dir)
            save_games_folder = install_path / "Save Games Folder"
            save_games_folder.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created Save Games Folder: {save_games_folder}")
            self._log_progress(f"Created Save Games Folder in {manager_name} directory")

            # Get all available Bethesda games
            available_games = symlinker.list_available_games()
            games_with_saves = [g for g in available_games if g['found']]

            if not games_with_saves:
                self.logger.info("No Bethesda games with saves found")
                return {
                    "success": True,
                    "message": "No Bethesda games with saves found to symlink",
                    "games_symlinked": 0
                }

            self.logger.info(f"Found {len(games_with_saves)} Bethesda game(s) with existing saves")
            symlinked_count = 0
            failed_games = []

            # Get mod manager compatdata path
            steam_root = self.steam_utils.get_steam_root()
            compatdata = Path(steam_root) / "steamapps" / "compatdata" / str(app_id)

            for game in games_with_saves:
                game_name = game['name']
                save_path = Path(game['save_path'])

                try:
                    self.logger.info(f"Setting up symlinks for {game_name}...")
                    self._log_progress(f"Setting up save symlinks for {game_name}...")

                    # 1. Create symlink in "Save Games Folder"
                    safe_game_name = game_name.replace(":", "").replace("/", "-")
                    folder_symlink = save_games_folder / safe_game_name

                    if not folder_symlink.exists():
                        folder_symlink.symlink_to(save_path, target_is_directory=True)
                        self.logger.info(f"  [OK] Created folder symlink: {folder_symlink} → {save_path}")
                    else:
                        self.logger.info(f"  [OK] Folder symlink already exists: {folder_symlink}")

                    # 2. Create symlink in mod manager prefix (compatdata)
                    location_type = game['location_type']
                    save_identifier = game['save_folder']

                    if location_type == "my_games":
                        # Create symlink in My Games
                        prefix_save_location = compatdata / "pfx" / "drive_c" / "users" / "steamuser" / "My Documents" / "My Games" / save_identifier
                        prefix_save_location.parent.mkdir(parents=True, exist_ok=True)

                        if not prefix_save_location.exists() and not prefix_save_location.is_symlink():
                            prefix_save_location.symlink_to(save_path, target_is_directory=True)
                            self.logger.info(f"  [OK] Created prefix symlink: {prefix_save_location} → {save_path}")
                        else:
                            self.logger.info(f"  [OK] Prefix symlink already exists: {prefix_save_location}")

                    symlinked_count += 1
                    self.logger.info(f"  [OK] Successfully set up symlinks for {game_name}")

                except Exception as e:
                    self.logger.error(f"  [FAILED] Failed to setup symlinks for {game_name}: {e}")
                    failed_games.append(game_name)

            result_message = f"Set up save symlinks for {symlinked_count}/{len(games_with_saves)} game(s)"
            if failed_games:
                result_message += f" ({len(failed_games)} failed: {', '.join(failed_games)})"

            self.logger.info("===============================================================")
            self.logger.info("SAVE SYMLINK SETUP COMPLETE")
            self.logger.info("===============================================================")
            self.logger.info(result_message)
            self._log_progress(result_message)

            return {
                "success": True,
                "message": result_message,
                "games_symlinked": symlinked_count,
                "total_games": len(games_with_saves),
                "failed_games": failed_games
            }

        except Exception as e:
            self.logger.error(f"Failed to setup save symlinks: {e}")
            return {
                "success": False,
                "error": str(e),
                "games_symlinked": 0
            }

    def _extract_archive(self, archive_path: str, extract_dir: str, search_pattern: Optional[str] = None) -> Optional[str]:
        """
        Extract archive to installation directory

        Args:
            archive_path: Path to archive file
            extract_dir: Directory to extract to
            search_pattern: Optional pattern to search for in extracted directory (case-insensitive)

        Returns:
            Path to extracted directory, or None if extraction failed
        """
        try:
            self.logger.info(f"Extracting {archive_path} to {extract_dir}")

            # Determine extraction method based on file extension
            if archive_path.endswith('.7z'):
                return self._extract_7z(archive_path, extract_dir, search_pattern)
            elif archive_path.endswith('.zip'):
                return self._extract_zip(archive_path, extract_dir, search_pattern)
            else:
                self.logger.error(f"Unsupported archive format: {archive_path}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to extract archive: {e}")
            return None

    def _extract_7z(self, archive_path: str, extract_dir: str, search_pattern: Optional[str] = None) -> Optional[str]:
        """
        Extract 7z archive

        Args:
            archive_path: Path to 7z file
            extract_dir: Directory to extract to
            search_pattern: Optional pattern to search for in extracted directory (case-insensitive)

        Returns:
            Path to extracted directory, or None if extraction failed
        """
        try:
            import subprocess
            import os

            self.logger.info(f"Extracting 7z archive: {archive_path}")
            self.logger.info(f"Extraction directory: {extract_dir}")

            # Create clean environment to avoid AppImage library conflicts
            # Remove AppImage-specific env vars that can cause symbol lookup errors
            env = os.environ.copy()
            appimage_vars = [
                'APPIMAGE', 'APPDIR', 'OWD', 'ARGV0',
                'LD_LIBRARY_PATH', 'LIBRARY_PATH', 'LD_PRELOAD',
                'PYTHONHOME', 'PYTHONPATH'
            ]
            for var in appimage_vars:
                env.pop(var, None)

            # Try to use 7z command with increased timeout (5 minutes for large archives)
            cmd = ["7z", "x", archive_path, f"-o{extract_dir}", "-y"]
            self.logger.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)

            if result.returncode == 0:
                self.logger.info("7z extraction completed successfully")
                self.logger.debug(f"7z stdout: {result.stdout[:500]}")

                # Find the extracted directory
                extracted_items = os.listdir(extract_dir)
                self.logger.info(f"Extracted items: {extracted_items}")

                if search_pattern:
                    # Search for directory matching pattern
                    for item in extracted_items:
                        item_path = os.path.join(extract_dir, item)
                        if os.path.isdir(item_path) and search_pattern.lower() in item.lower():
                            self.logger.info(f"Found matching directory: {item_path}")
                            return item_path

                    # Fallback: return the extract directory itself
                    self.logger.warning(f"No '{search_pattern}' directory found, using extract_dir: {extract_dir}")
                    return extract_dir
                else:
                    # No search pattern, just return extract dir
                    return extract_dir
            else:
                self.logger.error(f"7z extraction failed with return code: {result.returncode}")
                self.logger.error(f"7z stderr: {result.stderr}")
                self.logger.error(f"7z stdout: {result.stdout}")
                return None

        except FileNotFoundError:
            self.logger.error("7z command not found. Please install p7zip-full package.")
            self.logger.error("Install with: sudo apt-get install p7zip-full")
            return None
        except subprocess.TimeoutExpired:
            self.logger.error(f"7z extraction timed out after 300 seconds")
            self.logger.error(f"Archive may be corrupted or too large: {archive_path}")
            return None
        except Exception as e:
            self.logger.error(f"7z extraction error: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _extract_zip(self, archive_path: str, extract_dir: str, search_pattern: Optional[str] = None) -> Optional[str]:
        """
        Extract zip archive

        Args:
            archive_path: Path to zip file
            extract_dir: Directory to extract to
            search_pattern: Optional pattern to search for in extracted directory (case-insensitive)

        Returns:
            Path to extracted directory, or None if extraction failed
        """
        try:
            import zipfile
            import os

            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            if search_pattern:
                # Find the extracted directory matching pattern
                for item in os.listdir(extract_dir):
                    item_path = os.path.join(extract_dir, item)
                    if os.path.isdir(item_path) and search_pattern.lower() in item.lower():
                        self.logger.info(f"Extracted to: {item_path}")
                        return item_path

                # Fallback: return the extract directory itself
                return extract_dir
            else:
                # No search pattern, just return extract dir
                return extract_dir

        except Exception as e:
            self.logger.error(f"Zip extraction error: {e}")
            return None
