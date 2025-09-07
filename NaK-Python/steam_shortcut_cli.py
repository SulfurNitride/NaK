#!/usr/bin/env python3
"""
CLI interface for Steam shortcut functionality
Provides command-line access to auto non-Steam game app ID adder and automatic prefix creation
"""

import sys
import argparse
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.steam_utils import SteamUtils

def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def list_games(steam_utils: SteamUtils):
    """List all non-Steam games"""
    print("📋 Non-Steam Games:")
    print("-" * 40)
    
    try:
        games = steam_utils.get_non_steam_games()
        if not games:
            print("No non-Steam games found.")
            return
        
        for i, game in enumerate(games, 1):
            print(f"{i:2d}. {game['Name']} (AppID: {game['AppID']})")
            
    except Exception as e:
        print(f"❌ Error listing games: {e}")

def add_game(steam_utils: SteamUtils, app_name: str, exe_path: str, proton_tool: str):
    """Add a game to Steam with automatic prefix creation"""
    print(f"🚀 Adding '{app_name}' to Steam...")
    print(f"   Executable: {exe_path}")
    print(f"   Proton tool: {proton_tool}")
    print("-" * 40)
    
    try:
        # Check if executable exists
        if not Path(exe_path).exists():
            print(f"❌ Error: Executable not found: {exe_path}")
            return
        
        # Add game to Steam
        result = steam_utils.add_game_to_steam(app_name, exe_path, proton_tool)
        
        if result["success"]:
            print("✅ Success!")
            print(f"   AppID: {result['app_id']}")
            print(f"   Compat data path: {result['compat_data_path']}")
            print(f"   Message: {result['message']}")
        else:
            print(f"❌ Failed: {result['error']}")
            
    except Exception as e:
        print(f"❌ Error adding game: {e}")

def create_shortcut_only(steam_utils: SteamUtils, app_name: str, exe_path: str, proton_tool: str):
    """Create only a Steam shortcut without prefix creation"""
    print(f"📝 Creating Steam shortcut for '{app_name}'...")
    print(f"   Executable: {exe_path}")
    print(f"   Proton tool: {proton_tool}")
    print("-" * 40)
    
    try:
        # Check if executable exists
        if not Path(exe_path).exists():
            print(f"❌ Error: Executable not found: {exe_path}")
            return
        
        # Create shortcut
        app_id = steam_utils.create_steam_shortcut(app_name, exe_path, proton_tool)
        
        print("✅ Shortcut created successfully!")
        print(f"   AppID: {app_id}")
        
    except Exception as e:
        print(f"❌ Error creating shortcut: {e}")

def create_prefix_only(steam_utils: SteamUtils, app_id: int, app_name: str):
    """Create only a Wine prefix for an existing game"""
    print(f"🍷 Creating Wine prefix for '{app_name}' (AppID: {app_id})...")
    print("-" * 40)
    
    try:
        # Create compatdata folder
        compat_data_path = steam_utils.create_compat_data_folder(app_id)
        print(f"✅ Compatdata folder created: {compat_data_path}")
        
        # Create and run .bat file
        success = steam_utils.create_and_run_bat_file(compat_data_path, app_name)
        
        if success:
            print("✅ Wine prefix created successfully!")
        else:
            print("❌ Failed to create Wine prefix")
            
    except Exception as e:
        print(f"❌ Error creating prefix: {e}")

def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Steam Shortcut Manager - Auto non-Steam game app ID adder and prefix creation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                                    # List all non-Steam games
  %(prog)s add "My Game" "/path/to/game.exe"      # Add game with prefix creation
  %(prog)s shortcut "My Game" "/path/to/game.exe" # Create shortcut only
  %(prog)s prefix 123456789 "My Game"             # Create prefix for existing game
        """
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all non-Steam games")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add game to Steam with prefix creation")
    add_parser.add_argument("app_name", help="Name of the application")
    add_parser.add_argument("exe_path", help="Path to the executable")
    add_parser.add_argument(
        "--proton", 
        default="proton_experimental",
        help="Proton tool to use (default: proton_experimental)"
    )
    
    # Shortcut command
    shortcut_parser = subparsers.add_parser("shortcut", help="Create Steam shortcut only")
    shortcut_parser.add_argument("app_name", help="Name of the application")
    shortcut_parser.add_argument("exe_path", help="Path to the executable")
    shortcut_parser.add_argument(
        "--proton", 
        default="proton_experimental",
        help="Proton tool to use (default: proton_experimental)"
    )
    
    # Prefix command
    prefix_parser = subparsers.add_parser("prefix", help="Create Wine prefix for existing game")
    prefix_parser.add_argument("app_id", type=int, help="Steam AppID")
    prefix_parser.add_argument("app_name", help="Name of the application")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Initialize Steam utils
    try:
        steam_utils = SteamUtils()
    except Exception as e:
        print(f"❌ Failed to initialize Steam utils: {e}")
        return 1
    
    # Execute command
    if args.command == "list":
        list_games(steam_utils)
    elif args.command == "add":
        add_game(steam_utils, args.app_name, args.exe_path, args.proton)
    elif args.command == "shortcut":
        create_shortcut_only(steam_utils, args.app_name, args.exe_path, args.proton)
    elif args.command == "prefix":
        create_prefix_only(steam_utils, args.app_id, args.app_name)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
