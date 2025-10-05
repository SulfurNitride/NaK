#!/usr/bin/env python3
"""
Main application module for NaK Python
"""
import argparse
import sys
from typing import Dict, Any, Optional

from core.core import Core
from utils.logger import get_logger, setup_comprehensive_logging


class NaKApp:
    """Main NaK application class"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.core = Core()
    
    def run(self, args: argparse.Namespace) -> int:
        """Run the application with given arguments"""
        try:
            if args.command == "check-deps":
                return self._check_dependencies()
            elif args.command == "list-games":
                return self._list_games()
            elif args.command == "install-mo2":
                return self._install_mo2(args.install_dir if hasattr(args, 'install_dir') else None)
            elif args.command == "setup-existing-mo2":
                return self._setup_existing_mo2(args.mo2_path, args.custom_name)
            elif args.command == "configure-nxm-handler":
                return self._configure_nxm_handler(args.app_id, args.nxm_handler_path)
            elif args.command == "remove-nxm-handlers":
                return self._remove_nxm_handlers()
            elif args.command == "add-game":
                return self._add_game_to_steam(args.name, args.exe_path)
            elif args.command == "install-deps":
                return self._install_dependencies(args.game_id)
            elif args.command == "install-mo2-deps":
                return self._install_mo2_dependencies(args.game_id)
            elif args.command == "setup-fnv":
                return self._setup_fnv_dependencies()
            elif args.command == "setup-enderal":
                return self._setup_enderal_dependencies()
            elif args.command == "version":
                return self._show_version()
            else:
                self.logger.error(f"Unknown command: {args.command}")
                return 1
                
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            return 1
    
    def _check_dependencies(self) -> int:
        """Check if all required dependencies are available"""
        self.logger.debug("Checking dependencies...")
        
        if self.core.check_dependencies():
            print("All dependencies are available!")
            return 0
        else:
            print("Some dependencies are missing!")
            return 1
    
    def _list_games(self) -> int:
        """List non-Steam games"""
        self.logger.debug("Listing non-Steam games...")
        
        games = self.core.get_non_steam_games()
        if not games:
            result = {
                "success": False,
                "count": 0,
                "games": [],
                "error": "No non-Steam games found"
            }
        else:
            # Convert games to the format expected by the frontend
            formatted_games = []
            for game in games:
                formatted_games.append({
                    "name": game.get('Name', 'Unknown'),
                    "app_id": game.get('AppID', 'Unknown'),
                    "path": game.get('Path', ''),
                    "platform": game.get('Platform', 'Unknown')
                })
            
            result = {
                "success": True,
                "count": len(games),
                "games": formatted_games
            }
        
        # Output JSON result for the Wails frontend
        import json
        print(json.dumps(result, indent=2), flush=True)
        
        return 0 if result["success"] else 1
    
    def _install_mo2(self, install_dir: Optional[str] = None) -> int:
        """Install Mod Organizer 2"""
        self.logger.info(f"Installing Mod Organizer 2 to: {install_dir or 'default location'}")
        
        # Set up progress callback for real-time updates
        def progress_callback(message):
            # Output progress in a simple format for streaming
            print(f"PROGRESS: {message}", flush=True)
        
        # Set the progress callback
        self.core.mo2.set_progress_callback(progress_callback)
        
        result = self.core.install_mo2(install_dir)
        
        # Output final JSON result for the Wails frontend
        import json
        print(json.dumps(result, indent=2), flush=True)
        
        return 0 if result.get("success") else 1
    
    def _setup_existing_mo2(self, mo2_path: str, custom_name: str) -> int:
        """Setup existing MO2 installation"""
        self.logger.info(f"Setting up existing MO2 at: {mo2_path} with name: {custom_name}")
        
        # Set up progress callback for real-time updates
        def progress_callback(message):
            # Output progress in a simple format for streaming
            print(f"PROGRESS: {message}", flush=True)
        
        # Set the progress callback
        self.core.mo2.set_progress_callback(progress_callback)
        
        result = self.core.setup_existing_mo2(mo2_path, custom_name)
        
        # Output final JSON result for the Wails frontend
        import json
        print(json.dumps(result, indent=2), flush=True)
        
        return 0 if result.get("success") else 1
    
    def _configure_nxm_handler(self, app_id: str, nxm_handler_path: str) -> int:
        """Configure NXM handler for a game"""
        self.logger.info(f"Configuring NXM handler for AppID {app_id} with path: {nxm_handler_path}")
        
        result = self.core.configure_nxm_handler(app_id, nxm_handler_path)
        
        # Output final JSON result for the Wails frontend
        import json
        print(json.dumps(result, indent=2), flush=True)
        
        return 0 if result.get("success") else 1
    
    def _remove_nxm_handlers(self) -> int:
        """Remove all NXM handlers"""
        self.logger.info("Removing NXM handlers")
        
        result = self.core.remove_nxm_handlers()
        
        # Output final JSON result for the Wails frontend
        import json
        print(json.dumps(result, indent=2), flush=True)
        
        return 0 if result.get("success") else 1
    
    def _add_game_to_steam(self, name: str, exe_path: str) -> int:
        """Add a game to Steam"""
        self.logger.info(f"Adding '{name}' to Steam")
        
        result = self.core.steam_utils.add_game_to_steam(name, exe_path)
        if result.get("success"):
            print("Success!")
            print(f"   AppID: {result.get('app_id')}")
            print(f"   Compat data path: {result.get('compat_data_path')}")
            print(f"   Message: {result.get('message')}")
            return 0
        else:
            print(f"Failed to add game to Steam: {result.get('error')}")
            return 1
    
    def _install_dependencies(self, game_id: str) -> int:
        """Install dependencies for a game"""
        self.logger.info(f"Installing dependencies for game {game_id}")
        
        result = self.core.dependency_installer.install_dependencies_for_game(game_id)
        if result.get("success"):
            print("Dependencies installed successfully!")
            print(result.get("message", ""))
            return 0
        else:
            print(f"Failed to install dependencies: {result.get('error')}")
            return 1
    
    def _install_mo2_dependencies(self, game_id: str) -> int:
        """Install MO2 dependencies for a game"""
        self.logger.info(f"Installing MO2 dependencies for game {game_id}")
        
        result = self.core.dependency_installer.install_mo2_dependencies_for_game(game_id)
        if result.get("success"):
            print("MO2 dependencies installed successfully!")
            print(result.get("message", ""))
            return 0
        else:
            print(f"Failed to install MO2 dependencies: {result.get('error')}")
            return 1
    
    def _setup_fnv_dependencies(self) -> int:
        """Setup Fallout New Vegas dependencies"""
        self.logger.info("Setting up FNV dependencies")
        
        result = self.core.dependency_installer.setup_fnv_dependencies()
        if result.get("success"):
            print("FNV dependencies setup complete!")
            print(result.get("message", ""))
            return 0
        else:
            print(f"Failed to setup FNV dependencies: {result.get('error')}")
            return 1
    
    def _setup_enderal_dependencies(self) -> int:
        """Setup Enderal dependencies"""
        self.logger.info("Setting up Enderal dependencies")
        
        result = self.core.dependency_installer.setup_enderal_dependencies()
        if result.get("success"):
            print("Enderal dependencies setup complete!")
            print(result.get("message", ""))
            return 0
        else:
            print(f"Failed to setup Enderal dependencies: {result.get('error')}")
            return 1
    
    def _show_version(self) -> int:
        """Show version information"""
        version, date = self.core.get_version_info()
        print(f"NaK Python v{version} ({date})")
        return 0


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="NaK - Linux Modding Helper (Python)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s check-deps                    # Check if all dependencies are available
  %(prog)s list-games                    # List non-Steam games
  %(prog)s install-mo2                  # Install Mod Organizer 2
  %(prog)s add-game "My Game" "/path/to/game.exe"  # Add game to Steam
  %(prog)s install-deps 470057975       # Install dependencies for game
  %(prog)s install-mo2-deps 470057975   # Install MO2 dependencies for game
  %(prog)s setup-fnv                     # Setup Fallout New Vegas dependencies
  %(prog)s setup-enderal                 # Setup Enderal dependencies
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # check-deps command
    subparsers.add_parser("check-deps", help="Check if all dependencies are available")
    
    # list-games command
    subparsers.add_parser("list-games", help="List non-Steam games")
    
    # install-mo2 command
    install_mo2_parser = subparsers.add_parser("install-mo2", help="Install Mod Organizer 2")
    install_mo2_parser.add_argument("--install-dir", help="Custom installation directory")
    
    # setup-existing-mo2 command
    setup_existing_parser = subparsers.add_parser("setup-existing-mo2", help="Setup existing MO2 installation")
    setup_existing_parser.add_argument("--mo2-path", required=True, help="Path to existing MO2 installation")
    setup_existing_parser.add_argument("--custom-name", required=True, help="Custom name for MO2 installation")
    
    # configure-nxm-handler command
    nxm_parser = subparsers.add_parser("configure-nxm-handler", help="Configure NXM handler for a game")
    nxm_parser.add_argument("--app-id", required=True, help="Steam AppID of the game")
    nxm_parser.add_argument("--nxm-handler-path", required=True, help="Path to NXM handler executable")
    
    # remove-nxm-handlers command
    subparsers.add_parser("remove-nxm-handlers", help="Remove all NXM handlers")
    
    # add-game command
    add_game_parser = subparsers.add_parser("add-game", help="Add a game to Steam")
    add_game_parser.add_argument("name", help="Name of the game")
    add_game_parser.add_argument("exe_path", help="Path to the game executable")
    
    # install-deps command
    install_deps_parser = subparsers.add_parser("install-deps", help="Install dependencies for a game")
    install_deps_parser.add_argument("game_id", help="Game AppID")
    
    # install-mo2-deps command
    install_mo2_deps_parser = subparsers.add_parser("install-mo2-deps", help="Install MO2 dependencies for a game")
    install_mo2_deps_parser.add_argument("game_id", help="Game AppID")
    
    # setup-fnv command
    subparsers.add_parser("setup-fnv", help="Setup Fallout New Vegas dependencies")
    
    # setup-enderal command
    subparsers.add_parser("setup-enderal", help="Setup Enderal dependencies")
    
    # version command
    subparsers.add_parser("version", help="Show version information")
    
    return parser


def main():
    """Main entry point"""
    # Setup logging
    setup_comprehensive_logging()

    # Debug: Print all command line arguments
    print(f"DEBUG: Command line arguments: {sys.argv}", file=sys.stderr)

    # Smart NXM Handler Logic
    nxm_url = next((arg for arg in sys.argv if arg.startswith("nxm://")), None)
    if nxm_url:
        logger = get_logger(__name__)
        logger.info(f"NXM link detected: {nxm_url}")

        from utils.settings_manager import SettingsManager
        from utils.game_finder import GameFinder, GameInfo
        from utils.steam_utils import SteamUtils
        from utils.heroic_utils import HeroicUtils
        import subprocess
        import os

        # 1. Parse the game from the NXM URL
        try:
            game_domain = nxm_url.split('/')[2]
            logger.info(f"Parsed game domain: {game_domain}")
        except IndexError:
            logger.error("Invalid NXM URL format. Could not parse game domain.")
            return 1

        # 2. Find the game installation
        logger.info(f"Searching for '{game_domain}' in Steam and Heroic libraries...")
        game_finder = GameFinder()
        all_games = game_finder.find_games()
        
        target_game: Optional[GameInfo] = None
        for game in all_games:
            # A simple matching logic. This can be improved with a mapping of nxm domains to game names.
            if game_domain.lower().replace(" ", "") in game.name.lower().replace(" ", ""):
                target_game = game
                logger.info(f"Found matching game: {game.name} (Platform: {game.platform})")
                break
        
        if not target_game:
            logger.error(f"Could not find an installed game matching '{game_domain}'.")
            return 1

        settings = SettingsManager()

        # 3. Handle based on platform
        if target_game.platform.startswith("Steam"):
            logger.info("Game is on Steam. Using Steam NXM handler.")
            mo2_appid = settings.get_nxm_steam_mo2_appid()

            if not mo2_appid:
                logger.error("NXM handler triggered for a Steam game, but no Steam MO2 AppID is configured.")
                return 1
            
            logger.info(f"Found configured Steam MO2 AppID: {mo2_appid}. Launching via Steam...")
            command = ["steam", f"steam://run/{mo2_appid}//{nxm_url}"]
            
            try:
                subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info("Successfully launched Steam MO2 to handle the NXM link.")
                return 0
            except Exception as e:
                logger.error(f"Failed to launch Steam: {e}")
                return 1

        elif target_game.platform.startswith("Heroic"):
            logger.info("Game is on Heroic. Using Heroic NXM handler.")
            mo2_path = settings.get_nxm_heroic_mo2_path()

            if not mo2_path or not os.path.exists(mo2_path):
                logger.error(f"NXM handler triggered for a Heroic game, but the configured MO2 path is invalid or not set. Path: '{mo2_path}'")
                return 1

            heroic_utils = HeroicUtils()
            prefix_path = heroic_utils.get_prefix_for_game(target_game)

            if not prefix_path:
                logger.error(f"Found Heroic game '{target_game.name}' but could not locate its Wine prefix.")
                return 1
            
            logger.info(f"Found Heroic prefix: {prefix_path}")
            logger.info(f"Launching MO2 executable: {mo2_path}")

            try:
                env = os.environ.copy()
                env["WINEPREFIX"] = prefix_path
                
                # We need to find the correct wine binary. For now, we assume 'wine' is in PATH.
                # A better implementation would get the specific runner from Heroic's config for the game.
                command = ["wine", mo2_path, nxm_url]
                
                subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info("Successfully launched Heroic MO2 to handle the NXM link.")
                return 0
            except Exception as e:
                logger.error(f"Failed to launch MO2 in Heroic prefix: {e}")
                return 1
        
        else:
            logger.warning(f"Game '{target_game.name}' found, but its platform '{target_game.platform}' is not supported by the NXM handler.")
            return 1

    # Create parser
    parser = create_parser()
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check if command was provided
    if not args.command:
        parser.print_help()
        return 1
    
    # Create and run application
    app = NaKApp()
    return app.run(args)


if __name__ == "__main__":
    sys.exit(main())
