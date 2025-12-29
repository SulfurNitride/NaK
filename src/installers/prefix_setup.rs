//! Unified prefix setup for mod managers
//!
//! This module handles all the common dependency installation logic
//! shared between MO2 and Vortex installers.
//!
//! Key approach for .NET Framework installation:
//! 1. Remove mono
//! 2. Set winxp → install dotnet40
//! 3. Set win7 → install dotnet48 + dotnet481 (win7 avoids "already installed" detection)
//! 4. Set win11 for normal operation
//! 5. Install remaining dependencies via winetricks

use std::error::Error;
use std::fs;
use std::path::Path;
use std::process::{Child, Command};

use super::{apply_wine_registry_settings, TaskContext, DOTNET9_SDK_URL, STANDARD_DEPS};
use crate::config::AppConfig;
use crate::logging::{log_download, log_error, log_install, log_warning};
use crate::utils::{detect_steam_path, download_file};
use crate::wine::{ensure_dotnet48_proton, DependencyManager, ProtonInfo};

// .NET Framework installer URLs
const DOTNET40_URL: &str = "https://download.microsoft.com/download/9/5/A/95A9616B-7A37-4AF6-BC36-D6EA96C8DAAE/dotNetFx40_Full_x86_x64.exe";
const DOTNET48_URL: &str = "https://download.visualstudio.microsoft.com/download/pr/7afca223-55d2-470a-8edc-6a1739ae3252/abd170b4b0ec15ad0222a809b761a036/ndp48-x86-x64-allos-enu.exe";
const DOTNET481_URL: &str = "https://download.visualstudio.microsoft.com/download/pr/6f083c7e-bd40-44d4-9e3f-ffba71ec8b09/3951fd5af6098f2c7e8ff5c331a0679c/ndp481-x86-x64-allos-enu.exe";

/// Get the proton to use for .NET Framework installation.
/// Valve Proton versions fail to install dotnet48 properly, so we use GE-Proton10-18 for those.
/// GE-Proton versions work fine with the win7 approach.
pub fn get_install_proton(proton: &ProtonInfo, ctx: &TaskContext) -> ProtonInfo {
    if proton.needs_ge_proton_workaround() {
        log_install(&format!(
            "{} needs GE-Proton10-18 workaround for dotnet installation",
            proton.name
        ));
        ctx.set_status("Preparing GE-Proton10-18 for dotnet installation...".to_string());

        let status_cb = {
            let ctx = ctx.clone();
            move |msg: &str| ctx.log(msg.to_string())
        };

        match ensure_dotnet48_proton(status_cb) {
            Ok(p) => {
                log_install(&format!("Using {} for dotnet installation", p.name));
                p
            }
            Err(e) => {
                log_warning(&format!(
                    "Failed to get GE-Proton10-18: {}, falling back to {}",
                    e, proton.name
                ));
                proton.clone()
            }
        }
    } else {
        log_install(&format!("Using {} for dotnet installation (no workaround needed)", proton.name));
        proton.clone()
    }
}

