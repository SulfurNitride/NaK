//! Mod Organizer 2 installation (Steam-native)

use std::error::Error;
use std::fs;
use std::path::PathBuf;

use super::common::{check_cancelled, check_disk_space, finalize_steam_installation_with_tools, get_dxvk_conf_path, InstallError, ManagerType};
use super::{fetch_latest_mo2_release, install_all_dependencies, TaskContext};
use crate::config::{AppConfig, ManagedPrefixes};
use crate::logging::{log_download, log_error, log_install};
use crate::steam::{self, SteamProton};
use crate::utils::download_file;

/// Minimum disk space required for MO2 installation (in GB)
const MIN_DISK_SPACE_GB: f64 = 5.0;

/// NaK Steam integration config file name
const NAK_STEAM_CONFIG: &str = ".nak_steam.json";

/// Save the Steam integration config to the install directory
fn save_steam_config(install_path: &std::path::Path, app_id: u32) -> Result<(), Box<dyn Error>> {
    let config_path = install_path.join(NAK_STEAM_CONFIG);
    let config = serde_json::json!({
        "steam_app_id": app_id,
        "created": chrono::Utc::now().to_rfc3339(),
    });
    std::fs::write(&config_path, serde_json::to_string_pretty(&config)?)?;
    log_install(&format!("Saved Steam config to {:?}", config_path));
    Ok(())
}

/// Result of MO2 installation
pub struct Mo2InstallResult {
    /// Steam AppID for the shortcut
    pub app_id: u32,
    /// Path to the Wine prefix
    pub prefix_path: PathBuf,
}

/// Install MO2 using Steam-native integration
///
/// This creates a Steam shortcut for MO2, sets up the prefix in Steam's
/// compatdata directory, and configures the Proton version.
pub fn install_mo2(
    install_name: &str,
    install_path: PathBuf,
    proton: &SteamProton,
    ctx: TaskContext,
    skip_disk_check: bool,
) -> Result<Mo2InstallResult, Box<dyn Error>> {
    log_install(&format!(
        "Starting MO2 installation: {} -> {:?}",
        install_name, install_path
    ));
    log_install(&format!("Using Proton: {} (Steam-native)", proton.name));

    // Get primary Steam path (where prefixes are always created)
    let steam_path = steam::find_steam_path()
        .ok_or_else(|| InstallError::SteamError { reason: "Steam not found".to_string() })?;

    // Check disk space on primary Steam installation
    if !skip_disk_check {
        if let Err(e) = check_disk_space(&steam_path, MIN_DISK_SPACE_GB) {
            log_error(&format!("Disk space check failed: {}", e));
            return Err(e.into());
        }
    }

    check_cancelled(&ctx)?;

    // 1. Create Steam shortcut first (this determines the prefix location)
    ctx.set_status("Creating Steam shortcut...".to_string());
    ctx.set_progress(0.05);

    let exe_path = install_path.join("ModOrganizer.exe");
    let dxvk_conf_path = get_dxvk_conf_path(&install_path);
    let steam_result = steam::add_mod_manager_shortcut(
        install_name,
        exe_path.to_str().unwrap_or(""),
        install_path.to_str().unwrap_or(""),
        &proton.config_name,
        Some(&dxvk_conf_path),
    ).map_err(|e| InstallError::SteamError { reason: e.to_string() })?;

    log_install(&format!(
        "Created Steam shortcut with AppID: {}",
        steam_result.app_id
    ));
    log_install(&format!(
        "Prefix will be at: {:?}",
        steam_result.prefix_path
    ));

    check_cancelled(&ctx)?;

    // 2. Create install directory
    ctx.set_status("Creating directories...".to_string());
    ctx.set_progress(0.08);

    fs::create_dir_all(&install_path).map_err(|e| InstallError::DirectoryCreation {
        path: install_path.display().to_string(),
        reason: e.to_string(),
    })?;

    check_cancelled(&ctx)?;

    // 3. Download MO2
    ctx.set_status("Fetching MO2 release info...".to_string());
    let release = fetch_latest_mo2_release()?;

    let invalid_terms = ["Linux", "pdbs", "src", "uibase", "commits"];
    let asset = release
        .assets
        .iter()
        .find(|a| {
            a.name.starts_with("Mod.Organizer-2")
                && a.name.ends_with(".7z")
                && !invalid_terms.iter().any(|term| a.name.contains(term))
        })
        .ok_or_else(|| InstallError::Other {
            context: "MO2 download".to_string(),
            reason: "No valid MO2 archive found in release".to_string(),
        })?;

    ctx.set_status(format!("Downloading {}...", asset.name));
    ctx.set_progress(0.10);
    log_download(&format!("Downloading MO2: {}", asset.name));

    let tmp_dir = AppConfig::get_tmp_path();
    fs::create_dir_all(&tmp_dir)?;
    let archive_path = tmp_dir.join(&asset.name);
    download_file(&asset.browser_download_url, &archive_path)?;
    log_download(&format!("MO2 downloaded to: {:?}", archive_path));

    check_cancelled(&ctx)?;

    // 4. Extract
    ctx.set_status("Extracting MO2...".to_string());
    ctx.set_progress(0.15);

    if let Err(e) = sevenz_rust::decompress_file(&archive_path, &install_path) {
        log_error(&format!("Failed to extract MO2 archive: {}", e));
        return Err(InstallError::Other {
            context: "MO2 extraction".to_string(),
            reason: e.to_string(),
        }
        .into());
    }

    // Clean up archive
    let _ = fs::remove_file(&archive_path);

    ctx.set_progress(0.20);

    // 5. Verify executable exists
    if !exe_path.exists() {
        log_error("ModOrganizer.exe not found after extraction");
        return Err(InstallError::ExeNotFound {
            exe_name: "ModOrganizer.exe".to_string(),
            path: install_path.display().to_string(),
        }
        .into());
    }

    check_cancelled(&ctx)?;

    // 6. Initialize prefix and install dependencies
    install_all_dependencies(&steam_result.prefix_path, proton, &ctx, 0.20, 0.90)?;

    ctx.set_progress(0.92);

    check_cancelled(&ctx)?;

    // 7. Finalize installation (creates NaK Tools folder)
    finalize_steam_installation_with_tools(
        ManagerType::MO2,
        &steam_result.prefix_path,
        &install_path,
        steam_result.app_id,
        &proton.path,
        &ctx,
    )?;

    // 8. Save Steam integration config
    if let Err(e) = save_steam_config(&install_path, steam_result.app_id) {
        log_error(&format!("Warning: Failed to save Steam config: {}", e));
    }

    // 9. Register prefix for cleanup tracking
    ManagedPrefixes::register(
        steam_result.app_id,
        install_name,
        steam_result.prefix_path.to_str().unwrap_or(""),
        install_path.to_str().unwrap_or(""),
        crate::config::ManagerType::MO2,
        steam_path.to_str().unwrap_or(""),
        Some(&proton.config_name),
    );
    log_install("Registered prefix for cleanup tracking");

    ctx.set_progress(1.0);
    ctx.set_status("MO2 Installed! Restart Steam to see it.".to_string());
    log_install(&format!("MO2 installation complete: {}", install_name));

    Ok(Mo2InstallResult {
        app_id: steam_result.app_id,
        prefix_path: steam_result.prefix_path,
    })
}

