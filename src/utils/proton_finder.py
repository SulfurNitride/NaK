"""
Unified Proton Finder
Finds all available Proton versions (system, GE, custom) on the system
"""

import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from src.utils.logger import get_logger


@dataclass
class ProtonInfo:
    """Information about a detected Proton installation"""
    name: str              # Display name (e.g., "Proton Experimental", "GE-Proton9-7")
    path: Path             # Full path to the Proton directory
    proton_type: str       # Type: "steam", "proton-ge", "custom"
    version: Optional[str] = None  # Version string if available
    is_experimental: bool = False  # Whether this is Proton Experimental

    def __str__(self):
        return f"{self.name} ({self.proton_type})"


class ProtonFinder:
    """Unified Proton finder - scans all known Proton locations"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def find_all_proton_versions(self) -> List[ProtonInfo]:
        """
        Find all available Proton versions on the system

        Returns:
            List of ProtonInfo objects for all detected Proton installations
        """
        proton_versions = []

        # 1. Find Steam's official Proton versions
        steam_protons = self._find_steam_proton_versions()
        proton_versions.extend(steam_protons)
        self.logger.info(f"Found {len(steam_protons)} Steam Proton version(s)")

        # 2. Find Proton-GE versions
        ge_protons = self._find_proton_ge_versions()
        proton_versions.extend(ge_protons)
        self.logger.info(f"Found {len(ge_protons)} Proton-GE version(s)")

        # 3. Find custom compatibility tools
        custom_protons = self._find_custom_proton_versions()
        proton_versions.extend(custom_protons)
        self.logger.info(f"Found {len(custom_protons)} custom Proton version(s)")

        self.logger.info(f"Total: {len(proton_versions)} Proton version(s) detected")
        return proton_versions

    def _get_all_steam_library_paths(self) -> List[Path]:
        """Get all Steam library paths including additional libraries on other drives"""
        all_library_paths = []

        # Common Steam installation paths
        steam_root_paths = [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
            Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",  # Flatpak
        ]

        for steam_root in steam_root_paths:
            steamapps = steam_root / "steamapps"
            if not steamapps.exists():
                continue

            # Add the main Steam library
            all_library_paths.append(steamapps)
            self.logger.debug(f"Found main Steam library: {steamapps}")

            # Parse libraryfolders.vdf to find additional Steam libraries
            libraryfolders_vdf = steamapps / "libraryfolders.vdf"
            if libraryfolders_vdf.exists():
                try:
                    with open(libraryfolders_vdf, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        for line in content.split('\n'):
                            line = line.strip()
                            if '"path"' in line:
                                parts = line.split('"')
                                if len(parts) >= 4:
                                    library_path = Path(parts[3]) / "steamapps"
                                    if library_path.exists() and library_path not in all_library_paths:
                                        all_library_paths.append(library_path)
                                        self.logger.debug(f"Found additional Steam library: {library_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to parse {libraryfolders_vdf}: {e}")

        return all_library_paths

    def _find_steam_proton_versions(self) -> List[ProtonInfo]:
        """Find official Steam Proton versions"""
        proton_versions = []
        seen_paths = set()  # Track resolved paths to avoid duplicates from symlinks

        # Get all Steam library paths (including additional libraries on other drives)
        steam_library_paths = self._get_all_steam_library_paths()

        for steamapps in steam_library_paths:
            steamapps_common = steamapps / "common"

            if not steamapps_common.exists():
                continue

            self.logger.debug(f"Scanning Steam directory: {steamapps_common}")

            # Look for Proton directories
            for item in steamapps_common.iterdir():
                if not item.is_dir():
                    continue

                # Check if it's a Proton installation (has a 'proton' file)
                proton_binary = item / "proton"
                if not proton_binary.exists():
                    continue

                # Resolve path to handle symlinks and avoid duplicates
                resolved_path = item.resolve()
                if resolved_path in seen_paths:
                    self.logger.debug(f"Skipping duplicate Steam Proton at {item} (already found at {resolved_path})")
                    continue
                seen_paths.add(resolved_path)

                # It's a valid Proton installation
                name = item.name
                is_experimental = "experimental" in name.lower()

                # Try to extract version from directory name
                version = self._extract_version_from_name(name)

                proton_info = ProtonInfo(
                    name=name,
                    path=item,
                    proton_type="steam",
                    version=version,
                    is_experimental=is_experimental
                )

                proton_versions.append(proton_info)
                self.logger.debug(f"Found Steam Proton: {name} at {item}")

        return proton_versions

    def _find_proton_ge_versions(self) -> List[ProtonInfo]:
        """Find Proton-GE versions installed by NaK"""
        proton_versions = []
        seen_paths = set()  # Track resolved paths to avoid duplicates from symlinks

        # NaK's Proton-GE directory
        proton_ge_dir = Path.home() / "NaK" / "ProtonGE"

        if not proton_ge_dir.exists():
            return proton_versions

        self.logger.debug(f"Scanning Proton-GE directory: {proton_ge_dir}")

        for item in proton_ge_dir.iterdir():
            if not item.is_dir():
                continue

            # Skip the 'active' symlink
            if item.name == "active":
                continue

            # Check if it's a valid Proton installation
            proton_binary = item / "proton"
            if not proton_binary.exists():
                continue

            # Resolve path to handle symlinks and avoid duplicates
            resolved_path = item.resolve()
            if resolved_path in seen_paths:
                self.logger.debug(f"Skipping duplicate Proton-GE at {item} (already found at {resolved_path})")
                continue
            seen_paths.add(resolved_path)

            name = item.name
            version = self._extract_version_from_name(name)

            proton_info = ProtonInfo(
                name=name,
                path=item,
                proton_type="proton-ge",
                version=version,
                is_experimental=False
            )

            proton_versions.append(proton_info)
            self.logger.debug(f"Found Proton-GE: {name} at {item}")

        return proton_versions

    def _find_custom_proton_versions(self) -> List[ProtonInfo]:
        """Find custom Proton versions in Steam's compatibilitytools.d"""
        proton_versions = []
        seen_paths = set()  # Track resolved paths to avoid duplicates from symlinks

        # Steam compatibility tools directory
        steam_paths = [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
            Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",  # Flatpak
            Path("/") / "usr" / "share" / "steam", # proton-cachyos
        ]

        for steam_path in steam_paths:
            compat_tools_dir = steam_path / "compatibilitytools.d"

            if not compat_tools_dir.exists():
                continue

            self.logger.debug(f"Scanning compatibility tools directory: {compat_tools_dir}")

            for item in compat_tools_dir.iterdir():
                if not item.is_dir():
                    continue

                # Skip NaK's own compatibility tool registration
                if item.name == "NaK-Proton-Manager":
                    continue

                # Check if it's a valid Proton installation
                proton_binary = item / "proton"
                if not proton_binary.exists():
                    continue

                # Resolve path to handle symlinks and avoid duplicates
                resolved_path = item.resolve()
                if resolved_path in seen_paths:
                    self.logger.debug(f"Skipping duplicate custom Proton at {item} (already found at {resolved_path})")
                    continue
                seen_paths.add(resolved_path)

                name = item.name
                version = self._extract_version_from_name(name)

                # Determine if it's Proton-GE (might be installed here instead of NaK dir)
                proton_type = "proton-ge" if "GE-Proton" in name else "custom"

                proton_info = ProtonInfo(
                    name=name,
                    path=item,
                    proton_type=proton_type,
                    version=version,
                    is_experimental=False
                )

                proton_versions.append(proton_info)
                self.logger.debug(f"Found custom Proton: {name} at {item}")

        return proton_versions

    def _extract_version_from_name(self, name: str) -> Optional[str]:
        """
        Extract version number from Proton directory name

        Examples:
            "Proton 8.0" -> "8.0"
            "GE-Proton9-7" -> "9-7"
            "Proton - Experimental" -> "Experimental"
        """
        import re

        # Handle Proton Experimental
        if "experimental" in name.lower():
            return "Experimental"

        # Handle GE-Proton9-7 format
        ge_match = re.search(r'GE-Proton(\d+(?:-\d+)?)', name)
        if ge_match:
            return ge_match.group(1)

        # Handle "Proton 8.0" format
        proton_match = re.search(r'Proton\s+(\d+\.\d+)', name)
        if proton_match:
            return proton_match.group(1)

        # Handle just numbers
        number_match = re.search(r'(\d+\.\d+)', name)
        if number_match:
            return number_match.group(1)

        return None

    def get_proton_by_name(self, name: str) -> Optional[ProtonInfo]:
        """
        Get a specific Proton version by name

        Args:
            name: Proton directory name

        Returns:
            ProtonInfo object if found, None otherwise
        """
        all_protons = self.find_all_proton_versions()

        for proton in all_protons:
            if proton.name == name:
                return proton

        return None

    def get_proton_experimental(self) -> Optional[ProtonInfo]:
        """
        Get Proton Experimental specifically

        Returns:
            ProtonInfo for Proton Experimental if found
        """
        all_protons = self.find_all_proton_versions()

        for proton in all_protons:
            if proton.is_experimental:
                return proton

        return None
