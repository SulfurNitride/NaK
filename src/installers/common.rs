//! Common installer utilities shared between MO2 and Vortex
//!
//! This module contains shared logic to reduce code duplication between
//! the MO2 and Vortex installers.

use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use crate::game_finder::detect_all_games;
use crate::logging::{log_error, log_install, log_warning};

use super::symlinks::{create_game_symlinks, create_nak_tools_symlinks, ensure_temp_directory};
use super::TaskContext;

// Re-export ManagerType from config for use in other installer modules
pub use crate::config::ManagerType;

// ============================================================================
// DXVK Configuration
// ============================================================================

/// URL to the latest dxvk.conf template from the DXVK repository
const DXVK_CONF_URL: &str = "https://raw.githubusercontent.com/doitsujin/dxvk/master/dxvk.conf";

/// Custom DXVK settings to append to the config file
const DXVK_CUSTOM_SETTINGS: &str = r#"
# =============================================================================
# NaK Custom Settings
# =============================================================================

# Disable Graphics Pipeline Library (can cause issues with modded games)
dxvk.enableGraphicsPipelineLibrary = False
"#;

/// Download dxvk.conf from GitHub and append custom settings
/// Returns the path to the created config file
pub fn download_and_create_dxvk_conf(install_dir: &Path) -> Result<PathBuf, Box<dyn std::error::Error>> {
    let tools_dir = install_dir.join("NaK Tools");
    fs::create_dir_all(&tools_dir)?;

    let dxvk_conf_path = tools_dir.join("dxvk.conf");

    // Try to download the latest dxvk.conf from GitHub
    let base_config = match download_dxvk_conf_template() {
        Ok(content) => {
            log_install("Downloaded latest dxvk.conf from DXVK repository");
            content
        }
        Err(e) => {
            log_warning(&format!("Could not download dxvk.conf: {}. Using minimal config.", e));
            // Fallback minimal config
            "# DXVK Configuration File\n# See https://github.com/doitsujin/dxvk for all options\n".to_string()
        }
    };

    // Append our custom settings
    let full_config = format!("{}\n{}", base_config, DXVK_CUSTOM_SETTINGS);

    // Write to file
    fs::write(&dxvk_conf_path, full_config)?;
    log_install(&format!("Created dxvk.conf at {:?}", dxvk_conf_path));

    Ok(dxvk_conf_path)
}

/// Download the dxvk.conf template from GitHub
fn download_dxvk_conf_template() -> Result<String, Box<dyn std::error::Error>> {
    use std::io::Read;
    use std::time::Duration;

    let agent = ureq::AgentBuilder::new()
        .timeout_read(Duration::from_secs(30))
        .timeout_write(Duration::from_secs(10))
        .build();

    let response = agent.get(DXVK_CONF_URL).call()?;

    let mut content = String::new();
    response.into_reader().take(512 * 1024).read_to_string(&mut content)?; // Max 512KB

    Ok(content)
}

/// Get the path where dxvk.conf will be created (for use before actual creation)
pub fn get_dxvk_conf_path(install_dir: &Path) -> PathBuf {
    install_dir.join("NaK Tools").join("dxvk.conf")
}

// ============================================================================
// Shared Installation Errors
// ============================================================================

/// Custom error type for installation operations
#[derive(Debug)]
pub enum InstallError {
    /// User cancelled the operation
    Cancelled,
    /// Executable not found at expected path
    ExeNotFound { exe_name: String, path: String },
    /// Failed to create directory
    DirectoryCreation { path: String, reason: String },
    /// Insufficient disk space
    InsufficientDiskSpace { required_gb: f64, available_gb: f64 },
    /// Steam integration error
    SteamError { reason: String },
    /// Generic error with context
    Other { context: String, reason: String },
}

impl std::fmt::Display for InstallError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            InstallError::Cancelled => write!(f, "Installation cancelled by user"),
            InstallError::ExeNotFound { exe_name, path } => {
                write!(f, "{} not found at path: {}", exe_name, path)
            }
            InstallError::DirectoryCreation { path, reason } => {
                write!(f, "Failed to create directory '{}': {}", path, reason)
            }
            InstallError::InsufficientDiskSpace { required_gb, available_gb } => {
                write!(
                    f,
                    "Insufficient disk space: {:.1}GB required, {:.1}GB available",
                    required_gb, available_gb
                )
            }
            InstallError::SteamError { reason } => {
                write!(f, "Steam integration error: {}", reason)
            }
            InstallError::Other { context, reason } => {
                write!(f, "{}: {}", context, reason)
            }
        }
    }
}

