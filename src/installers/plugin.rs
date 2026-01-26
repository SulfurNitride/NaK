//! Plugin installation from NaK Marketplace

use std::error::Error;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::Duration;
use wait_timeout::ChildExt;

use super::common::{check_cancelled, check_disk_space, finalize_steam_installation_with_tools, get_dxvk_conf_path, InstallError, ManagerType};
use super::{install_all_dependencies, TaskContext};
use crate::config::{AppConfig, ManagedPrefixes};
use crate::logging::{log_download, log_error, log_install};
use crate::marketplace::{PluginManifest, get_plugin_download_url, get_installer_args, get_plugin_exe_name, get_plugin_install_type};
use crate::steam::{self, SteamProton};
use crate::utils::download_file;

/// Minimum disk space required for plugin installation (in GB)
const MIN_DISK_SPACE_GB: f64 = 5.0;

/// Timeout for installers (5 minutes)
const INSTALLER_TIMEOUT_SECS: u64 = 300;

/// Result of plugin installation
pub struct PluginInstallResult {
    pub app_id: u32,
}

/// Install a plugin using its manifest
pub fn install_plugin(
    manifest: &PluginManifest,
    install_name: &str,
    install_path: PathBuf,
    proton: &SteamProton,
    ctx: TaskContext,
    skip_disk_check: bool,
) -> Result<PluginInstallResult, Box<dyn Error>> {
    let plugin_id = &manifest.plugin.id;
    let plugin_name = &manifest.plugin.name;
    let exe_name = get_plugin_exe_name(manifest);
    let install_type = get_plugin_install_type(manifest);

    log_install(&format!(
        "Starting {} ({}) installation: {} -> {:?}",
        plugin_name, plugin_id, install_name, install_path
    ));
    log_install(&format!(
        "Install type: {}, Executable: {}",
        install_type, exe_name
    ));

    // Get primary Steam path
    let primary_steam_path = steam::find_steam_path()
        .ok_or_else(|| InstallError::SteamError { reason: "Steam not found".to_string() })?;

    // Check disk space
    if !skip_disk_check {
        if let Err(e) = check_disk_space(&primary_steam_path, MIN_DISK_SPACE_GB) {
            log_error(&format!("Disk space check failed: {}", e));
            return Err(e.into());
        }
    }

    check_cancelled(&ctx)?;

    // 1. Create Steam shortcut
    ctx.set_status("Creating Steam shortcut...".to_string());
    ctx.set_progress(0.05);

    let exe_path = install_path.join(exe_name);
    let dxvk_conf_path = get_dxvk_conf_path(&install_path);

    // Check if this is an Electron app
    let is_electron = install_type == "electron-nsis";

    let steam_result = steam::add_mod_manager_shortcut(
        install_name,
        exe_path.to_str().unwrap_or(""),
        install_path.to_str().unwrap_or(""),
        &proton.config_name,
        Some(&dxvk_conf_path),
        is_electron,
    ).map_err(|e| InstallError::SteamError { reason: e.to_string() })?;

    log_install(&format!("Created Steam shortcut with AppID: {}", steam_result.app_id));

    check_cancelled(&ctx)?;

    // 2. Create install directory
    ctx.set_status("Creating directories...".to_string());
    ctx.set_progress(0.08);

    fs::create_dir_all(&install_path).map_err(|e| InstallError::DirectoryCreation {
        path: install_path.display().to_string(),
        reason: e.to_string(),
    })?;

    check_cancelled(&ctx)?;

    // 3. Download the plugin
    ctx.set_status(format!("Fetching {} download URL...", plugin_name));
    ctx.set_progress(0.10);

    let (download_url, version) = get_plugin_download_url(manifest)?;
    let filename = download_url.split('/').next_back().unwrap_or("installer.exe");

    ctx.set_status(format!("Downloading {} {}...", plugin_name, version));
    log_download(&format!("Downloading {} {}: {}", plugin_name, version, filename));

    let tmp_dir = AppConfig::get_tmp_path();
    fs::create_dir_all(&tmp_dir)?;
    let installer_path = tmp_dir.join(filename);
    download_file(&download_url, &installer_path)?;
    log_download(&format!("{} downloaded to: {:?}", plugin_name, installer_path));

    check_cancelled(&ctx)?;

    // 4. Run installer based on install type
    ctx.set_status(format!("Running {} installer...", plugin_name));
    ctx.set_progress(0.15);

    match install_type {
        "electron-nsis" | "nsis" => {
            run_nsis_installer(
                &installer_path,
                &install_path,
                manifest,
                proton,
                &steam_result.prefix_path,
                &primary_steam_path,
            )?;
        }
        "archive-7z" => {
            // Extract 7z archive
            if let Err(e) = sevenz_rust::decompress_file(&installer_path, &install_path) {
                log_error(&format!("Failed to extract archive: {}", e));
                return Err(InstallError::Other {
                    context: "Archive extraction".to_string(),
                    reason: e.to_string(),
                }.into());
            }
        }
        "archive-zip" => {
            // Extract zip archive
            let file = fs::File::open(&installer_path)?;
            let mut archive = zip::ZipArchive::new(file)?;
            archive.extract(&install_path)?;
        }
        other => {
            return Err(format!("Unknown install type: {}", other).into());
        }
    }

    // Clean up installer
    let _ = fs::remove_file(&installer_path);
    ctx.set_progress(0.20);

    // 5. Verify executable exists
    if !exe_path.exists() {
        // Check subdirectory (some installers create a subfolder)
        let sub_exe = install_path.join(plugin_name).join(exe_name);
        if !sub_exe.exists() {
            log_error(&format!("{} not found after installation", exe_name));
            return Err(InstallError::ExeNotFound {
                exe_name: exe_name.to_string(),
                path: install_path.display().to_string(),
            }.into());
        }
    }

    check_cancelled(&ctx)?;

    // 6. Install dependencies
    install_all_dependencies(&steam_result.prefix_path, proton, &ctx, 0.20, 0.90, steam_result.app_id)?;

    ctx.set_progress(0.92);

    check_cancelled(&ctx)?;

    // 7. Finalize installation
    finalize_steam_installation_with_tools(
        ManagerType::Plugin,
        &steam_result.prefix_path,
        &install_path,
        steam_result.app_id,
        &proton.path,
        &ctx,
    )?;

    // 8. Register prefix for cleanup tracking
    ManagedPrefixes::register(
        steam_result.app_id,
        install_name,
        steam_result.prefix_path.to_str().unwrap_or(""),
        install_path.to_str().unwrap_or(""),
        crate::config::ManagerType::Plugin,
        primary_steam_path.to_str().unwrap_or(""),
        Some(&proton.config_name),
    );
    log_install("Registered prefix for cleanup tracking");

    ctx.set_progress(1.0);
    ctx.set_status(format!("{} Installed! Restart Steam to see it.", plugin_name));
    log_install(&format!("{} installation complete: {}", plugin_name, install_name));

    Ok(PluginInstallResult {
        app_id: steam_result.app_id,
    })
}

