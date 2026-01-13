//! Direct DLL download and installation
//!
//! For dependencies that are just DLL files that need to be copied
//! directly to system32/syswow64 (e.g., d3dcompiler_47).

use std::error::Error;
use std::fs;

use crate::logging::{log_download, log_install};
use crate::utils::download_file;

use super::registry::Dependency;
use super::DepInstallContext;

/// Install a direct DLL dependency
pub fn install(dep: &Dependency, ctx: &DepInstallContext) -> Result<(), Box<dyn Error>> {
    let tmp_dir = ctx.tmp_dir();
    fs::create_dir_all(&tmp_dir)?;

    // On 64-bit Wine prefixes (which Proton always creates):
    //   - system32 = 64-bit DLLs
    //   - syswow64 = 32-bit DLLs (WoW64 compatibility layer)
    let system32 = ctx.prefix.join("drive_c/windows/system32");  // 64-bit
    let syswow64 = ctx.prefix.join("drive_c/windows/syswow64");  // 32-bit

    fs::create_dir_all(&system32)?;
    fs::create_dir_all(&syswow64)?;

    let target_name = get_target_dll_name(dep);

    // Download and install x86 (32-bit) DLL to syswow64
    let x86_filename = url_to_filename(dep.urls.x86);
    let x86_tmp = tmp_dir.join(&x86_filename);

    if !x86_tmp.exists() {
        ctx.log(&format!("Downloading {} (x86)...", dep.name));
        log_download(&format!("Downloading {}", x86_filename));
        download_file(dep.urls.x86, &x86_tmp)?;
    }

    // 32-bit DLLs go to syswow64 on 64-bit prefix
    let syswow64_target = syswow64.join(&target_name);
    ctx.log(&format!("Installing {} to syswow64 (32-bit)...", target_name));
    fs::copy(&x86_tmp, &syswow64_target)?;

    // Download and install x64 (64-bit) DLL to system32 if available
    if let Some(x64_url) = dep.urls.x64 {
        let x64_filename = url_to_filename(x64_url);
        let x64_tmp = tmp_dir.join(&x64_filename);

        if !x64_tmp.exists() {
            ctx.log(&format!("Downloading {} (x64)...", dep.name));
            log_download(&format!("Downloading {}", x64_filename));
            download_file(x64_url, &x64_tmp)?;
        }

        // 64-bit DLLs go to system32 on 64-bit prefix
        let system32_target = system32.join(&target_name);
        ctx.log(&format!("Installing {} to system32 (64-bit)...", target_name));
        fs::copy(&x64_tmp, &system32_target)?;
    }

    log_install(&format!("{} installed successfully", dep.name));
    Ok(())
}

/// Get the target DLL name from the dependency
fn get_target_dll_name(dep: &Dependency) -> String {
    // The installed_check field tells us what the DLL should be named
    dep.installed_check.to_string()
}

/// Extract filename from URL
fn url_to_filename(url: &str) -> String {
    url.rsplit('/').next().unwrap_or("file.dll").to_string()
}
