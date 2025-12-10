//! Dependency management via Winetricks

use std::error::Error;
use std::fs;
use std::io::BufRead;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use super::ProtonInfo;
use crate::logging::{log_error, log_info, log_warning};

// ============================================================================
// NaK Bin Directory (for bundled tools like cabextract)
// ============================================================================

/// Get the resolved NaK base directory (handles symlinks)
pub fn get_nak_real_path() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_default();
    let nak_base = PathBuf::from(format!("{}/NaK", home));

    // Try to read symlink directly first
    if let Ok(target) = fs::read_link(&nak_base) {
        // If it's a relative symlink, resolve it relative to parent
        if target.is_relative() {
            if let Some(parent) = nak_base.parent() {
                return parent.join(&target);
            }
        }
        return target;
    }

    // Fallback to canonicalize
    fs::canonicalize(&nak_base).unwrap_or(nak_base)
}

/// Get the NaK bin directory path (~//NaK/bin)
pub fn get_nak_bin_path() -> PathBuf {
    get_nak_real_path().join("bin")
}

/// Resolve a path that might be under ~/NaK through the symlink
pub fn resolve_nak_path(path: &Path) -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_default();
    let nak_prefix = format!("{}/NaK/", home);

    // If path starts with ~/NaK/, resolve it through the symlink
    if let Some(path_str) = path.to_str() {
        if path_str.starts_with(&nak_prefix) {
            let relative = &path_str[nak_prefix.len()..];
            return get_nak_real_path().join(relative);
        }
    }

    // Otherwise try canonicalize or return as-is
    fs::canonicalize(path).unwrap_or_else(|_| path.to_path_buf())
}

/// Check if a command exists (either in system PATH or NaK bin)
pub fn check_command_available(cmd: &str) -> bool {
    // Check system PATH first
    if Command::new("which")
        .arg(cmd)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
    {
        return true;
    }

    // Check NaK bin directory
    let nak_bin = get_nak_bin_path().join(cmd);
    nak_bin.exists()
}

// ============================================================================
// Cabextract Download (for SteamOS/immutable systems)
// ============================================================================

/// URL for static cabextract binary (zip file)
const CABEXTRACT_URL: &str =
    "https://github.com/SulfurNitride/NaK/releases/download/Cabextract/cabextract-linux-x86_64.zip";

/// Ensures cabextract is available (either system or downloaded)
pub fn ensure_cabextract() -> Result<PathBuf, Box<dyn Error>> {
    // First check if system has cabextract
    if Command::new("which")
        .arg("cabextract")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
    {
        // Return a marker that system cabextract is available
        return Ok(PathBuf::from("cabextract"));
    }

    // Check if we already downloaded it - resolve NaK symlink first
    let home = std::env::var("HOME").unwrap_or_default();
    let nak_base = PathBuf::from(format!("{}/NaK", home));
    let nak_real = fs::canonicalize(&nak_base).unwrap_or(nak_base);
    let bin_dir = nak_real.join("bin");
    let cabextract_path = bin_dir.join("cabextract");

    if cabextract_path.exists() {
        return Ok(cabextract_path);
    }

    // Download cabextract zip
    log_warning("System cabextract not found, downloading...");
    fs::create_dir_all(&bin_dir)?;

    let response = ureq::get(CABEXTRACT_URL).call().map_err(|e| {
        format!(
            "Failed to download cabextract: {}. Please install cabextract manually.",
            e
        )
    })?;

    // Download to temp zip file
    let zip_path = bin_dir.join("cabextract.zip");
    let mut zip_file = fs::File::create(&zip_path)?;
    std::io::copy(&mut response.into_reader(), &mut zip_file)?;

    // Extract using unzip command (available on most systems including SteamOS)
    let status = Command::new("unzip")
        .arg("-o")
        .arg(&zip_path)
        .arg("-d")
        .arg(&bin_dir)
        .status()?;

    if !status.success() {
        // Fallback: try with busybox unzip or python
        let _ = Command::new("python3")
            .arg("-c")
            .arg(format!(
                "import zipfile; zipfile.ZipFile('{}').extractall('{}')",
                zip_path.display(),
                bin_dir.display()
            ))
            .status();
    }

    // Clean up zip file
    let _ = fs::remove_file(&zip_path);

    // Make executable
    if cabextract_path.exists() {
        let mut perms = fs::metadata(&cabextract_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&cabextract_path, perms)?;
        log_info(&format!("cabextract downloaded to {:?}", cabextract_path));
        Ok(cabextract_path)
    } else {
        log_error("Failed to extract cabextract from zip");
        Err("Failed to extract cabextract from zip".into())
    }
}

