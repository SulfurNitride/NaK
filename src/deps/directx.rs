//! DirectX cab extraction
//!
//! Extracts DLLs from the DirectX June 2010 redistributable.
//! Used for: xact, d3dx9, d3dcompiler_43, d3dx11_43, etc.

use std::error::Error;
use std::fs;
use std::path::Path;
use std::process::Command;

use crate::logging::{log_download, log_install, log_warning};
use crate::utils::download_file;

use super::tools::ensure_cabextract;

use super::registry::{Dependency, DIRECTX_JUN2010_FILE, DIRECTX_JUN2010_URL};
use super::DepInstallContext;

/// Install a DirectX cab-based dependency
pub fn install(
    dep: &Dependency,
    ctx: &DepInstallContext,
    cab_patterns: &[&str],
    dll_patterns: &[&str],
) -> Result<(), Box<dyn Error>> {
    let tmp_dir = ctx.tmp_dir();
    let directx_dir = tmp_dir.join("directx9");
    fs::create_dir_all(&directx_dir)?;

    // Ensure we have cabextract
    let cabextract = ensure_cabextract()?;

    // Download DirectX redistributable if not present
    let directx_path = directx_dir.join(DIRECTX_JUN2010_FILE);
    if !directx_path.exists() {
        ctx.log("Downloading DirectX June 2010 redistributable...");
        log_download("Downloading DirectX June 2010 redistributable");
        download_file(DIRECTX_JUN2010_URL, &directx_path)?;
    }

    // Create temp extraction directory
    let extract_dir = tmp_dir.join(format!("dx_extract_{}", dep.id));
    let _ = fs::remove_dir_all(&extract_dir); // Clean up any previous
    fs::create_dir_all(&extract_dir)?;

    // Determine target directory based on dep ID
    // On 64-bit Wine prefixes (which Proton always creates):
    //   - system32 = 64-bit DLLs
    //   - syswow64 = 32-bit DLLs (WoW64 compatibility layer)
    // This matches Windows behavior and winetricks' W_SYSTEM32_DLLS/W_SYSTEM64_DLLS
    let is_x64 = dep.id.contains("x64") || dep.id.contains("_64");
    let target_dir = if is_x64 {
        // 64-bit DLLs go to system32 on 64-bit prefix
        ctx.prefix.join("drive_c/windows/system32")
    } else {
        // 32-bit DLLs go to syswow64 on 64-bit prefix
        ctx.prefix.join("drive_c/windows/syswow64")
    };
    fs::create_dir_all(&target_dir)?;

    ctx.log(&format!("Extracting {} cabs...", dep.name));

    // Extract matching cab files from the DirectX redistributable
    for pattern in cab_patterns {
        extract_cabs_matching(&cabextract, &directx_path, &extract_dir, pattern)?;
    }

    // Now extract DLLs from the cab files
    ctx.log(&format!("Extracting {} DLLs...", dep.name));
    let mut extracted_count = 0;

    // Find all .cab files in extract_dir
    for entry in fs::read_dir(&extract_dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().map(|e| e == "cab").unwrap_or(false) {
            // Extract DLLs from this cab to target directory
            for dll_pattern in dll_patterns {
                let count = extract_dlls_from_cab(&cabextract, &path, &target_dir, dll_pattern)?;
                extracted_count += count;
            }
        }
    }

    // Clean up extract directory
    let _ = fs::remove_dir_all(&extract_dir);

    if extracted_count > 0 {
        log_install(&format!(
            "{}: Extracted {} DLLs to {:?}",
            dep.name, extracted_count, target_dir
        ));
    } else {
        log_warning(&format!("{}: No DLLs extracted", dep.name));
    }

    Ok(())
}

/// Extract cab files matching a pattern from the DirectX redistributable
fn extract_cabs_matching(
    cabextract: &Path,
    directx_exe: &Path,
    output_dir: &Path,
    pattern: &str,
) -> Result<(), Box<dyn Error>> {
    // cabextract -d output_dir -L -F 'pattern' directx.exe
    let status = Command::new(cabextract)
        .arg("-d")
        .arg(output_dir)
        .arg("-L") // Lowercase filenames
        .arg("-F")
        .arg(pattern)
        .arg(directx_exe)
        .output()?;

    // cabextract returns non-zero if no files match, which is OK
    if !status.status.success() && !status.stderr.is_empty() {
        let stderr = String::from_utf8_lossy(&status.stderr);
        if !stderr.contains("no files matched") {
            log_warning(&format!("cabextract warning: {}", stderr.trim()));
        }
    }

    Ok(())
}

/// Extract DLLs from a cab file to target directory
fn extract_dlls_from_cab(
    cabextract: &Path,
    cab_path: &Path,
    target_dir: &Path,
    dll_pattern: &str,
) -> Result<usize, Box<dyn Error>> {
    // cabextract -d target_dir -L -F 'pattern' cab_file
    let output = Command::new(cabextract)
        .arg("-d")
        .arg(target_dir)
        .arg("-L") // Lowercase filenames
        .arg("-F")
        .arg(dll_pattern)
        .arg(cab_path)
        .output()?;

    // Count extracted files from output
    let stdout = String::from_utf8_lossy(&output.stdout);
    let count = stdout.lines().filter(|l| l.contains("extracting")).count();

    Ok(count)
}
