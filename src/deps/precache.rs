//! Dependency pre-caching
//!
//! Downloads all dependency files upfront so installations are faster
//! and don't require network access during setup.
//!
//! Includes:
//! - Windows dependencies (VC++, DirectX, .NET, etc.)
//! - Mod manager installers (MO2, Vortex)

use std::collections::HashSet;
use std::fs;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use crate::config::AppConfig;
use crate::installers::{fetch_latest_mo2_release, fetch_latest_vortex_release};

use super::registry::{DIRECTX_JUN2010_URL, STANDARD_DEPS};

/// Information about a file to pre-cache
#[derive(Debug, Clone)]
pub struct CacheFile {
    pub url: String,
    pub filename: String,
    pub description: String,
    pub size_estimate_mb: u64, // Approximate size in MB
}

/// Get all files that need to be pre-cached (dependencies only)
pub fn get_dependency_files() -> Vec<CacheFile> {
    let mut files = Vec::new();
    let mut seen_urls: HashSet<String> = HashSet::new();

    // DirectX June 2010 redistributable (largest file, ~95MB)
    // Used for: XACT, d3dcompiler, d3dx9, d3dx11
    if !seen_urls.contains(DIRECTX_JUN2010_URL) {
        files.push(CacheFile {
            url: DIRECTX_JUN2010_URL.to_string(),
            filename: "directx_Jun2010_redist.exe".to_string(),
            description: "DirectX June 2010 (XACT, D3D9, D3D11)".to_string(),
            size_estimate_mb: 95,
        });
        seen_urls.insert(DIRECTX_JUN2010_URL.to_string());
    }

    // Collect unique URLs from STANDARD_DEPS
    for dep in STANDARD_DEPS {
        // Skip GitHubRelease type (vkd3d is handled by Proton)
        if matches!(dep.dep_type, super::registry::DepType::GitHubRelease) {
            continue;
        }

        // Skip if URL is the DirectX redistributable (already added)
        if dep.urls.x86 == DIRECTX_JUN2010_URL {
            continue;
        }

        // x86 URL
        if !dep.urls.x86.is_empty() && !seen_urls.contains(dep.urls.x86) {
            let filename = url_to_filename(dep.urls.x86);
            let size = estimate_size(&filename);
            files.push(CacheFile {
                url: dep.urls.x86.to_string(),
                filename: filename.clone(),
                description: format!("{} (32-bit)", dep.name),
                size_estimate_mb: size,
            });
            seen_urls.insert(dep.urls.x86.to_string());
        }

        // x64 URL if available
        if let Some(x64_url) = dep.urls.x64 {
            if !x64_url.is_empty() && !seen_urls.contains(x64_url) {
                let filename = url_to_filename(x64_url);
                let size = estimate_size(&filename);
                files.push(CacheFile {
                    url: x64_url.to_string(),
                    filename: filename.clone(),
                    description: format!("{} (64-bit)", dep.name),
                    size_estimate_mb: size,
                });
                seen_urls.insert(x64_url.to_string());
            }
        }
    }

    files
}

/// Get mod manager installer files to pre-cache
/// Note: This requires network access to get current release info
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
            } else {
                eprintln!("MO2: No matching asset found in release");
            }
        }
        Err(e) => {
            eprintln!("Failed to fetch MO2 release: {}", e);
        }
    }

    // Try to get Vortex release info
    match fetch_latest_vortex_release() {
        Ok(vortex_release) => {
            if let Some(asset) = vortex_release.assets.iter().find(|a| {
                let name = a.name.to_lowercase();
                name.starts_with("vortex-setup") && name.ends_with(".exe")
            }) {
                files.push(CacheFile {
                    url: asset.browser_download_url.clone(),
                    filename: asset.name.clone(),
                    description: format!("Vortex {}", vortex_release.tag_name),
                    size_estimate_mb: 150,
                });
            } else {
                eprintln!("Vortex: No matching asset found in release");
            }
        }
        Err(e) => {
            eprintln!("Failed to fetch Vortex release: {}", e);
        }
    }

    files
}

