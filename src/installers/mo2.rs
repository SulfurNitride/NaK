//! Mod Organizer 2 installation

use std::error::Error;
use std::fs;
use std::path::PathBuf;

use super::{
    apply_wine_registry_settings, fetch_latest_mo2_release, TaskContext, DOTNET9_SDK_URL,
    STANDARD_DEPS,
};
use crate::logging::{log_download, log_error, log_install, log_warning};
use crate::scripts::ScriptGenerator;
use crate::utils::{detect_steam_path, download_file};
use crate::wine::{DependencyManager, PrefixManager, ProtonInfo};

pub fn install_mo2(
    install_name: &str,
    target_install_path: PathBuf,
    proton: &ProtonInfo,
    ctx: TaskContext,
) -> Result<(), Box<dyn Error>> {
    let home = std::env::var("HOME")?;

    // Collision Check
    let prefix_mgr = PrefixManager::new();
    let base_name = format!("mo2_{}", install_name.replace(" ", "_").to_lowercase());
    let unique_name = prefix_mgr.get_unique_prefix_name(&base_name);

    let prefix_root = PathBuf::from(format!("{}/NaK/Prefixes/{}/pfx", home, unique_name));
    let install_dir = target_install_path;

    log_install(&format!(
        "Starting MO2 installation: {} -> {:?}",
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

    // 2. Download MO2
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
        .ok_or("No valid MO2 archive found")?;

    ctx.set_status(format!("Downloading {}...", asset.name));
    ctx.set_progress(0.10);
    log_download(&format!("Downloading MO2: {}", asset.name));
    let archive_path = PathBuf::from(format!("{}/NaK/tmp/{}", home, asset.name));
    download_file(&asset.browser_download_url, &archive_path)?;
    log_download(&format!("MO2 downloaded to: {:?}", archive_path));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // 3. Extract
    ctx.set_status("Extracting MO2...".to_string());
    ctx.set_progress(0.15);
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
    ctx.set_progress(0.20);

    // 4. Dependencies
    ctx.set_status("Preparing to install dependencies...".to_string());
    let dep_mgr = DependencyManager::new(ctx.winetricks_path.clone());

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // 4.1 DotNet 4.8 (Priority)
    if proton.supports_dotnet48() {
        ctx.set_status("Installing dotnet48 (Critical Step)...".to_string());
        log_install("Installing dependency: dotnet48");
        // Note: dep_mgr still uses raw callbacks, so we adapt TaskContext to match
        // But better is to just pass the closures from TaskContext if accessible,
        // or wrap them. For now, since dep_mgr expects simple Fns, we can just pass
        // closures that call ctx methods.
        // Actually, DependencyManager signature is:
        // fn install_dependencies(..., log_callback: impl Fn(String), cancel_flag: Arc<AtomicBool>)

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
            ctx.set_status(format!("Warning: Failed to set win11: {}", e));
            log_warning(&format!("Failed to set win11: {}", e));
        }
    } else {
        ctx.set_status("Skipping dotnet48 (not supported by this Proton version).".to_string());
        log_install("Skipping dotnet48 (not supported by this Proton version)");
    }

    // 4.2 Registry Settings
    let msg = "Applying Wine Registry Settings...".to_string();
    ctx.set_status(msg.clone());
    ctx.log(msg);

    let log_cb = {
        let ctx = ctx.clone();
        move |msg: String| ctx.log(msg)
    };
    apply_wine_registry_settings(&prefix_root, proton, &log_cb)?;

    // 4.3 Main Dependencies
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
            ctx.log(format!("Warning: Failed to install {}: {}", dep, e));
            log_warning(&format!("Failed to install {}: {}", dep, e));
        } else {
            log_install(&format!("Dependency {} installed successfully", dep));
        }
    }

    // 4.4 DotNet 9 SDK
    let msg = "Installing .NET 9 SDK...".to_string();
    ctx.set_status(msg.clone());
    ctx.log(msg);
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

    let proton_bin = proton.path.join("proton");
    let compat_data = prefix_root.parent().unwrap_or(&prefix_root);
    let steam_path = detect_steam_path();

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

    let mo2_exe = install_dir.join("ModOrganizer.exe");
    if !mo2_exe.exists() {
        log_error("ModOrganizer.exe not found after extraction");
        return Err("ModOrganizer.exe not found after extraction".into());
    }

    let script_dir = prefix_root.parent().ok_or("Invalid prefix root")?;

    let script_path = ScriptGenerator::generate_mo2_launch_script(
        &prefix_root,
        &mo2_exe,
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

    // Setup Global Instance support
    setup_global_instance_symlink(&prefix_root, &install_dir);

    ctx.set_progress(1.0);
    ctx.set_status("MO2 Installed Successfully!".to_string());
    log_install(&format!("MO2 installation complete: {}", install_name));
    Ok(())
}

