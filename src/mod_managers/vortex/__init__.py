"""
Vortex Installer Module (Proton-GE Standalone Only)

This module provides Vortex installation with standalone Proton-GE.
NO Steam integration - uses ~/NaK/Prefixes for Wine prefixes.

The installer is broken down into focused modules for better maintainability:

- installer.py: Main VortexInstaller class (orchestration) - Proton-GE only
- download.py: Download and installation operations (mixin)

Inherits from shared mixins in parent module:
- ProtonGEDependencyMixin: Dependency installation with Proton-GE
- GitHubDownloadMixin: GitHub release downloads and caching
"""

from .installer import VortexInstaller

__all__ = ['VortexInstaller']
