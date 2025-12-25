//! Shared utility functions used across the application

use std::error::Error;
use std::fs;
use std::path::Path;

use crate::logging::{log_info, log_warning};

/// Detect the Steam installation path
/// Checks common locations for native, Flatpak, and Snap Steam installs
/// Returns None if Steam is not found
#[must_use]
pub fn detect_steam_path_checked() -> Option<String> {
    let home = std::env::var("HOME").unwrap_or_default();

    // Check native Steam locations in order of preference
    let native_paths = [
        format!("{}/.steam/steam", home),
        format!("{}/.local/share/Steam", home),
    ];

    for path in &native_paths {
        if Path::new(path).exists() {
            log_info(&format!("Steam detected at: {}", path));
            return Some(path.clone());
        }
    }

    // Check Flatpak Steam location
    let flatpak_path = format!("{}/.var/app/com.valvesoftware.Steam/.steam/steam", home);
    if Path::new(&flatpak_path).exists() {
        log_info(&format!("Steam detected (Flatpak) at: {}", flatpak_path));
        return Some(flatpak_path);
    }

    // Check Snap Steam location
    let snap_path = format!("{}/snap/steam/common/.steam/steam", home);
    if Path::new(&snap_path).exists() {
        log_info(&format!("Steam detected (Snap) at: {}", snap_path));
        return Some(snap_path);
    }

    log_warning("Steam installation not detected! NaK requires Steam to be installed.");
    None
}

/// Detect the Steam installation path (always returns a path)
/// Wrapper around detect_steam_path_checked that provides a fallback
#[must_use]
pub fn detect_steam_path() -> String {
    detect_steam_path_checked().unwrap_or_else(|| {
        let home = std::env::var("HOME").unwrap_or_default();
        format!("{}/.steam/steam", home)
    })
}

/// Download a file from URL to the specified path
pub fn download_file(url: &str, path: &Path) -> Result<(), Box<dyn Error>> {
    // Ensure parent directory exists
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }

    let resp = ureq::get(url).call()?;
    let mut reader = resp.into_reader();
    let mut file = fs::File::create(path)?;
    std::io::copy(&mut reader, &mut file)?;
    Ok(())
}
