//! Mod Organizer 2 installation

use std::path::PathBuf;
use std::fs;
use std::error::Error;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use crate::wine::{ProtonInfo, DependencyManager, PrefixManager};
use crate::utils::{detect_steam_path, download_file};
use crate::scripts::ScriptGenerator;
use super::{fetch_latest_mo2_release, apply_wine_registry_settings, STANDARD_DEPS, DOTNET9_SDK_URL};

pub fn install_mo2(
    install_name: &str,
    target_install_path: PathBuf,
    proton: &ProtonInfo,
    winetricks_path: PathBuf,
    status_callback: impl Fn(String) + Clone + Send + 'static,
    log_callback: impl Fn(String) + Clone + Send + 'static,
    progress_callback: impl Fn(f32) + Clone + Send + 'static,
    cancel_flag: Arc<AtomicBool>
) -> Result<(), Box<dyn Error>> {
    let home = std::env::var("HOME")?;

    // Collision Check
    let prefix_mgr = PrefixManager::new();
    let base_name = format!("mo2_{}", install_name.replace(" ", "_").to_lowercase());
    let unique_name = prefix_mgr.get_unique_prefix_name(&base_name);

    let prefix_root = PathBuf::from(format!("{}/NaK/Prefixes/{}/pfx", home, unique_name));
    let install_dir = target_install_path;

    if cancel_flag.load(Ordering::Relaxed) { return Err("Cancelled".into()); }

    // 1. Create Directories
    status_callback("Creating directories...".to_string());
    progress_callback(0.05);
    fs::create_dir_all(&prefix_root)?;
    fs::create_dir_all(&install_dir)?;

    if cancel_flag.load(Ordering::Relaxed) { return Err("Cancelled".into()); }

    // 2. Download MO2
    status_callback("Fetching MO2 release info...".to_string());
    let release = fetch_latest_mo2_release()?;

    let invalid_terms = ["Linux", "pdbs", "src", "uibase", "commits"];
    let asset = release.assets.iter()
        .find(|a| {
            a.name.starts_with("Mod.Organizer-2") &&
            a.name.ends_with(".7z") &&
            !invalid_terms.iter().any(|term| a.name.contains(term))
        })
        .ok_or("No valid MO2 archive found")?;

    status_callback(format!("Downloading {}...", asset.name));
    progress_callback(0.10);
    let archive_path = PathBuf::from(format!("{}/NaK/tmp/{}", home, asset.name));
    download_file(&asset.browser_download_url, &archive_path)?;

    if cancel_flag.load(Ordering::Relaxed) { return Err("Cancelled".into()); }

    // 3. Extract
    status_callback("Extracting MO2...".to_string());
    progress_callback(0.15);
    let status = std::process::Command::new("7z")
        .arg("x")
        .arg(&archive_path)
        .arg(format!("-o{}", install_dir.to_string_lossy()))
        .arg("-y")
        .status();

    if status.is_err() || !status.unwrap().success() {
         std::process::Command::new("unzip")
            .arg(&archive_path)
            .arg("-d")
            .arg(&install_dir)
            .status()?;
    }
    progress_callback(0.20);

    // 4. Dependencies
    status_callback("Preparing to install dependencies...".to_string());
    let dep_mgr = DependencyManager::new(winetricks_path);

    if cancel_flag.load(Ordering::Relaxed) { return Err("Cancelled".into()); }

    // 4.1 DotNet 4.8 (Priority)
    if proton.supports_dotnet48() {
        status_callback("Installing dotnet48 (Critical Step)...".to_string());
        if let Err(e) = dep_mgr.install_dependencies(&prefix_root, proton, &["dotnet48"], log_callback.clone(), cancel_flag.clone()) {
             status_callback(format!("Warning: dotnet48 failed: {}", e));
        }

        status_callback("Setting Windows version to win11...".to_string());
        if let Err(e) = dep_mgr.run_winetricks_command(&prefix_root, proton, "win11", log_callback.clone()) {
             status_callback(format!("Warning: Failed to set win11: {}", e));
        }
    } else {
        status_callback("Skipping dotnet48 (not supported by this Proton version).".to_string());
    }

    // 4.2 Registry Settings
    let msg = "Applying Wine Registry Settings...".to_string();
    status_callback(msg.clone());
    log_callback(msg);
    apply_wine_registry_settings(&prefix_root, proton, &log_callback)?;

    // 4.3 Main Dependencies
    let total = STANDARD_DEPS.len();
    let start_progress = 0.30;
    let end_progress = 0.85;
    let step_size = (end_progress - start_progress) / total as f32;

    for (i, dep) in STANDARD_DEPS.iter().enumerate() {
        if cancel_flag.load(Ordering::Relaxed) { return Err("Cancelled".into()); }

        let current_p = start_progress + (i as f32 * step_size);
        progress_callback(current_p);

        status_callback(format!("Installing dependency {}/{} : {}...", i + 1, total, dep));
        if let Err(e) = dep_mgr.install_dependencies(&prefix_root, proton, &[dep], log_callback.clone(), cancel_flag.clone()) {
            status_callback(format!("Warning: Failed to install {}: {} (Continuing...)", dep, e));
            log_callback(format!("Warning: Failed to install {}: {}", dep, e));
        }
    }

    // 4.4 DotNet 9 SDK
    let msg = "Installing .NET 9 SDK...".to_string();
    status_callback(msg.clone());
    log_callback(msg);
    progress_callback(0.90);

    let tmp_dir = PathBuf::from(format!("{}/NaK/tmp", home));
    fs::create_dir_all(&tmp_dir)?;
    let dotnet_installer = tmp_dir.join("dotnet9_sdk.exe");

    if !dotnet_installer.exists() {
        log_callback("Downloading .NET 9 SDK...".to_string());
        download_file(DOTNET9_SDK_URL, &dotnet_installer)?;
    }

    let proton_bin = proton.path.join("proton");
    let compat_data = prefix_root.parent().unwrap_or(&prefix_root);
    let steam_path = detect_steam_path();

    log_callback("Running .NET 9 SDK installer...".to_string());
    match std::process::Command::new(&proton_bin)
        .arg("run")
        .arg(&dotnet_installer)
        .arg("/quiet")
        .arg("/norestart")
        .env("WINEPREFIX", &prefix_root)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_path)
        .env("LD_LIBRARY_PATH", "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu")
        .status()
    {
        Ok(status) => {
            if status.success() {
                log_callback(".NET 9 SDK installed successfully".to_string());
            } else {
                log_callback(format!(".NET 9 SDK installer exited with code: {:?}", status.code()));
            }
        }
        Err(e) => {
            log_callback(format!("Failed to run .NET 9 SDK installer: {}", e));
        }
    }

    progress_callback(0.95);

    // 5. Generate Scripts
    status_callback("Generating launch scripts...".to_string());

    let mo2_exe = install_dir.join("ModOrganizer.exe");
    if !mo2_exe.exists() {
        return Err("ModOrganizer.exe not found after extraction".into());
    }

    let script_dir = prefix_root.parent().ok_or("Invalid prefix root")?;

    let script_path = ScriptGenerator::generate_mo2_launch_script(
        &prefix_root,
        &mo2_exe,
        &proton.path,
        &install_dir,
        script_dir
    )?;

    let kill_script = ScriptGenerator::generate_kill_prefix_script(
        &prefix_root,
        &proton.path,
        script_dir
    )?;

    let reg_script = ScriptGenerator::generate_fix_game_registry_script(
        &prefix_root,
        &proton.path,
        install_name,
        script_dir
    )?;

    let create_link = |target: &std::path::Path, link_name: &str| {
        let link_path = install_dir.join(link_name);
        if link_path.exists() || fs::symlink_metadata(&link_path).is_ok() {
            let _ = fs::remove_file(&link_path);
        }
        if let Err(e) = std::os::unix::fs::symlink(target, &link_path) {
             eprintln!("Failed to symlink {:?} to {:?}: {}", target, link_path, e);
        }
    };

    create_link(&script_path, "Launch MO2");
    create_link(&kill_script, "Kill MO2 Prefix");
    create_link(&reg_script, "Fix Game Registry");

    if let Some(prefix_base) = prefix_root.parent() {
        let backlink = prefix_base.join("manager_link");
        if backlink.exists() || fs::symlink_metadata(&backlink).is_ok() {
            let _ = fs::remove_file(&backlink);
        }
        let _ = std::os::unix::fs::symlink(&install_dir, &backlink);
    }

    progress_callback(1.0);
    status_callback("MO2 Installed Successfully!".to_string());
    Ok(())
}
