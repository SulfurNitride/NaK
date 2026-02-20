//! Heroic Games Launcher detection
//!
//! Detects games installed via Heroic (GOG and Epic Games).
//! Parses installed.json and GamesConfig/*.json for game and prefix info.

use std::fs;
use std::path::{Path, PathBuf};

use serde::Deserialize;

use super::known_games::{find_by_epic_id, find_by_gog_id, find_by_title};
use super::{Game, HeroicStore, Launcher};
use crate::logging::{log_info, log_warning};

/// Possible Heroic configuration paths
const HEROIC_PATHS: &[&str] = &[
    ".config/heroic",                                          // Native
    ".var/app/com.heroicgameslauncher.hgl/config/heroic",      // Flatpak
];

/// Detect all Heroic games
pub fn detect_heroic_games() -> Vec<Game> {
    let mut games = Vec::new();
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return games,
    };

    for relative_path in HEROIC_PATHS {
        let heroic_path = PathBuf::from(&home).join(relative_path);
        if !heroic_path.exists() {
            continue;
        }

        log_info(&format!("Found Heroic installation: {}", heroic_path.display()));

        // Detect GOG games
        let gog_games = detect_gog_games(&heroic_path);
        games.extend(gog_games);

        // Detect Epic games
        let epic_games = detect_epic_games(&heroic_path);
        games.extend(epic_games);
    }

    log_info(&format!("Heroic: Found {} installed games", games.len()));
    games
}

// ============================================================================
// GOG Detection
// ============================================================================

/// GOG installed game entry from installed.json
#[derive(Debug, Deserialize)]
struct GogInstalledGame {
    #[serde(rename = "appName")]
    app_name: String,
    title: Option<String>,
    #[serde(rename = "install_path")]
    install_path: Option<String>,
    platform: Option<String>,
}

/// Wrapper for Heroic's GOG installed.json format: {"installed": [...]}
#[derive(Debug, Deserialize)]
struct GogInstalledWrapper {
    installed: Vec<GogInstalledGame>,
}

/// Detect GOG games from Heroic
fn detect_gog_games(heroic_path: &Path) -> Vec<Game> {
    let mut games = Vec::new();
    let installed_json = heroic_path.join("gog_store/installed.json");

    let Ok(content) = fs::read_to_string(&installed_json) else {
        return games;
    };

    // Heroic wraps GOG games in {"installed": [...]}, but also handle bare arrays
    let installed: Vec<GogInstalledGame> =
        if let Ok(wrapper) = serde_json::from_str::<GogInstalledWrapper>(&content) {
            wrapper.installed
        } else if let Ok(list) = serde_json::from_str::<Vec<GogInstalledGame>>(&content) {
            list
        } else {
            log_warning("Failed to parse Heroic GOG installed.json");
            return games;
        };

    for gog_game in installed {
        // Skip non-Windows games (we only care about Wine prefixes)
        if gog_game.platform.as_deref() != Some("windows") {
            continue;
        }

        let Some(install_path_str) = gog_game.install_path else {
            continue;
        };

        let install_path = PathBuf::from(&install_path_str);
        if !install_path.exists() {
            continue;
        }

        // Get the game config for Wine prefix info
        let prefix_path = get_heroic_game_prefix(heroic_path, &gog_game.app_name);

        // Look up known game info
        let known_game = find_by_gog_id(&gog_game.app_name);

        let name = gog_game
            .title
            .unwrap_or_else(|| gog_game.app_name.clone());

        games.push(Game {
            name,
            app_id: gog_game.app_name,
            install_path,
            prefix_path,
            launcher: Launcher::Heroic {
                store: HeroicStore::GOG,
            },
            my_games_folder: known_game.and_then(|g| g.my_games_folder.map(String::from)),
            appdata_local_folder: known_game.and_then(|g| g.appdata_local_folder.map(String::from)),
            appdata_roaming_folder: known_game.and_then(|g| g.appdata_roaming_folder.map(String::from)),
            registry_path: known_game.map(|g| g.registry_path.to_string()),
            registry_value: known_game.map(|g| g.registry_value.to_string()),
        });
    }

    games
}

// ============================================================================
// Epic Detection
// ============================================================================

