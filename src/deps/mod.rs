//! Dependency management via winetricks
//!
//! Uses winetricks for all Windows dependency installation.
//! Winetricks handles prefix initialization, downloads, and DLL overrides automatically.

pub mod precache;
pub mod tools;

use std::error::Error;
use std::path::Path;
use std::process::Command;

use crate::config::AppConfig;
use crate::logging::{log_error, log_install};
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
    "faudio",         // FAudio (XAudio reimplementation)
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
    // both native and Flatpak environments
    let status = Command::new(&winetricks_path)
        .arg("-q") // Quiet mode
        .args(verbs)
        .env("PATH", &new_path)
        .env("WINE", &wine_bin)
        .env("WINESERVER", &wineserver_bin)
        .env("WINEPREFIX", prefix_path)
        .env("WINETRICKS_CACHE", &cache_dir)
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
