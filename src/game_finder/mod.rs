//! Game detection module
//!
//! Provides unified game detection across multiple launchers:
//! - Steam (native, Flatpak, Snap)
//! - Heroic (GOG, Epic)
//! - Bottles
//!
//! # Example
//!
//! ```rust,ignore
//! use nak::game_finder::{detect_all_games, Launcher};
//!
//! let result = detect_all_games();
//! for game in &result.games {
//!     println!("Found: {} ({:?})", game.name, game.launcher);
//! }
//! ```

// Allow unused items - this is a public API module and not all items may be used yet
#![allow(dead_code)]
#![allow(unused_imports)]

mod bottles;
mod heroic;
pub mod known_games;
mod registry;
mod steam;
mod vdf;

use std::path::PathBuf;

pub use bottles::detect_bottles_games;
pub use heroic::detect_heroic_games;
pub use known_games::{find_by_gog_id, find_by_name, find_by_steam_id, KnownGame, KNOWN_GAMES};
pub use registry::{read_registry_value, wine_path_to_linux};
pub use steam::{detect_steam_games, find_game_install_path, find_game_prefix_path, get_known_game};

// ============================================================================
// Core Types
// ============================================================================

/// The launcher/store a game was installed from
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Launcher {
    /// Steam (with Flatpak/Snap variant info)
    Steam { is_flatpak: bool, is_snap: bool },
    /// Heroic Games Launcher
    Heroic { store: HeroicStore },
    /// Bottles
    Bottles,
}

impl Launcher {
    /// Get a display name for the launcher
    pub fn display_name(&self) -> &'static str {
        match self {
            Launcher::Steam { is_flatpak: true, .. } => "Steam (Flatpak)",
            Launcher::Steam { is_snap: true, .. } => "Steam (Snap)",
            Launcher::Steam { .. } => "Steam",
            Launcher::Heroic { store: HeroicStore::GOG } => "Heroic (GOG)",
            Launcher::Heroic { store: HeroicStore::Epic } => "Heroic (Epic)",
            Launcher::Bottles => "Bottles",
        }
    }
}

/// Store type for Heroic games
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HeroicStore {
    GOG,
    Epic,
}

/// A detected game installation
#[derive(Debug, Clone)]
pub struct Game {
    /// Game display name
    pub name: String,
    /// App ID (Steam App ID, GOG ID, etc.)
    pub app_id: String,
    /// Path to the game installation directory
    pub install_path: PathBuf,
    /// Path to the Wine prefix (if applicable)
    pub prefix_path: Option<PathBuf>,
    /// The launcher this game was installed from
    pub launcher: Launcher,
    /// Folder name in Documents/My Games (if applicable)
    pub my_games_folder: Option<String>,
    /// Folder name in AppData/Local (if applicable)
    pub appdata_local_folder: Option<String>,
    /// Folder name in AppData/Roaming (if applicable)
    pub appdata_roaming_folder: Option<String>,
    /// Registry path for game detection (under HKLM\Software\)
    pub registry_path: Option<String>,
    /// Registry value name for install path
    pub registry_value: Option<String>,
}

impl Game {
    /// Check if this game has a Wine prefix
    pub fn has_prefix(&self) -> bool {
        self.prefix_path.is_some()
    }

    /// Get the user folder path within the prefix
    pub fn get_prefix_user_path(&self) -> Option<PathBuf> {
        let prefix = self.prefix_path.as_ref()?;
        let users_dir = prefix.join("drive_c/users");

        // Find the username (usually "steamuser" for Proton)
        if let Ok(entries) = std::fs::read_dir(&users_dir) {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().to_string();
                if name != "Public" && name != "root" {
                    return Some(users_dir.join(name));
                }
            }
        }

        // Fallback to steamuser
        Some(users_dir.join("steamuser"))
    }

    /// Get the Documents folder path within the prefix
    pub fn get_prefix_documents_path(&self) -> Option<PathBuf> {
        self.get_prefix_user_path().map(|p| p.join("Documents"))
    }

    /// Get the My Games folder path within the prefix (if applicable)
    pub fn get_prefix_my_games_path(&self) -> Option<PathBuf> {
        let docs = self.get_prefix_documents_path()?;
        let folder = self.my_games_folder.as_ref()?;
        Some(docs.join("My Games").join(folder))
    }

    /// Get the AppData/Local folder path within the prefix (if applicable)
    pub fn get_prefix_appdata_local_path(&self) -> Option<PathBuf> {
        let user = self.get_prefix_user_path()?;
        let folder = self.appdata_local_folder.as_ref()?;
        Some(user.join("AppData/Local").join(folder))
    }

    /// Get the AppData/Roaming folder path within the prefix (if applicable)
    pub fn get_prefix_appdata_roaming_path(&self) -> Option<PathBuf> {
        let user = self.get_prefix_user_path()?;
        let folder = self.appdata_roaming_folder.as_ref()?;
        Some(user.join("AppData/Roaming").join(folder))
    }
}

// ============================================================================
// Scan Results
// ============================================================================

/// Result of scanning for games
#[derive(Debug, Default)]
pub struct GameScanResult {
    /// All detected games
    pub games: Vec<Game>,
    /// Number of Steam games found
    pub steam_count: usize,
    /// Number of Heroic games found
    pub heroic_count: usize,
    /// Number of Bottles games found
    pub bottles_count: usize,
}

impl GameScanResult {
    /// Get games that have Wine prefixes with save data folders
    pub fn games_with_prefixes(&self) -> impl Iterator<Item = &Game> {
        self.games.iter().filter(|g| g.has_prefix())
    }

    /// Get games by launcher type
    pub fn games_by_launcher(&self, launcher_type: &str) -> Vec<&Game> {
        self.games
            .iter()
            .filter(|g| {
                matches!(
                    (&g.launcher, launcher_type),
                    (Launcher::Steam { .. }, "steam")
                        | (Launcher::Heroic { .. }, "heroic")
                        | (Launcher::Bottles, "bottles")
                )
            })
            .collect()
    }

    /// Find a game by name (case-insensitive)
    pub fn find_by_name(&self, name: &str) -> Option<&Game> {
        let name_lower = name.to_lowercase();
        self.games
            .iter()
            .find(|g| g.name.to_lowercase() == name_lower)
    }

    /// Find a game by app ID
    pub fn find_by_app_id(&self, app_id: &str) -> Option<&Game> {
        self.games.iter().find(|g| g.app_id == app_id)
    }
}

// ============================================================================
// Public API
// ============================================================================

/// Detect all installed games from all supported launchers
///
/// This function scans:
/// - Steam (native, Flatpak, Snap) via appmanifest_*.acf parsing
/// - Heroic (GOG, Epic) via installed.json
/// - Bottles via registry scanning
///
/// Returns a `GameScanResult` containing all found games.
pub fn detect_all_games() -> GameScanResult {
    let mut result = GameScanResult::default();

    // Detect Steam games
    let steam_games = detect_steam_games();
    result.steam_count = steam_games.len();
    result.games.extend(steam_games);

    // Detect Heroic games
    let heroic_games = detect_heroic_games();
    result.heroic_count = heroic_games.len();
    result.games.extend(heroic_games);

    // Detect Bottles games
    let bottles_games = detect_bottles_games();
    result.bottles_count = bottles_games.len();
    result.games.extend(bottles_games);

    result
}

/// Detect only Steam games
pub fn detect_steam_only() -> GameScanResult {
    let steam_games = detect_steam_games();
    GameScanResult {
        steam_count: steam_games.len(),
        games: steam_games,
        ..Default::default()
    }
}
