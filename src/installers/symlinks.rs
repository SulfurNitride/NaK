//! Symlink management for NaK prefixes
//!
//! Creates symlinks FROM NaK prefix TO game prefixes.
//! Data stays in the game prefix, NaK just has links pointing to it.
//!
//! This inverted approach means:
//! - Game saves remain in their original location (Steam cloud sync works)
//! - NaK prefix provides unified access to all game data
//! - No data duplication or sync issues
//!
//! NaK Tools folder contains convenience symlinks pointing INTO the prefix
//! for easy access to Documents, AppData, etc.

// Allow unused items - some functions are public API for future use
#![allow(dead_code)]

use std::fs;
use std::path::Path;

use crate::game_finder::{detect_all_games, Game, GameScanResult};
use crate::logging::{log_info, log_warning};

// ============================================================================
// Public API
// ============================================================================

/// Create symlinks from NaK prefix to game prefixes for all detected games
///
/// This creates symlinks in the NaK prefix pointing to the actual save/config
/// folders in each game's own prefix. The symlink direction is:
///
/// NaK/Documents/My Games/Skyrim -> game_prefix/Documents/My Games/Skyrim
/// NaK/AppData/Local/Skyrim -> game_prefix/AppData/Local/Skyrim
///
/// Data stays in the game prefix (preserving Steam Cloud sync), while NaK
/// provides unified access through symlinks.
pub fn create_game_symlinks(nak_prefix: &Path, games: &[Game]) {
    let users_dir = nak_prefix.join("drive_c/users");
    let username = find_prefix_username(&users_dir);
    let user_dir = users_dir.join(&username);

    let documents = user_dir.join("Documents");
    let my_games = documents.join("My Games");
    let appdata_local = user_dir.join("AppData/Local");
    let appdata_roaming = user_dir.join("AppData/Roaming");

    // Ensure base directories exist (real folders in NaK prefix)
    let _ = fs::create_dir_all(&my_games);
    let _ = fs::create_dir_all(&appdata_local);
    let _ = fs::create_dir_all(&appdata_roaming);

    let mut linked_count = 0;

    for game in games {
        // Skip games without prefixes
        let Some(game_prefix) = &game.prefix_path else {
            continue;
        };

        // Link My Games folder
        if let Some(folder) = &game.my_games_folder {
            if link_game_folder(
                &my_games.join(folder),
                game_prefix,
                &format!("Documents/My Games/{}", folder),
                &game.name,
            ) {
                linked_count += 1;
            }
        }

        // Link AppData/Local folder
        if let Some(folder) = &game.appdata_local_folder {
            if link_game_folder(
                &appdata_local.join(folder),
                game_prefix,
                &format!("AppData/Local/{}", folder),
                &game.name,
            ) {
                linked_count += 1;
            }
        }

        // Link AppData/Roaming folder
        if let Some(folder) = &game.appdata_roaming_folder {
            if link_game_folder(
                &appdata_roaming.join(folder),
                game_prefix,
                &format!("AppData/Roaming/{}", folder),
                &game.name,
            ) {
                linked_count += 1;
            }
        }
    }

    if linked_count > 0 {
        log_info(&format!(
            "Created {} symlinks to game prefixes",
            linked_count
        ));
    }

    // Create "My Documents" symlink for compatibility
    let my_documents = user_dir.join("My Documents");
    if !my_documents.exists() && fs::symlink_metadata(&my_documents).is_err() {
        if let Err(e) = std::os::unix::fs::symlink("Documents", &my_documents) {
            log_warning(&format!("Failed to create My Documents symlink: {}", e));
        }
    }
}

/// Create NaK Tools convenience symlinks pointing INTO the prefix
///
/// Creates symlinks in NaK Tools folder for easy access:
/// - NaK Tools/Prefix Documents -> prefix/drive_c/users/<user>/Documents
/// - NaK Tools/Prefix AppData Local -> prefix/drive_c/users/<user>/AppData/Local
/// - NaK Tools/Prefix AppData Roaming -> prefix/drive_c/users/<user>/AppData/Roaming
pub fn create_nak_tools_symlinks(tools_dir: &Path, prefix_path: &Path) {
    let users_dir = prefix_path.join("drive_c/users");
    let username = find_prefix_username(&users_dir);
    let user_dir = users_dir.join(&username);

    // Symlink: NaK Tools/Prefix Documents -> prefix Documents
    let documents_link = tools_dir.join("Prefix Documents");
    let documents_target = user_dir.join("Documents");
    create_or_update_symlink(&documents_link, &documents_target, "Prefix Documents");

    // Symlink: NaK Tools/Prefix AppData Local -> prefix AppData/Local
    let appdata_local_link = tools_dir.join("Prefix AppData Local");
    let appdata_local_target = user_dir.join("AppData/Local");
    create_or_update_symlink(&appdata_local_link, &appdata_local_target, "Prefix AppData Local");

    // Symlink: NaK Tools/Prefix AppData Roaming -> prefix AppData/Roaming
    let appdata_roaming_link = tools_dir.join("Prefix AppData Roaming");
    let appdata_roaming_target = user_dir.join("AppData/Roaming");
    create_or_update_symlink(&appdata_roaming_link, &appdata_roaming_target, "Prefix AppData Roaming");

    log_info("Created NaK Tools convenience symlinks to prefix folders");
}

