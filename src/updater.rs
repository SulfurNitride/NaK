//! In-place updater for NaK
//!
//! Checks GitHub releases and updates the application binary.

use std::error::Error;
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;

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

    // Create temp file for download
    let temp_path = exe_dir.join(".nak_update_temp");
    let backup_path = exe_dir.join(".nak_backup");

    // Download the new binary
    log_download("Downloading NaK update...");
    let response = ureq::get(download_url)
        .set("User-Agent", "NaK-Updater")
        .call()?;

    let mut file = fs::File::create(&temp_path)?;
    let mut reader = response.into_reader();
    std::io::copy(&mut reader, &mut file)?;
    file.flush()?;
    drop(file);

    // Make the new binary executable
    let mut perms = fs::metadata(&temp_path)?.permissions();
    perms.set_mode(0o755);
    fs::set_permissions(&temp_path, perms)?;

    // Backup current executable
    if backup_path.exists() {
        fs::remove_file(&backup_path)?;
    }
    fs::rename(&current_exe, &backup_path)?;

    // Move new binary into place
    if let Err(e) = fs::rename(&temp_path, &current_exe) {
        // Restore backup on failure
        log_error(&format!("Failed to install update: {}", e));
        let _ = fs::rename(&backup_path, &current_exe);
        return Err(e.into());
    }

    // Clean up backup (optional - could keep it for rollback)
    let _ = fs::remove_file(&backup_path);

    log_info("Update installed successfully! Please restart NaK.");
    Ok(())
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
