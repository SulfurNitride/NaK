use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

fn get_home() -> String {
    std::env::var("HOME").unwrap_or_default()
}

/// Normalize a path for compatibility with pressure-vessel/Steam container.
///
/// On Fedora Atomic/Bazzite/Silverblue, $HOME is `/var/home/user` but `/home`
/// is a symlink to `/var/home`. Pressure-vessel exposes `/home` but may not
/// properly handle paths that explicitly use `/var/home/`. This function
/// converts such paths to use `/home/` instead for maximum compatibility.
pub fn normalize_path_for_steam(path: &str) -> String {
    // Convert /var/home/user/... to /home/user/...
    if let Some(stripped) = path.strip_prefix("/var/home/") {
        format!("/home/{}", stripped)
    } else {
        path.to_string()
    }
}

fn default_data_path() -> String {
    format!("{}/NaK", get_home())
}

// ============================================================================
// Main App Config - stored in ~/.config/nak/config.json
// ============================================================================

#[derive(Serialize, Deserialize, Clone)]
pub struct AppConfig {
    pub selected_proton: Option<String>,
    /// Whether the first-run setup has been completed
    #[serde(default)]
    pub first_run_completed: bool,
    /// Path to NaK data folder (legacy ~/NaK - used for migration detection)
    #[serde(default = "default_data_path")]
    pub data_path: String,
    /// Whether the Steam-native migration popup has been shown
    /// (shown once when user has legacy NaK prefixes)
    #[serde(default)]
    pub steam_migration_shown: bool,
    /// Custom cache location (for downloads, tmp files during install)
    /// If empty/not set, uses ~/.cache/nak/
    #[serde(default)]
    pub cache_location: String,
    /// Selected Steam account ID (Steam3 format, e.g., "910757758")
    /// If empty/not set, uses the most recently active account
    #[serde(default)]
    pub selected_steam_account: String,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            selected_proton: None,
            first_run_completed: false,
            data_path: default_data_path(),
            steam_migration_shown: false,
            cache_location: String::new(),
            selected_steam_account: String::new(),
        }
    }
}

impl AppConfig {
    /// Config file path: ~/.config/nak/config.json
    fn get_config_path() -> PathBuf {
        PathBuf::from(format!("{}/.config/nak/config.json", get_home()))
    }

    /// Legacy config path for migration: ~/NaK/config.json
    fn get_legacy_path() -> PathBuf {
        PathBuf::from(format!("{}/NaK/config.json", get_home()))
    }

    pub fn load() -> Self {
        let config_path = Self::get_config_path();
        let legacy_path = Self::get_legacy_path();

        // Try new location first
        if config_path.exists() {
            if let Ok(content) = fs::read_to_string(&config_path) {
                if let Ok(config) = serde_json::from_str(&content) {
                    return config;
                }
            }
        }

        // Try legacy location and migrate if found
        if legacy_path.exists() {
            if let Ok(content) = fs::read_to_string(&legacy_path) {
                if let Ok(mut config) = serde_json::from_str::<AppConfig>(&content) {
                    // Ensure data_path is set (old configs won't have it)
                    if config.data_path.is_empty() {
                        config.data_path = default_data_path();
                    }
                    // Save to new location
                    config.save();
                    // Remove old config
                    let _ = fs::remove_file(&legacy_path);
                    return config;
                }
            }
        }

        Self::default()
    }

    pub fn save(&self) {
        let path = Self::get_config_path();
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(json) = serde_json::to_string_pretty(self) {
            let _ = fs::write(path, json);
        }
    }

    /// Get the NaK data directory path (legacy ~/NaK - used for migration detection)
    pub fn get_data_path(&self) -> PathBuf {
        PathBuf::from(&self.data_path)
    }

    /// Get the NaK config directory (~/.config/nak/)
    pub fn get_config_dir() -> PathBuf {
        PathBuf::from(format!("{}/.config/nak", get_home()))
    }

    /// Get the default cache directory (~/.cache/nak/)
    pub fn get_default_cache_dir() -> PathBuf {
        PathBuf::from(format!("{}/.cache/nak", get_home()))
    }

    /// Get the cache directory (custom location or default ~/.cache/nak/)
    pub fn get_cache_dir(&self) -> PathBuf {
        if self.cache_location.is_empty() {
            Self::get_default_cache_dir()
        } else {
            PathBuf::from(&self.cache_location)
        }
    }

    /// Get path to tmp directory (~/.cache/nak/tmp/)
    pub fn get_tmp_path() -> PathBuf {
        let config = Self::load();
        config.get_cache_dir().join("tmp")
    }

    /// Get path to Prefixes directory (legacy - for migration detection only)
    pub fn get_prefixes_path(&self) -> PathBuf {
        self.get_data_path().join("Prefixes")
    }
}

// ============================================================================
// Managed Prefixes - tracks NaK-created Steam prefixes for cleanup
// Stored in ~/.config/nak/managed_prefixes.json
// ============================================================================

/// Type of mod manager
#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq)]
pub enum ManagerType {
    MO2,
    Plugin,
    Vortex,
}

impl std::fmt::Display for ManagerType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ManagerType::MO2 => write!(f, "MO2"),
            ManagerType::Plugin => write!(f, "Plugin"),
            ManagerType::Vortex => write!(f, "Vortex"),
        }
    }
}

impl ManagerType {
    /// Get the display name for this manager type
    pub fn display_name(&self) -> &'static str {
        match self {
            ManagerType::MO2 => "MO2",
            ManagerType::Plugin => "Plugin",
            ManagerType::Vortex => "Vortex",
        }
    }
}