// ============================================================================
// Winetricks Download
// ============================================================================

/// Ensures winetricks is downloaded and available (stored in ~/NaK/bin)
pub fn ensure_winetricks() -> Result<PathBuf, Box<dyn Error>> {
    let home = std::env::var("HOME")?;
    let nak_base = PathBuf::from(format!("{}/NaK", home));

    // Resolve symlink for NaK directory if it exists
    let nak_real = fs::canonicalize(&nak_base).unwrap_or(nak_base);
    let bin_dir = nak_real.join("bin");
    let winetricks_path = bin_dir.join("winetricks");

    fs::create_dir_all(&bin_dir)?;

    // Check if it exists (we could add version checking later)
    if !winetricks_path.exists() {
        println!("Downloading winetricks...");
        let response = ureq::get(
            "https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks",
        )
        .call()?;

        let mut file = fs::File::create(&winetricks_path)?;
        std::io::copy(&mut response.into_reader(), &mut file)?;

        // Make executable (chmod +x)
        let mut perms = fs::metadata(&winetricks_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&winetricks_path, perms)?;

        println!("Winetricks downloaded to {:?}", winetricks_path);
    }

    Ok(winetricks_path)
}

// ============================================================================
// Dependency Manager
// ============================================================================

pub struct DependencyManager;

impl DependencyManager {
    pub fn new(_winetricks_path: PathBuf) -> Self {
        Self
    }

    pub fn install_dependencies(
        &self,
        prefix_path: &Path,
        proton: &ProtonInfo,
        dependencies: &[&str],
        status_callback: impl Fn(String) + Clone + Send + 'static,
        cancel_flag: Arc<AtomicBool>,
    ) -> Result<(), Box<dyn Error>> {
        // Get winetricks from NaK bin directory (handles symlinks properly)
        let nak_bin = get_nak_bin_path();
        let winetricks_real = nak_bin.join("winetricks");

        if !winetricks_real.exists() {
            return Err(format!("Winetricks not found at {:?}", winetricks_real).into());
        }

        // Prepare environment - resolve proton path through NaK symlink
        let proton_real = resolve_nak_path(&proton.path);
        let wine_bin = proton_real.join("files/bin/wine");
        let wineserver = proton_real.join("files/bin/wineserver");

        // Also resolve prefix path through NaK symlink
        let prefix_real = resolve_nak_path(prefix_path);

        // Include NaK bin directory for bundled tools (cabextract, winetricks, etc.)
        let path_env = format!(
            "{}:{}:{}",
            proton_real.join("files/bin").to_string_lossy(),
            nak_bin.to_string_lossy(),
            std::env::var("PATH").unwrap_or_default()
        );

        if !wine_bin.exists() {
            return Err(format!("Wine binary not found at {:?}", wine_bin).into());
        }

        status_callback(format!(
            "Installing dependencies: {}",
            dependencies.join(", ")
        ));

        let mut cmd = Command::new(&winetricks_real);
        cmd.arg("--unattended")
            .args(dependencies)
            .env("WINEPREFIX", &prefix_real)
            .env("WINE", &wine_bin)
            .env("WINESERVER", &wineserver)
            .env("PATH", &path_env)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = cmd.spawn().map_err(|e| {
            format!(
                "Failed to spawn winetricks: {} | winetricks={:?} wine={:?} prefix={:?}",
                e, winetricks_real, wine_bin, prefix_real
            )
        })?;

        // Stream Stdout
        let stdout = child.stdout.take().unwrap();
        let cb_out = status_callback.clone();
        thread::spawn(move || {
            let reader = std::io::BufReader::new(stdout);
            for line in reader.lines().map_while(Result::ok) {
                // Hard block Wine internal logs
                if line.contains(":err:") || line.contains(":fixme:") || line.contains(":warn:") {
                    continue;
                }

                let l = line.to_lowercase();
                if l.contains("executing")
                    || l.contains("installing")
                    || l.contains("downloading")
                    || l.contains("completed")
                    || l.contains("success")
                    || l.contains("fail")
                    || l.contains("error")
                {
                    cb_out(format!("[WINETRICKS] {}", line));
                }
            }
        });

        // Stream Stderr
        let stderr = child.stderr.take().unwrap();
        let cb_err = status_callback.clone();
        thread::spawn(move || {
            let reader = std::io::BufReader::new(stderr);
            for line in reader.lines().map_while(Result::ok) {
                // Hard block Wine internal logs
                if line.contains(":err:") || line.contains(":fixme:") || line.contains(":warn:") {
                    continue;
                }

                let l = line.to_lowercase();
                if l.contains("executing")
                    || l.contains("installing")
                    || l.contains("downloading")
                    || l.contains("completed")
                    || l.contains("success")
                    || l.contains("fail")
                    || l.contains("error")
                {
                    cb_err(format!("[WINETRICKS] {}", line));
                }
            }
        });

        // Loop to check for cancel or exit
        loop {
            if cancel_flag.load(Ordering::Relaxed) {
                let _ = child.kill();
                let _ = child.wait(); // Clean up zombie
                return Err("Installation Cancelled by User".into());
            }

            match child.try_wait() {
                Ok(Some(status)) => {
                    if !status.success() {
                        return Err(format!("Winetricks exited with code: {}", status).into());
                    }
                    break;
                }
                Ok(None) => {
                    // Still running
                    thread::sleep(Duration::from_millis(100));
                }
                Err(e) => return Err(e.into()),
            }
        }

        status_callback("Dependencies installed successfully.".to_string());
        Ok(())
    }

