//! Native dependency management for NaK
//!
//! Replaces winetricks for standard dependency installation.
//! Provides direct downloads, cab extraction, and Wine command helpers.
//!
//! Also includes Linux tool management (cabextract, winetricks binaries).

pub mod direct_dll;
pub mod directx;
pub mod exe_installer;
pub mod precache;
pub mod registry;
pub mod tools;
pub mod wine_utils;

use std::error::Error;
use std::path::PathBuf;
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use crate::steam::SteamProton;

// Re-exports for Windows dependencies
pub use registry::{DepType, Dependency, STANDARD_DEPS};

// Re-exports for Linux tools
pub use tools::{check_command_available, ensure_cabextract, ensure_winetricks};

/// Context for dependency installation
#[derive(Clone)]
pub struct DepInstallContext {
    /// Prefix path (the pfx directory)
    pub prefix: PathBuf,
    /// Proton to use for installation
    pub proton: SteamProton,
    /// Log callback
    log_callback: Arc<dyn Fn(String) + Send + Sync>,
    /// Cancellation flag
    pub cancel_flag: Arc<AtomicBool>,
}

impl DepInstallContext {
    pub fn new(
        prefix: PathBuf,
        proton: SteamProton,
        log: impl Fn(String) + Send + Sync + 'static,
        cancel: Arc<AtomicBool>,
    ) -> Self {
        Self {
            prefix,
            proton,
            log_callback: Arc::new(log),
            cancel_flag: cancel,
        }
    }

    pub fn log(&self, msg: &str) {
        (self.log_callback)(msg.to_string());
    }

    /// Get the tmp directory for downloads
    pub fn tmp_dir(&self) -> PathBuf {
        crate::config::AppConfig::get_tmp_path()
    }
}

/// Native dependency manager - replaces winetricks for core installs
pub struct NativeDependencyManager {
    ctx: DepInstallContext,
}

impl NativeDependencyManager {
    pub fn new(ctx: DepInstallContext) -> Self {
        Self { ctx }
    }

    /// Install a single dependency
    pub fn install_dep(&self, dep: &Dependency) -> Result<(), Box<dyn Error>> {
        self.ctx.log(&format!("Installing {}...", dep.name));

        match &dep.dep_type {
            DepType::ExeInstaller { args } => {
                exe_installer::install(dep, &self.ctx, args)?;
            }
            DepType::DirectXCab { dll_patterns, cab_patterns } => {
                directx::install(dep, &self.ctx, cab_patterns, dll_patterns)?;
            }
            DepType::DirectDll => {
                direct_dll::install(dep, &self.ctx)?;
            }
            DepType::GitHubRelease => {
                // VKD3D-Proton - skip, Proton already includes it
                self.ctx.log(&format!("Skipping {} (Proton includes vkd3d)", dep.name));
                return Ok(());
            }
        }

        // Apply DLL overrides
        for dll in dep.dll_overrides {
            wine_utils::set_dll_override(&self.ctx, dll, "native,builtin")?;
        }

        // Register COM DLLs (xactengine, xaudio, etc.)
        if !dep.register_dlls.is_empty() {
            self.ctx.log(&format!("Registering {} COM DLLs...", dep.register_dlls.len()));
            for dll in dep.register_dlls {
                wine_utils::register_dll(&self.ctx, dll)?;
            }
        }

        self.ctx.log(&format!("{} installed successfully", dep.name));
        Ok(())
    }
}