/// Setup an existing MO2 installation with a new prefix
pub fn setup_existing_mo2(
    install_name: &str,
    existing_path: PathBuf,
    proton: &ProtonInfo,
    ctx: TaskContext,
) -> Result<(), Box<dyn Error>> {
    let home = std::env::var("HOME")?;

    // Verify MO2 exists at path
    let mo2_exe = existing_path.join("ModOrganizer.exe");
    if !mo2_exe.exists() {
        log_error("ModOrganizer.exe not found at selected path");
        return Err("ModOrganizer.exe not found at selected path".into());
    }

    log_install(&format!(
        "Setting up existing MO2: {} at {:?}",
        install_name, existing_path
    ));
    log_install(&format!("Using Proton: {}", proton.name));

    // Collision Check
    let prefix_mgr = PrefixManager::new();
    let base_name = format!("mo2_{}", install_name.replace(" ", "_").to_lowercase());
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
        ctx.set_status("Installing dotnet48 (Critical Step)...".to_string());
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
            ctx.set_status(format!("Warning: Failed to set win11: {}", e));
            log_warning(&format!("Failed to set win11: {}", e));
        }
    } else {
        ctx.set_status("Skipping dotnet48 (not supported by this Proton version).".to_string());
        log_install("Skipping dotnet48 (not supported by this Proton version)");
    }

    // 2.2 Registry Settings
    ctx.set_status("Applying Wine Registry Settings...".to_string());
    let log_cb = {
        let ctx = ctx.clone();
        move |msg: String| ctx.log(msg)
    };
    apply_wine_registry_settings(&prefix_root, proton, &log_cb)?;

    // 2.3 Main Dependencies
    let total = STANDARD_DEPS.len();
    let start_progress = 0.20;
    let end_progress = 0.80;
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

    // 2.4 DotNet 9 SDK
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

    let proton_bin = proton.path.join("proton");
    let compat_data = prefix_root.parent().unwrap_or(&prefix_root);
    let steam_path = detect_steam_path();

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

    let script_path = ScriptGenerator::generate_mo2_launch_script(
        &prefix_root,
        &mo2_exe,
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
        let _ = std::os::unix::fs::symlink(&existing_path, &backlink);
    }

    // Setup Global Instance support
    setup_global_instance_symlink(&prefix_root, &existing_path);

    ctx.set_progress(1.0);
    ctx.set_status("MO2 Setup Complete!".to_string());
    log_install(&format!("MO2 setup complete: {}", install_name));
    Ok(())
}

/// Sets up the symlink for Global Instance support
/// Symlinks `.../pfx/drive_c/users/<user>/AppData/Local/ModOrganizer` -> `install_dir/Global Instance`
fn setup_global_instance_symlink(prefix_root: &std::path::Path, install_dir: &std::path::Path) {
    use std::fs;

    let users_dir = prefix_root.join("drive_c/users");
    let mut username = "steamuser".to_string(); // Default fallback

    // Try to detect the correct user folder (not Public, not root if possible)
    if let Ok(entries) = fs::read_dir(&users_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name != "Public" && name != "root" {
                username = name;
                break;
            }
        }
    }

    let appdata_local = users_dir.join(&username).join("AppData/Local");
    let mo2_global_path = appdata_local.join("ModOrganizer");
    let target_global_instance = install_dir.join("Global Instance");

    // 1. Ensure target "Global Instance" folder exists in our managed directory
    if !target_global_instance.exists() {
        if let Err(e) = fs::create_dir_all(&target_global_instance) {
            crate::logging::log_error(&format!("Failed to create Global Instance folder: {}", e));
            return;
        }
    }

    // 2. Ensure parent AppData/Local exists in prefix
    if !appdata_local.exists() {
        if let Err(e) = fs::create_dir_all(&appdata_local) {
            crate::logging::log_error(&format!("Failed to create AppData/Local in prefix: {}", e));
            return;
        }
    }

    // 3. Create Symlink: AppData/Local/ModOrganizer -> Global Instance
    if mo2_global_path.exists() || fs::symlink_metadata(&mo2_global_path).is_ok() {
        // If it's already a symlink or folder, remove it to overwrite (unless it has data we care about? 
        // For a new/setup install, we prioritize our structure).
        // If it's a real folder with data, we might be destroying it. 
        // But this runs on setup. Safe assumption is we want to link it.
        let _ = fs::remove_dir_all(&mo2_global_path); // recursive remove works on symlinks too? No, remove_file for symlink.
        let _ = fs::remove_file(&mo2_global_path);
    }

    if let Err(e) = std::os::unix::fs::symlink(&target_global_instance, &mo2_global_path) {
        crate::logging::log_error(&format!("Failed to create Global Instance symlink: {}", e));
    } else {
        crate::logging::log_install("Enabled Global Instance support (symlinked AppData/Local/ModOrganizer)");
    }
}