impl std::error::Error for InstallError {}

// ============================================================================
// Post-Installation Setup (Steam-native)
// ============================================================================

/// Performs all post-installation setup tasks for Steam-native integration:
/// - Creates game folders in the prefix
/// - Sets up MO2 Global Instance support (if MO2)
/// - Creates NaK Tools folder with utilities
pub fn finalize_steam_installation_with_tools(
    manager_type: ManagerType,
    prefix_path: &Path,
    install_dir: &Path,
    app_id: u32,
    proton_path: &Path,
    ctx: &TaskContext,
) -> Result<(), InstallError> {
    if ctx.is_cancelled() {
        return Err(InstallError::Cancelled);
    }

    ctx.set_status("Finalizing installation...".to_string());

    // Manager-specific setup
    if manager_type == ManagerType::MO2 {
        setup_mo2_global_instance(prefix_path, install_dir);
    }

    // Create NaK Tools folder with utilities (only if we have a valid app_id)
    // This also handles game symlinks and folder creation via game_finder
    if app_id > 0 {
        ctx.set_status("Creating NaK Tools folder...".to_string());
        if let Err(e) = create_nak_tools_folder(manager_type, install_dir, prefix_path, app_id, proton_path) {
            log_warning(&format!("Failed to create NaK Tools folder: {}", e));
            // Non-fatal - continue with installation
        }
    }

    log_install(&format!(
        "{} installation finalized (Steam-native)",
        manager_type.display_name()
    ));

    Ok(())
}

// ============================================================================
// MO2-Specific Setup
// ============================================================================

/// Sets up the symlink for MO2 Global Instance support.
/// Symlinks `.../pfx/drive_c/users/<user>/AppData/Local/ModOrganizer` -> `install_dir/Global Instance`
fn setup_mo2_global_instance(prefix_path: &Path, install_dir: &Path) {
    let users_dir = prefix_path.join("drive_c/users");
    let username = find_prefix_username(&users_dir);

    let appdata_local = users_dir.join(&username).join("AppData/Local");
    let mo2_global_path = appdata_local.join("ModOrganizer");
    let target_global_instance = install_dir.join("Global Instance");

    // 1. Ensure target "Global Instance" folder exists
    if !target_global_instance.exists() {
        if let Err(e) = fs::create_dir_all(&target_global_instance) {
            log_error(&format!("Failed to create Global Instance folder: {}", e));
            return;
        }
    }

    // 2. Ensure AppData/Local exists in prefix
    if !appdata_local.exists() {
        if let Err(e) = fs::create_dir_all(&appdata_local) {
            log_error(&format!("Failed to create AppData/Local in prefix: {}", e));
            return;
        }
    }

    // 3. Create symlink
    if mo2_global_path.exists() || fs::symlink_metadata(&mo2_global_path).is_ok() {
        let _ = fs::remove_dir_all(&mo2_global_path);
        let _ = fs::remove_file(&mo2_global_path);
    }

    if let Err(e) = std::os::unix::fs::symlink(&target_global_instance, &mo2_global_path) {
        log_error(&format!("Failed to create Global Instance symlink: {}", e));
    } else {
        log_install("Enabled Global Instance support (symlinked AppData/Local/ModOrganizer)");
    }
}

/// Find the username from a Wine prefix users directory
fn find_prefix_username(users_dir: &Path) -> String {
    if let Ok(entries) = fs::read_dir(users_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name != "Public" && name != "root" {
                return name;
            }
        }
    }
    "steamuser".to_string()
}

// ============================================================================
// Disk Space Validation
// ============================================================================

/// Minimum required disk space for a full installation (in GB)
pub const MIN_REQUIRED_DISK_SPACE_GB: f64 = 5.0;

