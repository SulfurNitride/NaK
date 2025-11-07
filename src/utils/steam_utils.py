"""
Steam utilities module
Provides minimal Steam integration for NaK
"""

from pathlib import Path
from src.utils.logger import get_logger


class SteamUtils:
    """Minimal Steam utilities - only for detecting Steam installation path"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def get_steam_root(self) -> str:
        """
        Find the Steam installation directory

        This is used for setting STEAM_COMPAT_CLIENT_INSTALL_PATH in launch scripts,
        which is required by Proton even when using custom prefixes outside Steam's compatdata.

        Supports both native Steam and Flatpak Steam installations.

        Returns:
            Path to Steam installation directory

        Raises:
            RuntimeError: If Steam installation cannot be found
        """
        home_dir = Path.home()

        # Check common Steam installation locations
        # Order matters: Check native Steam first, then Flatpak
        candidates = [
            # Native Steam locations
            home_dir / ".local" / "share" / "Steam",
            home_dir / ".steam" / "steam",
            home_dir / ".steam" / "debian-installation",
            Path("/usr/local/steam"),
            Path("/usr/share/steam"),
            # Flatpak Steam location
            home_dir / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
        ]

        for candidate in candidates:
            if candidate.exists():
                # Detect if this is Flatpak Steam
                is_flatpak = "com.valvesoftware.Steam" in str(candidate)
                steam_type = "Flatpak" if is_flatpak else "Native"

                self.logger.info(f"Found Steam root: {candidate}")
                self.logger.info(f"Steam Type: {steam_type}")
                return str(candidate)

        # Steam not found - this is a warning, not a fatal error
        self.logger.warning("Steam installation not found - this may cause issues with Proton")
        raise RuntimeError("Could not find Steam installation")
