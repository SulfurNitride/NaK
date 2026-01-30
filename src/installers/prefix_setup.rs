//! Unified prefix setup for MO2
//!
//! This module handles all the dependency installation logic.
//!
//! Key approach (ORDER MATTERS):
//! 1. Install dependencies via winetricks (handles wineboot internally)
//! 2. Install custom dotnet runtimes (dotnet9sdk, dotnetdesktop10)
//! 3. Auto-detect installed games and apply registry entries
//! 4. Apply Wine registry settings (LAST - after prefix is fully set up)

use std::error::Error;
use std::fs;
use std::path::Path;
use std::process::{Child, Command};

use super::{apply_wine_registry_settings, TaskContext};
use crate::config::AppConfig;
use crate::deps::{install_standard_deps, STANDARD_VERBS};
use crate::game_finder::{detect_all_games, Game};
use crate::logging::{log_install, log_warning};
use crate::steam::{detect_steam_path_checked, SteamProton};

// =============================================================================
// Constants
// =============================================================================

/// .NET 9 SDK download URL
const DOTNET9_SDK_URL: &str = "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.310/dotnet-sdk-9.0.310-win-x64.exe";

/// .NET Desktop Runtime 10 download URL
const DOTNET_DESKTOP10_URL: &str = "https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/10.0.2/windowsdesktop-runtime-10.0.2-win-x64.exe";

/// Install all dependencies to a prefix.
///
/// Order: proton init → winetricks → custom dotnet → game detection → registry → win10 → dotnet fixes
///
/// # Arguments
/// * `app_id` - Steam AppID (used for registry operations)
pub fn install_all_dependencies(
    prefix_root: &Path,
    install_proton: &SteamProton,
    ctx: &TaskContext,
    start_progress: f32,
    end_progress: f32,
    app_id: u32,
) -> Result<(), Box<dyn Error>> {
    fs::create_dir_all(AppConfig::get_tmp_path())?;

    // Progress distribution
    let init_end = start_progress + (end_progress - start_progress) * 0.10;
    let winetricks_end = start_progress + (end_progress - start_progress) * 0.50;
    let dotnet_end = start_progress + (end_progress - start_progress) * 0.65;
    let games_end = start_progress + (end_progress - start_progress) * 0.75;

    // =========================================================================
    // 0. Initialize prefix with Proton wrapper (creates proper prefix structure)
    // =========================================================================
    ctx.set_status("Initializing Wine prefix with Proton...".to_string());
    ctx.log("Initializing Wine prefix with Proton...".to_string());
    log_install("Running proton wineboot to initialize prefix");

    if let Err(e) = initialize_prefix_with_proton(prefix_root, install_proton, app_id) {
        ctx.log(format!("Warning: Proton prefix init failed: {}", e));
        log_warning(&format!("Proton prefix init failed: {}", e));
        // Continue anyway - winetricks might still work
    }

    ctx.set_progress(init_end);

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // 1. Standard Dependencies via Winetricks
    // =========================================================================
    ctx.set_status("Installing dependencies via winetricks...".to_string());
    ctx.log(format!(
        "Installing {} dependencies via winetricks: {}",
        STANDARD_VERBS.len(),
        STANDARD_VERBS.join(", ")
    ));
    log_install(&format!("Running winetricks with {} verbs", STANDARD_VERBS.len()));

    let winetricks_log_cb = {
        let ctx = ctx.clone();
        move |msg: String| {
            ctx.log(msg.clone());
            ctx.set_status(msg);
        }
    };

    if let Err(e) = install_standard_deps(prefix_root, install_proton, winetricks_log_cb) {
        let msg = format!("Winetricks installation had issues: {}", e);
        ctx.log(format!("Warning: {}", msg));
        log_warning(&msg);
    }

    ctx.set_progress(winetricks_end);

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // 2. Custom .NET Runtimes (not in winetricks yet)
    // =========================================================================
    ctx.set_status("Installing .NET 9 SDK...".to_string());
    ctx.log("Installing .NET 9 SDK...".to_string());

    if let Err(e) = install_dotnet_runtime(prefix_root, install_proton, DOTNET9_SDK_URL, "dotnet-sdk-9") {
        ctx.log(format!("Warning: .NET 9 SDK install failed: {}", e));
        log_warning(&format!(".NET 9 SDK install failed: {}", e));
    }

    ctx.set_status("Installing .NET Desktop Runtime 10...".to_string());
    ctx.log("Installing .NET Desktop Runtime 10...".to_string());

    if let Err(e) = install_dotnet_runtime(prefix_root, install_proton, DOTNET_DESKTOP10_URL, "dotnet-desktop-10") {
        ctx.log(format!("Warning: .NET Desktop 10 install failed: {}", e));
        log_warning(&format!(".NET Desktop 10 install failed: {}", e));
    }

    ctx.set_progress(dotnet_end);

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // 3. Auto-detect and register installed games
    // =========================================================================
    ctx.set_status("Detecting installed games...".to_string());
    ctx.log("Auto-detecting installed Steam games...".to_string());
    log_install("Auto-detecting installed games for registry");

    let game_log_cb = {
        let ctx = ctx.clone();
        move |msg: String| ctx.log(msg)
    };
    auto_apply_game_registries(prefix_root, install_proton, &game_log_cb, Some(app_id));

    ctx.set_progress(games_end);

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // 4. Registry Settings (after prefix is fully initialized)
    // =========================================================================
    ctx.set_status("Applying Wine Registry Settings...".to_string());
    ctx.log("Applying Wine Registry Settings...".to_string());
    log_install("Applying Wine registry settings");

    let log_cb = {
        let ctx = ctx.clone();
        move |msg: String| ctx.log(msg)
    };
    apply_wine_registry_settings(prefix_root, install_proton, &log_cb, Some(app_id))?;

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // 5. Set Windows 10 Mode
    // =========================================================================
    ctx.set_status("Setting Windows 10 mode...".to_string());
    ctx.log("Setting Windows 10 mode...".to_string());
    log_install("Setting Windows 10 mode via winetricks");

    if let Err(e) = set_windows_10_mode(prefix_root, install_proton) {
        ctx.log(format!("Warning: Failed to set Windows 10 mode: {}", e));
        log_warning(&format!("Failed to set Windows 10 mode: {}", e));
    }

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    ctx.set_progress(end_progress);
    ctx.set_status("Dependencies installed".to_string());
    Ok(())
}