/// Install all dependencies to a prefix.
/// For Proton 10+: Installs .NET Framework 4.0/4.8/4.8.1 using manual approach.
/// For Proton < 10: Skips .NET Framework installation entirely.
/// Always installs: registry settings, standard deps via winetricks, and .NET 9 SDK.
///
/// # Arguments
/// * `prefix_root` - The prefix path (ending in /pfx)
/// * `install_proton` - The proton to use for installation
/// * `ctx` - Task context for status updates and cancellation
/// * `start_progress` - Starting progress value (0.0-1.0)
/// * `end_progress` - Ending progress value (0.0-1.0)
/// * `user_proton` - The user's originally selected proton (for version checking)
pub fn install_all_dependencies(
    prefix_root: &Path,
    install_proton: &ProtonInfo,
    ctx: &TaskContext,
    start_progress: f32,
    end_progress: f32,
) -> Result<(), Box<dyn Error>> {
    let config = AppConfig::load();
    let dep_mgr = DependencyManager::new(ctx.winetricks_path.clone());
    let tmp_dir = config.get_data_path().join("tmp");
    fs::create_dir_all(&tmp_dir)?;

    // Check if we need to install .NET Framework (only for Proton 10+)
    let needs_dotnet = install_proton.is_proton_10_plus();

    // Calculate progress ranges
    let dotnet_steps = if needs_dotnet { 4 } else { 0 }; // remove_mono, dotnet40, dotnet48, dotnet481
    let total_steps = dotnet_steps + 1 + STANDARD_DEPS.len() + 1; // + registry + deps + dotnet9sdk
    let progress_per_step = (end_progress - start_progress) / total_steps as f32;
    let mut current_step = 0;

    let log_cb = {
        let ctx = ctx.clone();
        move |msg: String| ctx.log(msg)
    };

    // Helper to run winetricks commands
    let run_winetricks = |cmd: &str, ctx: &TaskContext| -> Result<(), Box<dyn Error>> {
        dep_mgr.run_winetricks_command(prefix_root, install_proton, cmd, {
            let ctx = ctx.clone();
            move |msg: String| ctx.log(msg)
        }, ctx.cancel_flag.clone())
    };

    // =========================================================================
    // .NET Framework Installation (Only for Proton 10+)
    // =========================================================================
    if needs_dotnet {
        log_install(&format!(
            "Proton 10+ detected ({}) - installing .NET Framework",
            install_proton.name
        ));

        // 1. Remove Mono and set winxp for dotnet40
        ctx.set_status("Removing Wine Mono...".to_string());
        log_install("Removing Wine Mono for .NET Framework installation");

        if let Err(e) = run_winetricks("remove_mono", ctx) {
            ctx.log(format!("Warning: remove_mono failed: {}", e));
            log_warning(&format!("remove_mono failed: {}", e));
        }

        if ctx.is_cancelled() {
            return Err("Cancelled".into());
        }

        ctx.set_status("Setting Windows XP for dotnet40...".to_string());
        log_install("Setting Windows version to winxp for dotnet40");
        if let Err(e) = run_winetricks("winxp", ctx) {
            log_warning(&format!("Failed to set winxp: {}", e));
        }

        current_step += 1;
        ctx.set_progress(start_progress + (current_step as f32 * progress_per_step));

        if ctx.is_cancelled() {
            return Err("Cancelled".into());
        }

        // 2. Install .NET Framework 4.0
        ctx.set_status("Installing .NET Framework 4.0...".to_string());
        log_install("Installing .NET Framework 4.0");

        let dotnet40_installer = tmp_dir.join("dotNetFx40_Full_x86_x64.exe");
        if !dotnet40_installer.exists() {
            ctx.log("Downloading .NET Framework 4.0...".to_string());
            log_download("Downloading .NET Framework 4.0...");
            download_file(DOTNET40_URL, &dotnet40_installer)?;
            log_download("Downloaded .NET Framework 4.0");
        }

        run_dotnet_installer(prefix_root, install_proton, &dotnet40_installer, ctx)?;
        log_install(".NET Framework 4.0 installed successfully");

        current_step += 1;
        ctx.set_progress(start_progress + (current_step as f32 * progress_per_step));

        if ctx.is_cancelled() {
            return Err("Cancelled".into());
        }

        // 3. Set win7 and install .NET Framework 4.8
        // IMPORTANT: Use win7, NOT win11! The dotnet48 installer detects Windows 11
        // as having .NET 4.8 built-in and skips installation.
        ctx.set_status("Setting Windows 7 for dotnet48...".to_string());
        log_install("Setting Windows version to win7 for dotnet48 (avoids built-in detection)");
        if let Err(e) = run_winetricks("win7", ctx) {
            log_warning(&format!("Failed to set win7: {}", e));
        }

        ctx.set_status("Installing .NET Framework 4.8...".to_string());
        log_install("Installing .NET Framework 4.8");

        let dotnet48_installer = tmp_dir.join("ndp48-x86-x64-allos-enu.exe");
        if !dotnet48_installer.exists() {
            ctx.log("Downloading .NET Framework 4.8...".to_string());
            log_download("Downloading .NET Framework 4.8...");
            download_file(DOTNET48_URL, &dotnet48_installer)?;
            log_download("Downloaded .NET Framework 4.8");
        }

        run_dotnet_installer(prefix_root, install_proton, &dotnet48_installer, ctx)?;
        log_install(".NET Framework 4.8 installed successfully");

        current_step += 1;
        ctx.set_progress(start_progress + (current_step as f32 * progress_per_step));

        if ctx.is_cancelled() {
            return Err("Cancelled".into());
        }

        // 4. Install .NET Framework 4.8.1
        ctx.set_status("Installing .NET Framework 4.8.1...".to_string());
        log_install("Installing .NET Framework 4.8.1");

        let dotnet481_installer = tmp_dir.join("ndp481-x86-x64-allos-enu.exe");
        if !dotnet481_installer.exists() {
            ctx.log("Downloading .NET Framework 4.8.1...".to_string());
            log_download("Downloading .NET Framework 4.8.1...");
            download_file(DOTNET481_URL, &dotnet481_installer)?;
            log_download("Downloaded .NET Framework 4.8.1");
        }

        run_dotnet_installer(prefix_root, install_proton, &dotnet481_installer, ctx)?;
        log_install(".NET Framework 4.8.1 installed successfully");

        current_step += 1;
        ctx.set_progress(start_progress + (current_step as f32 * progress_per_step));

        if ctx.is_cancelled() {
            return Err("Cancelled".into());
        }

        // 5. Set win11 for normal operation
        ctx.set_status("Setting Windows 11 for normal operation...".to_string());
        log_install("Setting Windows version to win11");
        if let Err(e) = run_winetricks("win11", ctx) {
            log_warning(&format!("Failed to set win11: {}", e));
        }
    } else {
        // Proton < 10: Skip .NET Framework installation
        log_install(&format!(
            "Proton < 10 detected ({}) - skipping .NET Framework installation",
            install_proton.name
        ));
        ctx.log("Skipping .NET Framework installation (not needed for Proton < 10)".to_string());
    }

    // =========================================================================
    // Registry Settings
    // =========================================================================
    ctx.set_status("Applying Wine Registry Settings...".to_string());
    ctx.log("Applying Wine Registry Settings...".to_string());
    log_install("Applying Wine registry settings");
    apply_wine_registry_settings(prefix_root, install_proton, &log_cb)?;

    current_step += 1;
    ctx.set_progress(start_progress + (current_step as f32 * progress_per_step));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // 7. Standard Dependencies via winetricks
    // =========================================================================
    let total = STANDARD_DEPS.len();
    for (i, dep) in STANDARD_DEPS.iter().enumerate() {
        if ctx.is_cancelled() {
            return Err("Cancelled".into());
        }

        ctx.set_progress(start_progress + ((current_step + i) as f32 * progress_per_step));

        ctx.set_status(format!(
            "Installing dependency {}/{}: {}...",
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
            prefix_root,
            install_proton,
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

    current_step += total;
    ctx.set_progress(start_progress + (current_step as f32 * progress_per_step));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // 8. .NET 9 SDK
    // =========================================================================
    ctx.set_status("Installing .NET 9 SDK...".to_string());
    ctx.log("Installing .NET 9 SDK...".to_string());
    log_install("Installing .NET 9 SDK...");

    let dotnet9_installer = tmp_dir.join("dotnet9_sdk.exe");

    if !dotnet9_installer.exists() {
        ctx.log("Downloading .NET 9 SDK...".to_string());
        log_download("Downloading .NET 9 SDK...");
        download_file(DOTNET9_SDK_URL, &dotnet9_installer)?;
        log_download("Downloaded .NET 9 SDK");
    }

    let install_proton_bin = install_proton.path.join("proton");
    let compat_data = prefix_root.parent().unwrap_or(prefix_root);
    let steam_path = detect_steam_path();

    ctx.log("Running .NET 9 SDK installer...".to_string());
    match std::process::Command::new(&install_proton_bin)
        .arg("run")
        .arg(&dotnet9_installer)
        .arg("/quiet")
        .arg("/norestart")
        .env("WINEPREFIX", prefix_root)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_path)
        .env("PROTON_NO_XALIA", "1")
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

    ctx.set_progress(end_progress);
    Ok(())
}

/// Run a .NET Framework installer using Proton
fn run_dotnet_installer(
    prefix_root: &Path,
    proton: &ProtonInfo,
    installer_path: &Path,
    ctx: &TaskContext,
) -> Result<(), Box<dyn Error>> {
    let proton_bin = proton.path.join("proton");
    let wineserver = proton.path.join("files/bin/wineserver");
    let compat_data = prefix_root.parent().unwrap_or(prefix_root);
    let steam_path = detect_steam_path();

    ctx.log(format!(
        "Running installer: {}",
        installer_path.file_name().unwrap_or_default().to_string_lossy()
    ));

    // Kill any xalia processes that might be lingering
    kill_xalia_processes();

    let mut child = std::process::Command::new(&proton_bin)
        .arg("run")
        .arg(installer_path)
        .arg("/q")
        .arg("/norestart")
        .env("WINEPREFIX", prefix_root)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_path)
        // Disable xalia - it requires .NET 4.8 to run, causing a chicken-and-egg problem
        .env("PROTON_NO_XALIA", "1")
        .env(
            "LD_LIBRARY_PATH",
            "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu",
        )
        .spawn()?;

    // Poll for completion with cancel check
    loop {
        if ctx.is_cancelled() {
            let _ = child.kill();
            let _ = child.wait();
            // Kill wineserver to stop all Wine processes
            let _ = Command::new(&wineserver)
                .arg("-k")
                .env("WINEPREFIX", prefix_root)
                .status();
            kill_xalia_processes();
            return Err("Installation Cancelled by User".into());
        }

        match child.try_wait() {
            Ok(Some(status)) => {
                if !status.success() {
                    let code = status.code();
                    // Exit code 236 = reboot required, which is expected
                    if code != Some(236) {
                        let msg = format!(
                            "Installer {} exited with code: {:?}",
                            installer_path.file_name().unwrap_or_default().to_string_lossy(),
                            code
                        );
                        log_warning(&msg);
                        ctx.log(format!("Warning: {}", msg));
                    }
                }
                break;
            }
            Ok(None) => {
                // Still running - also kill any xalia that pops up
                kill_xalia_processes();
                std::thread::sleep(std::time::Duration::from_millis(200));
            }
            Err(e) => return Err(e.into()),
        }
    }

    // Final cleanup of any xalia
    kill_xalia_processes();

    // Kill wineserver to simulate reboot (required after .NET installation)
    ctx.log("Simulating reboot (killing wineserver)...".to_string());
    let _ = Command::new(&wineserver)
        .arg("-k")
        .env("WINEPREFIX", prefix_root)
        .status();

    // Wait for wineserver to fully shut down
    std::thread::sleep(std::time::Duration::from_secs(2));

    Ok(())
}

/// Kill any xalia processes that might be running
fn kill_xalia_processes() {
    // Use pkill to kill any xalia.exe processes
    let _ = Command::new("pkill")
        .arg("-f")
        .arg("xalia")
        .status();
}

/// Brief launch of an executable to initialize the prefix, then kill it.
/// This ensures the prefix is properly initialized before the user runs the mod manager.
///
/// # Arguments
/// * `exe_path` - Path to the executable to launch
/// * `prefix_root` - The prefix path (ending in /pfx)
/// * `install_proton` - The proton to use for the brief launch
/// * `ctx` - Task context for status updates
/// * `app_name` - Name of the application (for logging)
pub fn brief_launch_and_kill(
    exe_path: &Path,
    prefix_root: &Path,
    install_proton: &ProtonInfo,
    ctx: &TaskContext,
    app_name: &str,
) {
    ctx.set_status("Initializing prefix (brief launch)...".to_string());
    log_install(&format!(
        "Launching {} briefly to initialize prefix...",
        app_name
    ));

    let compat_data = prefix_root.parent().unwrap_or(prefix_root);
    let steam_path = detect_steam_path();

    let mut child = std::process::Command::new(install_proton.path.join("proton"))
        .arg("run")
        .arg(exe_path)
        .env("WINEPREFIX", prefix_root)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_path)
        .env("PROTON_NO_XALIA", "1")
        .spawn();

    match &mut child {
        Ok(process) => {
            // Wait 8 seconds
            std::thread::sleep(std::time::Duration::from_secs(8));
            ctx.set_status("Killing prefix after initialization...".to_string());
            log_install("Killing prefix after brief launch");
            let _ = process.kill();
            let _ = process.wait();

            // Also kill any remaining wine processes in prefix
            let _ = std::process::Command::new(install_proton.path.join("files/bin/wineserver"))
                .arg("-k")
                .env("WINEPREFIX", prefix_root)
                .status();
        }
        Err(e) => {
            log_warning(&format!(
                "Failed to launch {} for initialization: {}",
                app_name, e
            ));
        }
    }
}

