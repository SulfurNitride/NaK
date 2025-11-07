"""
MO2 Installer Module (Proton-GE Standalone Only)

This module provides Mod Organizer 2 installation with standalone Proton-GE.
NO Steam integration - uses ~/NaK/Prefixes for Wine prefixes.

The installer is broken down into focused modules for better maintainability:

- installer.py: Main MO2Installer class (orchestration) - Proton-GE only
- verification.py: Installation verification and utilities (mixin)
- download.py: Download, extraction, and dependency operations (mixin)
"""

from .installer import MO2Installer

__all__ = ['MO2Installer']
