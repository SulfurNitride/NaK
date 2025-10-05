"""
Smart Prefix Manager - Intelligent prefix detection and management
Finds the best prefix for games across all platforms and manages dependencies
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from utils.game_finder import GameFinder, GameInfo
from utils.prefix_locator import PrefixLocator, PrefixInfo
from utils.settings_manager import SettingsManager


@dataclass
class SmartPrefixResult:
    """Result of smart prefix detection"""
    game: GameInfo
    prefix: PrefixInfo
    platform: str
    confidence: float  # 0.0 to 1.0
    reason: str


class SmartPrefixManager:
    """Intelligent prefix management for cross-platform games"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.game_finder = GameFinder()
        self.prefix_locator = PrefixLocator()
        self.settings = SettingsManager()

    def _get_winetricks_command(self) -> str:
        """Get the bundled winetricks command path - ONLY use bundled version"""
        # Check if we're running in AppImage
        appdir = os.environ.get('APPDIR')
        if appdir:
            # Use ONLY bundled winetricks from AppImage
            bundled_winetricks = os.path.join(appdir, "usr", "bin", "winetricks")
            if os.path.exists(bundled_winetricks):
                self.logger.info(f"*** USING BUNDLED WINETRICKS: {bundled_winetricks} ***")
                return bundled_winetricks
            else:
                self.logger.error(f"CRITICAL: Bundled winetricks not found at {bundled_winetricks}")
                return ""

        # If not in AppImage, this is a development environment - still prefer bundled
        local_winetricks = os.path.join(os.getcwd(), "winetricks")
        if os.path.exists(local_winetricks):
            self.logger.info(f"*** USING LOCAL BUNDLED WINETRICKS: {local_winetricks} ***")
            return local_winetricks

        self.logger.error("CRITICAL: No bundled winetricks found - this should not happen in production")
        return ""

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run([command, "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def find_best_prefix_for_game(self, game_name: str) -> Optional[SmartPrefixResult]:
        """Find the best prefix for a specific game across all platforms"""
        self.logger.info(f"Finding best prefix for: {game_name}")
        
        # Find all installations of the game
        game_installations = self.game_finder.find_specific_game(game_name)
        
        if not game_installations:
            self.logger.warning(f"No installations found for {game_name}")
            return None
        
        # Score each installation
        best_result = None
        best_score = 0.0
        
        for game in game_installations:
            result = self._score_game_installation(game)
            if result and result.confidence > best_score:
                best_score = result.confidence
                best_result = result
        
        if best_result:
            self.logger.info(f"Best prefix for {game_name}: {best_result.platform} (confidence: {best_result.confidence:.2f})")
            self.logger.info(f"   Reason: {best_result.reason}")
            self.logger.info(f"   Path: {best_result.prefix.path}")
        
        return best_result
    
    def _score_game_installation(self, game: GameInfo) -> Optional[SmartPrefixResult]:
        """Score a game installation and return the best prefix"""
        try:
            # Find prefix for this game
            prefix = self.prefix_locator.find_game_prefix(game)
            if not prefix:
                return None
            
            # Calculate confidence score
            confidence = 0.0
            reason_parts = []
            
            # Platform scoring - prefer Heroic/GOG over Steam for better modding support
            if game.platform in ["Epic", "GOG"]:
                confidence += 0.5  # Higher score for Heroic/GOG
                reason_parts.append(f"{game.platform} via Heroic (preferred for modding)")
            elif game.platform == "Steam":
                confidence += 0.3  # Lower score for Steam
                reason_parts.append("Steam integration")
            elif game.platform == "Wine":
                confidence += 0.2
                reason_parts.append("Native Wine")
            else:
                confidence += 0.1
                reason_parts.append(f"{game.platform} platform")
            
            # Prefix type scoring
            if prefix.prefix_type == "proton":
                confidence += 0.3
                reason_parts.append("Proton compatibility")
            elif prefix.prefix_type == "heroic":
                confidence += 0.25
                reason_parts.append("Heroic Wine prefix")
            elif prefix.prefix_type == "wine":
                confidence += 0.2
                reason_parts.append("Native Wine prefix")
            else:
                confidence += 0.1
                reason_parts.append(f"{prefix.prefix_type} prefix")
            
            # Version scoring
            if prefix.proton_version:
                confidence += 0.2
                reason_parts.append(f"Proton {prefix.proton_version}")
            elif prefix.wine_version:
                confidence += 0.15
                reason_parts.append(f"Wine {prefix.wine_version}")
            
            # Path validation
            if prefix.path.exists():
                confidence += 0.1
                reason_parts.append("Valid prefix path")
            
            return SmartPrefixResult(
                game=game,
                prefix=prefix,
                platform=game.platform,
                confidence=min(confidence, 1.0),
                reason=", ".join(reason_parts)
            )
            
        except Exception as e:
            self.logger.error(f"Error scoring game installation {game.name}: {e}")
            return None
    
    def find_fnv_prefixes(self) -> List[SmartPrefixResult]:
        """Find all Fallout New Vegas prefixes across platforms"""
        self.logger.info("Finding all Fallout New Vegas installations...")
        
        fnv_installations = self.game_finder.find_fnv_installations()
        self.logger.info(f"GameFinder returned {len(fnv_installations)} FNV installations")
        
        results = []
        
        for game in fnv_installations:
            self.logger.info(f"Processing FNV game: {game.name} ({game.platform})")
            result = self._score_game_installation(game)
            if result:
                self.logger.info(f"Scored FNV game: {result.confidence:.2f} - {result.prefix.path}")
                results.append(result)
            else:
                self.logger.warning(f"Failed to score FNV game: {game.name}")
        
        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        self.logger.info(f"Found {len(results)} Fallout New Vegas installations")
        for result in results:
            self.logger.info(f"   {result.platform}: {result.confidence:.2f} - {result.prefix.path}")
        
        return results
    
    def find_enderal_prefixes(self) -> List[SmartPrefixResult]:
        """Find all Enderal prefixes across platforms"""
        self.logger.info("Finding all Enderal installations...")
        
        enderal_installations = self.game_finder.find_enderal_installations()
        results = []
        
        for game in enderal_installations:
            result = self._score_game_installation(game)
            if result:
                results.append(result)
        
        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        self.logger.info(f"Found {len(results)} Enderal installations")
        for result in results:
            self.logger.info(f"   {result.platform}: {result.confidence:.2f} - {result.prefix.path}")
        
        return results
    
    def find_skyrim_prefixes(self) -> List[SmartPrefixResult]:
        """Find all Skyrim prefixes across platforms"""
        self.logger.info("Finding all Skyrim installations...")
        
        skyrim_installations = self.game_finder.find_skyrim_installations()
        results = []
        
        for game in skyrim_installations:
            result = self._score_game_installation(game)
            if result:
                results.append(result)
        
        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        self.logger.info(f"Found {len(results)} Skyrim installations")
        for result in results:
            self.logger.info(f"   {result.platform}: {result.confidence:.2f} - {result.prefix.path}")
        
        return results
    
    def install_dependencies_smart(self, game_name: str, dependencies: List[str]) -> Dict[str, Any]:
        """Install dependencies to the best available prefix for a game"""
        self.logger.info(f"Installing dependencies for {game_name}...")

        try:
            # Find the best prefix
            best_result = self.find_best_prefix_for_game(game_name)
            if not best_result:

                settings = SettingsManager()
                preferred_version = settings.get_preferred_proton_version()

                # Check if it's Wine (including Wine-TKG)
                if preferred_version in ["Wine", "Wine-TKG"]:
                    self.logger.info(f"*** Using Wine for {game_name} installation ***")
                    wine_path = settings.get_wine_path()
                    if wine_path and os.path.exists(wine_path):
                        return self._install_dependencies_wine_direct(best_result, dependencies, wine_path)
                    else:
                        return {
                            "success": False,
                            "error": "Wine not found. Please install Wine or Proton.",
                            "method": "wine_not_found"
                        }
                else:
                    # Use platform-specific method
                    if best_result.platform == "Steam":
                        return self._install_dependencies_steam(best_result, dependencies)
                    elif best_result.platform in ["Epic", "GOG"]:
                        return self._install_dependencies_heroic(best_result, dependencies)
                    else:
                        return self._install_dependencies_wine(best_result, dependencies)

        except Exception as e:
            self.logger.error(f"Failed to determine installation method: {e}")
            # Fallback to platform-specific method
            if best_result.platform == "Steam":
                return self._install_dependencies_steam(best_result, dependencies)
            elif best_result.platform in ["Epic", "GOG"]:
                return self._install_dependencies_heroic(best_result, dependencies)
            else:
                return self._install_dependencies_wine(best_result, dependencies)
    
    def _install_dependencies_steam(self, result: SmartPrefixResult, dependencies: List[str]) -> Dict[str, Any]:
        """Install dependencies for Steam games using protontricks or Heroic's winetricks"""
        try:
            self.logger.info(f"Installing Steam dependencies for {result.game.name}...")
            
            # Try to use Heroic's winetricks setup for faster installation
            heroic_wine_bin = self._get_heroic_wine_binary_for_steam()
            if heroic_wine_bin:
                self.logger.info(f"Using Heroic's winetricks setup for faster Steam installation")
                return self._install_dependencies_steam_with_heroic(result, dependencies, heroic_wine_bin)
            
            # Fallback to protontricks
            self.logger.info(f"Using protontricks for Steam installation")
            cmd = ["protontricks", "--no-bwrap", result.game.app_id, "-q"] + dependencies
            
            result_cmd = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result_cmd.returncode == 0:
                return {
                    "success": True,
                    "message": f"Dependencies installed successfully for {result.game.name}",
                    "platform": result.platform,
                    "prefix_path": str(result.prefix.path)
                }
            else:
                return {
                    "success": False,
                    "error": f"Protontricks failed: {result_cmd.stderr}",
                    "platform": result.platform
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to install Steam dependencies: {e}",
                "platform": result.platform
            }
    
    def _install_dependencies_heroic(self, result: SmartPrefixResult, dependencies: List[str]) -> Dict[str, Any]:
        """Install dependencies for Epic/GOG games using winetricks directly"""
        try:
            self.logger.info(f"Installing Heroic dependencies for {result.game.name}...")
            
            # Use winetricks directly for Heroic games (not through wine)
            wine_prefix = str(result.prefix.path)
            
            # Get the Wine binary path from Heroic's configuration
            wine_bin = self._get_heroic_wine_binary(result.game)
            
            # Set Wine prefix environment
            env = os.environ.copy()
            env["WINEPREFIX"] = wine_prefix
            env["WINEARCH"] = "win64"
            
            # Use the specific Wine binary if found
            if wine_bin and Path(wine_bin).exists():
                env["WINE"] = wine_bin
                self.logger.info(f"Using Heroic Wine binary: {wine_bin}")
            
            # Get bundled winetricks command
            winetricks_cmd = self._get_winetricks_command()
            if not winetricks_cmd:
                return {
                    "success": False,
                    "error": "Winetricks not found - cannot install dependencies",
                    "platform": result.platform
                }

            # Use winetricks directly (not through wine)
            cmd = [winetricks_cmd, "-q"] + dependencies
            
            self.logger.info(f"Installing dependencies for Heroic game {result.game.name}")
            self.logger.info(f"Wine prefix: {wine_prefix}")
            self.logger.info(f"Command: {' '.join(cmd)}")
            self.logger.info(f"Environment: WINEPREFIX={wine_prefix}, WINEARCH=win64, WINE={wine_bin}")
            
            # Log each dependency being installed
            self.logger.info(f"Installing {len(dependencies)} dependencies:")
            for i, dep in enumerate(dependencies, 1):
                self.logger.info(f"   {i}/{len(dependencies)}: {dep}")
            
            self.logger.info("Starting winetricks installation...")
            self.logger.info("This may take several minutes - please be patient...")
            
            result_cmd = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
            
            # Log the results
            self.logger.info(f"Winetricks completed with return code: {result_cmd.returncode}")
            if result_cmd.stdout:
                self.logger.info(f"Winetricks output:\n{result_cmd.stdout}")
            if result_cmd.stderr:
                self.logger.info(f"Winetricks warnings/errors:\n{result_cmd.stderr}")
            
            if result_cmd.returncode == 0:
                self.logger.info(f"Dependencies installed successfully for {result.game.name}")
                return {
                    "success": True,
                    "message": f"Dependencies installed for {result.game.name}",
                    "platform": result.platform,
                    "prefix_path": wine_prefix
                }
            else:
                self.logger.warning(f"Winetricks returned non-zero exit code: {result_cmd.returncode}")
                self.logger.warning(f"Error output: {result_cmd.stderr}")
                return {
                    "success": False,
                    "error": f"Dependency installation failed: {result_cmd.stderr}",
                    "platform": result.platform
                }
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"Winetricks installation timed out after 10 minutes")
            return {
                "success": False,
                "error": "Dependency installation timed out after 10 minutes",
                "platform": result.platform
            }
        except Exception as e:
            self.logger.error(f"Failed to install Heroic dependencies: {e}")
            return {
                "success": False,
                "error": f"Failed to install dependencies: {e}",
                "platform": result.platform
            }
    
    def _install_dependencies_wine(self, result: SmartPrefixResult, dependencies: List[str]) -> Dict[str, Any]:
        """Install dependencies for native Wine games"""
        try:
            self.logger.info(f"Installing Wine dependencies for {result.game.name}...")

            # Use Wine directly
            wine_prefix = str(result.prefix.path)

            # Set Wine prefix environment
            env = {
                "WINEPREFIX": wine_prefix,
                "WINEARCH": "win64"
            }

            # Get bundled winetricks command
            winetricks_cmd = self._get_winetricks_command()
            if not winetricks_cmd:
                return {
                    "success": False,
                    "error": "Winetricks not found - cannot install dependencies",
                    "platform": result.platform
                }

            # Install each dependency
            for dep in dependencies:
                cmd = ["wine", winetricks_cmd, dep]
                result_cmd = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)

                if result_cmd.returncode != 0:
                    self.logger.warning(f"Failed to install {dep}: {result_cmd.stderr}")

            return {
                "success": True,
                "message": f"Dependencies installed for {result.game.name}",
                "platform": result.platform,
                "prefix_path": wine_prefix
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to install Wine dependencies: {e}",
                "platform": result.platform
            }

    def _install_dependencies_wine_direct(self, result: SmartPrefixResult, dependencies: List[str], wine_path: str) -> Dict[str, Any]:
        """Install dependencies using Wine directly (not through prefix)"""
        try:
            self.logger.info(f"Installing dependencies using Wine: {wine_path}")

            # Set up Wine environment
            env = os.environ.copy()
            env["WINE"] = wine_path

            # Ensure we target the detected prefix
            if result.prefix and result.prefix.path:
                env["WINEPREFIX"] = str(result.prefix.path)
                self.logger.info(f"*** DEBUG: Using WINEPREFIX={env['WINEPREFIX']}")
            else:
                self.logger.warning("*** DEBUG: No prefix path supplied – falling back to default Wine prefix")

            # Provide sane defaults for headless-friendly execution
            env.setdefault("XDG_RUNTIME_DIR", "/tmp")
            env.setdefault("DISPLAY", os.environ.get("DISPLAY", ":0"))

            # Get bundled winetricks command
            winetricks_cmd = self._get_winetricks_command()
            if not winetricks_cmd:
                return {
                    "success": False,
                    "error": "Winetricks not found - cannot install dependencies",
                    "platform": result.platform
                }

            # Install dependencies using Wine + winetricks (quiet)
            cmd = [winetricks_cmd, "-q"] + dependencies

            self.logger.info("*** WINE INSTALL START ***")
            self.logger.info(f"*** Command: {' '.join(cmd)}")
            self.logger.info(f"*** Dependencies ({len(dependencies)}): {dependencies}")
            self.logger.info(f"*** ENV WINE: {env.get('WINE')}")
            self.logger.info(f"*** ENV WINEPREFIX: {env.get('WINEPREFIX')}")
            self.logger.info(f"*** ENV DISPLAY: {env.get('DISPLAY')}")
            self.logger.info(f"*** ENV XDG_RUNTIME_DIR: {env.get('XDG_RUNTIME_DIR')}")

            result_cmd = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

            self.logger.info("*** WINETRICKS FINISHED ***")
            self.logger.info(f"*** EXIT CODE: {result_cmd.returncode}")
            self.logger.info(f"*** STDOUT LENGTH: {len(result_cmd.stdout)}")
            self.logger.info(f"*** STDERR LENGTH: {len(result_cmd.stderr)}")

            if result_cmd.stdout:
                stdout_lines = result_cmd.stdout.split('\n')
                self.logger.info(f"*** STDOUT ({len(stdout_lines)} lines)")
                for i, line in enumerate(stdout_lines[:50]):
                    self.logger.info(f"*** STDOUT[{i}]: {line}")
                if len(stdout_lines) > 50:
                    self.logger.info(f"*** ... {len(stdout_lines) - 50} more stdout lines")

            if result_cmd.stderr:
                stderr_lines = result_cmd.stderr.split('\n')
                self.logger.warning(f"*** STDERR ({len(stderr_lines)} lines)")
                for i, line in enumerate(stderr_lines[:50]):
                    self.logger.warning(f"*** STDERR[{i}]: {line}")
                if len(stderr_lines) > 50:
                    self.logger.warning(f"*** ... {len(stderr_lines) - 50} more stderr lines")

            if result_cmd.returncode == 0:
                self.logger.info(f"Dependencies installed successfully using Wine for {result.game.name}")
                return {
                    "success": True,
                    "message": f"Dependencies installed for {result.game.name} using Wine",
                    "platform": result.platform,
                    "prefix_path": str(result.prefix.path)
                }
            else:
                self.logger.warning(f"Wine installation returned non-zero exit code: {result_cmd.returncode}")
                return {
                    "success": False,
                    "error": f"Wine dependency installation failed: {result_cmd.stderr}",
                    "platform": result.platform
                }

        except subprocess.TimeoutExpired:
            self.logger.error(f"Wine installation timed out after 10 minutes")
            return {
                "success": False,
                "error": "Wine dependency installation timed out after 10 minutes",
                "platform": result.platform
            }
        except Exception as e:
            self.logger.error(f"Failed to install Wine dependencies: {e}")
            return {
                "success": False,
                "error": f"Failed to install Wine dependencies: {e}",
                "platform": result.platform
            }
    
    def apply_regedit_smart(self, game_name: str, reg_file_path: str) -> Dict[str, Any]:
        """Apply registry settings to the best available prefix for a game"""
        self.logger.info(f"Applying registry settings for {game_name}...")

        # Find the best prefix
        best_result = self.find_best_prefix_for_game(game_name)
        if not best_result:
            self.logger.error(f"No suitable prefix found for {game_name}")
            return {
                "success": False,
                "error": f"No suitable prefix found for {game_name}"
            }

        self.logger.info(f"Using prefix: {best_result.prefix.path}")
        self.logger.info(f"Platform: {best_result.platform}")
        self.logger.info(f"Registry file: {reg_file_path}")

        # Check settings to determine Wine or Proton preference
        try:
            settings = SettingsManager()
            preferred_version = settings.get_preferred_proton_version()

            # Check if it's Wine (including Wine-TKG)
            if preferred_version in ["Wine", "Wine-TKG"]:
                self.logger.info("*** Using Wine for registry application ***")
                wine_path = settings.get_wine_path()
                if wine_path and os.path.exists(wine_path):
                    success = self._apply_registry_with_wine(wine_path, reg_file_path)
                else:
                    self.logger.error("Wine not found for registry application")
                    return {
                        "success": False,
                        "error": "Wine not found for registry application"
                    }
            else:
                # Use Proton (including Heroic Proton)
                self.logger.info("*** Using Proton for registry application ***")
                success = self.prefix_locator.apply_regedit_to_prefix(best_result.prefix, reg_file_path)

        except Exception as e:
            self.logger.error(f"Failed to determine registry method: {e}")
            # Fallback to prefix method
            success = self.prefix_locator.apply_regedit_to_prefix(best_result.prefix, reg_file_path)

        if success:
            self.logger.info(f"Registry settings applied successfully to {game_name}")
            return {
                "success": True,
                "message": f"Registry settings applied to {game_name}",
                "platform": best_result.platform,
                "prefix_path": str(best_result.prefix.path)
            }
        else:
            self.logger.error(f"Failed to apply registry settings to {game_name}")
            return {
                "success": False,
                "error": f"Failed to apply registry settings to {game_name}",
                "platform": best_result.platform
            }

    def _apply_registry_with_wine(self, wine_path: str, reg_file_path: str) -> bool:
        """Apply registry settings using Wine directly"""
        try:
            # Create temporary copy
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False) as temp_file:
                with open(reg_file_path, 'r') as f:
                    temp_file.write(f.read())
                temp_reg_path = temp_file.name

            # Set up Wine environment
            env = os.environ.copy()
            env["WINE"] = wine_path

            cmd = ["wine", "regedit", temp_reg_path]
            self.logger.info(f"*** WINE REGISTRY: Running {' '.join(cmd)} ***")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)

            # Cleanup
            Path(temp_reg_path).unlink(missing_ok=True)

            if result.returncode == 0:
                self.logger.info("*** WINE REGISTRY: Success! ***")
                return True
            else:
                self.logger.error(f"Wine registry application failed: {result.returncode}")
                return False

        except Exception as e:
            self.logger.error(f"Wine registry application error: {e}")
            return False
    
    def install_dotnet_smart(self, game_name: str) -> Dict[str, Any]:
        """Install .NET SDK to the best available prefix for a game"""
        self.logger.info(f"Installing .NET SDK for {game_name}...")

        # Find the best prefix
        best_result = self.find_best_prefix_for_game(game_name)
        if not best_result:
            self.logger.error(f"No suitable prefix found for {game_name}")
            return {
                "success": False,
                "error": f"No suitable prefix found for {game_name}"
            }

        self.logger.info(f"Using prefix: {best_result.prefix.path}")
        self.logger.info(f"Platform: {best_result.platform}")

        # Check settings to determine Wine or Proton preference
        try:

            settings = SettingsManager()
            preferred_version = settings.get_preferred_proton_version()

            # Check if it's Wine (including Wine-TKG)
            if preferred_version in ["Wine", "Wine-TKG"]:
                self.logger.info("*** DOTNET INSTALLER: Using Wine for .NET SDK installation ***")
                wine_path = settings.get_wine_path()
                if wine_path and os.path.exists(wine_path):
                    return self._install_dotnet_with_wine(wine_path)
                else:
                    self.logger.error("Wine not found for .NET SDK installation")
                    return {
                        "success": False,
                        "error": "Wine not found for .NET SDK installation"
                    }
            else:
                # Use platform-specific method
                if best_result.platform == "Steam":
                    self.logger.info("Using Steam method for .NET SDK installation")
                    return self._install_dotnet_steam(best_result)
                else:
                    self.logger.info("Using Wine method for .NET SDK installation")
                    return self._install_dotnet_wine(best_result)

        except Exception as e:
            self.logger.error(f"Failed to determine .NET SDK installation method: {e}")
            # Fallback to platform-specific method
            if best_result.platform == "Steam":
                return self._install_dotnet_steam(best_result)
            else:
                return self._install_dotnet_wine(best_result)

    def _install_dotnet_with_wine(self, wine_path: str) -> Dict[str, Any]:
        """Install .NET SDK using Wine directly"""
        self.logger.info(f"Installing .NET SDK using Wine: {wine_path}")

        try:
            # Use cached .NET 9 SDK if available
            from utils.dependency_cache_manager import DependencyCacheManager
            cache_manager = DependencyCacheManager()
            cached_file = cache_manager.get_cached_file("dotnet9_sdk")
            if cached_file:
                self.logger.info(f"Using cached .NET 9 SDK: {cached_file}")
                download_path = cached_file
            else:
                # Download .NET 9 SDK
                dotnet_url = "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe"
                dotnet_file = "dotnet-sdk-9.0.203-win-x64.exe"

                home_dir = str(Path.home())
                download_path = Path(home_dir) / "Downloads" / dotnet_file

                if not download_path.exists():
                    self.logger.info("Downloading .NET 9 SDK...")
                    import requests

                    response = requests.get(dotnet_url, stream=True)
                    with open(download_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                else:
                    self.logger.info(".NET 9 SDK installer already exists")

            # Install using Wine with proper headless environment
            env = os.environ.copy()
            env["WINE"] = wine_path
            env["DISPLAY"] = ":0"
            env["XDG_RUNTIME_DIR"] = "/tmp"
            env["WAYLAND_DISPLAY"] = ""
            env["QT_QPA_PLATFORM"] = "xcb"

            cmd = ["wine", str(download_path), "/quiet", "/norestart"]
            self.logger.info("Starting .NET 9 SDK installation with Wine...")

            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

            # Cleanup
            download_path.unlink(missing_ok=True)

            if result.returncode == 0:
                self.logger.info(".NET 9 SDK installed successfully with Wine")
                return {
                    "success": True,
                    "message": ".NET SDK installed using Wine"
                }
            else:
                self.logger.warning(f"Wine installation returned non-zero exit code: {result.returncode}")
                return {
                    "success": False,
                    "error": f"Wine .NET SDK installation failed: {result.stderr}"
                }

        except Exception as e:
            self.logger.error(f"Failed to install .NET SDK with Wine: {e}")
            return {
                "success": False,
                "error": f"Failed to install .NET SDK with Wine: {e}"
            }
    
    def _install_dotnet_steam(self, result: SmartPrefixResult) -> Dict[str, Any]:
        """Install .NET SDK for Steam games"""
        try:
            self.logger.info(f"Installing .NET SDK for Steam game: {result.game.name}")
            
            # Download .NET SDK installer first
            dotnet_url = "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe"
            installer_path = Path.home() / "Downloads" / "dotnet-sdk-9.0.203-win-x64.exe"
            
            self.logger.info(f".NET SDK installer: {installer_path}")
            
            # Download if not exists
            if not installer_path.exists():
                self.logger.info("Downloading .NET SDK installer...")
                import requests
                response = requests.get(dotnet_url, stream=True)
                with open(installer_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.logger.info(".NET SDK installer downloaded")
            else:
                self.logger.info(".NET SDK installer already exists")
            
            # Use protontricks-launch with local file path
            cmd = ["protontricks-launch", "--appid", result.game.app_id, str(installer_path), "/q"]
            self.logger.info(f"Starting .NET SDK installation with protontricks-launch...")
            self.logger.info(f"Command: {' '.join(cmd)}")
            self.logger.info("This may take several minutes...")
            
            result_cmd = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            self.logger.info(f".NET SDK installation completed with return code: {result_cmd.returncode}")
            if result_cmd.stdout:
                self.logger.info(f"Installation output:\n{result_cmd.stdout}")
            if result_cmd.stderr:
                self.logger.info(f"Installation warnings/errors:\n{result_cmd.stderr}")
            
            # Cleanup
            installer_path.unlink(missing_ok=True)
            self.logger.info("Cleaned up installer file")
            
            if result_cmd.returncode == 0:
                self.logger.info(f".NET SDK installed successfully for {result.game.name}")
                return {
                    "success": True,
                    "message": f".NET SDK installed for {result.game.name}",
                    "platform": result.platform,
                    "prefix_path": str(result.prefix.path)
                }
            else:
                self.logger.warning(f".NET SDK installation returned non-zero exit code: {result_cmd.returncode}")
                return {
                    "success": False,
                    "error": f".NET SDK installation failed: {result_cmd.stderr}",
                    "platform": result.platform
                }
                
        except subprocess.TimeoutExpired:
            self.logger.error(f".NET SDK installation timed out after 10 minutes")
            return {
                "success": False,
                "error": ".NET SDK installation timed out after 10 minutes",
                "platform": result.platform
            }
        except Exception as e:
            self.logger.error(f"Failed to install .NET SDK: {e}")
            return {
                "success": False,
                "error": f"Failed to install .NET SDK: {e}",
                "platform": result.platform
            }
    
    def _get_heroic_wine_binary(self, game: GameInfo) -> Optional[str]:
        """Get the Wine binary path - use Proton Experimental for consistency"""
        try:
            # Use Proton Experimental's proton file for Heroic games (more universal)
            steam_root = self._find_steam_root()

            steam_manager = SteamShortcutManager()
            all_libraries = steam_manager._get_steam_libraries()

            proton_versions = [
                "Proton - Experimental",
                "Proton 9.0",
                "Proton 8.0",
                "Proton 7.0",
                "Proton 6.0"
            ]

            for library_path in all_libraries:
                library_path = Path(library_path)

                # Check if this library has a steamapps/common directory
                common_path = library_path / "steamapps" / "common"
                if common_path.exists():
                    for version in proton_versions:
                        proton_path = common_path / version / "proton"
                        if proton_path.exists():
                                self.logger.info(f"Using Proton for Heroic: {proton_path}")
                                return str(proton_path)

            # Fallback: try to find Wine in common locations
            common_wine_paths = [
                "/usr/bin/wine",
                "/usr/local/bin/wine",
                "/opt/wine-stable/bin/wine",
                "/opt/wine-development/bin/wine"
            ]

            for wine_path in common_wine_paths:
                if Path(wine_path).exists():
                    self.logger.info(f"Using system Wine for Heroic: {wine_path}")
                    return wine_path

            return None

        except Exception as e:
            self.logger.warning(f"Could not determine Wine binary for Heroic: {e}")
            return None
    
    def _find_steam_root(self) -> Optional[str]:
        """Find Steam installation root"""
        try:
            steam_paths = [
                Path.home() / ".steam" / "steam",
                Path.home() / ".local" / "share" / "Steam",
                Path("/usr/share/steam"),
                Path("/opt/steam")
            ]
            
            for steam_path in steam_paths:
                if steam_path.exists() and (steam_path / "steamapps").exists():
                    return str(steam_path)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Could not find Steam root: {e}")
            return None
    
    def _install_dotnet_wine(self, result: SmartPrefixResult) -> Dict[str, Any]:
        """Install .NET SDK for Wine games"""
        try:
            self.logger.info(f"Installing .NET SDK for Wine game: {result.game.name}")
            
            # Download .NET SDK installer
            dotnet_url = "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe"
            installer_path = Path.home() / "Downloads" / "dotnet-sdk-9.0.203-win-x64.exe"
            
            self.logger.info(f".NET SDK installer: {installer_path}")
            
            # Download if not exists
            if not installer_path.exists():
                self.logger.info("Downloading .NET SDK installer...")
                import requests
                response = requests.get(dotnet_url, stream=True)
                with open(installer_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.logger.info(".NET SDK installer downloaded")
            else:
                self.logger.info(".NET SDK installer already exists")
            
            # Install using Wine with proper headless environment
            wine_prefix = str(result.prefix.path)
            env = os.environ.copy()
            env["WINEPREFIX"] = wine_prefix
            env["WINEARCH"] = "win64"
            
            # Add headless environment variables for .NET SDK installation
            env["DISPLAY"] = ":0"  # Set display for GUI applications
            env["XDG_RUNTIME_DIR"] = "/tmp"  # Set runtime directory
            env["WAYLAND_DISPLAY"] = ""  # Disable Wayland
            env["QT_QPA_PLATFORM"] = "xcb"  # Force X11 platform
            
            # Get the Wine binary path for Heroic games
            wine_bin = self._get_heroic_wine_binary(result.game)
            if wine_bin and Path(wine_bin).exists():
                env["WINE"] = wine_bin
                self.logger.info(f"Using Heroic Wine binary for .NET SDK: {wine_bin}")
            
            cmd = ["wine", str(installer_path), "/quiet", "/norestart"]
            self.logger.info(f"Starting .NET SDK installation with Wine...")
            self.logger.info(f"Command: {' '.join(cmd)}")
            self.logger.info(f"Environment: WINEPREFIX={wine_prefix}, WINEARCH=win64, WINE={wine_bin}")
            self.logger.info(f"Headless setup: DISPLAY={env.get('DISPLAY')}, XDG_RUNTIME_DIR={env.get('XDG_RUNTIME_DIR')}")
            self.logger.info("This may take several minutes...")
            
            result_cmd = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
            
            self.logger.info(f".NET SDK installation completed with return code: {result_cmd.returncode}")
            if result_cmd.stdout:
                self.logger.info(f"Installation output:\n{result_cmd.stdout}")
            if result_cmd.stderr:
                self.logger.info(f"Installation warnings/errors:\n{result_cmd.stderr}")
            
            # Cleanup
            installer_path.unlink(missing_ok=True)
            self.logger.info("Cleaned up installer file")
            
            if result_cmd.returncode == 0:
                self.logger.info(f".NET SDK installed successfully for {result.game.name}")
                return {
                    "success": True,
                    "message": f".NET SDK installed for {result.game.name}",
                    "platform": result.platform,
                    "prefix_path": wine_prefix
                }
            else:
                self.logger.warning(f".NET SDK installation returned non-zero exit code: {result_cmd.returncode}")
                return {
                    "success": False,
                    "error": f".NET SDK installation failed: {result_cmd.stderr}",
                    "platform": result.platform
                }
                
        except subprocess.TimeoutExpired:
            self.logger.error(f".NET SDK installation timed out after 10 minutes")
            return {
                "success": False,
                "error": ".NET SDK installation timed out after 10 minutes",
                "platform": result.platform
            }
        except Exception as e:
            self.logger.error(f"Failed to install .NET SDK: {e}")
            return {
                "success": False,
                "error": f"Failed to install .NET SDK: {e}",
                "platform": result.platform
            }
    
    def _get_heroic_wine_binary(self, game: GameInfo) -> Optional[str]:
        """Get the Wine binary path from Heroic's configuration"""
        try:
            # Look for Heroic's configuration files
            heroic_config_paths = [
                Path.home() / ".config" / "heroic" / "config.json",
                Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic" / "config.json",  # Flatpak
                Path.home() / "Games" / "Heroic" / "config.json"
            ]
            
            for config_path in heroic_config_paths:
                if config_path.exists():
                    import json
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    
                    # Look for Wine configuration
                    wine_config = config.get("wine", {})
                    wine_bin = wine_config.get("winePrefix", {}).get("wineBin", "")
                    
                    if wine_bin and Path(wine_bin).exists():
                        return wine_bin
                    
                    # Alternative: look for wineVersion in game-specific config
                    wine_version = wine_config.get("wineVersion", {})
                    if wine_version:
                        wine_bin = wine_version.get("bin", "")
                        if wine_bin and Path(wine_bin).exists():
                            return wine_bin
            
            # Fallback: try to find Wine in common locations
            common_wine_paths = [
                "/usr/bin/wine",
                "/usr/local/bin/wine",
                "/opt/wine-stable/bin/wine",
                "/opt/wine-development/bin/wine"
            ]
            
            for wine_path in common_wine_paths:
                if Path(wine_path).exists():
                    return wine_path
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Could not determine Heroic Wine binary: {e}")
            return None

    def _get_heroic_wine_binary_for_steam(self) -> Optional[str]:
        """Get Heroic's Wine binary for use with Steam games (faster than protontricks)"""
        try:
            # FIRST: Check user settings for custom Proton path
            custom_proton_path = self.settings.get_proton_path()
            if custom_proton_path:
                self.logger.info(f"Using user-configured Proton path: {custom_proton_path}")
                return custom_proton_path

            # SECOND: If auto-detection is disabled, don't proceed with automatic detection
            if not self.settings.should_auto_detect():
                self.logger.info("Auto-detection disabled, skipping automatic Proton detection")
                return None

            # Use Proton Experimental's proton file for Heroic games (more universal)
            steam_root = self._find_steam_root()
            if steam_root:
                # Try multiple Proton versions in order of preference
                proton_versions = [
                    "Proton - Experimental",
                    "Proton 9.0",
                    "Proton 8.0",
                    "Proton 7.0",
                    "Proton 6.0"
                ]

                # Check ALL Steam libraries for Proton installations
                from utils.steam_shortcut_manager import SteamShortcutManager
                steam_manager = SteamShortcutManager()
                all_libraries = steam_manager._get_steam_libraries()

                for library_path in all_libraries:
                    library_path = Path(library_path)

                    # Check if this library has a steamapps/common directory
                    common_path = library_path / "steamapps" / "common"
                    if common_path.exists():
                        for version in proton_versions:
                            proton_path = common_path / version / "proton"
                            if proton_path.exists():
                                self.logger.info(f"Found Heroic-style Wine binary for Steam: {proton_path}")
                                return str(proton_path)

                # Also check compatibility tools directory for custom Proton versions
                compat_tools_dirs = [
                    Path(steam_root) / "compatibilitytools.d",
                    Path.home() / ".steam" / "root" / "compatibilitytools.d",
                    Path.home() / ".local" / "share" / "Steam" / "compatibilitytools.d",
                ]

                for compat_dir in compat_tools_dirs:
                    if compat_dir.exists():
                        for tool_dir in compat_dir.iterdir():
                            if tool_dir.is_dir() and "proton" in tool_dir.name.lower():
                                proton_path = tool_dir / "proton"
                                if proton_path.exists():
                                    self.logger.info(f"Found Proton in compatibility tools: {proton_path}")
                                    return str(proton_path)

            # Fallback: Check for any proton binary in the system PATH
            try:
                import subprocess
                result = subprocess.run(["which", "proton"], capture_output=True, text=True)
                if result.returncode == 0:
                    proton_path = result.stdout.strip()
                    if proton_path and Path(proton_path).exists():
                        self.logger.info(f"Found Proton in PATH: {proton_path}")
                        return proton_path
            except Exception as e:
                self.logger.debug(f"Could not check PATH for proton: {e}")

            # Last resort: Try to find proton in common alternative locations
            common_proton_locations = [
                "/usr/local/bin/proton",
                "/opt/proton/proton",
                "/usr/bin/proton"
            ]

            for proton_path in common_proton_locations:
                if Path(proton_path).exists():
                    self.logger.info(f"Found Proton in common location: {proton_path}")
                    return proton_path

            return None

        except Exception as e:
            self.logger.warning(f"Could not determine Heroic Wine binary for Steam: {e}")
            return None

    def _install_dependencies_steam_with_heroic(self, result: SmartPrefixResult, dependencies: List[str], wine_bin: str) -> Dict[str, Any]:
        """Install Steam dependencies using Proton's verb-based interface (same method as MO2)"""
        try:
            self.logger.info(f"Installing Steam dependencies using Proton verb interface for {result.game.name}...")

            # Use Proton's verb-based interface like MO2 does
            wine_prefix = str(result.prefix.path)

            # Extract compat data path from prefix path
            if "/compatdata/" in wine_prefix and wine_prefix.endswith("/pfx"):
                compat_data_path = wine_prefix.rsplit("/pfx", 1)[0]
                self.logger.info(f"Using compat data path: {compat_data_path}")
            else:
                return {
                    "success": False,
                    "error": f"Invalid Steam compatdata path format: {wine_prefix}",
                    "platform": result.platform
                }

            # Find Steam root from compat data path
            steam_root = compat_data_path.split("/steamapps/compatdata/")[0]
            self.logger.info(f"Using Steam root: {steam_root}")

            # Find Proton path (wine_bin should be the proton executable)
            proton_path = wine_bin
            if not os.path.exists(proton_path):
                return {
                    "success": False,
                    "error": f"Proton path not found: {proton_path}",
                    "platform": result.platform
                }

            self.logger.info(f"Using Proton: {proton_path}")

            # Set up Proton environment
            env = os.environ.copy()
            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam_root
            env["STEAM_COMPAT_DATA_PATH"] = compat_data_path

            self.logger.info(f"Environment: STEAM_COMPAT_CLIENT_INSTALL_PATH={steam_root}")
            self.logger.info(f"Environment: STEAM_COMPAT_DATA_PATH={compat_data_path}")

            # Install each dependency using Proton run winetricks (same as MO2)
            success_count = 0
            failed_deps = []

            self.logger.info(f"Installing {len(dependencies)} dependencies using Proton verb interface:")
            for i, dep in enumerate(dependencies, 1):
                self.logger.info(f"   {i}/{len(dependencies)}: Installing {dep}...")

                # Use Proton's verb interface: proton run winetricks dep
                cmd = [proton_path, "run", "winetricks", dep]

                self.logger.info(f"Running: {' '.join(cmd)}")

                try:
                    result_cmd = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)

                    if result_cmd.returncode == 0:
                        self.logger.info(f"   Successfully installed {dep}")
                        success_count += 1
                    else:
                        self.logger.warning(f"   Failed to install {dep}: {result_cmd.stderr}")
                        failed_deps.append(dep)

                except subprocess.TimeoutExpired:
                    self.logger.warning(f"   Timeout installing {dep}")
                    failed_deps.append(dep)
                except Exception as e:
                    self.logger.warning(f"   Error installing {dep}: {e}")
                    failed_deps.append(dep)

            # Report results
            self.logger.info(f"Installation complete: {success_count}/{len(dependencies)} successful")

            if success_count == len(dependencies):
                self.logger.info(f"All dependencies installed successfully for {result.game.name}")
                return {
                    "success": True,
                    "message": f"All dependencies installed for {result.game.name} (using Proton verb interface)",
                    "platform": result.platform,
                    "prefix_path": wine_prefix
                }
            elif success_count > 0:
                self.logger.warning(f"Partial success: {success_count}/{len(dependencies)} dependencies installed")
                self.logger.warning(f"Failed dependencies: {', '.join(failed_deps)}")
                return {
                    "success": True,
                    "message": f"Partial success: {success_count}/{len(dependencies)} dependencies installed for {result.game.name}",
                    "platform": result.platform,
                    "prefix_path": wine_prefix,
                    "warning": f"Failed to install: {', '.join(failed_deps)}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to install any dependencies. Failed: {', '.join(failed_deps)}",
                    "platform": result.platform
                }
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"Winetricks installation timed out after 10 minutes")
            return {
                "success": False,
                "error": "Dependency installation timed out after 10 minutes",
                "platform": result.platform
            }
        except Exception as e:
            self.logger.error(f"Failed to install Steam dependencies with Heroic method: {e}")
            return {
                "success": False,
                "error": f"Failed to install dependencies: {e}",
                "platform": result.platform
            }
