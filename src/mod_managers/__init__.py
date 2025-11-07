"""
Mod Managers Module

Provides installation and management for Windows mod managers on Linux.
Uses standalone Proton-GE (NO Steam integration).

Supported Mod Managers:
- MO2 (Mod Organizer 2) - Modular structure
- Vortex - Modular structure

All mod managers share common mixins in the shared/ module for:
- Proton-GE dependency installation
- GitHub release downloads and caching
"""

from .mo2 import MO2Installer
from .vortex import VortexInstaller

__all__ = ['MO2Installer', 'VortexInstaller']
