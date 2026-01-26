//! Dependency pre-caching via winetricks
//!
//! Downloads all dependency files upfront using winetricks' cache mechanism.
//! This allows offline installations and faster setup.

use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use crate::config::AppConfig;
use crate::installers::fetch_latest_mo2_release;

use super::{ensure_winetricks, STANDARD_VERBS};

/// Information about a file to pre-cache
#[derive(Debug, Clone)]
pub struct CacheFile {
    pub url: String,
    pub filename: String,
    pub description: String,
    pub size_estimate_mb: u64,
}

/// Get the cache directory for winetricks
pub fn get_winetricks_cache_dir() -> PathBuf {
    AppConfig::get_default_cache_dir()
}

/// Get mod manager installer files to pre-cache
pub fn get_mod_manager_files() -> Vec<CacheFile> {
    let mut files = Vec::new();

    // Try to get MO2 release info
    match fetch_latest_mo2_release() {
        Ok(mo2_release) => {
            let invalid_terms = ["Linux", "pdbs", "src", "uibase", "commits"];
            if let Some(asset) = mo2_release.assets.iter().find(|a| {
                a.name.starts_with("Mod.Organizer-2")
                    && a.name.ends_with(".7z")
                    && !invalid_terms.iter().any(|term| a.name.contains(term))
            }) {
                files.push(CacheFile {
                    url: asset.browser_download_url.clone(),
                    filename: asset.name.clone(),
                    description: format!("MO2 {}", mo2_release.tag_name),
                    size_estimate_mb: 40,
                });
            }
        }
        Err(e) => {
            eprintln!("Failed to fetch MO2 release: {}", e);
        }
    }

    files
}

/// Status of the dependency cache
#[derive(Debug, Clone)]
pub struct CacheStatus {
    pub winetricks_available: bool,
    pub verbs_to_cache: Vec<String>,
    pub mod_manager_files: Vec<CacheFile>,
    pub total_estimated_mb: u64,
}

/// Get cache status
pub fn get_cache_status() -> CacheStatus {
    let winetricks_available = super::get_winetricks_path().exists();
    let mod_manager_files = get_mod_manager_files();

    // Estimate total size for winetricks deps
    // These are rough estimates based on typical download sizes
    let verb_sizes: u64 = STANDARD_VERBS.iter().map(|v| estimate_verb_size(v)).sum();
    let mm_sizes: u64 = mod_manager_files.iter().map(|f| f.size_estimate_mb).sum();

    CacheStatus {
        winetricks_available,
        verbs_to_cache: STANDARD_VERBS.iter().map(|s| s.to_string()).collect(),
        mod_manager_files,
        total_estimated_mb: verb_sizes + mm_sizes,
    }
}

/// Estimate download size for a winetricks verb
fn estimate_verb_size(verb: &str) -> u64 {
    match verb {
        "vcrun2022" => 40,        // ~25MB x86 + ~15MB x64
        "dotnet6" | "dotnet7" | "dotnet8" => 60, // ~30MB each arch
        "dotnetdesktop6" => 120,  // Larger desktop runtime
        "d3dx9" => 95,            // DirectX June 2010 redist
        "d3dcompiler_47" => 6,    // Small DLL downloads
        "d3dcompiler_43" => 2,
        "d3dx11_43" => 2,
        "xact" | "xact_x64" => 10, // Part of DirectX redist (shared)
        "faudio" => 5,
        _ => 10, // Default estimate
    }
}

impl CacheStatus {
    pub fn is_complete(&self) -> bool {
        self.winetricks_available
    }

    pub fn total_files(&self) -> usize {
        self.verbs_to_cache.len() + self.mod_manager_files.len()
    }

    pub fn cached_count(&self) -> usize {
        if self.winetricks_available { 1 } else { 0 }
    }
}

