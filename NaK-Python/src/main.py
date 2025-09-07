#!/usr/bin/env python3
"""
Main application module for NaK Python
"""
import argparse
import sys
from typing import Dict, Any

from .core.core import Core
from .utils.logger import get_logger, setup_logging


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
                return self._install_mo2()
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
        self.logger.info("Checking dependencies...")
        
        if self.core.check_dependencies():
            print("✅ All dependencies are available!")
            return 0
        else:
            print("❌ Some dependencies are missing!")
            return 1
    
    def _list_games(self) -> int:
        """List non-Steam games"""
        self.logger.info("Listing non-Steam games...")
        
        games = self.core.get_non_steam_games()
        if not games:
            print("No non-Steam games found.")
            return 0
        
        print("📋 Non-Steam Games:")
        print("----------------------------------------")
        for i, game in enumerate(games, 1):
            print(f" {i}. {game.get('Name', 'Unknown')} (AppID: {game.get('AppID', 'Unknown')})")
        
        return 0
    
    def _install_mo2(self) -> int:
        """Install Mod Organizer 2"""
        self.logger.info("Installing Mod Organizer 2...")
        
        result = self.core.install_mo2()
        if result.get("success"):
            print("✅ Mod Organizer 2 installed successfully!")
            print(f"Installation directory: {result.get('install_dir')}")
            print(f"MO2 executable: {result.get('mo2_exe')}")
            return 0
        else:
            print(f"❌ Failed to install Mod Organizer 2: {result.get('error')}")
            return 1
    
    def _add_game_to_steam(self, name: str, exe_path: str) -> int:
        """Add a game to Steam"""
        self.logger.info(f"Adding '{name}' to Steam...")
        
        result = self.core.steam_utils.add_game_to_steam(name, exe_path)
        if result.get("success"):
            print("✅ Success!")
            print(f"   AppID: {result.get('app_id')}")
            print(f"   Compat data path: {result.get('compat_data_path')}")
            print(f"   Message: {result.get('message')}")
            return 0
        else:
            print(f"❌ Failed to add game to Steam: {result.get('error')}")
            return 1
    
    def _install_dependencies(self, game_id: str) -> int:
        """Install dependencies for a game"""
        self.logger.info(f"Installing dependencies for game {game_id}...")
        
        result = self.core.dependency_installer.install_dependencies_for_game(game_id)
        if result.get("success"):
            print("✅ Dependencies installed successfully!")
            print(result.get("message", ""))
            return 0
        else:
            print(f"❌ Failed to install dependencies: {result.get('error')}")
            return 1
    
    def _install_mo2_dependencies(self, game_id: str) -> int:
        """Install MO2 dependencies for a game"""
        self.logger.info(f"Installing MO2 dependencies for game {game_id}...")
        
        result = self.core.dependency_installer.install_mo2_dependencies_for_game(game_id)
        if result.get("success"):
            print("✅ MO2 dependencies installed successfully!")
            print(result.get("message", ""))
            return 0
        else:
            print(f"❌ Failed to install MO2 dependencies: {result.get('error')}")
            return 1
    
    def _setup_fnv_dependencies(self) -> int:
        """Setup Fallout New Vegas dependencies"""
        self.logger.info("Setting up FNV dependencies...")
        
        result = self.core.dependency_installer.setup_fnv_dependencies()
        if result.get("success"):
            print("✅ FNV dependencies setup complete!")
            print(result.get("message", ""))
            return 0
        else:
            print(f"❌ Failed to setup FNV dependencies: {result.get('error')}")
            return 1
    
    def _setup_enderal_dependencies(self) -> int:
        """Setup Enderal dependencies"""
        self.logger.info("Setting up Enderal dependencies...")
        
        result = self.core.dependency_installer.setup_enderal_dependencies()
        if result.get("success"):
            print("✅ Enderal dependencies setup complete!")
            print(result.get("message", ""))
            return 0
        else:
            print(f"❌ Failed to setup Enderal dependencies: {result.get('error')}")
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
    subparsers.add_parser("install-mo2", help="Install Mod Organizer 2")
    
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
    setup_logging()
    
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
