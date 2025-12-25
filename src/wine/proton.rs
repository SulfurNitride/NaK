//! Proton detection and GE-Proton management

use flate2::read::GzDecoder;
use serde::Deserialize;
use std::error::Error;
use std::fs;
use std::io::{Read, Write};
use std::path::PathBuf;
use tar::Archive;

use crate::config::AppConfig;

// ============================================================================
// Proton Info & Finder
// ============================================================================

#[derive(Debug, Clone, PartialEq)]
pub struct ProtonInfo {
    pub name: String,
    pub path: PathBuf,
    pub version: String,
    pub is_experimental: bool,
}

pub struct ProtonFinder {
    pub steam_root: PathBuf,
    pub nak_proton_ge_root: PathBuf,
    pub nak_proton_cachyos_root: PathBuf,
}

impl ProtonFinder {
    pub fn new() -> Self {
        let home = std::env::var("HOME").expect("Failed to get HOME directory");
        let config = AppConfig::load();
        let data_path = config.get_data_path();
        Self {
            steam_root: PathBuf::from(format!("{}/.steam/steam", home)),
            nak_proton_ge_root: data_path.join("ProtonGE"),
            nak_proton_cachyos_root: data_path.join("ProtonCachyOS"),
        }
    }

    pub fn find_all(&self) -> Vec<ProtonInfo> {
        let mut protons = Vec::new();

        // 1. Find Steam Proton Versions
        protons.extend(self.find_steam_protons());

        // 2. Find NaK Proton-GE Versions
        protons.extend(self.find_ge_protons());

        // 3. Find NaK Proton-CachyOS Versions
        protons.extend(self.find_cachyos_protons());

        protons
    }

    fn find_steam_protons(&self) -> Vec<ProtonInfo> {
        let mut found = Vec::new();
        let common_dir = self.steam_root.join("steamapps/common");

        if let Ok(entries) = fs::read_dir(common_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if !path.is_dir() {
                    continue;
                }

                let name = entry.file_name().to_string_lossy().to_string();

                // Check for valid Proton directory (must have 'proton' script)
                if name.starts_with("Proton") && path.join("proton").exists() {
                    let is_experimental = name.contains("Experimental");
                    let version = if is_experimental {
                        "Experimental".to_string()
                    } else {
                        name.replace("Proton ", "")
                    };

                    found.push(ProtonInfo {
                        name: name.clone(),
                        path,
                        version,
                        is_experimental,
                    });
                }
            }
        }
        found
    }

    fn find_ge_protons(&self) -> Vec<ProtonInfo> {
        let mut found = Vec::new();

        // Canonicalize the root path to resolve symlinks
        let ge_root =
            fs::canonicalize(&self.nak_proton_ge_root).unwrap_or(self.nak_proton_ge_root.clone());

        if let Ok(entries) = fs::read_dir(&ge_root) {
            for entry in entries.flatten() {
                let path = entry.path();
                if !path.is_dir() {
                    continue;
                }

                let name = entry.file_name().to_string_lossy().to_string();

                // Skip the 'active' symlink
                if name == "active" {
                    continue;
                }

                // Must look like "GE-Proton..."
                if name.starts_with("GE-Proton") {
                    // Canonicalize the full path to resolve any symlinks
                    let real_path = fs::canonicalize(&path).unwrap_or(path);
                    found.push(ProtonInfo {
                        name: name.clone(),
                        path: real_path,
                        version: name.clone(),
                        is_experimental: false,
                    });
                }
            }
        }
        found
    }

    fn find_cachyos_protons(&self) -> Vec<ProtonInfo> {
        let mut found = Vec::new();

        // Canonicalize the root path to resolve symlinks
        let cachyos_root = fs::canonicalize(&self.nak_proton_cachyos_root)
            .unwrap_or(self.nak_proton_cachyos_root.clone());

        if let Ok(entries) = fs::read_dir(&cachyos_root) {
            for entry in entries.flatten() {
                let path = entry.path();
                if !path.is_dir() {
                    continue;
                }

                let name = entry.file_name().to_string_lossy().to_string();

                // Skip the 'active' symlink
                if name == "active" {
                    continue;
                }

                // Must look like "proton-cachyos..."
                if name.starts_with("proton-cachyos") {
                    // Canonicalize the full path to resolve any symlinks
                    let real_path = fs::canonicalize(&path).unwrap_or(path);
                    found.push(ProtonInfo {
                        name: name.clone(),
                        path: real_path,
                        version: name.clone(),
                        is_experimental: false,
                    });
                }
            }
        }
        found
    }
}