    pub fn run_winetricks_command(
        &self,
        prefix_path: &Path,
        proton: &ProtonInfo,
        verb: &str,
        status_callback: impl Fn(String) + Clone + Send + 'static,
    ) -> Result<(), Box<dyn Error>> {
        // Get winetricks from NaK bin directory (handles symlinks properly)
        let nak_bin = get_nak_bin_path();
        let winetricks_real = nak_bin.join("winetricks");

        if !winetricks_real.exists() {
            return Err(format!("Winetricks not found at {:?}", winetricks_real).into());
        }

        // Prepare environment - resolve proton path through NaK symlink
        let proton_real = resolve_nak_path(&proton.path);
        let wine_bin = proton_real.join("files/bin/wine");
        let wineserver = proton_real.join("files/bin/wineserver");

        // Also resolve prefix path through NaK symlink
        let prefix_real = resolve_nak_path(prefix_path);

        // Include NaK bin directory for bundled tools (cabextract, winetricks, etc.)
        let path_env = format!(
            "{}:{}:{}",
            proton_real.join("files/bin").to_string_lossy(),
            nak_bin.to_string_lossy(),
            std::env::var("PATH").unwrap_or_default()
        );

        if !wine_bin.exists() {
            return Err(format!("Wine binary not found at {:?}", wine_bin).into());
        }

        status_callback(format!("Running winetricks verb: {}", verb));

        let mut cmd = Command::new(&winetricks_real);
        cmd.arg("--unattended")
            .arg(verb)
            .env("WINEPREFIX", &prefix_real)
            .env("WINE", &wine_bin)
            .env("WINESERVER", &wineserver)
            .env("PATH", &path_env)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = cmd.spawn().map_err(|e| {
            format!(
                "Failed to spawn winetricks: {} | winetricks={:?} wine={:?}",
                e, winetricks_real, wine_bin
            )
        })?;

        // Stream Stdout (Simplified for single command)
        let stdout = child.stdout.take().unwrap();
        let cb_out = status_callback.clone();
        thread::spawn(move || {
            let reader = std::io::BufReader::new(stdout);
            for line in reader.lines().map_while(Result::ok) {
                cb_out(format!("[STDOUT] {}", line));
            }
        });

        let status = child.wait()?;

        if !status.success() {
            return Err(format!("Winetricks verb '{}' failed", verb).into());
        }

        Ok(())
    }
}