// =============================================================================
// DPI Configuration
// =============================================================================

/// Common DPI presets with their percentage labels
pub const DPI_PRESETS: &[(u32, &str)] = &[
    (96, "100%"),
    (120, "125%"),
    (144, "150%"),
    (192, "200%"),
];

/// Apply DPI setting to a Wine prefix via registry
/// Uses: HKCU\Control Panel\Desktop\LogPixels
pub fn apply_dpi(
    prefix_root: &Path,
    proton: &ProtonInfo,
    dpi_value: u32,
) -> Result<(), Box<dyn Error>> {
    log_install(&format!("Applying DPI {} to prefix", dpi_value));

    let wine_bin = proton.path.join("files/bin/wine");

    let status = Command::new(&wine_bin)
        .arg("reg")
        .arg("add")
        .arg(r"HKCU\Control Panel\Desktop")
        .arg("/v")
        .arg("LogPixels")
        .arg("/t")
        .arg("REG_DWORD")
        .arg("/d")
        .arg(dpi_value.to_string())
        .arg("/f")
        .env("WINEPREFIX", prefix_root)
        .env("PROTON_NO_XALIA", "1")
        .status()?;

    if !status.success() {
        return Err(format!("Failed to apply DPI setting: exit code {:?}", status.code()).into());
    }

    log_install(&format!("DPI {} applied successfully", dpi_value));
    Ok(())
}

