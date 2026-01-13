//! Steam path detection utilities
//!
//! Provides functions to locate Steam installation directories,
//! user data paths, and related filesystem operations.

use std::fs;
use std::path::PathBuf;

use crate::logging::{log_info, log_warning};

// ============================================================================
// Core Path Detection
// ============================================================================

/// Find the Steam installation path.
///
/// Checks common locations for native, Flatpak, and Snap Steam installs.
/// Returns `None` if Steam is not found.
#[must_use]
pub fn find_steam_path() -> Option<PathBuf> {
    let home = std::env::var("HOME").ok()?;

    let steam_paths = [
        format!("{}/.steam/steam", home),
        format!("{}/.local/share/Steam", home),
        format!("{}/.var/app/com.valvesoftware.Steam/.steam/steam", home),
        format!("{}/snap/steam/common/.steam/steam", home),
    ];

    steam_paths
        .iter()
        .map(PathBuf::from)
        .find(|p| p.exists())
}

/// Find the Steam userdata directory (most recently used user).
///
/// Returns the path to the most recently modified user's config directory,
/// which is typically the active Steam user.
#[must_use]
pub fn find_userdata_path() -> Option<PathBuf> {
    let steam_path = find_steam_path()?;
    let userdata = steam_path.join("userdata");

    if !userdata.exists() {
        return None;
    }

    // Get all user directories and find the most recently modified
    let mut user_dirs: Vec<PathBuf> = Vec::new();

    if let Ok(entries) = fs::read_dir(&userdata) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                // Check if it's a numeric user ID directory
                if let Some(name) = path.file_name() {
                    if name.to_string_lossy().chars().all(|c| c.is_ascii_digit()) {
                        user_dirs.push(path);
                    }
                }
            }
        }
    }

    // Sort by modification time (most recent first)
    user_dirs.sort_by(|a, b| {
        let a_time = fs::metadata(a).and_then(|m| m.modified()).ok();
        let b_time = fs::metadata(b).and_then(|m| m.modified()).ok();
        b_time.cmp(&a_time)
    });

    user_dirs.into_iter().next()
}

// ============================================================================
// Convenience Wrappers (for backwards compatibility)
// ============================================================================

/// Detect the Steam installation path with logging.
///
/// Use this at startup to log whether Steam was found.
/// Returns `None` if Steam is not found.
#[must_use]
pub fn detect_steam_path_checked() -> Option<String> {
    match find_steam_path() {
        Some(path) => {
            let path_str = path.to_string_lossy().to_string();
            log_info(&format!("Steam detected at: {}", path_str));
            Some(path_str)
        }
        None => {
            log_warning("Steam installation not detected! NaK requires Steam to be installed.");
            None
        }
    }
}

/// Detect the Steam installation path (always returns a path).
///
/// Returns the detected Steam path, or a fallback default path if not found.
/// Does not log. Use this when you need a path and can handle a possibly
/// non-existent location.
#[must_use]
pub fn detect_steam_path() -> String {
    find_steam_path()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|| {
            let home = std::env::var("HOME").unwrap_or_default();
            format!("{}/.steam/steam", home)
        })
}
