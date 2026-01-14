//! Unified prefix setup for mod managers
//!
//! This module handles all the common dependency installation logic
//! shared between MO2 and Vortex installers.
//!
//! Key approach (Jackify-style):
//! 1. Install dependencies via native deps system (vcrun2022, physx, etc.)
//! 2. Apply universal dotnet4.x registry fixes (*mscoree=native, OnlyUseLatestCLR=1)
//!
//! This approach replaces installing dotnet40/dotnet48/etc which caused Wine version
//! mismatch issues. The registry fixes tell Wine to use native .NET runtime.

use std::error::Error;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};

use super::{apply_wine_registry_settings, TaskContext};
use crate::config::AppConfig;
use crate::deps::wine_utils::apply_universal_dotnet_fixes;
use crate::deps::{DepInstallContext, NativeDependencyManager, STANDARD_DEPS};
use crate::logging::{log_error, log_install, log_warning};
use crate::steam::{detect_steam_path_checked, SteamProton};

// =============================================================================
// Constants
// =============================================================================

/// Default Wine prefix username (Proton always uses this)
const PREFIX_USERNAME: &str = "steamuser";

/// Create a DepInstallContext from TaskContext
fn create_dep_context(
    prefix: &Path,
    proton: &SteamProton,
    ctx: &TaskContext,
) -> DepInstallContext {
    let log_ctx = ctx.clone();
    DepInstallContext::new(
        prefix.to_path_buf(),
        proton.clone(),
        move |msg| log_ctx.log(msg),
        ctx.cancel_flag.clone(),
    )
}

/// Install all dependencies to a prefix using Jackify-style approach.
///
/// Installs: registry settings, standard deps (vcrun2022, physx, etc.),
/// and universal dotnet4.x registry fixes.
///
/// This approach replaces installing dotnet40/dotnet48/etc which caused Wine version
/// mismatch issues. The registry fixes tell Wine to use native .NET runtime.
pub fn install_all_dependencies(
    prefix_root: &Path,
    install_proton: &SteamProton,
    ctx: &TaskContext,
    start_progress: f32,
    end_progress: f32,
) -> Result<(), Box<dyn Error>> {
    fs::create_dir_all(AppConfig::get_tmp_path())?;

    // Create NativeDependencyManager for all dep operations
    let dep_ctx = create_dep_context(prefix_root, install_proton, ctx);
    let dep_mgr = NativeDependencyManager::new(dep_ctx);

    // Calculate progress ranges: registry + deps + dotnet_fixes
    let total_steps = 1 + STANDARD_DEPS.len() + 1; // registry + deps + dotnet_fixes
    let progress_per_step = (end_progress - start_progress) / total_steps as f32;
    let mut current_step = 0;

    // =========================================================================
    // Registry Settings
    // =========================================================================
    ctx.set_status("Applying Wine Registry Settings...".to_string());
    ctx.log("Applying Wine Registry Settings...".to_string());
    log_install("Applying Wine registry settings");

    let log_cb = {
        let ctx = ctx.clone();
        move |msg: String| ctx.log(msg)
    };
    apply_wine_registry_settings(prefix_root, install_proton, &log_cb)?;

    current_step += 1;
    ctx.set_progress(start_progress + (current_step as f32 * progress_per_step));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // Auto-detect and register installed games
    // =========================================================================
    ctx.set_status("Detecting installed games...".to_string());
    ctx.log("Auto-detecting installed Steam games...".to_string());
    log_install("Auto-detecting installed games for registry");

    let game_log_cb = {
        let ctx = ctx.clone();
        move |msg: String| ctx.log(msg)
    };
    auto_apply_game_registries(prefix_root, install_proton, &game_log_cb);

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // Standard Dependencies via Native System (NO WINETRICKS!)
    // =========================================================================
    // Critical dependencies that MUST succeed - failure stops the entire installation
    const CRITICAL_DEPS: &[&str] = &["vcrun2022"];

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
            dep.name
        ));
        log_install(&format!(
            "Installing dependency {}/{}: {}",
            i + 1,
            total,
            dep.name
        ));

        // Install using NativeDependencyManager
        if let Err(e) = dep_mgr.install_dep(dep) {
            let is_critical = CRITICAL_DEPS.contains(&dep.id);

            if is_critical {
                // Critical dependency failed - stop the entire installation
                let err_msg = format!(
                    "Critical dependency '{}' failed to install: {}. Installation cannot continue.",
                    dep.name, e
                );
                ctx.set_status(format!("ERROR: {}", err_msg));
                ctx.log(format!("ERROR: {}", err_msg));
                log_error(&err_msg);
                return Err(err_msg.into());
            } else {
                // Non-critical dependency failed - warn and continue
                ctx.set_status(format!(
                    "Warning: Failed to install {}: {} (Continuing...)",
                    dep.id, e
                ));
                ctx.log(format!("Warning: Failed to install {}: {}", dep.id, e));
                log_warning(&format!("Failed to install {}: {}", dep.id, e));
            }
        } else {
            log_install(&format!("Dependency {} installed successfully", dep.id));
        }
    }

    current_step += total;
    ctx.set_progress(start_progress + (current_step as f32 * progress_per_step));

    if ctx.is_cancelled() {
        return Err("Cancelled".into());
    }

    // =========================================================================
    // Universal dotnet4.x Registry Fixes (Jackify-style)
    // =========================================================================
    // Apply AFTER wine component installation to prevent overwrites.
    // This replaces the need to install dotnet40/dotnet48/etc.
    ctx.set_status("Applying dotnet4.x compatibility fixes...".to_string());
    log_install("Applying universal dotnet4.x compatibility registry fixes");

    let fix_ctx = create_dep_context(prefix_root, install_proton, ctx);
    if let Err(e) = apply_universal_dotnet_fixes(&fix_ctx) {
        // Don't fail installation, just warn - the fixes are best-effort
        ctx.log(format!("Warning: dotnet fixes failed: {}", e));
        log_warning(&format!("dotnet4.x registry fixes failed: {}", e));
    }

    ctx.set_progress(end_progress);
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
        .env("PROTON_USE_XALIA", "0")
        .spawn()?;

    Ok(child)
}