/// Sets the 'active' symlink for the selected proton (at $DATA_PATH/ProtonGE/active)
pub fn set_active_proton(proton: &ProtonInfo) -> Result<(), Box<dyn std::error::Error>> {
    let config = AppConfig::load();
    let active_link = config.get_data_path().join("ProtonGE/active");

    // Ensure parent directory exists
    if let Some(parent) = active_link.parent() {
        fs::create_dir_all(parent)?;
    }

    // Remove existing symlink if present
    if active_link.exists() || fs::symlink_metadata(&active_link).is_ok() {
        let _ = fs::remove_file(&active_link);
    }

    // Create new symlink pointing to the selected proton
    std::os::unix::fs::symlink(&proton.path, &active_link)?;

    Ok(())
}

// ============================================================================
// GE-Proton10-18 Workaround for dotnet48
// ============================================================================
// Valve's Proton Experimental and some other Proton versions fail to install
// .NET Framework 4.8 properly. GE-Proton10-18 is known to work reliably.

const DOTNET48_PROTON_VERSION: &str = "GE-Proton10-18";
const DOTNET48_PROTON_URL: &str = "https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton10-18/GE-Proton10-18.tar.gz";

impl ProtonInfo {
    /// Parse the major and minor version numbers from the Proton name.
    /// Returns (major, minor) tuple, (0, 0) if parsing fails.
    pub fn version(&self) -> (u32, u32) {
        // GE-Proton format: "GE-Proton10-18" -> (10, 18)
        if self.name.starts_with("GE-Proton") {
            if let Some(ver_part) = self.name.strip_prefix("GE-Proton") {
                let parts: Vec<&str> = ver_part.split('-').collect();
                let major = parts.first().and_then(|s| s.parse().ok()).unwrap_or(0);
                let minor = parts.get(1).and_then(|s| s.parse().ok()).unwrap_or(0);
                return (major, minor);
            }
            return (0, 0);
        }

        // Valve Proton format: "Proton 9.0 (Beta)" or "Proton - Experimental"
        if self.name.starts_with("Proton") {
            // Experimental is always latest, assume 10+
            if self.name.contains("Experimental") {
                return (10, 0);
            }

            let version_str = self.name
                .replace("Proton ", "")
                .replace(" (Beta)", "");

            let parts: Vec<&str> = version_str.split('.').collect();
            let major = parts.first().and_then(|s| s.parse().ok()).unwrap_or(0);
            let minor = parts.get(1).and_then(|s| s.parse().ok()).unwrap_or(0);
            return (major, minor);
        }

        // CachyOS format: "proton-cachyos-10.0" -> (10, 0)
        if self.name.starts_with("proton-cachyos") {
            if let Some(ver) = self.name.strip_prefix("proton-cachyos-") {
                let parts: Vec<&str> = ver.split('.').collect();
                let major = parts.first().and_then(|s| s.parse().ok()).unwrap_or(0);
                let minor = parts.get(1).and_then(|s| s.parse().ok()).unwrap_or(0);
                return (major, minor);
            }
            return (0, 0);
        }

        (0, 0)
    }

    /// Check if this Proton version is 10 or higher (requires manual dotnet installation).
    pub fn is_proton_10_plus(&self) -> bool {
        self.version().0 >= 10
    }

    /// Check if this Proton version needs the GE-Proton10-18 workaround for dotnet installation.
    /// ALL Proton 10+ versions use GE-Proton10-18 for dependency installation, then switch
    /// to the user's selected Proton for runtime.
    pub fn needs_ge_proton_workaround(&self) -> bool {
        self.is_proton_10_plus()
    }
}

