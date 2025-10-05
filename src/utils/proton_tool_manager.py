"""
Proton Tool Manager
Handles automatic Proton tool setting for Steam games
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, List
try:
    import vdf
    VDF_AVAILABLE = True
except ImportError:
    VDF_AVAILABLE = False
    vdf = None

class ProtonToolManager:
    """Manages Proton tool selection for Steam games"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.steam_root = self._find_steam_root()
        self.user_id = self._find_steam_user_id()
        
    def _find_steam_root(self) -> str:
        """Find Steam installation directory"""
        home_dir = Path.home()
        
        candidates = [
            home_dir / ".local" / "share" / "Steam",
            home_dir / ".steam" / "steam",
            home_dir / ".steam" / "debian-installation",
            Path("/usr/local/steam"),
            Path("/usr/share/steam"),
        ]
        
        for candidate in candidates:
            if candidate.exists():
                self.logger.info(f"Found Steam root: {candidate}")
                return str(candidate)
        
        raise RuntimeError("Could not find Steam installation")
    
    def _find_steam_user_id(self) -> str:
        """Find Steam user ID"""
        userdata_path = Path(self.steam_root) / "userdata"
        if not userdata_path.exists():
            raise RuntimeError("Could not find Steam userdata directory")
        
        # Find the first user directory
        for user_dir in userdata_path.iterdir():
            if user_dir.is_dir() and user_dir.name.isdigit():
                self.logger.info(f"Found Steam user ID: {user_dir.name}")
                return user_dir.name
        
        raise RuntimeError("Could not find Steam user ID")
    
    def set_proton_tool(self, app_id: str, proton_tool: str = "proton_experimental") -> bool:
        """Set Proton tool for a specific app"""
        try:
            # Register NaK as a compatibility tool first
            self._register_nak_compatibility_tool()
            
            # Update compat.vdf to enable Linux compatibility
            self._update_compat_vdf(app_id)
            
            # Update localconfig.vdf to set the actual Proton tool
            self._update_localconfig_vdf(app_id, proton_tool)
            
            # Store the actual Proton tool preference in our own config
            self._store_proton_preference(app_id, proton_tool)
            
            self.logger.info(f"Successfully set {proton_tool} for app {app_id} via NaK compatibility tool")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set Proton tool for app {app_id}: {e}")
            return False
    
    def _update_compat_vdf(self, app_id: str) -> None:
        """Update compat.vdf to enable Linux compatibility"""
        compat_path = Path(self.steam_root) / "userdata" / self.user_id / "config" / "compat.vdf"
        
        # Create directory if it doesn't exist
        compat_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or create new one
        if compat_path.exists():
            with open(compat_path, 'r') as f:
                config = vdf.load(f)
        else:
            config = {"platform_overrides": {}}
        
        # Ensure platform_overrides exists
        if "platform_overrides" not in config:
            config["platform_overrides"] = {}
        
        # Add or update the app entry
        config["platform_overrides"][app_id] = {
            "dest": "linux",
            "src": "windows"
        }
        
        # Write back to file
        with open(compat_path, 'w') as f:
            vdf.dump(config, f, pretty=True)
        
        self.logger.info(f"Updated compat.vdf for app {app_id}")
    
    def _update_localconfig_vdf(self, app_id: str, proton_tool: str) -> None:
        """Update localconfig.vdf to set the specific Proton tool"""
        localconfig_path = Path(self.steam_root) / "userdata" / self.user_id / "config" / "localconfig.vdf"
        
        # Create directory if it doesn't exist
        localconfig_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or create new one
        if localconfig_path.exists():
            with open(localconfig_path, 'r') as f:
                config = vdf.load(f)
        else:
            config = {"UserLocalConfigStore": {"Software": {"Valve": {"Steam": {}}}}}
        
        # Navigate to the correct section
        if "UserLocalConfigStore" not in config:
            config["UserLocalConfigStore"] = {}
        if "Software" not in config["UserLocalConfigStore"]:
            config["UserLocalConfigStore"]["Software"] = {}
        if "Valve" not in config["UserLocalConfigStore"]["Software"]:
            config["UserLocalConfigStore"]["Software"]["Valve"] = {}
        if "Steam" not in config["UserLocalConfigStore"]["Software"]["Valve"]:
            config["UserLocalConfigStore"]["Software"]["Valve"]["Steam"] = {}
        
        # Add compatibility tool setting
        steam_config = config["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]
        
        if "CompatToolMapping" not in steam_config:
            steam_config["CompatToolMapping"] = {}
        
        steam_config["CompatToolMapping"][app_id] = {
            "name": proton_tool,
            "config": "",
            "priority": "250"
        }
        
        # Write back to file
        with open(localconfig_path, 'w') as f:
            vdf.dump(config, f, pretty=True)
        
        self.logger.info(f"Updated localconfig.vdf for app {app_id} with {proton_tool}")
    
    def get_proton_tool(self, app_id: str) -> Optional[str]:
        """Get the currently set Proton tool for an app"""
        try:
            localconfig_path = Path(self.steam_root) / "userdata" / self.user_id / "config" / "localconfig.vdf"
            
            if not localconfig_path.exists():
                return None
            
            with open(localconfig_path, 'r') as f:
                config = vdf.load(f)
            
            # Navigate to the compatibility tool mapping
            try:
                compat_mapping = config["UserLocalConfigStore"]["Software"]["Valve"]["Steam"]["CompatToolMapping"]
                if app_id in compat_mapping:
                    return compat_mapping[app_id]["name"]
            except KeyError:
                pass
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get Proton tool for app {app_id}: {e}")
            return None
    
    def list_available_proton_tools(self) -> List[str]:
        """List available Proton tools"""
        tools = []
        
        # Check for official Proton versions
        proton_path = Path(self.steam_root) / "steamapps" / "common"
        for proton_dir in proton_path.iterdir():
            if proton_dir.name.startswith("Proton"):
                tools.append(proton_dir.name)
        
        # Check for custom Proton tools
        compat_tools_path = Path(self.steam_root) / "compatibilitytools.d"
        if compat_tools_path.exists():
            for tool_dir in compat_tools_path.iterdir():
                if tool_dir.is_dir():
                    tools.append(tool_dir.name)
        
        return sorted(tools)
    
    def load_reg_file(self, app_id: str, reg_file_path: str) -> bool:
        """Load a reg file to a Proton prefix"""
        try:
            # Find the compatdata path
            compatdata_path = self._find_compatdata_path(app_id)
            if not compatdata_path:
                self.logger.error(f"Could not find compatdata for app {app_id}")
                return False
            
            # Find Proton installation
            proton_path = self._find_proton_installation()
            if not proton_path:
                self.logger.error("Could not find Proton installation")
                return False
            
            # Set up environment variables
            env = os.environ.copy()
            env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = self.steam_root
            env['STEAM_COMPAT_DATA_PATH'] = compatdata_path
            
            # Execute regedit command
            result = subprocess.run([
                proton_path, "run", "regedit", reg_file_path
            ], env=env, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                self.logger.info(f"Successfully loaded reg file {reg_file_path} to app {app_id}")
                return True
            else:
                self.logger.error(f"Regedit failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to load reg file for app {app_id}: {e}")
            return False
    
    def _find_compatdata_path(self, app_id: str) -> Optional[str]:
        """Find the compatibility data path for an app"""
        try:
            # Check main Steam library
            compatdata_path = Path(self.steam_root) / "steamapps" / "compatdata" / app_id
            if compatdata_path.exists():
                return str(compatdata_path)
            
            # Check additional Steam libraries
            libraryfolders_path = Path(self.steam_root) / "steamapps" / "libraryfolders.vdf"
            if libraryfolders_path.exists():
                with open(libraryfolders_path, 'r') as f:
                    content = f.read()
                    lines = content.split("\n")
                    for line in lines:
                        if '"path"' in line:
                            parts = line.split('"')
                            if len(parts) >= 4:
                                library_path = parts[3]
                                compatdata_path = Path(library_path) / "steamapps" / "compatdata" / app_id
                                if compatdata_path.exists():
                                    return str(compatdata_path)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to find compatdata for app {app_id}: {e}")
            return None
    
    def _find_proton_installation(self) -> Optional[str]:
        """Find Proton installation path"""
        try:
            # Look for Proton Experimental first
            proton_path = Path(self.steam_root) / "steamapps" / "common" / "Proton - Experimental" / "proton"
            if proton_path.exists():
                return str(proton_path)
            
            # Fallback to any available Proton version
            common_path = Path(self.steam_root) / "steamapps" / "common"
            for proton_dir in common_path.iterdir():
                if proton_dir.name.startswith("Proton"):
                    proton_path = proton_dir / "proton"
                    if proton_path.exists():
                        return str(proton_path)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to find Proton installation: {e}")
            return None
    
    def _register_nak_compatibility_tool(self) -> None:
        """Register NaK as a Steam compatibility tool"""
        compat_tools_dir = Path(self.steam_root) / "compatibilitytools.d" / "NaK-Proton-Manager"
        compat_tools_dir.mkdir(parents=True, exist_ok=True)
        
        # Create compatibility tool VDF
        compat_vdf_content = '''
"compatibilitytools"
{
  "compat_tools"
  {
        "NaK-Proton-Manager" // Internal name of this tool
        {
          "install_path" "."
          "display_name" "NaK Proton Manager"

          "from_oslist"  "windows"
          "to_oslist"    "linux"
        }
  }
}
'''
        
        compat_vdf_path = compat_tools_dir / "compatibilitytool.vdf"
        with open(compat_vdf_path, 'w') as f:
            f.write(compat_vdf_content.strip())
        
        # Create tool manifest
        manifest_content = '''
"manifest"
{
    "version" "2"
    "commandline" "/NaK-Proton-Manager/nak-proton-wrapper"
}
'''
        
        manifest_path = compat_tools_dir / "toolmanifest.vdf"
        with open(manifest_path, 'w') as f:
            f.write(manifest_content.strip())
        
        # Create wrapper script
        wrapper_script = f'''#!/bin/bash
# NaK Proton Manager Wrapper Script

APP_ID="$1"
COMMAND="$2"
shift 2

# Get the actual Proton tool preference for this app
PROTON_TOOL=$(python3 {Path(__file__).parent.parent.parent / "proton_manager_cli.py"} get-preference "$APP_ID")

if [ -z "$PROTON_TOOL" ]; then
    PROTON_TOOL="proton_experimental"
fi

# Find the actual Proton installation
PROTON_PATH="{self.steam_root}/steamapps/common/Proton - Experimental/proton"

if [ ! -f "$PROTON_PATH" ]; then
    # Fallback to any available Proton
    PROTON_PATH="{self.steam_root}/steamapps/common/Proton - Experimental/proton"
fi

# Execute with the actual Proton tool
exec "$PROTON_PATH" "$COMMAND" "$@"
'''
        
        wrapper_path = compat_tools_dir / "nak-proton-wrapper"
        with open(wrapper_path, 'w') as f:
            f.write(wrapper_script)
        
        # Make wrapper executable
        wrapper_path.chmod(0o755)
        
        self.logger.info("Registered NaK as Steam compatibility tool")
    
    def _store_proton_preference(self, app_id: str, proton_tool: str) -> None:
        """Store Proton tool preference for an app"""
        config_dir = Path.home() / ".config" / "nak-proton-manager"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = config_dir / "app_preferences.json"
        
        # Load existing preferences
        preferences = {}
        if config_file.exists():
            with open(config_file, 'r') as f:
                preferences = json.load(f)
        
        # Update preference
        preferences[app_id] = proton_tool
        
        # Save preferences
        with open(config_file, 'w') as f:
            json.dump(preferences, f, indent=2)
        
        self.logger.info(f"Stored Proton preference: {app_id} -> {proton_tool}")
    
    def get_proton_preference(self, app_id: str) -> Optional[str]:
        """Get stored Proton tool preference for an app"""
        config_file = Path.home() / ".config" / "nak-proton-manager" / "app_preferences.json"
        
        if not config_file.exists():
            return None
        
        try:
            with open(config_file, 'r') as f:
                preferences = json.load(f)
            return preferences.get(app_id)
        except Exception as e:
            self.logger.error(f"Failed to get Proton preference for app {app_id}: {e}")
            return None