/// Get current DPI setting from a Wine prefix
#[allow(dead_code)]
pub fn get_current_dpi(prefix_root: &Path, proton: &ProtonInfo) -> Option<u32> {
    let proton_bin = proton.path.join("proton");
    let compat_data = prefix_root.parent().unwrap_or(prefix_root);
    let steam_path = detect_steam_path();

    let output = Command::new(&proton_bin)
        .arg("run")
        .arg("reg")
        .arg("query")
        .arg(r"HKCU\Control Panel\Desktop")
        .arg("/v")
        .arg("LogPixels")
        .env("WINEPREFIX", prefix_root)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_path)
        .env("PROTON_NO_XALIA", "1")
        .output()
        .ok()?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    // Parse output like: "    LogPixels    REG_DWORD    0x60" (0x60 = 96)
    for line in stdout.lines() {
        if line.contains("LogPixels") {
            // Find the hex value
            if let Some(hex_part) = line.split_whitespace().last() {
                if let Some(stripped) = hex_part.strip_prefix("0x") {
                    if let Ok(val) = u32::from_str_radix(stripped, 16) {
                        return Some(val);
                    }
                }
            }
        }
    }
    None
}

/// Launch a test application (winecfg, regedit, notepad, control) and return its PID
pub fn launch_dpi_test_app(
    prefix_root: &Path,
    proton: &ProtonInfo,
    app_name: &str,
) -> Result<Child, Box<dyn Error>> {
    let wine_bin = proton.path.join("files/bin/wine");

    log_install(&format!(
        "Launching {} with wine={:?} prefix={:?}",
        app_name, wine_bin, prefix_root
    ));

    if !wine_bin.exists() {
        return Err(format!("Wine binary not found: {:?}", wine_bin).into());
    }

    if !prefix_root.exists() {
        return Err(format!("Prefix not found: {:?}", prefix_root).into());
    }

    let child = Command::new(&wine_bin)
        .arg(app_name)
        .env("WINEPREFIX", prefix_root)
        .env("PROTON_NO_XALIA", "1")
        .spawn()?;

    Ok(child)
}

