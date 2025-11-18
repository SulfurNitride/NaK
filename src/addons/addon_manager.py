"""
Simple NaK Addon Manager
Fetches and manages addons from GitHub (NaK-Addons repository)
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import requests


class AddonManager:
    """Manages NaK addons - simple version for 1-2 addons"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.addon_dir = Path.home() / ".config" / "nak" / "addons"
        self.addon_dir.mkdir(parents=True, exist_ok=True)

        # GitHub repo for addons
        self.addon_repo_owner = "SulfurNitride"
        self.addon_repo_name = "NaK-Addons"

    def fetch_addon_catalog(self) -> Optional[List[Dict]]:
        """
        Fetch available addons from NaK-Addons repository
        Looks for marketplace.json in the latest release
        """
        try:
            # Get latest release from GitHub API
            api_url = f"https://api.github.com/repos/{self.addon_repo_owner}/{self.addon_repo_name}/releases/latest"
            self.logger.info(f"Fetching addon catalog from: {api_url}")

            response = requests.get(api_url, timeout=10)
            response.raise_for_status()

            release_data = response.json()

            # Find marketplace.json in release assets
            marketplace_url = None
            for asset in release_data.get('assets', []):
                if asset['name'] == 'marketplace.json':
                    marketplace_url = asset['browser_download_url']
                    break

            if not marketplace_url:
                self.logger.warning("No marketplace.json found in latest release")
                return []

            # Download and parse marketplace.json
            catalog_response = requests.get(marketplace_url, timeout=10)
            catalog_response.raise_for_status()
            catalog = catalog_response.json()

            addons = catalog.get('addons', [])
            self.logger.info(f"Found {len(addons)} addons in catalog")
            return addons

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch addon catalog: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing addon catalog: {e}")
            return None

    def get_installed_addons(self) -> List[Dict]:
        """Get list of installed addons"""
        installed = []

        for meta_file in self.addon_dir.glob("*.meta.json"):
            try:
                with open(meta_file, 'r') as f:
                    metadata = json.load(f)
                    installed.append(metadata)
            except Exception as e:
                self.logger.error(f"Failed to load addon metadata {meta_file}: {e}")

        return installed

    def is_addon_installed(self, addon_id: str) -> bool:
        """Check if an addon is installed"""
        meta_file = self.addon_dir / f"{addon_id}.meta.json"
        return meta_file.exists()

    def install_addon(self, addon_info: Dict, progress_callback=None) -> bool:
        """
        Install an addon from the marketplace
        Downloads the addon package and extracts it
        """
        try:
            addon_id = addon_info['id']
            addon_name = addon_info['name']
            asset_name = addon_info['asset']

            self.logger.info(f"Installing addon: {addon_name}")

            if progress_callback:
                progress_callback(0, 100, f"Downloading {addon_name}...")

            # Get latest release
            api_url = f"https://api.github.com/repos/{self.addon_repo_owner}/{self.addon_repo_name}/releases/latest"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            release_data = response.json()

            # Find the addon asset
            download_url = None
            for asset in release_data.get('assets', []):
                if asset['name'] == asset_name:
                    download_url = asset['browser_download_url']
                    break

            if not download_url:
                self.logger.error(f"Asset not found: {asset_name}")
                return False

            # Download the addon package
            if progress_callback:
                progress_callback(30, 100, "Downloading addon package...")

            download_response = requests.get(download_url, timeout=60)
            download_response.raise_for_status()

            # Save to temp file
            temp_file = self.addon_dir / asset_name
            temp_file.write_bytes(download_response.content)

            if progress_callback:
                progress_callback(60, 100, "Extracting addon...")

            # Extract addon
            addon_install_path = self.addon_dir / addon_id
            if addon_install_path.exists():
                import shutil
                shutil.rmtree(addon_install_path)

            import zipfile
            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                zip_ref.extractall(addon_install_path)

            # Clean up temp file
            temp_file.unlink()

            if progress_callback:
                progress_callback(90, 100, "Finalizing installation...")

            # Save installed addon metadata
            self._save_addon_metadata(addon_id, addon_info)

            if progress_callback:
                progress_callback(100, 100, "Installation complete!")

            self.logger.info(f"Addon installed successfully: {addon_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to install addon: {e}")
            return False

    def uninstall_addon(self, addon_id: str) -> bool:
        """Uninstall an addon"""
        try:
            addon_path = self.addon_dir / addon_id
            meta_file = self.addon_dir / f"{addon_id}.meta.json"

            if addon_path.exists():
                import shutil
                shutil.rmtree(addon_path)

            if meta_file.exists():
                meta_file.unlink()

            self.logger.info(f"Addon uninstalled: {addon_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to uninstall addon: {e}")
            return False

    def _save_addon_metadata(self, addon_id: str, metadata: Dict):
        """Save metadata about installed addon"""
        meta_file = self.addon_dir / f"{addon_id}.meta.json"
        with open(meta_file, 'w') as f:
            json.dump(metadata, f, indent=2)
