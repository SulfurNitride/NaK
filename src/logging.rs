//! NaK Logging System
//!
//! Provides structured logging with system information header

use chrono::Local;
use std::fs::{self, File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::Command;
use std::sync::{Arc, Mutex, OnceLock};

static LOGGER: OnceLock<Arc<Mutex<NakLogger>>> = OnceLock::new();

// ============================================================================
// System Information Detection
// ============================================================================

#[derive(Debug, Clone)]
pub struct SystemInfo {
    pub app_version: String,
    pub distro: String,
    pub distro_version: String,
    pub kernel: String,
    pub session_type: String,
    pub desktop_env: String,
    pub cpu: String,
    pub memory_gb: String,
    pub gpu: String,
    pub glibc_version: String,
    pub disk_space_free: String,
}

impl SystemInfo {
    pub fn detect() -> Self {
        Self {
            app_version: env!("CARGO_PKG_VERSION").to_string(),
            distro: detect_distro(),
            distro_version: detect_distro_version(),
            kernel: detect_kernel(),
            session_type: detect_session_type(),
            desktop_env: detect_desktop_env(),
            cpu: detect_cpu(),
            memory_gb: detect_memory(),
            gpu: detect_gpu(),
            glibc_version: detect_glibc(),
            disk_space_free: detect_disk_space(),
        }
    }

    pub fn to_log_header(&self) -> String {
        format!(
r#"================================================================================
NaK Log - {}
================================================================================
Application:   NaK v{}
System Info:
  Distro:      {} {}
  Kernel:      {}
  Session:     {}
  Desktop:     {}
  CPU:         {}
  Memory:      {}
  GPU:         {}
  GLIBC:       {}
  Disk Free:   {}
================================================================================
"#,
            Local::now().format("%Y-%m-%d %H:%M:%S"),
            self.app_version,
            self.distro,
            self.distro_version,
            self.kernel,
            self.session_type,
            self.desktop_env,
            self.cpu,
            self.memory_gb,
            self.gpu,
            self.glibc_version,
            self.disk_space_free
        )
    }
}

fn detect_session_type() -> String {
    std::env::var("XDG_SESSION_TYPE").unwrap_or_else(|_| "Unknown".to_string())
}

fn detect_glibc() -> String {
    if let Ok(output) = Command::new("ldd").arg("--version").output() {
        if output.status.success() {
            // First line usually: "ldd (GNU libc) 2.35"
            let out = String::from_utf8_lossy(&output.stdout);
            if let Some(line) = out.lines().next() {
                return line.split(')').next_back().unwrap_or("Unknown").trim().to_string();
            }
        }
    }
    "Unknown".to_string()
}

fn detect_disk_space() -> String {
    // Check space on HOME
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    if let Ok(output) = Command::new("df").arg("-h").arg(&home).output() {
        if output.status.success() {
            // Output is header + 1 line. We want the 'Avail' column (usually 4th)
            let out = String::from_utf8_lossy(&output.stdout);
            if let Some(line) = out.lines().nth(1) {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() >= 4 {
                    return format!("{} (on {})", parts[3], parts[5]); // Avail + Mount point
                }
            }
        }
    }
    "Unknown".to_string()
}

fn detect_distro() -> String {    // Try /etc/os-release first
    if let Ok(file) = File::open("/etc/os-release") {
        let reader = BufReader::new(file);
        for line in reader.lines().map_while(Result::ok) {
            if line.starts_with("NAME=") {
                return line
                    .trim_start_matches("NAME=")
                    .trim_matches('"')
                    .to_string();
            }
        }
    }

    // Fallback to lsb_release
    if let Ok(output) = Command::new("lsb_release").arg("-is").output() {
        if output.status.success() {
            return String::from_utf8_lossy(&output.stdout).trim().to_string();
        }
    }

    "Unknown".to_string()
}

fn detect_distro_version() -> String {
    // Try /etc/os-release first
    if let Ok(file) = File::open("/etc/os-release") {
        let reader = BufReader::new(file);
        for line in reader.lines().map_while(Result::ok) {
            if line.starts_with("VERSION_ID=") {
                return line
                    .trim_start_matches("VERSION_ID=")
                    .trim_matches('"')
                    .to_string();
            }
        }
    }

    // Fallback to lsb_release
    if let Ok(output) = Command::new("lsb_release").arg("-rs").output() {
        if output.status.success() {
            return String::from_utf8_lossy(&output.stdout).trim().to_string();
        }
    }

    "".to_string()
}

fn detect_kernel() -> String {
    if let Ok(output) = Command::new("uname").arg("-r").output() {
        if output.status.success() {
            return String::from_utf8_lossy(&output.stdout).trim().to_string();
        }
    }
    "Unknown".to_string()
}

fn detect_desktop_env() -> String {
    // Check common environment variables
    if let Ok(de) = std::env::var("XDG_CURRENT_DESKTOP") {
        return de;
    }
    if let Ok(de) = std::env::var("DESKTOP_SESSION") {
        return de;
    }
    if let Ok(de) = std::env::var("XDG_SESSION_DESKTOP") {
        return de;
    }

    // Check for specific DEs
    if std::env::var("KDE_FULL_SESSION").is_ok() {
        return "KDE".to_string();
    }
    if std::env::var("GNOME_DESKTOP_SESSION_ID").is_ok() {
        return "GNOME".to_string();
    }

    "Unknown".to_string()
}

fn detect_cpu() -> String {
    if let Ok(file) = File::open("/proc/cpuinfo") {
        let reader = BufReader::new(file);
        for line in reader.lines().map_while(Result::ok) {
            if line.starts_with("model name") {
                if let Some(name) = line.split(':').nth(1) {
                    return name.trim().to_string();
                }
            }
        }
    }
    "Unknown".to_string()
}

fn detect_memory() -> String {
    if let Ok(file) = File::open("/proc/meminfo") {
        let reader = BufReader::new(file);
        for line in reader.lines().map_while(Result::ok) {
            if line.starts_with("MemTotal:") {
                if let Some(kb_str) = line.split_whitespace().nth(1) {
                    if let Ok(kb) = kb_str.parse::<u64>() {
                        let gb = kb as f64 / 1024.0 / 1024.0;
                        return format!("{:.1} GB", gb);
                    }
                }
            }
        }
    }
    "Unknown".to_string()
}

fn detect_gpu() -> String {
    // Try lspci for GPU info
    if let Ok(output) = Command::new("lspci").output() {
        if output.status.success() {
            let output_str = String::from_utf8_lossy(&output.stdout);
            for line in output_str.lines() {
                if line.contains("VGA") || line.contains("3D") || line.contains("Display") {
                    // Extract the device name after the colon
                    if let Some(device) = line.split(':').next_back() {
                        let gpu = device.trim();
                        // Shorten if too long
                        if gpu.len() > 60 {
                            return format!("{}...", &gpu[..57]);
                        }
                        return gpu.to_string();
                    }
                }
            }
        }
    }
    "Unknown".to_string()
}

// ============================================================================
// Log Levels
// ============================================================================

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum LogLevel {
    Info,
    Action, // User actions (button clicks, etc.)
    Download,
    Install,
    Warning,
    Error,
}

impl LogLevel {
    pub fn prefix(&self) -> &'static str {
        match self {
            LogLevel::Info => "[INFO]",
            LogLevel::Action => "[ACTION]",
            LogLevel::Download => "[DOWNLOAD]",
            LogLevel::Install => "[INSTALL]",
            LogLevel::Warning => "[WARNING]",
            LogLevel::Error => "[ERROR]",
        }
    }
}

