"""
Steam Shortcut Manager
Handles automatic non-Steam game app ID generation and prefix creation
Migrated from the Go implementation
"""

import os
import subprocess
import time
import logging
import struct
import zlib
import vdf
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

@dataclass
class SteamShortcut:
    """Represents a Steam shortcut entry"""
    index: str = ""
    app_id: int = 0
    app_name: str = ""
    exe: str = ""
    start_dir: str = ""
    icon: str = ""
    shortcut_path: str = ""
    launch_options: str = ""
    is_hidden: int = 0
    allow_desktop_config: int = 1
    allow_overlay: int = 1
    open_vr: int = 0
    devkit: int = 0
    devkit_game_id: str = ""
    devkit_override_app_id: int = 0
    last_play_time: int = 0
    flatpak_app_id: str = ""
    tags: Dict[str, str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}

class SteamShortcutManager:
    """Manages Steam shortcuts with automatic app ID generation and prefix creation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.steam_path = None
        self.user_id = None
        self.user_data_path = None
        self._initialize_steam_paths()
    
    def _initialize_steam_paths(self):
        """Initialize Steam paths"""
        try:
            self.steam_path = self._find_steam_path()
            self.user_id, self.user_data_path = self._find_latest_user(self.steam_path)
            self.logger.info(f"Steam paths initialized: {self.steam_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Steam paths: {e}")
            raise
    
    def _find_steam_path(self) -> str:
        """Find Steam installation directory"""
        home_dir = Path.home()
        
        candidates = [
            home_dir / ".local" / "share" / "Steam",
            home_dir / ".steam" / "steam",
            home_dir / ".steam" / "debian-installation",
            home_dir / ".steam" / "root",
            Path("/usr/share/steam"),
            Path("/opt/steam"),
        ]
        
        # Check environment variable
        if steam_root := os.getenv("STEAM_ROOT"):
            candidates.insert(0, Path(steam_root))
        
        for path in candidates:
            if self._is_valid_steam_path(path):
                return str(path)
        
        raise RuntimeError("Steam installation not found")
    
    def _is_valid_steam_path(self, path: Path) -> bool:
        """Check if path contains a valid Steam installation"""
        user_data_path = path / "userdata"
        return user_data_path.exists() and user_data_path.is_dir()
    
    def _find_latest_user(self, steam_path: str) -> Tuple[str, str]:
        """Find the most recently used Steam user"""
        user_data_path = Path(steam_path) / "userdata"
        
        if not user_data_path.exists():
            raise RuntimeError("Steam userdata directory not found")
        
        latest_user = None
        latest_time = 0
        
        for entry in user_data_path.iterdir():
            if not entry.is_dir():
                continue
            
            # Check if directory name is numeric (user ID)
            if not entry.name.isdigit():
                continue
            
            # Check modification time
            mtime = entry.stat().st_mtime
            if mtime > latest_time:
                latest_time = mtime
                latest_user = entry.name
        
        if not latest_user:
            raise RuntimeError("No Steam user found")
        
        user_path = user_data_path / latest_user
        return latest_user, str(user_path)
    
    def get_shortcuts_path(self) -> str:
        """Get path to shortcuts.vdf"""
        return str(Path(self.user_data_path) / "config" / "shortcuts.vdf")
    
    def get_config_path(self) -> str:
        """Get path to config.vdf"""
        return str(Path(self.steam_path) / "config" / "config.vdf")
    
    def generate_app_id(self, app_name: str, exe_path: str) -> int:
        """Generate a deterministic AppID for a non-Steam game"""
        combined = exe_path + app_name + "\x00"
        crc = zlib.crc32(combined.encode('utf-8'))
        # Match Go implementation exactly: crc | 0x80000000
        # Return as unsigned 32-bit integer (Steam AppIDs are unsigned)
        return (crc & 0xFFFFFFFF) | 0x80000000
    
    def list_shortcuts(self) -> List[SteamShortcut]:
        """Read and return all non-Steam game shortcuts"""
        shortcuts_path = self.get_shortcuts_path()
        
        if not os.path.exists(shortcuts_path):
            return []
        
        try:
            with open(shortcuts_path, 'rb') as f:
                data = vdf.binary_load(f)
            
            shortcuts = []
            shortcuts_data = data.get('shortcuts', {})
            
            for index, shortcut_data in shortcuts_data.items():
                # Convert signed AppID back to unsigned if needed
                app_id_raw = shortcut_data.get('appid', 0)
                if app_id_raw < 0:
                    app_id = app_id_raw + 4294967296  # Convert signed back to unsigned
                else:
                    app_id = app_id_raw
                
                shortcut = SteamShortcut(
                    index=index,
                    app_id=app_id,
                    app_name=shortcut_data.get('AppName', ''),
                    exe=shortcut_data.get('Exe', ''),
                    start_dir=shortcut_data.get('StartDir', ''),
                    icon=shortcut_data.get('icon', ''),
                    shortcut_path=shortcut_data.get('ShortcutPath', ''),
                    launch_options=shortcut_data.get('LaunchOptions', ''),
                    is_hidden=shortcut_data.get('IsHidden', 0),
                    allow_desktop_config=shortcut_data.get('AllowDesktopConfig', 1),
                    allow_overlay=shortcut_data.get('AllowOverlay', 1),
                    open_vr=shortcut_data.get('OpenVR', 0),
                    devkit=shortcut_data.get('Devkit', 0),
                    devkit_game_id=shortcut_data.get('DevkitGameID', ''),
                    devkit_override_app_id=shortcut_data.get('DevkitOverrideAppID', 0),
                    last_play_time=shortcut_data.get('LastPlayTime', 0),
                    flatpak_app_id=shortcut_data.get('FlatpakAppID', '')
                )
                shortcuts.append(shortcut)
            
            return shortcuts
        except Exception as e:
            self.logger.error(f"Failed to read shortcuts file: {e}")
            self.logger.info("Creating new shortcuts file from scratch")
            return []
    

    

    
    def create_steam_shortcut(self, app_name: str, exe_path: str, proton_tool: str = "proton_experimental") -> int:
        """Create a Steam shortcut and return the generated AppID"""
        # Generate AppID
        app_id = self.generate_app_id(app_name, exe_path)
        self.logger.info(f"Generated AppID: {app_id} (hex: {app_id:08x})")
        
        # Create shortcut object
        # Add quotes around exe path and start dir if not present (matches Go implementation)
        exe_path_quoted = exe_path if exe_path.startswith('"') else f'"{exe_path}"'
        start_dir = str(Path(exe_path).parent)
        start_dir_quoted = start_dir if not start_dir or start_dir.startswith('"') else f'"{start_dir}"'
        
        shortcut = SteamShortcut(
            app_name=app_name,
            exe=exe_path_quoted,
            start_dir=start_dir_quoted,
            app_id=app_id,
            last_play_time=int(time.time()),
            allow_desktop_config=1,
            allow_overlay=1
        )
        
        # Read existing shortcuts
        shortcuts = self.list_shortcuts()
        
        # Check if already exists (exact match: same name, exe, and start dir)
        for i, existing in enumerate(shortcuts):
            if (existing.app_name == shortcut.app_name and
                existing.exe == shortcut.exe and
                existing.start_dir == shortcut.start_dir):
                # Update existing
                shortcuts[i] = shortcut
                break
        else:
            # Add as new - use the next available index
            next_index = len(shortcuts)
            shortcut.index = str(next_index)
            shortcuts.append(shortcut)
        
        # Write shortcuts back
        self._write_shortcuts(shortcuts)
        
        # Set compatibility tool if specified
        if proton_tool:
            try:
                self.logger.info(f"Setting compatibility tool '{proton_tool}' for AppID {app_id}")
                self._set_compatibility_tool(app_id, proton_tool)
                self.logger.info(f"Successfully set compatibility tool '{proton_tool}' for AppID {app_id}")
            except Exception as e:
                self.logger.warning(f"Could not set compatibility tool: {e}")
        else:
            self.logger.info(f"No compatibility tool specified for AppID {app_id} - Steam will use default behavior")
        
        return app_id
    
    def add_single_shortcut(self, app_name: str, exe_path: str, proton_tool: str = "proton_experimental") -> int:
        """Add a single shortcut without affecting existing ones - safer approach"""
        # Generate AppID
        app_id = self.generate_app_id(app_name, exe_path)
        
        # Create shortcut object
        # Add quotes around exe path and start dir if not present (matches Go implementation)
        exe_path_quoted = exe_path if exe_path.startswith('"') else f'"{exe_path}"'
        start_dir = str(Path(exe_path).parent)
        start_dir_quoted = start_dir if not start_dir or start_dir.startswith('"') else f'"{start_dir}"'
        
        # Generate STEAM_COMPAT_MOUNTS for cross-library compatibility
        compat_mounts = self.create_steam_compat_mounts_string()
        launch_options = f"{compat_mounts} %command%" if compat_mounts else ""
        
        if launch_options:
            self.logger.info(f"Adding STEAM_COMPAT_MOUNTS to launch options: {launch_options}")
        
        shortcut = SteamShortcut(
            app_name=app_name,
            exe=exe_path_quoted,
            start_dir=start_dir_quoted,
            app_id=app_id,
            launch_options=launch_options,
            last_play_time=int(time.time()),
            allow_desktop_config=1,
            allow_overlay=1
        )
        
        # Read existing shortcuts
        shortcuts = self.list_shortcuts()
        
        # Check if already exists
        for existing in shortcuts:
            if (existing.app_name == shortcut.app_name and
                existing.exe == shortcut.exe and
                existing.start_dir == shortcut.start_dir):
                self.logger.info(f"Shortcut already exists: {app_name}")
                return existing.app_id
        
        # Add as new - use the next available index
        next_index = len(shortcuts)
        shortcut.index = str(next_index)
        shortcuts.append(shortcut)
        
        # Write shortcuts back
        self._write_shortcuts(shortcuts)
        
        # Set compatibility tool if specified
        if proton_tool:
            try:
                self.logger.info(f"Setting compatibility tool '{proton_tool}' for AppID {app_id}")
                self._set_compatibility_tool(app_id, proton_tool)
                self.logger.info(f"Successfully set compatibility tool '{proton_tool}' for AppID {app_id}")
            except Exception as e:
                self.logger.warning(f"Could not set compatibility tool: {e}")
        else:
            self.logger.info(f"No compatibility tool specified for AppID {app_id} - Steam will use default behavior")
        
        self.logger.info(f"Added new shortcut: {app_name} (AppID: {app_id})")
        return app_id
    
    def _write_shortcuts(self, shortcuts: List[SteamShortcut]):
        """Write shortcuts to the VDF file"""
        shortcuts_path = self.get_shortcuts_path()
        
        # Ensure directory exists
        shortcuts_dir = Path(shortcuts_path).parent
        shortcuts_dir.mkdir(parents=True, exist_ok=True)
        
        # Create backup with timestamp
        if os.path.exists(shortcuts_path):
            timestamp = int(time.time())
            backup_path = shortcuts_path + f".bak.{timestamp}"
            with open(shortcuts_path, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
            self.logger.info(f"Created backup: {backup_path}")
        
        # Convert shortcuts to VDF format
        shortcuts_dict = {}
        for shortcut in shortcuts:
            # Convert unsigned AppID to signed for VDF library compatibility
            # Steam AppIDs are unsigned, but Python VDF library expects signed
            if shortcut.app_id > 2147483647:  # Max signed int32
                app_id_signed = shortcut.app_id - 4294967296  # Convert to signed
            else:
                app_id_signed = shortcut.app_id
            
            shortcuts_dict[shortcut.index] = {
                'appid': app_id_signed,
                'AppName': shortcut.app_name,
                'Exe': shortcut.exe,
                'StartDir': shortcut.start_dir,
                'icon': shortcut.icon,
                'ShortcutPath': shortcut.shortcut_path,
                'LaunchOptions': shortcut.launch_options,
                'IsHidden': shortcut.is_hidden,
                'AllowDesktopConfig': shortcut.allow_desktop_config,
                'AllowOverlay': shortcut.allow_overlay,
                'OpenVR': shortcut.open_vr,
                'Devkit': shortcut.devkit,
                'DevkitGameID': shortcut.devkit_game_id,
                'DevkitOverrideAppID': shortcut.devkit_override_app_id,
                'LastPlayTime': shortcut.last_play_time,
                'FlatpakAppID': shortcut.flatpak_app_id,
                'tags': {}
            }
        
        # Create VDF data structure
        data = {'shortcuts': shortcuts_dict}
        
        # Write file using VDF library
        with open(shortcuts_path, 'wb') as f:
            vdf.binary_dump(data, f)
        
        self.logger.info(f"Wrote {len(shortcuts)} shortcuts to file")
    

    
    def _set_compatibility_tool(self, app_id: int, tool_name: str):
        """Set the Proton/compatibility tool for an AppID"""
        config_path = self.get_config_path()
        self.logger.info(f"Setting compatibility tool '{tool_name}' for AppID {app_id} in config: {config_path}")
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Find CompatToolMapping section
        import re
        pattern = r'"CompatToolMapping"\s*{([^{}]*(?:{[^{}]*}[^{}]*)*)}\s*'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if not match:
            self.logger.info("CompatToolMapping section not found, creating it...")
            # Find the end of the config file and add CompatToolMapping section
            # Look for the last closing brace before the end
            last_brace_pos = content.rfind('}')
            if last_brace_pos == -1:
                self.logger.error("Could not find end of config.vdf")
                raise RuntimeError("Invalid config.vdf format")
            
            # Insert CompatToolMapping section before the last closing brace
            compat_section = '''
	"CompatToolMapping"
	{
	}
'''
            content = content[:last_brace_pos] + compat_section + "\n" + content[last_brace_pos:]
            
            # Re-search for the section we just created
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if not match:
                self.logger.error("Failed to create CompatToolMapping section")
                raise RuntimeError("Failed to create CompatToolMapping section")
        
        # Build new entry - use AppID as-is (it's already unsigned)
        app_id_str = str(app_id)
        new_entry = f'''
	"{app_id_str}"
	{{
	"name"		"{tool_name}"
	"config"		""
	"priority"		"250"
}}'''
        
        # Check if AppID already exists in the CompatToolMapping section
        compat_section_start = match.start(1)
        compat_section_end = match.end(1)
        compat_section_content = content[compat_section_start:compat_section_end]
        
        if f'"{app_id_str}"' in compat_section_content:
            # Update existing
            entry_pattern = rf'"{app_id_str}"\s*{{[^}}]*}}'
            content = re.sub(entry_pattern, new_entry.strip(), content)
        else:
            # Insert new entry before the closing brace of CompatToolMapping
            insert_pos = match.end(1)
            content = content[:insert_pos] + new_entry + "\n" + content[insert_pos:]
        
        # Write back
        with open(config_path, 'w') as f:
            f.write(content)
        
        self.logger.info(f"Successfully wrote compatibility tool '{tool_name}' for AppID {app_id} to config.vdf")
    
    def create_compat_data_folder(self, app_id: int) -> str:
        """Create the Steam compatdata folder for the game"""
        compat_data_path = Path(self.steam_path) / "steamapps" / "compatdata" / str(app_id)
        
        self.logger.info(f"Creating compatdata folder: {compat_data_path}")
        
        # Create the compatdata directory
        compat_data_path.mkdir(parents=True, exist_ok=True)
        
        # Create the pfx directory (Wine prefix)
        pfx_path = compat_data_path / "pfx"
        pfx_path.mkdir(exist_ok=True)
        
        self.logger.info(f"✅ Created compatdata folder: {compat_data_path}")
        return str(compat_data_path)
    
    def create_and_run_bat_file(self, compat_data_path: str, app_name: str) -> bool:
        """Create a .bat file in the compatdata folder and run it with Proton"""
        self.logger.info(f"🚀 Starting .bat file creation and execution for: {app_name}")
        self.logger.info(f"📁 Compatdata path: {compat_data_path}")
        
        # Create the .bat file content
        bat_content = """@echo off
