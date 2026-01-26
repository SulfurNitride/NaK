//! Vortex installation (Steam-native)

use std::error::Error;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::Duration;
use wait_timeout::ChildExt;

use super::common::{check_cancelled, check_disk_space, finalize_steam_installation_with_tools, get_dxvk_conf_path, InstallError, ManagerType};
use super::{fetch_latest_vortex_release, install_all_dependencies, TaskContext};
use crate::config::{AppConfig, ManagedPrefixes};
use crate::deps::wine_utils::run_protontricks_launch;
use crate::logging::{log_download, log_error, log_install};
use crate::steam::{self, is_flatpak_steam, is_flatpak_protontricks_installed, SteamProton};
use crate::utils::download_file;

/// Minimum disk space required for Vortex installation (in GB)
const MIN_DISK_SPACE_GB: f64 = 5.0;

/// Timeout for Vortex installer (5 minutes)
const INSTALLER_TIMEOUT_SECS: u64 = 300;

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

/// Result of Vortex installation
pub struct VortexInstallResult {
    /// Steam AppID for the shortcut
    pub app_id: u32,
    /// Path to the Wine prefix
    pub prefix_path: PathBuf,
}

/// Install Vortex using Steam-native integration
pub fn install_vortex(
    install_name: &str,
    install_path: PathBuf,
    proton: &SteamProton,
    ctx: TaskContext,
    skip_disk_check: bool,
) -> Result<VortexInstallResult, Box<dyn Error>> {
    log_install(&format!(
        "Starting Vortex installation: {} -> {:?}",
        install_name, install_path
    ));
    log_install(&format!(
        "Using Proton: {} (wine: {})",
        proton.name,
        proton.wine_binary().map(|p| p.display().to_string()).unwrap_or_else(|| "NOT FOUND".to_string())
    ));

    // Get primary Steam path (where prefixes are always created)
    let primary_steam_path = steam::find_steam_path()
        .ok_or_else(|| InstallError::SteamError { reason: "Steam not found".to_string() })?;

    // Check disk space on primary Steam installation
    if !skip_disk_check {
        if let Err(e) = check_disk_space(&primary_steam_path, MIN_DISK_SPACE_GB) {
            log_error(&format!("Disk space check failed: {}", e));
            return Err(e.into());
        }
    }

    check_cancelled(&ctx)?;

    // 1. Create Steam shortcut first (this determines the prefix location)
    ctx.set_status("Creating Steam shortcut...".to_string());
    ctx.set_progress(0.05);

    let exe_path = install_path.join("Vortex.exe");
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

    // 3. Download Vortex
    ctx.set_status("Fetching Vortex release info...".to_string());
    let release = fetch_latest_vortex_release()?;

    ctx.log(format!("Found release: {}", release.tag_name));

    let asset = release.assets.iter().find(|a| {
        let name = a.name.to_lowercase();
        name.starts_with("vortex-setup") && name.ends_with(".exe")
    });

    if asset.is_none() {
        ctx.log("Available assets:".to_string());
        for a in &release.assets {
            ctx.log(format!(" - {}", a.name));
        }
        log_error("No valid Vortex installer found (expected Vortex-setup-*.exe)");
        return Err(InstallError::Other {
            context: "Vortex download".to_string(),
            reason: "No valid Vortex installer found (expected Vortex-setup-*.exe)".to_string(),
        }
        .into());
    }
    let asset = asset.unwrap();

    ctx.set_status(format!("Downloading {}...", asset.name));
    ctx.set_progress(0.10);
    log_download(&format!("Downloading Vortex: {}", asset.name));

    let tmp_dir = AppConfig::get_tmp_path();
    fs::create_dir_all(&tmp_dir)?;
    let installer_path = tmp_dir.join(&asset.name);
    download_file(&asset.browser_download_url, &installer_path)?;
    log_download(&format!("Vortex downloaded to: {:?}", installer_path));

    check_cancelled(&ctx)?;

    // 4. Run Installer using Proton directly
    ctx.set_status("Running Vortex Installer...".to_string());
    ctx.set_progress(0.15);

    let win_install_path = format!("Z:{}", install_path.to_string_lossy().replace("/", "\\"));
    let proton_bin = proton.path.join("proton");

    let steam_path = steam::find_steam_path()
        .ok_or_else(|| InstallError::SteamError { reason: "Steam not found".to_string() })?;

    ctx.log("Running Vortex installer...".to_string());

    // For Flatpak Steam, prefer protontricks-launch if available
    let use_flatpak = is_flatpak_steam();
    let use_protontricks = use_flatpak && is_flatpak_protontricks_installed();

    if use_flatpak {
        if use_protontricks {
            log_install("Flatpak Steam detected - running Vortex installer via protontricks-launch");
        } else {
            log_install("Flatpak Steam detected - running Vortex installer through Flatpak (protontricks recommended)");
        }
    }

    let status = if use_protontricks {
        // Use protontricks-launch for proper sandbox handling
        run_protontricks_launch(
            steam_result.app_id,
            &installer_path,
            &["/S", &format!("/D={}", win_install_path)],
        )?
    } else if use_flatpak {
        // Fallback: run through flatpak bash (less reliable)
        let cmd_str = format!(
            "STEAM_COMPAT_DATA_PATH='{}' STEAM_COMPAT_CLIENT_INSTALL_PATH='{}' '{}' run '{}' /S '/D={}'",
            steam_result.compat_data_path.to_string_lossy(),
            steam_path.to_string_lossy(),
            proton_bin.to_string_lossy(),
            installer_path.to_string_lossy(),
            win_install_path
        );
        let mut child = Command::new("flatpak")
            .arg("run")
            .arg("--filesystem=home")
            .arg("--command=bash")
            .arg("com.valvesoftware.Steam")
            .arg("-c")
            .arg(&cmd_str)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;

        let timeout = Duration::from_secs(INSTALLER_TIMEOUT_SECS);
        match child.wait_timeout(timeout)? {
            Some(status) => status,
            None => {
                let _ = child.kill();
                log_error(&format!(
                    "Vortex installer timed out after {} seconds",
                    INSTALLER_TIMEOUT_SECS
                ));
                return Err(InstallError::Other {
                    context: "Vortex installer".to_string(),
                    reason: format!("Timed out after {} seconds", INSTALLER_TIMEOUT_SECS),
                }
                .into());
            }
        }
    } else {
        // Native Steam - run proton directly
        let mut child = Command::new(&proton_bin)
            .args([
                "run",
                installer_path.to_str().unwrap_or(""),
                "/S",
                &format!("/D={}", win_install_path),
            ])
            .env("STEAM_COMPAT_DATA_PATH", &steam_result.compat_data_path)
            .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;

        let timeout = Duration::from_secs(INSTALLER_TIMEOUT_SECS);
        match child.wait_timeout(timeout)? {
            Some(status) => status,
            None => {
                let _ = child.kill();
                log_error(&format!(
                    "Vortex installer timed out after {} seconds",
                    INSTALLER_TIMEOUT_SECS
                ));
                return Err(InstallError::Other {
                    context: "Vortex installer".to_string(),
                    reason: format!("Timed out after {} seconds", INSTALLER_TIMEOUT_SECS),
                }
                .into());
            }
        }
    };

    if !status.success() {
        ctx.log(format!("Installer exit code: {:?}", status.code()));
        log_error(&format!(
            "Vortex installer failed with exit code: {:?}",
            status.code()
        ));
        return Err(InstallError::Other {
            context: "Vortex installer".to_string(),
            reason: format!("Failed with exit code: {:?}", status.code()),
        }
        .into());
    }

    // Wait for files to settle
    std::thread::sleep(Duration::from_secs(2));

    // Clean up installer
    let _ = fs::remove_file(&installer_path);

    ctx.set_progress(0.20);

    // 5. Find and verify Vortex executable
    let vortex_exe = find_vortex_exe(&install_path)?;
    let actual_install_dir = vortex_exe.parent().unwrap_or(&install_path).to_path_buf();

    check_cancelled(&ctx)?;

    // 6. Install dependencies
    install_all_dependencies(&steam_result.prefix_path, proton, &ctx, 0.20, 0.90, steam_result.app_id)?;

    ctx.set_progress(0.92);

    check_cancelled(&ctx)?;

    // 7. Finalize installation (creates NaK Tools folder)
    finalize_steam_installation_with_tools(
        ManagerType::Vortex,
        &steam_result.prefix_path,
        &actual_install_dir,
        steam_result.app_id,
        &proton.path,
        &ctx,
    )?;

    // 8. Save Steam integration config
    if let Err(e) = save_steam_config(&actual_install_dir, steam_result.app_id) {
        log_error(&format!("Warning: Failed to save Steam config: {}", e));
    }

    // 9. Register prefix for cleanup tracking
    ManagedPrefixes::register(
        steam_result.app_id,
        install_name,
        steam_result.prefix_path.to_str().unwrap_or(""),
        actual_install_dir.to_str().unwrap_or(""),
        crate::config::ManagerType::Vortex,
        primary_steam_path.to_str().unwrap_or(""),
        Some(&proton.config_name),
    );
    log_install("Registered prefix for cleanup tracking");

    ctx.set_progress(1.0);
    ctx.set_status("Vortex Installed! Restart Steam to see it.".to_string());
    log_install(&format!("Vortex installation complete: {}", install_name));

    Ok(VortexInstallResult {
        app_id: steam_result.app_id,
        prefix_path: steam_result.prefix_path,
    })
}