/// Get available disk space at the given path (in GB).
pub fn get_available_disk_space(path: &Path) -> Option<f64> {
    use std::process::Command;

    let output = Command::new("df")
        .arg("-BG")
        .arg(path)
        .output()
        .ok()?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    for line in stdout.lines().skip(1) {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() >= 4 {
            let available_str = parts[3].trim_end_matches('G');
            if let Ok(available) = available_str.parse::<f64>() {
                return Some(available);
            }
        }
    }
    None
}

/// Check if there's sufficient disk space at the given path.
pub fn check_disk_space(path: &Path, required_gb: f64) -> Result<f64, InstallError> {
    match get_available_disk_space(path) {
        Some(available) => {
            if available < required_gb {
                Err(InstallError::InsufficientDiskSpace {
                    required_gb,
                    available_gb: available,
                })
            } else {
                Ok(available)
            }
        }
        None => {
            log_warning("Could not check disk space - df command failed");
            Ok(required_gb)
        }
    }
}

// ============================================================================
// Cancellation Helper
// ============================================================================

/// Check if the task has been cancelled and return an error if so.
#[inline]
pub fn check_cancelled(ctx: &TaskContext) -> Result<(), InstallError> {
    if ctx.is_cancelled() {
        Err(InstallError::Cancelled)
    } else {
        Ok(())
    }
}

// ============================================================================
// NaK Tools Creation (Steam-native)
// ============================================================================

/// Creates NaK utility scripts in the mod manager installation directory.
/// Scripts are placed directly in the root folder alongside the mod manager executable.
/// The NaK Tools subfolder contains the Wine Prefix symlink.
///
/// Uses the new GameFinder-style approach:
/// - Detects games from all supported launchers (Steam, Heroic, Bottles)
/// - Creates symlinks FROM NaK prefix TO game prefixes (data stays in game prefix)
/// - Only creates essential directories (Temp)
pub fn create_nak_tools_folder(
    manager_type: ManagerType,
    install_dir: &Path,
    prefix_path: &Path,
    app_id: u32,
    proton_path: &Path,
) -> Result<(), InstallError> {
    let manager_name = manager_type.display_name();

    // Create NaK Tools subfolder for Wine Prefix symlink and other resources
    let tools_dir = install_dir.join("NaK Tools");
    fs::create_dir_all(&tools_dir).map_err(|e| InstallError::DirectoryCreation {
        path: tools_dir.display().to_string(),
        reason: e.to_string(),
    })?;

    // 1. Create prefix symlink in NaK Tools folder
    let prefix_link = tools_dir.join("Wine Prefix");
    if prefix_link.exists() || fs::symlink_metadata(&prefix_link).is_ok() {
        let _ = fs::remove_file(&prefix_link);
    }
    if let Err(e) = std::os::unix::fs::symlink(prefix_path, &prefix_link) {
        log_warning(&format!("Failed to create prefix symlink: {}", e));
    } else {
        log_install("Created Wine Prefix symlink");
    }

    // 2. Detect all games using the game_finder module
    let scan_result = detect_all_games();
    log_install(&format!(
        "Detected {} games (Steam: {}, Heroic: {}, Bottles: {})",
        scan_result.games.len(),
        scan_result.steam_count,
        scan_result.heroic_count,
        scan_result.bottles_count
    ));

    // 3. Create symlinks from NaK prefix to game prefixes
    // This inverts the symlink direction: NaK prefix -> game prefix
    // Data stays in the game prefix (preserving Steam Cloud sync)
    create_game_symlinks(prefix_path, &scan_result.games);

    // 4. Ensure only essential directories exist (Temp required by MO2)
    ensure_temp_directory(prefix_path);

    // 5. Create NaK Tools convenience symlinks pointing INTO the prefix
    // These provide easy access to prefix folders from NaK Tools:
    // - Prefix Documents -> prefix/Documents
    // - Prefix AppData Local -> prefix/AppData/Local
    // - Prefix AppData Roaming -> prefix/AppData/Roaming
    create_nak_tools_symlinks(&tools_dir, prefix_path);

    // === All scripts and configs go in NaK Tools folder ===

    // 6. Download and create dxvk.conf (non-fatal if download fails)
    if let Err(e) = download_and_create_dxvk_conf(install_dir) {
        log_warning(&format!("Could not create dxvk.conf: {}", e));
    }

    // 7. Create Launch script
    let launch_script = generate_steam_launch_script(app_id, manager_name);
    write_script(&tools_dir.join(format!("Launch {}.sh", manager_name)), &launch_script)?;
    log_install(&format!("Created Launch {} script", manager_name));

    // 8. Create NXM Toggle script
    let nxm_script = generate_nxm_toggle_script(app_id, manager_name, install_dir, prefix_path, proton_path);
    write_script(&tools_dir.join("NXM Toggle.sh"), &nxm_script)?;
    log_install("Created NXM Toggle script");

    // 9. Create Fix Game Registry script
    let registry_script = generate_fix_registry_script(manager_name, prefix_path, proton_path);
    write_script(&tools_dir.join("Fix Game Registry.sh"), &registry_script)?;
    log_install("Created Fix Game Registry script");

    // 10. Create Import Saves script (for manual import of non-Steam games)
    let import_script = generate_import_saves_script(prefix_path);
    write_script(&tools_dir.join("Import Saves.sh"), &import_script)?;
    log_install("Created Import Saves script");

    // 11. Create Winetricks GUI script
    let winetricks_script = generate_winetricks_gui_script(prefix_path);
    write_script(&tools_dir.join("Winetricks.sh"), &winetricks_script)?;
    log_install("Created Winetricks GUI script");

    log_install(&format!("NaK Tools created in {:?}", install_dir));
    Ok(())
}