// ============================================================================
// NaK Logger
// ============================================================================

pub struct NakLogger {
    log_file: Option<File>,
}

impl NakLogger {
    pub fn new() -> Self {
        let home = std::env::var("HOME").unwrap_or_default();
        let log_dir = PathBuf::from(format!("{}/NaK/logs", home));
        let _ = fs::create_dir_all(&log_dir);

        let timestamp = Local::now().format("%Y%m%d_%H%M%S");
        let log_path = log_dir.join(format!("nak_{}.log", timestamp));

        let log_file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .ok();

        let mut logger = Self { log_file };

        // Write system info header
        let sys_info = SystemInfo::detect();
        let header = sys_info.to_log_header();
        logger.write_raw(&header);

        logger
    }

    fn write_raw(&mut self, msg: &str) {
        // Write to file
        if let Some(ref mut file) = self.log_file {
            let _ = writeln!(file, "{}", msg);
            let _ = file.flush();
        }

        // Also print to console
        println!("{}", msg);
    }

    pub fn log(&mut self, level: LogLevel, message: &str) {
        let timestamp = Local::now().format("%H:%M:%S");
        let formatted = format!("[{}] {} {}", timestamp, level.prefix(), message);
        self.write_raw(&formatted);
    }
}

// ============================================================================
// Global Logger Access
// ============================================================================

/// Initialize the global logger (call once at startup)
pub fn init_logger() {
    LOGGER.get_or_init(|| Arc::new(Mutex::new(NakLogger::new())));
}

/// Get the global logger instance
fn logger() -> Arc<Mutex<NakLogger>> {
    LOGGER
        .get_or_init(|| Arc::new(Mutex::new(NakLogger::new())))
        .clone()
}

// ============================================================================
// Convenience Logging Functions
// ============================================================================

pub fn log_info(message: &str) {
    if let Ok(mut log) = logger().lock() {
        log.log(LogLevel::Info, message);
    }
}

pub fn log_action(message: &str) {
    if let Ok(mut log) = logger().lock() {
        log.log(LogLevel::Action, message);
    }
}

pub fn log_download(message: &str) {
    if let Ok(mut log) = logger().lock() {
        log.log(LogLevel::Download, message);
    }
}

pub fn log_install(message: &str) {
    if let Ok(mut log) = logger().lock() {
        log.log(LogLevel::Install, message);
    }
}

pub fn log_warning(message: &str) {
    if let Ok(mut log) = logger().lock() {
        log.log(LogLevel::Warning, message);
    }
}

pub fn log_error(message: &str) {
    if let Ok(mut log) = logger().lock() {
        log.log(LogLevel::Error, message);
    }
}
