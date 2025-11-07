"""
.NET 9 SDK Installer
Downloads and installs .NET 9 SDK via Wine for Synthesis patcher support
"""

import os
import subprocess
import requests
from pathlib import Path
from typing import Optional
from src.utils.logger import get_logger


class DotNet9SDKInstaller:
    """Handles .NET 9 SDK installation via Wine"""

    # Official Microsoft .NET 9 SDK download URL (direct download from builds.dotnet.microsoft.com)
    DOTNET9_SDK_URL = "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.306/dotnet-sdk-9.0.306-win-x64.exe"

    def __init__(self):
        self.logger = get_logger(__name__)
        self.cache_dir = Path.home() / "NaK" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_dotnet9_sdk(self, progress_callback=None) -> Optional[Path]:
        """
        Download .NET 9 SDK installer

        Args:
            progress_callback: Optional callback(percent, downloaded_mb, total_mb)

        Returns:
            Path to downloaded installer, or None on failure
        """
        try:
            installer_path = self.cache_dir / "dotnet-sdk-9.0.306-win-x64.exe"

            # Check if already downloaded
            if installer_path.exists():
                self.logger.info(f".NET 9 SDK installer already cached at {installer_path}")
                return installer_path

            self.logger.info("Downloading .NET 9 SDK installer...")
            self.logger.info(f"URL: {self.DOTNET9_SDK_URL}")

            # Download with progress
            response = requests.get(self.DOTNET9_SDK_URL, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(installer_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1048576):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            progress_callback(percent, downloaded_mb, total_mb)

            self.logger.info(f".NET 9 SDK installer downloaded: {installer_path}")
            return installer_path

        except Exception as e:
            self.logger.error(f"Failed to download .NET 9 SDK installer: {e}")
            return None

    def install_dotnet9_sdk(
        self,
        prefix_path: Path,
        wine_path: Path,
        progress_callback=None
    ) -> bool:
        """
        Install .NET 9 SDK into a Wine prefix

        Args:
            prefix_path: Path to Wine prefix
            wine_path: Path to Wine binary
            progress_callback: Optional callback(percent, downloaded_mb, total_mb)

        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info("Installing .NET 9 SDK...")

            # Download installer
            installer_path = self.download_dotnet9_sdk(progress_callback)
            if not installer_path:
                return False

            # Verify prefix exists
            if not prefix_path.exists():
                self.logger.error(f"Wine prefix not found: {prefix_path}")
                return False

            # Verify wine binary exists
            if not wine_path.exists():
                self.logger.error(f"Wine binary not found: {wine_path}")
                return False

            self.logger.info(f"Installing .NET 9 SDK to prefix: {prefix_path}")

            # Set up environment
            env = os.environ.copy()
            env["WINEPREFIX"] = str(prefix_path)

            # CRITICAL: Reset LD_LIBRARY_PATH to system-only paths
            env["LD_LIBRARY_PATH"] = "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu"

            # Run installer with quiet/silent flags
            # /install = install mode
            # /quiet = quiet mode (no UI)
            # /norestart = don't restart after installation
            install_cmd = [
                str(wine_path),
                str(installer_path),
                "/install",
                "/quiet",
                "/norestart"
            ]

            self.logger.info(f"Running: {' '.join(install_cmd)}")

            result = subprocess.run(
                install_cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout for installation
            )

            if result.returncode == 0:
                self.logger.info("[OK] .NET 9 SDK installed successfully")
                return True
            else:
                self.logger.warning(f".NET 9 SDK installation exited with code {result.returncode}")
                if result.stderr:
                    self.logger.warning(f"stderr: {result.stderr}")
                # Note: Some installers return non-zero even on success, so we'll check if files exist
                dotnet_path = prefix_path / "drive_c" / "Program Files" / "dotnet"
                if dotnet_path.exists():
                    self.logger.info("[OK] .NET 9 SDK appears to be installed (dotnet directory exists)")
                    return True
                else:
                    self.logger.error(".NET 9 SDK installation failed - dotnet directory not found")
                    return False

        except subprocess.TimeoutExpired:
            self.logger.error(".NET 9 SDK installation timed out after 10 minutes")
            return False
        except Exception as e:
            self.logger.error(f"Failed to install .NET 9 SDK: {e}")
            return False

    def is_dotnet9_installed(self, prefix_path: Path) -> bool:
        """
        Check if .NET 9 SDK is already installed in prefix

        Args:
            prefix_path: Path to Wine prefix

        Returns:
            True if installed, False otherwise
        """
        try:
            # Check for dotnet directory
            dotnet_path = prefix_path / "drive_c" / "Program Files" / "dotnet"

            if not dotnet_path.exists():
                return False

            # Check for dotnet.exe
            dotnet_exe = dotnet_path / "dotnet.exe"
            if not dotnet_exe.exists():
                return False

            # Check for SDK directory
            sdk_path = dotnet_path / "sdk"
            if not sdk_path.exists():
                return False

            # Check for version 9.x SDK
            for sdk_version in sdk_path.iterdir():
                if sdk_version.is_dir() and sdk_version.name.startswith("9."):
                    self.logger.info(f".NET 9 SDK found: {sdk_version.name}")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking for .NET 9 SDK: {e}")
            return False