/// A single managed prefix entry
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ManagedPrefix {
    /// Steam AppID for the non-Steam game shortcut
    pub app_id: u32,
    /// User-chosen instance name (e.g., "MO2 - Skyrim")
    pub name: String,
    /// Path to the compatdata prefix folder
    pub prefix_path: String,
    /// Path to the mod manager installation
    pub install_path: String,
    /// Type of mod manager (MO2 or Vortex)
    pub manager_type: ManagerType,
    /// Steam library path where this prefix lives
    pub library_path: String,
    /// When this prefix was created
    pub created: DateTime<Utc>,
    /// Proton config_name used for this instance (for script regeneration)
    /// Optional for backward compatibility with existing installs
    #[serde(default)]
    pub proton_config_name: Option<String>,
}

/// Container for all managed prefixes
#[derive(Serialize, Deserialize, Clone, Debug, Default)]
pub struct ManagedPrefixes {
    pub prefixes: Vec<ManagedPrefix>,
}

impl ManagedPrefixes {
    /// Get the path to managed_prefixes.json
    fn get_path() -> PathBuf {
        AppConfig::get_config_dir().join("managed_prefixes.json")
    }

    /// Load managed prefixes from disk
    pub fn load() -> Self {
        let path = Self::get_path();
        if path.exists() {
            if let Ok(content) = fs::read_to_string(&path) {
                if let Ok(prefixes) = serde_json::from_str(&content) {
                    return prefixes;
                }
            }
        }
        Self::default()
    }

    /// Save managed prefixes to disk
    pub fn save(&self) {
        let path = Self::get_path();
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(json) = serde_json::to_string_pretty(self) {
            let _ = fs::write(path, json);
        }
    }

    /// Register a new managed prefix
    pub fn register(
        app_id: u32,
        name: &str,
        prefix_path: &str,
        install_path: &str,
        manager_type: ManagerType,
        library_path: &str,
        proton_config_name: Option<&str>,
    ) {
        let mut prefixes = Self::load();

        // Remove any existing entry with the same app_id (shouldn't happen, but just in case)
        prefixes.prefixes.retain(|p| p.app_id != app_id);

        prefixes.prefixes.push(ManagedPrefix {
            app_id,
            name: name.to_string(),
            prefix_path: prefix_path.to_string(),
            install_path: install_path.to_string(),
            manager_type,
            library_path: library_path.to_string(),
            created: Utc::now(),
            proton_config_name: proton_config_name.map(|s| s.to_string()),
        });

        prefixes.save();
    }

    /// Update the Proton config name for an existing prefix
    pub fn update_proton(app_id: u32, proton_config_name: &str) {
        let mut prefixes = Self::load();
        if let Some(prefix) = prefixes.prefixes.iter_mut().find(|p| p.app_id == app_id) {
            prefix.proton_config_name = Some(proton_config_name.to_string());
        }
        prefixes.save();
    }

    /// Remove a managed prefix entry (does NOT delete files)
    pub fn unregister(app_id: u32) {
        let mut prefixes = Self::load();
        prefixes.prefixes.retain(|p| p.app_id != app_id);
        prefixes.save();
    }

    /// Get a prefix by app_id
    pub fn get_by_app_id(&self, app_id: u32) -> Option<&ManagedPrefix> {
        self.prefixes.iter().find(|p| p.app_id == app_id)
    }

    /// Get the size of a prefix directory in bytes
    #[allow(dead_code)]
    pub fn get_prefix_size(prefix_path: &str) -> u64 {
        let path = PathBuf::from(prefix_path);
        if !path.exists() {
            return 0;
        }

        fn dir_size(path: &PathBuf) -> u64 {
            let mut size = 0;
            if let Ok(entries) = fs::read_dir(path) {
                for entry in entries.flatten() {
                    let entry_path = entry.path();
                    if entry_path.is_dir() {
                        size += dir_size(&entry_path);
                    } else if let Ok(metadata) = entry.metadata() {
                        size += metadata.len();
                    }
                }
            }
            size
        }

        dir_size(&path)
    }

    /// Format bytes as human-readable size
    #[allow(dead_code)]
    pub fn format_size(bytes: u64) -> String {
        const KB: u64 = 1024;
        const MB: u64 = KB * 1024;
        const GB: u64 = MB * 1024;

        if bytes >= GB {
            format!("{:.1} GB", bytes as f64 / GB as f64)
        } else if bytes >= MB {
            format!("{:.1} MB", bytes as f64 / MB as f64)
        } else if bytes >= KB {
            format!("{:.1} KB", bytes as f64 / KB as f64)
        } else {
            format!("{} B", bytes)
        }
    }

    /// Delete a prefix directory and unregister it
    ///
    /// Deletes the entire appid folder (steamapps/compatdata/{app_id}/)
    /// to avoid leaving empty folders that bloat the compatdata directory.
    pub fn delete_prefix(app_id: u32) -> Result<(), String> {
        let prefixes = Self::load();
        if let Some(prefix) = prefixes.get_by_app_id(app_id) {
            let pfx_path = PathBuf::from(&prefix.prefix_path);

            // The appid folder is the parent of the pfx folder
            // Structure: steamapps/compatdata/{app_id}/pfx/
            // We want to delete the entire {app_id} folder, not just pfx
            if let Some(appid_folder) = pfx_path.parent() {
                if appid_folder.exists() {
                    fs::remove_dir_all(appid_folder)
                        .map_err(|e| format!("Failed to delete prefix: {}", e))?;
                }
            } else {
                // Fallback: if no parent, just delete the pfx folder
                if pfx_path.exists() {
                    fs::remove_dir_all(&pfx_path)
                        .map_err(|e| format!("Failed to delete prefix: {}", e))?;
                }
            }

            Self::unregister(app_id);
            Ok(())
        } else {
            Err("Prefix not found".to_string())
        }
    }
}
