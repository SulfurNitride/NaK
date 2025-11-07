"""
MO2 Verification Mixin

Provides verification and utility methods for MO2 installations.
"""
import os
from typing import Dict, Any, Optional


class MO2VerificationMixin:
    """Mixin providing MO2 installation verification methods"""

    def _verify_installation(self, install_dir: str) -> Dict[str, Any]:
        """Verify that MO2 was installed correctly"""
        try:
            self.logger.info(f"Verifying MO2 installation in {install_dir}")

            # Check if directory exists
            if not os.path.exists(install_dir):
                return {
                    "success": False,
                    "error": f"Installation directory does not exist: {install_dir}"
                }

            # Check for ModOrganizer.exe
            mo2_exe = self._find_mo2_executable(install_dir)
            if not mo2_exe:
                return {
                    "success": False,
                    "error": "ModOrganizer.exe not found in installation"
                }

            self.logger.info("MO2 installation verification successful")
            return {"success": True}

        except Exception as e:
            self.logger.error(f"Installation verification failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _find_mo2_executable(self, install_dir: str) -> Optional[str]:
        """Find ModOrganizer.exe in the installation directory"""
        try:
            self.logger.info(f"Searching for ModOrganizer.exe in {install_dir}")

            # Look for ModOrganizer.exe
            for root, dirs, files in os.walk(install_dir):
                for file in files:
                    if file.lower() == "modorganizer.exe":
                        exe_path = os.path.join(root, file)
                        self.logger.info(f"Found ModOrganizer.exe: {exe_path}")
                        return exe_path

            self.logger.error("ModOrganizer.exe not found")
            return None

        except Exception as e:
            self.logger.error(f"Failed to find ModOrganizer.exe: {e}")
            return None

    def _get_installed_mo2_version(self, mo2_dir: str) -> Optional[str]:
        """Get the installed MO2 version from ModOrganizer.ini"""
        try:
            # Look for ModOrganizer.ini in the MO2 directory
            ini_path = os.path.join(mo2_dir, "ModOrganizer.ini")

            if not os.path.exists(ini_path):
                self.logger.debug(f"ModOrganizer.ini not found at {ini_path}")
                return None

            # Read the INI file
            import configparser
            config = configparser.ConfigParser()
            config.read(ini_path)

            # Try to get version from [General] section
            if "General" in config and "version" in config["General"]:
                version = config["General"]["version"]
                self.logger.info(f"Found MO2 version in INI: {version}")
                return version

            self.logger.debug("Version field not found in ModOrganizer.ini")
            return None

        except Exception as e:
            self.logger.debug(f"Failed to read MO2 version from INI: {e}")
            return None

    def check_mo2_update_available(self, mo2_dir: str) -> Dict[str, Any]:
        """Check if an update is available for an existing MO2 installation"""
        try:
            # Get installed version
            installed_version = self._get_installed_mo2_version(mo2_dir)
            if not installed_version:
                return {
                    "success": False,
                    "error": "Could not determine installed MO2 version"
                }

            # Get latest version
            release = self._get_latest_release()
            if not release:
                return {
                    "success": False,
                    "error": "Could not fetch latest MO2 version"
                }

            latest_version = release.tag_name

            # Compare versions (simple string comparison)
            needs_update = installed_version != latest_version

            return {
                "success": True,
                "installed_version": installed_version,
                "latest_version": latest_version,
                "update_available": needs_update,
                "message": f"Installed: {installed_version}, Latest: {latest_version}"
            }

        except Exception as e:
            self.logger.error(f"Failed to check for MO2 updates: {e}")
            return {
                "success": False,
                "error": str(e)
            }
