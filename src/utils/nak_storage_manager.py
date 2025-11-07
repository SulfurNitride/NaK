"""
NaK Storage Manager
Manages the NaK folder location and handles symlink creation
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
from src.utils.logger import get_logger


class NaKStorageManager:
    """Manages NaK folder storage location and symlinks"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.default_nak_path = Path.home() / "NaK"

    def get_nak_path(self, custom_location: Optional[str] = None) -> Path:
        """
        Get the actual NaK storage path

        Args:
            custom_location: Custom storage location (if None, uses default ~/NaK)

        Returns:
            Path to the actual NaK storage directory
        """
        if custom_location:
            return Path(custom_location) / "NaK"

        # If ~/NaK is a symlink, resolve it to get the real location
        if self.default_nak_path.is_symlink():
            return self.default_nak_path.resolve()

        return self.default_nak_path

    def is_symlink_setup(self) -> bool:
        """Check if ~/NaK is a symlink to a custom location"""
        return self.default_nak_path.is_symlink()

    def get_real_location(self) -> Path:
        """Get the real storage location (resolves symlinks)"""
        if self.default_nak_path.exists():
            return self.default_nak_path.resolve()
        return self.default_nak_path

    def validate_storage_location(self, location: Path) -> Tuple[bool, str]:
        """
        Validate if a location is suitable for NaK storage

        Args:
            location: Path to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if location exists
        if not location.exists():
            return False, f"Location does not exist: {location}"

        # Check if it's a directory
        if not location.is_dir():
            return False, f"Location is not a directory: {location}"

        # Check if we have write permission
        if not os.access(location, os.W_OK):
            return False, f"No write permission for: {location}"

        # Check if there's enough space (warn if less than 5GB)
        try:
            stat = os.statvfs(location)
            free_space_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            if free_space_gb < 5:
                return False, f"Insufficient space: {free_space_gb:.2f}GB available (minimum 5GB recommended)"
        except Exception as e:
            self.logger.warning(f"Could not check available space: {e}")

        # Check if NaK folder would conflict
        target_nak = location / "NaK"
        if target_nak.exists() and not target_nak.is_dir():
            return False, f"A file named 'NaK' already exists at: {location}"

        return True, ""

    def setup_symlink(self, new_location: Path, move_existing: bool = False) -> Tuple[bool, str]:
        """
        Set up symlink from ~/NaK to a custom location

        Args:
            new_location: New storage location (e.g., /mnt/data)
            move_existing: If True, move existing ~/NaK data to new location

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Validate the new location
            is_valid, error_msg = self.validate_storage_location(new_location)
            if not is_valid:
                return False, error_msg

            target_nak = new_location / "NaK"

            # Handle existing ~/NaK
            if self.default_nak_path.exists():
                if self.default_nak_path.is_symlink():
                    # Already a symlink, update it
                    self.logger.info(f"Updating existing symlink from {self.default_nak_path} -> {target_nak}")
                    self.default_nak_path.unlink()
                else:
                    # It's a real directory
                    if move_existing:
                        self.logger.info(f"Moving existing NaK folder to {target_nak}")
                        if target_nak.exists():
                            return False, f"Target location already has a NaK folder: {target_nak}"
                        shutil.move(str(self.default_nak_path), str(target_nak))
                    else:
                        # Rename the old one as backup
                        backup_path = self.default_nak_path.with_name("NaK.backup")
                        counter = 1
                        while backup_path.exists():
                            backup_path = self.default_nak_path.with_name(f"NaK.backup.{counter}")
                            counter += 1

                        self.logger.info(f"Backing up existing NaK folder to {backup_path}")
                        self.default_nak_path.rename(backup_path)

            # Create target directory if it doesn't exist
            if not target_nak.exists():
                target_nak.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created NaK directory at {target_nak}")

            # Create the symlink
            self.default_nak_path.symlink_to(target_nak, target_is_directory=True)
            self.logger.info(f"Created symlink: {self.default_nak_path} -> {target_nak}")

            return True, f"Successfully set up NaK storage at {target_nak}"

        except Exception as e:
            self.logger.error(f"Failed to setup symlink: {e}", exc_info=True)
            return False, f"Error: {str(e)}"

    def remove_symlink(self, restore_backup: bool = False) -> Tuple[bool, str]:
        """
        Remove symlink and optionally restore from backup

        Args:
            restore_backup: If True, restore NaK.backup if it exists

        Returns:
            Tuple of (success, error_message)
        """
        try:
            if not self.default_nak_path.is_symlink():
                return False, "~/NaK is not a symlink"

            # Get the real location before removing symlink
            real_location = self.default_nak_path.resolve()

            # Remove symlink
            self.default_nak_path.unlink()
            self.logger.info(f"Removed symlink at {self.default_nak_path}")

            if restore_backup:
                backup_path = self.default_nak_path.with_name("NaK.backup")
                if backup_path.exists():
                    backup_path.rename(self.default_nak_path)
                    self.logger.info(f"Restored backup from {backup_path}")
                    return True, f"Symlink removed and backup restored. Data still at {real_location}"
                else:
                    return True, f"Symlink removed. No backup found. Data still at {real_location}"

            return True, f"Symlink removed. Data still at {real_location}"

        except Exception as e:
            self.logger.error(f"Failed to remove symlink: {e}", exc_info=True)
            return False, f"Error: {str(e)}"

    def get_storage_info(self) -> dict:
        """
        Get information about current storage setup

        Returns:
            Dict with storage information
        """
        info = {
            "is_symlink": self.is_symlink_setup(),
            "nak_path": str(self.default_nak_path),
            "real_path": str(self.get_real_location()),
            "exists": self.default_nak_path.exists(),
            "free_space_gb": 0.0,
            "used_space_gb": 0.0
        }

        # Get available space
        if info["exists"]:
            try:
                real_path = Path(info["real_path"])
                stat = os.statvfs(real_path)
                info["free_space_gb"] = (stat.f_bavail * stat.f_frsize) / (1024**3)

                # Calculate used space
                info["used_space_gb"] = self.get_directory_size(real_path)
            except Exception as e:
                self.logger.warning(f"Could not get storage info: {e}")

        return info

    def get_directory_size(self, path: Path) -> float:
        """
        Calculate total size of a directory in GB

        Args:
            path: Directory to measure

        Returns:
            Size in GB
        """
        try:
            import subprocess
            result = subprocess.run(
                ["du", "-sb", str(path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                size_bytes = int(result.stdout.split()[0])
                return size_bytes / (1024**3)
        except Exception as e:
            self.logger.warning(f"Could not calculate directory size: {e}")

        return 0.0

    def detect_installations(self) -> dict:
        """
        Detect existing mod manager installations in NaK folder

        Returns:
            Dict with installation counts and details
        """
        installations = {
            "prefixes": [],
            "total_count": 0,
            "mo2_count": 0,
            "vortex_count": 0,
            "has_proton_ge": False,
            "has_cache": False
        }

        if not self.default_nak_path.exists():
            return installations

        try:
            # Check for Proton-GE
            proton_ge_dir = self.default_nak_path / "ProtonGE"
            if proton_ge_dir.exists():
                installations["has_proton_ge"] = True

            # Check for cache
            cache_dir = self.default_nak_path / "cache"
            if cache_dir.exists():
                installations["has_cache"] = True

            # Scan prefixes
            prefixes_dir = self.default_nak_path / "Prefixes"
            if prefixes_dir.exists():
                for prefix_dir in prefixes_dir.iterdir():
                    if not prefix_dir.is_dir():
                        continue

                    # Look for marker file
                    marker_file = prefix_dir / "pfx" / "NAK_MANAGED_INSTANCE.txt"
                    if marker_file.exists():
                        try:
                            # Read marker to get info
                            info = {}
                            for line in marker_file.read_text().splitlines():
                                if '=' in line and not line.startswith('#'):
                                    key, value = line.split('=', 1)
                                    info[key] = value

                            instance_type = info.get('INSTANCE_TYPE', 'Unknown')
                            instance_name = info.get('INSTANCE_NAME', prefix_dir.name)

                            installations["prefixes"].append({
                                "name": instance_name,
                                "type": instance_type,
                                "path": str(prefix_dir)
                            })

                            installations["total_count"] += 1
                            if instance_type == "MO2":
                                installations["mo2_count"] += 1
                            elif instance_type == "Vortex":
                                installations["vortex_count"] += 1

                        except Exception as e:
                            self.logger.warning(f"Failed to read marker in {prefix_dir}: {e}")

        except Exception as e:
            self.logger.error(f"Failed to detect installations: {e}")

        return installations

    def preview_migration(self, new_location: Path) -> dict:
        """
        Preview what will happen during migration without actually doing it

        Args:
            new_location: Target location for migration

        Returns:
            Dict with preview information
        """
        preview = {
            "valid": False,
            "error": None,
            "source_path": str(self.get_real_location()),
            "target_path": str(new_location / "NaK"),
            "installations": {},
            "space_needed_gb": 0.0,
            "space_available_gb": 0.0,
            "will_move": False,
            "warnings": []
        }

        # Validate location
        is_valid, error_msg = self.validate_storage_location(new_location)
        if not is_valid:
            preview["error"] = error_msg
            return preview

        preview["valid"] = True

        # Get space info
        if self.default_nak_path.exists():
            preview["space_needed_gb"] = self.get_directory_size(self.default_nak_path)

        try:
            stat = os.statvfs(new_location)
            preview["space_available_gb"] = (stat.f_bavail * stat.f_frsize) / (1024**3)
        except Exception as e:
            preview["warnings"].append(f"Could not check available space: {e}")

        # Check if there's enough space
        if preview["space_needed_gb"] > preview["space_available_gb"]:
            preview["error"] = f"Insufficient space: Need {preview['space_needed_gb']:.2f}GB, have {preview['space_available_gb']:.2f}GB"
            preview["valid"] = False
            return preview

        # Detect what will be migrated
        preview["installations"] = self.detect_installations()

        # Check if target already has NaK folder
        target_nak = new_location / "NaK"
        if target_nak.exists():
            preview["warnings"].append(f"Target location already has a 'NaK' folder")

        return preview
