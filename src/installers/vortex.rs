//! Vortex installation

use std::error::Error;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;
use wait_timeout::ChildExt;

use super::{
    apply_wine_registry_settings, fetch_latest_vortex_release, TaskContext, DOTNET9_SDK_URL,
    STANDARD_DEPS,
};
use crate::logging::{log_download, log_error, log_install, log_warning};
use crate::scripts::ScriptGenerator;
use crate::utils::{detect_steam_path, download_file};
use crate::wine::{DependencyManager, PrefixManager, ProtonInfo};

pub fn install_vortex(
    install_name: &str,
    target_install_path: PathBuf,
    proton: &ProtonInfo,
    ctx: TaskContext,
) -> Result<(), Box<dyn Error>> {
    let home = std::env::var("HOME")?;

    // Collision Check
    let prefix_mgr = PrefixManager::new();
    let base_name = format!("vortex_{}", install_name.replace(" ", "_").to_lowercase());
    let unique_name = prefix_mgr.get_unique_prefix_name(&base_name);

    let prefix_root = PathBuf::from(format!("{}/NaK/Prefixes/{}/pfx", home, unique_name));
    let install_dir = target_install_path;

    log_install(&format!(
        "Starting Vortex installation: {} -> {:?}",
        install_name, install_dir
    ));
    log_install(&format!("Using Proton: {}", proton.name));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // 1. Create Directories
    ctx.set_status("Creating directories...".to_string());
    ctx.set_progress(0.05);
    fs::create_dir_all(&prefix_root)?;
    fs::create_dir_all(&install_dir)?;
    log_install(&format!("Created prefix at: {:?}", prefix_root));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // 2. Download Vortex
    ctx.set_status("Fetching Vortex release info...".to_string());
    let release = fetch_latest_vortex_release()?;

    ctx.log(format!("Found release: {}", release.tag_name));

    // Find asset: Vortex-setup-*.exe (Case insensitive)
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
        return Err("No valid Vortex installer found (expected Vortex-setup-*.exe)".into());
    }
    let asset = asset.unwrap();

    ctx.set_status(format!("Downloading {}...", asset.name));
    ctx.set_progress(0.10);
    log_download(&format!("Downloading Vortex: {}", asset.name));
    let installer_path = PathBuf::from(format!("{}/NaK/tmp/{}", home, asset.name));
    download_file(&asset.browser_download_url, &installer_path)?;
    log_download(&format!("Vortex downloaded to: {:?}", installer_path));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // 3. Run Installer (Silent) - Use proton run, NOT wine directly
    ctx.set_status("Running Vortex Installer...".to_string());
    ctx.set_progress(0.15);

    let proton_bin = proton.path.join("proton");
    // Convert install_dir to Windows path Z:\...
    let win_install_path = format!("Z:{}", install_dir.to_string_lossy().replace("/", "\\"));

    // Get compat_data path (parent of prefix)
    let compat_data = prefix_root.parent().unwrap_or(&prefix_root);

    // Detect Steam path for proper DRM support
    let steam_path = detect_steam_path();
    ctx.log(format!("Using Steam path: {}", steam_path));

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
        .env(
            "LD_LIBRARY_PATH",
            "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu",
        )
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
            log_error("Vortex installer timed out after 5 minutes");
            return Err("Vortex installer timed out after 5 minutes".into());
        }
    };

    if !status.success() {
        // Capture stdout and stderr for better error reporting
        let stdout = child.stdout.take()
            .map(|mut s| {
                let mut buf = String::new();
                use std::io::Read;
                let _ = s.read_to_string(&mut buf);
                buf
            })
            .unwrap_or_default();

        let stderr = child.stderr.take()
            .map(|mut s| {
                let mut buf = String::new();
                use std::io::Read;
                let _ = s.read_to_string(&mut buf);
                buf
            })
            .unwrap_or_default();

        ctx.log(format!("Installer exit code: {:?}", status.code()));
        log_error(&format!(
            "Vortex installer failed with exit code: {:?}",
            status.code()
        ));

        if !stdout.is_empty() {
            ctx.log(format!("Installer stdout:\n{}", stdout));
            log_error(&format!("Vortex installer stdout:\n{}", stdout));
        }

        if !stderr.is_empty() {
            ctx.log(format!("Installer stderr:\n{}", stderr));
            log_error(&format!("Vortex installer stderr:\n{}", stderr));
        }

        return Err(format!("Vortex installer failed with exit code: {:?}", status.code()).into());
    }

    // Wait for files to settle (same as Python)
    std::thread::sleep(Duration::from_secs(2));

    ctx.set_progress(0.20);

    // 4. Dependencies
    ctx.set_status("Preparing to install dependencies...".to_string());
    let dep_mgr = DependencyManager::new(ctx.winetricks_path.clone());

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // 4.1 DotNet 4.8 (Priority)
    if proton.supports_dotnet48() {
        ctx.set_status("Installing dotnet48...".to_string());
        log_install("Installing dependency: dotnet48");

        let log_cb = {
            let ctx = ctx.clone();
            move |msg: String| ctx.log(msg)
        };

        if let Err(e) = dep_mgr.install_dependencies(
            &prefix_root,
            proton,
            &["dotnet48"],
            log_cb.clone(),
            ctx.cancel_flag.clone(),
        ) {
            ctx.set_status(format!("Warning: dotnet48 failed: {}", e));
            log_warning(&format!("dotnet48 installation failed: {}", e));
        } else {
            log_install("Dependency dotnet48 installed successfully");
        }

        ctx.set_status("Setting Windows version to win11...".to_string());
        log_install("Setting Windows version to win11");
        if let Err(e) = dep_mgr.run_winetricks_command(&prefix_root, proton, "win11", log_cb) {
            log_warning(&format!("Failed to set win11: {}", e));
        }
    } else {
        ctx.set_status("Skipping dotnet48 (not supported).".to_string());
        log_install("Skipping dotnet48 (not supported by this Proton version)");
    }

    // 4.2 Main Dependencies
    let total = STANDARD_DEPS.len();
    let start_progress = 0.30;
    let end_progress = 0.85;
    let step_size = (end_progress - start_progress) / total as f32;

    for (i, dep) in STANDARD_DEPS.iter().enumerate() {
        if ctx.is_cancelled() {
            return Err("Cancelled".into());
        }

        let current_p = start_progress + (i as f32 * step_size);
        ctx.set_progress(current_p);

        ctx.set_status(format!(
            "Installing dependency {}/{} : {}...",
            i + 1,
            total,
            dep
        ));
        log_install(&format!(
            "Installing dependency {}/{}: {}",
            i + 1,
            total,
            dep
        ));

        let log_cb = {
            let ctx = ctx.clone();
            move |msg: String| ctx.log(msg)
        };

        if let Err(e) = dep_mgr.install_dependencies(
            &prefix_root,
            proton,
            &[dep],
            log_cb,
            ctx.cancel_flag.clone(),
        ) {
            ctx.set_status(format!(
                "Warning: Failed to install {}: {} (Continuing...)",
                dep, e
            ));
            log_warning(&format!("Failed to install {}: {}", dep, e));
        } else {
            log_install(&format!("Dependency {} installed successfully", dep));
        }
    }

    // 4.3 Apply Wine registry settings
    ctx.set_status("Applying Wine registry settings...".to_string());
    ctx.set_progress(0.87);
    let log_cb = {
        let ctx = ctx.clone();
        move |msg: String| ctx.log(msg)
    };
    apply_wine_registry_settings(&prefix_root, proton, &log_cb)?;

    // 4.4 DotNet 9 SDK
    ctx.set_status("Installing .NET 9 SDK...".to_string());
    log_install("Installing .NET 9 SDK...");
    ctx.set_progress(0.90);
    let tmp_dir = PathBuf::from(format!("{}/NaK/tmp", home));
    fs::create_dir_all(&tmp_dir)?;
    let dotnet_installer = tmp_dir.join("dotnet9_sdk.exe");
    if !dotnet_installer.exists() {
        ctx.log("Downloading .NET 9 SDK...".to_string());
        log_download("Downloading .NET 9 SDK...");
        download_file(DOTNET9_SDK_URL, &dotnet_installer)?;
        log_download("Downloaded .NET 9 SDK");
    }
    ctx.log("Running .NET 9 SDK installer...".to_string());
    match std::process::Command::new(&proton_bin)
        .arg("run")
        .arg(&dotnet_installer)
        .arg("/quiet")
        .arg("/norestart")
        .env("WINEPREFIX", &prefix_root)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_path)
        .env(
            "LD_LIBRARY_PATH",
            "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu",
        )
        .status()
    {
        Ok(status) => {
            if status.success() {
                ctx.log(".NET 9 SDK installed successfully".to_string());
                log_install(".NET 9 SDK installed successfully");
            } else {
                ctx.log(format!(
                    ".NET 9 SDK installer exited with code: {:?}",
                    status.code()
                ));
                log_warning(&format!(
                    ".NET 9 SDK installer exited with code: {:?}",
                    status.code()
                ));
            }
        }
        Err(e) => {
            ctx.log(format!("Failed to run .NET 9 SDK installer: {}", e));
            log_error(&format!("Failed to run .NET 9 SDK installer: {}", e));
        }
    }

    ctx.set_progress(0.95);

    // 5. Generate Scripts
    ctx.set_status("Generating launch scripts...".to_string());

    // Vortex.exe location might vary slightly
    let mut vortex_exe = install_dir.join("Vortex.exe");
    if !vortex_exe.exists() {
        // Check subdir
        let sub = install_dir.join("Vortex").join("Vortex.exe");
        if sub.exists() {
            vortex_exe = sub;
        } else {
            log_error("Vortex.exe not found after installation");
            return Err("Vortex.exe not found after installation".into());
        }
    }

    let script_dir = prefix_root.parent().ok_or("Invalid prefix root")?;

    let script_path = ScriptGenerator::generate_vortex_launch_script(
        &prefix_root,
        &vortex_exe,
        &proton.path,
        &install_dir,
        script_dir,
    )?;

    let kill_script =
        ScriptGenerator::generate_kill_prefix_script(&prefix_root, &proton.path, script_dir)?;

    let reg_script = ScriptGenerator::generate_fix_game_registry_script(
        &prefix_root,
        &proton.path,
        install_name,
        script_dir,
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

    ctx.set_progress(1.0);
    ctx.set_status("Vortex Installed Successfully!".to_string());
    log_install(&format!("Vortex installation complete: {}", install_name));
    Ok(())
}

