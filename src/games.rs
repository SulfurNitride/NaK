//! Game Finder - Detects Steam and Heroic games and their Wine prefixes
//!
//! This module scans for installed games and allows applying fixes
//! (dependencies and registry settings) to their Wine prefixes.

use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use crate::config::AppConfig;
use crate::logging::{log_info, log_warning};

// ============================================================================
// Types
// ============================================================================

#[derive(Clone, Debug)]
pub enum GameSource {
    Steam { app_id: String },
    Heroic { store: String }, // "gog", "legendary" (Epic), "nile" (Amazon)
}

#[derive(Clone, Debug)]
pub struct DetectedGame {
    pub name: String,
    pub source: GameSource,
    pub install_path: PathBuf,
    pub prefix_path: Option<PathBuf>,
    pub has_prefix: bool,
}

// ============================================================================
// Game Finder
// ============================================================================

pub struct GameFinder {
    steam_path: Option<PathBuf>,
    heroic_config_path: Option<PathBuf>,
}

impl Default for GameFinder {
    fn default() -> Self {
        Self::new()
    }
}

impl GameFinder {
    #[must_use]
    pub fn new() -> Self {
        let home = std::env::var("HOME").unwrap_or_default();

        // Find Steam path
        let steam_paths = [
            format!("{}/.steam/steam", home),
            format!("{}/.local/share/Steam", home),
            format!("{}/.var/app/com.valvesoftware.Steam/.steam/steam", home),
            format!("{}/snap/steam/common/.steam/steam", home),
        ];

        let steam_path = steam_paths
            .iter()
            .map(PathBuf::from)
            .find(|p| p.exists());

        // Find Heroic config path
        let heroic_paths = [
            format!("{}/.config/heroic", home),
            format!("{}/.var/app/com.heroicgameslauncher.hgl/config/heroic", home),
        ];

        let heroic_config_path = heroic_paths
            .iter()
            .map(PathBuf::from)
            .find(|p| p.exists());

        Self {
            steam_path,
            heroic_config_path,
        }
    }

