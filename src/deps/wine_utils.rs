//! Wine prefix utilities
//!
//! Simple helpers for running Wine/Proton commands with proper environment setup.

use std::error::Error;
use std::ffi::OsStr;
use std::path::Path;
use std::process::{Child, Command, ExitStatus};

use crate::logging::{log_error, log_install};
use crate::steam::{detect_steam_path, SteamProton};

use super::DepInstallContext;

/// Run a Wine command with proper environment setup
pub fn run_wine_cmd<I, S>(
    proton: &SteamProton,
    prefix: &Path,
    wine_cmd: &str,
    args: I,
) -> Result<ExitStatus, std::io::Error>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let args: Vec<_> = args.into_iter().collect();
    let steam_path = detect_steam_path();
    let compat_data = prefix.parent().unwrap_or(prefix);

    // Check if this is a standalone binary or a wine subcommand
    let standalone_binaries = ["wine", "wine64", "wineserver", "wine-preloader", "wine64-preloader"];
    let is_standalone = standalone_binaries.contains(&wine_cmd);

    let wine_bin = proton.path.join("files/bin/wine");

    let mut cmd;
    if is_standalone {
        cmd = Command::new(proton.path.join("files/bin").join(wine_cmd));
    } else {
        cmd = Command::new(&wine_bin);
        cmd.arg(wine_cmd);
    }

    for arg in &args {
        cmd.arg(arg);
    }

    cmd.env("WINEPREFIX", prefix)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", steam_path)
        .env("PROTON_USE_XALIA", "0")
        .env("WINEDLLOVERRIDES", "mshtml=d");

    cmd.status()
}

/// Spawn a Proton process (non-blocking)
pub fn spawn_proton<I, S>(
    proton: &SteamProton,
    prefix: &Path,
    args: I,
) -> Result<Child, std::io::Error>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let proton_bin = proton.path.join("proton");
    let args: Vec<_> = args.into_iter().collect();
    let steam_path = detect_steam_path();
    let compat_data = prefix.parent().unwrap_or(prefix);

    let mut cmd = Command::new(&proton_bin);
    for arg in &args {
        cmd.arg(arg);
    }

    cmd.env("WINEPREFIX", prefix)
        .env("STEAM_COMPAT_DATA_PATH", compat_data)
        .env("STEAM_COMPAT_CLIENT_INSTALL_PATH", steam_path)
        .env("PROTON_USE_XALIA", "0")
        .env("WINEDLLOVERRIDES", "mshtml=d");

    cmd.spawn()
}

/// Kill wineserver for a prefix
pub fn kill_wineserver(proton: &SteamProton, prefix: &Path) {
    let wineserver = proton.path.join("files/bin/wineserver");
    let _ = Command::new(&wineserver)
        .arg("-k")
        .env("WINEPREFIX", prefix)
        .status();
}

/// Kill any xalia processes (accessibility helper that conflicts with .NET install)
pub fn kill_xalia() {
    let _ = Command::new("pkill")
        .arg("-f")
        .arg("xalia")
        .status();
}

/// Set a DLL override in the Wine registry
pub fn set_dll_override(
    ctx: &DepInstallContext,
    dll: &str,
    mode: &str,
) -> Result<(), Box<dyn Error>> {
    let status = run_wine_cmd(
        &ctx.proton,
        &ctx.prefix,
        "reg",
        [
            "add",
            r"HKCU\Software\Wine\DllOverrides",
            "/v",
            dll,
            "/t",
            "REG_SZ",
            "/d",
            mode,
            "/f",
        ],
    )?;

    if !status.success() {
        let err_msg = format!("Failed to set DLL override for {} (exit code: {:?})", dll, status.code());
        log_error(&err_msg);
        return Err(err_msg.into());
    }

    Ok(())
}

/// Register a DLL using regsvr32
pub fn register_dll(
    ctx: &DepInstallContext,
    dll_name: &str,
) -> Result<(), Box<dyn Error>> {
    ctx.log(&format!("Registering {}...", dll_name));

    let status = run_wine_cmd(&ctx.proton, &ctx.prefix, "regsvr32", ["/s", dll_name])?;

    if !status.success() {
        log_install(&format!(
            "Note: regsvr32 {} returned {:?} (may be OK if not a COM DLL)",
            dll_name,
            status.code()
        ));
    }

    Ok(())
}