/// Kill the wineserver for a prefix (terminates all Wine processes in that prefix)
pub fn kill_wineserver(prefix_root: &Path, proton: &SteamProton) {
    log_install("Killing wineserver for prefix");

    let wineserver_bin = proton.path.join("files/bin/wineserver");

    let _ = Command::new(&wineserver_bin)
        .arg("-k")
        .env("WINEPREFIX", prefix_root)
        .status();
}

// Enderal Special Edition config files (embedded in binary)
const ENDERAL_SE_INI: &str = include_str!("../../resources/game_configs/enderal_se/Enderal.ini");
const ENDERAL_SE_PREFS_INI: &str =
    include_str!("../../resources/game_configs/enderal_se/EnderalPrefs.ini");

// ============================================================================
// Bethesda Game Mapping
// ============================================================================

/// Mapping of My Games folder name to Steam App ID
const BETHESDA_GAMES: &[(&str, &str)] = &[
    // (My Games folder name, Steam App ID)
    ("Enderal", "933480"),                    // Enderal: Forgotten Stories
    ("Enderal Special Edition", "976620"),    // Enderal: Forgotten Stories SE
    ("Fallout3", "22300"),                    // Fallout 3 (also 22370 for GOTY)
    ("Fallout4", "377160"),                   // Fallout 4
    ("Fallout4VR", "611660"),                 // Fallout 4 VR
    ("FalloutNV", "22380"),                   // Fallout: New Vegas
    ("Morrowind", "22320"),                   // Morrowind
    ("Oblivion", "22330"),                    // Oblivion
    ("Skyrim", "72850"),                      // Skyrim (original)
    ("Skyrim Special Edition", "489830"),     // Skyrim SE/AE
    ("Skyrim VR", "611670"),                  // Skyrim VR
    ("Starfield", "1716740"),                 // Starfield
];

/// Games that need AppData/Local/<name>/
const APPDATA_GAMES: &[&str] = &[
    "Fallout3",
    "Fallout4",
    "FalloutNV",
    "Oblivion",
    "Skyrim",
    "Skyrim Special Edition",
];

// ============================================================================
// Game Registry Configuration (for auto-detection)
// ============================================================================

/// Game registry configuration for auto-detection
struct GameRegistryConfig {
    /// Display name
    name: &'static str,
    /// Steam App ID
    app_id: &'static str,
    /// Registry key path (under HKLM\Software\)
    reg_path: &'static str,
    /// Registry value name for install path
    value_name: &'static str,
    /// Expected folder name in steamapps/common/
    steam_folder: &'static str,
}

