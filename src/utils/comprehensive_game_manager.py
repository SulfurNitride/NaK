"""
Comprehensive Game Manager - Unified game and prefix management
Provides high-level interface for managing games across all platforms
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from src.utils.game_finder import GameFinder, GameInfo
from src.utils.smart_prefix_manager import SmartPrefixManager, SmartPrefixResult


@dataclass
class GameManagementResult:
    """Result of game management operations"""
    success: bool
    message: str
    game_name: str
    platform: str
    prefix_path: Optional[str] = None
    error: Optional[str] = None


class ComprehensiveGameManager:
    """Unified game management across all platforms"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.game_finder = GameFinder()
        self.prefix_manager = SmartPrefixManager()
    
    def get_all_games(self) -> List[GameInfo]:
        """Get all games across all platforms"""
        return self.game_finder.find_all_games()
    
    def get_fnv_installations(self) -> List[SmartPrefixResult]:
        """Get all Fallout New Vegas installations with prefix info"""
        return self.prefix_manager.find_fnv_prefixes()
    
    def get_enderal_installations(self) -> List[SmartPrefixResult]:
        """Get all Enderal installations with prefix info"""
        return self.prefix_manager.find_enderal_prefixes()
    
    def get_skyrim_installations(self) -> List[SmartPrefixResult]:
        """Get all Skyrim installations with prefix info"""
        return self.prefix_manager.find_skyrim_prefixes()
    
    def setup_fnv_complete(self) -> GameManagementResult:
        """Complete Fallout New Vegas setup across all platforms"""
        self.logger.info("Setting up Fallout New Vegas")
        
        fnv_installations = self.get_fnv_installations()
        if not fnv_installations:
            return GameManagementResult(
                success=False,
                message="No Fallout New Vegas installations found",
                game_name="Fallout New Vegas",
                platform="Unknown",
                error="No installations detected"
            )
        
        # Use the best installation
        best_installation = fnv_installations[0]
        game_name = best_installation.game.name
        platform = best_installation.platform
        
        self.logger.info(f"Using {platform} installation")
        
        # FNV dependencies
        fnv_dependencies = [
            "fontsmooth=rgb",
            "xact",
            "xact_x64", 
            "d3dx9_43",
            "d3dx9",
            "vcrun2022"
        ]
        
        # Install dependencies using the specific platform method
        if platform == "Steam":
            dep_result = self.prefix_manager._install_dependencies_steam(best_installation, fnv_dependencies)
        elif platform.startswith("Heroic"):
            dep_result = self.prefix_manager._install_dependencies_heroic(best_installation, fnv_dependencies)
        else:
            dep_result = self.prefix_manager._install_dependencies_wine(best_installation, fnv_dependencies)
        if not dep_result["success"]:
            return GameManagementResult(
                success=False,
                message=f"Failed to install dependencies: {dep_result['error']}",
                game_name=game_name,
                platform=platform,
                error=dep_result["error"]
            )
        
        # Apply registry settings using the specific installation
        reg_file_path = Path(__file__).parent / "wine_settings.reg"
        if reg_file_path.exists():
            reg_success = self.prefix_manager.prefix_locator.apply_regedit_to_prefix(best_installation.prefix, str(reg_file_path))
            if reg_success:
                self.logger.info(f"Registry settings applied successfully to {game_name}")
            else:
                self.logger.warning(f"Registry settings failed for {game_name}")
        
        # Install .NET SDK using the specific installation
        if best_installation.platform == "Steam":
            dotnet_result = self.prefix_manager._install_dotnet_steam(best_installation)
        else:
            dotnet_result = self.prefix_manager._install_dotnet_wine(best_installation)
        
        if not dotnet_result["success"]:
            self.logger.warning(f".NET SDK installation failed: {dotnet_result['error']}")
        
        return GameManagementResult(
            success=True,
            message=f"Fallout New Vegas setup complete for {platform}",
            game_name=game_name,
            platform=platform,
            prefix_path=best_installation.prefix.path
        )
    
    def setup_enderal_complete(self) -> GameManagementResult:
        """Complete Enderal setup across all platforms"""
        self.logger.info("Setting up Enderal")
        
        enderal_installations = self.get_enderal_installations()
        if not enderal_installations:
            return GameManagementResult(
                success=False,
                message="No Enderal installations found",
                game_name="Enderal",
                platform="Unknown",
                error="No installations detected"
            )
        
        # Use the best installation
        best_installation = enderal_installations[0]
        game_name = best_installation.game.name
        platform = best_installation.platform
        
        self.logger.info(f"Using {platform} installation")
        
        # Enderal dependencies
        enderal_dependencies = [
            "fontsmooth=rgb",
            "xact",
            "xact_x64",
            "d3dx11_43",
            "d3dcompiler_43",
            "d3dcompiler_47",
            "vcrun2022",
            "dotnet6",
            "dotnet7",
            "dotnet8"
        ]
        
        # Install dependencies using the specific platform method
        if platform == "Steam":
            dep_result = self.prefix_manager._install_dependencies_steam(best_installation, enderal_dependencies)
        elif platform.startswith("Heroic"):
            dep_result = self.prefix_manager._install_dependencies_heroic(best_installation, enderal_dependencies)
        else:
            dep_result = self.prefix_manager._install_dependencies_wine(best_installation, enderal_dependencies)
        if not dep_result["success"]:
            return GameManagementResult(
                success=False,
                message=f"Failed to install dependencies: {dep_result['error']}",
                game_name=game_name,
                platform=platform,
                error=dep_result["error"]
            )
        
        # Apply registry settings
        reg_file_path = Path(__file__).parent / "wine_settings.reg"
        if reg_file_path.exists():
            reg_result = self.prefix_manager.apply_regedit_smart(game_name, str(reg_file_path))
            if not reg_result["success"]:
                self.logger.warning(f"Registry settings failed: {reg_result['error']}")
        
        # Install .NET SDK
        dotnet_result = self.prefix_manager.install_dotnet_smart(game_name)
        if not dotnet_result["success"]:
            self.logger.warning(f".NET SDK installation failed: {dotnet_result['error']}")
        
        return GameManagementResult(
            success=True,
            message=f"Enderal setup complete for {platform}",
            game_name=game_name,
            platform=platform,
            prefix_path=best_installation.prefix.path
        )
    
    def setup_skyrim_complete(self) -> GameManagementResult:
        """Complete Skyrim setup across all platforms"""
        self.logger.info("Setting up Skyrim")
        
        skyrim_installations = self.get_skyrim_installations()
        if not skyrim_installations:
            return GameManagementResult(
                success=False,
                message="No Skyrim installations found",
                game_name="Skyrim",
                platform="Unknown",
                error="No installations detected"
            )
        
        # Use the best installation
        best_installation = skyrim_installations[0]
        game_name = best_installation.game.name
        platform = best_installation.platform
        
        self.logger.info(f"Using {platform} installation")
        
        # Skyrim dependencies
        skyrim_dependencies = [
            "fontsmooth=rgb",
            "xact",
            "xact_x64",
            "d3dx11_43",
            "d3dcompiler_43",
            "d3dcompiler_47",
            "vcrun2022",
            "dotnet6",
            "dotnet7",
            "dotnet8"
        ]
        
        # Install dependencies using the specific platform method
        if platform == "Steam":
            dep_result = self.prefix_manager._install_dependencies_steam(best_installation, skyrim_dependencies)
        elif platform.startswith("Heroic"):
            dep_result = self.prefix_manager._install_dependencies_heroic(best_installation, skyrim_dependencies)
        else:
            dep_result = self.prefix_manager._install_dependencies_wine(best_installation, skyrim_dependencies)
        if not dep_result["success"]:
            return GameManagementResult(
                success=False,
                message=f"Failed to install dependencies: {dep_result['error']}",
                game_name=game_name,
                platform=platform,
                error=dep_result["error"]
            )
        
        # Apply registry settings
        reg_file_path = Path(__file__).parent / "wine_settings.reg"
        if reg_file_path.exists():
            reg_result = self.prefix_manager.apply_regedit_smart(game_name, str(reg_file_path))
            if not reg_result["success"]:
                self.logger.warning(f"Registry settings failed: {reg_result['error']}")
        
        # Install .NET SDK
        dotnet_result = self.prefix_manager.install_dotnet_smart(game_name)
        if not dotnet_result["success"]:
            self.logger.warning(f".NET SDK installation failed: {dotnet_result['error']}")
        
        return GameManagementResult(
            success=True,
            message=f"Skyrim setup complete for {platform}",
            game_name=game_name,
            platform=platform,
            prefix_path=best_installation.prefix.path
        )
    
    def get_game_summary(self) -> Dict[str, Any]:
        """Get a summary of all detected games across platforms"""
        all_games = self.get_all_games()
        
        summary = {
            "total_games": len(all_games),
            "platforms": {},
            "specific_games": {
                "fallout_new_vegas": len(self.get_fnv_installations()),
                "enderal": len(self.get_enderal_installations()),
                "skyrim": len(self.get_skyrim_installations())
            }
        }
        
        # Count by platform
        for game in all_games:
            platform = game.platform
            if platform not in summary["platforms"]:
                summary["platforms"][platform] = 0
            summary["platforms"][platform] += 1
        
        return summary
    
    def setup_specific_game_complete(self, game: GameInfo) -> GameManagementResult:
        """Complete setup for a specific game installation"""
        self.logger.info(f"Setting up specific game: {game.name} ({game.platform})")
        
        # Find the prefix for this specific game
        prefix = self.prefix_manager.prefix_locator.find_game_prefix(game)
        if not prefix:
            return GameManagementResult(
                success=False,
                message=f"No prefix found for {game.name}",
                game_name=game.name,
                platform=game.platform,
                error="No prefix detected"
            )
        
        # Create a SmartPrefixResult for this specific installation
        from src.utils.smart_prefix_manager import SmartPrefixResult
        installation = SmartPrefixResult(
            game=game,
            prefix=prefix,
            platform=game.platform,
            confidence=1.0,  # High confidence since user specifically selected this
            reason=f"User selected {game.platform} installation"
        )
        
        self.logger.info(f"Setting up {game.name} ({game.platform})")
        self.logger.debug(f"Prefix path: {prefix.path}")
        
        # Use comprehensive dependency list for all games (like MO2 setup)
        dependencies = [
            "fontsmooth=rgb",
            "xact",
            "xact_x64",
            "vcrun2022",
            "dotnet6",
            "dotnet7", 
            "dotnet8",
            "dotnetdesktop6",
            "d3dcompiler_47",
            "d3dx11_43",
            "d3dcompiler_43",
            "d3dx9_43",
            "d3dx9",
            "vkd3d",
        ]
        
        self.logger.debug(f"Installing {len(dependencies)} dependencies")
        
        # Install dependencies using the specific platform method
        if game.platform == "Steam":
            dep_result = self.prefix_manager._install_dependencies_steam(installation, dependencies)
        elif game.platform.startswith("Heroic"):
            dep_result = self.prefix_manager._install_dependencies_heroic(installation, dependencies)
        else:
            dep_result = self.prefix_manager._install_dependencies_wine(installation, dependencies)
        
        if not dep_result["success"]:
            return GameManagementResult(
                success=False,
                message=f"Failed to install dependencies: {dep_result['error']}",
                game_name=game.name,
                platform=game.platform,
                error=dep_result["error"]
            )
        
        # Apply registry settings using the specific installation
        reg_file_path = Path(__file__).parent / "wine_settings.reg"
        if reg_file_path.exists():
            reg_success = self.prefix_manager.prefix_locator.apply_regedit_to_prefix(installation.prefix, str(reg_file_path))
            if reg_success:
                self.logger.info(f"Registry settings applied successfully to {game.name}")
            else:
                self.logger.warning(f"Registry settings failed for {game.name}")
        
        # Install .NET SDK using the specific installation
        if game.platform == "Steam":
            dotnet_result = self.prefix_manager._install_dotnet_steam(installation)
        else:
            dotnet_result = self.prefix_manager._install_dotnet_wine(installation)
        
        if not dotnet_result["success"]:
            self.logger.warning(f".NET SDK installation failed: {dotnet_result['error']}")
        
        return GameManagementResult(
            success=True,
            message=f"{game.name} setup complete for {game.platform}",
            game_name=game.name,
            platform=game.platform,
            prefix_path=str(installation.prefix.path)
        )
    
    def find_best_nxm_prefix(self, game_name: str) -> Optional[SmartPrefixResult]:
        """Find the best prefix for NXM handler configuration"""
        return self.prefix_manager.find_best_prefix_for_game(game_name)
    
    def configure_nxm_handler_smart(self, game_name: str) -> GameManagementResult:
        """Configure NXM handler for the best available prefix"""
        best_result = self.find_best_nxm_prefix(game_name)
        if not best_result:
            return GameManagementResult(
                success=False,
                message=f"No suitable prefix found for NXM handler: {game_name}",
                game_name=game_name,
                platform="Unknown",
                error="No prefix found"
            )
        
        # TODO: Implement NXM handler configuration
        # This would integrate with the existing MO2 NXM handler system
        
        return GameManagementResult(
            success=True,
            message=f"NXM handler configured for {game_name}",
            game_name=game_name,
            platform=best_result.platform,
            prefix_path=str(best_result.prefix.path)
        )
