//! Shared utility functions used across the application

use std::error::Error;
use std::fs;
use std::path::Path;

/// Detect the Steam installation path
/// Checks common locations for both native and Flatpak Steam installs
pub fn detect_steam_path() -> String {
    let home = std::env::var("HOME").unwrap_or_default();

    // Check native Steam locations in order of preference
    let native_paths = [
        format!("{}/.steam/steam", home),
        format!("{}/.local/share/Steam", home),
    ];

    for path in &native_paths {
        if Path::new(path).exists() {
            return path.clone();
        }
    }

    // Check Flatpak Steam location
    let flatpak_path = format!("{}/.var/app/com.valvesoftware.Steam/.steam/steam", home);
    if Path::new(&flatpak_path).exists() {
        return flatpak_path;
    }

    // Fallback to default
    native_paths[0].clone()
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
