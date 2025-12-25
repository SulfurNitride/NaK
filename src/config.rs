use serde::{Deserialize, Serialize};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

/// Move a directory, handling cross-device moves by copying + deleting
fn move_dir_all(src: &Path, dst: &Path) -> io::Result<()> {
    // Try rename first (fast, same filesystem)
    match fs::rename(src, dst) {
        Ok(()) => return Ok(()),
        Err(e) if e.raw_os_error() == Some(18) => {
            // EXDEV (18) = cross-device link, need to copy + delete
        }
        Err(e) => return Err(e),
    }

    // Cross-device move: recursive copy then delete
    copy_dir_all(src, dst)?;
    fs::remove_dir_all(src)?;
    Ok(())
}

/// Recursively copy a directory
fn copy_dir_all(src: &Path, dst: &Path) -> io::Result<()> {
    fs::create_dir_all(dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());

        if src_path.is_dir() {
            copy_dir_all(&src_path, &dst_path)?;
        } else if src_path.is_symlink() {
            // Preserve symlinks
            let target = fs::read_link(&src_path)?;
            let _ = fs::remove_file(&dst_path); // Remove if exists
            std::os::unix::fs::symlink(target, &dst_path)?;
        } else {
            fs::copy(&src_path, &dst_path)?;
        }
    }
    Ok(())
}

fn get_home() -> String {
    std::env::var("HOME").unwrap_or_default()
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
    pub active_nxm_prefix: Option<String>,
    /// Whether to use Steam Linux Runtime (pressure-vessel) for launching
    #[serde(default = "default_true")]
    pub use_steam_runtime: bool,
    /// Whether the first-run setup has been completed
    #[serde(default)]
    pub first_run_completed: bool,
    /// Path to NaK data folder (Prefixes, ProtonGE, cache, etc.)
    /// Defaults to ~/NaK
    #[serde(default = "default_data_path")]
    pub data_path: String,
}

fn default_true() -> bool {
    true
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            selected_proton: None,
            active_nxm_prefix: None,
            use_steam_runtime: true,
            first_run_completed: false,
            data_path: default_data_path(),
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

    /// Get the NaK data directory path
    pub fn get_data_path(&self) -> PathBuf {
        PathBuf::from(&self.data_path)
    }

    /// Get path to Prefixes directory
    pub fn get_prefixes_path(&self) -> PathBuf {
        self.get_data_path().join("Prefixes")
    }

    /// Get path to cache directory
    pub fn get_cache_path(&self) -> PathBuf {
        self.get_data_path().join("cache")
    }
}

// ============================================================================
// Cache Config - also stored in ~/.config/nak/
// ============================================================================

#[derive(Serialize, Deserialize, Clone)]
pub struct CacheConfig {
    pub cache_enabled: bool,
    pub cache_dependencies: bool,
    pub cache_mo2: bool,
    pub cache_vortex: bool,
    #[serde(default)]
    pub cache_location: String, // Deprecated - now uses AppConfig::get_cache_path()
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            cache_enabled: true,
            cache_dependencies: true,
            cache_mo2: true,
            cache_vortex: true,
            cache_location: String::new(),
        }
    }
}

impl CacheConfig {
    fn get_config_path() -> PathBuf {
        PathBuf::from(format!("{}/.config/nak/cache_config.json", get_home()))
    }

