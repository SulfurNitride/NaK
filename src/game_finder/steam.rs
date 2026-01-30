//! Steam game detection
//!
//! Detects games installed via Steam by parsing appmanifest_*.acf files.
//! Supports native, Flatpak, and Snap Steam installations.

use std::fs;
use std::path::{Path, PathBuf};

use super::known_games::{find_by_steam_id, KnownGame};
use super::vdf::{parse_library_folders, AppManifest};
use super::{Game, Launcher};
use crate::logging::log_info;

/// All possible Steam installation paths to check
const STEAM_PATHS: &[&str] = &[
    ".local/share/Steam",
    ".steam/debian-installation",
    ".steam/steam",
    ".var/app/com.valvesoftware.Steam/data/Steam",
    ".var/app/com.valvesoftware.Steam/.local/share/Steam",
    "snap/steam/common/.local/share/Steam",
];

/// Detect all Steam games across all installations
pub fn detect_steam_games() -> Vec<Game> {
    let mut games = Vec::new();
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return games,
    };

    // Find all Steam installations
    for steam_info in find_steam_installations(&home) {
        let libraries = get_library_folders(&steam_info.path);

        for library_path in libraries {
            let steamapps = library_path.join("steamapps");
            if !steamapps.exists() {
                continue;
            }

            // Scan for appmanifest_*.acf files
            let Ok(entries) = fs::read_dir(&steamapps) else {
                continue;
            };

            for entry in entries.flatten() {
                let path = entry.path();
                let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
                    continue;
                };

                if name.starts_with("appmanifest_") && name.ends_with(".acf") {
                    if let Some(game) = parse_appmanifest(&path, &steamapps, &steam_info) {
                        games.push(game);
                    }
                }
            }
        }
    }

    log_info(&format!("Steam: Found {} installed games", games.len()));
    games
}

/// Information about a Steam installation
struct SteamInstallation {
    path: PathBuf,
    is_flatpak: bool,
    is_snap: bool,
}

/// Find all Steam installations on the system
fn find_steam_installations(home: &str) -> Vec<SteamInstallation> {
    let mut installations = Vec::new();

    for relative_path in STEAM_PATHS {
        let full_path = PathBuf::from(home).join(relative_path);

        // Check if this is a valid Steam installation
        if full_path.join("steamapps").exists() || full_path.join("steam.pid").exists() {
            let is_flatpak = relative_path.contains(".var/app/com.valvesoftware.Steam");
            let is_snap = relative_path.contains("snap/steam");

            // Avoid duplicates (symlinks can cause the same installation to appear twice)
            let canonical = full_path.canonicalize().unwrap_or(full_path.clone());
            if !installations.iter().any(|i: &SteamInstallation| {
                i.path.canonicalize().unwrap_or(i.path.clone()) == canonical
            }) {
                log_info(&format!(
                    "Found Steam installation: {} (flatpak={}, snap={})",
                    full_path.display(),
                    is_flatpak,
                    is_snap
                ));
                installations.push(SteamInstallation {
                    path: full_path,
                    is_flatpak,
                    is_snap,
                });
            }
        }
    }

    installations
}

/// Get all library folders for a Steam installation
fn get_library_folders(steam_path: &Path) -> Vec<PathBuf> {
    let mut folders = Vec::new();

    // The Steam installation directory itself is always a library
    folders.push(steam_path.to_path_buf());

    // Parse libraryfolders.vdf for additional libraries
    let vdf_path = steam_path.join("steamapps/libraryfolders.vdf");
    if let Ok(content) = fs::read_to_string(&vdf_path) {
        for path_str in parse_library_folders(&content) {
            let path = PathBuf::from(&path_str);
            if path.exists() && !folders.contains(&path) {
                folders.push(path);
            }
        }
    }

    // Also check the older config/libraryfolders.vdf location
    let old_vdf_path = steam_path.join("config/libraryfolders.vdf");
    if old_vdf_path != vdf_path {
        if let Ok(content) = fs::read_to_string(&old_vdf_path) {
            for path_str in parse_library_folders(&content) {
                let path = PathBuf::from(&path_str);
                if path.exists() && !folders.contains(&path) {
                    folders.push(path);
                }
            }
        }
    }

    folders
}

/// Parse an appmanifest_*.acf file and create a Game struct
fn parse_appmanifest(
    manifest_path: &Path,
    steamapps_path: &Path,
    steam_info: &SteamInstallation,
) -> Option<Game> {
    let content = fs::read_to_string(manifest_path).ok()?;
    let manifest = AppManifest::from_vdf(&content)?;

    // Only consider fully installed games
    if !manifest.is_installed() {
        return None;
    }

    // Build the install path
    let install_path = steamapps_path.join("common").join(&manifest.install_dir);
    if !install_path.exists() {
        return None;
    }

    // Build the prefix path
    let prefix_path = steamapps_path
        .join("compatdata")
        .join(&manifest.app_id)
        .join("pfx");

    let prefix_path = if prefix_path.exists() {
        Some(prefix_path)
    } else {
        None
    };

    // Look up known game info
    let known_game = find_by_steam_id(&manifest.app_id);

    Some(Game {
        name: manifest.name,
        app_id: manifest.app_id,
        install_path,
        prefix_path,
        launcher: Launcher::Steam {
            is_flatpak: steam_info.is_flatpak,
            is_snap: steam_info.is_snap,
        },
        my_games_folder: known_game.and_then(|g| g.my_games_folder.map(String::from)),
        appdata_local_folder: known_game.and_then(|g| g.appdata_local_folder.map(String::from)),
        appdata_roaming_folder: known_game.and_then(|g| g.appdata_roaming_folder.map(String::from)),
        registry_path: known_game.map(|g| g.registry_path.to_string()),
        registry_value: known_game.map(|g| g.registry_value.to_string()),
    })
}

/// Find the installation path for a specific Steam game by App ID
pub fn find_game_install_path(app_id: &str) -> Option<PathBuf> {
    let home = std::env::var("HOME").ok()?;

    for steam_info in find_steam_installations(&home) {
        let libraries = get_library_folders(&steam_info.path);

        for library_path in libraries {
            let manifest_path = library_path
                .join("steamapps")
                .join(format!("appmanifest_{}.acf", app_id));

            if manifest_path.exists() {
                let content = fs::read_to_string(&manifest_path).ok()?;
                let manifest = AppManifest::from_vdf(&content)?;

                if manifest.is_installed() {
                    let install_path = library_path
                        .join("steamapps/common")
                        .join(&manifest.install_dir);

                    if install_path.exists() {
                        return Some(install_path);
                    }
                }
            }
        }
    }

    None
}

/// Find the Wine prefix for a specific Steam game by App ID
pub fn find_game_prefix_path(app_id: &str) -> Option<PathBuf> {
    let home = std::env::var("HOME").ok()?;

    for steam_info in find_steam_installations(&home) {
        let libraries = get_library_folders(&steam_info.path);

        for library_path in libraries {
            let prefix_path = library_path
                .join("steamapps/compatdata")
                .join(app_id)
                .join("pfx");

            if prefix_path.exists() {
                return Some(prefix_path);
            }
        }
    }

    None
}

/// Get the known game configuration for a Steam App ID
pub fn get_known_game(app_id: &str) -> Option<&'static KnownGame> {
    find_by_steam_id(app_id)
}
