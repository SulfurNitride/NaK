"""
Shared Installer Mixins

Reusable mixins that can be shared across different mod manager installers (MO2, Vortex).
"""

from .proton_ge_dependency_mixin import ProtonGEDependencyMixin
from .github_download_mixin import GitHubDownloadMixin

__all__ = ['ProtonGEDependencyMixin', 'GitHubDownloadMixin']
