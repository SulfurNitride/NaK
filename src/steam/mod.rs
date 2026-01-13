//! Steam integration module
//!
//! Handles Steam shortcut creation, Proton compatibility settings,
//! library folder detection, and NXM handler integration.

mod config;
mod paths;
mod proton;
mod shortcuts;

// Re-export path detection utilities
pub use paths::{detect_steam_path, detect_steam_path_checked, find_steam_path, find_userdata_path};

// Re-export Steam integration components
pub use config::set_compat_tool;
pub use proton::{find_steam_protons, SteamProton};
pub use shortcuts::{Shortcut, ShortcutsVdf};

use std::fs;
use std::path::PathBuf;

/// Kill Steam process gracefully, then force if needed
pub fn kill_steam() -> Result<(), Box<dyn std::error::Error>> {
    use std::process::Command;

    // Try steam -shutdown first (graceful)
    let _ = Command::new("steam")
        .arg("-shutdown")
        .status();

    std::thread::sleep(std::time::Duration::from_secs(2));

    // Then force kill if still running
    let _ = Command::new("pkill")
        .arg("-9")
        .arg("steam")
        .status();

    // Brief wait for Steam to fully exit
    std::thread::sleep(std::time::Duration::from_secs(2));

    Ok(())
}

/// Start Steam in background
pub fn start_steam() -> Result<(), Box<dyn std::error::Error>> {
    use std::process::{Command, Stdio};

    // Use setsid to detach Steam from our process
    Command::new("setsid")
        .arg("steam")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?;

    Ok(())
}

/// Restart Steam (kill then start)
pub fn restart_steam() -> Result<(), Box<dyn std::error::Error>> {
    kill_steam()?;
    start_steam()?;
    Ok(())
}

// ============================================================================
// STEAM_COMPAT_MOUNTS Detection
// ============================================================================

/// Directories that pressure-vessel already exposes by default
const ALREADY_EXPOSED: &[&str] = &[
    "bin", "etc", "home", "lib", "lib32", "lib64",
    "overrides", "run", "sbin", "tmp", "usr", "var",
];

/// System directories that shouldn't be mounted
const SYSTEM_DIRS: &[&str] = &[
    "proc", "sys", "dev", "boot", "root", "lost+found", "snap",
];

/// Detect directories at root that need to be added to STEAM_COMPAT_MOUNTS
///
/// This finds any directories in `/` that aren't already exposed by pressure-vessel
/// and aren't system directories, so they can be made available to the container.
pub fn detect_extra_mounts() -> Vec<String> {
    let mut mounts = Vec::new();

    let Ok(entries) = fs::read_dir("/") else {
        return mounts;
    };

    for entry in entries.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();

        // Skip already-exposed directories
        if ALREADY_EXPOSED.contains(&name.as_str()) {
            continue;
        }

        // Skip system directories
        if SYSTEM_DIRS.contains(&name.as_str()) {
            continue;
        }

        // Skip hidden directories
        if name.starts_with('.') {
            continue;
        }

        // Only include actual directories
        if entry.path().is_dir() {
            mounts.push(format!("/{}", name));
        }
    }

    // Sort for consistent output
    mounts.sort();

    mounts
}

/// DXVK configuration to disable Graphics Pipeline Library
/// (can cause issues with modded games)
const DXVK_CONFIG: &str = r#"DXVK_CONFIG="dxvk.enableGraphicsPipelineLibrary = False""#;

/// Generate launch options string with DXVK config and STEAM_COMPAT_MOUNTS
///
/// Returns something like:
/// `DXVK_CONFIG="..." STEAM_COMPAT_MOUNTS=/mnt:/media:/opt %command%`
pub fn generate_launch_options() -> String {
    let mounts = detect_extra_mounts();

    if mounts.is_empty() {
        format!("{} %command%", DXVK_CONFIG)
    } else {
        format!("{} STEAM_COMPAT_MOUNTS={} %command%", DXVK_CONFIG, mounts.join(":"))
    }
}

