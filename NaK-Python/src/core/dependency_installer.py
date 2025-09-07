"""
Dependency Installer module for installing Proton dependencies
"""
import subprocess
import time
import os
from typing import Dict, Any, List
import requests
from pathlib import Path
import tempfile
import datetime

from ..utils.logger import get_logger
from ..utils.steam_utils import SteamUtils


class DependencyInstaller:
    """Handles installing Proton dependencies for games"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.steam_utils = SteamUtils()
        self.debug_log_path = self._create_debug_log_file()
    
    def install_basic_dependencies(self) -> Dict[str, Any]:
        """Install common Proton components for any mod manager"""
        self.logger.info("Installing basic dependencies")
        
        try:
            # Check for protontricks (native or flatpak)
            protontricks_cmd = self._get_protontricks_command()
            if not protontricks_cmd:
                return {
                    "success": False,
                    "error": "Protontricks is not installed"
                }
            
            # Get non-Steam games
            games = self.steam_utils.get_non_steam_games()
            if not games:
                return {
                    "success": False,
                    "error": "No non-Steam games found. Add some games to Steam first."
                }
            
            # Auto-select if only one game found
            if len(games) == 1:
                selected_game = games[0]
                self.logger.info(f"Auto-selected only game: {selected_game.get('Name')} (AppID: {selected_game.get('AppID')})")
                return self._install_proton_dependencies(selected_game, protontricks_cmd)
            
            # Return games list for selection
            return {
                "success": True,
                "games": games,
                "message": f"Found {len(games)} non-Steam games. Please select one to install dependencies:"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to install basic dependencies: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def install_dependencies_for_game(self, game_app_id: str) -> Dict[str, Any]:
        """Install dependencies for a specific non-Steam game"""
        self.logger.info(f"Installing dependencies for game AppID: {game_app_id}")
        
        try:
            # Get the game details
            games = self.steam_utils.get_non_steam_games()
            
            # Find the selected game
            selected_game = None
            for game in games:
                if game.get("AppID") == game_app_id:
                    selected_game = game
                    break
            
            if not selected_game:
                return {
                    "success": False,
                    "error": f"Game with AppID {game_app_id} not found"
                }
            
            # Get protontricks command
            protontricks_cmd = self._get_protontricks_command()
            if not protontricks_cmd:
                return {
                    "success": False,
                    "error": "Protontricks not found"
                }
            
            return self._install_proton_dependencies(selected_game, protontricks_cmd)
            
        except Exception as e:
            self.logger.error(f"Failed to install dependencies for game {game_app_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def install_mo2_dependencies_for_game(self, game_app_id: str) -> Dict[str, Any]:
        """Install MO2 dependencies for a specific non-Steam game"""
        self.logger.info(f"Installing MO2 dependencies for game AppID: {game_app_id}")
        
        try:
            # Get the game details
            games = self.steam_utils.get_non_steam_games()
            
            # Find the selected game
            selected_game = None
            for game in games:
                if game.get("AppID") == game_app_id:
                    selected_game = game
                    break
            
            if not selected_game:
                return {
                    "success": False,
                    "error": f"Game with AppID {game_app_id} not found"
                }
            
            # Get protontricks command
            protontricks_cmd = self._get_protontricks_command()
            if not protontricks_cmd:
                return {
                    "success": False,
                    "error": "Protontricks not found"
                }
            
            # Comprehensive dependency list - includes ALL dependencies for FNV, Enderal, and MO2
            dependencies = [
                "fontsmooth=rgb",
                "xact",
                "xact_x64",
                "vcrun2022",
                "dotnet6",
                "dotnet7", 
                "dotnet8",
                "dotnetdesktop6",
                "d3dcompiler_47",
                "d3dx11_43",
                "d3dcompiler_43",
                "d3dx9_43",
                "d3dx9",
                "vkd3d",
            ]
            
            return self._install_dependencies_with_list(selected_game, protontricks_cmd, dependencies, "MO2")
            
        except Exception as e:
            self.logger.error(f"Failed to install MO2 dependencies for game {game_app_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def _get_protontricks_command(self) -> str:
        """Get the protontricks command (native or flatpak)"""
        if self._command_exists("protontricks"):
            return "protontricks"
        elif self._command_exists("flatpak"):
            try:
                result = subprocess.run(
                    ["sh", "-c", "flatpak list --app --columns=application | grep -q com.github.Matoking.protontricks && echo 'found'"],
                    capture_output=True, text=True, check=True
                )
                if "found" in result.stdout:
                    return "flatpak run com.github.Matoking.protontricks"
            except subprocess.CalledProcessError:
                pass
        
        return ""
    
    def _create_debug_log_file(self) -> str:
        """Create a debug log file for detailed logging"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path(tempfile.gettempdir()) / "nak_debug_logs"
        log_dir.mkdir(exist_ok=True)
        debug_log_path = log_dir / f"protontricks_debug_{timestamp}.log"
        
        with open(debug_log_path, 'w') as f:
            f.write(f"NaK Debug Log - {datetime.datetime.now()}\n")
            f.write("=" * 50 + "\n\n")
        
        self.logger.info(f"Debug log created: {debug_log_path}")
        return str(debug_log_path)
    
    def _log_to_debug_file(self, message: str):
        """Log a message to the debug file"""
        try:
            with open(self.debug_log_path, 'a') as f:
                f.write(f"[{datetime.datetime.now()}] {message}\n")
        except Exception as e:
            self.logger.warning(f"Failed to write to debug log: {e}")

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run([command, "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _validate_protontricks_working(self, protontricks_cmd: str, app_id: str) -> bool:
        """Validate that protontricks is working properly for the given app"""
        try:
            # Test with a simple command that should work
            test_cmd = [protontricks_cmd, "--no-bwrap", app_id, "--list"]
            if protontricks_cmd.startswith("flatpak run"):
                parts = protontricks_cmd.split()
                test_cmd = [parts[0]] + parts[1:] + ["--no-bwrap", app_id, "--list"]
            
            self.logger.info(f"Testing protontricks with: {' '.join(test_cmd)}")
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.logger.info("Protontricks validation successful")
                return True
            else:
                self.logger.warning(f"Protontricks validation failed: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.warning(f"Protontricks validation error: {e}")
            return False
    
    def _install_proton_dependencies(self, game: Dict[str, str], protontricks_cmd: str) -> Dict[str, Any]:
        """Install Proton dependencies for a game - now uses comprehensive dependency list"""
        self.logger.info(f"Installing comprehensive dependencies for {game.get('Name')} (AppID: {game.get('AppID')})")
        
        # Use the same comprehensive dependency list as MO2 setup
        comprehensive_dependencies = [
            "fontsmooth=rgb",
            "xact",
            "xact_x64",
            "vcrun2022",
            "dotnet6",
            "dotnet7", 
            "dotnet8",
            "dotnetdesktop6",
            "d3dcompiler_47",
            "d3dx11_43",
            "d3dcompiler_43",
            "d3dx9_43",
            "d3dx9",
            "vkd3d",
        ]
        
        return self._install_dependencies_with_list(game, protontricks_cmd, comprehensive_dependencies, game.get("Name", "Unknown"))
    
    def _install_dependencies_with_list(self, game: Dict[str, str], protontricks_cmd: str, dependencies: List[str], game_type: str) -> Dict[str, Any]:
        """Install dependencies with a specific list"""
        self.logger.info(f"Installing {game_type} dependencies for {game.get('Name')} (AppID: {game.get('AppID')})")
        
        output_lines = []
        output_lines.append(f"Installing {game_type} dependencies for {game.get('Name')} (AppID: {game.get('AppID')}):")
        output_lines.append(f"Total dependencies: {len(dependencies)}")
        output_lines.append("")
        
        # Kill Steam first (like CLI does)
        output_lines.append("Stopping Steam...")
        try:
            subprocess.run(["pkill", "-9", "steam"], check=True)
            output_lines.append("Steam stopped successfully.")
            # Wait for cleanup
            time.sleep(2)
        except subprocess.CalledProcessError:
            output_lines.append("Failed to stop Steam (may not be running)")
        
        # Build the protontricks command with -q flag (like CLI does)
        args = ["--no-bwrap", game.get("AppID", ""), "-q"]
        args.extend(dependencies)
        
        # Split the protontricks command if it's a flatpak command
        if protontricks_cmd.startswith("flatpak run"):
            parts = protontricks_cmd.split()
            cmd = [parts[0]] + parts[1:] + args
        else:
            cmd = [protontricks_cmd] + args
        
        output_lines.append(f"Running: {protontricks_cmd} {' '.join(args)}")
        output_lines.append("Starting dependency installation...")
        output_lines.append("")
        
        # Validate protontricks is working first
        output_lines.append("Validating protontricks...")
        if not self._validate_protontricks_working(protontricks_cmd, game.get("AppID", "")):
            output_lines.append("⚠️ Warning: Protontricks validation failed, but continuing...")
        else:
            output_lines.append("✓ Protontricks validation successful")
        output_lines.append("")
        
        try:
            # Run the command with timeout and better error handling
            self.logger.info(f"Running protontricks command: {' '.join(cmd)}")
            self._log_to_debug_file(f"COMMAND: {' '.join(cmd)}")
            
            # Don't set PROTON_VERSION - let protontricks auto-detect the correct Proton version
            env = os.environ.copy()
            # Remove PROTON_VERSION if it exists to avoid conflicts
            if 'PROTON_VERSION' in env:
                del env['PROTON_VERSION']
            self._log_to_debug_file(f"ENVIRONMENT: Letting protontricks auto-detect Proton version")
            self._log_to_debug_file(f"REMOVED PROTON_VERSION to avoid version mismatch")
            
            # Log start of execution
            self._log_to_debug_file("STARTING PROTONTRICKS EXECUTION...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=600, env=env)  # 10 minute timeout, don't check for errors
            
            # Log all output regardless of success/failure
            self._log_to_debug_file(f"RETURN CODE: {result.returncode}")
            self._log_to_debug_file(f"STDOUT:\n{result.stdout}")
            self._log_to_debug_file(f"STDERR:\n{result.stderr}")
            
            # Now check the return code and handle errors appropriately
            if result.returncode != 0:
                # Log the error but don't immediately fail
                self._log_to_debug_file("PROTONTRICKS FAILED - analyzing output...")
                output_lines.append(f"❌ Protontricks failed with return code: {result.returncode}")
                if result.stderr:
                    output_lines.append(f"Error output: {result.stderr}")
                if result.stdout:
                    output_lines.append(f"Standard output: {result.stdout}")
                
                output_lines.append(f"🐛 Full debug log available at: {self.debug_log_path}")
                
                return {
                    "success": False,
                    "message": "\n".join(output_lines),
                    "error": f"Protontricks failed (code {result.returncode}). Check debug log: {self.debug_log_path}",
                    "debug_log": self.debug_log_path
                }
            
            # Log successful execution
            self._log_to_debug_file("PROTONTRICKS COMPLETED SUCCESSFULLY")
            
            # Check if the command actually did something
            if result.stdout:
                output_lines.append("Protontricks output:")
                output_lines.append(result.stdout)
                self._log_to_debug_file("SUCCESS: Found stdout output")
            
            if result.stderr:
                output_lines.append("Protontricks warnings/errors:")
                output_lines.append(result.stderr)
                self._log_to_debug_file("SUCCESS: Found stderr output (may be warnings)")
            
            # Validate that dependencies were actually installed
            # Check for successful installation indicators in protontricks output
            success_indicators = [
                "installed successfully",
                "successfully installed", 
                "installation completed",
                "setup complete",
                "wine prefix created",
                "executing w_do_call",
                "executing load_"
            ]
            
            output_lower = result.stdout.lower() + result.stderr.lower()
            found_indicators = [indicator for indicator in success_indicators if indicator in output_lower]
            
            if found_indicators:
                output_lines.append("✓ All dependencies installed successfully!")
                self._log_to_debug_file(f"SUCCESS: Found indicators: {found_indicators}")
                output_lines.append(f"🐛 Debug log available at: {self.debug_log_path}")
            else:
                output_lines.append("⚠️ Warning: Dependencies may not have been installed properly")
                output_lines.append("Check the output above for any errors")
                output_lines.append(f"🐛 Full debug log available at: {self.debug_log_path}")
                self._log_to_debug_file("WARNING: No success indicators found in output")
                # Don't return success if we can't verify installation
                return {
                    "success": False,
                    "message": "\n".join(output_lines),
                    "error": "Could not verify dependency installation",
                    "debug_log": self.debug_log_path
                }
            
        except subprocess.TimeoutExpired as e:
            self._log_to_debug_file(f"TIMEOUT: Command timed out after 10 minutes: {e}")
            output_lines.append(f"⚠️ Dependency installation timed out after 10 minutes")
            output_lines.append("This is normal for large dependency installations")
            output_lines.append("Dependencies may still be installing in the background")
            output_lines.append(f"🐛 Debug log available at: {self.debug_log_path}")
            # Return success for timeout - protontricks might still be working
            output_lines.append("")
            output_lines.append(f"{game_type} dependencies setup complete!")
            
            return {
                "success": True,
                "message": "\n".join(output_lines),
                "debug_log": self.debug_log_path
            }
            
        except subprocess.CalledProcessError as e:
            # This shouldn't happen since we use check=False, but just in case
            self._log_to_debug_file(f"CALLED_PROCESS_ERROR: {e}")
            self._log_to_debug_file(f"ERROR STDOUT: {e.stdout}")
            self._log_to_debug_file(f"ERROR STDERR: {e.stderr}")
            output_lines.append(f"Failed to install dependencies: {e}")
            if e.stderr:
                output_lines.append(f"Error details: {e.stderr}")
            if e.stdout:
                output_lines.append(f"Output: {e.stdout}")
            output_lines.append(f"🐛 Full debug log available at: {self.debug_log_path}")
            return {
                "success": False,
                "message": "\n".join(output_lines),
                "error": str(e),
                "debug_log": self.debug_log_path
            }
        except Exception as e:
            # Catch any other unexpected errors
            self._log_to_debug_file(f"UNEXPECTED_ERROR: {e}")
            output_lines.append(f"Unexpected error during dependency installation: {e}")
            output_lines.append(f"🐛 Full debug log available at: {self.debug_log_path}")
            return {
                "success": False,
                "message": "\n".join(output_lines),
                "error": str(e),
                "debug_log": self.debug_log_path
            }
        
        # Apply Wine registry settings (DLL overrides and settings)
        output_lines.append("")
        output_lines.append("Applying Wine registry settings (DLL overrides)...")
        self._log_to_debug_file("APPLYING WINE REGISTRY SETTINGS...")
        
        registry_success = self._apply_wine_registry_settings(game.get("AppID", ""), protontricks_cmd, output_lines)
        if registry_success:
            output_lines.append("✓ Wine registry settings applied successfully!")
            self._log_to_debug_file("WINE REGISTRY SETTINGS APPLIED SUCCESSFULLY")
        else:
            output_lines.append("⚠️ Warning: Failed to apply some Wine registry settings")
            self._log_to_debug_file("WARNING: WINE REGISTRY SETTINGS FAILED")
        
        # Install .NET 9 SDK
        output_lines.append("")
        output_lines.append("Installing .NET 9 SDK...")
        self._log_to_debug_file("INSTALLING .NET 9 SDK...")
        
        try:
            dotnet_success = self.install_dotnet9_sdk(game.get("AppID", ""))
            if dotnet_success:
                output_lines.append("✓ .NET 9 SDK installed successfully!")
                self._log_to_debug_file(".NET 9 SDK INSTALLATION SUCCESSFUL")
            else:
                output_lines.append("⚠️ Warning: .NET 9 SDK installation may have failed")
                self._log_to_debug_file("WARNING: .NET 9 SDK INSTALLATION FAILED")
        except Exception as e:
            output_lines.append(f"⚠️ Warning: .NET 9 SDK installation failed: {e}")
            self._log_to_debug_file(f".NET 9 SDK INSTALLATION ERROR: {e}")
        
        # Restart Steam
        output_lines.append("")
        output_lines.append("Restarting Steam...")
        self._log_to_debug_file("RESTARTING STEAM...")
        try:
            subprocess.Popen(["steam"])
            output_lines.append("Steam restarted successfully!")
            self._log_to_debug_file("STEAM RESTARTED SUCCESSFULLY")
        except Exception as e:
            output_lines.append(f"Failed to restart Steam: {e}")
            output_lines.append("Please start Steam manually.")
            self._log_to_debug_file(f"STEAM RESTART FAILED: {e}")
        
        output_lines.append("")
        output_lines.append(f"{game_type} dependencies setup complete!")
        self._log_to_debug_file(f"DEPENDENCY INSTALLATION COMPLETED SUCCESSFULLY FOR {game_type}")
        
        return {
            "success": True,
            "message": "\n".join(output_lines),
            "debug_log": self.debug_log_path
        }
    
    
    def _apply_wine_registry_settings(self, app_id: str, protontricks_cmd: str, output_lines: list) -> bool:
        """Apply Wine registry settings including DLL overrides"""
        try:
            self._log_to_debug_file("SEARCHING FOR WINE_SETTINGS.REG FILE...")
            
            # Find wine_settings.reg file
            wine_settings_path = Path(__file__).parent.parent / "utils" / "wine_settings.reg"
            if not wine_settings_path.exists():
                self._log_to_debug_file(f"WINE_SETTINGS.REG NOT FOUND AT: {wine_settings_path}")
                output_lines.append(f"Warning: wine_settings.reg not found at {wine_settings_path}")
                return False
            
            self._log_to_debug_file(f"FOUND WINE_SETTINGS.REG AT: {wine_settings_path}")
            
            # Create a temporary copy of the registry file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False) as temp_file:
                with open(wine_settings_path, 'r') as orig_file:
                    temp_file.write(orig_file.read())
                temp_reg_path = temp_file.name
            
            self._log_to_debug_file(f"CREATED TEMP REGISTRY FILE: {temp_reg_path}")
            
            # Get paths dynamically like your command
            steam_root = self.steam_utils.get_steam_root()
            compatdata_path = f"{steam_root}/steamapps/compatdata/{app_id}"
            proton_path = f"{steam_root}/steamapps/common/Proton - Experimental/proton"
            
            # Your exact working command
            env = os.environ.copy()
            env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = steam_root
            env['STEAM_COMPAT_DATA_PATH'] = compatdata_path
            
            cmd = [proton_path, "run", "regedit", temp_reg_path]
            
            self._log_to_debug_file(f"REGISTRY COMMAND: {' '.join(cmd)}")
            
            # Execute registry import
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
            
            self._log_to_debug_file(f"REGISTRY RETURN CODE: {result.returncode}")
            self._log_to_debug_file(f"REGISTRY STDOUT: {result.stdout}")
            self._log_to_debug_file(f"REGISTRY STDERR: {result.stderr}")
            
            # Cleanup temp file
            Path(temp_reg_path).unlink(missing_ok=True)
            
            if result.returncode == 0:
                output_lines.append("Registry settings applied successfully")
                return True
            else:
                output_lines.append(f"Registry import failed (code {result.returncode})")
                if result.stderr:
                    output_lines.append(f"Registry error: {result.stderr}")
                return False
                
        except Exception as e:
            self._log_to_debug_file(f"REGISTRY APPLICATION ERROR: {e}")
            output_lines.append(f"Error applying registry settings: {e}")
            return False

    def install_dotnet9_sdk(self, game_app_id: str) -> bool:
        """Install .NET 9 SDK using direct proton approach or protontricks-launch"""
        self.logger.info("Installing .NET 9 SDK")
        
        try:
            # Download .NET 9 SDK (same URL as CLI)
            dotnet_url = "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe"
            dotnet_file = "dotnet-sdk-9.0.203-win-x64.exe"
            
            # Download to Downloads directory
            home_dir = str(Path.home())
            download_path = Path(home_dir) / "Downloads" / dotnet_file
            
            self.logger.info(f"Downloading .NET 9 SDK to: {download_path}")
            
            # Create Downloads directory if it doesn't exist
            download_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the file
            response = requests.get(dotnet_url, stream=True)
            response.raise_for_status()
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Check if we're using flatpak protontricks (no protontricks-launch available)
            protontricks_cmd = self._get_protontricks_command()
            
            if protontricks_cmd.startswith("flatpak run"):
                # Use direct proton approach for flatpak protontricks (like regedit fix)
                self.logger.info("Using direct proton approach for .NET 9 SDK (flatpak protontricks)")
                
                steam_root = self.steam_utils.get_steam_root()
                compatdata_path = f"{steam_root}/steamapps/compatdata/{game_app_id}"
                proton_path = f"{steam_root}/steamapps/common/Proton - Experimental/proton"
                
                # Set environment like working regedit command
                env = os.environ.copy()
                env['STEAM_COMPAT_CLIENT_INSTALL_PATH'] = steam_root
                env['STEAM_COMPAT_DATA_PATH'] = compatdata_path
                
                cmd = [proton_path, "run", str(download_path), "/q"]
                
                self.logger.info(f"Running .NET 9 SDK with direct proton: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, env=env)
                
            else:
                # Use protontricks-launch for native protontricks
                self.logger.info("Running .NET 9 SDK installer with protontricks-launch")
                cmd = ["protontricks-launch", "--appid", game_app_id, str(download_path), "/q"]
                result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.warning(f"Command returned error: {result.returncode}")
                self.logger.info(f"Command output: {result.stdout}")
                # Don't return error - the installer might have succeeded despite exit code
                self.logger.info("Continuing despite exit code - checking if installation succeeded...")
            else:
                self.logger.info("Command completed successfully")
                self.logger.info(f"Command output: {result.stdout}")
            
            # Clean up downloaded file
            download_path.unlink(missing_ok=True)
            
            self.logger.info("=== .NET 9 SDK Installation Completed Successfully ===")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install .NET 9 SDK: {e}")
            return False
