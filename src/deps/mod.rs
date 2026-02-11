//! Dependency management via winetricks
//!
//! Uses winetricks for all Windows dependency installation.
//! Winetricks handles prefix initialization, downloads, and DLL overrides automatically.

#[cfg(feature = "full")]
pub mod precache;
pub mod tools;

use std::error::Error;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use crate::config::AppConfig;
use crate::logging::{log_error, log_install};
use crate::runtime_wrap;
use crate::steam::SteamProton;

// Re-export tools
pub use tools::{check_command_available, ensure_cabextract, ensure_winetricks, get_winetricks_path};

/// Standard winetricks verbs for MO2 prefix
pub const STANDARD_VERBS: &[&str] = &[
    "vcrun2022",      // Visual C++ 2015-2022 Runtime
    "dotnet6",        // .NET 6.0
    "dotnet7",        // .NET 7.0
    "dotnet8",        // .NET 8.0
    "dotnetdesktop6", // .NET Desktop Runtime 6.0
    "d3dcompiler_47", // DirectX Compiler 47
    "d3dcompiler_43", // DirectX Compiler 43
    "d3dx9",          // DirectX 9 (all versions)
    "d3dx11_43",      // DirectX 11
    "xact",           // XACT Audio (32-bit)
    "xact_x64",       // XACT Audio (64-bit)
];


/// Run winetricks to install dependencies
///
/// This handles:
/// - Prefix initialization (wineboot) automatically
/// - All dependency downloads and installation
/// - DLL overrides
///
/// Winetricks is stored in ~/.config/nak/bin/ which is accessible
/// from both native and Flatpak environments - no special handling needed.
pub fn run_winetricks(
    prefix_path: &Path,
    proton: &SteamProton,
    verbs: &[&str],
    log_callback: impl Fn(String),
) -> Result<(), Box<dyn Error>> {
    if verbs.is_empty() {
        return Ok(());
    }

    // Ensure winetricks is available (downloads to ~/.config/nak/bin/)
    let winetricks_path = ensure_winetricks()?;

    // Ensure cabextract is available (required by winetricks for cab extraction)
    ensure_cabextract()?;

    let Some(wine_bin) = proton.wine_binary() else {
        return Err("Wine binary not found in Proton".into());
    };

    let Some(wineserver_bin) = proton.wineserver_binary() else {
        return Err("Wineserver binary not found in Proton".into());
    };

    // Set up cache directory
    let cache_dir = AppConfig::get_default_cache_dir();
    std::fs::create_dir_all(&cache_dir)?;

    let verbs_str = verbs.join(" ");
    log_callback(format!("Installing dependencies via winetricks: {}", verbs_str));
    log_install(&format!("Running winetricks with verbs: {}", verbs_str));

    // Build PATH with NaK bin directory so winetricks can find cabextract
    let nak_bin = tools::get_nak_bin_path();
    let current_path = std::env::var("PATH").unwrap_or_default();
    let new_path = format!("{}:{}", nak_bin.display(), current_path);

    // Run winetricks directly - ~/.config/nak/bin/ is accessible from
    // both native and Flatpak environments.
    // Use build_command so env vars are forwarded via --env= flags in Flatpak.
    let envs: Vec<(&str, String)> = vec![
        ("PATH", new_path),
        ("WINE", wine_bin.display().to_string()),
        ("WINESERVER", wineserver_bin.display().to_string()),
        ("WINEPREFIX", prefix_path.display().to_string()),
        ("WINETRICKS_CACHE", cache_dir.display().to_string()),
    ];
    let status = runtime_wrap::build_command(&winetricks_path, &envs)
        .arg("-q") // Quiet mode
        .args(verbs)
        .status()?;

    if !status.success() {
        let err_msg = format!("Winetricks failed with exit code: {:?}", status.code());
        log_error(&err_msg);
        return Err(err_msg.into());
    }

    log_install("Winetricks completed successfully");
    Ok(())
}

/// Install all standard dependencies to a prefix
///
/// This is the main entry point for dependency installation.
/// Runs winetricks with all standard verbs.
pub fn install_standard_deps(
    prefix_path: &Path,
    proton: &SteamProton,
    log_callback: impl Fn(String),
) -> Result<(), Box<dyn Error>> {
    run_winetricks(prefix_path, proton, STANDARD_VERBS, log_callback)
}

/// Run winetricks with cancellation support.
///
/// Like `run_winetricks` but uses spawn + poll so the child process
/// can be killed if the user cancels.
pub fn run_winetricks_cancellable(
    prefix_path: &Path,
    proton: &SteamProton,
    verbs: &[&str],
    log_callback: impl Fn(String),
    cancel_flag: &Arc<AtomicBool>,
) -> Result<(), Box<dyn Error>> {
    if verbs.is_empty() {
        return Ok(());
    }

    let winetricks_path = ensure_winetricks()?;
    ensure_cabextract()?;

    let Some(wine_bin) = proton.wine_binary() else {
        return Err("Wine binary not found in Proton".into());
    };

    let Some(wineserver_bin) = proton.wineserver_binary() else {
        return Err("Wineserver binary not found in Proton".into());
    };

    let cache_dir = AppConfig::get_default_cache_dir();
    std::fs::create_dir_all(&cache_dir)?;

    let verbs_str = verbs.join(" ");
    log_callback(format!("Installing dependencies via winetricks: {}", verbs_str));
    log_install(&format!("Running winetricks with verbs: {}", verbs_str));

    let nak_bin = tools::get_nak_bin_path();
    let current_path = std::env::var("PATH").unwrap_or_default();
    let new_path = format!("{}:{}", nak_bin.display(), current_path);

    // Use build_command so env vars are forwarded via --env= flags in Flatpak.
    let envs: Vec<(&str, String)> = vec![
        ("PATH", new_path),
        ("WINE", wine_bin.display().to_string()),
        ("WINESERVER", wineserver_bin.display().to_string()),
        ("WINEPREFIX", prefix_path.display().to_string()),
        ("WINETRICKS_CACHE", cache_dir.display().to_string()),
    ];
    let mut child = runtime_wrap::build_command(&winetricks_path, &envs)
        .arg("-q")
        .args(verbs)
        .spawn()?;

    loop {
        match child.try_wait()? {
            Some(status) => {
                if !status.success() {
                    let err_msg = format!("Winetricks failed with exit code: {:?}", status.code());
                    log_error(&err_msg);
                    return Err(err_msg.into());
                }
                log_install("Winetricks completed successfully");
                return Ok(());
            }
            None => {
                if cancel_flag.load(Ordering::Relaxed) {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err("Cancelled".into());
                }
                std::thread::sleep(std::time::Duration::from_millis(250));
            }
        }
    }
}

/// Install standard deps with cancellation support
pub fn install_standard_deps_cancellable(
    prefix_path: &Path,
    proton: &SteamProton,
    log_callback: impl Fn(String),
    cancel_flag: &Arc<AtomicBool>,
) -> Result<(), Box<dyn Error>> {
    run_winetricks_cancellable(prefix_path, proton, STANDARD_VERBS, log_callback, cancel_flag)
}