    /// Find all detectable games from Steam and Heroic
    pub fn find_all_games(&self) -> Vec<DetectedGame> {
        let mut games = Vec::new();
        let mut seen_ids: std::collections::HashSet<String> = std::collections::HashSet::new();

        // Find Steam games
        if let Some(ref steam_path) = self.steam_path {
            for game in self.find_steam_games(steam_path) {
                // Deduplicate by app_id (same game can appear in multiple library folders)
                let id = match &game.source {
                    GameSource::Steam { app_id } => app_id.clone(),
                    GameSource::Heroic { store } => format!("heroic_{}_{}", store, game.name),
                };
                if seen_ids.insert(id) {
                    games.push(game);
                }
            }
        }

        // Find Heroic games
        if let Some(ref heroic_path) = self.heroic_config_path {
            for game in self.find_heroic_games(heroic_path) {
                let id = match &game.source {
                    GameSource::Steam { app_id } => app_id.clone(),
                    GameSource::Heroic { store } => format!("heroic_{}_{}", store, game.name),
                };
                if seen_ids.insert(id) {
                    games.push(game);
                }
            }
        }

        // Sort by name
        games.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));

        games
    }

    /// Find Steam games by scanning steamapps
    fn find_steam_games(&self, steam_path: &Path) -> Vec<DetectedGame> {
        let mut games = Vec::new();

        // Get all library folders
        let library_folders = self.get_steam_library_folders(steam_path);

        for library_path in library_folders {
            let steamapps = library_path.join("steamapps");
            let common = steamapps.join("common");
            let compatdata = steamapps.join("compatdata");

            if !common.exists() {
                continue;
            }

            // Read app manifests to get app IDs and names
            if let Ok(entries) = fs::read_dir(&steamapps) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                        if name.starts_with("appmanifest_") && name.ends_with(".acf") {
                            if let Some(game) = self.parse_steam_manifest(&path, &common, &compatdata) {
                                games.push(game);
                            }
                        }
                    }
                }
            }
        }

        log_info(&format!("Found {} Steam games", games.len()));
        games
    }

    /// Get all Steam library folders from libraryfolders.vdf
    fn get_steam_library_folders(&self, steam_path: &Path) -> Vec<PathBuf> {
        let mut folders = vec![steam_path.to_path_buf()];

        let vdf_path = steam_path.join("steamapps/libraryfolders.vdf");
        if let Ok(content) = fs::read_to_string(&vdf_path) {
            // Simple VDF parsing - look for "path" entries
            for line in content.lines() {
                let trimmed = line.trim();
                if trimmed.starts_with("\"path\"") {
                    // Extract path value: "path"		"/path/to/library"
                    if let Some(path_str) = trimmed.split('"').nth(3) {
                        let path = PathBuf::from(path_str);
                        if path.exists() && !folders.contains(&path) {
                            folders.push(path);
                        }
                    }
                }
            }
        }

        folders
    }

    /// Parse a Steam app manifest file
    fn parse_steam_manifest(
        &self,
        manifest_path: &Path,
        common_path: &Path,
        compatdata_path: &Path,
    ) -> Option<DetectedGame> {
        let content = fs::read_to_string(manifest_path).ok()?;

        let mut app_id = None;
        let mut name = None;
        let mut install_dir = None;

        for line in content.lines() {
            let trimmed = line.trim();

            if trimmed.starts_with("\"appid\"") {
                app_id = trimmed.split('"').nth(3).map(String::from);
            } else if trimmed.starts_with("\"name\"") {
                name = trimmed.split('"').nth(3).map(String::from);
            } else if trimmed.starts_with("\"installdir\"") {
                install_dir = trimmed.split('"').nth(3).map(String::from);
            }
        }

        let app_id = app_id?;
        let name = name?;
        let install_dir = install_dir?;

        // Skip Proton and Steam tools
        let skip_prefixes = ["Proton", "Steam Linux Runtime", "Steamworks"];
        if skip_prefixes.iter().any(|p| name.starts_with(p)) {
            return None;
        }

        let install_path = common_path.join(&install_dir);
        if !install_path.exists() {
            return None;
        }

        // Check for Wine prefix
        let prefix_path = compatdata_path.join(&app_id).join("pfx");
        let has_prefix = prefix_path.exists();

        Some(DetectedGame {
            name,
            source: GameSource::Steam { app_id },
            install_path,
            prefix_path: if has_prefix { Some(prefix_path) } else { None },
            has_prefix,
        })
    }

    /// Find Heroic games (GOG, Epic, Amazon)
    fn find_heroic_games(&self, heroic_path: &Path) -> Vec<DetectedGame> {
        let mut games = Vec::new();

        // Check GOG games
        games.extend(self.find_heroic_gog_games(heroic_path));

        // Check Epic/Legendary games
        games.extend(self.find_heroic_legendary_games(heroic_path));

        log_info(&format!("Found {} Heroic games", games.len()));
        games
    }

    /// Find GOG games from Heroic
    fn find_heroic_gog_games(&self, heroic_path: &Path) -> Vec<DetectedGame> {
        let mut games = Vec::new();
        let gog_installed = heroic_path.join("gog_store/installed.json");

        if let Ok(content) = fs::read_to_string(&gog_installed) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(installed) = json.get("installed").and_then(|v| v.as_array()) {
                    for game in installed {
                        if let Some(game_info) = self.parse_heroic_game(game, heroic_path, "gog") {
                            games.push(game_info);
                        }
                    }
                }
            }
        }

        games
    }

    /// Find Epic/Legendary games from Heroic
    fn find_heroic_legendary_games(&self, heroic_path: &Path) -> Vec<DetectedGame> {
        let mut games = Vec::new();
        let legendary_installed = heroic_path.join("legendaryConfig/legendary/installed.json");

        if let Ok(content) = fs::read_to_string(&legendary_installed) {
            if let Ok(json) = serde_json::from_str::<HashMap<String, serde_json::Value>>(&content) {
                for (_app_name, game) in json {
                    if let Some(game_info) = self.parse_heroic_game(&game, heroic_path, "legendary") {
                        games.push(game_info);
                    }
                }
            }
        }

        games
    }

    /// Parse a Heroic game entry
    fn parse_heroic_game(
        &self,
        game: &serde_json::Value,
        heroic_path: &Path,
        store: &str,
    ) -> Option<DetectedGame> {
        let title = game.get("title")
            .or_else(|| game.get("name"))
            .and_then(|v| v.as_str())?;

        let install_path_str = game.get("install_path")
            .or_else(|| game.get("install_dir"))
            .and_then(|v| v.as_str())?;

        let install_path = PathBuf::from(install_path_str);
        if !install_path.exists() {
            return None;
        }

        // Find Wine prefix - Heroic stores them in various locations
        let app_name = game.get("appName")
            .or_else(|| game.get("app_name"))
            .and_then(|v| v.as_str())
            .unwrap_or(title);

        // Check common prefix locations
        let prefix_locations = [
            heroic_path.join(format!("Prefixes/{}", app_name)),
            heroic_path.join(format!("prefixes/{}", app_name)),
            heroic_path.join(format!("GamesConfig/{}/pfx", app_name)),
        ];

        let prefix_path = prefix_locations.into_iter().find(|p| p.exists());
        let has_prefix = prefix_path.is_some();

        Some(DetectedGame {
            name: title.to_string(),
            source: GameSource::Heroic { store: store.to_string() },
            install_path,
            prefix_path,
            has_prefix,
        })
    }
}

