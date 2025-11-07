"""
Central NaK Paths Helper
Provides centralized path resolution for NaK directories
Handles symlink resolution transparently
"""

from pathlib import Path
from typing import Optional


def get_nak_home() -> Path:
    """
    Get the NaK home directory path

    This always returns ~/NaK which may be:
    - A real directory at ~/NaK (default)
    - A symlink to another location (custom storage)

    All code should use this instead of hardcoding Path.home() / "NaK"
    to ensure consistent behavior regardless of storage location.

    Returns:
        Path to NaK home (may be symlink or real directory)
    """
    return Path.home() / "NaK"


def get_nak_real_path() -> Path:
    """
    Get the real (resolved) path to NaK directory

    If ~/NaK is a symlink, this resolves to the actual location.
    If ~/NaK is a real directory, returns ~/NaK.

    Returns:
        Resolved path to NaK directory
    """
    nak_path = get_nak_home()
    if nak_path.is_symlink():
        return nak_path.resolve()
    return nak_path


def get_proton_ge_dir() -> Path:
    """Get ProtonGE directory path"""
    return get_nak_home() / "ProtonGE"


def get_prefixes_dir() -> Path:
    """Get Prefixes directory path"""
    return get_nak_home() / "Prefixes"


def get_cache_dir() -> Path:
    """Get cache directory path"""
    return get_nak_home() / "cache"


def get_nxm_links_dir() -> Path:
    """Get NXM links directory path"""
    return get_nak_home() / "NXM_Links"


def get_active_proton() -> Path:
    """Get active Proton-GE symlink path"""
    return get_proton_ge_dir() / "active"


# Convenience function for common checks
def nak_exists() -> bool:
    """Check if NaK directory exists"""
    return get_nak_home().exists()


def is_nak_symlink() -> bool:
    """Check if NaK is a symlink to custom location"""
    return get_nak_home().is_symlink()
