use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

// ============================================================================
// Main App Config
// ============================================================================

#[derive(Serialize, Deserialize, Default, Clone)]
pub struct AppConfig {
    pub selected_proton: Option<String>,
    pub active_nxm_prefix: Option<String>,
}

impl AppConfig {
    fn get_path() -> PathBuf {
        let home = std::env::var("HOME").expect("Failed to get HOME");
        PathBuf::from(format!("{}/NaK/config.json", home))
    }

    pub fn load() -> Self {
        let path = Self::get_path();
        if path.exists() {
            if let Ok(content) = fs::read_to_string(&path) {
                if let Ok(config) = serde_json::from_str(&content) {
                    return config;
                }
            }
        }
        Self::default()
    }

    pub fn save(&self) {
        let path = Self::get_path();
        // Ensure parent dir exists
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(json) = serde_json::to_string_pretty(self) {
            let _ = fs::write(path, json);
        }
    }
}

// ============================================================================
// Cache Config
// ============================================================================

#[derive(Serialize, Deserialize, Clone)]
pub struct CacheConfig {
    pub cache_enabled: bool,
    pub cache_dependencies: bool,
    pub cache_mo2: bool,
    pub cache_vortex: bool,
    pub cache_location: String,
}

impl Default for CacheConfig {
    fn default() -> Self {
        let home = std::env::var("HOME").unwrap_or_default();
        Self {
            cache_enabled: true,
            cache_dependencies: true,
            cache_mo2: true,
            cache_vortex: true,
            cache_location: format!("{}/NaK/cache", home),
        }
    }
}

impl CacheConfig {
    fn get_path() -> PathBuf {
        let home = std::env::var("HOME").expect("Failed to get HOME");
        PathBuf::from(format!("{}/NaK/cache_config.json", home))
    }

    pub fn load() -> Self {
        let path = Self::get_path();
        if path.exists() {
            if let Ok(content) = fs::read_to_string(&path) {
                if let Ok(config) = serde_json::from_str(&content) {
                    return config;
                }
            }
        }
        Self::default()
    }

    pub fn save(&self) {
        let path = Self::get_path();
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(json) = serde_json::to_string_pretty(self) {
            let _ = fs::write(path, json);
        }
    }

    /// Get cache info (size, file count)
    pub fn get_cache_info(&self) -> CacheInfo {
        let cache_dir = PathBuf::from(&self.cache_location);

        if !cache_dir.exists() {
            return CacheInfo {
                exists: false,
                size_mb: 0.0,
                file_count: 0,
                location: self.cache_location.clone(),
            };
        }

        let mut total_size: u64 = 0;
        let mut file_count: u64 = 0;

        for entry in walkdir::WalkDir::new(&cache_dir).into_iter().flatten() {
            if entry.file_type().is_file() {
                if let Ok(meta) = entry.metadata() {
                    total_size += meta.len();
                    file_count += 1;
                }
            }
        }

        CacheInfo {
            exists: true,
            size_mb: total_size as f64 / (1024.0 * 1024.0),
            file_count,
            location: self.cache_location.clone(),
        }
    }

    /// Clear the cache directory
    pub fn clear_cache(&self) -> Result<(), std::io::Error> {
        let cache_dir = PathBuf::from(&self.cache_location);
        if cache_dir.exists() {
            fs::remove_dir_all(&cache_dir)?;
            fs::create_dir_all(&cache_dir)?;
        }
        Ok(())
    }
}

#[derive(Clone)]
pub struct CacheInfo {
    pub exists: bool,
    pub size_mb: f64,
    pub file_count: u64,
    pub location: String,
}

// ============================================================================
// Storage Manager (for NaK folder location/migration)
// ============================================================================

pub struct StorageManager {
    default_nak_path: PathBuf,
}

impl StorageManager {
    pub fn new() -> Self {
        let home = std::env::var("HOME").unwrap_or_default();
        Self {
            default_nak_path: PathBuf::from(format!("{}/NaK", home)),
        }
    }