/// Setup an existing MO2 installation with Steam integration
pub fn setup_existing_mo2(
    install_name: &str,
    existing_path: PathBuf,
    proton: &SteamProton,
    ctx: TaskContext,
) -> Result<Mo2InstallResult, Box<dyn Error>> {
    // Verify MO2 exists at path
    let mo2_exe = existing_path.join("ModOrganizer.exe");
    if !mo2_exe.exists() {
        log_error("ModOrganizer.exe not found at selected path");
        return Err(InstallError::ExeNotFound {
            exe_name: "ModOrganizer.exe".to_string(),
            path: existing_path.display().to_string(),
        }
        .into());
    }

    log_install(&format!(
        "Setting up existing MO2: {} at {:?}",
        install_name, existing_path
    ));
    log_install(&format!("Using Proton: {} (Steam-native)", proton.name));

    // Get primary Steam path (where prefixes are always created)
    let steam_path = steam::find_steam_path()
        .ok_or_else(|| InstallError::SteamError { reason: "Steam not found".to_string() })?;

    check_cancelled(&ctx)?;

    // 1. Create Steam shortcut
    ctx.set_status("Creating Steam shortcut...".to_string());
    ctx.set_progress(0.05);

    let dxvk_conf_path = get_dxvk_conf_path(&existing_path);
    let steam_result = steam::add_mod_manager_shortcut(
        install_name,
        mo2_exe.to_str().unwrap_or(""),
        existing_path.to_str().unwrap_or(""),
        &proton.config_name,
        Some(&dxvk_conf_path),
    ).map_err(|e| InstallError::SteamError { reason: e.to_string() })?;

    log_install(&format!(
        "Created Steam shortcut with AppID: {}",
        steam_result.app_id
    ));

    check_cancelled(&ctx)?;

    // 2. Install dependencies
    install_all_dependencies(&steam_result.prefix_path, proton, &ctx, 0.10, 0.85)?;

    ctx.set_progress(0.90);

    check_cancelled(&ctx)?;

    // 3. Finalize (creates NaK Tools folder)
    finalize_steam_installation_with_tools(
        ManagerType::MO2,
        &steam_result.prefix_path,
        &existing_path,
        steam_result.app_id,
        &proton.path,
        &ctx,
    )?;

    // 4. Save Steam integration config
    if let Err(e) = save_steam_config(&existing_path, steam_result.app_id) {
        log_error(&format!("Warning: Failed to save Steam config: {}", e));
    }

    // 5. Register prefix for cleanup tracking
    ManagedPrefixes::register(
        steam_result.app_id,
        install_name,
        steam_result.prefix_path.to_str().unwrap_or(""),
        existing_path.to_str().unwrap_or(""),
        crate::config::ManagerType::MO2,
        steam_path.to_str().unwrap_or(""),
        Some(&proton.config_name),
    );
    log_install("Registered prefix for cleanup tracking");

    ctx.set_progress(1.0);
    ctx.set_status("MO2 Setup Complete! Restart Steam to see it.".to_string());
    log_install(&format!("MO2 setup complete: {}", install_name));

    Ok(Mo2InstallResult {
        app_id: steam_result.app_id,
        prefix_path: steam_result.prefix_path,
    })
}