/// Install a .NET runtime via direct exe download and wine execution
fn install_dotnet_runtime(
    prefix_root: &Path,
    proton: &SteamProton,
    url: &str,
    name: &str,
) -> Result<(), Box<dyn Error>> {
    let cache_dir = AppConfig::get_default_cache_dir();
    fs::create_dir_all(&cache_dir)?;

    let filename = url.split('/').next_back().unwrap_or("dotnet-installer.exe");
    let installer_path = cache_dir.join(filename);

    // Download if not cached
    if !installer_path.exists() {
        log_install(&format!("Downloading {}...", name));
        let response = ureq::get(url)
            .set("User-Agent", "NaK-Rust")
            .call()
            .map_err(|e| format!("Failed to download {}: {}", name, e))?;

        let mut file = fs::File::create(&installer_path)?;
        std::io::copy(&mut response.into_reader(), &mut file)?;
    }

    // Run installer with wine
    let Some(wine_bin) = proton.wine_binary() else {
        return Err("Wine binary not found".into());
    };

    log_install(&format!("Running {} installer...", name));

    let status = Command::new(&wine_bin)
        .arg(&installer_path)
        .arg("/install")
        .arg("/quiet")
        .arg("/norestart")
        .env("WINEPREFIX", prefix_root)
        .env("WINEDLLOVERRIDES", "mshtml=d")
        .status()?;

    if !status.success() {
        return Err(format!("{} installer exited with code {:?}", name, status.code()).into());
    }

    log_install(&format!("{} installed successfully", name));
    Ok(())
}

