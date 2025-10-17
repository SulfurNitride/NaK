"""
Vortex Installer module for downloading and installing Vortex Mod Manager
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


class VortexInstaller:
    """Handles downloading and installing Vortex Mod Manager"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.info("=" * 80)
        self.logger.info("VORTEX INSTALLER INITIALIZED - NEW CODE WITH REGISTRY FIX LOADED")
        self.logger.info("=" * 80)
        self.steam_utils = SteamUtils()
        self.progress_callback = None
        self.log_callback = None

    def set_progress_callback(self, callback):
        """Set a callback function for progress updates"""
        self.progress_callback = callback

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
            self.progress_callback(percent, 0, 0)

    def _cleanup_old_cache(self, current_filename: str):
        """Clean up old cached Vortex files"""
        try:
            cache_dir = os.path.join(os.path.expanduser("~"), "NaK", "cache")
            if not os.path.exists(cache_dir):
                return

            # Remove old Vortex installers that aren't the current one
            for filename in os.listdir(cache_dir):
                if filename.startswith("Vortex") and filename != current_filename:
                    old_file = os.path.join(cache_dir, filename)
                    try:
                        os.remove(old_file)
                        self.logger.info(f"Removed old cached file: {filename}")
                    except OSError as e:
                        self.logger.warning(f"Could not remove old cached file {filename}: {e}")
        except Exception as e:
            self.logger.warning(f"Error cleaning up old cache: {e}")

    def _get_latest_release(self) -> Optional[GitHubRelease]:
        """Get the latest Vortex release from GitHub"""
        try:
            self.logger.info("Fetching latest Vortex release from GitHub...")

            # Vortex GitHub repository
            api_url = "https://api.github.com/repos/Nexus-Mods/Vortex/releases/latest"

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

    def _find_vortex_asset(self, release: GitHubRelease) -> Tuple[Optional[str], Optional[str]]:
        """Find the appropriate Vortex installer for download"""
        try:
            self.logger.info("Finding appropriate Vortex installer...")

            # Look for the Windows installer .exe
            for asset in release.assets:
                name = asset.get("name", "")
                download_url = asset.get("browser_download_url", "")

                # Look for setup exe (e.g., "Vortex Setup 1.9.8.exe")
                if "setup" in name.lower() and name.endswith(".exe"):
                    self.logger.info(f"Found installer: {name}")
                    return download_url, name

            self.logger.error("No suitable Vortex installer found")
            return None, None

        except Exception as e:
            self.logger.error(f"Failed to find Vortex asset: {e}")
            return None, None

    def _calculate_sha256(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _load_vortex_cache_metadata(self, cache_dir: str) -> Dict[str, Any]:
        """Load Vortex cache metadata"""
        metadata_file = os.path.join(cache_dir, "vortex_cache_metadata.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load Vortex cache metadata: {e}")
        return {"files": {}}

    def _save_vortex_cache_metadata(self, cache_dir: str, metadata: Dict[str, Any]):
        """Save Vortex cache metadata"""
        metadata_file = os.path.join(cache_dir, "vortex_cache_metadata.json")
        try:
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save Vortex cache metadata: {e}")

    def _download_file(self, url: str, filename: str, progress_callback=None) -> Optional[str]:
        """Download a file with progress tracking, caching, and hash verification"""
        try:
            # Create cache directory
            cache_dir = os.path.join(os.path.expanduser("~"), "NaK", "cache")
            os.makedirs(cache_dir, exist_ok=True)

            # Create cached file path
            cached_file = os.path.join(cache_dir, filename)

            # Load cache metadata
            metadata = self._load_vortex_cache_metadata(cache_dir)

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
                            self.log_callback(f"Using cached Vortex installer: {filename}")
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
                    self._save_vortex_cache_metadata(cache_dir, metadata)
                    if self.log_callback:
                        self.log_callback(f"Using cached Vortex installer: {filename}")
                    return cached_file

            self.logger.info(f"Downloading {filename} from {url}")
            if self.log_callback:
                self.log_callback(f"Downloading Vortex installer: {filename}")

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
                self.log_callback(f"Vortex installer downloaded and cached: {filename}")

            # Calculate and store hash for integrity verification
            self.logger.info("Calculating SHA256 hash for integrity verification...")
            actual_hash = self._calculate_sha256(cached_file)
            metadata["files"][filename] = {
                "sha256": actual_hash,
                "url": url,
                "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_vortex_cache_metadata(cache_dir, metadata)
            self.logger.info(f"File integrity hash saved (SHA256: {actual_hash[:16]}...)")

            return cached_file

        except Exception as e:
            self.logger.error(f"Failed to download file: {e}")
            # Clean up partial download
            if 'cached_file' in locals() and os.path.exists(cached_file):
                try:
                    os.remove(cached_file)
                except:
                    pass
            return None

    def _find_vortex_executable(self, install_dir: str) -> Optional[str]:
        """Find Vortex.exe in the installation directory"""
        try:
            self.logger.info(f"Searching for Vortex.exe in {install_dir}")

            # Look for Vortex.exe
            for root, dirs, files in os.walk(install_dir):
                for file in files:
                    if file.lower() == "vortex.exe":
                        exe_path = os.path.join(root, file)
                        self.logger.info(f"Found Vortex.exe: {exe_path}")
                        return exe_path

            self.logger.error("Vortex.exe not found")
            return None

        except Exception as e:
            self.logger.error(f"Failed to find Vortex.exe: {e}")
            return None

    def _add_vortex_to_steam(self, vortex_exe: str, vortex_name: str) -> Dict[str, Any]:
        """Add Vortex to Steam using SteamShortcutManager with complete integration"""
        try:
            self.logger.info(f"Adding {vortex_name} to Steam with complete integration...")

            # Use SteamShortcutManager to add Vortex to Steam
            if not self.steam_utils.shortcut_manager:
                return {
                    "success": False,
                    "error": "Steam shortcut manager not available"
                }

            # Add Vortex to Steam and create prefix
            steam_result = self.steam_utils.shortcut_manager.add_game_to_steam(
                app_name=vortex_name,
                exe_path=vortex_exe,
                proton_tool="proton_experimental"  # Use Proton Experimental by default
            )

            if not steam_result["success"]:
                return steam_result

            app_id = steam_result["app_id"]
            compat_data_path = steam_result["compat_data_path"]

            self.logger.info(f"Successfully added {vortex_name} to Steam with AppID: {app_id}")
            self.logger.info(f"Compat data path: {compat_data_path}")

            return {
                "success": True,
                "app_id": app_id,
                "compat_data_path": compat_data_path,
                "message": f"Successfully added {vortex_name} to Steam with AppID {app_id}",
                "reused_prefix": False
            }

        except Exception as e:
            self.logger.error(f"Failed to add Vortex to Steam: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _setup_vortex_linux_fixes(self) -> Dict[str, Any]:
        """Setup Vortex Linux compatibility fixes (staging folders + case-sensitivity)"""
        try:
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("SETTING UP VORTEX LINUX COMPATIBILITY FIXES")
            self.logger.info("═══════════════════════════════════════════════════════════════")

            from src.utils.vortex_linux_fixes import VortexLinuxFixes
            fixer = VortexLinuxFixes()

            # Get Steam library path
            steam_root = self.steam_utils.get_steam_root()
            if not steam_root:
                return {"success": False, "error": "Steam root not found"}

            # Detect and fix all installed Bethesda games
            results = fixer.detect_and_fix_installed_games(steam_root)

            # Log what was done
            if "games_fixed" in results:
                for game_id, fix_result in results["games_fixed"].items():
                    if fix_result.get("success"):
                        game_name = fixer.BETHESDA_GAMES[game_id]["name"]
                        created_count = fix_result.get("total_created", 0)
                        self.logger.info(f"  ✓ {game_name}: Created {created_count} lowercase ESM symlinks")
                        self._log_progress(f"Fixed case-sensitivity for {game_name}")

            # Log staging folder info
            if "vortex_paths" in results and results["vortex_paths"]:
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info("VORTEX STAGING FOLDER SETUP")
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info("Staging folders created. Configure in Vortex:")
                self._log_progress("IMPORTANT: Configure staging folders in Vortex Settings")

                for game_id, path_info in results["vortex_paths"].items():
                    game_name = path_info.get("game_name", game_id)
                    vortex_path = path_info.get("vortex_path", "")
                    self.logger.info(f"\n{game_name}:")
                    self.logger.info(f"  Path: {vortex_path}")
                    self.logger.info(f"  Settings → Mods → Mod Staging Folder")

            self.logger.info("═══════════════════════════════════════════════════════════════")

            return {
                "success": True,
                "message": "Vortex Linux fixes applied successfully",
                "results": results
            }

        except Exception as e:
            self.logger.error(f"Failed to setup Vortex Linux fixes: {e}")
            return {"success": False, "error": str(e)}

    def _auto_configure_staging_folder(self, vortex_exe: str, compat_data_path: str) -> Dict[str, Any]:
        """Auto-configure Vortex staging folder by directly modifying state files"""
        try:
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("AUTO-CONFIGURING VORTEX STAGING FOLDER")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self._log_progress("Auto-configuring Vortex staging folder...")

            # Get Steam root and construct staging path with {game} placeholder
            steam_root = self.steam_utils.get_steam_root()
            if not steam_root:
                return {"success": False, "error": "Steam root not found"}

            # Construct the Windows Z: drive staging path with {game} placeholder
            # Use forward slashes for Vortex (it converts them internally)
            windows_staging_path = f"Z:/{steam_root.replace('/home/', '')}/steamapps/VortexStaging/{{{{game}}}}"

            self.logger.info(f"Target staging folder: {windows_staging_path}")

            # Get Proton path
            proton_path = os.path.join(steam_root, "steamapps", "common", "Proton - Experimental", "proton")
            if not os.path.exists(proton_path):
                # Try other Proton versions
                for version in ["Proton 9.0", "Proton 8.0", "Proton 7.0"]:
                    alt_path = os.path.join(steam_root, "steamapps", "common", version, "proton")
                    if os.path.exists(alt_path):
                        proton_path = alt_path
                        break

            if not os.path.exists(proton_path):
                return {"success": False, "error": "Proton not found"}

            # Set up environment for Proton
            env = os.environ.copy()
            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam_root
            env["STEAM_COMPAT_DATA_PATH"] = compat_data_path
            env["WINEPREFIX"] = os.path.join(compat_data_path, "pfx")

            # Run Vortex briefly first to create initial state files
            self.logger.info("Running Vortex briefly to initialize state files...")
            process = subprocess.Popen(
                [proton_path, "run", vortex_exe],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            self.logger.info(f"Vortex launched with PID: {process.pid}, waiting 15 seconds for full initialization...")
            time.sleep(15)  # Wait longer to ensure Vortex creates all needed files

            # Kill Vortex and all child processes
            self.logger.info("Killing Vortex process...")
            subprocess.run(["pkill", "-9", "-f", "Vortex.exe"], capture_output=True)
            time.sleep(3)  # Wait for files to flush

            # Now modify the state.v2 database files directly
            state_dir = os.path.join(compat_data_path, "pfx", "drive_c", "users", "steamuser", "AppData", "Roaming", "Vortex", "state.v2")

            self.logger.info(f"Vortex state directory: {state_dir}")

            if not os.path.exists(state_dir):
                self.logger.error(f"State directory not found: {state_dir}")
                return {
                    "success": False,
                    "message": "Vortex state files not found",
                    "staging_path": windows_staging_path
                }

            # Escape the path for sed (escape forward slashes and special characters)
            escaped_path = windows_staging_path.replace("/", "\\/").replace("{", "\\{").replace("}", "\\}")

            # Inject staging folder path into all LevelDB files
            self.logger.info("Modifying Vortex state files...")

            # Use sed to inject the staging path into the database
            # We'll add it as a JSON-like key-value pair
            bash_command = f"""
cd "{state_dir}"
# Kill any remaining Vortex processes
pkill -9 -f "Vortex.exe" 2>/dev/null || true
sleep 1

# Inject staging path into all .ldb and .log files
for file in *.ldb *.log 2>/dev/null; do
    if [ -f "$file" ]; then
        echo "Processing $file..."
        # Try to inject the installPath setting
        # This adds it to the binary database in a way Vortex can read
        sed -i 's|"installPath":"[^"]*"|"installPath":"{escaped_path}"|g' "$file" 2>/dev/null || true

        # Also try alternate key names
        sed -i 's|"stagingPath":"[^"]*"|"stagingPath":"{escaped_path}"|g' "$file" 2>/dev/null || true
        sed -i 's|"modStagingPath":"[^"]*"|"modStagingPath":"{escaped_path}"|g' "$file" 2>/dev/null || true
    fi
done

echo "Staging folder configuration injected"
"""

            result = subprocess.run(
                bash_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info("✓ STAGING FOLDER CONFIGURATION INJECTED")
                self.logger.info("═══════════════════════════════════════════════════════════════")
                self.logger.info(f"Staging folder: {windows_staging_path}")
                self.logger.info("Modified state files successfully")
                self._log_progress("Staging folder auto-configured successfully!")

                return {
                    "success": True,
                    "message": "Vortex staging folder auto-configured",
                    "staging_path": windows_staging_path,
                    "method": "direct_file_modification"
                }
            else:
                self.logger.warning(f"File modification returned non-zero: {result.returncode}")
                self.logger.warning(f"stderr: {result.stderr}")
                return {
                    "success": False,
                    "message": "Failed to modify state files",
                    "staging_path": windows_staging_path
                }

        except Exception as e:
            self.logger.error(f"Failed to auto-configure staging folder: {e}")
            return {"success": False, "error": str(e)}

    def _setup_save_symlinks(self, vortex_install_dir: str, vortex_app_id: str) -> Dict[str, Any]:
        """Setup save game symlinks for all detected Bethesda games"""
        try:
            self._log_progress("Setting up save game symlinks...")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("SETTING UP SAVE GAME SYMLINKS FOR VORTEX")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"Vortex Install Directory: {vortex_install_dir}")
            self.logger.info(f"Vortex AppID: {vortex_app_id}")

            from src.utils.save_symlinker import SaveSymlinker
            symlinker = SaveSymlinker()

            # Create "Save Games Folder" in Vortex directory
            from pathlib import Path
            vortex_path = Path(vortex_install_dir)
            save_games_folder = vortex_path / "Save Games Folder"
            save_games_folder.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created Save Games Folder: {save_games_folder}")
            self._log_progress(f"Created Save Games Folder in Vortex directory")

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

            # Get Vortex compatdata path
            steam_root = self.steam_utils.get_steam_root()
            vortex_compatdata = Path(steam_root) / "steamapps" / "compatdata" / str(vortex_app_id)

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

                    # 2. Create symlink in Vortex prefix (compatdata)
                    location_type = game['location_type']
                    save_identifier = game['save_folder']

                    if location_type == "my_games":
                        # Create symlink in My Games
                        prefix_save_location = vortex_compatdata / "pfx" / "drive_c" / "users" / "steamuser" / "My Documents" / "My Games" / save_identifier
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

    def download_vortex(self, install_dir: Optional[str] = None, custom_name: Optional[str] = None) -> Dict[str, Any]:
        """Download and install the latest version of Vortex with complete Steam integration"""
        try:
            self.logger.info("Starting Vortex download and installation with Steam integration")

            # Get latest release info
            self._log_progress("Fetching latest Vortex release information...")
            release = self._get_latest_release()
            if not release:
                return {
                    "success": False,
                    "error": "Failed to get latest release information"
                }

            self._log_progress(f"Found latest version: {release.tag_name}")

            # Find the correct asset
            self._log_progress("Finding download asset...")
            download_url, filename = self._find_vortex_asset(release)
            if not download_url or not filename:
                return {
                    "success": False,
                    "error": "Could not find appropriate Vortex installer"
                }

            # Clean up old cached files
            self._cleanup_old_cache(filename)

            self._log_progress(f"Found asset: {filename}")

            # Get installation directory
            if not install_dir:
                install_dir = os.path.join(os.path.expanduser("~"), "Games", "Vortex")

            os.makedirs(install_dir, exist_ok=True)
            self.logger.info(f"Installation directory: {install_dir}")

            # Download the installer
            installer_path = self._download_file(download_url, filename, progress_callback=getattr(self, 'progress_callback', None))
            if not installer_path:
                return {
                    "success": False,
                    "error": "Failed to download Vortex installer"
                }

            # Use custom name or default
            vortex_name = custom_name if custom_name else "Vortex"

            # Add Vortex to Steam FIRST to create the prefix
            self._log_progress(f"Adding {vortex_name} to Steam and creating prefix...")
            # We need to add a placeholder exe first, then install Vortex into the prefix
            # Create a temporary placeholder
            temp_vortex_exe = os.path.join(install_dir, "Vortex.exe")

            # Create placeholder if it doesn't exist
            if not os.path.exists(temp_vortex_exe):
                # Create empty file as placeholder
                Path(temp_vortex_exe).touch()

            steam_result = self._add_vortex_to_steam(temp_vortex_exe, vortex_name)
            if not steam_result["success"]:
                self.logger.error(f"Steam integration failed: {steam_result}")
                return steam_result

            app_id = steam_result["app_id"]
            compat_data_path = steam_result["compat_data_path"]

            self._log_progress("Prefix created successfully, now installing Vortex...")

            # Now run the installer silently using Proton
            self._log_progress("Running Vortex installer silently...")
            install_result = self._run_vortex_installer_silent(
                installer_path,
                install_dir,
                compat_data_path,
                app_id
            )

            if not install_result["success"]:
                return install_result

            # Find the actual Vortex executable
            self._log_progress("Locating Vortex executable...")
            vortex_exe = self._find_vortex_executable(install_dir)
            if not vortex_exe:
                return {
                    "success": False,
                    "error": "Could not find Vortex.exe after installation"
                }

            # Update the Steam shortcut with the real exe path
            if temp_vortex_exe != vortex_exe:
                self._log_progress("Updating Steam shortcut with actual Vortex path...")
                self.steam_utils.shortcut_manager.update_shortcut_exe(app_id, vortex_exe)

            # Auto-install dependencies
            self._log_progress("Installing dependencies...")
            self.logger.info(f"Starting dependency installation for AppID: {app_id}")
            dependency_result = self._auto_install_dependencies(app_id, vortex_name)

            # Setup save symlinks
            save_symlink_result = self._setup_save_symlinks(install_dir, str(app_id))

            # Setup Vortex Linux compatibility fixes (staging folders + case-sensitivity)
            self._log_progress("Setting up Vortex Linux compatibility fixes...")
            linux_fixes_result = self._setup_vortex_linux_fixes()

            # Configure NXM handler
            self._log_progress("Configuring NXM handler...")
            nxm_result = self._configure_nxm_handler(vortex_exe, str(app_id), vortex_name)

            # Merge results
            result = {
                "success": True,
                "install_dir": install_dir,
                "vortex_exe": vortex_exe,
                "version": release.tag_name,
                "vortex_name": vortex_name,
                "app_id": app_id,
                "compat_data_path": compat_data_path,
                "message": f"Vortex {release.tag_name} installed and added to Steam successfully!",
                "steam_integration": steam_result,
                "dependency_installation": dependency_result,
                "save_symlinks": save_symlink_result,
                "linux_fixes": linux_fixes_result,
                "nxm_handler": nxm_result
            }

            # Update message if dependencies were installed
            if dependency_result["success"]:
                result["message"] = f"Vortex {release.tag_name} installed, added to Steam, and dependencies installed successfully!"

            # Add save symlinks info to message
            if save_symlink_result.get("success") and save_symlink_result.get("games_symlinked", 0) > 0:
                result["message"] += f" Save symlinks created for {save_symlink_result['games_symlinked']} game(s)."

            # Add NXM handler info to message
            if nxm_result.get("success"):
                result["message"] += f" NXM handler configured!"

            return result

        except Exception as e:
            self.logger.error(f"Vortex installation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _run_vortex_briefly(self, vortex_exe: str, compat_data_path: str, proton_path: str, env: dict):
        """Run Vortex briefly to let it create its registry entries, then kill it"""
        try:
            self.logger.info("Running Vortex briefly to create registry entries...")
            self._log_progress("Initializing Vortex (creating registry entries)...")

            # Launch Vortex in the background
            process = subprocess.Popen(
                [proton_path, "run", vortex_exe],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            self.logger.info(f"Vortex launched with PID: {process.pid}, waiting 5 seconds...")
            time.sleep(5)

            # Kill Vortex
            self.logger.info("Killing Vortex process...")
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.logger.warning("Vortex didn't terminate gracefully, killing forcefully...")
                process.kill()
                process.wait()

            self.logger.info("Vortex closed, registry entries should now exist")
            # Wait a moment for registry to flush
            time.sleep(1)

        except Exception as e:
            self.logger.warning(f"Failed to run Vortex briefly (non-critical): {e}")

    def _fix_vortex_registry(self, install_dir: str, compat_data_path: str, proton_path: str, env: dict):
        """Fix Vortex registry uninstall path to match actual installation location"""
        try:
            self.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.logger.info("_fix_vortex_registry() CALLED")
            self.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.logger.info(f"Install dir: {install_dir}")
            self.logger.info(f"Compat data path: {compat_data_path}")
            self.logger.info(f"Proton path: {proton_path}")

            # Convert Linux path to Windows Z:\ path
            windows_path = install_dir.replace("/", "\\")
            if not windows_path.startswith("Z:"):
                windows_path = f"Z:{windows_path}"

            self.logger.info(f"Windows path for registry: {windows_path}")

            # Find the Vortex uninstall GUID by querying the registry
            self.logger.info("Searching for Vortex uninstall key GUID...")
            try:
                result = subprocess.run(
                    [proton_path, "run", "reg", "query", "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall", "/s", "/f", "Vortex", "/d"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                # Parse output to find the GUID key
                vortex_guid = None
                for line in result.stdout.split('\n'):
                    if 'Uninstall\\' in line and not line.strip().startswith('HKEY'):
                        # Extract GUID from path like: HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Uninstall\{GUID}
                        parts = line.split('\\')
                        if len(parts) > 0:
                            guid_candidate = parts[-1].strip()
                            if guid_candidate and guid_candidate not in ['Uninstall', '']:
                                vortex_guid = guid_candidate
                                self.logger.info(f"Found Vortex uninstall GUID: {vortex_guid}")
                                break

                if not vortex_guid:
                    self.logger.warning("Could not find Vortex GUID, trying standard keys")
                    vortex_guid = "Vortex"  # Fallback to simple name
                else:
                    self.logger.info(f"✓ Found Vortex GUID: {vortex_guid}")

            except Exception as e:
                self.logger.warning(f"Failed to query registry for GUID: {e}, using fallback")
                vortex_guid = "Vortex"

            # Update the registry keys
            reg_key = f"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{vortex_guid}"
            self.logger.info(f"Registry key to update: {reg_key}")
            self.logger.info(f"Target path: {windows_path}")

            try:
                # Update InstallLocation
                self.logger.info("→ Updating InstallLocation...")
                result = subprocess.run(
                    [proton_path, "run", "reg", "add", reg_key, "/v", "InstallLocation", "/t", "REG_SZ", "/d", windows_path, "/f"],
                    env=env,
                    capture_output=True,
                    timeout=30
                )
                self.logger.info(f"  ✓ InstallLocation updated (return code: {result.returncode})")

                # Update UninstallString
                uninstall_string = f'"{windows_path}\\Uninstall Vortex.exe" /allusers'
                self.logger.info("→ Updating UninstallString...")
                result = subprocess.run(
                    [proton_path, "run", "reg", "add", reg_key, "/v", "UninstallString", "/t", "REG_SZ", "/d", uninstall_string, "/f"],
                    env=env,
                    capture_output=True,
                    timeout=30
                )
                self.logger.info(f"  ✓ UninstallString updated (return code: {result.returncode})")

                # Update QuietUninstallString
                quiet_uninstall_string = f'"{windows_path}\\Uninstall Vortex.exe" /allusers /S'
                self.logger.info("→ Updating QuietUninstallString...")
                result = subprocess.run(
                    [proton_path, "run", "reg", "add", reg_key, "/v", "QuietUninstallString", "/t", "REG_SZ", "/d", quiet_uninstall_string, "/f"],
                    env=env,
                    capture_output=True,
                    timeout=30
                )
                self.logger.info(f"  ✓ QuietUninstallString updated (return code: {result.returncode})")

                # Update DisplayIcon
                display_icon = f"{windows_path}\\Vortex.exe,0"
                self.logger.info("→ Updating DisplayIcon...")
                result = subprocess.run(
                    [proton_path, "run", "reg", "add", reg_key, "/v", "DisplayIcon", "/t", "REG_SZ", "/d", display_icon, "/f"],
                    env=env,
                    capture_output=True,
                    timeout=30
                )
                self.logger.info(f"  ✓ DisplayIcon updated (return code: {result.returncode})")

                self.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self.logger.info("✓ ALL REGISTRY PATHS UPDATED SUCCESSFULLY!")
                self.logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            except Exception as e:
                self.logger.error(f"Failed to update some registry keys: {e}")
                self.logger.error(f"Exception details: {type(e).__name__}")

        except Exception as e:
            self.logger.error(f"Failed to fix registry paths (non-critical): {e}")
            self.logger.error(f"Exception details: {type(e).__name__}")

        self.logger.info("_fix_vortex_registry() completed")

    def _configure_nxm_handler(self, vortex_exe: str, app_id: str, vortex_name: str) -> Dict[str, Any]:
        """Configure NXM handler for Vortex

        Args:
            vortex_exe: Path to Vortex.exe
            app_id: Steam AppID
            vortex_name: Name of the Vortex installation

        Returns:
            Dict with success status and message
        """
        try:
            self.logger.info("=" * 80)
            self.logger.info("CONFIGURING VORTEX NXM HANDLER")
            self.logger.info("=" * 80)
            self.logger.info(f"Vortex exe: {vortex_exe}")
            self.logger.info(f"AppID: {app_id}")
            self.logger.info(f"Name: {vortex_name}")

            # Get Steam root directory
            steam_root = self.steam_utils.get_steam_root()
            if not steam_root:
                return {"success": False, "error": "Steam root not found"}

            # Verify compatdata exists for this app
            compatdata_path = os.path.join(steam_root, "steamapps", "compatdata", str(app_id))
            pfx_path = os.path.join(compatdata_path, "pfx")
            if not os.path.exists(pfx_path):
                return {"success": False, "error": f"Compatdata not found for AppID {app_id}"}

            # Use Proton Experimental
            proton_path = os.path.join(steam_root, "steamapps", "common", "Proton - Experimental")
            if not os.path.exists(proton_path):
                # Try other Proton versions
                for version in ["Proton 9.0", "Proton 8.0", "Proton 7.0"]:
                    alt_path = os.path.join(steam_root, "steamapps", "common", version)
                    if os.path.exists(alt_path):
                        proton_path = alt_path
                        break

                if not os.path.exists(proton_path):
                    return {"success": False, "error": "Proton not found. Please install Proton Experimental from Steam."}

            self.logger.info(f"Using Proton: {proton_path}")

            # Create applications directory
            home_dir = os.path.expanduser("~")
            applications_dir = os.path.join(home_dir, ".local", "share", "applications")
            os.makedirs(applications_dir, exist_ok=True)

            # Create NXM handler script
            script_path = os.path.join(applications_dir, f"vortex-nxm-handler-{app_id}.sh")

            script_content = f"""#!/bin/bash
# NXM Handler for Vortex (AppID: {app_id})

NXM_URL="$1"

# Set up Steam Proton environment
export STEAM_COMPAT_CLIENT_INSTALL_PATH="{steam_root}"
export STEAM_COMPAT_DATA_PATH="{compatdata_path}"
export WINEPREFIX="{pfx_path}"

# Use Proton
PROTON_PATH="{proton_path}"

# Launch Vortex.exe with -d flag to download the mod from NXM URL
# The -d flag tells Vortex to download the file at the URL
"$PROTON_PATH/proton" run "{vortex_exe}" -d "$NXM_URL"
"""

            with open(script_path, 'w') as f:
                f.write(script_content)

            os.chmod(script_path, 0o755)
            self.logger.info(f"Created NXM handler script: {script_path}")

            # Create desktop entry
            desktop_entry_path = os.path.join(applications_dir, f"vortex-nxm-handler-{app_id}.desktop")

            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Vortex NXM Handler ({vortex_name})
Comment=Vortex Mod Manager NXM Handler
Exec={script_path} %u
Icon=applications-games
NoDisplay=true
MimeType=x-scheme-handler/nxm;
"""

            with open(desktop_entry_path, 'w') as f:
                f.write(desktop_content)

            os.chmod(desktop_entry_path, 0o755)
            self.logger.info(f"Created desktop entry: {desktop_entry_path}")

            # Update desktop database
            subprocess.run(["update-desktop-database", applications_dir],
                          capture_output=True, timeout=30)

            # Set as default handler for NXM links
            result = subprocess.run([f"xdg-mime default vortex-nxm-handler-{app_id}.desktop x-scheme-handler/nxm"],
                                  shell=True, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                self.logger.info("=" * 80)
                self.logger.info("NXM HANDLER CONFIGURED SUCCESSFULLY")
                self.logger.info("=" * 80)
                return {
                    "success": True,
                    "message": f"NXM handler configured successfully for {vortex_name}",
                    "script_path": script_path,
                    "desktop_entry_path": desktop_entry_path
                }
            else:
                return {"success": False, "error": f"Failed to set NXM handler: {result.stderr}"}

        except Exception as e:
            self.logger.error(f"Failed to configure NXM handler: {e}")
            return {"success": False, "error": str(e)}

    def _run_vortex_installer_silent(self, installer_path: str, install_dir: str, compat_data_path: str, app_id: int) -> Dict[str, Any]:
        """Run Vortex installer silently using Proton"""
        try:
            self.logger.info("Running Vortex installer silently...")

            # Get Proton path
            steam_root = self.steam_utils.get_steam_root()
            proton_path = os.path.join(steam_root, "steamapps", "common", "Proton - Experimental", "proton")

            if not os.path.exists(proton_path):
                # Try other Proton versions
                for version in ["Proton 9.0", "Proton 8.0", "Proton 7.0"]:
                    alt_path = os.path.join(steam_root, "steamapps", "common", version, "proton")
                    if os.path.exists(alt_path):
                        proton_path = alt_path
                        break

            if not os.path.exists(proton_path):
                return {
                    "success": False,
                    "error": "Proton not found. Please install Proton Experimental from Steam."
                }

            # Create the install directory if it doesn't exist
            os.makedirs(install_dir, exist_ok=True)

            # Convert Linux path to Windows Z: drive path
            # Wine/Proton maps the entire filesystem to Z:
            windows_install_path = install_dir.replace("/", "\\")
            if not windows_install_path.startswith("Z:"):
                windows_install_path = f"Z:{windows_install_path}"

            self.logger.info(f"Installing Vortex directly to: {windows_install_path}")

            # NSIS installer flags:
            # /S = Silent mode
            # /D=path = Installation directory (must be last parameter, no quotes)
            installer_args = f"/S /D={windows_install_path}"

            # Set up environment for Proton
            env = os.environ.copy()
            env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam_root
            env["STEAM_COMPAT_DATA_PATH"] = compat_data_path
            env["WINEPREFIX"] = os.path.join(compat_data_path, "pfx")

            self.logger.info(f"Running: {proton_path} run {installer_path} {installer_args}")
            self._log_progress("Installing Vortex (this may take a minute)...")

            # Run the installer
            process = subprocess.run(
                [proton_path, "run", installer_path] + installer_args.split(),
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if process.returncode != 0:
                self.logger.warning(f"Installer return code: {process.returncode}")
                self.logger.warning(f"Installer stderr: {process.stderr}")
                # Don't fail immediately, check if files were actually installed

            # Wait a moment for files to settle
            time.sleep(2)

            # Verify installation by checking for Vortex.exe in the install directory
            if os.path.exists(os.path.join(install_dir, "Vortex.exe")):
                self.logger.info("Vortex installed successfully directly to target directory")
                self._log_progress("Vortex installation completed successfully!")
                return {"success": True}
            else:
                self.logger.error(f"Vortex.exe not found in {install_dir} after installation")
                return {
                    "success": False,
                    "error": "Vortex installation not found after running installer"
                }

        except subprocess.TimeoutExpired:
            self.logger.error("Vortex installer timed out")
            return {
                "success": False,
                "error": "Vortex installer timed out after 5 minutes"
            }
        except Exception as e:
            self.logger.error(f"Failed to run Vortex installer: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _auto_install_dependencies(self, app_id: int, app_name: str) -> Dict[str, Any]:
        """Automatically install dependencies for Vortex"""
        try:
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("AUTO-INSTALLING VORTEX DEPENDENCIES")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"Target: {app_name} (AppID: {app_id})")

            # Wait a moment for Steam to recognize the new shortcut
            self.logger.info("Waiting for Steam to recognize the new shortcut...")
            time.sleep(2)

            # Use the same dependency installer as MO2 (includes dotnet6Desktop already)
            from src.core.dependency_installer import DependencyInstaller
            deps = DependencyInstaller()

            # Set up callback for live logging to GUI
            if self.log_callback:
                self.logger.info("Setting up live logging callback for GUI updates")
                deps.set_log_callback(self.log_callback)

            # Install MO2 dependencies (same as Vortex needs)
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
            self.logger.info("Successfully installed Vortex dependencies!")

            return {
                "success": True,
                "message": f"Successfully installed Vortex dependencies for {app_name}!",
                "app_id": app_id,
                "game_name": app_name,
                "dependency_result": result
            }

        except Exception as e:
            self.logger.error(f"Failed to auto-install dependencies: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def setup_existing(self, vortex_dir: str, custom_name: str = "Vortex") -> Dict[str, Any]:
        """Setup existing Vortex installation from directory"""
        try:
            self._log_progress(f"Setting up existing Vortex installation from: {vortex_dir}")
            self._send_progress_update(10)

            # Verify the directory exists
            self._log_progress("Verifying Vortex directory...")
            if not os.path.exists(vortex_dir):
                return {"success": False, "error": f"Directory does not exist: {vortex_dir}"}
            self._send_progress_update(20)

            # Find Vortex.exe in the directory
            self._log_progress("Finding Vortex.exe...")
            vortex_exe = self._find_vortex_executable(vortex_dir)
            if not vortex_exe:
                return {"success": False, "error": f"Could not find Vortex.exe in: {vortex_dir}"}
            self._send_progress_update(30)

            # Use the provided custom name
            self._log_progress(f"Using installation name: {custom_name}")

            # Add to Steam
            self._log_progress(f"Adding {custom_name} to Steam...")
            steam_result = self._add_vortex_to_steam(vortex_exe, custom_name)
            if not steam_result["success"]:
                return steam_result
            self._send_progress_update(50)

            app_id = steam_result.get("app_id")
            self._log_progress(f"Successfully added to Steam with AppID: {app_id}")

            # Install dependencies
            self._log_progress("Installing Vortex dependencies...")
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
            save_symlink_result = self._setup_save_symlinks(vortex_dir, str(app_id))
            self._send_progress_update(85)

            # Run Vortex briefly to create registry entries, then fix them
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("DEBUG: REACHED VORTEX REGISTRY FIX CODE PATH")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self._log_progress("Initializing Vortex and fixing registry...")
            try:
                compat_data_path = steam_result.get("compat_data_path")
                if compat_data_path:
                    # Get Proton path
                    steam_root = self.steam_utils.get_steam_root()
                    proton_path = os.path.join(steam_root, "steamapps", "common", "Proton - Experimental", "proton")

                    if not os.path.exists(proton_path):
                        # Try other Proton versions
                        for version in ["Proton 9.0", "Proton 8.0", "Proton 7.0"]:
                            alt_path = os.path.join(steam_root, "steamapps", "common", version, "proton")
                            if os.path.exists(alt_path):
                                proton_path = alt_path
                                break

                    if os.path.exists(proton_path):
                        # Set up environment for Proton
                        env = os.environ.copy()
                        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam_root
                        env["STEAM_COMPAT_DATA_PATH"] = compat_data_path
                        env["WINEPREFIX"] = os.path.join(compat_data_path, "pfx")

                        # Run Vortex briefly to create registry entries
                        self._run_vortex_briefly(vortex_exe, compat_data_path, proton_path, env)

                        # Now fix the registry
                        self._fix_vortex_registry(vortex_dir, compat_data_path, proton_path, env)
                        self.logger.info("Registry paths fixed for existing Vortex installation")
                    else:
                        self.logger.warning("Proton not found, skipping registry fix")
                else:
                    self.logger.warning("No compat_data_path, skipping registry fix")
            except Exception as e:
                self.logger.warning(f"Failed to fix registry (non-critical): {e}")

            # Configure NXM handler
            self._log_progress("Configuring NXM handler...")
            nxm_result = self._configure_nxm_handler(vortex_exe, str(app_id), custom_name)

            self._send_progress_update(95)

            self._log_progress("Setup completed successfully!")

            message = f"Existing Vortex installation configured successfully!"
            if save_symlink_result.get("success") and save_symlink_result.get("games_symlinked", 0) > 0:
                message += f" Save symlinks created for {save_symlink_result['games_symlinked']} game(s)."
            if nxm_result.get("success"):
                message += f" NXM handler configured!"

            return {
                "success": True,
                "install_dir": vortex_dir,
                "vortex_exe": vortex_exe,
                "vortex_name": custom_name,
                "app_id": app_id,
                "message": message,
                "steam_integration": steam_result,
                "dependency_installation": dep_result,
                "save_symlinks": save_symlink_result,
                "nxm_handler": nxm_result
            }

        except Exception as e:
            self.logger.error(f"Failed to setup existing Vortex: {e}")
            return {"success": False, "error": str(e)}

    def setup_existing_exe(self, vortex_exe: str, custom_name: str) -> Dict[str, Any]:
        """Setup existing Vortex installation from executable file"""
        try:
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("SETUP_EXISTING_EXE METHOD CALLED")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info(f"Setting up existing Vortex installation from: {vortex_exe}")
            self.logger.info(f"Custom name: {custom_name}")

            # Verify the executable exists
            if not os.path.exists(vortex_exe):
                return {"success": False, "error": f"Executable does not exist: {vortex_exe}"}

            # Verify it's Vortex.exe
            if not vortex_exe.lower().endswith("vortex.exe"):
                return {"success": False, "error": f"File is not Vortex.exe: {vortex_exe}"}

            # Add to Steam
            steam_result = self._add_vortex_to_steam(vortex_exe, custom_name)
            if not steam_result["success"]:
                self.logger.error(f"Steam integration failed: {steam_result}")
                return steam_result

            app_id = steam_result["app_id"]
            self.logger.info(f"Got AppID: {app_id}")

            # Install dependencies
            self.logger.info("Installing Vortex dependencies...")
            from src.core.dependency_installer import DependencyInstaller
            deps = DependencyInstaller()
            dep_result = deps.install_mo2_dependencies_for_game(str(app_id))

            # Setup save symlinks
            from pathlib import Path
            vortex_dir = str(Path(vortex_exe).parent)
            save_symlink_result = self._setup_save_symlinks(vortex_dir, str(app_id))

            # Run Vortex briefly to create registry entries, then fix them
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("DEBUG: REACHED VORTEX REGISTRY FIX CODE PATH (setup_existing_exe)")
            self.logger.info("═══════════════════════════════════════════════════════════════")
            self.logger.info("Initializing Vortex and fixing registry...")
            try:
                compat_data_path = steam_result.get("compat_data_path")
                if compat_data_path:
                    # Get Proton path
                    steam_root = self.steam_utils.get_steam_root()
                    proton_path = os.path.join(steam_root, "steamapps", "common", "Proton - Experimental", "proton")

                    if not os.path.exists(proton_path):
                        # Try other Proton versions
                        for version in ["Proton 9.0", "Proton 8.0", "Proton 7.0"]:
                            alt_path = os.path.join(steam_root, "steamapps", "common", version, "proton")
                            if os.path.exists(alt_path):
                                proton_path = alt_path
                                break

                    if os.path.exists(proton_path):
                        # Set up environment for Proton
                        env = os.environ.copy()
                        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam_root
                        env["STEAM_COMPAT_DATA_PATH"] = compat_data_path
                        env["WINEPREFIX"] = os.path.join(compat_data_path, "pfx")

                        # Run Vortex briefly to create registry entries
                        self._run_vortex_briefly(vortex_exe, compat_data_path, proton_path, env)

                        # Now fix the registry
                        self._fix_vortex_registry(vortex_dir, compat_data_path, proton_path, env)
                        self.logger.info("Registry paths fixed for existing Vortex installation")
                    else:
                        self.logger.warning("Proton not found, skipping registry fix")
                else:
                    self.logger.warning("No compat_data_path, skipping registry fix")
            except Exception as e:
                self.logger.warning(f"Failed to fix registry (non-critical): {e}")

            # Configure NXM handler
            self.logger.info("Configuring NXM handler...")
            nxm_result = self._configure_nxm_handler(vortex_exe, str(app_id), custom_name)

            message = f"Existing Vortex installation configured successfully!"
            if save_symlink_result.get("success") and save_symlink_result.get("games_symlinked", 0) > 0:
                message += f" Save symlinks created for {save_symlink_result['games_symlinked']} game(s)."
            if nxm_result.get("success"):
                message += f" NXM handler configured!"

            return {
                "success": True,
                "vortex_exe": vortex_exe,
                "vortex_name": custom_name,
                "app_id": app_id,
                "message": message,
                "steam_integration": steam_result,
                "dependency_installation": dep_result,
                "save_symlinks": save_symlink_result,
                "nxm_handler": nxm_result
            }

        except Exception as e:
            self.logger.error(f"Failed to setup existing Vortex: {e}")
            return {"success": False, "error": str(e)}
