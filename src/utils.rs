//! Shared utility functions used across the application

use std::error::Error;
use std::fs;
use std::path::Path;

/// Download a file from URL to the specified path
pub fn download_file(url: &str, path: &Path) -> Result<(), Box<dyn Error>> {
    // Ensure parent directory exists
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }

    let resp = ureq::get(url).call()?;
    let mut reader = resp.into_reader();
    let mut file = fs::File::create(path)?;
    std::io::copy(&mut reader, &mut file)?;
    Ok(())
}
