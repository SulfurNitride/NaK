"""
MO2 Installer module for downloading and installing Mod Organizer 2
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import requests

from ..utils.logger import get_logger
from ..utils.steam_utils import SteamUtils


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
        """Set progress callback for download updates"""
        self.progress_callback = callback
    
    def set_log_callback(self, callback):
        """Set log callback for status messages"""
        self.log_callback = callback
    
    def _log_progress(self, message):
        """Log progress message to both logger and callback"""
        self.logger.info(message)
        if self.log_callback:
            self.log_callback(message)
    
    def download_mo2(self, install_dir: Optional[str] = None, custom_name: Optional[str] = None) -> Dict[str, Any]:
        """Download and install the latest version of Mod Organizer 2 with complete Steam integration"""
        try:
            self.logger.info("Starting MO2 download and installation with Steam integration")
            
            # Check dependencies
            self._log_progress("Checking dependencies...")
            deps_result = self._check_dependencies()
            if not deps_result["success"]:
                return deps_result
            
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
                    return steam_result
                
                # Auto-install dependencies
                self._log_progress("Installing dependencies...")
                dependency_result = self._auto_install_dependencies(steam_result["app_id"], mo2_name)
                
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
                    "dependency_installation": dependency_result
                }
                
                # Update message if dependencies were installed
                if dependency_result["success"]:
                    result["message"] = f"Mod Organizer 2 {release.tag_name} installed, added to Steam, and dependencies installed successfully!"
                
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
    
    def setup_existing(self) -> Dict[str, Any]:
        """Configure an existing MO2 installation"""
        try:
            self.logger.info("Setting up existing MO2 installation")
            
            # Ask user to select MO2 directory
            mo2_dir = self._select_mo2_directory()
            if not mo2_dir:
                return {"success": False, "error": "No MO2 directory selected"}
            
            # Verify it's a valid MO2 installation
            self._verify_installation(mo2_dir)
            
            # Find MO2 executable
            mo2_exe = self._find_mo2_executable(mo2_dir)
            
            return {
                "success": True,
                "install_dir": mo2_dir,
                "mo2_exe": mo2_exe,
                "message": "Existing MO2 installation configured successfully!"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to setup existing MO2: {e}")
            return {"success": False, "error": str(e)}
    
    def remove_nxm_handlers(self) -> Dict[str, Any]:
        """Remove previously configured NXM handlers"""
        try:
            self.logger.info("Removing NXM handlers")
            
            # Remove desktop file
            desktop_file = os.path.expanduser("~/.local/share/applications/nxm-handler.desktop")
            if os.path.exists(desktop_file):
                os.remove(desktop_file)
                self.logger.info("Removed NXM handler desktop file")
            
            # Remove MIME type registration
            try:
                subprocess.run(["xdg-mime", "uninstall", "application/x-nxm"], 
                             check=True, capture_output=True)
                self.logger.info("Removed MIME type registration")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to remove MIME type: {e}")
            
            # Update desktop database
            try:
                subprocess.run(["update-desktop-database", 
                              os.path.expanduser("~/.local/share/applications")], 
                             check=True, capture_output=True)
                self.logger.info("Updated desktop database")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to update desktop database: {e}")
            
            return {
                "success": True,
                "message": "NXM handlers removed successfully!"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to remove NXM handlers: {e}")
            return {"success": False, "error": str(e)}
    
    def _check_dependencies(self) -> Dict[str, Any]:
        """Check if required dependencies are available"""
        # Check for curl or requests (for downloading)
        if not self._command_exists("curl"):
            self.logger.info("curl not found, will use requests library")
        
        # Check for 7z tools
        if not self._check_7z_tools():
            self.logger.warning("No 7z tools found, extraction may fail")
            return {
                "success": False,
                "error": "Missing required dependencies (7z tools not found)"
            }
        
        return {"success": True}
    
    def _check_7z_tools(self) -> bool:
        """Check if 7z tools are available"""
        tools = ["7z", "7za", "7zr", "7zip", "p7zip"]
        
        for tool in tools:
            if self._command_exists(tool):
                self.logger.info(f"Found 7z tool: {tool}")
                return True
        
        self.logger.error("No 7z tools found")
        return False
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists"""
        try:
            subprocess.run([command, "--help"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL, 
                         check=False)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _get_latest_release(self) -> Optional[GitHubRelease]:
        """Get the latest MO2 release from GitHub"""
        try:
            # MO2 GitHub API URL
            url = "https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest"
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return GitHubRelease(data["tag_name"], data["assets"])
            
        except Exception as e:
            self.logger.error(f"Failed to get latest release: {e}")
            return None
    
    def _find_mo2_asset(self, release: GitHubRelease) -> Tuple[Optional[str], Optional[str]]:
        """Find the appropriate MO2 asset for download"""
        # Look for the exact pattern: Mod.Organizer-X.Y.Z.7z (main release)
        for asset in release.assets:
            name = asset["name"]
            if (name.startswith("Mod.Organizer-") and
                name.endswith(".7z") and
                "pdbs" not in name and
                "src" not in name and
                "uibase" not in name and
                "uicpp" not in name and
                "bsa" not in name):
                return asset["browser_download_url"], name
        
        # If no main release found, look for any 7z file (but exclude problematic ones)
        for asset in release.assets:
            name = asset["name"]
            if (name.startswith("Mod.Organizer-") and
                name.endswith(".7z") and
                "src" not in name):
                return asset["browser_download_url"], name
        
        return None, None
    
    def _get_install_directory(self) -> Optional[str]:
        """Get installation directory"""
        default_dir = str(Path.home() / "ModOrganizer2")
        
        self.logger.info(f"Default directory: {default_dir}")
        
        # For now, use default directory
        # TODO: Add user input for custom directory
        install_dir = default_dir
        
        # Create directory if it doesn't exist
        try:
            Path(install_dir).mkdir(parents=True, exist_ok=True)
            return install_dir
        except Exception as e:
            self.logger.error(f"Failed to create directory: {e}")
            return None
    
    def _download_file(self, url: str, filename: str, progress_callback=None) -> Optional[str]:
        """Download the MO2 archive with progress tracking"""
        self.logger.info(f"Downloading Mod Organizer 2...")
        self.logger.info(f"From: {url}")
        
        try:
            # Create temporary file
            temp_file = os.path.join(tempfile.gettempdir(), filename)
            
            # Download the file with progress tracking and optimized settings
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            
            # Debug: Log the actual download URL being used
            self.logger.info(f"Download URL: {url}")
            
            response = requests.get(url, stream=True, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # Debug: Log final URL after redirects and some response info
            self.logger.info(f"Final download URL: {response.url}")
            self.logger.info(f"Response status: {response.status_code}")
            self.logger.info(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            # Get total file size from headers
            total_size = int(response.headers.get('content-length', 0))
            self.logger.info(f"File size: {total_size} bytes ({total_size / (1024*1024):.1f} MB)")
            downloaded_size = 0
            last_progress_update = 0
            start_time = time.time()
            
            # Use larger chunk size for better performance (1MB chunks)  
            chunk_size = 1024 * 1024  # 1MB chunks instead of 8KB
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:  # filter out keep-alive chunks
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Report progress if callback provided (but not on every chunk)
                        if progress_callback and total_size > 0:
                            progress_percent = int((downloaded_size / total_size) * 100)
                            
                            # Only call progress callback if percent changed to reduce overhead
                            if progress_percent != last_progress_update:
                                progress_callback(progress_percent, downloaded_size, total_size)
                                last_progress_update = progress_percent
                        
                        # Also log progress to main logger every 20MB for terminal output (less spam)
                        if downloaded_size % (20 * 1024 * 1024) < len(chunk) and total_size > 0:
                            progress_percent = int((downloaded_size / total_size) * 100)
                            downloaded_mb = downloaded_size / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            self.logger.info(f"Download progress: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({progress_percent}%)")
            
            # Calculate and log download speed
            end_time = time.time()
            download_time = end_time - start_time
            if download_time > 0:
                speed_bps = downloaded_size / download_time
                speed_mbps = speed_bps / (1024 * 1024)
                self.logger.info(f"Download completed! Speed: {speed_mbps:.2f} MB/s ({speed_bps/1024:.1f} KB/s)")
            else:
                self.logger.info("Download completed!")
            
            return temp_file
            
        except Exception as e:
            self.logger.error(f"Failed to download file: {e}")
            return None
    
    def _extract_archive(self, archive_path: str, extract_path: str) -> Optional[str]:
        """Extract the 7z archive"""
        self.logger.info(f"Extracting to {extract_path}...")
        
        # Try system 7z tools first
        if self._check_7z_tools():
            result = self._extract_with_system_7z(archive_path, extract_path)
            if result:
                return result
        
        # Fall back to Python extraction
        self.logger.warning("System 7z tools failed, trying Python extraction")
        return self._extract_with_python(archive_path, extract_path)
    
    def _extract_with_system_7z(self, archive_path: str, extract_path: str) -> Optional[str]:
        """Extract using system 7z tools"""
        tools = ["7z", "7za", "7zr", "7zip", "p7zip"]
        
        for tool in tools:
            if self._command_exists(tool):
                try:
                    self.logger.info(f"Trying to extract with {tool}")
                    
                    # Create the extract directory if it doesn't exist
                    Path(extract_path).mkdir(parents=True, exist_ok=True)
                    
                    # Use different command line options based on the tool
                    if tool in ["7z", "7za"]:
                        args = ["x", archive_path, f"-o{extract_path}", "-y"]
                    else:
                        args = ["x", archive_path, "-o", extract_path, "-y"]
                    
                    result = subprocess.run([tool] + args, 
                                          capture_output=True, 
                                          text=True, 
                                          check=False)
                    
                    if result.returncode == 0:
                        self.logger.info(f"Successfully extracted using {tool}")
                        return extract_path
                    else:
                        self.logger.warning(f"{tool} failed: {result.stderr}")
                        continue
                        
                except Exception as e:
                    self.logger.warning(f"Failed to use {tool}: {e}")
                    continue
        
        return None
    
    def _extract_with_python(self, archive_path: str, extract_path: str) -> Optional[str]:
        """Extract using Python (basic implementation)"""
        try:
            # Try using py7zr if available
            try:
                import py7zr
                
                self.logger.info("Using py7zr for extraction")
                
                # Create the extract directory
                Path(extract_path).mkdir(parents=True, exist_ok=True)
                
                with py7zr.SevenZipFile(archive_path, mode='r') as z:
                    z.extractall(extract_path)
                
                self.logger.info("Successfully extracted using py7zr")
                return extract_path
                
            except ImportError:
                self.logger.warning("py7zr not available")
            
            # Try using zipfile for zip files (if MO2 provides zip)
            if archive_path.endswith('.zip'):
                import zipfile
                
                self.logger.info("Using zipfile for extraction")
                
                # Create the extract directory
                Path(extract_path).mkdir(parents=True, exist_ok=True)
                
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                self.logger.info("Successfully extracted using zipfile")
                return extract_path
            
            self.logger.error("No suitable extraction method available")
            return None
            
        except Exception as e:
            self.logger.error(f"Python extraction failed: {e}")
            return None
    
    def _verify_installation(self, install_dir: str) -> Dict[str, Any]:
        """Verify that MO2 was installed correctly"""
        self.logger.info(f"Verifying installation in: {install_dir}")
        
        # Check if the directory exists
        if not os.path.exists(install_dir):
            self.logger.error(f"Installation directory does not exist: {install_dir}")
            return {
                "success": False,
                "error": f"Installation directory does not exist: {install_dir}"
            }
        
        # List all files in the directory for debugging
        try:
            files = os.listdir(install_dir)
            self.logger.info(f"Files in installation directory: {files}")
        except Exception as e:
            self.logger.error(f"Could not list files in directory: {e}")
            return {
                "success": False,
                "error": f"Could not list files in directory: {e}"
            }
        
        # Look for ModOrganizer.exe in the root directory
        mo2_exe = os.path.join(install_dir, "ModOrganizer.exe")
        if os.path.exists(mo2_exe):
            self.logger.info(f"Found ModOrganizer.exe in root directory: {mo2_exe}")
            return {"success": True}
        
        # Try to find it in subdirectories
        mo2_exe = self._find_mo2_executable(install_dir)
        if mo2_exe:
            self.logger.info(f"Found ModOrganizer.exe in subdirectory: {mo2_exe}")
            return {"success": True}
        
        # If we still can't find it, let's look for any .exe files
        exe_files = []
        for root, dirs, files in os.walk(install_dir):
            for file in files:
                if file.endswith('.exe'):
                    exe_files.append(os.path.join(root, file))
        
        if exe_files:
            self.logger.warning(f"Found .exe files but no ModOrganizer.exe: {exe_files}")
            return {
                "success": False,
                "error": f"Found .exe files but no ModOrganizer.exe: {exe_files}"
            }
        else:
            self.logger.error("No .exe files found in the extracted directory")
            return {
                "success": False,
                "error": "No .exe files found in the extracted directory"
            }
    
    def _find_mo2_executable(self, root_dir: str) -> Optional[str]:
        """Search for ModOrganizer.exe in subdirectories"""
        self.logger.info(f"Searching for ModOrganizer.exe in: {root_dir}")
        
        for root, dirs, files in os.walk(root_dir):
            self.logger.debug(f"Checking directory: {root}")
            self.logger.debug(f"Files found: {files}")
            
            if "ModOrganizer.exe" in files:
                path = os.path.join(root, "ModOrganizer.exe")
                self.logger.info(f"Found ModOrganizer.exe: {path}")
                return path
            
            # Also check for variations in case
            for file in files:
                if file.lower() == "modorganizer.exe":
                    path = os.path.join(root, file)
                    self.logger.info(f"Found ModOrganizer.exe (case variation): {path}")
                    return path
        
        self.logger.warning("ModOrganizer.exe not found in any subdirectory")
        return None
    
    def setup_existing(self, mo2_dir: str) -> Dict[str, Any]:
        """Setup existing MO2 installation from directory"""
        try:
            self.logger.info(f"Setting up existing MO2 installation from: {mo2_dir}")
            
            # Verify the directory exists
            if not os.path.exists(mo2_dir):
                return {"success": False, "error": f"Directory does not exist: {mo2_dir}"}
            
            # Find ModOrganizer.exe in the directory
            mo2_exe = self._find_mo2_executable(mo2_dir)
            if not mo2_exe:
                return {"success": False, "error": f"Could not find ModOrganizer.exe in: {mo2_dir}"}
            
            # Ask for custom name (this will be handled by GUI)
            custom_name = "Mod Organizer 2"
            
            # Add to Steam
            steam_result = self._add_mo2_to_steam(mo2_exe, custom_name)
            if not steam_result["success"]:
                return steam_result
            
            app_id = steam_result["app_id"]
            
            # Install dependencies directly
            self.logger.info("Installing MO2 dependencies...")
            from .dependency_installer import DependencyInstaller
            deps = DependencyInstaller()
            dep_result = deps.install_mo2_dependencies_for_game(str(app_id))
            
            return {
                "success": True,
                "install_dir": mo2_dir,
                "mo2_exe": mo2_exe,
                "mo2_name": custom_name,
                "app_id": app_id,
                "message": f"Existing MO2 installation configured successfully!",
                "steam_integration": steam_result,
                "dependency_installation": dep_result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to setup existing MO2: {e}")
            return {"success": False, "error": str(e)}
    
    def setup_existing_exe(self, mo2_exe: str, custom_name: str) -> Dict[str, Any]:
        """Setup existing MO2 installation from executable file"""
        try:
            self.logger.info(f"Setting up existing MO2 installation from: {mo2_exe}")
            
            # Verify the executable exists
            if not os.path.exists(mo2_exe):
                return {"success": False, "error": f"Executable does not exist: {mo2_exe}"}
            
            # Verify it's ModOrganizer.exe
            if not mo2_exe.lower().endswith("modorganizer.exe"):
                return {"success": False, "error": f"File is not ModOrganizer.exe: {mo2_exe}"}
            
            # Add to Steam
            steam_result = self._add_mo2_to_steam(mo2_exe, custom_name)
            if not steam_result["success"]:
                return steam_result
            
            app_id = steam_result["app_id"]
            
            # Install dependencies directly
            self.logger.info("Installing MO2 dependencies...")
            from .dependency_installer import DependencyInstaller
            deps = DependencyInstaller()
            dep_result = deps.install_mo2_dependencies_for_game(str(app_id))
            
            return {
                "success": True,
                "mo2_exe": mo2_exe,
                "mo2_name": custom_name,
                "app_id": app_id,
                "message": f"Existing MO2 installation configured successfully!",
                "steam_integration": steam_result,
                "dependency_installation": dep_result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to setup existing MO2: {e}")
            return {"success": False, "error": str(e)}
    
    def configure_nxm_handler(self, app_id: str, nxm_handler_path: str) -> Dict[str, Any]:
        """Configure improved NXM handler for a specific game with smart process detection"""
        try:
            self.logger.info(f"Configuring improved NXM handler for AppID {app_id} with handler: {nxm_handler_path}")
            
            # Verify the nxmhandler.exe exists
            if not os.path.exists(nxm_handler_path):
                return {"success": False, "error": f"NXM handler not found: {nxm_handler_path}"}
            
            # Verify it's nxmhandler.exe
            if not nxm_handler_path.lower().endswith("nxmhandler.exe"):
                return {"success": False, "error": f"File is not nxmhandler.exe: {nxm_handler_path}"}
            
            # Get Steam root directory
            steam_root = self.steam_utils.get_steam_root()
            if not steam_root:
                return {"success": False, "error": "Could not find Steam installation"}
            
            # Get MO2 executable path from the nxmhandler path
            mo2_dir = os.path.dirname(nxm_handler_path)
            mo2_exe = os.path.join(mo2_dir, "ModOrganizer.exe")
            if not os.path.exists(mo2_exe):
                return {"success": False, "error": f"ModOrganizer.exe not found in: {mo2_dir}"}
            
            # Create the smart NXM handler script
            handler_script_path = self._create_smart_nxm_script(app_id, mo2_exe, nxm_handler_path, steam_root)
            if not handler_script_path:
                return {"success": False, "error": "Failed to create NXM handler script"}
            
            # Create desktop file that calls our smart script
            home_dir = os.path.expanduser("~")
            desktop_file = os.path.join(home_dir, ".local", "share", "applications", "modorganizer2-nxm-handler.desktop")
            
            # Create applications directory if it doesn't exist
            applications_dir = os.path.dirname(desktop_file)
            os.makedirs(applications_dir, exist_ok=True)
            
            desktop_content = f"""[Desktop Entry]
Type=Application
Categories=Game;
Exec=bash "{handler_script_path}" "%u"
Name=Mod Organizer 2 NXM Handler
MimeType=x-scheme-handler/nxm;
NoDisplay=true
"""
            
            # Write desktop file
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
            
            self.logger.info(f"Created desktop file: {desktop_file}")
            
            # Make handler script executable
            os.chmod(handler_script_path, 0o755)
            
            # Register MIME handler
            mime_result = self._register_mime_handler()
            if not mime_result["success"]:
                return mime_result
            
            return {
                "success": True,
                "message": f"Smart NXM handler configured successfully for AppID {app_id}!",
                "desktop_file": desktop_file,
                "handler_script": handler_script_path,
                "nxm_handler_path": nxm_handler_path,
                "mo2_exe": mo2_exe
            }
            
        except Exception as e:
            self.logger.error(f"Failed to configure NXM handler: {e}")
            return {"success": False, "error": str(e)}
    
    def remove_nxm_handlers(self) -> Dict[str, Any]:
        """Remove NXM handler configuration"""
        try:
            self.logger.info("Removing NXM handler configuration...")
            
            # Remove desktop file
            desktop_file = os.path.expanduser("~/.local/share/applications/modorganizer2-nxm-handler.desktop")
            if os.path.exists(desktop_file):
                os.remove(desktop_file)
                self.logger.info("Removed NXM handler desktop file")
            
            # Remove smart handler scripts
            home_dir = os.path.expanduser("~")
            script_dir = os.path.join(home_dir, ".local", "share", "nak")
            if os.path.exists(script_dir):
                import glob
                nxm_scripts = glob.glob(os.path.join(script_dir, "nxm-handler-*.sh"))
                for script in nxm_scripts:
                    try:
                        os.remove(script)
                        self.logger.info(f"Removed NXM handler script: {script}")
                    except Exception as e:
                        self.logger.warning(f"Failed to remove script {script}: {e}")
            
            # Remove MIME type registration
            try:
                subprocess.run(["xdg-mime", "uninstall", "application/x-nxm"], 
                             check=True, capture_output=True)
                self.logger.info("Removed MIME type registration")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to remove MIME type: {e}")
            
            # Update desktop database
            try:
                subprocess.run(["update-desktop-database", 
                              os.path.expanduser("~/.local/share/applications")], 
                             check=True, capture_output=True)
                self.logger.info("Updated desktop database")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to update desktop database: {e}")
            
            return {
                "success": True,
                "message": "NXM handlers removed successfully!"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to remove NXM handlers: {e}")
            return {"success": False, "error": str(e)}
    
    def _select_mo2_directory(self) -> Optional[str]:
        """Select MO2 directory from user input"""
        # This would be handled by the GUI layer
        # For now, return None to indicate user selection needed
        return None
    
    def _find_proton_path(self, steam_root: str, app_id: str) -> Optional[str]:
        """Find Proton path for a specific game"""
        try:
            # Check if game has compatibility tool set
            compat_data_path = os.path.join(steam_root, "steamapps", "compatdata", app_id)
            if not os.path.exists(compat_data_path):
                return None
            
            # Look for Proton installations in Steam
            steamapps_path = os.path.join(steam_root, "steamapps")
            common_path = os.path.join(steamapps_path, "common")
            
            if not os.path.exists(common_path):
                return None
            
            # Look for Proton directories
            proton_dirs = []
            for item in os.listdir(common_path):
                if item.startswith("Proton"):
                    proton_dirs.append(item)
            
            if not proton_dirs:
                return None
            
            # For now, return the first Proton found
            # In a full implementation, we'd check the game's compatibility tool setting
            proton_dir = proton_dirs[0]
            proton_path = os.path.join(common_path, proton_dir, "proton")
            
            if os.path.exists(proton_path):
                return proton_path
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to find Proton path: {e}")
            return None
    
    def _create_smart_nxm_script(self, app_id: str, mo2_exe: str, nxm_handler_path: str, steam_root: str) -> Optional[str]:
        """Create smart NXM handler script based on the bash script approach"""
        try:
            home_dir = os.path.expanduser("~")
            script_dir = os.path.join(home_dir, ".local", "share", "nak")
            os.makedirs(script_dir, exist_ok=True)
            
            script_path = os.path.join(script_dir, f"nxm-handler-{app_id}.sh")
            
            # Get compatdata path
            steam_compat_data_path = os.path.join(steam_root, "steamapps", "compatdata", app_id)
            
            # Find Proton path
            proton_path = self._find_proton_path(steam_root, app_id)
            if not proton_path:
                self.logger.error("Could not find Proton path for smart handler")
                return None
            
            # Determine if we need protontricks-launch or standard proton command
            use_wine_proton = "bin/wine" in proton_path
            
            # Create the smart handler script content
            script_content = f'''#!/usr/bin/env bash

# Smart NXM Handler for Mod Organizer 2
# Adapted from modorganizer2-nxm-broker.sh approach
# Generated by NaK Python Tool

# Parse NXM link
nxm_link="$1"

if [ -z "$nxm_link" ]; then
    echo "ERROR: please specify a NXM Link to download"
    # Try to show error in GUI if available
    if command -v zenity &> /dev/null; then
        zenity --error --text "ERROR: No NXM link provided"
    elif command -v notify-send &> /dev/null; then
        notify-send "NXM Handler Error" "No NXM link provided"
    fi
    exit 1
fi

# Extract game ID from NXM link
nexus_game_id="${{nxm_link#nxm://}}"
nexus_game_id="${{nexus_game_id%%/*}}"

# Paths
instance_dir="{os.path.dirname(mo2_exe)}"
mo2_exe="{mo2_exe}"
nxm_handler_exe="{nxm_handler_path}"
app_id="{app_id}"
steam_root="{steam_root}"
compat_data_path="{steam_compat_data_path}"
proton_path="{proton_path}"

# Check if MO2 is running
pgrep -f "$mo2_exe" > /dev/null 2>&1
process_search_status=$?

if [ "$process_search_status" == "0" ]; then
    echo "INFO: MO2 is running, sending download '$nxm_link' to existing instance"
    
    # Try protontricks-launch first if available
    if command -v protontricks-launch &> /dev/null; then
        download_start_output=$(WINEESYNC=1 WINEFSYNC=1 protontricks-launch --appid "$app_id" "$nxm_handler_exe" "$nxm_link" 2>&1)
        download_start_status=$?
    else
        # Fall back to direct Proton call
        if [ "{use_wine_proton}" == "True" ]; then
            # Wine-based Proton
            download_start_output=$(env "STEAM_COMPAT_CLIENT_INSTALL_PATH=$steam_root" "STEAM_COMPAT_DATA_PATH=$compat_data_path" "$proton_path" "$nxm_handler_exe" "$nxm_link" 2>&1)
        else
            # Standard Proton
            download_start_output=$(env "STEAM_COMPAT_CLIENT_INSTALL_PATH=$steam_root" "STEAM_COMPAT_DATA_PATH=$compat_data_path" "$proton_path" run "$nxm_handler_exe" "$nxm_link" 2>&1)
        fi
        download_start_status=$?
    fi
else
    echo "INFO: MO2 is not running, launching via Steam with NXM link"
    
    # Launch through Steam with the NXM link as parameter
    download_start_output=$(steam -applaunch "$app_id" "$nxm_link" 2>&1)
    download_start_status=$?
fi

# Handle results
if [ "$download_start_status" != "0" ]; then
    error_msg="Failed to start download:\\n\\n$download_start_output"
    echo "ERROR: $error_msg"
    
    # Show error in GUI if available
    if command -v zenity &> /dev/null; then
        zenity --ok-label=Exit --error --text "$error_msg"
    elif command -v notify-send &> /dev/null; then
        notify-send "NXM Handler Error" "$error_msg"
    fi
    exit 1
else
    echo "SUCCESS: Download started successfully"
    
    # Optional success notification
    if command -v notify-send &> /dev/null; then
        notify-send "NXM Handler" "Download started: $nexus_game_id"
    fi
fi

exit 0
'''
            
            # Write the script
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            self.logger.info(f"Created smart NXM handler script: {script_path}")
            return script_path
            
        except Exception as e:
            self.logger.error(f"Failed to create smart NXM handler script: {e}")
            return None
    
    def _register_mime_handler(self) -> Dict[str, Any]:
        """Register NXM MIME handler"""
        try:
            # Try xdg-mime first
            result = subprocess.run(["xdg-mime", "default", "modorganizer2-nxm-handler.desktop", "x-scheme-handler/nxm"], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                self.logger.info("MIME handler registered via xdg-mime")
                return {"success": True}
            
            # If xdg-mime fails, manually edit mimeapps.list
            self.logger.info("xdg-mime failed, trying manual registration...")
            
            home_dir = os.path.expanduser("~")
            mimeapps_path = os.path.join(home_dir, ".config", "mimeapps.list")
            
            # Create mimeapps.list if it doesn't exist
            if not os.path.exists(mimeapps_path):
                os.makedirs(os.path.dirname(mimeapps_path), exist_ok=True)
                with open(mimeapps_path, 'w') as f:
                    f.write("")
            
            # Read existing content
            with open(mimeapps_path, 'r') as f:
                content = f.read()
            
            # Remove any existing nxm handler entries
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                if "x-scheme-handler/nxm" not in line:
                    new_lines.append(line)
            
            # Add the new handler
            new_lines.append("x-scheme-handler/nxm=modorganizer2-nxm-handler.desktop")
            
            # Write back to file
            new_content = '\n'.join(new_lines)
            with open(mimeapps_path, 'w') as f:
                f.write(new_content)
            
            # Update desktop database
            update_cmd = subprocess.run(["update-desktop-database", 
                                      os.path.join(home_dir, ".local", "share", "applications")], 
                                     capture_output=True, text=True, check=False)
            
            if update_cmd.returncode == 0:
                self.logger.info("Desktop database updated successfully")
            else:
                self.logger.warning(f"Failed to update desktop database: {update_cmd.stderr}")
            
            return {"success": True}
            
        except Exception as e:
            self.logger.error(f"Failed to register MIME handler: {e}")
            return {"success": False, "error": str(e)}

    def _add_mo2_to_steam(self, mo2_exe: str, mo2_name: str) -> Dict[str, Any]:
        """Add MO2 to Steam with complete integration (shortcut, prefix, dependencies)"""
        try:
            self.logger.info(f"Adding {mo2_name} to Steam with complete integration...")
            
            # Step 1: Create Steam shortcut
            self.logger.info("Creating Steam shortcut...")
            steam_result = self.steam_utils.add_game_to_steam(mo2_name, mo2_exe)
            if not steam_result["success"]:
                return steam_result
            
            app_id = steam_result["app_id"]
            compat_data_path = steam_result["compat_data_path"]
            
            self.logger.info(f"Steam shortcut created with AppID: {app_id}")
            self.logger.info(f"Executable path: {mo2_exe}")
            self.logger.info(f"Compatdata folder created: {compat_data_path}")
            
            self.logger.info("Successfully ran .bat file with Proton")
            self.logger.info("Waiting 5 seconds for Wine prefix initialization...")
            time.sleep(5)
            
            return {
                "success": True,
                "app_id": app_id,
                "compat_data_path": compat_data_path,
                "message": f"Successfully added '{mo2_name}' to Steam! Compatdata folder created and Wine prefix initialized. AppID: {app_id}"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to add MO2 to Steam: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _auto_install_dependencies(self, app_id: int, app_name: str) -> Dict[str, Any]:
        """Automatically install dependencies for a newly created game"""
        try:
            self.logger.info(f"Auto-installing dependencies for newly created game: {app_name} (AppID: {app_id})")
            
            # Wait a moment for Steam to recognize the new shortcut
            self.logger.info("Waiting for Steam to recognize the new shortcut...")
            time.sleep(2)
            
            # Try to get the game from Steam shortcuts
            games = self.steam_utils.get_non_steam_games()
            if not games:
                self.logger.warning("Could not get Steam games list")
                return {
                    "success": True,
                    "message": "Game created successfully! Dependencies will be installed after Steam restart.",
                    "note": "Steam needs to be restarted to see the new shortcut before dependencies can be installed."
                }
            
            # Look for our newly created game
            found_game = None
            for game in games:
                if game.get("AppID") == str(app_id):
                    found_game = game
                    break
            
            if not found_game:
                self.logger.info("Game not yet visible in Steam shortcuts - this is normal")
                return {
                    "success": True,
                    "message": "Game created successfully! Dependencies will be installed after Steam restart.",
                    "note": "Steam needs to be restarted to see the new shortcut before dependencies can be installed."
                }
            
            # Game found! Install dependencies
            self.logger.info(f"Found game in Steam: {found_game['Name']}")
            self.logger.info("Installing MO2 dependencies...")
            
            # Import dependency installer here to avoid circular imports
            from .dependency_installer import DependencyInstaller
            deps = DependencyInstaller()
            
            # Install MO2 dependencies for this game
            result = deps.install_mo2_dependencies_for_game(str(app_id))
            if not result["success"]:
                self.logger.error(f"Failed to install dependencies: {result.get('error', 'Unknown error')}")
                return result
            
            self.logger.info("Successfully installed MO2 dependencies!")
            return {
                "success": True,
                "message": f"Successfully installed MO2 dependencies for {app_name}!",
                "app_id": app_id,
                "game_name": app_name
            }
            
        except Exception as e:
            self.logger.error(f"Failed to auto-install dependencies: {e}")
            return {
                "success": False,
                "error": str(e)
            }
