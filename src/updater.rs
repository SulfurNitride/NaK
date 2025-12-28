//! In-place updater for NaK
//!
//! Checks GitHub releases and updates the application binary.

use std::error::Error;
use std::fs::{self, File};
use std::io::{Read, Write};
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use crate::logging::{log_download, log_error, log_info};

const GITHUB_REPO: &str = "SulfurNitride/NaK";
const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(Debug, Clone)]
pub struct UpdateInfo {
    pub current_version: String,
    pub latest_version: String,
    pub download_url: Option<String>,
    pub release_notes: String,
    pub is_update_available: bool,
}

#[derive(serde::Deserialize)]
struct GitHubRelease {
    tag_name: String,
    body: Option<String>,
    assets: Vec<GitHubAsset>,
}

#[derive(serde::Deserialize)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
}

/// Check GitHub for the latest release
pub fn check_for_updates() -> Result<UpdateInfo, Box<dyn Error>> {
    let url = format!("https://api.github.com/repos/{}/releases/latest", GITHUB_REPO);
    let response = ureq::get(&url)
        .set("User-Agent", "NaK-Updater")
        .call()?;
    let release: GitHubRelease = response.into_json()?;

    // Extract version number from tag (remove 'v' prefix if present)
    let latest_version = release.tag_name.trim_start_matches('v').to_string();

    // Check if update is available by comparing versions
    let is_update_available = is_newer_version(&latest_version, CURRENT_VERSION);

    // Find the Linux binary asset
    let download_url = release.assets.iter()
        .find(|a| {
            let name = a.name.to_lowercase();
            // Look for Linux binary - adjust pattern based on your release naming
            name.contains("linux") || name == "nak" || name == "nak_rust"
        })
        .map(|a| a.browser_download_url.clone());

    Ok(UpdateInfo {
        current_version: CURRENT_VERSION.to_string(),
        latest_version,
        download_url,
        release_notes: release.body.unwrap_or_default(),
        is_update_available,
    })
}

/// Compare version strings (simple semver comparison)
fn is_newer_version(latest: &str, current: &str) -> bool {
    let parse_version = |v: &str| -> Vec<u32> {
        v.split('.')
            .filter_map(|s| s.parse::<u32>().ok())
            .collect()
    };

    let latest_parts = parse_version(latest);
    let current_parts = parse_version(current);

    for i in 0..latest_parts.len().max(current_parts.len()) {
        let l = latest_parts.get(i).copied().unwrap_or(0);
        let c = current_parts.get(i).copied().unwrap_or(0);
        if l > c {
            return true;
        } else if l < c {
            return false;
        }
    }
    false
}

/// Download and install the update
pub fn install_update(download_url: &str) -> Result<(), Box<dyn Error>> {
    log_info(&format!("Downloading update from: {}", download_url));

    // Get the current executable path
    let current_exe = std::env::current_exe()?;
    let exe_dir = current_exe.parent()
        .ok_or("Failed to get executable directory")?;

    // Create temp paths
    let temp_download = exe_dir.join(".nak_update_download");
    let temp_extract = exe_dir.join(".nak_update_extract");
    let backup_path = exe_dir.join(".nak_backup");

    // Clean up any previous failed update attempts
    let _ = fs::remove_file(&temp_download);
    let _ = fs::remove_dir_all(&temp_extract);

    // Download the update
    log_download("Downloading NaK update...");
    let response = ureq::get(download_url)
        .set("User-Agent", "NaK-Updater")
        .call()?;

    let mut file = File::create(&temp_download)?;
    let mut reader = response.into_reader();
    std::io::copy(&mut reader, &mut file)?;
    file.flush()?;
    drop(file);

    log_info("Download complete, extracting...");

    // Determine if it's an archive and extract if needed
    let new_binary_path = if download_url.ends_with(".zip") {
        extract_zip(&temp_download, &temp_extract)?
    } else if download_url.ends_with(".tar.gz") || download_url.ends_with(".tgz") {
        extract_tar_gz(&temp_download, &temp_extract)?
    } else {
        // Assume it's a raw binary
        temp_download.clone()
    };

    // Make the new binary executable
    let mut perms = fs::metadata(&new_binary_path)?.permissions();
    perms.set_mode(0o755);
    fs::set_permissions(&new_binary_path, perms)?;

    // Backup current executable
    if backup_path.exists() {
        fs::remove_file(&backup_path)?;
    }
    fs::rename(&current_exe, &backup_path)?;

    // Move new binary into place
    if let Err(e) = fs::rename(&new_binary_path, &current_exe) {
        // Restore backup on failure
        log_error(&format!("Failed to install update: {}", e));
        let _ = fs::rename(&backup_path, &current_exe);
        return Err(e.into());
    }

    // Clean up
    let _ = fs::remove_file(&backup_path);
    let _ = fs::remove_file(&temp_download);
    let _ = fs::remove_dir_all(&temp_extract);

    log_info("Update installed successfully!");
    Ok(())
}

