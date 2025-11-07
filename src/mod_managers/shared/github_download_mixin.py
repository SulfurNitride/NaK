"""
Shared GitHub Download Mixin

Provides GitHub release download and caching functionality.
Can be used by any installer that downloads from GitHub releases.
"""
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from src.core.installers.base.base_installer import GitHubRelease


class GitHubDownloadMixin:
    """Mixin providing GitHub download and caching operations"""

    def _get_latest_release(self) -> Optional[GitHubRelease]:
        """
        Get the latest release from GitHub

        Delegates to GitHubDownloader for consistent GitHub API access.
        """
        return self.github_downloader.get_latest_release()

    def _calculate_sha256(self, file_path: str) -> str:
        """
        Calculate SHA256 hash of a file

        Delegates to GitHubDownloader for consistent hash calculation.
        """
        return self.github_downloader.calculate_sha256(file_path)

    def _load_cache_metadata(self) -> Dict[str, Any]:
        """
        Load cache metadata

        Delegates to GitHubDownloader for consistent metadata handling.
        """
        return self.github_downloader.load_cache_metadata()

    def _save_cache_metadata(self, metadata: Dict[str, Any]):
        """
        Save cache metadata

        Delegates to GitHubDownloader for consistent metadata handling.
        """
        self.github_downloader.save_cache_metadata(metadata)

    def _download_file(self, url: str, filename: str, cache_enabled: bool = True, progress_callback=None) -> Optional[str]:
        """
        Download a file with progress tracking, caching, and hash verification

        Args:
            url: Download URL
            filename: Target filename
            cache_enabled: Whether to use caching (default: True)
            progress_callback: Optional progress callback

        Returns:
            Path to downloaded file, or None on failure
        """
        try:
            if not cache_enabled:
                self.logger.info("Caching disabled")
                if self.log_callback:
                    self.log_callback(f"Downloading {filename} (caching disabled)")

            # Delegate to GitHubDownloader
            result = self.github_downloader.download_file(
                url=url,
                filename=filename,
                cache_enabled=cache_enabled,
                progress_callback=progress_callback
            )

            if result and self.log_callback:
                if cache_enabled:
                    self.log_callback(f"Archive ready: {filename}")
                else:
                    self.log_callback(f"Archive downloaded: {filename}")

            return result

        except Exception as e:
            self.logger.error(f"Failed to download file: {e}")
            return None

    def _get_install_directory(self, custom_dir: Optional[str], default_name: str) -> Optional[str]:
        """Get the installation directory

        Args:
            custom_dir: Custom directory if provided
            default_name: Default directory name (e.g., "ModOrganizer2", "Vortex")

        Returns:
            Installation directory path or None on failure
        """
        try:
            import os

            if custom_dir:
                install_dir = custom_dir
                self.logger.info(f"Using custom installation directory: {install_dir}")
            else:
                # Create a default installation directory
                home_dir = os.path.expanduser("~")
                install_dir = os.path.join(home_dir, "Games", default_name)
                self.logger.info(f"Using default installation directory: {install_dir}")

            # Create directory if it doesn't exist
            os.makedirs(install_dir, exist_ok=True)

            return install_dir

        except Exception as e:
            self.logger.error(f"Failed to get install directory: {e}")
            return None