/// Get all files that need to be pre-cached (dependencies only - no network request)
pub fn get_precache_files() -> Vec<CacheFile> {
    get_dependency_files()
}

/// Get all files including mod managers (requires network to fetch release info)
pub fn get_all_precache_files() -> Vec<CacheFile> {
    let mut files = get_dependency_files();
    files.extend(get_mod_manager_files());
    files
}

/// Estimate file size based on filename patterns
fn estimate_size(filename: &str) -> u64 {
    let lower = filename.to_lowercase();
    if lower.contains("vc_redist") || lower.contains("vcredist") {
        if lower.contains("x64") { 25 } else { 14 }
    } else if lower.contains("dotnet") {
        if lower.contains("desktop") { 60 } else { 30 }
    } else if lower.contains("directx") {
        95
    } else if lower.contains("d3dcompiler") && lower.contains(".dll") {
        3
    } else {
        10 // Default estimate
    }
}

/// Extract filename from URL
fn url_to_filename(url: &str) -> String {
    url.rsplit('/')
        .next()
        .unwrap_or("download")
        .to_string()
}

/// Get the cache directory for dependencies
pub fn get_dep_cache_dir() -> PathBuf {
    AppConfig::get_tmp_path()
}

/// Check which files are already cached
pub fn get_cache_status() -> CacheStatus {
    let files = get_precache_files();
    let cache_dir = get_dep_cache_dir();

    let mut cached = Vec::new();
    let mut missing = Vec::new();
    let mut total_cached_bytes: u64 = 0;
    let mut total_missing_mb: u64 = 0;

    for file in files {
        let path = cache_dir.join(&file.filename);
        if path.exists() {
            if let Ok(meta) = fs::metadata(&path) {
                total_cached_bytes += meta.len();
            }
            cached.push(file);
        } else {
            total_missing_mb += file.size_estimate_mb;
            missing.push(file);
        }
    }

    CacheStatus {
        cached_files: cached,
        missing_files: missing,
        total_cached_mb: total_cached_bytes / (1024 * 1024),
        total_missing_mb,
    }
}

/// Status of the dependency cache
#[derive(Debug, Clone)]
pub struct CacheStatus {
    pub cached_files: Vec<CacheFile>,
    pub missing_files: Vec<CacheFile>,
    pub total_cached_mb: u64,
    pub total_missing_mb: u64,
}

impl CacheStatus {
    pub fn is_complete(&self) -> bool {
        self.missing_files.is_empty()
    }

    pub fn total_files(&self) -> usize {
        self.cached_files.len() + self.missing_files.len()
    }

    pub fn cached_count(&self) -> usize {
        self.cached_files.len()
    }
}

