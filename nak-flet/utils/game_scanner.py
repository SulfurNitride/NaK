"""
Game Scanner Utility

Handles background game scanning with periodic updates.
Extracted from main.py to improve code organization.
"""

import time
import threading
from pathlib import Path
import sys

# Add parent directory to path to import backend
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logger import get_logger

logger = get_logger(__name__)


class GameScanner:
    """Handles background game scanning and periodic updates"""

    def __init__(self, core, scan_interval=30):
        """
        Initialize game scanner

        Args:
            core: Core backend instance
            scan_interval: Interval in seconds between periodic scans (default: 30)
        """
        self.core = core
        self.scan_interval = scan_interval
        self.games_list = None
        self._scanning = False
        self._scan_thread = None
        self._periodic_thread = None

    def scan_games_background(self):
        """Scan for games silently in the background"""
        try:
            self._scanning = True
            games = self.core.get_all_games()
            self.games_list = games
            logger.debug(f"Background scan found {len(games)} games")
            self._scanning = False
            return games
        except Exception as e:
            logger.error(f"Background game scan failed: {e}")
            self._scanning = False
            return None

    def periodic_game_scan(self):
        """Periodically scan for games at the configured interval"""
        while True:
            time.sleep(self.scan_interval)
            try:
                games = self.core.get_all_games()
                old_count = len(self.games_list) if self.games_list else 0
                self.games_list = games
                new_count = len(games)
                if new_count != old_count:
                    logger.info(f"Periodic scan: Game count changed from {old_count} to {new_count}")
            except Exception as e:
                logger.error(f"Periodic game scan failed: {e}")

    def start_background_scan(self):
        """Start initial background scan"""
        if not self._scan_thread or not self._scan_thread.is_alive():
            self._scan_thread = threading.Thread(target=self.scan_games_background, daemon=True)
            self._scan_thread.start()
            logger.debug("Started background game scan")

    def start_periodic_scan(self):
        """Start periodic game scanning"""
        if not self._periodic_thread or not self._periodic_thread.is_alive():
            self._periodic_thread = threading.Thread(target=self.periodic_game_scan, daemon=True)
            self._periodic_thread.start()
            logger.debug(f"Started periodic game scan (interval: {self.scan_interval}s)")

    def start_all_scans(self):
        """Start both initial background scan and periodic scanning"""
        self.start_background_scan()
        self.start_periodic_scan()

    def get_games_list(self):
        """
        Get the current games list

        Returns:
            list: List of detected games, or None if not scanned yet
        """
        return self.games_list

    def is_scanning(self):
        """
        Check if a scan is currently in progress

        Returns:
            bool: True if scanning, False otherwise
        """
        return self._scanning
