//! Bottles prefix detection
//!
//! Detects games installed in Bottles prefixes by scanning registry files
//! for known game registry entries.

use std::fs;
use std::path::{Component, Path, PathBuf};

use super::known_games::KNOWN_GAMES;
use super::registry::{read_registry_value, wine_path_to_linux};
use super::{Game, Launcher};
use crate::logging::log_info;

/// Possible Bottles data paths
const BOTTLES_PATHS: &[&str] = &[
    ".local/share/bottles/bottles",
    ".var/app/com.usebottles.bottles/data/bottles/bottles",
];

/// Normalize a path by resolving `.` and `..` components without requiring the path to exist.
/// Used to prevent path traversal when converting Wine registry paths.
fn normalize_path(p: &Path) -> PathBuf {
    let mut stack: Vec<Component<'_>> = Vec::new();
    for component in p.components() {
        match component {
            Component::ParentDir => { stack.pop(); }
            Component::CurDir => {}
            c => stack.push(c),
        }
    }
    stack.iter().collect()
}

/// Detect all games in Bottles prefixes
pub fn detect_bottles_games() -> Vec<Game> {
    let mut games = Vec::new();
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return games,
    };

    for relative_path in BOTTLES_PATHS {
        let bottles_path = PathBuf::from(&home).join(relative_path);
        if !bottles_path.exists() {
            continue;
        }

        log_info(&format!("Found Bottles installation: {}", bottles_path.display()));

        // Scan each bottle
        let Ok(entries) = fs::read_dir(&bottles_path) else {
            continue;
        };

        for entry in entries.flatten() {
            let bottle_path = entry.path();
            if !bottle_path.is_dir() {
                continue;
            }

            // Each bottle might have games
            let bottle_games = scan_bottle(&bottle_path);
            games.extend(bottle_games);
        }
    }

    log_info(&format!("Bottles: Found {} installed games", games.len()));
    games
}

/// Scan a single Bottles bottle for known games
fn scan_bottle(bottle_path: &Path) -> Vec<Game> {
    let mut games = Vec::new();

    // The prefix is directly in the bottle folder (not in pfx subfolder like Steam)
    // Check for drive_c to confirm it's a valid Wine prefix
    let drive_c = bottle_path.join("drive_c");
    if !drive_c.exists() {
        return games;
    }

    let bottle_name = bottle_path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("Unknown");

    // Check for each known game by registry entry
    for known_game in KNOWN_GAMES {
        if let Some(install_path_wine) =
            read_registry_value(bottle_path, known_game.registry_path, known_game.registry_value)
        {
            // Convert Wine path to Linux path
            let install_path = match wine_path_to_linux(&install_path_wine) {
                Some(p) => p,
                None => {
                    // Try as a relative path within drive_c
                    if install_path_wine.starts_with("C:") || install_path_wine.starts_with("c:") {
                        let relative = install_path_wine[2..].replace('\\', "/");
                        let candidate = drive_c.join(relative.trim_start_matches('/'));
                        // Normalize .. components and verify the path stays within drive_c
                        let normalized = normalize_path(&candidate);
                        if !normalized.starts_with(&drive_c) {
                            continue; // path traversal detected, skip
                        }
                        normalized
                    } else {
                        continue;
                    }
                }
            };

            if !install_path.exists() {
                continue;
            }

            log_info(&format!(
                "Found {} in Bottles bottle '{}'",
                known_game.name, bottle_name
            ));

            games.push(Game {
                name: known_game.name.to_string(),
                app_id: format!("bottles-{}", known_game.steam_app_id),
                install_path,
                prefix_path: Some(bottle_path.to_path_buf()),
                launcher: Launcher::Bottles,
                my_games_folder: known_game.my_games_folder.map(String::from),
                appdata_local_folder: known_game.appdata_local_folder.map(String::from),
                appdata_roaming_folder: known_game.appdata_roaming_folder.map(String::from),
                registry_path: Some(known_game.registry_path.to_string()),
                registry_value: Some(known_game.registry_value.to_string()),
            });
        }
    }

    games
}

/// Find all Bottles prefixes (for manual prefix selection)
pub fn find_bottles_prefixes() -> Vec<PathBuf> {
    let mut prefixes = Vec::new();
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return prefixes,
    };

    for relative_path in BOTTLES_PATHS {
        let bottles_path = PathBuf::from(&home).join(relative_path);
        if !bottles_path.exists() {
            continue;
        }

        let Ok(entries) = fs::read_dir(&bottles_path) else {
            continue;
        };

        for entry in entries.flatten() {
            let bottle_path = entry.path();
            // Verify it's a valid Wine prefix
            if bottle_path.is_dir() && bottle_path.join("drive_c").exists() {
                prefixes.push(bottle_path);
            }
        }
    }

    prefixes
}
