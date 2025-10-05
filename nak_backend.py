#!/usr/bin/env python3
"""
NaK Linux Modding Helper - Backend CLI
This is the Python backend that Tauri will call via subprocess
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from utils.game_finder import GameFinder
from utils.comprehensive_game_manager import ComprehensiveGameManager
from core.dependency_installer import DependencyInstaller
from core.mo2_installer import MO2Installer
from utils.logger import setup_logger

def scan_games():
    """Scan for installed games"""
    try:
        logger = setup_logger()
        logger.info("Scanning for games...")
        
        # Initialize game manager
        game_manager = ComprehensiveGameManager()
        
        # Scan for games
        games = game_manager.scan_all_games()
        
        # Format results
        game_list = []
        for game in games:
            game_info = {
                'name': game.name,
                'path': str(game.install_path),
                'platform': game.platform,
                'steam_id': getattr(game, 'steam_id', None),
                'heroic_id': getattr(game, 'heroic_id', None)
            }
            game_list.append(game_info)
        
        result = {
            'success': True,
            'count': len(game_list),
            'games': game_list
        }
        
        print(json.dumps(result, indent=2))
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'count': 0,
            'games': []
        }
        print(json.dumps(error_result, indent=2))
        return error_result

def check_dependencies():
    """Check system dependencies"""
    try:
        logger = setup_logger()
        logger.info("Checking dependencies...")
        
        # Initialize dependency installer
        dep_installer = DependencyInstaller()
        
        # Check dependencies
        status = dep_installer.check_all_dependencies()
        
        result = {
            'success': True,
            'dependencies': status
        }
        
        print(json.dumps(result, indent=2))
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'dependencies': {}
        }
        print(json.dumps(error_result, indent=2))
        return error_result

def install_mo2():
    """Install Mod Organizer 2"""
    try:
        logger = setup_logger()
        logger.info("Installing Mod Organizer 2...")
        
        # Initialize MO2 installer
        mo2_installer = MO2Installer()
        
        # Install MO2
        result = mo2_installer.install_mo2()
        
        output = {
            'success': result,
            'message': 'Mod Organizer 2 installation completed' if result else 'Mod Organizer 2 installation failed'
        }
        
        print(json.dumps(output, indent=2))
        return output
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'message': f'Error installing MO2: {str(e)}'
        }
        print(json.dumps(error_result, indent=2))
        return error_result

def launch_mo2():
    """Launch Mod Organizer 2"""
    try:
        logger = setup_logger()
        logger.info("Launching Mod Organizer 2...")
        
        # Initialize MO2 installer
        mo2_installer = MO2Installer()
        
        # Launch MO2
        result = mo2_installer.launch_mo2()
        
        output = {
            'success': result,
            'message': 'Mod Organizer 2 launched successfully' if result else 'Failed to launch Mod Organizer 2'
        }
        
        print(json.dumps(output, indent=2))
        return output
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'message': f'Error launching MO2: {str(e)}'
        }
        print(json.dumps(error_result, indent=2))
        return error_result

def main():
    parser = argparse.ArgumentParser(description='NaK Linux Modding Helper Backend')
    parser.add_argument('--scan-games', action='store_true', help='Scan for installed games')
    parser.add_argument('--check-dependencies', action='store_true', help='Check system dependencies')
    parser.add_argument('--install-mo2', action='store_true', help='Install Mod Organizer 2')
    parser.add_argument('--launch-mo2', action='store_true', help='Launch Mod Organizer 2')
    
    args = parser.parse_args()
    
    # Execute the requested command
    if args.scan_games:
        scan_games()
    elif args.check_dependencies:
        check_dependencies()
    elif args.install_mo2:
        install_mo2()
    elif args.launch_mo2:
        launch_mo2()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
