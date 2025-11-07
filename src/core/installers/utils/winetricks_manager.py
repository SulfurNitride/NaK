"""
Winetricks Manager

This module provides winetricks management functionality for mod manager installers.
It handles downloading, caching, and locating winetricks.
"""

import os
import sys
import stat
import time
from pathlib import Path
from typing import Optional

import requests

from src.utils.logger import get_logger


class WinetricksManager:
    """
    Manages winetricks download, caching, and location

    This class provides a centralized way to get winetricks for dependency installation.
    It handles:
    - Downloading latest winetricks from GitHub
    - Caching winetricks locally (expires after 7 days)
    - Fallback to bundled winetricks (PyInstaller, AppImage, or local)
    - Auto-updating old cached versions
    """

    # Cache expiration in days
    CACHE_EXPIRATION_DAYS = 7

    # GitHub URL for latest winetricks
    WINETRICKS_URL = "https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks"

    def __init__(self):
        """Initialize winetricks manager"""
        self.logger = get_logger(__name__)
        self.cache_dir = Path.home() / "NaK" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cached_winetricks = self.cache_dir / "winetricks"

    def get_winetricks(self) -> Optional[str]:
        """
        Get winetricks command path

        Always uses cached winetricks downloaded from GitHub for latest version.
        No longer uses bundled winetricks to ensure we always have the newest version.

        Priority order:
        1. Cached winetricks (downloaded from GitHub, auto-updates every 7 days)
        2. Download fresh if not cached

        Returns:
            Path to winetricks command, or None if failed to download
        """
        # ALWAYS prefer cached/downloaded winetricks for latest version
        if self._ensure_cached_winetricks():
            self.logger.info(f"Using cached winetricks: {self.cached_winetricks}")
            return str(self.cached_winetricks)

        # If we get here, download failed - this is an error
        self.logger.error("Failed to get winetricks - download unsuccessful")
        return None

    def _ensure_cached_winetricks(self) -> bool:
        """
        Ensure cached winetricks exists and is up-to-date

        Downloads winetricks if:
        - Not cached
        - Cached version is older than CACHE_EXPIRATION_DAYS

        Returns:
            True if cached winetricks is available, False otherwise
        """
        should_download = False

        # Check if cached winetricks exists
        if not self.cached_winetricks.exists():
            self.logger.info("Cached winetricks not found, downloading latest version...")
            should_download = True
        else:
            # Check cache age
            file_age_days = (time.time() - self.cached_winetricks.stat().st_mtime) / 86400
            if file_age_days > self.CACHE_EXPIRATION_DAYS:
                self.logger.info(f"Cached winetricks is {file_age_days:.1f} days old, updating...")
                should_download = True

        # Download if needed
        if should_download:
            if self._download_winetricks():
                return True
            else:
                # Download failed - check if old cached version exists
                if self.cached_winetricks.exists():
                    self.logger.info("Using existing cached version despite update failure")
                    return True
                else:
                    return False
        else:
            return True

    def _download_winetricks(self) -> bool:
        """
        Download latest winetricks from GitHub

        Returns:
            True if download successful, False otherwise
        """
        try:
            self.logger.info("Downloading latest winetricks from GitHub...")
            response = requests.get(self.WINETRICKS_URL, timeout=30)
            response.raise_for_status()

            # Write to file
            self.cached_winetricks.write_text(response.text)

            # Make executable
            self.cached_winetricks.chmod(self.cached_winetricks.stat().st_mode | stat.S_IEXEC)

            self.logger.info(f"Downloaded latest winetricks to: {self.cached_winetricks}")
            return True

        except Exception as e:
            self.logger.warning(f"Failed to download winetricks: {e}")
            return False

    def _find_bundled_winetricks(self) -> Optional[str]:
        """
        Find bundled winetricks - DEPRECATED, no longer used

        We now always use the cached/downloaded version from GitHub.
        This method is kept for potential fallback but not called.

        Returns:
            None - bundled winetricks are no longer used
        """
        self.logger.debug("Bundled winetricks lookup skipped - using cached version only")
        return None

    def clear_cache(self):
        """Clear cached winetricks (force re-download on next get)"""
        if self.cached_winetricks.exists():
            try:
                self.cached_winetricks.unlink()
                self.logger.info("Cleared cached winetricks")
            except Exception as e:
                self.logger.warning(f"Failed to clear cached winetricks: {e}")


# Singleton instance for shared use
_winetricks_manager = None


def get_winetricks_manager() -> WinetricksManager:
    """
    Get singleton WinetricksManager instance

    Returns:
        Shared WinetricksManager instance
    """
    global _winetricks_manager
    if _winetricks_manager is None:
        _winetricks_manager = WinetricksManager()
    return _winetricks_manager
