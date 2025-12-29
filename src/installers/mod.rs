//! Mod manager installation logic

mod mo2;
mod prefix_setup;
mod vortex;

pub use mo2::{install_mo2, setup_existing_mo2};
pub use prefix_setup::{
    apply_dpi, brief_launch_and_kill, create_game_folders, get_install_proton,
    install_all_dependencies, kill_wineserver, launch_dpi_test_app, DPI_PRESETS,
};
pub use vortex::{install_vortex, setup_existing_vortex};

use std::error::Error;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use crate::config::AppConfig;
use crate::logging::{log_install, log_warning};
use crate::wine::{GithubRelease, ProtonInfo};

// ============================================================================
// Shared Types
// ============================================================================

/// Context for background installation tasks
#[derive(Clone)]
pub struct TaskContext {
    pub status_callback: Arc<dyn Fn(String) + Send + Sync>,
    pub log_callback: Arc<dyn Fn(String) + Send + Sync>,
    pub progress_callback: Arc<dyn Fn(f32) + Send + Sync>,
    pub cancel_flag: Arc<AtomicBool>,
    pub winetricks_path: PathBuf,
}

impl TaskContext {
    pub fn new(
        status: impl Fn(String) + Send + Sync + 'static,
        log: impl Fn(String) + Send + Sync + 'static,
        progress: impl Fn(f32) + Send + Sync + 'static,
        cancel: Arc<AtomicBool>,
        winetricks: PathBuf,
    ) -> Self {
        Self {
            status_callback: Arc::new(status),
            log_callback: Arc::new(log),
            progress_callback: Arc::new(progress),
            cancel_flag: cancel,
            winetricks_path: winetricks,
        }
    }

    pub fn set_status(&self, msg: String) {
        (self.status_callback)(msg);
    }

    pub fn log(&self, msg: String) {
        (self.log_callback)(msg);
    }

    pub fn set_progress(&self, p: f32) {
        (self.progress_callback)(p);
    }

    pub fn is_cancelled(&self) -> bool {
        self.cancel_flag.load(std::sync::atomic::Ordering::Relaxed)
    }
}

// ============================================================================
// Shared Wine Registry Settings
// ============================================================================

/// Wine registry settings from src/utils/wine_settings.reg (exact match)
pub const WINE_SETTINGS_REG: &str = r#"Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dwrite.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dwrite"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winmm.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winmm"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"version.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"version"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"ArchiveXL.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"ArchiveXL"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"Codeware.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"Codeware"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"TweakXL.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"TweakXL"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"input_loader.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"input_loader"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"RED4ext.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"RED4ext"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"mod_settings.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"mod_settings"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"scc_lib.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"scc_lib"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dxgi.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dxgi"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dbghelp.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dbghelp"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"d3d12.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"d3d12"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"wininet.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"wininet"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winhttp.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winhttp"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dinput.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dinput8"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dinput8.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"mscoree.dll"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"mscoree"="native,builtin"

[HKEY_CURRENT_USER\Software\Wine]
"ShowDotFiles"="Y"

[HKEY_CURRENT_USER\Control Panel\Desktop]
"FontSmoothing"="2"
"FontSmoothingGamma"=dword:00000578
"FontSmoothingOrientation"=dword:00000001
"FontSmoothingType"=dword:00000002

[HKEY_CURRENT_USER\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers]
@="~ HIGHDPIAWARE"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\Pandora Behaviour Engine+.exe\X11 Driver]
"Decorated"="N"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\Vortex.exe\X11 Driver]
"Decorated"="N"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\SSEEdit.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\SSEEdit64.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\FO4Edit.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\FO4Edit64.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\TES4Edit.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\TES4Edit64.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\xEdit64.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\SF1Edit64.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\FNVEdit.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\FNVEdit64.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\xFOEdit.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\xFOEdit64.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\xSFEEdit.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\xSFEEdit64.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\xTESEdit.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\xTESEdit64.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\FO3Edit.exe]
"Version"="winxp"

[HKEY_CURRENT_USER\Software\Wine\AppDefaults\FO3Edit64.exe]
"Version"="winxp"
"#;

// ============================================================================
// Shared Functions
// ============================================================================

