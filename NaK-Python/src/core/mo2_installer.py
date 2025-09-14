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
            
            # Create the NXM handler script directly in applications folder
            handler_script_path = self._create_nxm_handler_script(app_id, mo2_exe, nxm_handler_path, steam_root)
            if not handler_script_path:
                return {"success": False, "error": "Failed to create NXM handler script"}
            
            # Create desktop file that calls our script
            home_dir = os.path.expanduser("~")
            desktop_file = os.path.join(home_dir, ".local", "share", "applications", "mo2-nxm-handler.desktop")
            
            # Create applications directory if it doesn't exist
            applications_dir = os.path.dirname(desktop_file)
            os.makedirs(applications_dir, exist_ok=True)
            
            desktop_content = f"""[Desktop Entry]
Type=Application
Categories=Game;
Exec={handler_script_path} %u
Name=Mod Organizer 2 NXM Handler
MimeType=x-scheme-handler/nxm;
NoDisplay=true
"""
            
            # Write desktop file
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
            
            self.logger.info(f"Created desktop file: {desktop_file}")
            
            # Register MIME handler
            mime_result = self._register_mime_handler("mo2-nxm-handler.desktop")
            if not mime_result["success"]:
                return mime_result
            
            return {
                "success": True,
                "message": f"NXM handler configured successfully for AppID {app_id}!",
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
            
            home_dir = os.path.expanduser("~")
            applications_dir = os.path.join(home_dir, ".local", "share", "applications")
            
            # Remove all MO2 NXM handler files
            import glob
            
            # Remove desktop files
            desktop_patterns = [
                "mo2-nxm-handler.desktop",
                "modorganizer2-nxm-handler.desktop"
            ]
            
            for pattern in desktop_patterns:
                desktop_file = os.path.join(applications_dir, pattern)
                if os.path.exists(desktop_file):
                    os.remove(desktop_file)
                    self.logger.info(f"Removed desktop file: {desktop_file}")
            
            # Remove handler scripts
            script_patterns = [
                "mo2-nxm-handler-*.sh",
                "nxm-handler-*.sh"
            ]
            
            for pattern in script_patterns:
                scripts = glob.glob(os.path.join(applications_dir, pattern))
                for script in scripts:
                    try:
                        os.remove(script)
                        self.logger.info(f"Removed script: {script}")
                    except Exception as e:
                        self.logger.warning(f"Failed to remove script {script}: {e}")
            
            # Remove old NAK directory if it exists
            nak_dir = os.path.join(home_dir, ".local", "share", "nak")
            if os.path.exists(nak_dir):
                import shutil
                try:
                    shutil.rmtree(nak_dir)
                    self.logger.info("Removed old NAK directory")
                except Exception as e:
                    self.logger.warning(f"Failed to remove NAK directory: {e}")
            
            # Remove MIME type registration
            try:
                subprocess.run(["xdg-mime", "uninstall", "application/x-nxm"], 
                             check=True, capture_output=True)
                self.logger.info("Removed MIME type registration")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to remove MIME type: {e}")
            
            # Update desktop database
            try:
                subprocess.run(["update-desktop-database", applications_dir], 
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
    
    def _create_nxm_handler_script(self, app_id: str, mo2_exe: str, nxm_handler_path: str, steam_root: str) -> Optional[str]:
        """Create NXM handler script directly in applications folder"""
        try:
            home_dir = os.path.expanduser("~")
            applications_dir = os.path.join(home_dir, ".local", "share", "applications")
            os.makedirs(applications_dir, exist_ok=True)
            
            script_path = os.path.join(applications_dir, f"mo2-nxm-handler-{app_id}.sh")
            
            # Get compatdata path
            steam_compat_data_path = os.path.join(steam_root, "steamapps", "compatdata", app_id)
            
            # Find Proton path
            proton_path = self._find_proton_path(steam_root, app_id)
            if not proton_path:
                self.logger.error("Could not find Proton path for handler")
                return None
            
            # Create the handler script content
            script_content = f'''#!/usr/bin/env bash
# NXM Handler for Mod Organizer 2
# Generated by NaK Python Tool

NXM_LINK="$1"

if [ -z "$NXM_LINK" ]; then
    echo "ERROR: No NXM link provided"
    if command -v notify-send &> /dev/null; then
        notify-send "NXM Handler Error" "No NXM link provided"
    fi
    exit 1
fi

echo "NXM Handler: Processing $NXM_LINK"

# Use direct Proton approach (like .NET 9 SDK installation)
echo "Using direct Proton approach for maximum compatibility"

# Check if MO2 is running
if pgrep -f "{mo2_exe}" > /dev/null 2>&1; then
    echo "MO2 is running - sending to existing instance"
    env STEAM_COMPAT_CLIENT_INSTALL_PATH="{steam_root}" STEAM_COMPAT_DATA_PATH="{steam_compat_data_path}" "{proton_path}" run "{nxm_handler_path}" "$NXM_LINK"
else
    echo "MO2 is not running - launching directly through Proton"
    # Launch MO2 in background
    env STEAM_COMPAT_CLIENT_INSTALL_PATH="{steam_root}" STEAM_COMPAT_DATA_PATH="{steam_compat_data_path}" "{proton_path}" run "{mo2_exe}" &
    # Wait a moment for MO2 to start
    sleep 3
    # Then send the NXM link
    env STEAM_COMPAT_CLIENT_INSTALL_PATH="{steam_root}" STEAM_COMPAT_DATA_PATH="{steam_compat_data_path}" "{proton_path}" run "{nxm_handler_path}" "$NXM_LINK"
fi
'''
            
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
    
    def _register_mime_handler(self, desktop_file_name: str) -> Dict[str, Any]:
        """Register NXM MIME handler with proper Firefox support"""
        try:
            home_dir = os.path.expanduser("~")
            
            # Step 1: Create proper MIME type file
            self._create_nxm_mime_type()
            
            # Step 2: Try xdg-mime first
            result = subprocess.run(["xdg-mime", "default", desktop_file_name, "x-scheme-handler/nxm"], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                self.logger.info("MIME handler registered via xdg-mime")
            else:
                self.logger.warning(f"xdg-mime failed: {result.stderr}")
            
            # Step 3: Manually edit mimeapps.list with proper format
            self._update_mimeapps_list(desktop_file_name)
            
            # Step 4: Update desktop database
            applications_dir = os.path.join(home_dir, ".local", "share", "applications")
            update_cmd = subprocess.run(["update-desktop-database", applications_dir], 
                                     capture_output=True, text=True, check=False)
            
            if update_cmd.returncode == 0:
                self.logger.info("Desktop database updated successfully")
            else:
                self.logger.warning(f"Failed to update desktop database: {update_cmd.stderr}")
            
            # Step 5: Update MIME database
            mime_dir = os.path.join(home_dir, ".local", "share", "mime")
            mime_cmd = subprocess.run(["update-mime-database", mime_dir], 
                                    capture_output=True, text=True, check=False)
            
            if mime_cmd.returncode == 0:
                self.logger.info("MIME database updated successfully")
            else:
                self.logger.warning(f"Failed to update MIME database: {mime_cmd.stderr}")
            
            # Step 6: Try to register with gio (for newer systems)
            gio_cmd = subprocess.run(["gio", "mime", "x-scheme-handler/nxm", desktop_file_name], 
                                   capture_output=True, text=True, check=False)
            
            if gio_cmd.returncode == 0:
                self.logger.info("MIME handler registered via gio")
            else:
                self.logger.info(f"gio registration failed (this is normal on older systems): {gio_cmd.stderr}")
            
            # Step 7: Register with Firefox specifically
            self._register_firefox_handler(desktop_file_name)
            
            self.logger.info("NXM handler registration completed - you may need to restart Firefox for it to take effect")
            return {"success": True}
            
        except Exception as e:
            self.logger.error(f"Failed to register MIME handler: {e}")
            return {"success": False, "error": str(e)}
    
    def _create_nxm_mime_type(self):
        """Create proper MIME type definition for NXM"""
        try:
            home_dir = os.path.expanduser("~")
            mime_packages_dir = os.path.join(home_dir, ".local", "share", "mime", "packages")
            os.makedirs(mime_packages_dir, exist_ok=True)
            
            mime_xml_path = os.path.join(mime_packages_dir, "application-x-nxm.xml")
            
            mime_xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="x-scheme-handler/nxm">
    <comment>NXM Protocol</comment>
    <comment xml:lang="en">NXM Protocol</comment>
    <generic-icon name="application-x-executable"/>
    <glob pattern="nxm:*"/>
  </mime-type>
</mime-info>'''
            
            with open(mime_xml_path, 'w') as f:
                f.write(mime_xml_content)
            
            self.logger.info(f"Created MIME type definition: {mime_xml_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to create MIME type definition: {e}")
    
    def _update_mimeapps_list(self, desktop_file_name: str):
        """Update mimeapps.list with proper format"""
        try:
            home_dir = os.path.expanduser("~")
            mimeapps_path = os.path.join(home_dir, ".config", "mimeapps.list")
            
            # Create .config directory if needed
            os.makedirs(os.path.dirname(mimeapps_path), exist_ok=True)
            
            # Read existing content or create new
            content = ""
            if os.path.exists(mimeapps_path):
                with open(mimeapps_path, 'r') as f:
                    content = f.read()
            
            # Parse existing content
            lines = content.split('\n') if content else []
            
            # Find or create [Default Applications] section
            default_section_found = False
            new_lines = []
            nxm_line_added = False
            
            for line in lines:
                if line.strip() == "[Default Applications]":
                    default_section_found = True
                    new_lines.append(line)
                elif line.strip().startswith("[") and default_section_found and not nxm_line_added:
                    # We're entering a new section, add our line before it
                    new_lines.append(f"x-scheme-handler/nxm={desktop_file_name}")
                    nxm_line_added = True
                    new_lines.append(line)
                elif "x-scheme-handler/nxm" in line:
                    # Remove existing NXM handler entries
                    continue
                else:
                    new_lines.append(line)
            
            # If no [Default Applications] section found, create it
            if not default_section_found:
                if new_lines and new_lines[-1].strip():
                    new_lines.append("")  # Add blank line
                new_lines.append("[Default Applications]")
                new_lines.append(f"x-scheme-handler/nxm={desktop_file_name}")
                nxm_line_added = True
            elif not nxm_line_added:
                # Add at the end of the Default Applications section
                new_lines.append(f"x-scheme-handler/nxm={desktop_file_name}")
            
            # Write back to file
            new_content = '\n'.join(new_lines)
            with open(mimeapps_path, 'w') as f:
                f.write(new_content)
            
            self.logger.info(f"Updated mimeapps.list: {mimeapps_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to update mimeapps.list: {e}")
    
    def _register_firefox_handler(self, desktop_file_name: str):
        """Register NXM handler with Firefox specifically"""
        try:
            import json
            import glob
            
            home_dir = os.path.expanduser("~")
            firefox_profiles = glob.glob(os.path.join(home_dir, ".mozilla", "firefox", "*.default*"))
            
            if not firefox_profiles:
                self.logger.info("No Firefox profiles found - Firefox registration skipped")
                return
            
            for profile_path in firefox_profiles:
                handlers_json_path = os.path.join(profile_path, "handlers.json")
                
                try:
                    # Read existing handlers
                    handlers_data = {}
                    if os.path.exists(handlers_json_path):
                        with open(handlers_json_path, 'r') as f:
                            handlers_data = json.load(f)
                    
                    # Ensure required structure exists
                    if "schemes" not in handlers_data:
                        handlers_data["schemes"] = {}
                    
                    # Update NXM handler to use our application
                    handlers_data["schemes"]["nxm"] = {
                        "action": 2,  # Use application
                        "handlers": [{
                            "name": "Mod Organizer 2 NXM Handler",
                            "path": os.path.join(home_dir, ".local", "share", "applications", desktop_file_name)
                        }]
                    }
                    
                    # Write back to file
                    with open(handlers_json_path, 'w') as f:
                        json.dump(handlers_data, f, separators=(',', ':'))
                    
                    self.logger.info(f"Updated Firefox handlers: {handlers_json_path}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to update Firefox profile {profile_path}: {e}")
            
        except Exception as e:
            self.logger.warning(f"Failed to register Firefox handler: {e}")

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