/// Regenerate NaK Tools scripts for an existing instance.
/// This updates the Wine Prefix symlink and all scripts without touching
/// the folder structure (Prefix Documents, Vortex Data, etc.)
///
/// Used when NaK is updated to refresh scripts with bug fixes/improvements.
pub fn regenerate_nak_tools_scripts(
    manager_type: ManagerType,
    install_dir: &Path,
    prefix_path: &Path,
    app_id: u32,
    proton_path: &Path,
) -> Result<(), InstallError> {
    let manager_name = manager_type.display_name();
    let tools_dir = install_dir.join("NaK Tools");

    // Ensure NaK Tools folder exists
    if !tools_dir.exists() {
        return Err(InstallError::DirectoryCreation {
            path: tools_dir.display().to_string(),
            reason: "NaK Tools folder does not exist".to_string(),
        });
    }

    log_install(&format!("Regenerating scripts for {} instance...", manager_name));

    // 1. Update Wine Prefix symlink (in case prefix was moved)
    let prefix_link = tools_dir.join("Wine Prefix");
    if prefix_link.exists() || fs::symlink_metadata(&prefix_link).is_ok() {
        let _ = fs::remove_file(&prefix_link);
    }
    if let Err(e) = std::os::unix::fs::symlink(prefix_path, &prefix_link) {
        log_warning(&format!("Failed to update prefix symlink: {}", e));
    } else {
        log_install("Updated Wine Prefix symlink");
    }

    // 2. Regenerate Launch script
    let launch_script = generate_steam_launch_script(app_id, manager_name);
    write_script(&tools_dir.join(format!("Launch {}.sh", manager_name)), &launch_script)?;
    log_install(&format!("Regenerated Launch {} script", manager_name));

    // 3. Regenerate NXM Toggle script
    let nxm_script = generate_nxm_toggle_script(app_id, manager_name, install_dir, prefix_path, proton_path);
    write_script(&tools_dir.join("NXM Toggle.sh"), &nxm_script)?;
    log_install("Regenerated NXM Toggle script");

    // 4. Regenerate Fix Game Registry script
    let registry_script = generate_fix_registry_script(manager_name, prefix_path, proton_path);
    write_script(&tools_dir.join("Fix Game Registry.sh"), &registry_script)?;
    log_install("Regenerated Fix Game Registry script");

    // 5. Regenerate Import Saves script
    let import_script = generate_import_saves_script(prefix_path);
    write_script(&tools_dir.join("Import Saves.sh"), &import_script)?;
    log_install("Regenerated Import Saves script");

    // 6. Regenerate Winetricks GUI script
    let winetricks_script = generate_winetricks_gui_script(prefix_path);
    write_script(&tools_dir.join("Winetricks.sh"), &winetricks_script)?;
    log_install("Regenerated Winetricks GUI script");

    log_install(&format!("NaK Tools scripts regenerated for {:?}", install_dir));
    Ok(())
}