    /// Check if ~/NaK is a symlink
    pub fn is_symlink(&self) -> bool {
        self.default_nak_path.is_symlink()
    }

    /// Get the real storage location (resolves symlinks)
    pub fn get_real_location(&self) -> PathBuf {
        if self.default_nak_path.exists() {
            self.default_nak_path
                .canonicalize()
                .unwrap_or_else(|_| self.default_nak_path.clone())
        } else {
            self.default_nak_path.clone()
        }
    }

    /// Get storage info
    pub fn get_storage_info(&self) -> StorageInfo {
        let real_path = self.get_real_location();
        let exists = self.default_nak_path.exists();

        let (free_space_gb, used_space_gb, cache_size_gb, proton_size_gb, prefixes_size_gb, other_size_gb) =
            if exists {
                let free = Self::get_free_space(&real_path);
                let used = Self::get_directory_size(&real_path);

                let cache_size = Self::get_directory_size(&real_path.join("cache"));
                let proton_size = Self::get_directory_size(&real_path.join("ProtonGE"));
                let prefixes_size = Self::get_directory_size(&real_path.join("Prefixes"));
                
                let known_sum = cache_size + proton_size + prefixes_size;
                let other_size = (used - known_sum).max(0.0);

                (free, used, cache_size, proton_size, prefixes_size, other_size)
            } else {
                (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            };

        StorageInfo {
            is_symlink: self.is_symlink(),
            nak_path: self.default_nak_path.to_string_lossy().to_string(),
            real_path: real_path.to_string_lossy().to_string(),
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
                // Parse df output (second line, 4th column is available bytes)
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

        match Command::new("du").arg("-sb").arg(path).output() {
            Ok(output) => {
                if output.status.success() {
                    let output_str = String::from_utf8_lossy(&output.stdout);
                    if let Some(size_str) = output_str.split_whitespace().next() {
                        if let Ok(bytes) = size_str.parse::<u64>() {
                            return bytes as f64 / (1024.0 * 1024.0 * 1024.0);
                        }
                    }
                } else {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    crate::logging::log_error(&format!(
                        "Failed to calculate size for {}: {}",
                        path.display(),
                        stderr.trim()
                    ));
                }
            }
            Err(e) => {
                crate::logging::log_error(&format!(
                    "Failed to execute du for {}: {}",
                    path.display(),
                    e
                ));
            }
        }
        0.0
    }

    /// Validate a storage location
    pub fn validate_location(&self, location: &Path) -> Result<(), String> {
        if !location.exists() {
            return Err(format!("Location does not exist: {}", location.display()));
        }
        if !location.is_dir() {
            return Err(format!(
                "Location is not a directory: {}",
                location.display()
            ));
        }

        // Check write permission by trying to create a test file
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

    /// Setup symlink from ~/NaK to a new location
    pub fn setup_symlink(
        &self,
        new_location: &Path,
        move_existing: bool,
    ) -> Result<String, String> {
        // Validate new location
        self.validate_location(new_location)?;

        let target_nak = new_location.join("NaK");

        // Handle existing ~/NaK
        if self.default_nak_path.exists() {
            if self.default_nak_path.is_symlink() {
                // Already a symlink, remove it
                fs::remove_file(&self.default_nak_path)
                    .map_err(|e| format!("Failed to remove existing symlink: {}", e))?;
            } else {
                // It's a real directory
                if move_existing {
                    if target_nak.exists() {
                        return Err(format!(
                            "Target location already has a NaK folder: {}",
                            target_nak.display()
                        ));
                    }
                    // Move existing data
                    fs::rename(&self.default_nak_path, &target_nak)
                        .map_err(|e| format!("Failed to move existing NaK folder: {}", e))?;
                } else {
                    // Backup existing
                    let mut backup_path = self.default_nak_path.with_file_name("NaK.backup");
                    let mut counter = 1;
                    while backup_path.exists() {
                        backup_path = self
                            .default_nak_path
                            .with_file_name(format!("NaK.backup.{}", counter));
                        counter += 1;
                    }
                    fs::rename(&self.default_nak_path, &backup_path)
                        .map_err(|e| format!("Failed to backup existing NaK folder: {}", e))?;
                }
            }
        }

        // Create target directory if needed
        if !target_nak.exists() {
            fs::create_dir_all(&target_nak)
                .map_err(|e| format!("Failed to create NaK directory: {}", e))?;
        }

        // Create symlink
        std::os::unix::fs::symlink(&target_nak, &self.default_nak_path)
            .map_err(|e| format!("Failed to create symlink: {}", e))?;

        Ok(format!(
            "Successfully set up NaK storage at {}",
            target_nak.display()
        ))
    }

    /// Remove symlink and restore to default location
    pub fn remove_symlink(&self) -> Result<String, String> {
        if !self.default_nak_path.is_symlink() {
            return Err("~/NaK is not a symlink".to_string());
        }

        let real_location = self.get_real_location();

        fs::remove_file(&self.default_nak_path)
            .map_err(|e| format!("Failed to remove symlink: {}", e))?;

        // Check for backup
        let backup_path = self.default_nak_path.with_file_name("NaK.backup");
        if backup_path.exists() {
            fs::rename(&backup_path, &self.default_nak_path)
                .map_err(|e| format!("Failed to restore backup: {}", e))?;
            return Ok(format!(
                "Symlink removed and backup restored. Data still at {}",
                real_location.display()
            ));
        }

        Ok(format!(
            "Symlink removed. Data still at {}",
            real_location.display()
        ))
    }

    /// Detect existing installations in NaK folder
    pub fn detect_installations(&self) -> InstallationInfo {
        let mut info = InstallationInfo::default();

        if !self.default_nak_path.exists() {
            return info;
        }

        // Check for Proton-GE
        let proton_ge_dir = self.default_nak_path.join("ProtonGE");
        info.has_proton_ge = proton_ge_dir.exists();

        // Check for cache
        let cache_dir = self.default_nak_path.join("cache");
        info.has_cache = cache_dir.exists();

        // Scan prefixes
        let prefixes_dir = self.default_nak_path.join("Prefixes");
        if prefixes_dir.exists() {
            if let Ok(entries) = fs::read_dir(&prefixes_dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if !path.is_dir() {
                        continue;
                    }

                    let name = entry.file_name().to_string_lossy().to_string();

                    // Determine type from name
                    let prefix_type = if name.starts_with("mo2_") {
                        info.mo2_count += 1;
                        "MO2"
                    } else if name.starts_with("vortex_") {
                        info.vortex_count += 1;
                        "Vortex"
                    } else {
                        "Unknown"
                    };

                    info.prefixes.push(PrefixInfo {
                        name,
                        prefix_type: prefix_type.to_string(),
                        path: path.to_string_lossy().to_string(),
                    });
                    info.total_count += 1;
                }
            }
        }

        info
    }
}

#[derive(Clone, Default)]
pub struct StorageInfo {
    pub is_symlink: bool,
    pub nak_path: String,
    pub real_path: String,
    pub exists: bool,
    pub free_space_gb: f64,
    pub used_space_gb: f64,
    pub cache_size_gb: f64,
    pub proton_size_gb: f64,
    pub prefixes_size_gb: f64,
    pub other_size_gb: f64,
}

#[derive(Clone, Default)]
pub struct InstallationInfo {
    pub prefixes: Vec<PrefixInfo>,
    pub total_count: u32,
    pub mo2_count: u32,
    pub vortex_count: u32,
    pub has_proton_ge: bool,
    pub has_cache: bool,
}

#[derive(Clone)]
#[allow(dead_code)]
pub struct PrefixInfo {
    pub name: String,
    pub prefix_type: String,
    pub path: String,
}