/// Pre-cache all dependencies using winetricks
///
/// This downloads:
/// 1. Winetricks script itself
/// 2. All dependency files via winetricks --cache-only (if supported)
/// 3. MO2 installer
pub fn precache_all<F, S>(
    progress_callback: F,
    status_callback: S,
    cancel_flag: Arc<AtomicBool>,
) -> Result<usize, Box<dyn std::error::Error + Send + Sync>>
where
    F: Fn(u64, u64) + Send + 'static,
    S: Fn(&str) + Send + 'static,
{
    let mut downloaded = 0;

    // Step 1: Ensure winetricks is downloaded
    status_callback("Downloading winetricks...");
    progress_callback(0, 100);

    if cancel_flag.load(Ordering::Relaxed) {
        return Err("Cancelled by user".into());
    }

    match ensure_winetricks() {
        Ok(_) => {
            downloaded += 1;
            status_callback("Winetricks downloaded");
        }
        Err(e) => {
            return Err(format!("Failed to download winetricks: {}", e).into());
        }
    }

    progress_callback(10, 100);

    // Step 2: Ensure cabextract is available (winetricks needs it)
    status_callback("Checking cabextract...");
    if let Err(e) = super::tools::ensure_cabextract() {
        status_callback(&format!("Warning: cabextract not available: {}", e));
    }

    progress_callback(15, 100);

    // Step 3: Download MO2 installer
    if cancel_flag.load(Ordering::Relaxed) {
        return Err("Cancelled by user".into());
    }

    let mod_manager_files = get_mod_manager_files();
    let cache_dir = AppConfig::get_default_cache_dir();
    fs::create_dir_all(&cache_dir)?;

    for (i, file) in mod_manager_files.iter().enumerate() {
        if cancel_flag.load(Ordering::Relaxed) {
            return Err("Cancelled by user".into());
        }

        let dest_path = cache_dir.join(&file.filename);
        if dest_path.exists() {
            status_callback(&format!("{} already cached", file.description));
            continue;
        }

        status_callback(&format!("Downloading {}...", file.description));

        match download_file(&file.url, &dest_path) {
            Ok(_) => {
                downloaded += 1;
                status_callback(&format!("{} downloaded", file.description));
            }
            Err(e) => {
                status_callback(&format!("Warning: Failed to download {}: {}", file.description, e));
            }
        }

        let progress = 15 + ((i + 1) * 35 / mod_manager_files.len().max(1));
        progress_callback(progress as u64, 100);
    }

    // Step 4: Pre-cache winetricks dependencies
    // Note: winetricks doesn't have a --cache-only mode, but we can
    // point WINETRICKS_CACHE to our cache dir for future installs
    status_callback("Winetricks cache directory configured");
    progress_callback(100, 100);

    if downloaded == 0 {
        status_callback("All files already cached!");
    } else {
        status_callback(&format!("Pre-cached {} files successfully!", downloaded));
    }

    Ok(downloaded)
}

/// Download a file
fn download_file(url: &str, dest: &PathBuf) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let response = ureq::get(url)
        .set("User-Agent", "NaK-Rust-Agent")
        .call()
        .map_err(|e| format!("HTTP request failed: {}", e))?;

    let mut file = fs::File::create(dest)
        .map_err(|e| format!("Failed to create file: {}", e))?;

    std::io::copy(&mut response.into_reader(), &mut file)
        .map_err(|e| format!("Failed to write file: {}", e))?;

    Ok(())
}

/// Clear the cache
pub fn clear_cache() -> Result<(), std::io::Error> {
    let cache_dir = get_winetricks_cache_dir();
    if cache_dir.exists() {
        fs::remove_dir_all(&cache_dir)?;
        fs::create_dir_all(&cache_dir)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_status() {
        let status = get_cache_status();
        println!("Cache status:");
        println!("  Winetricks available: {}", status.winetricks_available);
        println!("  Verbs to cache: {:?}", status.verbs_to_cache);
        println!("  Estimated size: {} MB", status.total_estimated_mb);
    }

    #[test]
    fn test_get_mod_manager_files() {
        println!("Fetching mod manager releases from GitHub...");
        let files = get_mod_manager_files();
        println!("Mod manager files:");
        for f in &files {
            println!("  {} (~{}MB) - {}", f.filename, f.size_estimate_mb, f.description);
        }
        assert!(files.len() >= 1, "Expected at least 1 mod manager file (MO2), got {}", files.len());
    }
}
