"""
Core business logic for NaK application
This module contains all the business logic and is framework-agnostic
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
from src.mod_managers.mo2 import MO2Installer
from src.mod_managers.vortex import VortexInstaller
from src.core.dependency_installer import DependencyInstaller
from src.utils.steam_utils import SteamUtils
from src.utils.game_utils import GameUtils
from src.utils.utils import Utils
from src.utils.comprehensive_game_manager import ComprehensiveGameManager
from src.utils.settings_manager import SettingsManager
from src.utils.logger import get_logger
from src.constants import FeatureFlags, APP_VERSION, APP_DATE

class Core:
    """Core represents the main business logic of the NaK application"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.debug("Core initialization starting...")

        # Initialize utilities
        self.steam_utils = SteamUtils()
        self.settings = SettingsManager()

        # Initialize installers
        self.mo2 = MO2Installer(core=self)
        self.logger.debug("MO2Installer initialized")
        self.vortex = VortexInstaller(core=self)
        self.logger.debug("VortexInstaller initialized")

        self.deps = DependencyInstaller(settings_manager=self.settings)
        self.game_utils = GameUtils()
        self.utils = Utils()

        # Only initialize game manager if auto-detection is enabled
        if FeatureFlags.ENABLE_AUTO_GAME_DETECTION:
            self.game_manager = ComprehensiveGameManager()
            self.logger.debug("Game manager initialized (auto-detection enabled)")
        else:
            self.game_manager = None
            self.logger.debug("Game manager disabled (auto-detection off)")

        # Start background dependency caching
        self._start_background_caching()

    def get_version_info(self) -> tuple[str, str]:
        """Get version information from constants"""
        return APP_VERSION, APP_DATE

    def check_dependencies(self) -> bool:
        """
        Check if all required dependencies are available

        NOTE: Simplified check - Proton-GE is now managed separately via ProtonGEManager
        """
        self.logger.info("Checking dependencies...")

        try:
            # Check for Steam (not flatpak)
            self.logger.info("Checking Steam installation...")
            try:
                steam_root = self.steam_utils.get_steam_root()
                self.logger.info(f"Steam found at: {steam_root}")
            except Exception as e:
                self.logger.warning(f"Steam not found: {e}")
                # Steam is optional with Proton-GE

            self.logger.info("All dependencies are available")
            return True

        except Exception as e:
            self.logger.error(f"Dependency check failed: {e}")
            return False

    def get_dependency_details(self) -> Dict[str, Any]:
        """
        Get detailed information about dependencies for display

        NOTE: Proton-GE status should be checked via ProtonGEManager directly
        """
        self.logger.info("Getting dependency details for UI display...")

        details = {
            "proton_ge": {
                "available": "Check via ProtonGEManager",
                "status": "use_proton_ge_manager"
            },
            "steam_installation": {
                "type": "unknown",
                "path": None,
                "status": "error"
            },
            "winetricks": {
                "available": True,
                "bundled": True,
                "status": "success"
            }
        }

        try:
            # Check Steam installation
            steam_root = self.steam_utils.get_steam_root()
            self.logger.info(f"Steam root detected: {steam_root}")

            # Check Steam installation type
            if "debian-installation" in steam_root:
                details["steam_installation"]["type"] = "Debian Package"
                details["steam_installation"]["path"] = steam_root
                details["steam_installation"]["status"] = "success"
                self.logger.info(f"Steam installation type: Debian Package")
            elif ".local/share/Steam" in steam_root or ".steam/steam" in steam_root:
                details["steam_installation"]["type"] = "Native"
                details["steam_installation"]["path"] = steam_root
                details["steam_installation"]["status"] = "success"
                self.logger.info(f"Steam installation type: Native")
            else:
                self.logger.warning(f"Unknown Steam installation type for path: {steam_root}")

            self.logger.info(f"Dependency details: {details}")

        except Exception as e:
            self.logger.error(f"Failed to get dependency details: {e}", exc_info=True)

        return details

    def install_mo2(self, install_dir: Optional[str] = None) -> Dict[str, Any]:
        """Download and install Mod Organizer 2"""
        try:
            result = self.mo2.download_mo2(install_dir=install_dir)
            return result
        except Exception as e:
            self.logger.error(f"Failed to install MO2: {e}")
            return {"success": False, "error": str(e)}

    def setup_existing_mo2(self, mo2_path: str, custom_name: str) -> Dict[str, Any]:
        """Setup existing MO2 installation"""
        try:
            return self.mo2.setup_existing(mo2_path, custom_name)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def remove_nxm_handlers(self) -> Dict[str, Any]:
        """Remove NXM handlers"""
        try:
            return self.mo2.remove_nxm_handlers()
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def configure_nxm_handler(self, app_id: str, nxm_handler_path: str) -> Dict[str, Any]:
        """Configure NXM handler for a specific game"""
        try:
            return self.mo2.configure_nxm_handler(app_id, nxm_handler_path)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def test_nxm_handler(self, test_url: str = "nxm://skyrimspecialedition/mods/12345/files/67890") -> Dict[str, Any]:
        """
        Test the NXM handler by simulating an nxm:// link

        Args:
            test_url: Test NXM URL (default is a Skyrim SE test URL)

        Returns:
            Dictionary with test results
        """
        try:
            from src.utils.nxm_handler_manager import NXMHandlerManager
            nxm_manager = NXMHandlerManager()
            return nxm_manager.test_nxm_handler(test_url)
        except Exception as e:
            self.logger.error(f"Failed to test NXM handler: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_nxm_handler_status(self) -> Dict[str, Any]:
        """
        Get the current status of the NXM handler configuration

        Returns:
            Dictionary with handler status information
        """
        try:
            from src.utils.nxm_handler_manager import NXMHandlerManager
            nxm_manager = NXMHandlerManager()
            return nxm_manager.get_nxm_handler_status()
        except Exception as e:
            self.logger.error(f"Failed to get NXM handler status: {e}")
            return {
                "error": str(e)
            }

    def get_game_info(self) -> Dict[str, Any]:
        """Get information about supported games"""
        result = {
            "supported_games": [
                "Skyrim Special Edition",
                "Fallout 4",
                "Fallout 76",
                "Cyberpunk 2077",
                "And many more..."
            ],
            "launch_options": [
                "Proton-GE with Wine",
                "Native Linux (if available)",
            ]
        }

        # Try to detect installed games
        try:
            steam_root = self.steam_utils.get_steam_root()

            # Check for FNV (AppID: 22380)
            fnv_compatdata = self.game_utils.find_game_compatdata("22380", steam_root)
            if fnv_compatdata:
                result["fnv_compatdata"] = fnv_compatdata

            # Check for Enderal (AppID: 976620)
            enderal_compatdata = self.game_utils.find_game_compatdata("976620", steam_root)
            if enderal_compatdata:
                result["enderal_compatdata"] = enderal_compatdata

        except Exception as e:
            self.logger.warning(f"Could not find Steam installation: {e}")

        return result

    def check_for_updates(self) -> Dict[str, Any]:
        """Check if updates are available"""
        try:
            self.logger.info("Checking for updates...")
            # TODO: Implement actual update checking logic
            return {"success": True, "message": "No updates available"}
        except Exception as e:
            self.logger.error(f"Failed to check for updates: {e}")
            return {"success": False, "error": str(e)}

    def get_all_games(self) -> List[Dict[str, Any]]:
        """Get all games across all platforms"""
        # Return empty list if auto-detection is disabled
        if not FeatureFlags.ENABLE_AUTO_GAME_DETECTION or self.game_manager is None:
            return []

        try:
            games = self.game_manager.get_all_games()
            return [{
                "name": game.name,
                "path": game.path,
                "platform": game.platform,
                "app_id": game.app_id,
                "exe_path": game.exe_path,
                "prefix_path": game.prefix_path,
                "wine_version": game.wine_version,
                "proton_version": game.proton_version
            } for game in games]
        except Exception as e:
            self.logger.error(f"Failed to get all games: {e}")
            return []

    def get_fnv_installations(self) -> List[Dict[str, Any]]:
        """Get all Fallout New Vegas installations"""
        try:
            installations = self.game_manager.get_fnv_installations()
            return [{
                "game_name": result.game.name,
                "platform": result.platform,
                "confidence": result.confidence,
                "prefix_path": str(result.prefix.path),
                "reason": result.reason
            } for result in installations]
        except Exception as e:
            self.logger.error(f"Failed to get FNV installations: {e}")
            return []

    def get_enderal_installations(self) -> List[Dict[str, Any]]:
        """Get all Enderal installations"""
        try:
            installations = self.game_manager.get_enderal_installations()
            return [{
                "game_name": result.game.name,
                "platform": result.platform,
                "confidence": result.confidence,
                "prefix_path": str(result.prefix.path),
                "reason": result.reason
            } for result in installations]
        except Exception as e:
            self.logger.error(f"Failed to get Enderal installations: {e}")
            return []

    def get_skyrim_installations(self) -> List[Dict[str, Any]]:
        """Get all Skyrim installations"""
        try:
            installations = self.game_manager.get_skyrim_installations()
            return [{
                "game_name": result.game.name,
                "platform": result.platform,
                "confidence": result.confidence,
                "prefix_path": str(result.prefix.path),
                "reason": result.reason
            } for result in installations]
        except Exception as e:
            self.logger.error(f"Failed to get Skyrim installations: {e}")
            return []

    def setup_fnv_complete(self) -> Dict[str, Any]:
        """Complete Fallout New Vegas setup across all platforms"""
        try:
            result = self.game_manager.setup_fnv_complete()
            return {
                "success": result.success,
                "message": result.message,
                "game_name": result.game_name,
                "platform": result.platform,
                "prefix_path": result.prefix_path,
                "error": result.error
            }
        except Exception as e:
            self.logger.error(f"Failed to setup FNV complete: {e}")
            return {"success": False, "error": str(e)}

    def setup_enderal_complete(self) -> Dict[str, Any]:
        """Complete Enderal setup across all platforms"""
        try:
            result = self.game_manager.setup_enderal_complete()
            return {
                "success": result.success,
                "message": result.message,
                "game_name": result.game_name,
                "platform": result.platform,
                "prefix_path": result.prefix_path,
                "error": result.error
            }
        except Exception as e:
            self.logger.error(f"Failed to setup Enderal complete: {e}")
            return {"success": False, "error": str(e)}

    def setup_skyrim_complete(self) -> Dict[str, Any]:
        """Complete Skyrim setup across all platforms"""
        try:
            result = self.game_manager.setup_skyrim_complete()
            return {
                "success": result.success,
                "message": result.message,
                "game_name": result.game_name,
                "platform": result.platform,
                "prefix_path": result.prefix_path,
                "error": result.error
            }
        except Exception as e:
            self.logger.error(f"Failed to setup Skyrim complete: {e}")
            return {"success": False, "error": str(e)}

    def get_game_summary(self) -> Dict[str, Any]:
        """Get a summary of all detected games"""
        try:
            return self.game_manager.get_game_summary()
        except Exception as e:
            self.logger.error(f"Failed to get game summary: {e}")
            return {"error": str(e)}

    def cache_all_dependencies(self, force_download: bool = False) -> Dict[str, Any]:
        """Cache all dependency files for faster future installations"""
        try:
            return self.deps.cache_all_dependencies(force_download)
        except Exception as e:
            self.logger.error(f"Failed to cache dependencies: {e}")
            return {"success": False, "error": str(e)}

    def get_cache_status(self) -> Dict[str, Any]:
        """Get status of the dependency cache"""
        try:
            return self.deps.get_cache_status()
        except Exception as e:
            self.logger.error(f"Failed to get cache status: {e}")
            return {"error": str(e)}

    def clear_dependency_cache(self) -> Dict[str, Any]:
        """Clear all cached dependency files"""
        try:
            return self.deps.clear_dependency_cache()
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            return {"success": False, "error": str(e)}

    def _start_background_caching(self):
        """Background caching disabled - dependencies are now cached on-demand during installation"""
        # Background caching has been disabled to avoid unnecessary downloads at startup
        # Dependencies are now cached on-demand when winetricks runs (via W_CACHE environment variable)
        # MO2 archives are cached when first downloading during installation
        self.logger.info("Background caching is disabled - dependencies will be cached on-demand")
        return