/// Run an NSIS installer using Proton
fn run_nsis_installer(
    installer_path: &std::path::Path,
    install_path: &std::path::Path,
    manifest: &PluginManifest,
    proton: &SteamProton,
    prefix_path: &std::path::Path,
    steam_path: &std::path::Path,
) -> Result<(), Box<dyn Error>> {
    let proton_bin = proton.path.join("proton");
    let args = get_installer_args(manifest, install_path);

    log_install(&format!("Running NSIS installer with args: {:?}", args));

    // Get compat_data_path (parent of prefix_path)
    let compat_data_path = prefix_path.parent()
        .ok_or("Could not determine compat_data_path")?;

    let mut child = Command::new(&proton_bin)
        .arg("run")
        .arg(installer_path)
        .args(&args)
        .env("STEAM_COMPAT_DATA_PATH", compat_data_path)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", steam_path)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;

    let timeout = Duration::from_secs(INSTALLER_TIMEOUT_SECS);
    match child.wait_timeout(timeout)? {
        Some(status) => {
            if !status.success() {
                log_error(&format!("Installer failed with exit code: {:?}", status.code()));
                return Err(InstallError::Other {
                    context: "NSIS installer".to_string(),
                    reason: format!("Failed with exit code: {:?}", status.code()),
                }.into());
            }
        }
        None => {
            let _ = child.kill();
            log_error(&format!("Installer timed out after {} seconds", INSTALLER_TIMEOUT_SECS));
            return Err(InstallError::Other {
                context: "NSIS installer".to_string(),
                reason: format!("Timed out after {} seconds", INSTALLER_TIMEOUT_SECS),
            }.into());
        }
    }

    // Wait for files to settle
    std::thread::sleep(Duration::from_secs(2));

    Ok(())
}
