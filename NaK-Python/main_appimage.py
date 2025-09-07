#!/usr/bin/env python3
"""
NaK - Linux Modding Helper
Main entry point for the AppImage version
"""

import sys
import os
import argparse
import logging

# In AppImage, the source code is in the nak package
# Add the site-packages directory to the Python path first
site_packages = os.path.join(os.path.dirname(__file__), '..', 'lib', 'python3', 'site-packages')
sys.path.insert(0, site_packages)

# Now try to import PySide6 and other modules
try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QCoreApplication
    
    from nak.gui.main_window import main as gui_main
    from nak.core.core import Core
    from nak.utils.logger import setup_logging, get_logger
except ImportError as e:
    print(f"Import error in AppImage: {e}", file=sys.stderr)
    print(f"Python path: {sys.path}", file=sys.stderr)
    print(f"Site packages path: {site_packages}", file=sys.stderr)
    print(f"Site packages exists: {os.path.exists(site_packages)}", file=sys.stderr)
    if os.path.exists(site_packages):
        print(f"Contents of site-packages: {os.listdir(site_packages)}", file=sys.stderr)
    
    # Fallback for development
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import QCoreApplication
        from gui.main_window import main as gui_main
        from core.core import Core
        from utils.logger import setup_logging, get_logger
    except ImportError as e2:
        print(f"Fallback import also failed: {e2}", file=sys.stderr)
        sys.exit(1)


class NaKAppImage:
    """Main NaK AppImage application class"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.core = Core()
    
    def run_cli(self, args: argparse.Namespace) -> int:
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
        description="NaK - Linux Modding Helper (Python AppImage)",
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


def app_main():
    """Main application entry point"""
    try:
        # Setup logging
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("Starting NaK - Linux Modding Helper (Python AppImage)")
        
        # Create core application
        core = Core()
        
        # Check dependencies
        try:
            core.check_dependencies()
            logger.info("All dependencies are available")
        except Exception as e:
            logger.warning(f"Dependency check failed: {e}")
            # Continue anyway - user can still use some features
        
        # Parse command line arguments
        parser = create_parser()
        args = parser.parse_args()
        
        # If no command provided, launch GUI
        if not args.command:
            # Run GUI using PySide6
            gui_main()
            logger.info("GUI started successfully")
            return 0
        
        # Run CLI commands
        app = NaKAppImage()
        return app.run_cli(args)
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        # Show error dialog if GUI is available
        try:
            # Check if QApplication already exists
            app = QCoreApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("NaK Error")
            msg_box.setText(f"Application failed to start:\n{str(e)}")
            msg_box.exec()
        except:
            # Fallback to console output
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    sys.exit(app_main())