/// Initialize prefix with Proton wrapper
///
/// Runs `proton run wineboot -u` to properly initialize the prefix with all
/// the Steam/Proton environment variables. This creates a proper prefix
/// structure that Steam recognizes.
fn initialize_prefix_with_proton(
    prefix_root: &Path,
    proton: &SteamProton,
    app_id: u32,
) -> Result<(), Box<dyn Error>> {
    // Find the proton wrapper script (not the wine binary)
    let proton_script = proton.path.join("proton");
    if !proton_script.exists() {
        return Err(format!("Proton wrapper script not found at {:?}", proton_script).into());
    }

    // Get Steam root path
    let steam_root = detect_steam_path_checked()
        .ok_or("Could not find Steam installation")?;

    // The compatdata path is the PARENT of the pfx directory
    let compat_data_path = prefix_root.parent()
        .ok_or("Could not determine compatdata path")?;

    log_install(&format!("Initializing prefix with proton wrapper: {:?}", proton_script));
    log_install(&format!("STEAM_COMPAT_DATA_PATH={:?}", compat_data_path));

    let status = Command::new(&proton_script)
        .args(["run", "wineboot", "-u"])
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", &steam_root)
        .env("STEAM_COMPAT_DATA_PATH", compat_data_path)
        .env("SteamAppId", app_id.to_string())
        .env("SteamGameId", app_id.to_string())
        .env("DISPLAY", "") // Suppress GUI
        .env("WAYLAND_DISPLAY", "") // Suppress GUI
        .env("WINEDEBUG", "-all")
        .env("WINEDLLOVERRIDES", "msdia80.dll=n;conhost.exe=d;cmd.exe=d")
        .status()?;

    if !status.success() {
        return Err(format!("proton wineboot failed with exit code: {:?}", status.code()).into());
    }

    // Give it a moment for files to land
    std::thread::sleep(std::time::Duration::from_secs(2));

    // Verify prefix was created
    if prefix_root.exists() {
        log_install("Proton prefix initialized successfully");
        Ok(())
    } else {
        Err("Prefix directory not created after wineboot".into())
    }
}

