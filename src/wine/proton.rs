//! Proton detection and GE-Proton management

use flate2::read::GzDecoder;
use serde::Deserialize;
use std::error::Error;
use std::fs;
use std::io::{Read, Write};
use std::path::PathBuf;
use tar::Archive;

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
        Self {
            steam_root: PathBuf::from(format!("{}/.steam/steam", home)),
            nak_proton_ge_root: PathBuf::from(format!("{}/NaK/ProtonGE", home)),
            nak_proton_cachyos_root: PathBuf::from(format!("{}/NaK/ProtonCachyOS", home)),
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

/// Sets the 'active' symlink for the selected proton (at ~/NaK/ProtonGE/active)
pub fn set_active_proton(proton: &ProtonInfo) -> Result<(), Box<dyn std::error::Error>> {
    let home = std::env::var("HOME")?;
    let active_link = PathBuf::from(format!("{}/NaK/ProtonGE/active", home));

    // Remove existing symlink if present
    if active_link.exists() || fs::symlink_metadata(&active_link).is_ok() {
        let _ = fs::remove_file(&active_link);
    }

    // Create new symlink pointing to the selected proton
    std::os::unix::fs::symlink(&proton.path, &active_link)?;

    Ok(())
}

impl ProtonInfo {
    pub fn parse_version(&self) -> (u32, u32) {
        // Extract version from "GE-Proton9-20" -> 9, 20
        let parts: Vec<&str> = self.name.split("Proton").collect();
        if parts.len() < 2 {
            return (0, 0);
        }

        let ver_str = parts[1]; // "9-20"
        let nums: Vec<&str> = ver_str.split('-').collect();

        let major = nums.first().and_then(|s| s.parse().ok()).unwrap_or(0);
        let minor = nums.get(1).and_then(|s| s.parse().ok()).unwrap_or(0);

        (major, minor)
    }

    pub fn supports_dotnet48(&self) -> bool {
        // Most modern Proton versions support dotnet48 via winetricks
        // GE-Proton 8+ and Valve Proton 7+ should work fine

        if self.name.starts_with("GE-Proton") {
            let (major, _) = self.parse_version();
            return major >= 8;
        }

        // Valve Proton versions (e.g., "Proton 9.0 (Beta)", "Proton - Experimental")
        if self.name.starts_with("Proton") {
            // Experimental always supports it
            if self.is_experimental || self.name.contains("Experimental") {
                return true;
            }

            // Parse version like "Proton 9.0 (Beta)" or "Proton 8.0"
            let version_str = self
                .name
                .replace("Proton ", "")
                .replace(" (Beta)", "")
                .replace("-", ".");

            if let Some(major_str) = version_str.split('.').next() {
                if let Ok(major) = major_str.parse::<u32>() {
                    return major >= 7;
                }
            }
        }

        // Default to true - let winetricks try anyway
        true
    }
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
    let home = std::env::var("HOME")?;
    let install_root = PathBuf::from(format!("{}/NaK/ProtonGE", home));
    let temp_dir = PathBuf::from(format!("{}/NaK/tmp", home));

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
    let home = std::env::var("HOME")?;
    let install_path = PathBuf::from(format!("{}/NaK/ProtonGE/{}", home, version_name));

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

    let home = std::env::var("HOME")?;
    let install_root = PathBuf::from(format!("{}/NaK/ProtonCachyOS", home));
    let temp_dir = PathBuf::from(format!("{}/NaK/tmp", home));

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
    let home = std::env::var("HOME")?;
    let install_path = PathBuf::from(format!("{}/NaK/ProtonCachyOS/{}", home, version_name));

    if install_path.exists() {
        fs::remove_dir_all(install_path)?;
    }
    Ok(())
}
