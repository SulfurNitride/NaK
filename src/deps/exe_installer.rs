//! EXE installer runner
//!
//! Handles running Windows EXE installers through Proton.

use std::error::Error;
use std::fs;
use std::path::Path;
use std::process::Command;
use std::sync::atomic::Ordering;
use std::time::Duration;

use crate::logging::{log_download, log_install, log_warning};
use crate::utils::download_file;

use super::tools::ensure_cabextract;

use super::registry::Dependency;
use super::wine_utils::{kill_wineserver, kill_xalia, spawn_proton};
use super::DepInstallContext;

/// Install a dependency that uses an EXE installer
pub fn install(
    dep: &Dependency,
    ctx: &DepInstallContext,
    args: &[&str],
) -> Result<(), Box<dyn Error>> {
    let tmp_dir = ctx.tmp_dir();
    fs::create_dir_all(&tmp_dir)?;

    // Download x86 installer
    let x86_filename = url_to_filename(dep.urls.x86);
    let x86_path = tmp_dir.join(&x86_filename);

    if !x86_path.exists() {
        ctx.log(&format!("Downloading {} (x86)...", dep.name));
        log_download(&format!("Downloading {}", x86_filename));
        download_file(dep.urls.x86, &x86_path)?;
    }

    // Special handling for vcrun2022: extract msvcp140.dll BEFORE running installer
    // Wine bug 57518: installer refuses to replace msvcp140.dll because Wine's
    // builtin has a higher version number. Extract manually first.
    if dep.id == "vcrun2022" {
        extract_vcrun2022_msvcp140(&x86_path, ctx, false)?;
    }

    // Run x86 installer
    ctx.log(&format!("Installing {} (x86)...", dep.name));
    run_installer(&x86_path, args, ctx)?;

    // Download and run x64 installer if available
    if let Some(x64_url) = dep.urls.x64 {
        let x64_filename = url_to_filename(x64_url);
        let x64_path = tmp_dir.join(&x64_filename);

        if !x64_path.exists() {
            ctx.log(&format!("Downloading {} (x64)...", dep.name));
            log_download(&format!("Downloading {}", x64_filename));
            download_file(x64_url, &x64_path)?;
        }

        // Extract msvcp140.dll for x64 too
        if dep.id == "vcrun2022" {
            extract_vcrun2022_msvcp140(&x64_path, ctx, true)?;
        }

        ctx.log(&format!("Installing {} (x64)...", dep.name));
        run_installer(&x64_path, args, ctx)?;
    }

    log_install(&format!("{} installed successfully", dep.name));
    Ok(())
}

/// Extract msvcp140.dll from vcrun2022 installer (workaround for Wine bug 57518)
fn extract_vcrun2022_msvcp140(
    installer_path: &Path,
    ctx: &DepInstallContext,
    is_x64: bool,
) -> Result<(), Box<dyn Error>> {
    let cabextract = ensure_cabextract()?;
    let tmp_dir = ctx.tmp_dir();

    let target_dir = if is_x64 {
        ctx.prefix.join("drive_c/windows/system32")
    } else {
        ctx.prefix.join("drive_c/windows/syswow64")
    };
    fs::create_dir_all(&target_dir)?;

    let arch_label = if is_x64 { "x64" } else { "x86" };
    let cab_name = if is_x64 { "a11" } else { "a10" };
    let extract_dir = tmp_dir.join(format!("vcrun2022_{}", arch_label));
    let _ = fs::remove_dir_all(&extract_dir);
    fs::create_dir_all(&extract_dir)?;

    ctx.log(&format!("Extracting msvcp140.dll ({}) from VC++ redistributable...", arch_label));

    // Step 1: Extract the cab from the installer exe
    let output = Command::new(&cabextract)
        .arg("-d")
        .arg(&extract_dir)
        .arg("-F")
        .arg(cab_name)
        .arg(installer_path)
        .output()?;

    if !output.status.success() {
        log_warning(&format!(
            "Failed to extract {} from vcrun2022: {}",
            cab_name,
            String::from_utf8_lossy(&output.stderr)
        ));
        return Ok(());
    }

    // Step 2: Extract msvcp140.dll from the cab
    let cab_path = extract_dir.join(cab_name);
    if cab_path.exists() {
        let output = Command::new(&cabextract)
            .arg("-d")
            .arg(&target_dir)
            .arg("-F")
            .arg("msvcp140.dll")
            .arg(&cab_path)
            .output()?;

        if output.status.success() {
            log_install(&format!("Extracted msvcp140.dll ({}) to {:?}", arch_label, target_dir));
        } else {
            log_warning(&format!(
                "Failed to extract msvcp140.dll from {}: {}",
                cab_name,
                String::from_utf8_lossy(&output.stderr)
            ));
        }
    }

    let _ = fs::remove_dir_all(&extract_dir);
    Ok(())
}

/// Run an installer EXE through Proton
fn run_installer(
    installer_path: &Path,
    args: &[&str],
    ctx: &DepInstallContext,
) -> Result<(), Box<dyn Error>> {
    kill_xalia();

    // Build args: ["run", "installer.exe", "/q", "/norestart"]
    let mut proton_args: Vec<&str> = vec!["run"];
    proton_args.push(installer_path.to_str().ok_or("Invalid installer path")?);
    proton_args.extend(args);

    let mut child = spawn_proton(&ctx.proton, &ctx.prefix, &proton_args)?;

    // Poll for completion with cancel check
    loop {
        if ctx.cancel_flag.load(Ordering::Relaxed) {
            let _ = child.kill();
            let _ = child.wait();
            kill_wineserver(&ctx.proton, &ctx.prefix);
            kill_xalia();
            return Err("Cancelled by user".into());
        }

        match child.try_wait() {
            Ok(Some(status)) => {
                if !status.success() {
                    let code = status.code();
                    // Exit codes 3010, 1641, 0 are success
                    if code != Some(3010) && code != Some(1641) && code != Some(0) {
                        log_warning(&format!(
                            "Installer {:?} exited with code {:?}",
                            installer_path.file_name(),
                            code
                        ));
                    }
                }
                break;
            }
            Ok(None) => {
                kill_xalia();
                std::thread::sleep(Duration::from_millis(200));
            }
            Err(e) => return Err(e.into()),
        }
    }

    // Kill wineserver to simulate reboot
    ctx.log("Simulating reboot...");
    kill_wineserver(&ctx.proton, &ctx.prefix);
    std::thread::sleep(Duration::from_secs(2));

    Ok(())
}

fn url_to_filename(url: &str) -> String {
    url.rsplit('/')
        .next()
        .unwrap_or("installer.exe")
        .to_string()
}
