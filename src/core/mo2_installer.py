"""
MO2 Installer module for downloading and installing Mod Organizer 2
"""
import json
import os
import subprocess
import tempfile
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import requests

from src.utils.logger import get_logger
from src.utils.steam_utils import SteamUtils


class GitHubRelease:
    """GitHub release data structure"""
    def __init__(self, tag_name: str, assets: list):
        self.tag_name = tag_name
        self.assets = assets


class MO2Installer:
    """Handles downloading and installing Mod Organizer 2"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.steam_utils = SteamUtils()
        self.progress_callback = None
        self.log_callback = None
    
    def set_progress_callback(self, callback):
        """Set a callback function for progress updates"""
        self.progress_callback = callback
    
    def _cleanup_old_cache(self, current_filename: str):
        """Clean up old cached MO2 files"""
        try:
            cache_dir = os.path.join(os.path.expanduser("~"), "NaK", "cache")
            if not os.path.exists(cache_dir):
                return
            
            # Remove old MO2 archives that aren't the current one
            for filename in os.listdir(cache_dir):
                if filename.startswith("ModOrganizer") and filename != current_filename:
                    old_file = os.path.join(cache_dir, filename)
                    try:
                        os.remove(old_file)
                        self.logger.info(f"Removed old cached file: {filename}")
                    except OSError as e:
                        self.logger.warning(f"Could not remove old cached file {filename}: {e}")
        except Exception as e:
            self.logger.warning(f"Error cleaning up old cache: {e}")
    
    def set_log_callback(self, callback):
        """Set log callback for status messages"""
        self.log_callback = callback
    
    def _log_progress(self, message):
        """Log progress message to both logger and callback"""
        self.logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def _send_progress_update(self, percent):
        """Send progress percentage update to callback"""
        if self.progress_callback:
            # Call progress callback with percent, 0, 0 for non-download operations
            self.progress_callback(percent, 0, 0)
    
    def download_mo2(self, install_dir: Optional[str] = None, custom_name: Optional[str] = None) -> Dict[str, Any]:
        """Download and install the latest version of Mod Organizer 2 with complete Steam integration"""
        try:
            self.logger.info("Starting MO2 download and installation with Steam integration")
            
            # Skip dependency check - should be done on launch
            # Get latest release info
            self._log_progress("Fetching latest MO2 release information...")
            release = self._get_latest_release()
            if not release:
                return {
                    "success": False,
                    "error": "Failed to get latest release information"
                }
            
            self._log_progress(f"Found latest version: {release.tag_name}")
            
            # Find the correct asset
            self._log_progress("Finding download asset...")
            download_url, filename = self._find_mo2_asset(release)
            if not download_url or not filename:
                return {
                    "success": False,
                    "error": "Could not find appropriate MO2 asset"
                }
            
            # Clean up old cached files
            self._cleanup_old_cache(filename)
            
            self._log_progress(f"Found asset: {filename}")
            
            # Get installation directory
            if not install_dir:
                install_dir = self._get_install_directory()
            if not install_dir:
                return {
                    "success": False,
                    "error": "No installation directory specified"
                }
            
            # Download the file
            temp_file = self._download_file(download_url, filename, progress_callback=getattr(self, 'progress_callback', None))
            if not temp_file:
                return {
                    "success": False,
                    "error": "Failed to download MO2"
                }
            
            # Clean up temp file on exit
            try:
                # Extract the archive
                self._log_progress("Extracting MO2 archive...")
                actual_install_dir = self._extract_archive(temp_file, install_dir)
                if not actual_install_dir:
                    return {
                        "success": False,
                        "error": "Failed to extract MO2 archive"
                    }
                
                # Verify installation
                self._log_progress("Verifying installation...")
                verify_result = self._verify_installation(actual_install_dir)
                if not verify_result["success"]:
                    return verify_result
                
                self._log_progress("MO2 installation verified successfully!")
                
                # Find the MO2 executable
                self._log_progress("Finding MO2 executable...")
                mo2_exe = self._find_mo2_executable(actual_install_dir)
                if not mo2_exe:
                    return {
                        "success": False,
                        "error": "Could not find ModOrganizer.exe"
                    }
                
                # Use custom name or default
                mo2_name = custom_name if custom_name else "Mod Organizer 2"
                
                # Add MO2 to Steam with complete integration
                self._log_progress(f"Adding {mo2_name} to Steam...")
                steam_result = self._add_mo2_to_steam(mo2_exe, mo2_name)
                if not steam_result["success"]:
                    self.logger.error(f"Steam integration failed: {steam_result}")
                    return steam_result

                # Auto-install dependencies
                self._log_progress("Installing dependencies...")
                self.logger.info(f"Starting dependency installation for AppID: {steam_result['app_id']}")
                dependency_result = self._auto_install_dependencies(steam_result["app_id"], mo2_name)

                # Setup save symlinks
                save_symlink_result = self._setup_save_symlinks(actual_install_dir, str(steam_result["app_id"]))

                # Merge results
                result = {
                    "success": True,
                    "install_dir": actual_install_dir,
                    "mo2_exe": mo2_exe,
                    "version": release.tag_name,
                    "mo2_name": mo2_name,
                    "app_id": steam_result["app_id"],
                    "compat_data_path": steam_result["compat_data_path"],
                    "message": f"Mod Organizer 2 {release.tag_name} installed and added to Steam successfully!",
                    "steam_integration": steam_result,
                    "dependency_installation": dependency_result,
                    "save_symlinks": save_symlink_result
                }

                # Update message if dependencies were installed
                if dependency_result["success"]:
                    result["message"] = f"Mod Organizer 2 {release.tag_name} installed, added to Steam, and dependencies installed successfully!"

                # Add save symlinks info to message
                if save_symlink_result.get("success") and save_symlink_result.get("games_symlinked", 0) > 0:
                    result["message"] += f" Save symlinks created for {save_symlink_result['games_symlinked']} game(s)."

                return result
                
            finally:
                # Clean up temporary file
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        self.logger.info("Cleaned up temporary file")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up temporary file: {e}")
                
        except Exception as e:
            self.logger.error(f"MO2 installation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def setup_existing(self, mo2_dir: str, custom_name: str = "Mod Organizer 2") -> Dict[str, Any]:
        """Setup existing MO2 installation from directory"""
        try:
            self._log_progress(f"Setting up existing MO2 installation from: {mo2_dir}")
            self._send_progress_update(10)

            # Verify the directory exists
            self._log_progress("Verifying MO2 directory...")
            if not os.path.exists(mo2_dir):
                return {"success": False, "error": f"Directory does not exist: {mo2_dir}"}
            self._send_progress_update(20)

            # Find ModOrganizer.exe in the directory
            self._log_progress("Finding ModOrganizer.exe...")
            mo2_exe = self._find_mo2_executable(mo2_dir)
            if not mo2_exe:
                return {"success": False, "error": f"Could not find ModOrganizer.exe in: {mo2_dir}"}
            self._send_progress_update(30)

            # Check installed version
            self._log_progress("Checking MO2 version...")
            installed_version = self._get_installed_mo2_version(mo2_dir)
            if installed_version:
                self._log_progress(f"Found MO2 version: {installed_version}")
            else:
                self._log_progress("Could not determine MO2 version")

            # Use the provided custom name
            self._log_progress(f"Using installation name: {custom_name}")

            # Add to Steam
            self._log_progress(f"Adding {custom_name} to Steam...")
            steam_result = self._add_mo2_to_steam(mo2_exe, custom_name)
            if not steam_result["success"]:
                return steam_result
            self._send_progress_update(50)

            app_id = steam_result.get("app_id")
            self._log_progress(f"Successfully added to Steam with AppID: {app_id}")

            # Install dependencies directly
            self._log_progress("Installing MO2 dependencies...")
            from src.core.dependency_installer import DependencyInstaller
            deps = DependencyInstaller()

            # Set up callback for live logging to GUI
            if self.log_callback:
                deps.set_log_callback(self.log_callback)

            self._send_progress_update(60)
            dep_result = deps.install_mo2_dependencies_for_game(str(app_id))
            self._send_progress_update(85)

            # Setup save symlinks
            self._log_progress("Setting up save game symlinks...")
            save_symlink_result = self._setup_save_symlinks(mo2_dir, str(app_id))
            self._send_progress_update(95)

            self._log_progress("Setup completed successfully!")

            message = f"Existing MO2 installation configured successfully!"
            if save_symlink_result.get("success") and save_symlink_result.get("games_symlinked", 0) > 0:
                message += f" Save symlinks created for {save_symlink_result['games_symlinked']} game(s)."

            return {
                "success": True,
                "install_dir": mo2_dir,
                "mo2_exe": mo2_exe,
                "mo2_name": custom_name,
                "mo2_version": installed_version,
                "app_id": app_id,
                "message": message,
                "steam_integration": steam_result,
                "dependency_installation": dep_result,
                "save_symlinks": save_symlink_result
            }

        except Exception as e:
            self.logger.error(f"Failed to setup existing MO2: {e}")
            return {"success": False, "error": str(e)}
    
    def setup_existing_exe(self, mo2_exe: str, custom_name: str) -> Dict[str, Any]:
        """Setup existing MO2 installation from executable file"""
        try:
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("SETUP_EXISTING_EXE METHOD CALLED")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"Setting up existing MO2 installation from: {mo2_exe}")
            self.logger.info(f"Custom name: {custom_name}")
            
            # Verify the executable exists
            if not os.path.exists(mo2_exe):
                return {"success": False, "error": f"Executable does not exist: {mo2_exe}"}
            
            # Verify it's ModOrganizer.exe
            if not mo2_exe.lower().endswith("modorganizer.exe"):
                return {"success": False, "error": f"File is not ModOrganizer.exe: {mo2_exe}"}
            
            # Add to Steam
            steam_result = self._add_mo2_to_steam(mo2_exe, custom_name)
            if not steam_result["success"]:
                self.logger.error(f"Steam integration failed: {steam_result}")
                return steam_result

            app_id = steam_result["app_id"]
            self.logger.info(f"Got AppID: {app_id}")

            # Install dependencies directly
            self.logger.info("Installing MO2 dependencies...")
            from src.core.dependency_installer import DependencyInstaller
            deps = DependencyInstaller()
            dep_result = deps.install_mo2_dependencies_for_game(str(app_id))

            # Setup save symlinks
            from pathlib import Path
            mo2_dir = str(Path(mo2_exe).parent)
            save_symlink_result = self._setup_save_symlinks(mo2_dir, str(app_id))

            message = f"Existing MO2 installation configured successfully!"
            if save_symlink_result.get("success") and save_symlink_result.get("games_symlinked", 0) > 0:
                message += f" Save symlinks created for {save_symlink_result['games_symlinked']} game(s)."

            return {
                "success": True,
                "mo2_exe": mo2_exe,
                "mo2_name": custom_name,
                "app_id": app_id,
                "message": message,
                "steam_integration": steam_result,
                "dependency_installation": dep_result,
                "save_symlinks": save_symlink_result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to setup existing MO2: {e}")
            return {"success": False, "error": str(e)}
    
    def _find_proton_path(self, steam_root: str, app_id: str) -> Optional[str]:
        """Find Proton path using GameFinder and smart prefix management"""
        try:
            self.logger.info(f"Searching for Proton path in steam_root: {steam_root}")

            # Use simple direct approach first - check common Proton locations
            from pathlib import Path
            proton_paths = [
                Path(steam_root) / "steamapps" / "common" / "Proton - Experimental" / "proton",
                Path(steam_root) / "steamapps" / "common" / "Proton 9.0" / "proton",
                Path(steam_root) / "steamapps" / "common" / "Proton 8.0" / "proton",
                Path(steam_root) / "steamapps" / "common" / "Proton 7.0" / "proton"
            ]

            for proton_path in proton_paths:
                self.logger.info(f"Checking Proton path: {proton_path}")
                if proton_path.exists():
                    self.logger.info(f"Found Proton at: {proton_path}")
                    return str(proton_path)

            # Try using the comprehensive Proton tool manager
            try:
                from utils.proton_tool_manager import ProtonToolManager
                self.logger.info("Trying ProtonToolManager...")
                proton_manager = ProtonToolManager(steam_root)
                proton_path = proton_manager._find_proton_installation()
                if proton_path:
                    self.logger.info(f"Found Proton via ProtonToolManager: {proton_path}")
                    return proton_path
            except Exception as e:
                self.logger.warning(f"ProtonToolManager failed: {e}")

            # Try smart prefix manager's approach
            try:
                from utils.smart_prefix_manager import SmartPrefixManager
                self.logger.info("Trying SmartPrefixManager...")
                prefix_manager = SmartPrefixManager()
                steam_root_found = prefix_manager._find_steam_root()
                if steam_root_found:
                    self.logger.info(f"SmartPrefixManager found steam root: {steam_root_found}")
                    fallback_paths = [
                        Path(steam_root_found) / "steamapps" / "common" / "Proton - Experimental" / "proton",
                        Path(steam_root_found) / "steamapps" / "common" / "Proton 9.0" / "proton",
                        Path(steam_root_found) / "steamapps" / "common" / "Proton 8.0" / "proton",
                        Path(steam_root_found) / "steamapps" / "common" / "Proton 7.0" / "proton"
                    ]

                    for proton_path in fallback_paths:
                        if proton_path.exists():
                            self.logger.info(f"Found Proton via SmartPrefixManager: {proton_path}")
                            return str(proton_path)
            except Exception as e:
                self.logger.warning(f"SmartPrefixManager failed: {e}")

            self.logger.error("No Proton installation found in any location")
            return None

        except Exception as e:
            self.logger.error(f"Failed to find Proton path: {e}")
            return None
    
    def _create_nxm_handler_script(self, app_id: str, mo2_exe: str, nxm_handler_path: str, steam_root: str) -> Optional[str]:
        """Create NXM handler script that works with both Wine and Proton"""
        try:
            home_dir = os.path.expanduser("~")
            applications_dir = os.path.join(home_dir, ".local", "share", "applications")
            os.makedirs(applications_dir, exist_ok=True)

            script_path = os.path.join(applications_dir, f"mo2-nxm-handler-{app_id}.sh")

            # Check settings to determine Wine or Proton preference
            try:
                from utils.settings_manager import SettingsManager
                settings = SettingsManager()
                preferred_version = settings.get_preferred_proton_version()

                # Attempt to detect prefix from MO2 executable path
                detected_prefix: Optional[str] = None
                try:
                    mo2_path = Path(mo2_exe).resolve()
                    self.logger.info(f"Analyzing MO2 path for prefix detection: {mo2_path}")
                    
                    # Check for drive_c marker (standard Wine prefix structure)
                    for parent in mo2_path.parents:
                        if parent.name.lower() == "drive_c":
                            detected_prefix = str(parent.parent)
                            self.logger.info(f"Detected prefix from drive_c marker: {detected_prefix}")
                            break
                    
                    # If no drive_c found, check for Heroic prefix locations
                    if not detected_prefix:
                        mo2_str = str(mo2_path)
                        self.logger.info(f"Searching for Heroic prefix for MO2 path: {mo2_str}")
                        
                        # Look for Heroic prefix directories
                        home_dir = Path.home()
                        heroic_prefix_locations = [
                            home_dir / "Games" / "Heroic" / "Prefixes" / "default",
                            home_dir / ".config" / "heroic" / "prefixes",
                            home_dir / ".local" / "share" / "heroic" / "prefixes",
                            home_dir / ".var" / "app" / "com.heroicgameslauncher.hgl" / "data" / "heroic" / "prefixes"
                        ]
                        
                        # Try to find a prefix that contains this MO2 installation
                        for prefix_dir in heroic_prefix_locations:
                            if prefix_dir.exists():
                                self.logger.info(f"Checking Heroic prefix directory: {prefix_dir}")
                                for prefix_path in prefix_dir.iterdir():
                                    if prefix_path.is_dir():
                                        # Check if this prefix contains the MO2 path
                                        drive_c = prefix_path / "drive_c"
                                        if drive_c.exists():
                                            # Convert MO2 path to Wine path and check if it exists
                                            try:
                                                # Get relative path from drive_c
                                                mo2_relative = mo2_path.relative_to(drive_c)
                                                if (drive_c / mo2_relative).exists():
                                                    detected_prefix = str(prefix_path)
                                                    self.logger.info(f"Found Heroic prefix containing MO2: {detected_prefix}")
                                                    break
                                            except ValueError:
                                                # MO2 path is not under this drive_c
                                                continue
                                if detected_prefix:
                                    break
                        
                        # If still no prefix found, check for MO2-specific prefix
                        if not detected_prefix:
                            mo2_prefix = home_dir / "Games" / "Heroic" / "Prefixes" / "default" / "MO2"
                            if mo2_prefix.exists() and (mo2_prefix / "drive_c").exists():
                                detected_prefix = str(mo2_prefix)
                                self.logger.info(f"Found MO2-specific Heroic prefix: {detected_prefix}")
                    
                    # Also check if the MO2 directory itself might be a prefix
                    if not detected_prefix:
                        mo2_dir = mo2_path.parent
                        # Check if this directory contains Wine-like structure
                        wine_markers = ["drive_c", "dosdevices", "system.reg", "user.reg"]
                        if any((mo2_dir / marker).exists() for marker in wine_markers):
                            detected_prefix = str(mo2_dir)
                            self.logger.info(f"Detected prefix from MO2 directory markers: {detected_prefix}")
                            
                except Exception as e:
                    self.logger.debug(f"Failed to derive prefix from MO2 path: {e}")

                # Fall back to smart prefix detection
                from utils.comprehensive_game_manager import ComprehensiveGameManager
                game_manager = ComprehensiveGameManager()
                best_prefix = game_manager.find_best_nxm_prefix("Mod Organizer 2")

                if not detected_prefix and best_prefix and best_prefix.prefix and best_prefix.prefix.path:
                    detected_prefix = str(best_prefix.prefix.path)

                detected_version = None
                if best_prefix and best_prefix.prefix and best_prefix.prefix.wine_version:
                    detected_version = best_prefix.prefix.wine_version

                # Helper to build script content with optional prefix data
                def build_script(use_wine: bool) -> str:
                    if use_wine:
                        wine_path = settings.get_wine_path()
                        if not wine_path or not os.path.exists(wine_path):
                            self.logger.error("Wine not found for NXM handler")
                            return ""
                        return self._create_wine_nxm_script(
                            mo2_exe,
                            nxm_handler_path,
                            wine_path,
                            detected_prefix,
                            detected_version
                        )
                    else:
                        return self._create_proton_nxm_script(
                            app_id,
                            mo2_exe,
                            nxm_handler_path,
                            steam_root,
                            detected_prefix
                        )

                # Check if it's Wine (including Wine-TKG)
                if preferred_version in ["Wine", "Wine-TKG"]:
                    script_content = build_script(use_wine=True)
                    if not script_content:
                        return None
                else:
                    script_content = build_script(use_wine=False)

            except Exception as e:
                self.logger.error(f"Failed to determine NXM handler method: {e}")
                script_content = self._create_proton_nxm_script(app_id, mo2_exe, nxm_handler_path, steam_root)

            # Write the script
            with open(script_path, 'w') as f:
                f.write(script_content)

            # Make it executable
            os.chmod(script_path, 0o755)

            self.logger.info(f"Created NXM handler script: {script_path}")
            return script_path

        except Exception as e:
            self.logger.error(f"Failed to create NXM handler script: {e}")
            return None
    def _find_existing_mo2_shortcut(self, mo2_exe: str) -> Optional[int]:
        """Check if a Steam shortcut already exists for this MO2 exe path"""
        try:
            if not self.steam_utils.shortcut_manager:
                return None

            # Normalize the exe path for comparison
            mo2_exe_normalized = mo2_exe.strip('"')

            # Get all existing shortcuts
            shortcuts = self.steam_utils.shortcut_manager.list_shortcuts()

            # Look for existing shortcut with matching exe path
            for shortcut in shortcuts:
                shortcut_exe = shortcut.exe.strip('"')
                if shortcut_exe == mo2_exe_normalized:
                    self.logger.info(f"Found existing shortcut for {mo2_exe}: AppID {shortcut.app_id}, Name: {shortcut.app_name}")
                    return shortcut.app_id

            return None

        except Exception as e:
            self.logger.warning(f"Error checking for existing shortcuts: {e}")
            return None

    def _add_mo2_to_steam(self, mo2_exe: str, mo2_name: str) -> Dict[str, Any]:
        """Add MO2 to Steam using SteamShortcutManager with complete integration

        Checks for existing shortcuts first to avoid creating duplicate prefixes
        """
        try:
            self.logger.info(f"Adding {mo2_name} to Steam with complete integration...")

            # Use SteamShortcutManager to add MO2 to Steam
            if not self.steam_utils.shortcut_manager:
                return {
                    "success": False,
                    "error": "Steam shortcut manager not available"
                }

            # Check if a shortcut already exists for this MO2 exe
            existing_app_id = self._find_existing_mo2_shortcut(mo2_exe)

            if existing_app_id:
                # Reuse existing prefix
                self.logger.info(f"Reusing existing Steam shortcut and prefix for {mo2_name} (AppID: {existing_app_id})")

                steam_root = self.steam_utils.get_steam_root()
                compat_data_path = f"{steam_root}/steamapps/compatdata/{existing_app_id}"

                # Check if prefix exists, if not create it
                pfx_path = f"{compat_data_path}/pfx"
                if not os.path.exists(pfx_path):
                    self.logger.info("Existing prefix not found, initializing...")
                    # Create and initialize prefix
                    try:
                        self.steam_utils.shortcut_manager.create_compat_data_folder(existing_app_id)
                        self.steam_utils.shortcut_manager.create_and_run_bat_file(compat_data_path, mo2_name)
                    except Exception as e:
                        self.logger.warning(f"Failed to initialize prefix: {e}")

                return {
                    "success": True,
                    "app_id": existing_app_id,
                    "compat_data_path": compat_data_path,
                    "message": f"Reusing existing Steam shortcut for {mo2_name} (AppID {existing_app_id})",
                    "reused_prefix": True
                }

            # No existing shortcut found - create new one
            self.logger.info("No existing shortcut found, creating new one...")

            # Add MO2 to Steam and create prefix
            steam_result = self.steam_utils.shortcut_manager.add_game_to_steam(
                app_name=mo2_name,
                exe_path=mo2_exe,
                proton_tool="proton_experimental"  # Use Proton Experimental by default
            )

            if not steam_result["success"]:
                return steam_result

            app_id = steam_result["app_id"]
            compat_data_path = steam_result["compat_data_path"]

            self.logger.info(f"Successfully added {mo2_name} to Steam with AppID: {app_id}")
            self.logger.info(f"Compat data path: {compat_data_path}")

            return {
                "success": True,
                "app_id": app_id,
                "compat_data_path": compat_data_path,
                "message": f"Successfully added {mo2_name} to Steam with AppID {app_id}",
                "reused_prefix": False
            }

        except Exception as e:
            self.logger.error(f"Failed to add MO2 to Steam: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _setup_save_symlinks(self, mo2_install_dir: str, mo2_app_id: str) -> Dict[str, Any]:
        """Setup save game symlinks for all detected Bethesda games"""
        try:
            self._log_progress("Setting up save game symlinks...")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("SETTING UP SAVE GAME SYMLINKS")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"MO2 Install Directory: {mo2_install_dir}")
            self.logger.info(f"MO2 AppID: {mo2_app_id}")

            from src.utils.save_symlinker import SaveSymlinker
            symlinker = SaveSymlinker()

            # Create "Save Games Folder" in MO2 directory
            from pathlib import Path
            mo2_path = Path(mo2_install_dir)
            save_games_folder = mo2_path / "Save Games Folder"
            save_games_folder.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created Save Games Folder: {save_games_folder}")
            self._log_progress(f"Created Save Games Folder in MO2 directory")

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

            # Get MO2 compatdata path
            steam_root = self.steam_utils.get_steam_root()
            mo2_compatdata = Path(steam_root) / "steamapps" / "compatdata" / str(mo2_app_id)

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
                        self.logger.info(f"  ✓ Created folder symlink: {folder_symlink} → {save_path}")
                    else:
                        self.logger.info(f"  ✓ Folder symlink already exists: {folder_symlink}")

                    # 2. Create symlink in MO2 prefix (compatdata)
                    location_type = game['location_type']
                    save_identifier = game['save_folder']

                    if location_type == "my_games":
                        # Create symlink in My Games
                        prefix_save_location = mo2_compatdata / "pfx" / "drive_c" / "users" / "steamuser" / "My Documents" / "My Games" / save_identifier
                        prefix_save_location.parent.mkdir(parents=True, exist_ok=True)

                        if not prefix_save_location.exists() and not prefix_save_location.is_symlink():
                            prefix_save_location.symlink_to(save_path, target_is_directory=True)
                            self.logger.info(f"  ✓ Created prefix symlink: {prefix_save_location} → {save_path}")
                        else:
                            self.logger.info(f"  ✓ Prefix symlink already exists: {prefix_save_location}")

                    symlinked_count += 1
                    self.logger.info(f"  ✓ Successfully set up symlinks for {game_name}")

                except Exception as e:
                    self.logger.error(f"  ✗ Failed to setup symlinks for {game_name}: {e}")
                    failed_games.append(game_name)

            result_message = f"Set up save symlinks for {symlinked_count}/{len(games_with_saves)} game(s)"
            if failed_games:
                result_message += f" ({len(failed_games)} failed: {', '.join(failed_games)})"

            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("SAVE SYMLINK SETUP COMPLETE")
            self.logger.info("═══════════════════════════════════════════════════════════════")
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
                "error": str(e)
            }

    def _auto_install_dependencies(self, app_id: int, app_name: str) -> Dict[str, Any]:
        """Automatically install dependencies for a newly created game"""
        try:
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("AUTO-INSTALLING MO2 DEPENDENCIES")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"Target: {app_name} (AppID: {app_id})")
            self.logger.info("This will install all dependencies required for MO2 to function")

            # Wait a moment for Steam to recognize the new shortcut
            self.logger.info("Waiting for Steam to recognize the new shortcut...")
            time.sleep(2)

            # Try to get the game from Steam shortcuts
            self.logger.info("Checking Steam shortcuts for newly created game...")
            games = self.steam_utils.get_non_steam_games()
            self.logger.info(f"Found {len(games)} total games in Steam shortcuts")

            if not games:
                self.logger.warning("Could not get Steam games list")
                self.logger.warning("This may be because Steam needs to be restarted")
                return {
                    "success": True,
                    "message": "Game created successfully! Dependencies will be installed after Steam restart.",
                    "note": "Steam needs to be restarted to see the new shortcut before dependencies can be installed."
                }

            # Log all games for debugging
            self.logger.info("All games in Steam shortcuts:")
            for i, game in enumerate(games, 1):
                self.logger.info(f"   {i:2d}. {game.get('Name')} (AppID: {game.get('AppID')})")

            # Look for our newly created game
            found_game = None
            self.logger.info(f"Looking for game with AppID: {app_id}")
            for game in games:
                game_app_id = game.get('AppID')
                if game_app_id == str(app_id):
                    found_game = game
                    self.logger.info(f"SUCCESS: Found our newly created game: {game.get('Name')}")
                    break

            if not found_game:
                self.logger.warning("Game not yet visible in Steam shortcuts - this is normal")
                self.logger.warning("Steam may need time to recognize the new shortcut")
                return {
                    "success": True,
                    "message": "Game created successfully! Dependencies will be installed after Steam restart.",
                    "note": "Steam needs to be restarted to see the new shortcut before dependencies can be installed."
                }
            
            # Game found! Install dependencies
            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info("PROCEEDING WITH DEPENDENCY INSTALLATION")
            self.logger.info("───────────────────────────────────────────────────────────────")
            self.logger.info(f"Target Game: {found_game['Name']}")
            self.logger.info(f"AppID: {app_id}")
            self.logger.info("About to install comprehensive MO2 dependencies...")

            from src.core.dependency_installer import DependencyInstaller
            deps = DependencyInstaller()

            # Set up callback for live logging to GUI
            if self.log_callback:
                self.logger.info("Setting up live logging callback for GUI updates")
                deps.set_log_callback(self.log_callback)

            # Install MO2 dependencies for this game
            self.logger.info("Calling dependency installer...")
            result = deps.install_mo2_dependencies_for_game(str(app_id))

            if not result["success"]:
                self.logger.error("═══════════════════════════════════════════════════════════════")
                self.logger.error("DEPENDENCY INSTALLATION FAILED")
                self.logger.error("═══════════════════════════════════════════════════════════════")
                self.logger.error(f"Failed to install dependencies: {result.get('error', 'Unknown error')}")
                return result

            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("DEPENDENCY INSTALLATION COMPLETED SUCCESSFULLY")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("Successfully installed MO2 dependencies!")
            self.logger.info(f"Target: {app_name} (AppID: {app_id})")

            return {
                "success": True,
                "message": f"Successfully installed MO2 dependencies for {app_name}!",
                "app_id": app_id,
                "game_name": app_name,
                "dependency_result": result  # Include full dependency result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to auto-install dependencies: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _check_dependencies(self) -> Dict[str, Any]:
        """Check if required dependencies are available"""
        try:
            self.logger.info("Checking system dependencies...")
            
            # Check if Steam is installed
            if not self.steam_utils.get_steam_root():
                return {
                    "success": False,
                    "error": "Steam installation not found"
                }
            
            # Check if SteamShortcutManager is available
            if not self.steam_utils.shortcut_manager:
                return {
                    "success": False,
                    "error": "Steam shortcut manager not available"
                }
            
            return {"success": True}
            
        except Exception as e:
            self.logger.error(f"Dependency check failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_latest_release(self) -> Optional[GitHubRelease]:
        """Get the latest MO2 release from GitHub"""
        try:
            self.logger.info("Fetching latest MO2 release from GitHub...")
            
            # MO2 GitHub repository
            api_url = "https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest"
            
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            release_data = response.json()
            tag_name = release_data.get("tag_name", "")
            assets = release_data.get("assets", [])
            
            if not tag_name or not assets:
                self.logger.error("Invalid release data received from GitHub")
                return None
            
            self.logger.info(f"Found latest release: {tag_name}")
            return GitHubRelease(tag_name, assets)
            
        except Exception as e:
            self.logger.error(f"Failed to get latest release: {e}")
            return None
    
    def _find_mo2_asset(self, release: GitHubRelease) -> Tuple[Optional[str], Optional[str]]:
        """Find the appropriate MO2 asset for download"""
        try:
            self.logger.info("Finding appropriate MO2 asset...")
            
            # Priority 1: Look for the portable archive
            for asset in release.assets:
                name = asset.get("name", "")
                download_url = asset.get("browser_download_url", "")
                
                # Look for portable archive (usually ends with .7z or .zip)
                if "portable" in name.lower() and (name.endswith(".7z") or name.endswith(".zip")):
                    self.logger.info(f"Found portable asset: {name}")
                    return download_url, name
            
            # Priority 2: Look for main binary archive (not PDBs, src, or debug symbols)
            for asset in release.assets:
                name = asset.get("name", "")
                download_url = asset.get("browser_download_url", "")
                
                # Skip debug symbols, PDBs, source, and other non-binary files
                if any(skip in name.lower() for skip in ["pdb", "debug", "src", "uibase", "commits"]):
                    continue
                
                # Look for main binary archive (usually just "Mod.Organizer-X.X.X.7z")
                if name.endswith(".7z") and "Mod.Organizer" in name and not any(skip in name.lower() for skip in ["pdb", "debug", "src", "uibase", "commits"]):
                    self.logger.info(f"Found main binary archive asset: {name}")
                    return download_url, name
            
            # Priority 3: Fallback to any archive (excluding PDBs)
            for asset in release.assets:
                name = asset.get("name", "")
                download_url = asset.get("browser_download_url", "")
                
                # Skip debug symbols and PDBs
                if "pdb" in name.lower() or "debug" in name.lower():
                    continue
                
                if name.endswith(".7z") or name.endswith(".zip"):
                    self.logger.info(f"Found fallback archive asset: {name}")
                    return download_url, name
            
            self.logger.error("No suitable MO2 asset found")
            return None, None
            
        except Exception as e:
            self.logger.error(f"Failed to find MO2 asset: {e}")
            return None, None
    
    def _get_install_directory(self, custom_dir: Optional[str] = None) -> Optional[str]:
        """Get the installation directory for MO2"""
        try:
            if custom_dir:
                # Use custom directory if provided
                install_dir = custom_dir
                self.logger.info(f"Using custom installation directory: {install_dir}")
            else:
                # Create a default installation directory
                home_dir = os.path.expanduser("~")
                install_dir = os.path.join(home_dir, "Games", "ModOrganizer2")
                self.logger.info(f"Using default installation directory: {install_dir}")
            
            # Create directory if it doesn't exist
            os.makedirs(install_dir, exist_ok=True)
            
            return install_dir
            
        except Exception as e:
            self.logger.error(f"Failed to get install directory: {e}")
            return None
    
    def _calculate_sha256(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _load_mo2_cache_metadata(self, cache_dir: str) -> Dict[str, Any]:
        """Load MO2 cache metadata"""
        metadata_file = os.path.join(cache_dir, "mo2_cache_metadata.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load MO2 cache metadata: {e}")
        return {"files": {}}

    def _save_mo2_cache_metadata(self, cache_dir: str, metadata: Dict[str, Any]):
        """Save MO2 cache metadata"""
        metadata_file = os.path.join(cache_dir, "mo2_cache_metadata.json")
        try:
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save MO2 cache metadata: {e}")

    def _download_file(self, url: str, filename: str, progress_callback=None) -> Optional[str]:
        """Download a file with progress tracking, caching, and hash verification"""
        try:
            # Create cache directory
            cache_dir = os.path.join(os.path.expanduser("~"), "NaK", "cache")
            os.makedirs(cache_dir, exist_ok=True)

            # Create cached file path
            cached_file = os.path.join(cache_dir, filename)

            # Load cache metadata
            metadata = self._load_mo2_cache_metadata(cache_dir)

            # Check if file is already cached and verify integrity
            if os.path.exists(cached_file):
                self.logger.info(f"Found cached file: {cached_file}")

                # Verify file integrity if we have hash metadata
                if filename in metadata["files"] and metadata["files"][filename].get("sha256"):
                    expected_hash = metadata["files"][filename]["sha256"]
                    actual_hash = self._calculate_sha256(cached_file)

                    if actual_hash == expected_hash:
                        self.logger.info(f"Cache integrity verified (SHA256: {actual_hash[:16]}...)")
                        if self.log_callback:
                            self.log_callback(f"Using cached MO2 archive: {filename}")
                        return cached_file
                    else:
                        self.logger.warning(f"Cached file corrupted! Expected: {expected_hash[:16]}..., Got: {actual_hash[:16]}...")
                        self.logger.warning("Re-downloading file...")
                        os.remove(cached_file)
                else:
                    # No hash metadata, trust the cached file but calculate hash
                    self.logger.info(f"No hash metadata found, calculating...")
                    actual_hash = self._calculate_sha256(cached_file)
                    metadata["files"][filename] = {"sha256": actual_hash, "url": url}
                    self._save_mo2_cache_metadata(cache_dir, metadata)
                    if self.log_callback:
                        self.log_callback(f"Using cached MO2 archive: {filename}")
                    return cached_file
            
            self.logger.info(f"Downloading {filename} from {url}")
            if self.log_callback:
                self.log_callback(f"Downloading MO2 archive: {filename}")
            
            # Download with progress tracking
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(cached_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress
                        if progress_callback and total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            progress_callback(percent, downloaded, total_size)
            
            self.logger.info(f"Download completed and cached: {cached_file}")
            if self.log_callback:
                self.log_callback(f"MO2 archive downloaded and cached: {filename}")

            # Calculate and store hash for integrity verification
            self.logger.info("Calculating SHA256 hash for integrity verification...")
            actual_hash = self._calculate_sha256(cached_file)
            metadata["files"][filename] = {
                "sha256": actual_hash,
                "url": url,
                "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_mo2_cache_metadata(cache_dir, metadata)
            self.logger.info(f"File integrity hash saved (SHA256: {actual_hash[:16]}...)")

            return cached_file

        except Exception as e:
            self.logger.error(f"Failed to download file: {e}")
            # Clean up partial download
            if os.path.exists(cached_file):
                try:
                    os.remove(cached_file)
                except:
                    pass
            return None
    
    def _extract_archive(self, archive_path: str, extract_dir: str) -> Optional[str]:
        """Extract MO2 archive to installation directory"""
        try:
            self.logger.info(f"Extracting {archive_path} to {extract_dir}")
            
            # Determine extraction method based on file extension
            if archive_path.endswith('.7z'):
                return self._extract_7z(archive_path, extract_dir)
            elif archive_path.endswith('.zip'):
                return self._extract_zip(archive_path, extract_dir)
            else:
                self.logger.error(f"Unsupported archive format: {archive_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to extract archive: {e}")
            return None
    
    def _extract_7z(self, archive_path: str, extract_dir: str) -> Optional[str]:
        """Extract 7z archive"""
        try:
            import subprocess
            
            # Try to use 7z command
            cmd = ["7z", "x", archive_path, f"-o{extract_dir}", "-y"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Find the extracted directory
                for item in os.listdir(extract_dir):
                    item_path = os.path.join(extract_dir, item)
                    if os.path.isdir(item_path) and "modorganizer" in item.lower():
                        self.logger.info(f"Extracted to: {item_path}")
                        return item_path
                
                # Fallback: return the extract directory itself
                return extract_dir
            else:
                self.logger.error(f"7z extraction failed: {result.stderr}")
                return None
                
        except FileNotFoundError:
            self.logger.error("7z command not found")
            return None
        except Exception as e:
            self.logger.error(f"7z extraction error: {e}")
            return None
    
    def _extract_zip(self, archive_path: str, extract_dir: str) -> Optional[str]:
        """Extract zip archive"""
        try:
            import zipfile
            
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find the extracted directory
            for item in os.listdir(extract_dir):
                item_path = os.path.join(extract_dir, item)
                if os.path.isdir(item_path) and "modorganizer" in item.lower():
                    self.logger.info(f"Extracted to: {item_path}")
                    return item_path
            
            # Fallback: return the extract directory itself
            return extract_dir
            
        except Exception as e:
            self.logger.error(f"Zip extraction error: {e}")
            return None
    
    def _verify_installation(self, install_dir: str) -> Dict[str, Any]:
        """Verify that MO2 was installed correctly"""
        try:
            self.logger.info(f"Verifying MO2 installation in {install_dir}")
            
            # Check if directory exists
            if not os.path.exists(install_dir):
                return {
                    "success": False,
                    "error": f"Installation directory does not exist: {install_dir}"
                }
            
            # Check for ModOrganizer.exe
            mo2_exe = self._find_mo2_executable(install_dir)
            if not mo2_exe:
                return {
                    "success": False,
                    "error": "ModOrganizer.exe not found in installation"
                }
            
            self.logger.info("MO2 installation verification successful")
            return {"success": True}
            
        except Exception as e:
            self.logger.error(f"Installation verification failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _find_mo2_executable(self, install_dir: str) -> Optional[str]:
        """Find ModOrganizer.exe in the installation directory"""
        try:
            self.logger.info(f"Searching for ModOrganizer.exe in {install_dir}")

            # Look for ModOrganizer.exe
            for root, dirs, files in os.walk(install_dir):
                for file in files:
                    if file.lower() == "modorganizer.exe":
                        exe_path = os.path.join(root, file)
                        self.logger.info(f"Found ModOrganizer.exe: {exe_path}")
                        return exe_path

            self.logger.error("ModOrganizer.exe not found")
            return None

        except Exception as e:
            self.logger.error(f"Failed to find ModOrganizer.exe: {e}")
            return None

    def _get_installed_mo2_version(self, mo2_dir: str) -> Optional[str]:
        """Get the installed MO2 version from ModOrganizer.ini"""
        try:
            # Look for ModOrganizer.ini in the MO2 directory
            ini_path = os.path.join(mo2_dir, "ModOrganizer.ini")

            if not os.path.exists(ini_path):
                self.logger.debug(f"ModOrganizer.ini not found at {ini_path}")
                return None

            # Read the INI file
            import configparser
            config = configparser.ConfigParser()
            config.read(ini_path)

            # Try to get version from [General] section
            if "General" in config and "version" in config["General"]:
                version = config["General"]["version"]
                self.logger.info(f"Found MO2 version in INI: {version}")
                return version

            self.logger.debug("Version field not found in ModOrganizer.ini")
            return None

        except Exception as e:
            self.logger.debug(f"Failed to read MO2 version from INI: {e}")
            return None

    def check_mo2_update_available(self, mo2_dir: str) -> Dict[str, Any]:
        """Check if an update is available for an existing MO2 installation"""
        try:
            # Get installed version
            installed_version = self._get_installed_mo2_version(mo2_dir)
            if not installed_version:
                return {
                    "success": False,
                    "error": "Could not determine installed MO2 version"
                }

            # Get latest version
            release = self._get_latest_release()
            if not release:
                return {
                    "success": False,
                    "error": "Could not fetch latest MO2 version"
                }

            latest_version = release.tag_name

            # Compare versions (simple string comparison)
            needs_update = installed_version != latest_version

            return {
                "success": True,
                "installed_version": installed_version,
                "latest_version": latest_version,
                "update_available": needs_update,
                "message": f"Installed: {installed_version}, Latest: {latest_version}"
            }

        except Exception as e:
            self.logger.error(f"Failed to check for MO2 updates: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def configure_nxm_handler(self, app_id: str, mo2_folder_path: str) -> Dict[str, Any]:
        """Configure NXM handler for a specific game (supports both Steam and Heroic)

        Args:
            app_id: App ID of the game (Steam AppID or Heroic/MO2 identifier)
            mo2_folder_path: Path to the MO2 folder (will auto-detect nxmhandler.exe inside)
        """
        try:
            self.logger.info(f"Configuring NXM handler for AppID {app_id} with MO2 folder: {mo2_folder_path}")

            # Verify the MO2 folder exists
            if not os.path.exists(mo2_folder_path):
                return {"success": False, "error": f"MO2 folder does not exist: {mo2_folder_path}"}

            # Auto-detect nxmhandler.exe in the MO2 folder
            nxm_handler_exe = os.path.join(mo2_folder_path, "nxmhandler.exe")
            if not os.path.exists(nxm_handler_exe):
                return {"success": False, "error": f"nxmhandler.exe not found in {mo2_folder_path}"}

            self.logger.info(f"Found nxmhandler.exe at: {nxm_handler_exe}")

            # Get Steam root directory (needed for Proton path even if not a Steam game)
            steam_root = self.steam_utils.get_steam_root()
            if not steam_root:
                return {"success": False, "error": "Steam root not found (required for Proton)"}

            # Check if this is a Heroic/non-Steam game (app_id starts with "mo2_" or is not numeric)
            is_heroic = not app_id.isdigit() or app_id.startswith("mo2_")

            if is_heroic:
                self.logger.info(f"Detected Heroic/non-Steam game from app_id: {app_id}")
                # For Heroic games, we don't check Steam compatdata - the script will handle prefix detection
            else:
                # For Steam games, verify compatdata exists
                compatdata_path = os.path.join(steam_root, "steamapps", "compatdata", app_id, "pfx")
                if not os.path.exists(compatdata_path):
                    return {"success": False, "error": f"Compatdata not found for Steam AppID {app_id}"}
            
            # Find ModOrganizer.exe in the MO2 folder for the script
            mo2_exe = os.path.join(mo2_folder_path, "ModOrganizer.exe")
            if not os.path.exists(mo2_exe):
                # Try to find it recursively
                mo2_exe = self._find_mo2_executable(mo2_folder_path)
                if not mo2_exe:
                    self.logger.warning(f"ModOrganizer.exe not found, using folder path: {mo2_folder_path}")
                    mo2_exe = mo2_folder_path

            # Use the sophisticated NXM handler creation that handles Heroic prefixes
            script_path = self._create_nxm_handler_script(
                app_id=app_id,
                mo2_exe=mo2_exe,
                nxm_handler_path=nxm_handler_exe,
                steam_root=steam_root
            )

            if not script_path:
                return {"success": False, "error": "Failed to create NXM handler script"}
            
            # Create desktop entry
            desktop_entry_path = os.path.join(os.path.expanduser("~"), ".local", "share", "applications", f"mo2-nxm-handler-{app_id}.desktop")
            
            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=MO2 NXM Handler ({app_id})
Comment=Mod Organizer 2 NXM Handler for Game {app_id}
Exec={script_path} %u
Icon=applications-games
NoDisplay=true
MimeType=x-scheme-handler/nxm;
"""
            
            with open(desktop_entry_path, 'w') as f:
                f.write(desktop_content)
            
            # Make it executable
            os.chmod(desktop_entry_path, 0o755)
            os.chmod(script_path, 0o755)
            
            # Update desktop database
            subprocess.run(["update-desktop-database", os.path.join(os.path.expanduser("~"), ".local", "share", "applications")],
                          capture_output=True, timeout=30)
            
            # Set as default handler
            result = subprocess.run([f"xdg-mime default mo2-nxm-handler-{app_id}.desktop x-scheme-handler/nxm"], 
                                  shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": f"NXM handler configured successfully for AppID {app_id}",
                    "script_path": script_path,
                    "desktop_entry_path": desktop_entry_path,
                    "nxm_handler_exe": nxm_handler_exe,
                    "mo2_folder": mo2_folder_path
                }
            else:
                return {"success": False, "error": f"Failed to set NXM handler: {result.stderr}"}
                
        except Exception as e:
            self.logger.error(f"Failed to configure NXM handler: {e}")
            return {"success": False, "error": str(e)}
    
    def _detect_custom_mount_paths(self, steam_root: str, mo2_folder_path: str) -> list:
        """Detect non-standard root directories and additional Steam libraries to mount
        
        Args:
            steam_root: Path to Steam installation
            mo2_folder_path: Path to MO2 folder
            
        Returns:
            List of directory paths to mount
        """
        try:
            mount_paths = set()
            
            # Standard Linux directories that should NOT be mounted
            standard_dirs = {
                'bin', 'boot', 'dev', 'etc', 'home', 'lib', 'lib64', 
                'mnt', 'opt', 'proc', 'root', 'run', 'sbin', 'srv', 
                'sys', 'tmp', 'usr', 'var'
            }
            
            # 1. Detect non-standard directories in root /
            try:
                root_entries = os.listdir('/')
                for entry in root_entries:
                    if entry not in standard_dirs:
                        entry_path = os.path.join('/', entry)
                        if os.path.isdir(entry_path):
                            mount_paths.add(entry_path)
                            self.logger.info(f"Found non-standard root directory: {entry_path}")
            except Exception as e:
                self.logger.warning(f"Failed to scan root directory: {e}")
            
            # 2. Always include the MO2 folder's top-level directory if it's not in home
            mo2_abs = os.path.abspath(mo2_folder_path)
            home_dir = os.path.expanduser("~")
            if not mo2_abs.startswith(home_dir):
                # Get the top-level directory (e.g., /test from /test/mo2/something)
                parts = mo2_abs.split('/')
                if len(parts) > 1 and parts[1]:  # parts[0] is empty, parts[1] is first dir
                    top_level = '/' + parts[1]
                    mount_paths.add(top_level)
                    self.logger.info(f"Including MO2 top-level directory: {top_level}")
            
            # 3. Detect additional Steam library folders from libraryfolders.vdf
            try:
                libraryfolders_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
                if os.path.exists(libraryfolders_path):
                    import vdf
                    with open(libraryfolders_path, 'r') as f:
                        library_data = vdf.load(f)
                    
                    # Parse library folders
                    if 'libraryfolders' in library_data:
                        for key, value in library_data['libraryfolders'].items():
                            if isinstance(value, dict) and 'path' in value:
                                library_path = value['path']
                                if library_path and library_path != steam_root:
                                    # Get the top-level directory of the library
                                    parts = library_path.split('/')
                                    if len(parts) > 1 and parts[1]:
                                        top_level = '/' + parts[1]
                                        mount_paths.add(top_level)
                                        self.logger.info(f"Found Steam library folder: {library_path} (mounting {top_level})")
            except Exception as e:
                self.logger.warning(f"Failed to parse Steam library folders: {e}")
            
            return sorted(list(mount_paths))
            
        except Exception as e:
            self.logger.error(f"Failed to detect custom mount paths: {e}")
            return []
    
    def remove_nxm_handlers(self) -> Dict[str, Any]:
        """Remove all NXM handlers configured by this tool"""
        try:
            self.logger.info("Removing NXM handler configuration...")
            
            home_dir = os.path.expanduser("~")
            applications_dir = os.path.join(home_dir, ".local", "share", "applications")
            
            # Find all mo2-nxm-handler files
            import glob
            nxm_scripts = glob.glob(os.path.join(applications_dir, "mo2-nxm-handler-*.sh"))
            nxm_desktops = glob.glob(os.path.join(applications_dir, "mo2-nxm-handler-*.desktop"))
            
            removed_count = 0
            
            # Remove script files
            for script in nxm_scripts:
                try:
                    os.remove(script)
                    self.logger.info(f"Removed NXM handler script: {script}")
                    removed_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to remove script {script}: {e}")
            
            # Remove desktop files
            for desktop in nxm_desktops:
                try:
                    os.remove(desktop)
                    self.logger.info(f"Removed NXM handler desktop file: {desktop}")
                    removed_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to remove desktop file {desktop}: {e}")
            
            # Update desktop database
            subprocess.run(["update-desktop-database", applications_dir], 
                          capture_output=True, check=False, timeout=30)
            
            # Unset the NXM handler
            subprocess.run(["xdg-mime", "default", ""], 
                          capture_output=True, check=False, timeout=30)
            
            if removed_count > 0:
                message = f"Removed {removed_count} NXM handler file(s) successfully!"
                self.logger.info(message)
                return {"success": True, "message": message}
            else:
                message = "No NXM handler files found to remove."
                self.logger.info(message)
                return {"success": True, "message": message}
                
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while removing NXM handler: {e}")
            return {"success": False, "error": str(e)}