/// Set Windows 10 mode for the prefix using winetricks
///
/// This should be called AFTER all components are installed.
/// Sets the Windows version to Windows 10 which is required for MO2 to work properly.
fn set_windows_10_mode(
    prefix_root: &Path,
    proton: &SteamProton,
) -> Result<(), Box<dyn Error>> {
    use crate::deps::ensure_winetricks;

    let winetricks_path = ensure_winetricks()?;

    let Some(wine_bin) = proton.wine_binary() else {
        return Err("Wine binary not found".into());
    };

    let Some(wineserver_bin) = proton.wineserver_binary() else {
        return Err("Wineserver binary not found".into());
    };

    log_install("Running winetricks win10...");

    let status = Command::new(&winetricks_path)
        .arg("-q")
        .arg("win10")
        .env("WINE", &wine_bin)
        .env("WINESERVER", &wineserver_bin)
        .env("WINEPREFIX", prefix_root)
        .status()?;

    if !status.success() {
        return Err(format!("winetricks win10 failed with exit code: {:?}", status.code()).into());
    }

    log_install("Windows 10 mode set successfully");
    Ok(())
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
pub fn apply_dpi(
    prefix_root: &Path,
    proton: &SteamProton,
    dpi_value: u32,
) -> Result<(), Box<dyn Error>> {
    log_install(&format!("Applying DPI {} to prefix", dpi_value));

    let wine_bin = proton.wine_binary().ok_or_else(|| {
        format!("Wine binary not found for Proton '{}'", proton.name)
    })?;

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
        .env("PROTON_USE_XALIA", "0")
        .status()?;

    if !status.success() {
        return Err(format!("Failed to apply DPI setting: exit code {:?}", status.code()).into());
    }

    log_install(&format!("DPI {} applied successfully", dpi_value));
    Ok(())
}

/// Launch a test application (winecfg, regedit, notepad, control) and return its PID
pub fn launch_dpi_test_app(
    prefix_root: &Path,
    proton: &SteamProton,
    app_name: &str,
) -> Result<Child, Box<dyn Error>> {
    let wine_bin = proton.wine_binary().ok_or_else(|| {
        format!("Wine binary not found for Proton '{}'", proton.name)
    })?;

    log_install(&format!(
        "Launching {} with wine={:?} prefix={:?}",
        app_name, wine_bin, prefix_root
    ));

    if !prefix_root.exists() {
        return Err(format!("Prefix not found: {:?}", prefix_root).into());
    }

    let child = Command::new(&wine_bin)
        .arg(app_name)
        .env("WINEPREFIX", prefix_root)
        .env("PROTON_USE_XALIA", "0")
        .spawn()?;

    Ok(child)
}

/// Kill the wineserver for a prefix (terminates all Wine processes in that prefix)
/// Kill the wineserver for a prefix (terminates all Wine processes in that prefix)
pub fn kill_wineserver(prefix_root: &Path, proton: &SteamProton) {
    log_install("Killing wineserver for prefix");

    let Some(wineserver_bin) = proton.wineserver_binary() else {
        log_install("Wineserver binary not found, skipping kill");
        return;
    };

    let _ = Command::new(&wineserver_bin)
        .arg("-k")
        .env("WINEPREFIX", prefix_root)
        .status();
}

// ============================================================================
// Game Registry Detection (uses game_finder module)
// ============================================================================

/// Auto-detect installed games and apply registry entries
///
/// This uses the game_finder module to detect installed games across all
/// supported launchers (Steam, Heroic, Bottles) and automatically adds
/// the registry entries so mod managers can detect them.
pub fn auto_apply_game_registries(
    prefix_path: &Path,
    proton: &SteamProton,
    log_callback: &impl Fn(String),
    _app_id: Option<u32>,
) {
    let Some(wine_bin) = proton.wine_binary() else {
        log_warning("Wine binary not found, skipping game registry auto-detection");
        return;
    };

    // Use the new game_finder module to detect all games
    let scan_result = detect_all_games();
    let mut applied_count = 0;

    for game in &scan_result.games {
        // Only process games that have registry info
        let (Some(reg_path), Some(reg_value)) = (&game.registry_path, &game.registry_value) else {
            continue;
        };

        // Apply registry for this game
        if apply_game_registry(
            prefix_path,
            &wine_bin,
            game,
            reg_path,
            reg_value,
            log_callback,
        ) {
            applied_count += 1;
        }
    }

    if applied_count > 0 {
        log_callback(format!("Auto-configured {} game(s) in registry", applied_count));
        log_install(&format!("Auto-applied registry for {} detected game(s)", applied_count));
    }
}

/// Apply registry entry for a single game
fn apply_game_registry(
    prefix_path: &Path,
    wine_bin: &Path,
    game: &Game,
    reg_path: &str,
    reg_value: &str,
    log_callback: &impl Fn(String),
) -> bool {
    log_callback(format!("Found {}, applying registry...", game.name));

    // Convert Linux path to Wine Z: drive path with escaped backslashes for .reg file
    let linux_path = game.install_path.to_string_lossy();
    let wine_path_reg = format!("Z:{}", linux_path.replace('/', "\\\\"));

    // Create .reg file content
    let reg_content = format!(
        r#"Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\{}]
"{}"="{}"

[HKEY_LOCAL_MACHINE\SOFTWARE\Wow6432Node\{}]
"{}"="{}"
"#,
        reg_path,
        reg_value,
        wine_path_reg,
        reg_path.strip_prefix("Software\\").unwrap_or(reg_path),
        reg_value,
        wine_path_reg,
    );

    // Write temp .reg file
    let tmp_dir = AppConfig::get_tmp_path();
    let reg_file = tmp_dir.join(format!("game_reg_{}.reg", game.app_id));

    if let Err(e) = fs::write(&reg_file, &reg_content) {
        log_warning(&format!("Failed to write registry file for {}: {}", game.name, e));
        return false;
    }

    // Apply registry
    let status = Command::new(wine_bin)
        .arg("regedit")
        .arg(&reg_file)
        .env("WINEPREFIX", prefix_path)
        .env("WINEDLLOVERRIDES", "mshtml=d")
        .env("PROTON_USE_XALIA", "0")
        .status();

    let _ = fs::remove_file(&reg_file);

    match status {
        Ok(s) if s.success() => {
            log_install(&format!("Applied registry for {} -> {:?}", game.name, game.install_path));
            true
        }
        Ok(s) => {
            log_warning(&format!(
                "Registry for {} may have failed (exit code: {:?})",
                game.name,
                s.code()
            ));
            false
        }
        Err(e) => {
            log_warning(&format!("Failed to apply registry for {}: {}", game.name, e));
            false
        }
    }
}

