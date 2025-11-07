"""
Dependency Cache Manager
Handles downloading and caching dependency files for reuse across installations
"""

import os
import json
import hashlib
import requests
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import tempfile
import shutil
import sys
import os

from src.utils.logger import get_logger


class DependencyCacheManager:
    """Manages dependency file caching for faster installations"""
    
    def __init__(self):
        # Set up cache directory structure first
        self.cache_base = Path.home() / "NaK"
        self.cache_dir = self.cache_base / "cache"
        self.logs_dir = self.cache_base / "logs"
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        
        # Create directories if they don't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize logger after logs directory is created
        self.logger = get_logger(__name__)
        
        # Load cache metadata
        self.metadata = self._load_metadata()
        
        # Progress callback
        self.progress_callback: Optional[Callable] = None
        
        # Define all dependency URLs and their metadata
        self.dependency_urls = {
            # DirectX June 2010 (for xact, xact_x64, d3dx11_43, d3dcompiler_43, d3dx9_43, d3dx9)
            "directx_jun2010": {
                "url": "https://pub-1497a260bc754de2a75301ffe6a64244.r2.dev/directx9/directx_Jun2010_redist.exe",
                "filename": "directx_Jun2010_redist.exe",
                "sha256": "8746ee1a84a083a90e37899d71d50d5c7c015e69688a466aa80447f011780c0d",
                "dependencies": ["xact", "xact_x64", "d3dx11_43", "d3dcompiler_43", "d3dx9_43", "d3dx9"],
                "description": "DirectX June 2010 Redistributable"
            },
            
            # D3D Compiler 43 (extracted from DirectX June 2010)
            "d3dcompiler_43": {
                "url": None,  # Extracted from directx_jun2010
                "filename": "d3dcompiler_43.dll",
                "sha256": None,  # Will be calculated after extraction
                "dependencies": ["d3dcompiler_43"],
                "description": "D3D Compiler 43 (extracted from DirectX June 2010)",
                "source": "directx_jun2010"
            },
            
            # Visual C++ 2022 Redistributable
            "vcrun2022_x86": {
                "url": "https://aka.ms/vs/17/release/vc_redist.x86.exe",
                "filename": "vc_redist.x86.exe",
                "sha256": "0c09f2611660441084ce0df425c51c11e147e6447963c3690f97e0b25c55ed64",
                "dependencies": ["vcrun2022"],
                "description": "Visual C++ 2022 Redistributable (x86)"
            },
            "vcrun2022_x64": {
                "url": "https://aka.ms/vs/17/release/vc_redist.x64.exe",
                "filename": "vc_redist.x64.exe",
                "sha256": None,  # Will be calculated after download
                "dependencies": ["vcrun2022"],
                "description": "Visual C++ 2022 Redistributable (x64)"
            },

            # .NET Framework 4.0 (required before 4.8)
            "dotnet40": {
                "url": "https://download.microsoft.com/download/9/5/A/95A9616B-7A37-4AF6-BC36-D6EA96C8DAAE/dotNetFx40_Full_x86_x64.exe",
                "filename": "dotNetFx40_Full_x86_x64.exe",
                "sha256": "65e064258f2e418816b304f646ff9e87af101e4c9552ab064bb74d281c38659f",
                "dependencies": ["dotnet40"],
                "description": ".NET Framework 4.0 (Offline Installer)",
                "install_args": ["/q", "/c:install.exe /q"]  # Winetricks-style install flags
            },

            # .NET Framework 4.8
            "dotnet48": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/7afca223-55d2-470a-8edc-6a1739ae3252/abd170b4b0ec15ad0222a809b761a036/ndp48-x86-x64-allos-enu.exe",
                "filename": "ndp48-x86-x64-allos-enu.exe",
                "sha256": "95889d6de3f2070c07790ad6cf2000d33d9a1bdfc6a381725ab82ab1c314fd53",
                "dependencies": ["dotnet48"],
                "description": ".NET Framework 4.8 (Offline Installer)",
                "install_args": ["/sfxlang:1027", "/q", "/norestart"]  # Silent install flags from winetricks
            },

            # .NET 6 Runtime
            "dotnet6_x86": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/727d79cb-6a4c-4a6b-bd9e-af99ad62de0b/5cd3550f1589a2f1b3a240c745dd1023/dotnet-runtime-6.0.36-win-x86.exe",
                "filename": "dotnet-runtime-6.0.36-win-x86.exe",
                "sha256": "3b3cb4636251a582158f4b6b340f20b3861e6793eb9a3e64bda29cbf32da3604",
                "dependencies": ["dotnet6"],
                "description": ".NET 6 Runtime (x86)"
            },
            "dotnet6_x64": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/1a5fc50a-9222-4f33-8f73-3c78485a55c7/1cb55899b68fcb9d98d206ba56f28b66/dotnet-runtime-6.0.36-win-x64.exe",
                "filename": "dotnet-runtime-6.0.36-win-x64.exe",
                "sha256": "6bdad7bc4c41fe93d4ae7b0312b1d017cfe369d28e7e2e421f5b675f9feefe84",
                "dependencies": ["dotnet6"],
                "description": ".NET 6 Runtime (x64)"
            },
            
            # .NET 7 Runtime
            "dotnet7_x86": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/b2e820bd-b591-43df-ab10-1eeb7998cc18/661ca79db4934c6247f5c7a809a62238/dotnet-runtime-7.0.20-win-x86.exe",
                "filename": "dotnet-runtime-7.0.20-win-x86.exe",
                "sha256": None,  # Will be calculated after download
                "dependencies": ["dotnet7"],
                "description": ".NET 7 Runtime (x86)"
            },
            "dotnet7_x64": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/be7eaed0-4e32-472b-b53e-b08ac3433a22/fc99a5977c57cbfb93b4afb401953818/dotnet-runtime-7.0.20-win-x64.exe",
                "filename": "dotnet-runtime-7.0.20-win-x64.exe",
                "sha256": None,  # Will be calculated after download
                "dependencies": ["dotnet7"],
                "description": ".NET 7 Runtime (x64)"
            },
            
            # .NET 8 Runtime
            "dotnet8_x86": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/3210417e-ab32-4d14-a152-1ad9a2fcfdd2/da097cee5aa85bd79b6d593e3866fb7f/dotnet-runtime-8.0.12-win-x86.exe",
                "filename": "dotnet-runtime-8.0.12-win-x86.exe",
                "sha256": None,  # Will be calculated after download
                "dependencies": ["dotnet8"],
                "description": ".NET 8 Runtime (x86)"
            },
            "dotnet8_x64": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/136f4593-e3cd-4d52-bc25-579cdf46e80c/8b98c1347293b48c56c3a68d72f586a1/dotnet-runtime-8.0.12-win-x64.exe",
                "filename": "dotnet-runtime-8.0.12-win-x64.exe",
                "sha256": None,  # Will be calculated after download
                "dependencies": ["dotnet8"],
                "description": ".NET 8 Runtime (x64)"
            },

            # .NET 9 Desktop Runtime
            "dotnet9_x86": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/bf9b9997-99c2-47bb-abf7-3dae8856f78c/ef6ea2a61eff5e6a6f6b80f3e43c06d0/windowsdesktop-runtime-9.0.10-win-x86.exe",
                "filename": "windowsdesktop-runtime-9.0.10-win-x86.exe",
                "sha256": None,  # Will be calculated after download
                "dependencies": ["dotnet9"],
                "description": ".NET 9 Desktop Runtime (x86)"
            },
            "dotnet9_x64": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/ffa03262-db6e-4ee8-bc1f-d8cfa1e4dc99/6d75047b61ef1d10b9d1c0d52ef01d54/windowsdesktop-runtime-9.0.10-win-x64.exe",
                "filename": "windowsdesktop-runtime-9.0.10-win-x64.exe",
                "sha256": None,  # Will be calculated after download
                "dependencies": ["dotnet9"],
                "description": ".NET 9 Desktop Runtime (x64)"
            },

            # .NET Desktop 6 Runtime
            "dotnetdesktop6_x86": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/cdc314df-4a4c-4709-868d-b974f336f77f/acd5ab7637e456c8a3aa667661324f6d/windowsdesktop-runtime-6.0.36-win-x86.exe",
                "filename": "windowsdesktop-runtime-6.0.36-win-x86.exe",
                "sha256": None,  # Will be calculated after download
                "dependencies": ["dotnetdesktop6"],
                "description": ".NET Desktop 6 Runtime (x86)"
            },
            "dotnetdesktop6_x64": {
                "url": "https://download.visualstudio.microsoft.com/download/pr/f6b6c5dc-e02d-4738-9559-296e938dabcb/b66d365729359df8e8ea131197715076/windowsdesktop-runtime-6.0.36-win-x64.exe",
                "filename": "windowsdesktop-runtime-6.0.36-win-x64.exe",
                "sha256": None,  # Will be calculated after download
                "dependencies": ["dotnetdesktop6"],
                "description": ".NET Desktop 6 Runtime (x64)"
            },
            
            # D3D Compiler 47
            "d3dcompiler_47_x86": {
                "url": "https://raw.githubusercontent.com/mozilla/fxc2/master/dll/d3dcompiler_47_32.dll",
                "filename": "d3dcompiler_47_32.dll",
                "sha256": "2ad0d4987fc4624566b190e747c9d95038443956ed816abfd1e2d389b5ec0851",
                "dependencies": ["d3dcompiler_47"],
                "description": "D3D Compiler 47 (x86)"
            },
            "d3dcompiler_47_x64": {
                "url": "https://raw.githubusercontent.com/mozilla/fxc2/master/dll/d3dcompiler_47.dll",
                "filename": "d3dcompiler_47.dll",
                "sha256": "4432bbd1a390874f3f0a503d45cc48d346abc3a8c0213c289f4b615bf0ee84f3",
                "dependencies": ["d3dcompiler_47"],
                "description": "D3D Compiler 47 (x64)"
            },
            
            # VKD3D (dynamic version)
            "vkd3d": {
                "url": None,  # Will be resolved dynamically
                "filename": None,  # Will be resolved dynamically
                "sha256": None,  # Will be calculated after download
                "dependencies": ["vkd3d"],
                "description": "VKD3D Proton (latest version)"
            }

            # NOTE: dotnet9_sdk removed - not needed for mod managers
            # .NET 9 SDK is for development, not runtime dependencies
        }
        
        self.logger.info(f"Dependency cache manager initialized")
        self.logger.info(f"Cache directory: {self.cache_dir}")
        self.logger.info(f"Logs directory: {self.logs_dir}")
    
    def set_progress_callback(self, callback: Callable):
        """Set progress callback for download updates"""
        self.progress_callback = callback
    
    def _get_bundled_cabextract(self) -> str:
        """Get the bundled cabextract command path"""
        # Check if we're running in PyInstaller
        if getattr(sys, 'frozen', False):
            bundled_cabextract = os.path.join(sys._MEIPASS, "cabextract")
            if os.path.exists(bundled_cabextract):
                return bundled_cabextract
        
        # Check if we're running in AppImage
        appdir = os.environ.get('APPDIR')
        if appdir:
            bundled_cabextract = os.path.join(appdir, "usr", "bin", "cabextract")
            if os.path.exists(bundled_cabextract):
                return bundled_cabextract
        
        # Fallback to system cabextract
        return "cabextract"
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata from file"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load cache metadata: {e}")
        
        return {
            "files": {},
            "last_updated": None,
            "cache_version": "1.0"
        }
    
    def _save_metadata(self):
        """Save cache metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save cache metadata: {e}")
    
    def _get_winetricks_verb(self, dependency_name: str) -> str:
        """Map our cache keys to winetricks verb names

        Maps cache keys like "dotnet48" -> "dotnet48"
        Maps cache keys like "vcrun2022_x64" -> "vcrun2022"
        Maps cache keys like "directx_jun2010" -> "directx9"
        """
        # Mapping of our cache keys to winetricks verbs
        verb_mapping = {
            "directx_jun2010": "directx9",
            "d3dcompiler_43": "directx9",
            "vcrun2022_x86": "vcrun2022",
            "vcrun2022_x64": "vcrun2022",
            "dotnet6_x86": "dotnet6",
            "dotnet6_x64": "dotnet6",
            "dotnet7_x86": "dotnet7",
            "dotnet7_x64": "dotnet7",
            "dotnet8_x86": "dotnet8",
            "dotnet8_x64": "dotnet8",
            "dotnet9_x86": "dotnet9",
            "dotnet9_x64": "dotnet9",
            "dotnetdesktop6_x86": "dotnetdesktop6",
            "dotnetdesktop6_x64": "dotnetdesktop6",
            "d3dcompiler_47_x86": "d3dcompiler_47",
            "d3dcompiler_47_x64": "d3dcompiler_47",
        }

        # Return mapped verb or use the dependency_name as-is
        return verb_mapping.get(dependency_name, dependency_name)

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _download_file(self, url: str, file_path: Path, expected_sha256: Optional[str] = None) -> bool:
        """Download a file with progress tracking and verification"""
        try:
            # Check if file already exists and is valid
            if file_path.exists() and file_path.stat().st_size > 0:
                if expected_sha256:
                    actual_sha256 = self._calculate_sha256(file_path)
                    if actual_sha256.lower() == expected_sha256.lower():
                        self.logger.info(f"File already exists and verified: {file_path}")
                        return True
                    else:
                        self.logger.warning(f"Existing file has wrong checksum, re-downloading: {file_path}")
                        file_path.unlink()
                else:
                    # No checksum to verify, assume file is good
                    self.logger.info(f"File already exists: {file_path}")
                    return True

            self.logger.info(f"Downloading {url} to {file_path}")

            # Create parent directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Use wget for R2 URLs (faster and more reliable)
            if "r2.dev" in url:
                import subprocess
                result = subprocess.run(
                    ["wget", "-q", "--show-progress", "-O", str(file_path), url],
                    capture_output=False,
                    timeout=300
                )
                if result.returncode != 0:
                    self.logger.error(f"wget failed to download {url}")
                    if file_path.exists():
                        file_path.unlink()
                    return False
            else:
                # Use requests for other URLs
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            # Update progress
                            if total_size > 0 and self.progress_callback:
                                percent = (downloaded / total_size) * 100
                                self.progress_callback(percent, downloaded, total_size)

            # Verify file integrity if SHA256 provided
            if expected_sha256:
                actual_sha256 = self._calculate_sha256(file_path)
                if actual_sha256.lower() != expected_sha256.lower():
                    self.logger.error(f"SHA256 mismatch for {file_path}")
                    self.logger.error(f"Expected: {expected_sha256}")
                    self.logger.error(f"Actual: {actual_sha256}")
                    file_path.unlink()  # Delete corrupted file
                    return False

            self.logger.info(f"Successfully downloaded {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to download {url}: {e}")
            if file_path.exists():
                file_path.unlink()  # Clean up partial download
            return False
    
    def _get_vkd3d_latest_url(self) -> tuple[Optional[str], Optional[str]]:
        """Get the latest VKD3D download URL and filename"""
        try:
            # Get latest release info from GitHub API
            api_url = "https://api.github.com/repos/HansKristian-Work/vkd3d-proton/releases/latest"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            version = release_data["tag_name"]
            
            # Find the tar.zst asset
            for asset in release_data["assets"]:
                if asset["name"].endswith(".tar.zst"):
                    download_url = asset["browser_download_url"]
                    filename = asset["name"]
                    return download_url, filename
            
            return None, None
            
        except Exception as e:
            self.logger.error(f"Failed to get VKD3D latest version: {e}")
            return None, None
    
    def _resolve_aka_ms_url(self, url: str) -> str:
        """Resolve aka.ms redirect URLs to get the final download URL"""
        try:
            response = requests.head(url, allow_redirects=True, timeout=10)
            return response.url
        except Exception as e:
            self.logger.warning(f"Failed to resolve aka.ms URL {url}: {e}")
            return url
    
    def get_cached_file(self, dependency_name: str) -> Optional[Path]:
        """Get the cached file path for a dependency if it exists and is valid

        Files are stored in winetricks-compatible subdirectory structure:
        cache/dotnet48/ndp48-x86-x64-allos-enu.exe
        """
        if dependency_name not in self.metadata["files"]:
            return None

        file_info = self.metadata["files"][dependency_name]

        # Get the winetricks verb name for this dependency
        winetricks_verb = self._get_winetricks_verb(dependency_name)

        # Use subdirectory structure: cache/verb_name/filename
        file_path = self.cache_dir / winetricks_verb / file_info["filename"]

        # Check if file exists and is not corrupted
        if not file_path.exists():
            self.logger.warning(f"Cached file {file_path} does not exist")
            # Remove from metadata if file doesn't exist
            if dependency_name in self.metadata["files"]:
                del self.metadata["files"][dependency_name]
                self._save_metadata()
            return None
        
        # Verify file size (basic integrity check)
        if file_path.stat().st_size == 0:
            self.logger.warning(f"Cached file {file_path} is empty")
            return None
        
        # Verify SHA256 if available
        if file_info.get("sha256"):
            actual_sha256 = self._calculate_sha256(file_path)
            if actual_sha256.lower() != file_info["sha256"].lower():
                self.logger.warning(f"Cached file {file_path} has invalid SHA256")
                self.logger.debug(f"Expected: {file_info['sha256']}, Got: {actual_sha256}")
                return None
        
        self.logger.info(f"Using cached file: {file_path}")
        return file_path
    
    def cache_dependency(self, dependency_name: str, force_download: bool = False) -> Optional[Path]:
        """Cache a dependency file, downloading if necessary"""
        if dependency_name not in self.dependency_urls:
            self.logger.error(f"Unknown dependency: {dependency_name}")
            return None
        
        # Check if already cached and valid
        if not force_download:
            cached_file = self.get_cached_file(dependency_name)
            if cached_file:
                return cached_file
        
        dep_info = self.dependency_urls[dependency_name]
        
        # Handle special cases
        if dependency_name == "vkd3d":
            url, filename = self._get_vkd3d_latest_url()
            if not url or not filename:
                self.logger.error("Failed to get VKD3D download URL")
                return None
            dep_info = dep_info.copy()
            dep_info["url"] = url
            dep_info["filename"] = filename
        
        # Handle dependencies that are extracted from other files
        if dep_info.get("source"):
            source_dep = dep_info["source"]
            self.logger.info(f"Extracting {dependency_name} from {source_dep}")
            
            # First ensure the source dependency is cached
            source_file = self.cache_dependency(source_dep, force_download)
            if not source_file:
                self.logger.error(f"Failed to cache source dependency: {source_dep}")
                return None
            
            # Extract the specific file
            extracted_file = self._extract_file_from_source(source_file, dependency_name, dep_info)
            if extracted_file:
                # Update metadata
                actual_sha256 = self._calculate_sha256(extracted_file)
                self.metadata["files"][dependency_name] = {
                    "filename": dep_info["filename"],
                    "url": f"extracted_from_{source_dep}",
                    "sha256": actual_sha256,
                    "downloaded_at": datetime.now().isoformat(),
                    "description": dep_info["description"]
                }
                self.metadata["last_updated"] = datetime.now().isoformat()
                self._save_metadata()
                
                return extracted_file
            else:
                self.logger.error(f"Failed to extract {dependency_name} from {source_dep}")
                return None
        
        # Resolve aka.ms URLs
        if dep_info["url"] and dep_info["url"].startswith("https://aka.ms/"):
            resolved_url = self._resolve_aka_ms_url(dep_info["url"])
            if resolved_url != dep_info["url"]:
                self.logger.info(f"Resolved aka.ms URL: {resolved_url}")
                dep_info = dep_info.copy()
                dep_info["url"] = resolved_url

        # Get winetricks verb name for subdirectory structure
        winetricks_verb = self._get_winetricks_verb(dependency_name)

        # Create subdirectory for this dependency (winetricks expects this)
        dep_subdir = self.cache_dir / winetricks_verb
        dep_subdir.mkdir(parents=True, exist_ok=True)

        # Save file in subdirectory: cache/verb_name/filename
        file_path = dep_subdir / dep_info["filename"]

        # Download the file
        if self._download_file(dep_info["url"], file_path, dep_info.get("sha256")):
            # Calculate actual SHA256
            actual_sha256 = self._calculate_sha256(file_path)
            
            # Update metadata
            self.metadata["files"][dependency_name] = {
                "filename": dep_info["filename"],
                "url": dep_info["url"],
                "sha256": actual_sha256,
                "downloaded_at": datetime.now().isoformat(),
                "description": dep_info["description"]
            }
            self.metadata["last_updated"] = datetime.now().isoformat()
            self._save_metadata()
            
            return file_path
        
        return None
    
    def _extract_file_from_source(self, source_file: Path, dependency_name: str, dep_info: Dict[str, Any]) -> Optional[Path]:
        """Extract a specific file from a source dependency"""
        try:
            import tempfile
            import subprocess
            
            # Create temporary directory for extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Use cabextract to extract the specific file
                if dependency_name == "d3dcompiler_43":
                    # Extract d3dcompiler_43.dll from DirectX June 2010
                    cmd = [
                        self._get_bundled_cabextract(), "-d", str(temp_path), "-L", "-F", "*d3dcompiler_43*x86*", 
                        str(source_file)
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode != 0:
                        self.logger.error(f"Failed to extract d3dcompiler_43 from DirectX: {result.stderr}")
                        return None
                    
                    # Find extracted CAB files
                    cab_files = list(temp_path.glob("*.cab"))
                    if not cab_files:
                        self.logger.error("No CAB files found after extraction")
                        return None
                    
                    # Create directx9 subdirectory for extraction
                    directx9_dir = self.cache_dir / "directx9"
                    directx9_dir.mkdir(parents=True, exist_ok=True)

                    # Extract d3dcompiler_43.dll from CAB files to directx9 subdirectory
                    for cab_file in cab_files:
                        extract_cmd = [
                            self._get_bundled_cabextract(), "-d", str(directx9_dir), "-L", "-F", "d3dcompiler_43.dll",
                            str(cab_file)
                        ]
                        
                        extract_result = subprocess.run(extract_cmd, capture_output=True, text=True, timeout=30)
                        if extract_result.returncode == 0:
                            # d3dcompiler_43 goes in directx9 subdirectory
                            extracted_file = self.cache_dir / "directx9" / "d3dcompiler_43.dll"
                            if extracted_file.exists():
                                self.logger.info(f"Extracted d3dcompiler_43.dll to {extracted_file}")
                                return extracted_file
                    
                    self.logger.error("Failed to extract d3dcompiler_43.dll from any CAB file")
                    return None
                
                else:
                    self.logger.error(f"Unknown extraction method for {dependency_name}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Failed to extract {dependency_name} from source: {e}")
            return None
    
    def _download_r2_bulk_cache(self) -> bool:
        """
        Download and extract the bulk dependency archive from Cloudflare R2.
        This is much faster than downloading individual files.

        Returns:
            True if successful, False otherwise
        """
        try:
            import subprocess

            r2_url = "https://pub-1497a260bc754de2a75301ffe6a64244.r2.dev/nak_dependencies.7z"
            archive_path = self.cache_dir / "nak_dependencies.7z"

            self.logger.info("=" * 70)
            self.logger.info("ATTEMPTING FAST BULK DOWNLOAD FROM CLOUDFLARE R2")
            self.logger.info("=" * 70)
            self.logger.info(f"Downloading: {r2_url}")
            self.logger.info("This downloads ALL dependencies at once (610 MB)")

            if self.progress_callback:
                self.progress_callback("Downloading dependencies from R2 (fast)...")

            # Download the archive
            self.logger.info("Downloading archive...")
            download_result = subprocess.run(
                ["wget", "-O", str(archive_path), r2_url, "--progress=bar:force"],
                capture_output=False,  # Show progress
                timeout=300  # 5 minutes timeout
            )

            if download_result.returncode != 0:
                self.logger.warning("R2 download failed, will fall back to individual downloads")
                if archive_path.exists():
                    archive_path.unlink()
                return False

            if not archive_path.exists():
                self.logger.error("Archive download failed - file not found")
                return False

            self.logger.info(f"[OK] Downloaded {archive_path.stat().st_size / (1024*1024):.1f} MB")

            # Extract the archive
            if self.progress_callback:
                self.progress_callback("Extracting dependencies...")

            self.logger.info("Extracting archive to cache directory...")
            extract_result = subprocess.run(
                ["7z", "x", str(archive_path), f"-o{self.cache_dir}", "-y"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if extract_result.returncode != 0:
                self.logger.error(f"Failed to extract archive: {extract_result.stderr}")
                archive_path.unlink()
                return False

            self.logger.info("[OK] Successfully extracted all dependencies from R2 archive")

            # Clean up archive file
            archive_path.unlink()
            self.logger.info("Cleaned up archive file")

            # Verify extraction worked by checking a few key files
            test_files = [
                self.cache_dir / "directx9" / "directx_Jun2010_redist.exe",
                self.cache_dir / "dotnet48" / "ndp48-x86-x64-allos-enu.exe",
                self.cache_dir / "vcrun2022" / "vc_redist.x64.exe"
            ]

            for test_file in test_files:
                if not test_file.exists():
                    self.logger.error(f"Extraction verification failed - {test_file} not found")
                    return False

            self.logger.info("=" * 70)
            self.logger.info("R2 BULK DOWNLOAD SUCCESSFUL!")
            self.logger.info("All dependencies cached in seconds instead of minutes!")
            self.logger.info("=" * 70)

            return True

        except subprocess.TimeoutExpired:
            self.logger.warning("R2 download timed out, falling back to individual downloads")
            if archive_path.exists():
                archive_path.unlink()
            return False
        except Exception as e:
            self.logger.warning(f"R2 bulk download failed: {e}")
            if 'archive_path' in locals() and archive_path.exists():
                archive_path.unlink()
            return False

    def cache_all_dependencies(self, force_download: bool = False) -> Dict[str, bool]:
        """Cache all dependencies - tries R2 bulk download first for speed"""
        results = {}

        total_deps = len(self.dependency_urls)
        current_index = 0

        self.logger.info(f"Caching {total_deps} dependencies...")

        # Cache all dependencies
        for i, (dep_name, dep_info) in enumerate(self.dependency_urls.items()):
            # Skip if already cached from R2
            if dep_name in results and results[dep_name]:
                current_index += 1
                continue

            self.logger.info(f"Caching {dep_name} ({current_index+1}/{total_deps})")

            if self.progress_callback:
                self.progress_callback((current_index / total_deps) * 100, current_index, total_deps)

            cached_file = self.cache_dependency(dep_name, force_download)
            results[dep_name] = cached_file is not None

            if cached_file:
                self.logger.info(f"[OK] Cached {dep_name}")
            else:
                self.logger.error(f"[FAILED] Failed to cache {dep_name}")

            current_index += 1

        if self.progress_callback:
            self.progress_callback(100, total_deps, total_deps)

        return results
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get status of all cached dependencies"""
        total_deps = len(self.dependency_urls)

        status = {
            "cache_dir": str(self.cache_dir),
            "total_dependencies": total_deps,
            "cached_dependencies": 0,
            "cache_size_mb": 0,
            "last_updated": self.metadata.get("last_updated"),
            "dependencies": {}
        }

        total_size = 0
        for dep_name, dep_info in self.dependency_urls.items():
            cached_file = self.get_cached_file(dep_name)
            is_cached = cached_file is not None

            if is_cached:
                status["cached_dependencies"] += 1
                file_size = cached_file.stat().st_size
                total_size += file_size

                status["dependencies"][dep_name] = {
                    "cached": True,
                    "filename": dep_info["filename"],
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "description": dep_info["description"]
                }
            else:
                status["dependencies"][dep_name] = {
                    "cached": False,
                    "filename": dep_info["filename"],
                    "description": dep_info["description"]
                }

        status["cache_size_mb"] = round(total_size / (1024 * 1024), 2)
        return status

    def clean_winetricks_temp_folders(self) -> Dict[str, Any]:
        """Clean up temporary winetricks extraction folders to save disk space

        NOTE: With winetricks subdirectory structure, cache folders are now PERMANENT.
        Winetricks extracts temp files to $WINEPREFIX/drive_c/windows/temp/, not cache.
        This function now does nothing to avoid deleting our permanent cache.
        """
        try:
            # DISABLED: These are now permanent cache subdirectories, NOT temp folders!
            # Old behavior: Deleted cache/dotnet48/ etc thinking they were temp extraction folders
            # New behavior: cache/dotnet48/file.exe is our PERMANENT cache structure
            # Winetricks temp files are in the wine prefix, not in our cache directory

            self.logger.info("Temp folder cleanup disabled - cache subdirectories are permanent storage")

            return {
                "success": True,
                "cleaned_folders": [],
                "space_freed_mb": 0,
                "message": "Temp folder cleanup disabled - subdirectories are now permanent cache"
            }

        except Exception as e:
            self.logger.error(f"Failed to clean temp folders: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def clear_cache(self) -> bool:
        """Clear all cached files"""
        try:
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            self.metadata = {
                "files": {},
                "last_updated": None,
                "cache_version": "1.0"
            }
            self._save_metadata()
            
            self.logger.info("Cache cleared successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            return False
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """Remove cached files older than specified days"""
        if not self.metadata.get("last_updated"):
            return 0
        
        last_updated = datetime.fromisoformat(self.metadata["last_updated"])
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        if last_updated > cutoff_date:
            return 0  # Cache is still fresh
        
        # Clear entire cache if it's old
        return 1 if self.clear_cache() else 0