/// Apply Wine registry settings to a prefix
pub fn apply_wine_registry_settings(
    prefix_path: &Path,
    proton: &ProtonInfo,
    log_callback: &impl Fn(String),
) -> Result<(), Box<dyn Error>> {
    use std::io::Write;

    // Create temp file for registry
    let config = AppConfig::load();
    let tmp_dir = config.get_data_path().join("tmp");
    fs::create_dir_all(&tmp_dir)?;
    let reg_file = tmp_dir.join("wine_settings.reg");

    let mut file = fs::File::create(&reg_file)?;
    file.write_all(WINE_SETTINGS_REG.as_bytes())?;

    // Get wine binary path
    let wine_bin = proton.path.join("files/bin/wine");
    let wineboot_bin = proton.path.join("files/bin/wineboot");
    if !wine_bin.exists() {
        log_callback(format!("Warning: Wine binary not found at {:?}", wine_bin));
        return Ok(());
    }

    // Initialize prefix with wineboot first (required before regedit)
    log_callback("Initializing Wine prefix...".to_string());
    log_install("Initializing Wine prefix with wineboot...");

    let wineboot_status = std::process::Command::new(&wineboot_bin)
        .arg("-u")
        .env("WINEPREFIX", prefix_path)
        .env(
            "LD_LIBRARY_PATH",
            "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu",
        )
        .env("WINEDLLOVERRIDES", "mscoree=d;mshtml=d")
        .env("PROTON_NO_XALIA", "1")
        .status();

    match wineboot_status {
        Ok(s) if s.success() => {
            log_callback("Prefix initialized successfully".to_string());
        }
        Ok(s) => {
            log_callback(format!("Warning: wineboot exited with code {:?}", s.code()));
        }
        Err(e) => {
            log_callback(format!("Warning: Failed to run wineboot: {}", e));
        }
    }

    // Give Wine a moment to settle
    std::thread::sleep(std::time::Duration::from_secs(2));

    log_callback("Running wine regedit...".to_string());
    log_install("Applying Wine registry settings...");

    // Run wine regedit
    let status = std::process::Command::new(&wine_bin)
        .arg("regedit")
        .arg(&reg_file)
        .env("WINEPREFIX", prefix_path)
        .env(
            "LD_LIBRARY_PATH",
            "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu",
        )
        .env("PROTON_NO_XALIA", "1")
        .status();

    match status {
        Ok(s) if s.success() => {
            log_callback("Registry settings applied successfully".to_string());
            log_install("Wine registry settings applied successfully");
        }
        Ok(s) => {
            log_callback(format!("Warning: regedit exited with code {:?}", s.code()));
            log_warning(&format!("regedit exited with code {:?}", s.code()));
        }
        Err(e) => {
            log_callback(format!("Warning: Failed to run regedit: {}", e));
            log_warning(&format!("Failed to run regedit: {}", e));
        }
    }

    // Cleanup temp file
    let _ = fs::remove_file(&reg_file);

    Ok(())
}

/// Fetch the latest MO2 release from GitHub
pub fn fetch_latest_mo2_release() -> Result<GithubRelease, Box<dyn Error>> {
    let url = "https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest";
    let res = ureq::get(url)
        .set("User-Agent", "NaK-Rust")
        .call()?
        .into_json()?;
    Ok(res)
}

/// Fetch the latest Vortex release from GitHub
pub fn fetch_latest_vortex_release() -> Result<GithubRelease, Box<dyn Error>> {
    let url = "https://api.github.com/repos/Nexus-Mods/Vortex/releases/latest";
    let res = ureq::get(url)
        .set("User-Agent", "NaK-Rust")
        .call()?
        .into_json()?;
    Ok(res)
}

/// Standard dependencies for mod managers
pub const STANDARD_DEPS: &[&str] = &[
    "xact",
    "xact_x64",
    "vcrun2022",
    "dotnet6",
    "dotnet7",
    "dotnet8",
    "dotnet9",
    "dotnetdesktop6",
    "d3dcompiler_47",
    "d3dx11_43",
    "d3dcompiler_43",
    "d3dx9_43",
    "d3dx9",
    "vkd3d",
];

/// .NET 9 SDK URL
pub const DOTNET9_SDK_URL: &str =
    "https://builds.dotnet.microsoft.com/dotnet/Sdk/9.0.203/dotnet-sdk-9.0.203-win-x64.exe";
