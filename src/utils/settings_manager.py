"""
Settings Manager for NaK
Handles user preferences and manual configuration of Wine/Proton paths
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from src.utils.logger import get_logger


class SettingsManager:
    """Manages user settings and preferences"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings_file = Path.home() / ".config" / "nak" / "settings.json"
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load settings: {e}")

        return {
            "proton_path": "",
            "wine_path": "",
            "steam_path": "",  # User's preferred Steam installation (if multiple exist)
            "auto_detect": True,
            "preferred_proton_version": "Proton - Experimental",
            "first_run_complete": False,  # Track if first-run welcome has been shown
            "nak_storage_location": ""  # Custom location for NaK folder (empty = default ~/NaK)
        }

    def _save_settings(self):
        """Save settings to file"""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")

    def set_proton_path(self, path: str):
        """Set custom Proton path"""
        self.settings["proton_path"] = path
        self._save_settings()
        self.logger.info(f"Set custom Proton path: {path}")

    def set_wine_path(self, path: str):
        """Set custom Wine path"""
        self.settings["wine_path"] = path
        self._save_settings()
        self.logger.info(f"Set custom Wine path: {path}")

    def set_auto_detect(self, enabled: bool):
        """Enable/disable automatic detection"""
        self.settings["auto_detect"] = enabled
        self._save_settings()
        self.logger.info(f"Auto detection: {enabled}")

    def set_preferred_proton_version(self, version: str):
        """Set preferred Proton version"""
        self.settings["preferred_proton_version"] = version
        self._save_settings()
        self.logger.info(f"Preferred Proton version: {version}")

    def get_proton_path(self) -> Optional[str]:
        """Get Proton path (custom or auto-detected)"""
        if self.settings.get("proton_path"):
            if Path(self.settings["proton_path"]).exists():
                return self.settings["proton_path"]
            else:
                self.logger.warning(f"Custom Proton path does not exist: {self.settings['proton_path']}")

        return None

    def get_wine_path(self) -> Optional[str]:
        """Get Wine path (custom or auto-detected)"""
        if self.settings.get("wine_path"):
            if Path(self.settings["wine_path"]).exists():
                return self.settings["wine_path"]
            else:
                self.logger.warning(f"Custom Wine path does not exist: {self.settings['wine_path']}")

        # Auto-detect Wine if enabled
        if self.settings.get("auto_detect", True):
            return self._auto_detect_wine()

        return None

    def _auto_detect_wine(self) -> Optional[str]:
        """Auto-detect Wine installation including Wine-TKG"""
        import shutil
        
        # Check for wine in PATH
        wine_path = shutil.which("wine")
        if wine_path:
            self.logger.info(f"Found Wine in PATH: {wine_path}")
            return wine_path
        
        # Check for Wine-TKG (AUR package)
        wine_tkg_paths = [
            "/usr/bin/wine-tkg",
            "/usr/local/bin/wine-tkg",
            "/opt/wine-tkg/bin/wine"
        ]
        
        for wine_tkg_location in wine_tkg_paths:
            if Path(wine_tkg_location).exists():
                self.logger.info(f"Found Wine-TKG: {wine_tkg_location}")
                return wine_tkg_location
        
        # Check common Wine installation locations
        common_wine_locations = [
            "/usr/bin/wine",
            "/usr/local/bin/wine",
            "/opt/wine/bin/wine",
            "/home/linuxbrew/.linuxbrew/bin/wine"
        ]
        
        for wine_location in common_wine_locations:
            if Path(wine_location).exists():
                self.logger.info(f"Found Wine in common location: {wine_location}")
                return wine_location
        
        self.logger.warning("No Wine installation found")
        return None

    def should_auto_detect(self) -> bool:
        """Check if auto detection should be used"""
        return self.settings.get("auto_detect", True)

    def get_preferred_proton_version(self) -> str:
        """Get preferred Proton version"""
        return self.settings.get("preferred_proton_version", "Proton - Experimental")

    def set_steam_path(self, path: str):
        """Set user's preferred Steam installation path"""
        self.settings["steam_path"] = path
        self._save_settings()
        self.logger.info(f"Set Steam path: {path}")

    def get_steam_path(self) -> Optional[str]:
        """Get user's preferred Steam installation path"""
        steam_path = self.settings.get("steam_path", "")
        return steam_path if steam_path else None

    def set_show_heroic_games(self, enabled: bool):
        """Set whether to show Heroic games in NXM handler setup"""
        self.settings["show_heroic_games"] = enabled
        self._save_settings()

    def get_show_heroic_games(self) -> bool:
        """Get whether to show Heroic games in NXM handler setup"""
        return self.settings.get("show_heroic_games", False)

    def set_nxm_steam_mo2_appid(self, appid: str):
        """Set the AppID for the Steam-based MO2 shortcut for the NXM handler."""
        self.settings["nxm_steam_mo2_appid"] = appid
        self._save_settings()
        self.logger.info(f"Set NXM Steam MO2 AppID: {appid}")

    def get_nxm_steam_mo2_appid(self) -> Optional[str]:
        """Get the AppID for the Steam-based MO2 shortcut for the NXM handler."""
        return self.settings.get("nxm_steam_mo2_appid")

    def set_nxm_heroic_mo2_path(self, path: str):
        """Set the executable path for the Heroic/Linux MO2 for the NXM handler."""
        self.settings["nxm_heroic_mo2_path"] = path
        self._save_settings()
        self.logger.info(f"Set NXM Heroic MO2 Path: {path}")

    def get_nxm_heroic_mo2_path(self) -> Optional[str]:
        """Get the executable path for the Heroic/Linux MO2 for the NXM handler."""
        return self.settings.get("nxm_heroic_mo2_path")

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings"""
        return self.settings.copy()

    def is_first_run(self) -> bool:
        """Check if this is the first run"""
        return not self.settings.get("first_run_complete", False)

    def set_first_run_complete(self):
        """Mark first-run as complete"""
        self.settings["first_run_complete"] = True
        self._save_settings()
        self.logger.info("Marked first-run as complete")

    def set_nak_storage_location(self, location: str):
        """Set custom NaK storage location"""
        self.settings["nak_storage_location"] = location
        self._save_settings()
        self.logger.info(f"Set NaK storage location: {location}")

    def get_nak_storage_location(self) -> Optional[str]:
        """Get custom NaK storage location (returns None if using default ~/NaK)"""
        location = self.settings.get("nak_storage_location", "")
        return location if location else None

    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        self.settings = {
            "proton_path": "",
            "wine_path": "",
            "auto_detect": True,
            "preferred_proton_version": "Proton - Experimental",
            "show_heroic_games": False,
            "first_run_complete": False,
            "nak_storage_location": ""
        }
        self._save_settings()
        self.logger.info("Reset settings to defaults")