/// Setup an existing Vortex installation with Steam integration
pub fn setup_existing_vortex(
    install_name: &str,
    existing_path: PathBuf,
    proton: &SteamProton,
    ctx: TaskContext,
) -> Result<VortexInstallResult, Box<dyn Error>> {
    // Verify Vortex exists at path
    let vortex_exe = find_vortex_exe(&existing_path)?;
    let actual_install_dir = vortex_exe.parent().unwrap_or(&existing_path).to_path_buf();

    log_install(&format!(
        "Setting up existing Vortex: {} at {:?}",
        install_name, existing_path
    ));
    log_install(&format!(
        "Using Proton: {} (wine: {})",
        proton.name,
        proton.wine_binary().map(|p| p.display().to_string()).unwrap_or_else(|| "NOT FOUND".to_string())
    ));

    // Get primary Steam path (where prefixes are always created)
    let primary_steam_path = steam::find_steam_path()
        .ok_or_else(|| InstallError::SteamError { reason: "Steam not found".to_string() })?;

    check_cancelled(&ctx)?;

    // 1. Create Steam shortcut
    ctx.set_status("Creating Steam shortcut...".to_string());
    ctx.set_progress(0.05);

    let dxvk_conf_path = get_dxvk_conf_path(&actual_install_dir);
    let steam_result = steam::add_mod_manager_shortcut(
        install_name,
        vortex_exe.to_str().unwrap_or(""),
        actual_install_dir.to_str().unwrap_or(""),
        &proton.config_name,
        Some(&dxvk_conf_path),
    ).map_err(|e| InstallError::SteamError { reason: e.to_string() })?;

    log_install(&format!(
        "Created Steam shortcut with AppID: {}",
        steam_result.app_id
    ));

    check_cancelled(&ctx)?;

    // 2. Install dependencies
    install_all_dependencies(&steam_result.prefix_path, proton, &ctx, 0.10, 0.85, steam_result.app_id)?;

    ctx.set_progress(0.90);

    check_cancelled(&ctx)?;

    // 3. Finalize (creates NaK Tools folder)
    finalize_steam_installation_with_tools(
        ManagerType::Vortex,
        &steam_result.prefix_path,
        &actual_install_dir,
        steam_result.app_id,
        &proton.path,
        &ctx,
    )?;

    // 4. Save Steam integration config
    if let Err(e) = save_steam_config(&actual_install_dir, steam_result.app_id) {
        log_error(&format!("Warning: Failed to save Steam config: {}", e));
    }

    // 5. Register prefix for cleanup tracking
    ManagedPrefixes::register(
        steam_result.app_id,
        install_name,
        steam_result.prefix_path.to_str().unwrap_or(""),
        actual_install_dir.to_str().unwrap_or(""),
        crate::config::ManagerType::Vortex,
        primary_steam_path.to_str().unwrap_or(""),
        Some(&proton.config_name),
    );
    log_install("Registered prefix for cleanup tracking");

    ctx.set_progress(1.0);
    ctx.set_status("Vortex Setup Complete! Restart Steam to see it.".to_string());
    log_install(&format!("Vortex setup complete: {}", install_name));

    Ok(VortexInstallResult {
        app_id: steam_result.app_id,
        prefix_path: steam_result.prefix_path,
    })
}

/// Find Vortex.exe in the install directory (handles subdirectory case)
fn find_vortex_exe(install_dir: &std::path::Path) -> Result<PathBuf, Box<dyn Error>> {
    let vortex_exe = install_dir.join("Vortex.exe");
    if vortex_exe.exists() {
        return Ok(vortex_exe);
    }

    // Check subdirectory
    let sub = install_dir.join("Vortex").join("Vortex.exe");
    if sub.exists() {
        return Ok(sub);
    }

    log_error("Vortex.exe not found at selected path");
    Err(InstallError::ExeNotFound {
        exe_name: "Vortex.exe".to_string(),
        path: install_dir.display().to_string(),
    }
    .into())
}