/// Extract a zip archive and return the path to the binary inside
fn extract_zip(zip_path: &Path, extract_dir: &Path) -> Result<std::path::PathBuf, Box<dyn Error>> {
    fs::create_dir_all(extract_dir)?;

    let file = File::open(zip_path)?;
    let mut archive = zip::ZipArchive::new(file)?;

    // Extract all files
    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let outpath = extract_dir.join(file.mangled_name());

        if file.name().ends_with('/') {
            fs::create_dir_all(&outpath)?;
        } else {
            if let Some(p) = outpath.parent() {
                if !p.exists() {
                    fs::create_dir_all(p)?;
                }
            }
            let mut outfile = File::create(&outpath)?;
            std::io::copy(&mut file, &mut outfile)?;
        }
    }

    // Find the binary (look for nak_rust or nak)
    find_binary_in_dir(extract_dir)
}

/// Extract a tar.gz archive and return the path to the binary inside
fn extract_tar_gz(tar_path: &Path, extract_dir: &Path) -> Result<std::path::PathBuf, Box<dyn Error>> {
    fs::create_dir_all(extract_dir)?;

    let file = File::open(tar_path)?;
    let decoder = flate2::read::GzDecoder::new(file);
    let mut archive = tar::Archive::new(decoder);
    archive.unpack(extract_dir)?;

    // Find the binary
    find_binary_in_dir(extract_dir)
}

/// Find the NaK binary in an extracted directory
fn find_binary_in_dir(dir: &Path) -> Result<std::path::PathBuf, Box<dyn Error>> {
    // Look for common binary names
    let binary_names = ["nak_rust", "nak", "NaK"];

    for entry in walkdir::WalkDir::new(dir).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if path.is_file() {
            if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                // Check exact matches first
                if binary_names.contains(&name) {
                    return Ok(path.to_path_buf());
                }
                // Check if it's an executable (no extension, not a known non-binary)
                if !name.contains('.') && !name.starts_with('.') {
                    // Verify it's actually executable by checking for ELF header
                    if let Ok(mut f) = File::open(path) {
                        let mut magic = [0u8; 4];
                        if f.read_exact(&mut magic).is_ok() && magic == [0x7f, b'E', b'L', b'F'] {
                            return Ok(path.to_path_buf());
                        }
                    }
                }
            }
        }
    }

    Err("Could not find binary in update archive".into())
}

/// Restart NaK after update
pub fn restart_application() -> Result<(), Box<dyn Error>> {
    let current_exe = std::env::current_exe()?;
    log_info(&format!("Restarting NaK from: {:?}", current_exe));

    // Spawn the new process
    std::process::Command::new(&current_exe)
        .spawn()?;

    // Exit the current process
    std::process::exit(0);
}

/// Check if the current executable is in a writable location
pub fn can_self_update() -> bool {
    match std::env::current_exe() {
        Ok(exe_path) => {
            // Check if we can write to the directory
            if let Some(parent) = exe_path.parent() {
                let test_file = parent.join(".nak_write_test");
                if fs::write(&test_file, "test").is_ok() {
                    let _ = fs::remove_file(&test_file);
                    return true;
                }
            }
            false
        }
        Err(_) => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version_comparison() {
        assert!(is_newer_version("4.2.0", "4.1.2"));
        assert!(is_newer_version("4.1.3", "4.1.2"));
        assert!(is_newer_version("5.0.0", "4.9.9"));
        assert!(!is_newer_version("4.1.2", "4.1.2"));
        assert!(!is_newer_version("4.1.1", "4.1.2"));
        assert!(!is_newer_version("3.9.9", "4.0.0"));
    }
}