/// All supported games with their registry configurations
const GAME_REGISTRY_CONFIGS: &[GameRegistryConfig] = &[
    GameRegistryConfig {
        name: "Enderal",
        app_id: "933480",
        reg_path: r"Software\SureAI\Enderal",
        value_name: "Install_Path",
        steam_folder: "Enderal",
    },
    GameRegistryConfig {
        name: "Enderal Special Edition",
        app_id: "976620",
        reg_path: r"Software\SureAI\Enderal SE",
        value_name: "installed path",
        steam_folder: "Enderal Special Edition",
    },
    GameRegistryConfig {
        name: "Fallout 3",
        app_id: "22300",
        reg_path: r"Software\Bethesda Softworks\Fallout3",
        value_name: "Installed Path",
        steam_folder: "Fallout 3",
    },
    GameRegistryConfig {
        name: "Fallout 4",
        app_id: "377160",
        reg_path: r"Software\Bethesda Softworks\Fallout4",
        value_name: "Installed Path",
        steam_folder: "Fallout 4",
    },
    GameRegistryConfig {
        name: "Fallout 4 VR",
        app_id: "611660",
        reg_path: r"Software\Bethesda Softworks\Fallout 4 VR",
        value_name: "Installed Path",
        steam_folder: "Fallout 4 VR",
    },
    GameRegistryConfig {
        name: "Fallout New Vegas",
        app_id: "22380",
        reg_path: r"Software\Bethesda Softworks\FalloutNV",
        value_name: "Installed Path",
        steam_folder: "Fallout New Vegas",
    },
    GameRegistryConfig {
        name: "Morrowind",
        app_id: "22320",
        reg_path: r"Software\Bethesda Softworks\Morrowind",
        value_name: "Installed Path",
        steam_folder: "Morrowind",
    },
    GameRegistryConfig {
        name: "Oblivion",
        app_id: "22330",
        reg_path: r"Software\Bethesda Softworks\Oblivion",
        value_name: "Installed Path",
        steam_folder: "Oblivion",
    },
    GameRegistryConfig {
        name: "Skyrim",
        app_id: "72850",
        reg_path: r"Software\Bethesda Softworks\Skyrim",
        value_name: "Installed Path",
        steam_folder: "Skyrim",
    },
    GameRegistryConfig {
        name: "Skyrim Special Edition",
        app_id: "489830",
        reg_path: r"Software\Bethesda Softworks\Skyrim Special Edition",
        value_name: "Installed Path",
        steam_folder: "Skyrim Special Edition",
    },
    GameRegistryConfig {
        name: "Skyrim VR",
        app_id: "611670",
        reg_path: r"Software\Bethesda Softworks\Skyrim VR",
        value_name: "Installed Path",
        steam_folder: "Skyrim VR",
    },
    GameRegistryConfig {
        name: "Starfield",
        app_id: "1716740",
        reg_path: r"Software\Bethesda Softworks\Starfield",
        value_name: "Installed Path",
        steam_folder: "Starfield",
    },
];

/// Find the installation path for a game in Steam library folders
fn find_steam_game_install(steam_path: &Path, steam_folder: &str) -> Option<PathBuf> {
    // Check main steamapps first
    let main_path = steam_path.join("steamapps/common").join(steam_folder);
    if main_path.exists() {
        return Some(main_path);
    }

    // Check library folders
    let library_vdf = steam_path.join("steamapps/libraryfolders.vdf");
    if let Ok(content) = fs::read_to_string(&library_vdf) {
        for line in content.lines() {
            let trimmed = line.trim();
            if trimmed.starts_with("\"path\"") {
                if let Some(path_str) = trimmed.split('"').nth(3) {
                    let game_path = PathBuf::from(path_str)
                        .join("steamapps/common")
                        .join(steam_folder);
                    if game_path.exists() {
                        return Some(game_path);
                    }
                }
            }
        }
    }
    None
}