/// Create or update a symlink
fn create_or_update_symlink(link_path: &Path, target: &Path, name: &str) {
    // Remove existing symlink or file
    if link_path.exists() || fs::symlink_metadata(link_path).is_ok() {
        let _ = fs::remove_file(link_path);
        let _ = fs::remove_dir_all(link_path);
    }

    // Create symlink
    if let Err(e) = std::os::unix::fs::symlink(target, link_path) {
        log_warning(&format!("Failed to create {} symlink: {}", name, e));
    }
}

/// Create symlinks for all detected games
///
/// Convenience function that detects games and creates symlinks in one call.
pub fn create_game_symlinks_auto(nak_prefix: &Path) -> GameScanResult {
    let result = detect_all_games();
    create_game_symlinks(nak_prefix, &result.games);
    result
}

/// Ensure only the Temp directory exists in AppData/Local
///
/// MO2 and other tools require AppData/Local/Temp to exist.
/// We create only this essential directory, leaving other game-specific
/// folders to be symlinked from game prefixes.
pub fn ensure_temp_directory(prefix_path: &Path) {
    let users_dir = prefix_path.join("drive_c/users");
    let username = find_prefix_username(&users_dir);
    let user_dir = users_dir.join(&username);

    let temp_dir = user_dir.join("AppData/Local/Temp");
    if let Err(e) = fs::create_dir_all(&temp_dir) {
        log_warning(&format!("Failed to create Temp directory: {}", e));
    } else {
        log_info("Ensured AppData/Local/Temp directory exists");
    }
}

// ============================================================================
// Internal Functions
// ============================================================================

/// Create a symlink from NaK prefix to a game prefix folder
///
/// Returns true if a symlink was created (or already existed correctly)
fn link_game_folder(
    nak_path: &Path,
    game_prefix: &Path,
    relative_path: &str,
    game_name: &str,
) -> bool {
    // Build the source path in the game prefix
    let game_users_dir = game_prefix.join("drive_c/users");
    let game_username = find_prefix_username(&game_users_dir);
    let source_path = game_users_dir.join(&game_username).join(relative_path);

    // Only link if the source exists in the game prefix
    if !source_path.exists() {
        return false;
    }

    // Check if target already exists
    if nak_path.exists() || fs::symlink_metadata(nak_path).is_ok() {
        // Check if it's already a symlink to the correct location
        if let Ok(target) = fs::read_link(nak_path) {
            if target == source_path {
                return true; // Already correctly linked
            }
        }
        // Something else exists here, don't overwrite
        return false;
    }

    // Ensure parent directory exists
    if let Some(parent) = nak_path.parent() {
        let _ = fs::create_dir_all(parent);
    }

    // Create the symlink
    match std::os::unix::fs::symlink(&source_path, nak_path) {
        Ok(()) => {
            log_info(&format!(
                "Linked {} -> {}",
                nak_path.display(),
                source_path.display()
            ));
            true
        }
        Err(e) => {
            log_warning(&format!(
                "Failed to create symlink for {} ({}): {}",
                game_name,
                relative_path,
                e
            ));
            false
        }
    }
}

/// Find the username from a Wine prefix users directory
fn find_prefix_username(users_dir: &Path) -> String {
    if let Ok(entries) = fs::read_dir(users_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name != "Public" && name != "root" {
                return name;
            }
        }
    }
    "steamuser".to_string()
}

// ============================================================================
// Oblivion Lowercase INI Symlinks
// ============================================================================

/// Create lowercase INI symlinks for Oblivion (some tools expect lowercase)
pub fn create_oblivion_ini_symlinks(prefix_path: &Path) {
    let users_dir = prefix_path.join("drive_c/users");
    let username = find_prefix_username(&users_dir);
    let oblivion_dir = users_dir
        .join(&username)
        .join("Documents/My Games/Oblivion");

    if !oblivion_dir.exists() {
        return;
    }

    create_lowercase_ini_symlink(&oblivion_dir, "Oblivion.ini", "oblivion.ini");
    create_lowercase_ini_symlink(&oblivion_dir, "OblivionPrefs.ini", "oblivionprefs.ini");
}

/// Create a lowercase symlink for an INI file
fn create_lowercase_ini_symlink(dir: &Path, original: &str, lowercase: &str) {
    let original_path = dir.join(original);
    let lowercase_path = dir.join(lowercase);

    // Only create if original exists and lowercase doesn't
    if original_path.exists()
        && !lowercase_path.exists()
        && fs::symlink_metadata(&lowercase_path).is_err()
    {
        // Create relative symlink (just the filename)
        if let Err(e) = std::os::unix::fs::symlink(original, &lowercase_path) {
            log_warning(&format!(
                "Failed to create lowercase symlink {} -> {}: {}",
                lowercase, original, e
            ));
        } else {
            log_info(&format!(
                "Created lowercase INI symlink: {} -> {}",
                lowercase, original
            ));
        }
    }
}