// ============================================================================
// Game Fixer - Apply fixes to game prefixes
// ============================================================================

use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use crate::wine::{DependencyManager, ProtonInfo};
use crate::installers::WINE_SETTINGS_REG;

pub struct GameFixer;

impl GameFixer {
    /// Apply fixes to a game's Wine prefix
    pub fn apply_fixes(
        game: &DetectedGame,
        proton: &ProtonInfo,
        winetricks_path: &Path,
        deps_to_install: &[&str],
        apply_registry: bool,
        log_callback: impl Fn(String) + Send + Sync + 'static,
        cancel_flag: Arc<AtomicBool>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let prefix_path = game.prefix_path.as_ref()
            .ok_or("Game has no Wine prefix")?;

        log_callback(format!("Applying fixes to: {}", game.name));
        log_callback(format!("Prefix: {}", prefix_path.display()));

        // Install dependencies
        if !deps_to_install.is_empty() {
            log_callback("Installing dependencies...".to_string());
            let dep_mgr = DependencyManager::new(winetricks_path.to_path_buf());

            for (i, dep) in deps_to_install.iter().enumerate() {
                if cancel_flag.load(std::sync::atomic::Ordering::Relaxed) {
                    return Err("Cancelled".into());
                }

                log_callback(format!("Installing {}/{}: {}...", i + 1, deps_to_install.len(), dep));

                let log_cb = |msg: String| {
                    // Inner callback - we can't easily forward here without more complexity
                    println!("{}", msg);
                };

                if let Err(e) = dep_mgr.install_dependencies(
                    prefix_path,
                    proton,
                    &[dep],
                    log_cb,
                    cancel_flag.clone(),
                ) {
                    log_callback(format!("Warning: Failed to install {}: {}", dep, e));
                    log_warning(&format!("Failed to install {} for {}: {}", dep, game.name, e));
                }
            }
        }

        // Apply registry settings
        if apply_registry {
            log_callback("Applying registry settings...".to_string());
            Self::apply_registry_fixes(prefix_path, proton, &log_callback)?;
        }

        log_callback(format!("Fixes applied to {}!", game.name));
        Ok(())
    }

    /// Apply Wine registry fixes to a prefix
    fn apply_registry_fixes(
        prefix_path: &Path,
        proton: &ProtonInfo,
        log_callback: &impl Fn(String),
    ) -> Result<(), Box<dyn std::error::Error>> {
        use std::io::Write;

        let config = AppConfig::load();
        let tmp_dir = config.get_data_path().join("tmp");
        fs::create_dir_all(&tmp_dir)?;
        let reg_file = tmp_dir.join("game_fix_settings.reg");

        let mut file = fs::File::create(&reg_file)?;
        file.write_all(WINE_SETTINGS_REG.as_bytes())?;

        // Get wine binary path
        let wine_bin = proton.path.join("files/bin/wine");
        if !wine_bin.exists() {
            log_callback(format!("Warning: Wine binary not found at {:?}", wine_bin));
            return Ok(());
        }

        log_callback("Running wine regedit...".to_string());

        let status = std::process::Command::new(&wine_bin)
            .arg("regedit")
            .arg(&reg_file)
            .env("WINEPREFIX", prefix_path)
            .env(
                "LD_LIBRARY_PATH",
                "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu",
            )
            .env("PROTON_NO_XALIA", "1")
            .status();

        match status {
            Ok(s) if s.success() => {
                log_callback("Registry settings applied successfully".to_string());
            }
            Ok(s) => {
                log_callback(format!("Warning: regedit exited with code {:?}", s.code()));
            }
            Err(e) => {
                log_callback(format!("Warning: Failed to run regedit: {}", e));
            }
        }

        // Cleanup
        let _ = fs::remove_file(&reg_file);

        Ok(())
    }
}
