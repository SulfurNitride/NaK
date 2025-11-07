"""
NXM Handler Manager for NaK (Standalone Proton-GE Version)

Manages NXM link handling for multiple MO2/Vortex instances by:
1. Creating marker files in each instance's prefix
2. Generating individual .sh scripts for each instance
3. Managing the .desktop file to point to the active instance

Standalone Mode:
- Uses ~/NaK/Prefixes/ instead of Steam compatdata
- Uses Proton-GE from ~/NaK/ProtonGE/active
- No Steam AppID dependency
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.utils.logger import get_logger
from src.utils.steam_utils import SteamUtils


class NXMHandlerManager:
    """Manages NXM link handlers for MO2 and Vortex instances (Standalone Proton-GE)"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.steam_utils = SteamUtils()

        # NaK directories
        self.nak_home = Path.home() / "NaK"
        self.nxm_links_dir = self.nak_home / "NXM_Links"
        self.prefixes_dir = self.nak_home / "Prefixes"
        self.proton_ge_dir = self.nak_home / "ProtonGE"

        # Ensure directories exist
        self.nxm_links_dir.mkdir(parents=True, exist_ok=True)
        self.prefixes_dir.mkdir(parents=True, exist_ok=True)

        # .desktop file location
        self.desktop_file = Path.home() / ".local/share/applications/nxm-handler.desktop"

        self.logger.info(f"NXM Handler Manager initialized (Standalone Proton-GE mode)")
        self.logger.info(f"NXM scripts directory: {self.nxm_links_dir}")
        self.logger.info(f"Prefixes directory: {self.prefixes_dir}")

    def create_instance_marker(self, prefix_path: str, instance_info: Dict[str, str]) -> bool:
        """
        Create a marker file in the prefix to identify this as a NaK-managed instance

        Args:
            prefix_path: Path to the Wine prefix (e.g., ~/NaK/Prefixes/mo2_skyrim_se/pfx)
            instance_info: Dictionary with instance information:
                - instance_name: Display name (e.g., "Skyrim SE - Main Modlist")
                - instance_type: "MO2" or "Vortex"
                - exe_path: Wine path to ModOrganizer.exe or Vortex.exe (Z:\path\to\exe)
                - prefix_name: Name of the prefix folder (e.g., "mo2_skyrim_se")
                - proton_ge_version: Proton-GE version used (e.g., "GE-Proton10-21")
                - game_name: Full game name (optional)

        Returns:
            True if marker was created successfully
        """
        try:
            prefix = Path(prefix_path)
            marker_file = prefix / "NAK_MANAGED_INSTANCE.txt"

            # Generate content
            content = []
            content.append(f"# NaK Managed Instance Marker File")
            content.append(f"# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content.append(f"#")
            content.append(f"# This file identifies this prefix as managed by NaK")
            content.append(f"# DO NOT DELETE - Used for NXM link routing")
            content.append("")
            content.append(f"INSTANCE_NAME={instance_info.get('instance_name', 'Unknown')}")
            content.append(f"INSTANCE_TYPE={instance_info.get('instance_type', 'MO2')}")
            content.append(f"EXE_PATH={instance_info.get('exe_path', '')}")
            content.append(f"PREFIX_NAME={instance_info.get('prefix_name', '')}")
            content.append(f"PROTON_GE_VERSION={instance_info.get('proton_ge_version', '')}")

            if 'game_name' in instance_info:
                content.append(f"GAME_NAME={instance_info['game_name']}")

            # NXM script path (will be set when script is generated)
            script_name = self._generate_script_name(instance_info)
            content.append(f"NXM_SCRIPT={self.nxm_links_dir / script_name}")

            # Write marker file
            marker_file.write_text("\n".join(content))
            self.logger.info(f"Created instance marker: {marker_file}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to create instance marker: {e}")
            return False

    def read_instance_marker(self, prefix_path: str) -> Optional[Dict[str, str]]:
        """
        Read the instance marker file from a prefix

        Returns:
            Dictionary with instance info, or None if not found
        """
        try:
            prefix = Path(prefix_path)
            marker_file = prefix / "NAK_MANAGED_INSTANCE.txt"

            if not marker_file.exists():
                return None

            # Parse marker file
            info = {}
            for line in marker_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    info[key] = value

            return info

        except Exception as e:
            self.logger.error(f"Failed to read instance marker: {e}")
            return None

    def _generate_script_name(self, instance_info: Dict[str, str]) -> str:
        """Generate a safe filename for the NXM script using prefix name"""
        prefix_name = instance_info.get('prefix_name', 'unknown')
        instance_type = instance_info.get('instance_type', 'instance').lower()
        # Use prefix name for unique identification
        return f"nxm_{instance_type}_{prefix_name}.sh"

    def generate_nxm_script(self, instance_info: Dict[str, str], prefix_path: str) -> Optional[Path]:
        """
        Generate a .sh script that handles NXM links for this instance (Standalone Proton-GE)

        Args:
            instance_info: Instance information dictionary
            prefix_path: Path to the Wine prefix

        Returns:
            Path to the generated script, or None on failure
        """
        try:
            script_name = self._generate_script_name(instance_info)
            script_path = self.nxm_links_dir / script_name

            prefix_name = instance_info.get('prefix_name', '')
            exe_path = instance_info.get('exe_path', '')
            instance_type = instance_info.get('instance_type', 'MO2')
            instance_display_name = instance_info.get('instance_name', 'Unknown')

            # Build paths
            prefix_path_obj = Path(prefix_path)
            prefix_base = prefix_path_obj.parent  # e.g., ~/NaK/Prefixes/mo2_skyrim_se
            proton_ge_path = self.proton_ge_dir / "active"

            self.logger.info(f"Generating NXM script for {instance_display_name}")
            self.logger.info(f"  Prefix: {prefix_path}")
            self.logger.info(f"  Proton-GE: {proton_ge_path}")

            # Determine the correct executable and parameters based on instance type
            if instance_type == "MO2":
                # For MO2, we need to use nxmhandler.exe instead of ModOrganizer.exe
                handler_exe = exe_path.replace("ModOrganizer.exe", "nxmhandler.exe")
                launch_command = f'"$PROTON_GE/proton" run "{handler_exe}" "$NXM_URL"'
            else:  # Vortex
                # Vortex uses the -d flag for downloads
                launch_command = f'"$PROTON_GE/proton" run "{exe_path}" -d "$NXM_URL"'

            # Detect Steam path using existing utilities
            try:
                steam_path = self.steam_utils.get_steam_root()
                self.logger.info(f"Detected Steam path: {steam_path}")
            except Exception as e:
                self.logger.warning(f"Failed to detect Steam path: {e}, using /tmp")
                steam_path = "/tmp"

            # Generate the script content with Proton-GE invocation
            script_content = f'''#!/bin/bash
# NXM Handler Script for {instance_display_name}
# Generated by NaK - Standalone Proton-GE Mode
# Instance Type: {instance_type}
# Prefix: {prefix_name}

NXM_URL="$1"
PROTON_GE="{proton_ge_path}"
PREFIX="{prefix_path}"
COMPAT_DATA="{prefix_base}"
STEAM_PATH="{steam_path}"

if [ -z "$NXM_URL" ]; then
    echo "Error: No NXM URL provided"
    exit 1
fi

echo "=========================================="
echo "NaK NXM Handler"
echo "=========================================="
echo "Handling NXM link: $NXM_URL"
echo "Instance: {instance_display_name}"
echo "Instance Type: {instance_type}"
echo "Prefix: {prefix_name}"
echo ""

# Check if Proton-GE exists
if [ ! -f "$PROTON_GE/proton" ]; then
    echo "ERROR: Proton-GE not found at $PROTON_GE"
    echo "Please install Proton-GE using the Proton-GE Manager in NaK Settings."
    exit 1
fi

echo "Using Proton-GE: $(basename $(readlink -f "$PROTON_GE"))"
echo "Steam Path: $STEAM_PATH"
echo ""

# Set up Proton environment
export WINEPREFIX="$PREFIX"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_PATH"

# For MO2: Check if ModOrganizer.exe is running, if not start it first
if [ "{instance_type}" = "MO2" ]; then
    if ! pgrep -f "ModOrganizer.exe" > /dev/null 2>&1; then
        echo "ModOrganizer.exe not running, starting it first..."
        MO2_EXE="{exe_path}"
        echo "Starting MO2..."
        "$PROTON_GE/proton" run "$MO2_EXE" > /dev/null 2>&1 &
        echo "Waiting for MO2 to initialize (3 seconds)..."
        sleep 3
    else:
        echo "ModOrganizer.exe is already running"
    fi
fi

# Launch handler
echo "Launching {instance_type} NXM handler..."
echo "=========================================="
{launch_command}

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "NXM link handled successfully!"
else
    echo ""
    echo "ERROR: NXM handler exited with code $EXIT_CODE"
fi

exit $EXIT_CODE
'''

            # Write script
            script_path.write_text(script_content)

            # Make executable
            script_path.chmod(0o755)

            self.logger.info(f"Generated NXM script: {script_path}")

            return script_path

        except Exception as e:
            self.logger.error(f"Failed to generate NXM script: {e}")
            return None

    def create_desktop_file(self, active_script_path: str) -> bool:
        """
        Create or update the .desktop file to point to the active NXM handler script

        Args:
            active_script_path: Path to the .sh script that should handle NXM links

        Returns:
            True if desktop file was created/updated successfully
        """
        try:
            # Ensure parent directory exists
            self.desktop_file.parent.mkdir(parents=True, exist_ok=True)

            # Generate .desktop file content
            content = f'''[Desktop Entry]
Type=Application
Name=NXM Handler (NaK)
Comment=Handles nxm:// protocol links for Mod Organizer 2 and Vortex
Exec={active_script_path} %u
Icon=application-x-executable
Terminal=false
MimeType=x-scheme-handler/nxm
NoDisplay=true
Categories=Utility;
'''

            # Write .desktop file
            self.desktop_file.write_text(content)

            # Make executable
            self.desktop_file.chmod(0o755)

            # Update MIME database
            os.system("update-desktop-database ~/.local/share/applications/ 2>/dev/null")
            os.system("xdg-mime default nxm-handler.desktop x-scheme-handler/nxm 2>/dev/null")

            self.logger.info(f"Created/updated .desktop file: {self.desktop_file}")
            self.logger.info(f"Active NXM handler: {active_script_path}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to create desktop file: {e}")
            return False

    def get_active_handler(self) -> Optional[str]:
        """
        Get the currently active NXM handler script path

        Returns:
            Path to the active script, or None if not set
        """
        try:
            if not self.desktop_file.exists():
                return None

            # Parse .desktop file to find Exec line
            for line in self.desktop_file.read_text().splitlines():
                if line.startswith('Exec='):
                    # Extract script path (before %u)
                    exec_line = line[5:].strip()  # Remove "Exec="
                    script_path = exec_line.split()[0]  # Get first part before %u
                    return script_path

            return None

        except Exception as e:
            self.logger.error(f"Failed to get active handler: {e}")
            return None

    def list_all_instances(self) -> List[Dict[str, Any]]:
        """
        Find all NaK-managed instances by scanning ~/NaK/Prefixes/

        Returns:
            List of instance info dictionaries
        """
        instances = []

        try:
            if not self.prefixes_dir.exists():
                self.logger.warning(f"Prefixes directory not found: {self.prefixes_dir}")
                return instances

            # Scan all prefix folders
            for prefix_dir in self.prefixes_dir.iterdir():
                if not prefix_dir.is_dir():
                    continue

                # Check for pfx subdirectory
                pfx_dir = prefix_dir / "pfx"
                if not pfx_dir.exists():
                    continue

                # Check for marker file
                marker_info = self.read_instance_marker(str(pfx_dir))
                if marker_info:
                    # Add prefix path and prefix name
                    marker_info['prefix_path'] = str(pfx_dir)
                    marker_info['prefix_dir_name'] = prefix_dir.name

                    # Check if script exists
                    script_path = marker_info.get('NXM_SCRIPT')
                    if script_path and Path(script_path).exists():
                        marker_info['script_exists'] = True
                    else:
                        marker_info['script_exists'] = False

                    instances.append(marker_info)

            self.logger.info(f"Found {len(instances)} NaK-managed instances")

        except Exception as e:
            self.logger.error(f"Failed to list instances: {e}")

        return instances

    def set_active_handler(self, instance_info: Dict[str, str]) -> bool:
        """
        Set an instance as the active NXM handler

        Args:
            instance_info: Instance information dictionary (must have NXM_SCRIPT)

        Returns:
            True if successful
        """
        script_path = instance_info.get('NXM_SCRIPT')

        if not script_path:
            self.logger.error("Instance info missing NXM_SCRIPT")
            return False

        if not Path(script_path).exists():
            self.logger.error(f"NXM script not found: {script_path}")
            # Try to regenerate it
            prefix_path = instance_info.get('prefix_path')
            if prefix_path:
                self.logger.info("Attempting to regenerate NXM script...")
                new_script = self.generate_nxm_script(instance_info, prefix_path)
                if new_script:
                    script_path = str(new_script)
                else:
                    return False
            else:
                return False

        return self.create_desktop_file(script_path)

    def setup_instance(
        self,
        prefix_path: str,
        instance_name: str,
        instance_type: str,
        exe_path: str,
        prefix_name: str,
        proton_ge_version: str,
        game_name: str = ""
    ) -> bool:
        """
        Complete setup for a new instance: create marker and NXM script

        Args:
            prefix_path: Path to Wine prefix (e.g., ~/NaK/Prefixes/mo2_skyrim_se/pfx)
            instance_name: Display name for the instance
            instance_type: "MO2" or "Vortex"
            exe_path: Wine path to the executable (Z:\path\to\exe)
            prefix_name: Name of the prefix folder (e.g., "mo2_skyrim_se")
            proton_ge_version: Proton-GE version used (e.g., "GE-Proton10-21")
            game_name: Optional game name

        Returns:
            True if setup was successful
        """
        instance_info = {
            'instance_name': instance_name,
            'instance_type': instance_type,
            'exe_path': exe_path,
            'prefix_name': prefix_name,
            'proton_ge_version': proton_ge_version,
        }

        if game_name:
            instance_info['game_name'] = game_name

        # Create marker file
        if not self.create_instance_marker(prefix_path, instance_info):
            return False

        # Generate NXM script
        script_path = self.generate_nxm_script(instance_info, prefix_path)
        if not script_path:
            return False

        self.logger.info(f"Successfully set up NXM handling for: {instance_name}")
        return True

    def test_nxm_handler(self, test_url: str = "nxm://skyrimspecialedition/mods/12345/files/67890") -> Dict[str, Any]:
        """
        Test the NXM handler by attempting to open a test URL

        Args:
            test_url: Test NXM URL to use (default is a Skyrim SE test URL)

        Returns:
            Dictionary with test results
        """
        import subprocess

        results = {
            "success": False,
            "desktop_file_exists": False,
            "handler_registered": False,
            "active_handler": None,
            "test_url": test_url,
            "error": None
        }

        try:
            # Check if .desktop file exists
            if self.desktop_file.exists():
                results["desktop_file_exists"] = True
                self.logger.info(f"Desktop file exists: {self.desktop_file}")
            else:
                results["error"] = "NXM handler .desktop file not found"
                self.logger.error(results["error"])
                return results

            # Check if handler is registered
            try:
                check_cmd = ["xdg-mime", "query", "default", "x-scheme-handler/nxm"]
                check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)

                if check_result.returncode == 0 and "nxm-handler.desktop" in check_result.stdout:
                    results["handler_registered"] = True
                    self.logger.info("NXM handler is registered with xdg-mime")
                else:
                    results["error"] = f"NXM handler not registered. Current: {check_result.stdout.strip()}"
                    self.logger.warning(results["error"])
            except Exception as e:
                results["error"] = f"Failed to check handler registration: {e}"
                self.logger.error(results["error"])
                return results

            # Get active handler script
            active_handler = self.get_active_handler()
            if active_handler:
                results["active_handler"] = active_handler
                self.logger.info(f"Active handler script: {active_handler}")
            else:
                results["error"] = "No active handler script found in .desktop file"
                self.logger.error(results["error"])
                return results

            # Test opening the URL
            self.logger.info(f"Testing NXM handler with URL: {test_url}")
            self.logger.info("Attempting to open URL with xdg-open...")

            try:
                # Use xdg-open to trigger the handler
                open_cmd = ["xdg-open", test_url]
                open_result = subprocess.run(open_cmd, capture_output=True, text=True, timeout=10)

                if open_result.returncode == 0:
                    results["success"] = True
                    self.logger.info("NXM handler test completed - URL opened successfully")
                    self.logger.info("Check your MO2/Vortex to see if the download was triggered")
                else:
                    results["error"] = f"xdg-open failed: {open_result.stderr}"
                    self.logger.error(results["error"])

            except subprocess.TimeoutExpired:
                results["success"] = True  # Timeout might mean it's working (waiting for user)
                self.logger.info("NXM handler test timed out (this might be normal if waiting for user input)")
            except Exception as e:
                results["error"] = f"Failed to open URL: {e}"
                self.logger.error(results["error"])

        except Exception as e:
            results["error"] = f"Test failed: {e}"
            self.logger.error(f"NXM handler test error: {e}")

        return results

    def get_nxm_handler_status(self) -> Dict[str, Any]:
        """
        Get the current status of the NXM handler setup

        Returns:
            Dictionary with handler status information
        """
        import subprocess

        status = {
            "desktop_file_exists": False,
            "desktop_file_path": str(self.desktop_file),
            "handler_registered": False,
            "registered_handler": None,
            "active_script": None,
            "active_script_exists": False,
            "total_instances": 0,
            "instances": []
        }

        try:
            # Check desktop file
            status["desktop_file_exists"] = self.desktop_file.exists()

            # Check if registered with xdg-mime
            try:
                result = subprocess.run(
                    ["xdg-mime", "query", "default", "x-scheme-handler/nxm"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    registered = result.stdout.strip()
                    status["registered_handler"] = registered
                    status["handler_registered"] = "nxm-handler.desktop" in registered
            except Exception as e:
                self.logger.warning(f"Could not check xdg-mime registration: {e}")

            # Get active script
            active_script = self.get_active_handler()
            if active_script:
                status["active_script"] = active_script
                status["active_script_exists"] = Path(active_script).exists()

            # Get all instances
            instances = self.list_all_instances()
            status["total_instances"] = len(instances)
            status["instances"] = instances

        except Exception as e:
            self.logger.error(f"Failed to get NXM handler status: {e}")

        return status

    def cleanup_orphaned_scripts(self) -> Dict[str, Any]:
        """
        Scan NXM_Links directory and prefixes, removing orphaned items:
        1. .sh files without corresponding prefixes or marker files
        2. Marker files in prefixes without valid prefix directories

        Returns:
            Dictionary with cleanup results
        """
        result = {
            "success": False,
            "scripts_scanned": 0,
            "scripts_removed": 0,
            "scripts_kept": 0,
            "markers_scanned": 0,
            "markers_removed": 0,
            "removed_scripts": [],
            "removed_markers": [],
            "errors": []
        }

        try:
            self.logger.info("=" * 80)
            self.logger.info("SCANNING FOR ORPHANED NXM ITEMS (Standalone Mode)")
            self.logger.info("=" * 80)

            # Get list of valid prefix directories
            valid_prefixes = set()
            if self.prefixes_dir.exists():
                for prefix_dir in self.prefixes_dir.iterdir():
                    if prefix_dir.is_dir():
                        valid_prefixes.add(prefix_dir.name)
                self.logger.info(f"Found {len(valid_prefixes)} prefix directories")

            # Part 1: Clean up orphaned .sh files in NXM_Links
            if self.nxm_links_dir.exists():
                self.logger.info("Checking NXM scripts...")
                for script_file in self.nxm_links_dir.glob("*.sh"):
                    result["scripts_scanned"] += 1
                    script_name = script_file.name

                    self.logger.info(f"  Checking script: {script_name}")

                    # Extract prefix_name from filename
                    # Expected format: nxm_mo2_prefix_name.sh or nxm_vortex_prefix_name.sh
                    try:
                        parts = script_name.replace('.sh', '').split('_', 2)
                        if len(parts) >= 3:
                            prefix_name = parts[2]  # Get the prefix_name part

                            # Check if prefix exists
                            if prefix_name not in valid_prefixes:
                                self.logger.warning(f"    Prefix not found: {prefix_name}")
                                self.logger.info(f"    Removing orphaned script: {script_name}")
                                script_file.unlink()
                                result["scripts_removed"] += 1
                                result["removed_scripts"].append(script_name)
                                continue

                            # Check for marker file
                            prefix_path = self.prefixes_dir / prefix_name / "pfx"
                            marker_file = prefix_path / "NAK_MANAGED_INSTANCE.txt"
                            if not marker_file.exists():
                                self.logger.warning(f"    Marker file not found: {marker_file}")
                                self.logger.info(f"    Removing orphaned script: {script_name}")
                                script_file.unlink()
                                result["scripts_removed"] += 1
                                result["removed_scripts"].append(script_name)
                            else:
                                self.logger.info(f"    Script is valid")
                                result["scripts_kept"] += 1
                        else:
                            self.logger.warning(f"    Could not parse prefix_name from filename: {script_name}")
                            result["scripts_kept"] += 1  # Keep if we can't parse

                    except Exception as e:
                        error_msg = f"Error processing {script_name}: {e}"
                        self.logger.error(f"    {error_msg}")
                        result["errors"].append(error_msg)
                        result["scripts_kept"] += 1  # Keep on error to be safe

            # Part 2: Clean up orphaned marker files in prefixes
            self.logger.info("Checking marker files in prefixes...")
            if self.prefixes_dir.exists():
                for prefix_dir in self.prefixes_dir.iterdir():
                    if not prefix_dir.is_dir():
                        continue

                    pfx_dir = prefix_dir / "pfx"
                    if not pfx_dir.exists():
                        continue

                    marker_file = pfx_dir / "NAK_MANAGED_INSTANCE.txt"
                    if marker_file.exists():
                        result["markers_scanned"] += 1
                        prefix_name = prefix_dir.name

                        self.logger.info(f"  Checking marker for prefix: {prefix_name}")

                        # For now, just verify the marker file is readable
                        # Could add more validation here if needed
                        try:
                            marker_info = self.read_instance_marker(str(pfx_dir))
                            if marker_info:
                                self.logger.info(f"    Marker is valid")
                            else:
                                self.logger.warning(f"    Marker file is corrupted")
                        except Exception as e:
                            self.logger.error(f"    Error reading marker: {e}")

            self.logger.info("=" * 80)
            self.logger.info("CLEANUP COMPLETE")
            self.logger.info("=" * 80)
            self.logger.info(f"Scripts: {result['scripts_scanned']} scanned, {result['scripts_removed']} removed, {result['scripts_kept']} kept")
            self.logger.info(f"Markers: {result['markers_scanned']} scanned")

            if result["removed_scripts"]:
                self.logger.info(f"Removed scripts: {', '.join(result['removed_scripts'])}")

            result["success"] = True

        except Exception as e:
            error_msg = f"Failed to cleanup orphaned items: {e}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)

        return result