/// Kill the wineserver for a prefix (terminates all Wine processes in that prefix)
pub fn kill_wineserver(prefix_root: &Path, proton: &ProtonInfo) {
    log_install("Killing wineserver for prefix");

    let wineserver_bin = proton.path.join("files/bin/wineserver");

    let _ = Command::new(&wineserver_bin)
        .arg("-k")
        .env("WINEPREFIX", prefix_root)
        .status();
}

/// Kill specific processes by PID
#[allow(dead_code)]
pub fn kill_processes(pids: &[u32]) {
    for pid in pids {
        let _ = Command::new("kill")
            .arg("-9")
            .arg(pid.to_string())
            .status();
    }
}

// Enderal Special Edition config files (embedded in binary)
const ENDERAL_SE_INI: &str = include_str!("../../resources/game_configs/enderal_se/Enderal.ini");
const ENDERAL_SE_PREFS_INI: &str =
    include_str!("../../resources/game_configs/enderal_se/EnderalPrefs.ini");

/// Create game-specific folders in the Wine prefix
///
/// Some games crash on startup if their Documents/My Games folder doesn't exist.
/// This creates the necessary folder structure for all supported Bethesda/SureAI games.
/// Also copies premade config files for games that need them (e.g., Enderal SE).
pub fn create_game_folders(prefix_root: &Path) {
    let users_dir = prefix_root.join("drive_c/users");
    let mut username = "steamuser".to_string();

    // Detect the correct user folder
    if let Ok(entries) = fs::read_dir(&users_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name != "Public" && name != "root" {
                username = name;
                break;
            }
        }
    }

    let user_dir = users_dir.join(&username);
    let documents_dir = user_dir.join("Documents");
    let my_games_dir = documents_dir.join("My Games");
    let appdata_local = user_dir.join("AppData/Local");

    // Games that need Documents/My Games/<name>/
    let my_games_folders = [
        "Enderal",
        "Enderal Special Edition",
        "Fallout3",
        "Fallout4",
        "Fallout4VR",
        "FalloutNV",
        "Morrowind",
        "Oblivion",
        "Skyrim",
        "Skyrim Special Edition",
        "Skyrim VR",
        "Starfield",
    ];

    // Games that also need AppData/Local/<name>/
    let appdata_folders = [
        "Fallout3",
        "Fallout4",
        "FalloutNV",
        "Oblivion",
        "Skyrim",
        "Skyrim Special Edition",
    ];

    // Create My Games folders
    for game in &my_games_folders {
        let game_dir = my_games_dir.join(game);
        if !game_dir.exists() {
            if let Err(e) = fs::create_dir_all(&game_dir) {
                log_warning(&format!("Failed to create My Games/{}: {}", game, e));
            }
        }
    }

    // Create AppData/Local folders
    for game in &appdata_folders {
        let game_dir = appdata_local.join(game);
        if !game_dir.exists() {
            if let Err(e) = fs::create_dir_all(&game_dir) {
                log_warning(&format!("Failed to create AppData/Local/{}: {}", game, e));
            }
        }
    }

    // Create "My Documents" symlink if it doesn't exist (some games expect this)
    let my_documents_link = user_dir.join("My Documents");
    if !my_documents_link.exists() && fs::symlink_metadata(&my_documents_link).is_err() {
        // Create relative symlink: "My Documents" -> "Documents"
        if let Err(e) = std::os::unix::fs::symlink("Documents", &my_documents_link) {
            log_warning(&format!("Failed to create My Documents symlink: {}", e));
        }
    }

    // Copy Enderal Special Edition config files
    // These fix the Enderal Launcher not working properly and set sensible defaults
    let enderal_se_dir = my_games_dir.join("Enderal Special Edition");
    if enderal_se_dir.exists() {
        let enderal_ini = enderal_se_dir.join("Enderal.ini");
        let enderal_prefs_ini = enderal_se_dir.join("EnderalPrefs.ini");

        if !enderal_ini.exists() {
            if let Err(e) = fs::write(&enderal_ini, ENDERAL_SE_INI) {
                log_warning(&format!("Failed to write Enderal.ini: {}", e));
            }
        }
        if !enderal_prefs_ini.exists() {
            if let Err(e) = fs::write(&enderal_prefs_ini, ENDERAL_SE_PREFS_INI) {
                log_warning(&format!("Failed to write EnderalPrefs.ini: {}", e));
            }
        }
    }

    log_install("Created game folders in prefix (Documents/My Games, AppData/Local)");
}