/// Setup an existing Vortex installation with a new prefix
pub fn setup_existing_vortex(
    install_name: &str,
    existing_path: PathBuf,
    proton: &ProtonInfo,
    ctx: TaskContext,
) -> Result<(), Box<dyn Error>> {
    let home = std::env::var("HOME")?;

    // Verify Vortex exists at path
    let mut vortex_exe = existing_path.join("Vortex.exe");
    if !vortex_exe.exists() {
        // Check subdir
        let sub = existing_path.join("Vortex").join("Vortex.exe");
        if sub.exists() {
            vortex_exe = sub;
        } else {
            log_error("Vortex.exe not found at selected path");
            return Err("Vortex.exe not found at selected path".into());
        }
    }

    log_install(&format!(
        "Setting up existing Vortex: {} at {:?}",
        install_name, existing_path
    ));
    log_install(&format!("Using Proton: {}", proton.name));

    // Collision Check
    let prefix_mgr = PrefixManager::new();
    let base_name = format!("vortex_{}", install_name.replace(" ", "_").to_lowercase());
    let unique_name = prefix_mgr.get_unique_prefix_name(&base_name);

    let prefix_root = PathBuf::from(format!("{}/NaK/Prefixes/{}/pfx", home, unique_name));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // 1. Create Prefix Directory
    ctx.set_status("Creating prefix...".to_string());
    ctx.set_progress(0.05);
    fs::create_dir_all(&prefix_root)?;
    log_install(&format!("Created prefix at: {:?}", prefix_root));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // 2. Dependencies
    ctx.set_status("Preparing to install dependencies...".to_string());
    ctx.set_progress(0.10);
    let dep_mgr = DependencyManager::new(ctx.winetricks_path.clone());

    // 2.1 DotNet 4.8 (Priority)
    if proton.supports_dotnet48() {
        ctx.set_status("Installing dotnet48...".to_string());
        log_install("Installing dependency: dotnet48");

        let log_cb = {
            let ctx = ctx.clone();
            move |msg: String| ctx.log(msg)
        };

        if let Err(e) = dep_mgr.install_dependencies(
            &prefix_root,
            proton,
            &["dotnet48"],
            log_cb.clone(),
            ctx.cancel_flag.clone(),
        ) {
            ctx.set_status(format!("Warning: dotnet48 failed: {}", e));
            log_warning(&format!("dotnet48 installation failed: {}", e));
        } else {
            log_install("Dependency dotnet48 installed successfully");
        }

        ctx.set_status("Setting Windows version to win11...".to_string());
        log_install("Setting Windows version to win11");
        if let Err(e) = dep_mgr.run_winetricks_command(&prefix_root, proton, "win11", log_cb) {
            log_warning(&format!("Failed to set win11: {}", e));
        }
    } else {
        ctx.set_status("Skipping dotnet48 (not supported).".to_string());
        log_install("Skipping dotnet48 (not supported by this Proton version)");
    }

    // 2.2 Main Dependencies
    let total = STANDARD_DEPS.len();
    let start_progress = 0.20;
    let end_progress = 0.75;
    let step_size = (end_progress - start_progress) / total as f32;

    for (i, dep) in STANDARD_DEPS.iter().enumerate() {
        if ctx.is_cancelled() {
            return Err("Cancelled".into());
        }

        let current_p = start_progress + (i as f32 * step_size);
        ctx.set_progress(current_p);

        ctx.set_status(format!(
            "Installing dependency {}/{} : {}...",
            i + 1,
            total,
            dep
        ));
        log_install(&format!(
            "Installing dependency {}/{}: {}",
            i + 1,
            total,
            dep
        ));

        let log_cb = {
            let ctx = ctx.clone();
            move |msg: String| ctx.log(msg)
        };

        if let Err(e) = dep_mgr.install_dependencies(
            &prefix_root,
            proton,
            &[dep],
            log_cb,
            ctx.cancel_flag.clone(),
        ) {
            ctx.set_status(format!(
                "Warning: Failed to install {}: {} (Continuing...)",
                dep, e
            ));
            log_warning(&format!("Failed to install {}: {}", dep, e));
        } else {
            log_install("Dependency {} installed successfully");
        }
    }

    // 2.3 Apply Wine registry settings
    ctx.set_status("Applying Wine registry settings...".to_string());
    ctx.set_progress(0.80);
    let log_cb = {
        let ctx = ctx.clone();
        move |msg: String| ctx.log(msg)
    };
    apply_wine_registry_settings(&prefix_root, proton, &log_cb)?;

    // 2.4 DotNet 9 SDK
    let proton_bin = proton.path.join("proton");
    let compat_data = prefix_root.parent().unwrap_or(&prefix_root);
    let steam_path = detect_steam_path();

    ctx.set_status("Installing .NET 9 SDK...".to_string());
    log_install("Installing .NET 9 SDK...");
    ctx.set_progress(0.85);
    let tmp_dir = PathBuf::from(format!("{}/NaK/tmp", home));
    fs::create_dir_all(&tmp_dir)?;
    let dotnet_installer = tmp_dir.join("dotnet9_sdk.exe");
    if !dotnet_installer.exists() {
        ctx.log("Downloading .NET 9 SDK...".to_string());
        log_download("Downloading .NET 9 SDK...");
        download_file(DOTNET9_SDK_URL, &dotnet_installer)?;
        log_download("Downloaded .NET 9 SDK");
    }
    ctx.log("Running .NET 9 SDK installer...".to_string());
    match std::process::Command::new(&proton_bin)
        .arg("run")
        .arg(&dotnet_installer)
        .arg("/quiet")
        .arg("/norestart")
        .env("WINEPREFIX", &prefix_root)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_path)
        .env(
            "LD_LIBRARY_PATH",
            "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu",
        )
        .status()
    {
        Ok(status) => {
            if status.success() {
                ctx.log(".NET 9 SDK installed successfully".to_string());
                log_install(".NET 9 SDK installed successfully");
            } else {
                ctx.log(format!(
                    ".NET 9 SDK installer exited with code: {:?}",
                    status.code()
                ));
                log_warning(&format!(
                    ".NET 9 SDK installer exited with code: {:?}",
                    status.code()
                ));
            }
        }
        Err(e) => {
            ctx.log(format!("Failed to run .NET 9 SDK installer: {}", e));
            log_error(&format!("Failed to run .NET 9 SDK installer: {}", e));
        }
    }

    ctx.set_progress(0.90);

    // 3. Generate Scripts
    ctx.set_status("Generating launch scripts...".to_string());

    let script_dir = prefix_root.parent().ok_or("Invalid prefix root")?;

    let script_path = ScriptGenerator::generate_vortex_launch_script(
        &prefix_root,
        &vortex_exe,
        &proton.path,
        &existing_path,
        script_dir,
    )?;

    let kill_script =
        ScriptGenerator::generate_kill_prefix_script(&prefix_root, &proton.path, script_dir)?;

    let reg_script = ScriptGenerator::generate_fix_game_registry_script(
        &prefix_root,
        &proton.path,
        install_name,
        script_dir,
    )?;

    let create_link = |target: &std::path::Path, link_name: &str| {
        let link_path = existing_path.join(link_name);
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
        let _ = std::os::unix::fs::symlink(&existing_path, &backlink);
    }

    ctx.set_progress(1.0);
    ctx.set_status("Vortex Setup Complete!".to_string());
    log_install(&format!("Vortex setup complete: {}", install_name));
    Ok(())
}