/// Auto-detect installed Steam games and apply registry entries
///
/// This scans Steam library folders for installed games and automatically
/// adds the registry entries so mod managers can detect them.
pub fn auto_apply_game_registries(
    prefix_path: &Path,
    proton: &SteamProton,
    log_callback: &impl Fn(String),
) {
    let steam_path = match detect_steam_path_checked() {
        Some(p) => PathBuf::from(p),
        None => {
            log_warning("Could not find Steam path for game registry auto-detection");
            return;
        }
    };

    let wine_bin = proton.path.join("files/bin/wine");
    if !wine_bin.exists() {
        log_warning("Wine binary not found, skipping game registry auto-detection");
        return;
    }

    let mut applied_count = 0;

    for game in GAME_REGISTRY_CONFIGS {
        // Check if game is installed
        let game_path = match find_steam_game_install(&steam_path, game.steam_folder) {
            Some(p) => p,
            None => continue,
        };

        log_callback(format!("Found {}, applying registry...", game.name));

        // Convert Linux path to Wine Z: drive path with escaped backslashes for .reg file
        let linux_path = game_path.to_string_lossy();
        let wine_path_reg = format!("Z:{}", linux_path.replace('/', "\\\\"));

        // Create .reg file content
        let reg_content = format!(
            r#"Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\{}]
"{}"="{}"

[HKEY_LOCAL_MACHINE\SOFTWARE\Wow6432Node\{}]
"{}"="{}"
"#,
            game.reg_path,
            game.value_name,
            wine_path_reg,
            game.reg_path.strip_prefix("Software\\").unwrap_or(game.reg_path),
            game.value_name,
            wine_path_reg,
        );

        // Write temp .reg file
        let tmp_dir = AppConfig::get_tmp_path();
        let reg_file = tmp_dir.join(format!("game_reg_{}.reg", game.app_id));

        if let Err(e) = fs::write(&reg_file, &reg_content) {
            log_warning(&format!("Failed to write registry file for {}: {}", game.name, e));
            continue;
        }

        // Apply registry
        let status = Command::new(&wine_bin)
            .arg("regedit")
            .arg(&reg_file)
            .env("WINEPREFIX", prefix_path)
            .env("WINEDLLOVERRIDES", "mscoree=d;mshtml=d")
            .env("PROTON_USE_XALIA", "0")
            .status();

        let _ = fs::remove_file(&reg_file);

        match status {
            Ok(s) if s.success() => {
                log_install(&format!("Applied registry for {} -> {:?}", game.name, game_path));
                applied_count += 1;
            }
            Ok(s) => {
                log_warning(&format!(
                    "Registry for {} may have failed (exit code: {:?})",
                    game.name,
                    s.code()
                ));
            }
            Err(e) => {
                log_warning(&format!("Failed to apply registry for {}: {}", game.name, e));
            }
        }
    }

    if applied_count > 0 {
        log_callback(format!("Auto-configured {} game(s) in registry", applied_count));
        log_install(&format!("Auto-applied registry for {} detected game(s)", applied_count));
    }
}

/// Find the Steam prefix for a game by App ID
fn find_steam_game_prefix(steam_path: &Path, app_id: &str) -> Option<PathBuf> {
    // Check main steamapps first
    let main_prefix = steam_path
        .join("steamapps/compatdata")
        .join(app_id)
        .join("pfx");
    if main_prefix.exists() {
        return Some(main_prefix);
    }

    // Check library folders
    let library_vdf = steam_path.join("steamapps/libraryfolders.vdf");
    if let Ok(content) = fs::read_to_string(&library_vdf) {
        for line in content.lines() {
            let trimmed = line.trim();
            if trimmed.starts_with("\"path\"") {
                if let Some(path_str) = trimmed.split('"').nth(3) {
                    let prefix = PathBuf::from(path_str)
                        .join("steamapps/compatdata")
                        .join(app_id)
                        .join("pfx");
                    if prefix.exists() {
                        return Some(prefix);
                    }
                }
            }
        }
    }
    None
}

/// Get the username from a Wine prefix (Proton always uses "steamuser")
fn get_prefix_username(_prefix_root: &Path) -> &'static str {
    PREFIX_USERNAME
}