/// Epic installed game entry from installed.json
#[derive(Debug, Deserialize)]
struct EpicInstalledGame {
    #[serde(rename = "app_name")]
    app_name: String,
    title: Option<String>,
    install_path: Option<String>,
    platform: Option<String>,
    is_installed: Option<bool>,
}

/// Detect Epic games from Heroic
fn detect_epic_games(heroic_path: &Path) -> Vec<Game> {
    let mut games = Vec::new();
    let installed_json = heroic_path.join("store_cache/legendary_library.json");

    // Also try the older location
    let installed_json = if installed_json.exists() {
        installed_json
    } else {
        heroic_path.join("legendaryConfig/legendary/installed.json")
    };

    let Ok(content) = fs::read_to_string(&installed_json) else {
        return games;
    };

    // The Epic library format can vary - try parsing as an object with game keys
    if let Ok(library) = serde_json::from_str::<serde_json::Value>(&content) {
        if let Some(obj) = library.as_object() {
            for (app_name, game_data) in obj {
                let Some(game_obj) = game_data.as_object() else {
                    continue;
                };

                // Check if installed
                let is_installed = game_obj
                    .get("is_installed")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                if !is_installed {
                    continue;
                }

                // Get platform
                let platform = game_obj
                    .get("platform")
                    .and_then(|v| v.as_str());
                if platform != Some("Windows") && platform != Some("windows") {
                    continue;
                }

                // Get install path
                let Some(install_path_str) = game_obj
                    .get("install_path")
                    .and_then(|v| v.as_str())
                else {
                    continue;
                };

                let install_path = PathBuf::from(install_path_str);
                if !install_path.exists() {
                    continue;
                }

                // Get title
                let title = game_obj
                    .get("title")
                    .and_then(|v| v.as_str())
                    .unwrap_or(app_name);

                // Look up known game info: try Epic AppName first, then title match
                let known_game = find_by_epic_id(app_name)
                    .or_else(|| find_by_title(title));

                let name = title.to_string();

                // Get Wine prefix
                let prefix_path = get_heroic_game_prefix(heroic_path, app_name);

                games.push(Game {
                    name,
                    app_id: app_name.clone(),
                    install_path,
                    prefix_path,
                    launcher: Launcher::Heroic {
                        store: HeroicStore::Epic,
                    },
                    my_games_folder: known_game.and_then(|g| g.my_games_folder.map(String::from)),
                    appdata_local_folder: known_game.and_then(|g| g.appdata_local_folder.map(String::from)),
                    appdata_roaming_folder: known_game.and_then(|g| g.appdata_roaming_folder.map(String::from)),
                    registry_path: known_game.map(|g| g.registry_path.to_string()),
                    registry_value: known_game.map(|g| g.registry_value.to_string()),
                });
            }
        }
    }

    games
}

// ============================================================================
// Shared Utilities
// ============================================================================

/// Game config entry for Wine settings
#[derive(Debug, Deserialize)]
struct HeroicGameConfig {
    #[serde(rename = "winePrefix")]
    wine_prefix: Option<String>,
    #[serde(rename = "wineVersion")]
    wine_version: Option<WineVersion>,
}

#[derive(Debug, Deserialize)]
struct WineVersion {
    bin: Option<String>,
    name: Option<String>,
    #[serde(rename = "type")]
    wine_type: Option<String>,
}

/// Get the Wine prefix for a Heroic game from its config file
fn get_heroic_game_prefix(heroic_path: &Path, app_name: &str) -> Option<PathBuf> {
    let config_path = heroic_path.join(format!("GamesConfig/{}.json", app_name));

    let content = fs::read_to_string(&config_path).ok()?;

    // The config can be either a direct object or wrapped in the app_name key
    let config: serde_json::Value = serde_json::from_str(&content).ok()?;

    // Try to get winePrefix from the object or from a nested object
    let wine_prefix = config
        .get("winePrefix")
        .or_else(|| config.get(app_name).and_then(|v| v.get("winePrefix")))
        .and_then(|v| v.as_str())?;

    let prefix_path = PathBuf::from(wine_prefix);
    if prefix_path.exists() {
        Some(prefix_path)
    } else {
        None
    }
}
