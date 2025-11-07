"""
Installer utility modules

This package contains utility classes used by mod manager installers.
"""

from src.core.installers.utils.winetricks_manager import WinetricksManager, get_winetricks_manager
from src.core.installers.utils.github_downloader import GitHubDownloader

__all__ = ['WinetricksManager', 'get_winetricks_manager', 'GitHubDownloader']
