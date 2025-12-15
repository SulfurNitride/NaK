//! Steam Linux Runtime Management
//! Detects (and eventually downloads) the Steam Linux Runtime (Sniper).

use std::error::Error;
use std::fs;
use std::io::{Read, Write};
use std::path::PathBuf;
use xz2::read::XzDecoder;
use tar::Archive;

pub fn find_steam_runtime_sniper() -> Option<PathBuf> {
    // Check NaK standalone installation ONLY
    let home = std::env::var("HOME").expect("Failed to get HOME");
    let nak_runtime = PathBuf::from(format!("{}/NaK/Runtime/SteamLinuxRuntime_sniper", home));

    if nak_runtime.join("_v2-entry-point").exists() {
        return Some(nak_runtime);
    }

    None
}

pub fn get_entry_point() -> Option<PathBuf> {
    find_steam_runtime_sniper().map(|p| p.join("_v2-entry-point"))
}

pub fn is_runtime_installed() -> bool {
    find_steam_runtime_sniper().is_some()
}

pub fn download_runtime<F>(progress_callback: F) -> Result<PathBuf, Box<dyn Error>>
where
    F: Fn(u64, u64) + Send + 'static,
{
    let home = std::env::var("HOME")?;
    let install_root = PathBuf::from(format!("{}/NaK/Runtime", home));
    let temp_dir = PathBuf::from(format!("{}/NaK/tmp", home));

    fs::create_dir_all(&install_root)?;
    fs::create_dir_all(&temp_dir)?;

    let url = "https://repo.steampowered.com/steamrt-images-sniper/snapshots/latest-public-stable/SteamLinuxRuntime_sniper.tar.xz";
    let temp_file_path = temp_dir.join("SteamLinuxRuntime_sniper.tar.xz");

    // 1. Download
    let response = ureq::get(url)
        .set("User-Agent", "NaK-Rust-Agent")
        .call()?;

    let total_size = response
        .header("Content-Length")
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);

    let mut file = fs::File::create(&temp_file_path)?;

    let mut buffer = [0; 65536]; // 64KB buffer for faster downloads
    let mut downloaded: u64 = 0;
    let mut reader = response.into_reader();

    loop {
        let bytes_read = reader.read(&mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        file.write_all(&buffer[..bytes_read])?;
        downloaded += bytes_read as u64;

        if total_size > 0 {
            progress_callback(downloaded, total_size);
        }
    }

    // 2. Extract (.tar.xz)
    // Signal that we're extracting (progress will stay at 100%)
    progress_callback(total_size, total_size);

    let tar_xz = fs::File::open(&temp_file_path)?;
    let tar = XzDecoder::new(tar_xz);
    let mut archive = Archive::new(tar);

    archive.unpack(&install_root)?;

    // 3. Cleanup
    fs::remove_file(temp_file_path)?;

    // Return the path
    Ok(install_root.join("SteamLinuxRuntime_sniper"))
}