/// Create game-specific folders in the Wine prefix
/// Symlinks to existing Steam game saves/configs when available
pub fn create_game_folders(prefix_root: &Path) {
    let username = get_prefix_username(prefix_root);
    let user_dir = prefix_root.join("drive_c/users").join(username);
    let documents_dir = user_dir.join("Documents");
    let my_games_dir = documents_dir.join("My Games");
    let appdata_local = user_dir.join("AppData/Local");

    // Ensure base directories exist
    let _ = fs::create_dir_all(&my_games_dir);
    let _ = fs::create_dir_all(&appdata_local);

    // Find Steam installation (using shared utility)
    let steam_path = detect_steam_path_checked().map(PathBuf::from);

    // Process each Bethesda game
    for (game_folder, app_id) in BETHESDA_GAMES {
        let target_dir = my_games_dir.join(game_folder);

        // Skip if already exists (don't overwrite)
        if target_dir.exists() || fs::symlink_metadata(&target_dir).is_ok() {
            continue;
        }

        // Try to find and symlink from Steam prefix
        let mut linked = false;
        if let Some(ref steam) = steam_path {
            if let Some(game_prefix) = find_steam_game_prefix(steam, app_id) {
                let game_username = get_prefix_username(&game_prefix);
                let source_dir = game_prefix
                    .join("drive_c/users")
                    .join(game_username)
                    .join("Documents/My Games")
                    .join(game_folder);

                if source_dir.exists() {
                    match std::os::unix::fs::symlink(&source_dir, &target_dir) {
                        Ok(()) => {
                            log_install(&format!(
                                "Linked My Games/{} from Steam prefix (App {})",
                                game_folder, app_id
                            ));
                            linked = true;
                        }
                        Err(e) => {
                            log_warning(&format!(
                                "Failed to symlink My Games/{}: {}",
                                game_folder, e
                            ));
                        }
                    }
                }
            }
        }

        // Create empty folder if no Steam prefix found
        if !linked {
            if let Err(e) = fs::create_dir_all(&target_dir) {
                log_warning(&format!("Failed to create My Games/{}: {}", game_folder, e));
            }
        }
    }

    // Handle Oblivion lowercase INI symlinks
    // Some tools expect lowercase oblivion.ini alongside Oblivion.ini
    let oblivion_dir = my_games_dir.join("Oblivion");
    if oblivion_dir.exists() {
        create_lowercase_ini_symlink(&oblivion_dir, "Oblivion.ini", "oblivion.ini");
        create_lowercase_ini_symlink(&oblivion_dir, "OblivionPrefs.ini", "oblivionprefs.ini");
    }

    // Create AppData/Local folders (these don't usually have existing data to link)
    for game in APPDATA_GAMES {
        let game_dir = appdata_local.join(game);
        if !game_dir.exists() {
            if let Err(e) = fs::create_dir_all(&game_dir) {
                log_warning(&format!("Failed to create AppData/Local/{}: {}", game, e));
            }
        }
    }

    // Create "My Documents" symlink if it doesn't exist
    let my_documents_link = user_dir.join("My Documents");
    if !my_documents_link.exists() && fs::symlink_metadata(&my_documents_link).is_err() {
        if let Err(e) = std::os::unix::fs::symlink("Documents", &my_documents_link) {
            log_warning(&format!("Failed to create My Documents symlink: {}", e));
        }
    }

    // Copy Enderal Special Edition config files (if folder exists but is empty)
    let enderal_se_dir = my_games_dir.join("Enderal Special Edition");
    if enderal_se_dir.exists() && !fs::symlink_metadata(&enderal_se_dir).map(|m| m.file_type().is_symlink()).unwrap_or(false) {
        // Only write default configs if folder is NOT a symlink (i.e., we created it empty)
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

    log_install("Created/linked game folders in prefix (Documents/My Games, AppData/Local)");
}

/// Create a lowercase symlink for an INI file (for tools that expect lowercase)
fn create_lowercase_ini_symlink(dir: &Path, original: &str, lowercase: &str) {
    let original_path = dir.join(original);
    let lowercase_path = dir.join(lowercase);

    // Only create if original exists and lowercase doesn't
    if original_path.exists()
        && !lowercase_path.exists()
        && fs::symlink_metadata(&lowercase_path).is_err()
    {
        // Create relative symlink (just the filename)
        if let Err(e) = std::os::unix::fs::symlink(original, &lowercase_path) {
            log_warning(&format!(
                "Failed to create lowercase symlink {} -> {}: {}",
                lowercase, original, e
            ));
        } else {
            log_install(&format!("Created lowercase INI symlink: {} -> {}", lowercase, original));
        }
    }
}
