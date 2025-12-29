//! Mod Organizer 2 installation

use std::error::Error;
use std::fs;
use std::path::PathBuf;

use super::{
    brief_launch_and_kill, create_game_folders, fetch_latest_mo2_release, get_install_proton,
    install_all_dependencies, TaskContext,
};
use crate::config::AppConfig;
use crate::logging::{log_download, log_error, log_install};
use crate::scripts::ScriptGenerator;
use crate::utils::download_file;
use crate::wine::{PrefixManager, ProtonInfo};

pub fn install_mo2(
    install_name: &str,
    target_install_path: PathBuf,
    proton: &ProtonInfo,
    ctx: TaskContext,
) -> Result<(), Box<dyn Error>> {
    let config = AppConfig::load();

    // Collision Check
    let prefix_mgr = PrefixManager::new();
    let base_name = format!("mo2_{}", install_name.replace(" ", "_").to_lowercase());
    let unique_name = prefix_mgr.get_unique_prefix_name(&base_name);

    let prefix_root = config.get_prefixes_path().join(&unique_name).join("pfx");
    let install_dir = target_install_path;

    log_install(&format!(
        "Starting MO2 installation: {} -> {:?}",
        install_name, install_dir
    ));
    log_install(&format!("Using Proton: {}", proton.name));

    // For Proton 10+, use GE-Proton10-18 for the entire installation process
    let install_proton = get_install_proton(proton, &ctx);

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
    let tmp_dir = config.get_data_path().join("tmp");
    fs::create_dir_all(&tmp_dir)?;
    let archive_path = tmp_dir.join(&asset.name);
    download_file(&asset.browser_download_url, &archive_path)?;
    log_download(&format!("MO2 downloaded to: {:?}", archive_path));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // 3. Extract using native Rust 7z library
    ctx.set_status("Extracting MO2...".to_string());
    ctx.set_progress(0.15);

    if let Err(e) = sevenz_rust::decompress_file(&archive_path, &install_dir) {
        log_error(&format!("Failed to extract MO2 archive: {}", e));
        return Err(format!("Failed to extract MO2: {}", e).into());
    }

    ctx.set_progress(0.20);

    // 4. Install all dependencies (dotnet48, registry, standard deps, dotnet9sdk)
    install_all_dependencies(&prefix_root, &install_proton, &ctx, 0.20, 0.90)?;

    ctx.set_progress(0.92);

    // 5. Brief launch to initialize prefix, then kill
    let mo2_exe = install_dir.join("ModOrganizer.exe");
    if !mo2_exe.exists() {
        log_error("ModOrganizer.exe not found after extraction");
        return Err("ModOrganizer.exe not found after extraction".into());
    }

    brief_launch_and_kill(&mo2_exe, &prefix_root, &install_proton, &ctx, "MO2");

    ctx.set_progress(0.95);

    // 6. Generate Scripts (using user's selected proton)
    ctx.set_status("Generating launch scripts...".to_string());

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

    // Generate NXM handler script (for nxmhandler.exe)
    let nxm_handler_exe = install_dir.join("nxmhandler.exe");
    let _nxm_script = if nxm_handler_exe.exists() {
        Some(ScriptGenerator::generate_mo2_nxm_script(
            &prefix_root,
            &nxm_handler_exe,
            &proton.path,
            script_dir,
        )?)
    } else {
        None
    };

    // Create symlinks in the MO2 folder for easy access
    let create_link = |target: &std::path::Path, link_name: &str| {
        let link_path = install_dir.join(link_name);
        if link_path.exists() || fs::symlink_metadata(&link_path).is_ok() {
            let _ = fs::remove_file(&link_path);
        }
        let _ = std::os::unix::fs::symlink(target, &link_path);
    };

    create_link(&script_path, "Launch MO2");
    create_link(&kill_script, "Kill MO2 Prefix");
    create_link(&reg_script, "Fix Game Registry");
    log_install("Created shortcuts in MO2 folder: Launch MO2, Kill MO2 Prefix, Fix Game Registry");

    if let Some(prefix_base) = prefix_root.parent() {
        let backlink = prefix_base.join("manager_link");
        if backlink.exists() || fs::symlink_metadata(&backlink).is_ok() {
            let _ = fs::remove_file(&backlink);
        }
        let _ = std::os::unix::fs::symlink(&install_dir, &backlink);
    }

    // Setup Global Instance support
    setup_global_instance_symlink(&prefix_root, &install_dir);

    // Create game folders (prevents crashes for games that require them)
    create_game_folders(&prefix_root);

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
    let config = AppConfig::load();

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

    // For Proton 10+, use GE-Proton10-18 for the entire installation process
    let install_proton = get_install_proton(proton, &ctx);

    // Collision Check
    let prefix_mgr = PrefixManager::new();
    let base_name = format!("mo2_{}", install_name.replace(" ", "_").to_lowercase());
    let unique_name = prefix_mgr.get_unique_prefix_name(&base_name);

    let prefix_root = config.get_prefixes_path().join(&unique_name).join("pfx");

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

    // 2. Install all dependencies (dotnet48, registry, standard deps, dotnet9sdk)
    install_all_dependencies(&prefix_root, &install_proton, &ctx, 0.10, 0.85)?;

    ctx.set_progress(0.88);

    // 3. Brief launch to initialize prefix, then kill
    brief_launch_and_kill(&mo2_exe, &prefix_root, &install_proton, &ctx, "MO2");

    ctx.set_progress(0.92);

    // 4. Generate Scripts (using user's selected proton)
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

    // Generate NXM handler script (for nxmhandler.exe)
    let nxm_handler_exe = existing_path.join("nxmhandler.exe");
    let _nxm_script = if nxm_handler_exe.exists() {
        Some(ScriptGenerator::generate_mo2_nxm_script(
            &prefix_root,
            &nxm_handler_exe,
            &proton.path,
            script_dir,
        )?)
    } else {
        None
    };

    // Create symlinks in the MO2 folder for easy access
    let create_link = |target: &std::path::Path, link_name: &str| {
        let link_path = existing_path.join(link_name);
        if link_path.exists() || fs::symlink_metadata(&link_path).is_ok() {
            let _ = fs::remove_file(&link_path);
        }
        let _ = std::os::unix::fs::symlink(target, &link_path);
    };

    create_link(&script_path, "Launch MO2");
    create_link(&kill_script, "Kill MO2 Prefix");
    create_link(&reg_script, "Fix Game Registry");
    log_install("Created shortcuts in MO2 folder: Launch MO2, Kill MO2 Prefix, Fix Game Registry");

    if let Some(prefix_base) = prefix_root.parent() {
        let backlink = prefix_base.join("manager_link");
        if backlink.exists() || fs::symlink_metadata(&backlink).is_ok() {
            let _ = fs::remove_file(&backlink);
        }
        let _ = std::os::unix::fs::symlink(&existing_path, &backlink);
    }

    // Setup Global Instance support
    setup_global_instance_symlink(&prefix_root, &existing_path);

    // Create game folders (prevents crashes for games that require them)
    create_game_folders(&prefix_root);

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