#[cfg(test)]
mod mount_tests {
    use super::*;

    #[test]
    fn test_detect_extra_mounts() {
        let mounts = detect_extra_mounts();
        println!("Detected extra mounts: {:?}", mounts);

        // These should NOT be in the list (already exposed)
        assert!(!mounts.contains(&"/home".to_string()));
        assert!(!mounts.contains(&"/tmp".to_string()));
        assert!(!mounts.contains(&"/usr".to_string()));
        assert!(!mounts.contains(&"/var".to_string()));

        // These should NOT be in the list (system dirs)
        assert!(!mounts.contains(&"/proc".to_string()));
        assert!(!mounts.contains(&"/sys".to_string()));
        assert!(!mounts.contains(&"/dev".to_string()));
        assert!(!mounts.contains(&"/boot".to_string()));
    }

    #[test]
    fn test_generate_launch_options() {
        let options = generate_launch_options();
        println!("Generated launch options: {}", options);

        // Should always have DXVK_CONFIG and %command%
        assert!(options.contains("DXVK_CONFIG="));
        assert!(options.contains("enableGraphicsPipelineLibrary"));
        assert!(options.ends_with(" %command%"));
    }
}

// ============================================================================
// High-Level API for Mod Manager Integration
// ============================================================================

/// Result of adding a Steam shortcut
#[derive(Debug, Clone)]
pub struct SteamShortcutResult {
    /// The calculated AppID for this shortcut
    pub app_id: u32,
    /// Path to the prefix (in steamapps/compatdata/<appid>/pfx)
    pub prefix_path: PathBuf,
    /// Path to the compat data directory
    pub compat_data_path: PathBuf,
}

/// Add a mod manager as a non-Steam game shortcut
///
/// This is the main function for integrating MO2/Vortex with Steam:
/// 1. Creates/updates the shortcut in shortcuts.vdf
/// 2. Sets the Proton compatibility tool in config.vdf
/// 3. Returns paths for prefix creation
///
/// # Arguments
/// * `name` - Display name in Steam (e.g., "MO2 - Skyrim SE")
/// * `exe_path` - Path to the executable (e.g., "/path/to/ModOrganizer.exe")
/// * `start_dir` - Working directory for the exe
/// * `proton_name` - Proton config name (e.g., "GE-Proton9-20", "proton_experimental")
///
/// # Returns
/// `SteamShortcutResult` with AppID and prefix paths
pub fn add_mod_manager_shortcut(
    name: &str,
    exe_path: &str,
    start_dir: &str,
    proton_name: &str,
) -> Result<SteamShortcutResult, Box<dyn std::error::Error>> {
    // 1. Load existing shortcuts
    let mut vdf = ShortcutsVdf::load()?;

    // 2. Generate launch options with STEAM_COMPAT_MOUNTS
    let launch_options = generate_launch_options();
    if !launch_options.is_empty() {
        crate::logging::log_install(&format!("Setting launch options: {}", launch_options));
    }

    // 3. Create the shortcut
    let shortcut = Shortcut::new(name, exe_path, start_dir)
        .with_tag("NaK")
        .with_launch_options(&launch_options);

    let app_id = shortcut.appid;

    // 4. Add/update in shortcuts.vdf
    vdf.add_shortcut(shortcut);
    vdf.save()?;

    // 5. Set Proton compatibility tool
    set_compat_tool(app_id, proton_name)?;

    // 6. Calculate prefix paths
    // IMPORTANT: Steam creates non-Steam game prefixes in the PRIMARY Steam folder,
    // regardless of where the executable is located. We must match this behavior.
    let primary_steam = find_steam_path()
        .ok_or("Could not find Steam installation")?;
    let compat_data_path = primary_steam
        .join("steamapps/compatdata")
        .join(app_id.to_string());
    let prefix_path = compat_data_path.join("pfx");

    // 7. Ensure compat data directory exists
    fs::create_dir_all(&compat_data_path)?;

    Ok(SteamShortcutResult {
        app_id,
        prefix_path,
        compat_data_path,
    })
}


