#!/usr/bin/env python3
"""
NaK Linux Modding Helper - Simple Backend CLI
This is a simplified Python backend that Tauri will call via subprocess
"""

import sys
import os
import argparse
import json
import subprocess
import platform
from pathlib import Path

def scan_games():
    """Scan for installed games using the comprehensive GameFinder"""
    try:
        # Import the proper GameFinder
        from src.utils.game_finder import GameFinder
        
        # Create GameFinder instance and find games
        game_finder = GameFinder()
        detected_games = game_finder.find_all_games()
        
        # Convert GameInfo objects to dictionaries
        games = [{
            'name': game.name,
            'path': game.path,
            'platform': game.platform,
            'app_id': game.app_id
        } for game in detected_games]
        
        result = {
            'success': True,
            'count': len(games),
            'games': games
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
        dependencies = {
            'python': {
                'installed': True,
                'version': platform.python_version(),
                'status': 'OK'
            },
            'wine': {
                'installed': False,
                'version': None,
                'status': 'Not found'
            },
            'winetricks': {
                'installed': False,
                'version': None,
                'status': 'Not found'
            }
        }
        
        # Check for Wine
        try:
            result = subprocess.run(['wine', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                dependencies['wine']['installed'] = True
                dependencies['wine']['version'] = result.stdout.strip()
                dependencies['wine']['status'] = 'OK'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Check for winetricks
        try:
            result = subprocess.run(['winetricks', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                dependencies['winetricks']['installed'] = True
                dependencies['winetricks']['version'] = result.stdout.strip()
                dependencies['winetricks']['status'] = 'OK'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        result = {
            'success': True,
            'dependencies': dependencies
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
        # For now, just return a placeholder response
        result = {
            'success': True,
            'message': 'MO2 installation would be implemented here'
        }
        
        print(json.dumps(result, indent=2))
        return result
        
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
        # For now, just return a placeholder response
        result = {
            'success': True,
            'message': 'MO2 launch would be implemented here'
        }
        
        print(json.dumps(result, indent=2))
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'message': f'Error launching MO2: {str(e)}'
        }
        print(json.dumps(error_result, indent=2))
        return error_result

def find_existing_mo2():
    """Find existing MO2 installations"""
    try:
        installations = []
        
        # Common MO2 installation locations
        search_paths = [
            Path.home() / ".local" / "share" / "Steam" / "steamapps" / "compatdata",
            Path.home() / ".steam" / "steam" / "steamapps" / "compatdata",
            Path.home() / "Games",
            Path.home() / ".wine",
            Path.home() / "Documents",
        ]
        
        # Look for ModOrganizer.exe in wine prefixes
        for search_path in search_paths:
            if not search_path.exists():
                continue
                
            # Search for ModOrganizer.exe recursively
            for mo2_exe in search_path.rglob("ModOrganizer.exe"):
                mo2_dir = mo2_exe.parent
                
                # Check if it's a valid MO2 installation
                if (mo2_dir / "ModOrganizer.exe").exists():
                    # Try to determine the wine prefix
                    prefix_path = None
                    current = mo2_dir
                    while current != current.parent:
                        if (current / "system.reg").exists() or (current / "user.reg").exists():
                            prefix_path = str(current)
                            break
                        current = current.parent
                    
                    installation = {
                        'path': str(mo2_dir),
                        'exe': str(mo2_exe),
                        'prefix': prefix_path,
                        'version': 'Unknown'  # Could parse version from exe if needed
                    }
                    
                    # Avoid duplicates
                    if installation not in installations:
                        installations.append(installation)
        
        result = {
            'success': True,
            'count': len(installations),
            'installations': installations
        }
        
        print(json.dumps(result, indent=2))
        return result
        
    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'count': 0,
            'installations': []
        }
        print(json.dumps(error_result, indent=2))
        return error_result

def main():
    parser = argparse.ArgumentParser(description='NaK Linux Modding Helper Backend')
    parser.add_argument('--scan-games', action='store_true', help='Scan for installed games')
    parser.add_argument('--check-dependencies', action='store_true', help='Check system dependencies')
    parser.add_argument('--install-mo2', action='store_true', help='Install Mod Organizer 2')
    parser.add_argument('--launch-mo2', action='store_true', help='Launch Mod Organizer 2')
    parser.add_argument('--find-mo2', action='store_true', help='Find existing MO2 installations')
    
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
    elif args.find_mo2:
        find_existing_mo2()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
