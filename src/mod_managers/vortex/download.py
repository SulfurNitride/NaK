"""
Vortex Download Operations Mixin

Provides Vortex-specific download and installation functionality.
Inherits common GitHub download operations from shared mixin.
"""
from typing import Tuple, Optional

from src.core.installers.base.base_installer import GitHubRelease
from src.mod_managers.shared import GitHubDownloadMixin


class VortexDownloadMixin(GitHubDownloadMixin):
    """Mixin providing Vortex-specific download operations"""

    def _find_vortex_asset(self, release: GitHubRelease) -> Tuple[Optional[str], Optional[str]]:
        """Find the appropriate Vortex installer asset"""
        try:
            self.logger.info("Finding appropriate Vortex installer...")

            # Look for the Windows installer .exe file
            for asset in release.assets:
                name = asset.get("name", "")
                download_url = asset.get("browser_download_url", "")

                # Look for the main installer (vortex-setup-x.x.x.exe)
                if name.lower().startswith("vortex") and "setup" in name.lower() and name.lower().endswith(".exe"):
                    self.logger.info(f"Found Vortex installer: {name}")
                    return download_url, name

            # Fallback: any .exe file with "setup" in the name
            for asset in release.assets:
                name = asset.get("name", "")
                download_url = asset.get("browser_download_url", "")

                if "setup" in name.lower() and name.lower().endswith(".exe"):
                    self.logger.info(f"Found fallback installer: {name}")
                    return download_url, name

            self.logger.error("No suitable Vortex installer found")
            return None, None

        except Exception as e:
            self.logger.error(f"Failed to find Vortex asset: {e}")
            return None, None

    def _get_install_directory(self, custom_dir: Optional[str] = None) -> Optional[str]:
        """Get the installation directory for Vortex"""
        return super()._get_install_directory(custom_dir, "Vortex")

    def _download_file(self, url: str, filename: str, progress_callback=None) -> Optional[str]:
        """
        Download a file with Vortex-specific cache configuration

        Vortex always uses caching (unlike MO2 which has a setting).
        """
        try:
            # Vortex always caches installers
            cache_enabled = True

            # Delegate to parent class
            return super()._download_file(url, filename, cache_enabled, progress_callback)

        except Exception as e:
            self.logger.error(f"Failed to download file: {e}")
            return None
