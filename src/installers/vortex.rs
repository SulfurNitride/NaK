//! Vortex installation

use std::path::PathBuf;
use std::fs;
use std::error::Error;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use wait_timeout::ChildExt;

use crate::wine::{ProtonInfo, DependencyManager, PrefixManager};
use crate::utils::{detect_steam_path, download_file};
use crate::scripts::ScriptGenerator;
use crate::logging::{log_install, log_download, log_error};
use super::{fetch_latest_vortex_release, apply_wine_registry_settings, STANDARD_DEPS, DOTNET9_SDK_URL};

pub fn install_vortex(
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
    let base_name = format!("vortex_{}", install_name.replace(" ", "_").to_lowercase());
    let unique_name = prefix_mgr.get_unique_prefix_name(&base_name);

    let prefix_root = PathBuf::from(format!("{}/NaK/Prefixes/{}/pfx", home, unique_name));
    let install_dir = target_install_path;

    log_install(&format!("Starting Vortex installation: {} -> {:?}", install_name, install_dir));
    log_install(&format!("Using Proton: {}", proton.name));

    if cancel_flag.load(Ordering::Relaxed) { return Err("Cancelled".into()); }

    // 1. Create Directories
    status_callback("Creating directories...".to_string());
    progress_callback(0.05);
    fs::create_dir_all(&prefix_root)?;
    fs::create_dir_all(&install_dir)?;
    log_install(&format!("Created prefix at: {:?}", prefix_root));

    if cancel_flag.load(Ordering::Relaxed) { return Err("Cancelled".into()); }

    // 2. Download Vortex
    status_callback("Fetching Vortex release info...".to_string());
    let release = fetch_latest_vortex_release()?;

    log_callback(format!("Found release: {}", release.tag_name));

    // Find asset: Vortex-setup-*.exe (Case insensitive)
    let asset = release.assets.iter()
        .find(|a| {
            let name = a.name.to_lowercase();
            name.starts_with("vortex-setup") && name.ends_with(".exe")
        });

    if asset.is_none() {
        log_callback("Available assets:".to_string());
        for a in &release.assets {
            log_callback(format!(" - {}", a.name));
        }
        return Err("No valid Vortex installer found (expected Vortex-setup-*.exe)".into());
    }
    let asset = asset.unwrap();

    status_callback(format!("Downloading {}...", asset.name));
    progress_callback(0.10);
    log_download(&format!("Downloading Vortex: {}", asset.name));
    let installer_path = PathBuf::from(format!("{}/NaK/tmp/{}", home, asset.name));
    download_file(&asset.browser_download_url, &installer_path)?;
    log_download(&format!("Vortex downloaded to: {:?}", installer_path));

    if cancel_flag.load(Ordering::Relaxed) { return Err("Cancelled".into()); }

    // 3. Run Installer (Silent) - Use proton run, NOT wine directly
    status_callback("Running Vortex Installer...".to_string());
    progress_callback(0.15);

    let proton_bin = proton.path.join("proton");
    // Convert install_dir to Windows path Z:\...
    let win_install_path = format!("Z:{}", install_dir.to_string_lossy().replace("/", "\\"));

    // Get compat_data path (parent of prefix)
    let compat_data = prefix_root.parent().unwrap_or(&prefix_root);

    // Detect Steam path for proper DRM support
    let steam_path = detect_steam_path();
    log_callback(format!("Using Steam path: {}", steam_path));

    // Run installer with proper Proton environment (matching Python implementation)
    let mut child = std::process::Command::new(&proton_bin)
        .arg("run")
        .arg(&installer_path)
        .arg("/S")
        .arg(format!("/D={}", win_install_path))
        .env("WINEPREFIX", &prefix_root)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_path)
        // Reset LD_LIBRARY_PATH to prevent AppImage libs from breaking system binaries
        .env("LD_LIBRARY_PATH", "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu")
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()?;

    // Wait with timeout (5 minutes, same as Python)
    let timeout = Duration::from_secs(300);
    let status = match child.wait_timeout(timeout)? {
        Some(status) => status,
        None => {
            // Timeout - kill the process
            let _ = child.kill();
            return Err("Vortex installer timed out after 5 minutes".into());
        }
    };

    if !status.success() {
        log_callback(format!("Installer exit code: {:?}", status.code()));
        return Err("Vortex installer failed".into());
    }

    // Wait for files to settle (same as Python)
    std::thread::sleep(Duration::from_secs(2));

    progress_callback(0.20);

    // 4. Dependencies
    status_callback("Preparing to install dependencies...".to_string());
    let dep_mgr = DependencyManager::new(winetricks_path);

    if cancel_flag.load(Ordering::Relaxed) { return Err("Cancelled".into()); }

    // 4.1 DotNet 4.8 (Priority)
    if proton.supports_dotnet48() {
        status_callback("Installing dotnet48...".to_string());
        if let Err(e) = dep_mgr.install_dependencies(&prefix_root, proton, &["dotnet48"], log_callback.clone(), cancel_flag.clone()) {
             status_callback(format!("Warning: dotnet48 failed: {}", e));
        }

        status_callback("Setting Windows version to win11...".to_string());
        let _ = dep_mgr.run_winetricks_command(&prefix_root, proton, "win11", log_callback.clone());
    } else {
        status_callback("Skipping dotnet48 (not supported).".to_string());
    }

    // 4.2 Main Dependencies
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
        }
    }

    // 4.3 Apply Wine registry settings
    status_callback("Applying Wine registry settings...".to_string());
    progress_callback(0.87);
    apply_wine_registry_settings(&prefix_root, proton, &log_callback)?;

    // 4.4 DotNet 9 SDK
    status_callback("Installing .NET 9 SDK...".to_string());
    progress_callback(0.90);
    let tmp_dir = PathBuf::from(format!("{}/NaK/tmp", home));
    fs::create_dir_all(&tmp_dir)?;
    let dotnet_installer = tmp_dir.join("dotnet9_sdk.exe");
    if !dotnet_installer.exists() {
        log_callback("Downloading .NET 9 SDK...".to_string());
        download_file(DOTNET9_SDK_URL, &dotnet_installer)?;
    }
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

    // Vortex.exe location might vary slightly
    let mut vortex_exe = install_dir.join("Vortex.exe");
    if !vortex_exe.exists() {
        // Check subdir
        let sub = install_dir.join("Vortex").join("Vortex.exe");
        if sub.exists() {
            vortex_exe = sub;
        } else {
            return Err("Vortex.exe not found after installation".into());
        }
    }

    let script_dir = prefix_root.parent().ok_or("Invalid prefix root")?;

    let script_path = ScriptGenerator::generate_vortex_launch_script(
        &prefix_root,
        &vortex_exe,
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
        let _ = std::os::unix::fs::symlink(target, &link_path);
    };

    create_link(&script_path, "Launch Vortex");
    create_link(&kill_script, "Kill Vortex Prefix");
    create_link(&reg_script, "Fix Game Registry");

    if let Some(prefix_base) = prefix_root.parent() {
        let backlink = prefix_base.join("manager_link");
        if backlink.exists() || fs::symlink_metadata(&backlink).is_ok() {
            let _ = fs::remove_file(&backlink);
        }
        let _ = std::os::unix::fs::symlink(&install_dir, &backlink);
    }

    progress_callback(1.0);
    status_callback("Vortex Installed Successfully!".to_string());
    log_install(&format!("Vortex installation complete: {}", install_name));
    Ok(())
}