echo Creating Proton prefix...
timeout /t 5 /nobreak >nul
echo Prefix creation complete."""
        
        # Write the .bat file to the compatdata folder
        bat_path = Path(compat_data_path) / "run-mo2.bat"
        self.logger.info(f"📝 Writing .bat file to: {bat_path}")
        
        with open(bat_path, 'w') as f:
            f.write(bat_content)
        
        # Make executable
        bat_path.chmod(0o755)
        
        self.logger.info(f"✅ .bat file created successfully: {bat_path}")
        
        # Find Proton installation
        self.logger.info("🔍 Searching for Proton installation...")
        proton_path = self._find_proton_installation("Proton - Experimental")
        
        if not proton_path:
            self.logger.warning("⚠️  Proton Experimental not found")
            # Fallback to any available Proton version
            self.logger.info("🔄 Falling back to any available Proton version...")
            available_versions = self._get_all_available_proton_versions()
            if not available_versions:
                raise RuntimeError("Could not find any Proton installation")
            proton_path = self._find_proton_installation(available_versions[0])
            if not proton_path:
                raise RuntimeError("Could not find Proton installation")
            self.logger.info(f"✅ Using Proton version: {available_versions[0]}")
        else:
            self.logger.info(f"✅ Using Proton Experimental: {proton_path}")
        
        # Set up environment variables for Proton
        env = os.environ.copy()
        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = self.steam_path
        env["STEAM_COMPAT_DATA_PATH"] = compat_data_path
        env["DISPLAY"] = ""  # Prevent cmd popup when running with Proton wrapper
        
        self.logger.info("🔧 Environment variables set")
        
        # Run the .bat file using Proton
        self.logger.info(f"🚀 Executing command: {proton_path} run run-mo2.bat")
        self.logger.info(f"📁 Working directory: {compat_data_path}")
        
        try:
            result = subprocess.run(
                [proton_path, "run", "run-mo2.bat"],
                cwd=compat_data_path,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            
            self.logger.info("✅ Proton execution completed successfully")
            self.logger.info(f"📤 Stdout: {result.stdout}")
            self.logger.info(f"📤 Stderr: {result.stderr}")
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Proton execution failed with error: {e}")
            self.logger.error(f"📤 Stdout: {e.stdout}")
            self.logger.error(f"📤 Stderr: {e.stderr}")
            return False
        
        # Add a 5-second delay to allow the Wine prefix to fully initialize
        self.logger.info("⏳ Waiting 5 seconds for Wine prefix initialization...")
        time.sleep(5)
        self.logger.info("✅ Delay complete - Wine prefix should be ready")
        
        # Detect and configure supported games
        self._detect_and_configure_games(compat_data_path)
        
        return True
    
    def _find_proton_installation(self, proton_version: str) -> Optional[str]:
        """Find the actual Proton installation path"""
        home_dir = Path.home()
        
        # Check Steam compatibility tools directory (Steam's official way)
        compatibility_tools_dirs = [
            Path(self.steam_path) / "compatibilitytools.d",
            home_dir / ".steam" / "root" / "compatibilitytools.d",
            home_dir / ".local" / "share" / "Steam" / "compatibilitytools.d",
        ]
        
        for compat_dir in compatibility_tools_dirs:
            if compat_dir.exists():
                # Look for the specific version in compatibility tools
                tool_path = compat_dir / proton_version
                if tool_path.exists():
                    proton_path = tool_path / "proton"
                    if proton_path.exists():
                        self.logger.info(f"Found Proton in compatibility tools: {tool_path}")
                        return str(proton_path)
        
        # Check standard Steam Proton installations
        steam_proton_path = Path(self.steam_path) / "steamapps" / "common" / proton_version / "proton"
        if steam_proton_path.exists():
            self.logger.info(f"Found Proton in Steam: {steam_proton_path}")
            return str(steam_proton_path)
        
        return None
    
    def _get_all_available_proton_versions(self) -> List[str]:
        """Get all available Proton versions on the system"""
        versions = []
        home_dir = Path.home()
        
        # Check Steam compatibility tools directory
        compatibility_tools_dirs = [
            Path(self.steam_path) / "compatibilitytools.d",
            home_dir / ".steam" / "root" / "compatibilitytools.d",
            home_dir / ".local" / "share" / "Steam" / "compatibilitytools.d",
        ]
        
        for compat_dir in compatibility_tools_dirs:
            if compat_dir.exists():
                for entry in compat_dir.iterdir():
                    if entry.is_dir() and entry.name.startswith("Proton"):
                        proton_path = entry / "proton"
                        if proton_path.exists():
                            versions.append(entry.name)
                            self.logger.info(f"Found Proton in compatibility tools: {entry.name}")
        
        # Check standard Steam Proton installations
        steam_proton_dir = Path(self.steam_path) / "steamapps" / "common"
        if steam_proton_dir.exists():
            for entry in steam_proton_dir.iterdir():
                if entry.is_dir() and entry.name.startswith("Proton"):
                    proton_path = entry / "proton"
                    if proton_path.exists():
                        versions.append(entry.name)
                        self.logger.info(f"Found Proton in Steam: {entry.name}")
        
        # Remove duplicates
        return list(dict.fromkeys(versions))
    
    def add_game_to_steam(self, app_name: str, exe_path: str, proton_tool: str = "proton_experimental") -> Dict[str, Any]:
        """Complete workflow: add game to Steam, create prefix, and return results"""
        try:
            self.logger.info(f"Adding {app_name} to Steam...")
            
            # Create Steam shortcut
            self.logger.info("Creating Steam shortcut...")
            app_id = self.add_single_shortcut(app_name, exe_path, proton_tool)
            self.logger.info(f"Steam shortcut created with AppID: {app_id}")
            self.logger.info(f"Executable path: {exe_path}")
            
            # Create compatdata folder
            self.logger.info("Creating compatdata folder...")
            compat_data_path = self.create_compat_data_folder(app_id)
            self.logger.info(f"Compatdata folder created: {compat_data_path}")
            
            # Create and run the .bat file to initialize the Wine prefix
            self.logger.info("Creating and running .bat file with Proton...")
            if not self.create_and_run_bat_file(compat_data_path, app_name):
                return {
                    "success": False,
                    "error": "Failed to initialize Wine prefix"
                }
            
            self.logger.info("Successfully ran .bat file with Proton")
            
            return {
                "success": True,
                "message": f"Successfully added '{app_name}' to Steam! Compatdata folder created and Wine prefix initialized. AppID: {app_id}",
                "app_name": app_name,
                "app_id": app_id,
                "compat_data_path": compat_data_path
            }
            
        except Exception as e:
            self.logger.error(f"Failed to add game to Steam: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _detect_and_configure_games(self, compat_data_path: str):
        """Detect installed games using Steam library VDF files and configure Wine registry"""
        self.logger.info("🎮 Detecting supported games using Steam library files...")
        
        # Game detection configurations with Steam AppIDs
        games_config = {
            "22380": {  # Fallout New Vegas AppID
                "name": "Fallout New Vegas",
                "common_names": ["Fallout New Vegas", "FalloutNV"],
                "registry_key": r"[Software\\WOW6432Node\\bethesda softworks\\falloutnv]",
                "value_name": '"Installed Path"'
            },
            "976620": {  # Enderal Special Edition AppID
                "name": "Enderal",
                "common_names": ["Enderal Special Edition"],
                "registry_key": r"[Software\\WOW6432Node\\SureAI\\Enderal]",
                "value_name": '"Installed path"'
            }
        }
        
        detected_games = []
        
        try:
            steam_libraries = self._get_steam_libraries()
            self.logger.info(f"🔍 Found {len(steam_libraries)} Steam libraries to search")
            
            for app_id, config in games_config.items():
                game_path = self._find_game_in_libraries(app_id, config["common_names"], steam_libraries)
                if game_path:
                    wine_path = self._convert_to_wine_path(str(game_path))
                    detected_games.append({
                        "name": config["name"],
                        "path": str(game_path),
                        "wine_path": wine_path,
                        "registry_key": config["registry_key"],
                        "value_name": config["value_name"]
                    })
                    self.logger.info(f"✅ Detected {config['name']} at: {game_path}")
            
            if detected_games:
                self._modify_system_reg(compat_data_path, detected_games)
            else:
                self.logger.info("📝 No supported games detected for automatic configuration")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error during game detection: {e}")
    
    def _get_steam_libraries(self) -> List[Path]:
        """Get all Steam library directories from libraryfolders.vdf"""
        libraries = []
        
        try:
            steam_root = Path(self.steam_path)
            
            # Add main Steam library
            libraries.append(steam_root)
            
            # Parse libraryfolders.vdf for additional libraries
            libraryfolders_path = steam_root / "steamapps" / "libraryfolders.vdf"
            if libraryfolders_path.exists():
                self.logger.info(f"📖 Reading library folders from: {libraryfolders_path}")
                with open(libraryfolders_path, 'r') as f:
                    content = f.read()
                
                # Parse VDF format to extract library paths
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if '"path"' in line:
                        # Extract path from VDF format: "path"		"/path/to/library"
                        parts = line.split('"')
                        if len(parts) >= 4:
                            library_path = Path(parts[3])
                            if library_path.exists() and library_path not in libraries:
                                libraries.append(library_path)
                                self.logger.info(f"📁 Added Steam library: {library_path}")
            
            return libraries
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error reading Steam libraries: {e}")
            return [Path(self.steam_path)]  # Fallback to main Steam directory
    
    def _find_game_in_libraries(self, app_id: str, common_names: List[str], steam_libraries: List[Path]) -> Optional[Path]:
        """Find a game in Steam libraries using AppID and common folder names"""
        for library_path in steam_libraries:
            # Method 1: Check appmanifest file for exact AppID match
            appmanifest_path = library_path / "steamapps" / f"appmanifest_{app_id}.acf"
            if appmanifest_path.exists():
                try:
                    with open(appmanifest_path, 'r') as f:
                        content = f.read()
                    
                    # Extract installdir from appmanifest
                    for line in content.split('\n'):
                        if '"installdir"' in line:
                            parts = line.split('"')
                            if len(parts) >= 4:
                                install_dir = parts[3]
                                game_path = library_path / "steamapps" / "common" / install_dir
                                if game_path.exists():
                                    self.logger.info(f"🎯 Found game via appmanifest: {game_path}")
                                    return game_path
                except Exception as e:
                    self.logger.warning(f"⚠️ Error reading appmanifest for {app_id}: {e}")
            
            # Method 2: Fallback to common folder name check
            common_path = library_path / "steamapps" / "common"
            if common_path.exists():
                for name in common_names:
                    game_path = common_path / name
                    if game_path.exists() and game_path.is_dir():
                        self.logger.info(f"📂 Found game via folder name: {game_path}")
                        return game_path
        
        return None
    
    def _convert_to_wine_path(self, linux_path: str) -> str:
        """Convert Linux path to Wine Z: path format"""
        # Convert to Wine Z: drive format with backslashes
        wine_path = "Z:" + linux_path.replace("/", "\\\\") + "\\\\"
        return wine_path
    
    def _modify_system_reg(self, compat_data_path: str, detected_games: list):
        """Modify system.reg file to add game registry entries and Wine settings"""
        system_reg_path = Path(compat_data_path) / "pfx" / "system.reg"
        
        if not system_reg_path.exists():
            self.logger.warning(f"⚠️ system.reg not found at: {system_reg_path}")
            return
        
        self.logger.info(f"📝 Modifying system.reg for {len(detected_games)} detected games and Wine settings...")
        
        try:
            # Read existing system.reg
            with open(system_reg_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add registry entries for each detected game
            new_entries = []
            for game in detected_games:
                registry_entry = f'''
{game["registry_key"]} 1757116748
#time=1dc1ec111c49d2e
{game["value_name"]}="{game["wine_path"]}"
'''
                new_entries.append(registry_entry)
                self.logger.info(f"✅ Added registry entry for {game['name']}: {game['wine_path']}")
            
            # Add Wine DLL overrides and settings from wine_settings.reg
            wine_settings = self._get_wine_registry_entries()
            if wine_settings:
                new_entries.extend(wine_settings)
                self.logger.info(f"✅ Added {len(wine_settings)} Wine registry settings")
            
            # Insert new entries before the final newline
            if content.endswith('\n'):
                content = content[:-1] + ''.join(new_entries) + '\n'
            else:
                content += ''.join(new_entries)
            
            # Write back to system.reg
            with open(system_reg_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            total_entries = len(detected_games) + len(wine_settings) if wine_settings else len(detected_games)
            self.logger.info(f"✅ Successfully modified system.reg with {total_entries} registry entries")
            
        except Exception as e:
            self.logger.error(f"❌ Error modifying system.reg: {e}")
    
    def _get_wine_registry_entries(self) -> list:
        """Convert wine_settings.reg entries to system.reg format"""
        try:
            # Find wine_settings.reg file
            wine_settings_path = Path(__file__).parent / "wine_settings.reg"
            if not wine_settings_path.exists():
                self.logger.warning(f"⚠️ wine_settings.reg not found at: {wine_settings_path}")
                return []
            
            with open(wine_settings_path, 'r', encoding='utf-8') as f:
                wine_content = f.read()
            
            # Parse the .reg file and convert to system.reg format
            entries = []
            current_key = None
            
            for line in wine_content.split('\n'):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('Windows Registry Editor'):
                    continue
                
                # Registry key section
                if line.startswith('[') and line.endswith(']'):
                    # Convert registry key format
                    reg_key = line[1:-1]  # Remove brackets
                    
                    # Convert HKEY_CURRENT_USER to the system.reg format
                    if reg_key.startswith('HKEY_CURRENT_USER\\'):
                        # Convert to system.reg format: [S-1-5-21-0-0-0-1000\\...] 
                        key_path = reg_key[len('HKEY_CURRENT_USER\\'):]
                        current_key = f"[S-1-5-21-0-0-0-1000\\{key_path}]"
                    else:
                        current_key = f"[{reg_key}]"
                    continue
                
                # Registry value
                if '=' in line and current_key:
                    # Parse value: "name"="value" or "name"=dword:value
                    if line.startswith('"') and '"=' in line:
                        name_end = line.index('"=')
                        value_name = line[1:name_end]  # Remove quotes
                        value_part = line[name_end+2:]  # Get value part
                        
                        # Handle different value types
                        if value_part.startswith('"') and value_part.endswith('"'):
                            # String value
                            value_content = value_part[1:-1]  # Remove quotes
                            registry_entry = f'''
{current_key} 1757116748
#time=1dc1ec111c49d2e
"{value_name}"="{value_content}"
'''
                        elif value_part.startswith('dword:'):
                            # DWORD value
                            dword_val = value_part[6:]  # Remove 'dword:'
                            registry_entry = f'''
{current_key} 1757116748
#time=1dc1ec111c49d2e
"{value_name}"=dword:{dword_val}
'''
                        else:
                            # Raw value
                            registry_entry = f'''
{current_key} 1757116748
#time=1dc1ec111c49d2e
"{value_name}"={value_part}
'''
                        
                        entries.append(registry_entry)
            
            self.logger.info(f"📝 Converted {len(entries)} Wine registry entries from wine_settings.reg")
            return entries
            
        except Exception as e:
            self.logger.error(f"❌ Error reading wine_settings.reg: {e}")
            return []
    
    def _parse_simple_vdf(self, vdf_path: str) -> Dict[str, Any]:
        """Parse a simple VDF (Valve Data Format) file like libraryfolders.vdf"""
        if not os.path.exists(vdf_path):
            return {}
        
        try:
            with open(vdf_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Simple VDF parser - handles basic key-value pairs and sections
            result = {}
            stack = [result]
            current_section = None
            
            # Remove comments and clean up
            lines = content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                cleaned_lines.append(line)
            
            i = 0
            while i < len(cleaned_lines):
                line = cleaned_lines[i].strip()
                
                if not line:
                    i += 1
                    continue
                
                # Handle opening brace
                if line == '{':
                    if current_section:
                        new_dict = {}
                        stack[-1][current_section] = new_dict
                        stack.append(new_dict)
                        current_section = None
                    i += 1
                    continue
                
                # Handle closing brace
                if line == '}':
                    if len(stack) > 1:
                        stack.pop()
                    i += 1
                    continue
                
                # Handle key-value pairs
                key_match = re.match(r'^"([^"]+)"(?:\s+"([^"]*)")?', line)
                if key_match:
                    key = key_match.group(1)
                    value = key_match.group(2) if key_match.group(2) is not None else None
                    
                    if value is not None:
                        # It's a key-value pair
                        stack[-1][key] = value
                    else:
                        # It's just a key, probably followed by a section
                        current_section = key
                
                i += 1
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to parse VDF file {vdf_path}: {e}")
            return {}
    
    def find_steam_libraries(self) -> List[str]:
        """Find all Steam library folders from libraryfolders.vdf"""
        if not self.steam_path:
            return []
            
        libraryfolders_path = os.path.join(self.steam_path, "config", "libraryfolders.vdf")
        
        if not os.path.exists(libraryfolders_path):
            self.logger.warning(f"libraryfolders.vdf not found at: {libraryfolders_path}")
            return []
        
        try:
            vdf_data = self._parse_simple_vdf(libraryfolders_path)
            
            if "libraryfolders" not in vdf_data:
                self.logger.warning("No 'libraryfolders' section found in VDF")
                return []
            
            libraries = []
            libraryfolders = vdf_data["libraryfolders"]
            
            for key, value in libraryfolders.items():
                if isinstance(value, dict) and "path" in value:
                    path = value["path"]
                    libraries.append(path)
                    self.logger.debug(f"Found Steam library: {path}")
            
            self.logger.info(f"Found {len(libraries)} Steam libraries")
            return libraries
            
        except Exception as e:
            self.logger.error(f"Failed to find Steam libraries: {e}")
            return []
    
    def create_steam_compat_mounts_string(self, libraries: List[str] = None) -> str:
        """Create STEAM_COMPAT_MOUNTS environment variable string"""
        if libraries is None:
            libraries = self.find_steam_libraries()
        
        if not libraries:
            return ""
        
        # Quote each path and join with commas
        quoted_paths = [f'"{lib}"' for lib in libraries]
        compat_mounts = f'STEAM_COMPAT_MOUNTS={",".join(quoted_paths)}'
        
        self.logger.debug(f"Generated STEAM_COMPAT_MOUNTS: {compat_mounts}")
        return compat_mounts
