"""
GitHub Downloader

This module provides GitHub download functionality for mod manager installers.
It handles GitHub API access, release information, file downloads with caching,
and SHA256 verification.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable
import requests

from src.core.installers.base.base_installer import GitHubRelease
from src.utils.logger import get_logger


class GitHubDownloader:
    """
    Handles GitHub API access and file downloads for mod managers

    This class provides:
    - GitHub release information retrieval
    - Asset finding with pattern matching
    - File downloads with progress tracking
    - Caching with SHA256 verification
    - Cache metadata management
    """

    def __init__(self, repo_owner: str, repo_name: str, cache_prefix: str):
        """
        Initialize GitHub downloader

        Args:
            repo_owner: GitHub repository owner (e.g., "ModOrganizer2")
            repo_name: GitHub repository name (e.g., "modorganizer")
            cache_prefix: Prefix for cache files (e.g., "mo2", "vortex", "unverum")
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.cache_prefix = cache_prefix
        self.logger = get_logger(__name__)

        # Cache directory
        self.cache_dir = Path.home() / "NaK" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_latest_release(self) -> Optional[GitHubRelease]:
        """
        Get the latest release from GitHub

        Returns:
            GitHubRelease object, or None if failed
        """
        try:
            self.logger.info(f"Fetching latest {self.repo_name} release from GitHub...")

            api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"

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

    def find_asset(self, release: GitHubRelease, pattern: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Find an asset in a release matching a pattern

        Args:
            release: GitHubRelease object
            pattern: Regex pattern to match asset name (e.g., r"\.7z\.exe$", r"\.exe$")

        Returns:
            Tuple of (download_url, filename), or (None, None) if not found
        """
        import re

        try:
            for asset in release.assets:
                asset_name = asset.get("name", "")
                if re.search(pattern, asset_name):
                    download_url = asset.get("browser_download_url")
                    if download_url:
                        self.logger.info(f"Found asset: {asset_name}")
                        return (download_url, asset_name)

            self.logger.error(f"No asset matching pattern '{pattern}' found in release {release.tag_name}")
            return (None, None)

        except Exception as e:
            self.logger.error(f"Failed to find asset: {e}")
            return (None, None)

    def download_file(self,
                     url: str,
                     filename: str,
                     cache_enabled: bool = True,
                     progress_callback: Optional[Callable] = None) -> Optional[str]:
        """
        Download a file with progress tracking, caching, and hash verification

        Args:
            url: URL to download from
            filename: Filename to save as
            cache_enabled: Whether to use caching (default: True)
            progress_callback: Optional callback for progress (percent, current, total)

        Returns:
            Path to downloaded file, or None if failed
        """
        try:
            file_path = self.cache_dir / filename

            # Check cache if enabled
            if cache_enabled:
                # Load cache metadata
                metadata = self.load_cache_metadata()
                cached_file_info = metadata.get("files", {}).get(filename, {})
                cached_hash = cached_file_info.get("sha256")
                cached_url = cached_file_info.get("url")

                # If file exists and URL matches, verify hash
                if file_path.exists() and cached_url == url:
                    if cached_hash:
                        self.logger.info(f"Found cached file: {filename}")
                        self.logger.info("Verifying cached file integrity...")

                        current_hash = self.calculate_sha256(str(file_path))
                        if current_hash == cached_hash:
                            self.logger.info("Cache verification passed, using cached file")
                            return str(file_path)
                        else:
                            self.logger.warning("Cache verification failed, re-downloading...")
                    else:
                        self.logger.info(f"Using cached file (no hash available): {filename}")
                        return str(file_path)

            # Download file
            self.logger.info(f"Downloading {filename} from {url}")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            # Download with progress
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Report progress
                        if progress_callback and total_size > 0:
                            percent = (downloaded / total_size) * 100
                            progress_callback(percent, downloaded, total_size)

            self.logger.info(f"Download complete: {filename}")

            # Calculate hash and save metadata if caching enabled
            if cache_enabled:
                file_hash = self.calculate_sha256(str(file_path))
                self.logger.info(f"SHA256: {file_hash}")

                # Update metadata
                if "files" not in metadata:
                    metadata["files"] = {}

                metadata["files"][filename] = {
                    "url": url,
                    "sha256": file_hash,
                    "size": total_size,
                    "downloaded": downloaded
                }

                self.save_cache_metadata(metadata)

            return str(file_path)

        except Exception as e:
            self.logger.error(f"Failed to download file: {e}")
            return None

    def calculate_sha256(self, file_path: str) -> str:
        """
        Calculate SHA256 hash of a file

        Args:
            file_path: Path to file

        Returns:
            SHA256 hash as hex string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def load_cache_metadata(self) -> Dict[str, Any]:
        """
        Load cache metadata from JSON file

        Returns:
            Dictionary with cache metadata
        """
        metadata_file = self.cache_dir / f"{self.cache_prefix}_cache_metadata.json"

        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load cache metadata: {e}")

        return {}

    def save_cache_metadata(self, metadata: Dict[str, Any]):
        """
        Save cache metadata to JSON file

        Args:
            metadata: Dictionary with cache metadata
        """
        metadata_file = self.cache_dir / f"{self.cache_prefix}_cache_metadata.json"

        try:
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save cache metadata: {e}")

    def clear_cache(self, filename: Optional[str] = None):
        """
        Clear cache for this downloader

        Args:
            filename: Specific file to clear, or None to clear all
        """
        if filename:
            # Clear specific file
            file_path = self.cache_dir / filename
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.logger.info(f"Cleared cache: {filename}")

                    # Remove from metadata
                    metadata = self.load_cache_metadata()
                    if "files" in metadata and filename in metadata["files"]:
                        del metadata["files"][filename]
                        self.save_cache_metadata(metadata)

                except Exception as e:
                    self.logger.warning(f"Failed to clear cache: {e}")
        else:
            # Clear all files for this prefix
            metadata = self.load_cache_metadata()
            if "files" in metadata:
                for fname in list(metadata["files"].keys()):
                    file_path = self.cache_dir / fname
                    if file_path.exists():
                        try:
                            file_path.unlink()
                            self.logger.info(f"Cleared cache: {fname}")
                        except Exception as e:
                            self.logger.warning(f"Failed to clear {fname}: {e}")

                # Clear metadata
                metadata["files"] = {}
                self.save_cache_metadata(metadata)