    fn get_legacy_path() -> PathBuf {
        PathBuf::from(format!("{}/NaK/cache_config.json", get_home()))
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

        // Try legacy location and migrate
        if legacy_path.exists() {
            if let Ok(content) = fs::read_to_string(&legacy_path) {
                if let Ok(config) = serde_json::from_str::<CacheConfig>(&content) {
                    config.save();
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

    /// Clear the cache directory
    pub fn clear_cache(&self, app_config: &AppConfig) -> Result<(), std::io::Error> {
        let cache_dir = app_config.get_cache_path();
        if cache_dir.exists() {
            fs::remove_dir_all(&cache_dir)?;
            fs::create_dir_all(&cache_dir)?;
        }
        Ok(())
    }
}

// ============================================================================
// Storage Manager - for storage info and data path migration
// ============================================================================

pub struct StorageManager;

impl StorageManager {
    /// Get storage info for a given data path
    pub fn get_storage_info(data_path: &Path) -> StorageInfo {
        let exists = data_path.exists();

        let (free_space_gb, used_space_gb, cache_size_gb, proton_size_gb, prefixes_size_gb, other_size_gb) =
            if exists {
                let free = Self::get_free_space(data_path);
                let used = Self::get_directory_size(data_path);

                let cache_size = Self::get_directory_size(&data_path.join("cache"));
                let proton_size = Self::get_directory_size(&data_path.join("ProtonGE"));
                let prefixes_size = Self::get_directory_size(&data_path.join("Prefixes"));

                let known_sum = cache_size + proton_size + prefixes_size;
                let other_size = (used - known_sum).max(0.0);

                (free, used, cache_size, proton_size, prefixes_size, other_size)
            } else {
                (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            };

        StorageInfo {
            data_path: data_path.to_string_lossy().to_string(),
            exists,
            free_space_gb,
            used_space_gb,
            cache_size_gb,
            proton_size_gb,
            prefixes_size_gb,
            other_size_gb,
        }
    }

    /// Get free space on a path in GB
    fn get_free_space(path: &Path) -> f64 {
        use std::process::Command;

        if let Ok(output) = Command::new("df").arg("-B1").arg(path).output() {
            if output.status.success() {
                let output_str = String::from_utf8_lossy(&output.stdout);
                if let Some(line) = output_str.lines().nth(1) {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 4 {
                        if let Ok(bytes) = parts[3].parse::<u64>() {
                            return bytes as f64 / (1024.0 * 1024.0 * 1024.0);
                        }
                    }
                }
            }
        }
        0.0
    }

    /// Get directory size in GB using du
    fn get_directory_size(path: &Path) -> f64 {
        use std::process::Command;

        if !path.exists() {
            return 0.0;
        }

        if let Ok(output) = Command::new("du").arg("-sb").arg(path).output() {
            if output.status.success() {
                let output_str = String::from_utf8_lossy(&output.stdout);
                if let Some(size_str) = output_str.split_whitespace().next() {
                    if let Ok(bytes) = size_str.parse::<u64>() {
                        return bytes as f64 / (1024.0 * 1024.0 * 1024.0);
                    }
                }
            }
        }
        0.0
    }

    /// Validate a storage location
    pub fn validate_location(location: &Path) -> Result<(), String> {
        // Create parent if it doesn't exist
        if !location.exists() {
            if let Err(e) = fs::create_dir_all(location) {
                return Err(format!("Cannot create directory: {}", e));
            }
        }

        if !location.is_dir() {
            return Err(format!("Location is not a directory: {}", location.display()));
        }

        // Check write permission
        let test_file = location.join(".nak_write_test");
        if fs::write(&test_file, "test").is_err() {
            return Err(format!("No write permission for: {}", location.display()));
        }
        let _ = fs::remove_file(&test_file);

        // Check space
        let free_gb = Self::get_free_space(location);
        if free_gb < 5.0 {
            return Err(format!(
                "Insufficient space: {:.2}GB available (minimum 5GB recommended)",
                free_gb
            ));
        }

        Ok(())
    }

    /// Move NaK data to a new location
    pub fn move_data(config: &mut AppConfig, new_location: &Path) -> Result<String, String> {
        let target_nak = new_location.join("NaK");

        // Validate target
        Self::validate_location(new_location)?;

        // Check if target NaK folder already exists
        if target_nak.exists() {
            // Check if it's empty or only has hidden files (safe to overwrite)
            let is_empty = match fs::read_dir(&target_nak) {
                Ok(entries) => entries
                    .filter_map(|e| e.ok())
                    .filter(|e| {
                        // Filter out hidden files (starting with .)
                        !e.file_name().to_string_lossy().starts_with('.')
                    })
                    .count() == 0,
                Err(_) => false,
            };

            if is_empty {
                // Empty folder - safe to remove and proceed
                let _ = fs::remove_dir_all(&target_nak);
            } else {
                return Err(format!(
                    "Target location already has a NaK folder with data: {}\n\
                    Please remove it manually or choose a different location.",
                    target_nak.display()
                ));
            }
        }

        let current_path = config.get_data_path();

        // Move the data
        if current_path.exists() {
            move_dir_all(&current_path, &target_nak)
                .map_err(|e| format!("Failed to move NaK folder: {}", e))?;
        } else {
            // No existing data, just create the new directory
            fs::create_dir_all(&target_nak)
                .map_err(|e| format!("Failed to create NaK directory: {}", e))?;
        }

        // Update config
        config.data_path = target_nak.to_string_lossy().to_string();
        config.save();

        // Fix all symlinks that have absolute paths (they now point to old location)
        // This updates manager_link, convenience symlinks in mod manager folders, etc.
        if let Err(e) = crate::scripts::fix_symlinks_after_move() {
            eprintln!("Warning: Failed to fix symlinks after move: {}", e);
        }

        // Regenerate NXM handler - the .desktop file has absolute path to the script
        // which needs to be updated to the new location
        if let Err(e) = crate::nxm::NxmHandler::setup() {
            eprintln!("Warning: Failed to regenerate NXM handler: {}", e);
        }

        Ok(format!(
            "Successfully moved NaK data to {}",
            target_nak.display()
        ))
    }
}

#[derive(Clone, Default)]
pub struct StorageInfo {
    pub data_path: String,
    pub exists: bool,
    pub free_space_gb: f64,
    pub used_space_gb: f64,
    pub cache_size_gb: f64,
    pub proton_size_gb: f64,
    pub prefixes_size_gb: f64,
    pub other_size_gb: f64,
}
