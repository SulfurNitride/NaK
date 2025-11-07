"""
Proton-GE Manager
Handles downloading, extracting, and managing Proton-GE versions from GitHub
"""

import os
import json
import tarfile
import requests
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple
from src.utils.logger import get_logger


class ProtonGEVersion:
    """Represents a Proton-GE version"""

    def __init__(self, tag_name: str, download_url: str, size: int, published_at: str):
        self.tag_name = tag_name
        self.download_url = download_url
        self.size = size
        self.published_at = published_at

    def __repr__(self):
        return f"ProtonGEVersion({self.tag_name})"


class ProtonGEManager:
    """Manages Proton-GE versions: download, extract, version control"""

    GITHUB_API_URL = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"

    def __init__(self):
        self.logger = get_logger(__name__)

        # Set up directory structure
        self.nak_home = Path.home() / "NaK"
        self.proton_ge_dir = self.nak_home / "ProtonGE"
        self.cache_dir = self.nak_home / "cache"

        # Create directories if they don't exist
        self.proton_ge_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Proton-GE directory: {self.proton_ge_dir}")

    def fetch_available_versions(self, limit: int = 10) -> List[ProtonGEVersion]:
        """
        Fetch available Proton-GE versions from GitHub API

        Args:
            limit: Maximum number of versions to fetch

        Returns:
            List of ProtonGEVersion objects
        """
        try:
            self.logger.info(f"Fetching Proton-GE releases from GitHub...")

            response = requests.get(
                self.GITHUB_API_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10
            )
            response.raise_for_status()

            releases = response.json()
            versions = []

            for release in releases[:limit]:
                # Find the .tar.gz asset
                for asset in release.get('assets', []):
                    if asset['name'].endswith('.tar.gz') and 'sha512sum' not in asset['name']:
                        version = ProtonGEVersion(
                            tag_name=release['tag_name'],
                            download_url=asset['browser_download_url'],
                            size=asset['size'],
                            published_at=release['published_at']
                        )
                        versions.append(version)
                        break

            self.logger.info(f"Found {len(versions)} Proton-GE versions")
            return versions

        except Exception as e:
            self.logger.error(f"Failed to fetch Proton-GE versions: {e}")
            return []

    def download_version(
        self,
        version: ProtonGEVersion,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
        delete_archive: bool = True
    ) -> Optional[Path]:
        """
        Download a Proton-GE version

        Args:
            version: ProtonGEVersion to download
            progress_callback: Callback function(percent, downloaded_mb, total_mb)
            delete_archive: Whether to delete the .tar.gz after extraction

        Returns:
            Path to extracted directory, or None on failure
        """
        try:
            # Determine file paths
            archive_filename = f"{version.tag_name}.tar.gz"
            archive_path = self.cache_dir / archive_filename

            # Check if already downloaded
            if archive_path.exists():
                self.logger.info(f"Archive already exists: {archive_path}")
            else:
                self.logger.info(f"Downloading {version.tag_name}...")
                self.logger.info(f"URL: {version.download_url}")

                # Download with progress
                response = requests.get(version.download_url, stream=True, timeout=30)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(archive_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1048576):  # 1MB chunks for faster download
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            if progress_callback and total_size > 0:
                                percent = int((downloaded / total_size) * 100)
                                downloaded_mb = downloaded / (1024 * 1024)
                                total_mb = total_size / (1024 * 1024)
                                progress_callback(percent, downloaded_mb, total_mb)

                self.logger.info(f"Download complete: {archive_path}")

            # Extract
            extracted_path = self._extract_version(archive_path, version.tag_name)

            # Delete archive if requested
            if delete_archive and archive_path.exists():
                try:
                    archive_path.unlink()
                    self.logger.info(f"Deleted archive: {archive_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete archive: {e}")

            return extracted_path

        except Exception as e:
            self.logger.error(f"Failed to download Proton-GE version {version.tag_name}: {e}")
            return None

    def _extract_version(self, archive_path: Path, tag_name: str) -> Optional[Path]:
        """
        Extract a Proton-GE archive

        Args:
            archive_path: Path to .tar.gz file
            tag_name: Version tag name

        Returns:
            Path to extracted directory
        """
        try:
            import subprocess

            # Expected extraction directory name (GE uses this format)
            extracted_dir = self.proton_ge_dir / tag_name

            # Check if already extracted
            if extracted_dir.exists():
                self.logger.info(f"Already extracted: {extracted_dir}")
                return extracted_dir

            self.logger.info(f"Extracting {archive_path}...")

            # Use tar command instead of Python's tarfile module for better reliability
            result = subprocess.run(
                ["tar", "-xzf", str(archive_path), "-C", str(self.proton_ge_dir)],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                self.logger.error(f"tar extraction failed: {result.stderr}")
                return None

            # Verify extraction was successful
            if not extracted_dir.exists():
                self.logger.error(f"Extraction completed but directory not found: {extracted_dir}")
                return None

            # Verify proton binary exists
            proton_binary = extracted_dir / "proton"
            if not proton_binary.exists():
                self.logger.error(f"Extraction incomplete - proton binary not found: {proton_binary}")
                return None

            self.logger.info(f"Extracted to: {extracted_dir}")
            return extracted_dir

        except subprocess.TimeoutExpired:
            self.logger.error(f"Extraction timed out after 300 seconds")
            return None
        except Exception as e:
            self.logger.error(f"Failed to extract {archive_path}: {e}")
            return None

    def get_installed_versions(self) -> List[str]:
        """
        Get list of installed Proton-GE versions

        Returns:
            List of version tag names
        """
        try:
            versions = []

            if not self.proton_ge_dir.exists():
                return versions

            for item in self.proton_ge_dir.iterdir():
                if item.is_dir() and item.name != "active":
                    # Verify it's a valid Proton-GE installation
                    proton_binary = item / "proton"
                    if proton_binary.exists():
                        versions.append(item.name)

            # Sort versions (newest first)
            versions.sort(reverse=True)

            self.logger.debug(f"Found {len(versions)} installed Proton-GE versions")
            return versions

        except Exception as e:
            self.logger.error(f"Failed to get installed versions: {e}")
            return []

    def set_active_version(self, tag_name: str) -> bool:
        """
        Set a Proton-GE version as active by creating/updating symlink

        Args:
            tag_name: Version tag name to set as active

        Returns:
            True if successful
        """
        try:
            version_path = self.proton_ge_dir / tag_name
            active_symlink = self.proton_ge_dir / "active"

            # Verify version exists
            if not version_path.exists():
                self.logger.error(f"Version {tag_name} not found at {version_path}")
                return False

            # Remove old symlink if it exists
            if active_symlink.exists() or active_symlink.is_symlink():
                active_symlink.unlink()

            # Create new symlink
            active_symlink.symlink_to(version_path)

            self.logger.info(f"Set active Proton-GE version: {tag_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to set active version {tag_name}: {e}")
            return False

    def set_active_proton_path(self, proton_path: Path) -> bool:
        """
        Set any Proton installation as active by creating/updating symlink
        This works for both Proton-GE and system Proton versions

        Args:
            proton_path: Full path to the Proton directory

        Returns:
            True if successful
        """
        try:
            active_symlink = self.proton_ge_dir / "active"

            # Verify the path exists and has a proton binary
            if not proton_path.exists():
                self.logger.error(f"Proton path not found: {proton_path}")
                return False

            proton_binary = proton_path / "proton"
            if not proton_binary.exists():
                self.logger.error(f"Proton binary not found at {proton_binary}")
                return False

            # Remove old symlink if it exists
            if active_symlink.exists() or active_symlink.is_symlink():
                active_symlink.unlink()

            # Create new symlink (can point anywhere, not just ProtonGE dir)
            active_symlink.symlink_to(proton_path)

            self.logger.info(f"Set active Proton: {proton_path.name} at {proton_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to set active Proton path {proton_path}: {e}")
            return False

    def get_active_version(self) -> Optional[str]:
        """
        Get the currently active Proton-GE version

        Returns:
            Active version tag name, or None if not set
        """
        try:
            active_symlink = self.proton_ge_dir / "active"

            if active_symlink.exists() and active_symlink.is_symlink():
                # Resolve symlink to get actual directory name
                target = active_symlink.resolve()
                return target.name

            return None

        except Exception as e:
            self.logger.error(f"Failed to get active version: {e}")
            return None

    def get_active_proton_path(self) -> Optional[Path]:
        """
        Get path to the active Proton binary

        Returns:
            Path to proton binary, or None if no active version
        """
        try:
            active_symlink = self.proton_ge_dir / "active"

            if active_symlink.exists():
                proton_binary = active_symlink / "proton"
                if proton_binary.exists():
                    return proton_binary

            return None

        except Exception as e:
            self.logger.error(f"Failed to get active Proton path: {e}")
            return None

    def get_active_proton_directory(self) -> Optional[Path]:
        """
        Get path to the active Proton directory (not just the binary)

        Returns:
            Path to proton directory, or None if no active version
        """
        try:
            active_symlink = self.proton_ge_dir / "active"

            if active_symlink.exists() and active_symlink.is_symlink():
                target = active_symlink.resolve()
                if target.exists():
                    return target

            return None

        except Exception as e:
            self.logger.error(f"Failed to get active Proton directory: {e}")
            return None

    def delete_version(self, tag_name: str) -> bool:
        """
        Delete a Proton-GE version

        Args:
            tag_name: Version tag name to delete

        Returns:
            True if successful
        """
        try:
            version_path = self.proton_ge_dir / tag_name

            if not version_path.exists():
                self.logger.warning(f"Version {tag_name} not found")
                return False

            # Don't delete if it's the active version
            active_version = self.get_active_version()
            if active_version == tag_name:
                self.logger.error(f"Cannot delete active version {tag_name}")
                return False

            # Delete directory
            import shutil
            shutil.rmtree(version_path)

            self.logger.info(f"Deleted Proton-GE version: {tag_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete version {tag_name}: {e}")
            return False

    def cleanup_old_versions(self, keep_count: int = 2) -> Tuple[int, List[str]]:
        """
        Clean up old Proton-GE versions, keeping only the most recent N versions

        Args:
            keep_count: Number of versions to keep

        Returns:
            Tuple of (count_deleted, list_of_deleted_versions)
        """
        try:
            installed = self.get_installed_versions()
            active = self.get_active_version()

            # Ensure active version is in the keep list
            to_keep = set(installed[:keep_count])
            if active:
                to_keep.add(active)

            # Delete old versions
            deleted = []
            for version in installed:
                if version not in to_keep:
                    if self.delete_version(version):
                        deleted.append(version)

            self.logger.info(f"Cleaned up {len(deleted)} old Proton-GE versions")
            return len(deleted), deleted

        except Exception as e:
            self.logger.error(f"Failed to cleanup old versions: {e}")
            return 0, []

    def is_version_installed(self, tag_name: str) -> bool:
        """
        Check if a specific version is installed

        Args:
            tag_name: Version tag name

        Returns:
            True if installed
        """
        version_path = self.proton_ge_dir / tag_name
        proton_binary = version_path / "proton"
        return proton_binary.exists()