/// Ensures GE-Proton10-18 is available for dotnet installation workaround.
/// Returns the ProtonInfo for GE-Proton10-18.
pub fn ensure_dotnet48_proton<S>(status_callback: S) -> Result<ProtonInfo, Box<dyn Error>>
where
    S: Fn(&str) + Send + 'static,
{
    let config = AppConfig::load();
    let data_path = config.get_data_path();
    let install_root = data_path.join("ProtonGE");
    let proton_path = install_root.join(DOTNET48_PROTON_VERSION);

    // Check if already installed
    if proton_path.exists() && proton_path.join("proton").exists() {
        status_callback(&format!("{} already available", DOTNET48_PROTON_VERSION));
        return Ok(ProtonInfo {
            name: DOTNET48_PROTON_VERSION.to_string(),
            path: proton_path,
            version: DOTNET48_PROTON_VERSION.to_string(),
            is_experimental: false,
        });
    }

    // Download GE-Proton10-18
    status_callback(&format!(
        "Downloading {} for dotnet compatibility...",
        DOTNET48_PROTON_VERSION
    ));

    let temp_dir = data_path.join("tmp");
    fs::create_dir_all(&install_root)?;
    fs::create_dir_all(&temp_dir)?;

    let file_name = format!("{}.tar.gz", DOTNET48_PROTON_VERSION);
    let temp_file_path = temp_dir.join(&file_name);

    // Download
    let response = ureq::get(DOTNET48_PROTON_URL)
        .set("User-Agent", "NaK-Rust-Agent")
        .call()?;

    let mut file = fs::File::create(&temp_file_path)?;
    let mut buffer = [0; 65536];
    let mut reader = response.into_reader();

    loop {
        let bytes_read = reader.read(&mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        file.write_all(&buffer[..bytes_read])?;
    }

    // Extract
    status_callback("Extracting archive...");
    let tar_gz = fs::File::open(&temp_file_path)?;
    let tar = GzDecoder::new(tar_gz);
    let mut archive = Archive::new(tar);
    archive.unpack(&install_root)?;

    // Cleanup
    fs::remove_file(temp_file_path)?;

    status_callback(&format!("{} ready", DOTNET48_PROTON_VERSION));

    Ok(ProtonInfo {
        name: DOTNET48_PROTON_VERSION.to_string(),
        path: proton_path,
        version: DOTNET48_PROTON_VERSION.to_string(),
        is_experimental: false,
    })
}

// ============================================================================
// GitHub Release Types (shared for GE-Proton, MO2, Vortex)
// ============================================================================

#[derive(Deserialize, Debug, Clone)]
#[allow(dead_code)]
pub struct GithubRelease {
    pub tag_name: String,
    pub html_url: String,
    pub assets: Vec<GithubAsset>,
}

#[derive(Deserialize, Debug, Clone)]
#[allow(dead_code)]
pub struct GithubAsset {
    pub name: String,
    pub browser_download_url: String,
    pub size: u64,
}

// ============================================================================
// GE-Proton Download/Delete
// ============================================================================

/// Fetches the latest 100 releases from GitHub
pub fn fetch_ge_releases() -> Result<Vec<GithubRelease>, Box<dyn Error>> {
    let releases: Vec<GithubRelease> = ureq::get(
        "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases?per_page=100",
    )
    .set("User-Agent", "NaK-Rust-Agent")
    .call()?
    .into_json()?;
    Ok(releases)
}

/// Downloads and extracts a GE-Proton release with progress tracking
pub fn download_ge_proton<F, S>(
    asset_url: String,
    file_name: String,
    progress_callback: F,
    status_callback: S,
) -> Result<(), Box<dyn Error>>
where
    F: Fn(u64, u64) + Send + 'static,
    S: Fn(&str) + Send + 'static,
{
    let config = AppConfig::load();
    let data_path = config.get_data_path();
    let install_root = data_path.join("ProtonGE");
    let temp_dir = data_path.join("tmp");

    fs::create_dir_all(&install_root)?;
    fs::create_dir_all(&temp_dir)?;

    let temp_file_path = temp_dir.join(&file_name);

    // 1. Download
    let response = ureq::get(&asset_url)
        .set("User-Agent", "NaK-Rust-Agent")
        .call()?;

    let total_size = response
        .header("Content-Length")
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);

    let mut file = fs::File::create(&temp_file_path)?;

    let mut buffer = [0; 65536]; // 64KB buffer for faster downloads
    let mut downloaded: u64 = 0;
    let mut reader = response.into_reader();

    loop {
        let bytes_read = reader.read(&mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        file.write_all(&buffer[..bytes_read])?;
        downloaded += bytes_read as u64;

        if total_size > 0 {
            progress_callback(downloaded, total_size);
        }
    }

    // 2. Extract
    status_callback("Extracting archive (this may take a moment)...");
    let tar_gz = fs::File::open(&temp_file_path)?;
    let tar = GzDecoder::new(tar_gz);
    let mut archive = Archive::new(tar);

    // Extract to ~/NaK/ProtonGE/
    archive.unpack(&install_root)?;

    // 3. Cleanup
    fs::remove_file(temp_file_path)?;

    Ok(())
}

/// Deletes a GE-Proton version
pub fn delete_ge_proton(version_name: &str) -> Result<(), Box<dyn Error>> {
    let config = AppConfig::load();
    let install_path = config.get_data_path().join("ProtonGE").join(version_name);

    if install_path.exists() {
        fs::remove_dir_all(install_path)?;
    }
    Ok(())
}

// ============================================================================
// CachyOS Proton Download/Delete
// ============================================================================

/// Fetches the latest releases from CachyOS Proton GitHub
pub fn fetch_cachyos_releases() -> Result<Vec<GithubRelease>, Box<dyn Error>> {
    let releases: Vec<GithubRelease> =
        ureq::get("https://api.github.com/repos/CachyOS/proton-cachyos/releases?per_page=50")
            .set("User-Agent", "NaK-Rust-Agent")
            .call()?
            .into_json()?;
    Ok(releases)
}

/// Downloads and extracts a CachyOS Proton release with progress tracking
/// Note: CachyOS uses .tar.xz format
pub fn download_cachyos_proton<F, S>(
    asset_url: String,
    file_name: String,
    progress_callback: F,
    status_callback: S,
) -> Result<(), Box<dyn Error>>
where
    F: Fn(u64, u64) + Send + 'static,
    S: Fn(&str) + Send + 'static,
{
    use xz2::read::XzDecoder;

    let config = AppConfig::load();
    let data_path = config.get_data_path();
    let install_root = data_path.join("ProtonCachyOS");
    let temp_dir = data_path.join("tmp");

    fs::create_dir_all(&install_root)?;
    fs::create_dir_all(&temp_dir)?;

    let temp_file_path = temp_dir.join(&file_name);

    // 1. Download
    let response = ureq::get(&asset_url)
        .set("User-Agent", "NaK-Rust-Agent")
        .call()?;

    let total_size = response
        .header("Content-Length")
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);

    let mut file = fs::File::create(&temp_file_path)?;

    let mut buffer = [0; 65536]; // 64KB buffer for faster downloads
    let mut downloaded: u64 = 0;
    let mut reader = response.into_reader();

    loop {
        let bytes_read = reader.read(&mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        file.write_all(&buffer[..bytes_read])?;
        downloaded += bytes_read as u64;

        if total_size > 0 {
            progress_callback(downloaded, total_size);
        }
    }

    // 2. Extract (.tar.xz)
    status_callback("Extracting archive (this may take a moment)...");
    let tar_xz = fs::File::open(&temp_file_path)?;
    let tar = XzDecoder::new(tar_xz);
    let mut archive = Archive::new(tar);

    // Extract to ~/NaK/ProtonCachyOS/
    archive.unpack(&install_root)?;

    // 3. Cleanup
    fs::remove_file(temp_file_path)?;

    Ok(())
}

/// Deletes a CachyOS Proton version
pub fn delete_cachyos_proton(version_name: &str) -> Result<(), Box<dyn Error>> {
    let config = AppConfig::load();
    let install_path = config.get_data_path().join("ProtonCachyOS").join(version_name);

    if install_path.exists() {
        fs::remove_dir_all(install_path)?;
    }
    Ok(())
}