/// Write a script file with executable permissions
fn write_script(path: &Path, content: &str) -> Result<(), InstallError> {
    let mut file = fs::File::create(path).map_err(|e| InstallError::Other {
        context: "Script creation".to_string(),
        reason: e.to_string(),
    })?;

    file.write_all(content.as_bytes()).map_err(|e| InstallError::Other {
        context: "Script writing".to_string(),
        reason: e.to_string(),
    })?;

    let mut perms = fs::metadata(path).map_err(|e| InstallError::Other {
        context: "Script permissions".to_string(),
        reason: e.to_string(),
    })?.permissions();
    perms.set_mode(0o755);
    fs::set_permissions(path, perms).map_err(|e| InstallError::Other {
        context: "Script permissions".to_string(),
        reason: e.to_string(),
    })?;

    Ok(())
}

/// Generate Fix Game Registry script for Steam-native installs
fn generate_fix_registry_script(manager_name: &str, prefix_path: &Path, proton_path: &Path) -> String {
    // Normalize paths for Bazzite/Fedora Atomic compatibility
    let prefix_str = crate::config::normalize_path_for_steam(&prefix_path.to_string_lossy());
    let proton_str = crate::config::normalize_path_for_steam(&proton_path.to_string_lossy());

    include_str!("../scripts/fix_registry.sh")
        .replace("{{MANAGER_NAME}}", manager_name)
        .replace("{{PREFIX_PATH}}", &prefix_str)
        .replace("{{PROTON_PATH}}", &proton_str)
}

/// Generate NXM Toggle script
fn generate_nxm_toggle_script(app_id: u32, manager_name: &str, install_dir: &Path, prefix_path: &Path, proton_path: &Path) -> String {
    // Normalize paths for Bazzite/Fedora Atomic compatibility
    // On these systems, $HOME is /var/home/user but pressure-vessel exposes /home
    let install_str = crate::config::normalize_path_for_steam(&install_dir.to_string_lossy());
    let prefix_str = crate::config::normalize_path_for_steam(&prefix_path.to_string_lossy());
    let proton_str = crate::config::normalize_path_for_steam(&proton_path.to_string_lossy());

    // NXM handler exe path
    let nxm_exe = format!("{}/nxmhandler.exe", install_str);

    include_str!("../scripts/nxm_toggle.sh")
        .replace("{{APP_ID}}", &app_id.to_string())
        .replace("{{MANAGER_NAME}}", manager_name)
        .replace("{{NXM_EXE}}", &nxm_exe)
        .replace("{{PREFIX_PATH}}", &prefix_str)
        .replace("{{PROTON_PATH}}", &proton_str)
}

/// Generate Steam launch script (for manual use outside Steam)
fn generate_steam_launch_script(app_id: u32, manager_name: &str) -> String {
    // Convert 32-bit AppID to 64-bit Game ID (required for non-Steam shortcuts)
    // Formula: (appid << 32) | 0x02000000
    let game_id: u64 = ((app_id as u64) << 32) | 0x02000000;

    include_str!("../scripts/steam_launch.sh")
        .replace("{{MANAGER_NAME}}", manager_name)
        .replace("{{GAME_ID}}", &game_id.to_string())
}

/// Generate Import Saves script
fn generate_import_saves_script(prefix_path: &Path) -> String {
    // Normalize paths for Bazzite/Fedora Atomic compatibility
    let prefix_str = crate::config::normalize_path_for_steam(&prefix_path.to_string_lossy());

    include_str!("../scripts/import_saves.sh")
        .replace("{{PREFIX_PATH}}", &prefix_str)
}

/// Generate Winetricks GUI script for Steam-native installs
fn generate_winetricks_gui_script(prefix_path: &Path) -> String {
    // Normalize paths for Bazzite/Fedora Atomic compatibility
    let prefix_str = crate::config::normalize_path_for_steam(&prefix_path.to_string_lossy());

    include_str!("../scripts/winetricks.sh")
        .replace("{{PREFIX_PATH}}", &prefix_str)
}

