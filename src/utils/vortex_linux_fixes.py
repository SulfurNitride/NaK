"""
Vortex Linux Compatibility Fixes

This module handles Linux-specific workarounds for Vortex Mod Manager:
1. Automatic staging folder setup in Steam library
2. Case-sensitivity fixes for Bethesda games (lowercase ESM symlinks)
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from src.utils.logger import get_logger


class VortexLinuxFixes:
    """Handles Linux-specific compatibility fixes for Vortex"""

    # Game IDs that Vortex uses internally
    # folder_patterns: list of possible folder name patterns to search for
    BETHESDA_GAMES = {
        "skyrim": {"name": "Skyrim", "folder_patterns": ["Skyrim"]},
        "skyrimse": {"name": "Skyrim Special Edition", "folder_patterns": ["Skyrim Special Edition"]},
        "skyrimvr": {"name": "Skyrim VR", "folder_patterns": ["SkyrimVR"]},
        "oblivion": {"name": "Oblivion", "folder_patterns": ["Oblivion"]},
        "fallout3": {"name": "Fallout 3", "folder_patterns": ["Fallout 3 goty", "Fallout 3"]},
        "falloutnv": {"name": "Fallout New Vegas", "folder_patterns": ["Fallout New Vegas"]},
        "fallout4": {"name": "Fallout 4", "folder_patterns": ["Fallout 4"]},
        "fallout4vr": {"name": "Fallout 4 VR", "folder_patterns": ["Fallout 4 VR"]},
        "starfield": {"name": "Starfield", "folder_patterns": ["Starfield"]}
    }

    # Base ESMs that need lowercase symlinks (case-sensitivity fix for LOOT)
    BASE_ESMS = {
        "skyrim": ["Skyrim.esm", "Update.esm"],
        "skyrimse": ["Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm"],
        "skyrimvr": ["Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm", "SkyrimVR.esm"],
        "oblivion": ["Oblivion.esm"],
        "fallout3": ["Fallout3.esm"],
        "falloutnv": ["FalloutNV.esm"],
        "fallout4": ["Fallout4.esm"],
        "fallout4vr": ["Fallout4.esm", "Fallout4_VR.esm"],
        "starfield": ["Starfield.esm"]
    }

    def __init__(self):
        self.logger = get_logger(__name__)

    def setup_staging_folders(self, steam_library_path: str) -> Dict[str, str]:
        """
        Create Vortex staging folders in the Steam library

        Returns dict with game_id -> staging_path
        """
        try:
            staging_root = Path(steam_library_path) / "steamapps" / "VortexStaging"
            staging_root.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Created Vortex staging root: {staging_root}")

            created_folders = {}
            for game_id, game_info in self.BETHESDA_GAMES.items():
                staging_path = staging_root / game_id
                staging_path.mkdir(exist_ok=True)
                created_folders[game_id] = str(staging_path)
                self.logger.info(f"  ✓ Created staging folder for {game_info['name']}: {staging_path}")

            return created_folders

        except Exception as e:
            self.logger.error(f"Failed to setup staging folders: {e}")
            return {}

    def find_game_data_folder(self, steam_library_path: str, game_id: str) -> Optional[str]:
        """Find the game's Data folder in the Steam library"""
        try:
            if game_id not in self.BETHESDA_GAMES:
                return None

            game_info = self.BETHESDA_GAMES[game_id]
            common_path = Path(steam_library_path) / "steamapps" / "common"

            # Try each possible folder pattern
            for folder_pattern in game_info["folder_patterns"]:
                data_folder = common_path / folder_pattern / "Data"

                if data_folder.exists():
                    self.logger.info(f"Found {game_info['name']} Data folder: {data_folder}")
                    return str(data_folder)

            return None

        except Exception as e:
            self.logger.error(f"Failed to find game Data folder: {e}")
            return None

    def create_lowercase_esm_symlinks(self, data_folder: str, game_id: str) -> Dict[str, any]:
        """
        Create lowercase symlinks for base game ESMs to fix LOOT case-sensitivity

        Args:
            data_folder: Path to game's Data folder
            game_id: Vortex game ID (e.g., "skyrimse")

        Returns:
            Dict with success status and created symlinks
        """
        try:
            if game_id not in self.BASE_ESMS:
                self.logger.warning(f"No base ESMs defined for game_id: {game_id}")
                return {"success": False, "error": "Game not supported for ESM fix"}

            data_path = Path(data_folder)
            if not data_path.exists():
                return {"success": False, "error": f"Data folder not found: {data_folder}"}

            created_symlinks = []
            skipped_symlinks = []
            esms_to_fix = self.BASE_ESMS[game_id]

            self.logger.info(f"Creating lowercase ESM symlinks for {game_id}...")

            for esm_file in esms_to_fix:
                source_file = data_path / esm_file
                lowercase_name = esm_file.lower()
                target_file = data_path / lowercase_name

                # Skip if source doesn't exist
                if not source_file.exists():
                    self.logger.warning(f"  ⚠ Source file not found: {esm_file}")
                    continue

                # Skip if lowercase already exists
                if target_file.exists() or target_file.is_symlink():
                    self.logger.info(f"  ✓ Lowercase symlink already exists: {lowercase_name}")
                    skipped_symlinks.append(lowercase_name)
                    continue

                # Create symlink
                try:
                    target_file.symlink_to(esm_file)
                    created_symlinks.append(lowercase_name)
                    self.logger.info(f"  ✓ Created symlink: {lowercase_name} → {esm_file}")
                except Exception as e:
                    self.logger.error(f"  ✗ Failed to create symlink for {esm_file}: {e}")

            # Also handle _ResourcePack.esl for Skyrim SE/AE
            if game_id in ["skyrimse", "skyrimvr"]:
                resource_pack = data_path / "_ResourcePack.esl"
                if resource_pack.exists():
                    lowercase_resource = data_path / "_resourcepack.esl"
                    if not lowercase_resource.exists():
                        try:
                            lowercase_resource.symlink_to("_ResourcePack.esl")
                            created_symlinks.append("_resourcepack.esl")
                            self.logger.info(f"  ✓ Created symlink: _resourcepack.esl → _ResourcePack.esl")
                        except Exception as e:
                            self.logger.error(f"  ✗ Failed to create _resourcepack symlink: {e}")

            result = {
                "success": True,
                "created_symlinks": created_symlinks,
                "skipped_symlinks": skipped_symlinks,
                "total_created": len(created_symlinks),
                "game_id": game_id
            }

            if created_symlinks:
                self.logger.info(f"✓ Created {len(created_symlinks)} lowercase ESM symlinks for case-sensitivity fix")
            else:
                self.logger.info("No new symlinks needed (all already exist)")

            return result

        except Exception as e:
            self.logger.error(f"Failed to create lowercase ESM symlinks: {e}")
            return {"success": False, "error": str(e)}

    def get_vortex_staging_path_instructions(self, game_id: str, steam_library: str) -> Dict[str, str]:
        """
        Get the path the user needs to paste into Vortex for staging folder

        Returns dict with Z: drive path and instructions
        """
        try:
            if game_id not in self.BETHESDA_GAMES:
                return {"error": f"Game ID not supported: {game_id}"}

            # Linux path
            linux_path = f"{steam_library}/steamapps/VortexStaging/{game_id}"

            # Convert to Z: drive path for Vortex
            z_drive_path = f"Z:{linux_path.replace('/', '\\')}"

            game_name = self.BETHESDA_GAMES[game_id]["name"]

            return {
                "game_id": game_id,
                "game_name": game_name,
                "linux_path": linux_path,
                "vortex_path": z_drive_path,
                "instructions": f"In Vortex, go to Settings → Mods → Mod Staging Folder and set:\n{z_drive_path}"
            }

        except Exception as e:
            self.logger.error(f"Failed to get staging path instructions: {e}")
            return {"error": str(e)}

    def detect_and_fix_installed_games(self, steam_library: str) -> Dict[str, any]:
        """
        Detect all installed Bethesda games and apply fixes

        Returns dict with results for each game
        """
        try:
            self.logger.info("Detecting installed Bethesda games and applying Linux fixes...")

            results = {
                "staging_folders_created": {},
                "games_fixed": {},
                "games_not_found": [],
                "vortex_paths": {}
            }

            # Create all staging folders
            results["staging_folders_created"] = self.setup_staging_folders(steam_library)

            # Check each game and apply fixes if installed
            for game_id, game_info in self.BETHESDA_GAMES.items():
                game_name = game_info["name"]
                data_folder = self.find_game_data_folder(steam_library, game_id)

                if data_folder:
                    self.logger.info(f"Found {game_name}, applying fixes...")

                    # Create lowercase ESM symlinks
                    esm_result = self.create_lowercase_esm_symlinks(data_folder, game_id)
                    results["games_fixed"][game_id] = esm_result

                    # Get path instructions for Vortex
                    path_info = self.get_vortex_staging_path_instructions(game_id, steam_library)
                    results["vortex_paths"][game_id] = path_info

                    self.logger.info(f"✓ Fixed {game_name}")
                else:
                    results["games_not_found"].append(game_id)

            self.logger.info(f"Fixes applied to {len(results['games_fixed'])} game(s)")
            return results

        except Exception as e:
            self.logger.error(f"Failed to detect and fix games: {e}")
            return {"error": str(e)}
