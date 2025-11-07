"""
MO2 Download Operations Mixin

Provides MO2-specific download and extraction functionality.
Inherits common GitHub download operations from shared mixin.
"""
from typing import Tuple, Optional

from src.core.installers.base.base_installer import GitHubRelease
from src.mod_managers.shared import GitHubDownloadMixin


class MO2DownloadMixin(GitHubDownloadMixin):
    """Mixin providing MO2-specific download and extraction operations"""

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
        return super()._get_install_directory(custom_dir, "ModOrganizer2")

    def _download_file(self, url: str, filename: str, progress_callback=None) -> Optional[str]:
        """
        Download a file with MO2-specific cache configuration

        Checks MO2 cache settings and delegates to parent class.
        """
        try:
            # Check if MO2 caching is enabled
            from src.utils.cache_config import CacheConfig
            cache_config = CacheConfig()
            cache_enabled = cache_config.should_cache_mo2()

            # Delegate to parent class
            return super()._download_file(url, filename, cache_enabled, progress_callback)

        except Exception as e:
            self.logger.error(f"Failed to download file: {e}")
            return None

    def _extract_archive(self, archive_path: str, extract_dir: str) -> Optional[str]:
        """
        Extract MO2 archive to installation directory

        Delegates to base class implementation with MO2-specific search pattern.
        """
        return super()._extract_archive(archive_path, extract_dir, search_pattern="modorganizer")
