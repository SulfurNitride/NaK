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
    use crate::steam::is_flatpak_steam;

    let args: Vec<_> = args.into_iter().collect();
    let steam_path = detect_steam_path();
    let compat_data = prefix.parent().unwrap_or(prefix);

    let Some(wine_bin) = proton.wine_binary() else {
        return Err(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("Wine binary not found for Proton '{}'", proton.name),
        ));
    };
    let bin_dir = wine_bin.parent().unwrap_or(&proton.path);

    // Check if this is a standalone binary or a wine subcommand
    let standalone_binaries = ["wine", "wine64", "wineserver", "wine-preloader", "wine64-preloader"];
    let is_standalone = standalone_binaries.contains(&wine_cmd);

    // For Flatpak Steam, run through flatpak
    if is_flatpak_steam() {
        let mut cmd = Command::new("flatpak");
        cmd.arg("run")
            .arg("--command=bash")
            .arg("com.valvesoftware.Steam")
            .arg("-c");

        // Build command string for bash
        let wine_path = wine_bin.to_string_lossy();
        let prefix_str = prefix.to_string_lossy();
        let compat_str = compat_data.to_string_lossy();

        let args_str: Vec<String> = args.iter().map(|a| {
            format!("'{}'", a.as_ref().to_string_lossy().replace('\'', "'\\''"))
        }).collect();

        let full_cmd = if is_standalone {
            format!(
                "WINEPREFIX='{}' STEAM_COMPAT_DATA_PATH='{}' STEAM_COMPAT_CLIENT_INSTALL_PATH='{}' WINEDLLOVERRIDES='mshtml=d' PROTON_USE_XALIA='0' '{}' {}",
                prefix_str, compat_str, steam_path, bin_dir.join(wine_cmd).to_string_lossy(), args_str.join(" ")
            )
        } else {
            format!(
                "WINEPREFIX='{}' STEAM_COMPAT_DATA_PATH='{}' STEAM_COMPAT_CLIENT_INSTALL_PATH='{}' WINEDLLOVERRIDES='mshtml=d' PROTON_USE_XALIA='0' '{}' {} {}",
                prefix_str, compat_str, steam_path, wine_path, wine_cmd, args_str.join(" ")
            )
        };

        cmd.arg(full_cmd);
        return cmd.status();
    }

    // Native Steam - run directly
    let mut cmd;
    if is_standalone {
        cmd = Command::new(bin_dir.join(wine_cmd));
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
    use crate::steam::is_flatpak_steam;

    let Some(wineserver) = proton.wineserver_binary() else {
        return;
    };

    if is_flatpak_steam() {
        let cmd_str = format!(
            "WINEPREFIX='{}' '{}' -k",
            prefix.to_string_lossy(),
            wineserver.to_string_lossy()
        );
        let _ = Command::new("flatpak")
            .args(["run", "--command=bash", "com.valvesoftware.Steam", "-c", &cmd_str])
            .status();
    } else {
        let _ = Command::new(&wineserver)
            .arg("-k")
            .env("WINEPREFIX", prefix)
            .status();
    }
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