/// Pre-cache all dependency files (and mod managers)
///
/// Returns the number of files downloaded
pub fn precache_all<F, S>(
    progress_callback: F,
    status_callback: S,
    cancel_flag: Arc<AtomicBool>,
) -> Result<usize, Box<dyn std::error::Error + Send + Sync>>
where
    F: Fn(u64, u64) + Send + 'static,
    S: Fn(&str) + Send + 'static,
{
    status_callback("Checking for files to download...");

    // Get all files including mod managers (this does network requests)
    let all_files = get_all_precache_files();
    let cache_dir = get_dep_cache_dir();
    fs::create_dir_all(&cache_dir)?;

    // Filter to only missing files
    let missing_files: Vec<_> = all_files.into_iter()
        .filter(|f| !cache_dir.join(&f.filename).exists())
        .collect();

    if missing_files.is_empty() {
        status_callback("All files already cached!");
        return Ok(0);
    }

    let total_files = missing_files.len();
    let mut downloaded = 0;
    let mut current_file_idx = 0;

    // Estimate total bytes for progress
    let total_bytes_estimate: u64 = missing_files.iter()
        .map(|f| f.size_estimate_mb * 1024 * 1024)
        .sum();
    let mut downloaded_bytes: u64 = 0;

    for file in &missing_files {
        if cancel_flag.load(Ordering::Relaxed) {
            return Err("Cancelled by user".into());
        }

        current_file_idx += 1;
        status_callback(&format!(
            "Downloading ({}/{}) {}...",
            current_file_idx,
            total_files,
            file.description
        ));

        let dest_path = cache_dir.join(&file.filename);

        match download_with_progress(
            &file.url,
            &dest_path,
            |current, total| {
                let effective_total = if total > 0 { total } else { file.size_estimate_mb * 1024 * 1024 };
                let overall_downloaded = downloaded_bytes + current;
                let overall_total = downloaded_bytes + effective_total;
                progress_callback(overall_downloaded, total_bytes_estimate.max(overall_total));
            },
            cancel_flag.clone(),
        ) {
            Ok(bytes) => {
                downloaded_bytes += bytes;
                downloaded += 1;
            }
            Err(e) => {
                // Log warning but continue with other files
                eprintln!("Failed to download {}: {}", file.filename, e);
            }
        }
    }

    if downloaded == total_files {
        status_callback("All dependencies cached successfully!");
    } else {
        status_callback(&format!("Cached {} of {} files", downloaded, total_files));
    }

    Ok(downloaded)
}

/// Download a file with progress callback
fn download_with_progress<F>(
    url: &str,
    dest: &PathBuf,
    progress: F,
    cancel_flag: Arc<AtomicBool>,
) -> Result<u64, Box<dyn std::error::Error + Send + Sync>>
where
    F: Fn(u64, u64),
{
    let response = ureq::get(url)
        .set("User-Agent", "NaK-Rust-Agent")
        .call()
        .map_err(|e| format!("HTTP request failed: {}", e))?;

    let total_size = response
        .header("Content-Length")
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);

    let mut file = fs::File::create(dest)
        .map_err(|e| format!("Failed to create file: {}", e))?;

    let mut buffer = [0; 65536]; // 64KB buffer
    let mut downloaded: u64 = 0;
    let mut reader = response.into_reader();

    loop {
        if cancel_flag.load(Ordering::Relaxed) {
            // Clean up partial download
            drop(file);
            let _ = fs::remove_file(dest);
            return Err("Cancelled".into());
        }

        let bytes_read = reader.read(&mut buffer)
            .map_err(|e| format!("Read error: {}", e))?;

        if bytes_read == 0 {
            break;
        }

        file.write_all(&buffer[..bytes_read])
            .map_err(|e| format!("Write error: {}", e))?;

        downloaded += bytes_read as u64;
        progress(downloaded, total_size);
    }

    Ok(downloaded)
}

/// Clear the dependency cache
pub fn clear_cache() -> Result<(), std::io::Error> {
    let cache_dir = get_dep_cache_dir();
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
    fn test_get_precache_files() {
        let files = get_precache_files();
        println!("Dependency files to pre-cache:");
        for f in &files {
            println!("  {} (~{}MB) - {}", f.filename, f.size_estimate_mb, f.description);
        }
        assert!(!files.is_empty());
    }

    #[test]
    fn test_get_mod_manager_files() {
        println!("Fetching mod manager releases from GitHub...");
        let files = get_mod_manager_files();
        println!("Mod manager files:");
        for f in &files {
            println!("  {} (~{}MB) - {}", f.filename, f.size_estimate_mb, f.description);
        }
        // Should have both MO2 and Vortex
        assert!(files.len() >= 2, "Expected at least 2 mod manager files (MO2 + Vortex), got {}", files.len());
    }

    #[test]
    fn test_cache_status() {
        let status = get_cache_status();
        println!("Cache status:");
        println!("  Cached: {} files ({} MB)", status.cached_count(), status.total_cached_mb);
        println!("  Missing: {} files (~{} MB)", status.missing_files.len(), status.total_missing_mb);
    }
}
