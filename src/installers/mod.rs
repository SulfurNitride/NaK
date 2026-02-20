//! Mod manager installation logic (Steam-native)

// Full-only modules (need github, flate2, tar, zip, etc.)
#[cfg(feature = "full")]
mod common;
#[cfg(feature = "full")]
mod mo2;
#[cfg(feature = "full")]
mod plugin;
#[cfg(any(feature = "installer", feature = "full"))]
pub mod symlinks;

// Prefix setup - available with "installer" feature (needs ureq only)
mod prefix_setup;

#[cfg(feature = "full")]
pub use common::{get_available_disk_space, regenerate_nak_tools_scripts, MIN_REQUIRED_DISK_SPACE_GB};
#[cfg(feature = "full")]
pub use mo2::{install_mo2, setup_existing_mo2};
#[cfg(feature = "full")]
pub use plugin::install_plugin;
pub use prefix_setup::{
    apply_dpi, apply_registry_for_game_path, auto_apply_game_registries, cleanup_prefix_drives,
    install_all_dependencies, kill_wineserver, known_game_names, launch_dpi_test_app, DPI_PRESETS,
};

use std::error::Error;
use std::fs;
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

#[cfg(feature = "full")]
use crate::github::GithubRelease;
use crate::logging::log_install;
use crate::steam::SteamProton;

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
}

impl TaskContext {
    pub fn new(
        status: impl Fn(String) + Send + Sync + 'static,
        log: impl Fn(String) + Send + Sync + 'static,
        progress: impl Fn(f32) + Send + Sync + 'static,
        cancel: Arc<AtomicBool>,
    ) -> Self {
        Self {
            status_callback: Arc::new(status),
            log_callback: Arc::new(log),
            progress_callback: Arc::new(progress),
            cancel_flag: cancel,
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

    /// Run a command that can be killed if the user cancels.
    ///
    /// Uses spawn() + try_wait() polling instead of .status() so the child
    /// process can be killed promptly on cancellation.
    pub fn run_cancellable(&self, mut cmd: std::process::Command) -> Result<std::process::ExitStatus, Box<dyn std::error::Error>> {
        let mut child = cmd.spawn()?;

        loop {
            match child.try_wait()? {
                Some(status) => return Ok(status),
                None => {
                    if self.is_cancelled() {
                        let _ = child.kill();
                        let _ = child.wait(); // Reap the zombie
                        return Err("Cancelled".into());
                    }
                    std::thread::sleep(std::time::Duration::from_millis(250));
                }
            }
        }
    }
}

// ============================================================================
// Shared Wine Registry Settings
// ============================================================================

/// Wine registry settings
pub const WINE_SETTINGS_REG: &str = r#"Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"dwrite.dll"="native,builtin"
"dwrite"="native,builtin"
"winmm.dll"="native,builtin"
"winmm"="native,builtin"
"version.dll"="native,builtin"
"version"="native,builtin"
"ArchiveXL.dll"="native,builtin"
"ArchiveXL"="native,builtin"
"Codeware.dll"="native,builtin"
"Codeware"="native,builtin"
"TweakXL.dll"="native,builtin"
"TweakXL"="native,builtin"
"input_loader.dll"="native,builtin"
"input_loader"="native,builtin"
"RED4ext.dll"="native,builtin"
"RED4ext"="native,builtin"
"mod_settings.dll"="native,builtin"
"mod_settings"="native,builtin"
"scc_lib.dll"="native,builtin"
"scc_lib"="native,builtin"
"dxgi.dll"="native,builtin"
"dxgi"="native,builtin"
"dbghelp.dll"="native,builtin"
"dbghelp"="native,builtin"
"d3d12.dll"="native,builtin"
"d3d12"="native,builtin"
"wininet.dll"="native,builtin"
"wininet"="native,builtin"
"winhttp.dll"="native,builtin"
"winhttp"="native,builtin"
"dinput.dll"="native,builtin"
"dinput8"="native,builtin"
"dinput8.dll"="native,builtin"

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

; =============================================================================
; Native file browser integration (opens folders in native file manager)
; =============================================================================
[HKEY_CLASSES_ROOT\Folder\shell\explore\command]
@="C:\\windows\\system32\\winebrowser.exe -nohome \"%1\""

[HKEY_CLASSES_ROOT\Directory\shell\explore\command]
@="C:\\windows\\system32\\winebrowser.exe -nohome \"%1\""

[HKEY_CLASSES_ROOT\Folder\shell\open\command]
@="C:\\windows\\system32\\winebrowser.exe -nohome \"%1\""

[HKEY_CLASSES_ROOT\Directory\shell\open\command]
@="C:\\windows\\system32\\winebrowser.exe -nohome \"%1\""

; =============================================================================
; Native text editor integration (opens text files in native editor)
; =============================================================================
[HKEY_CLASSES_ROOT\txtfile\shell\open\command]
@="C:\\windows\\system32\\winebrowser.exe \"%1\""

[HKEY_CLASSES_ROOT\inifile\shell\open\command]
@="C:\\windows\\system32\\winebrowser.exe \"%1\""

[HKEY_CLASSES_ROOT\.txt]
@="txtfile"

[HKEY_CLASSES_ROOT\.ini]
@="inifile"

[HKEY_CLASSES_ROOT\.cfg]
@="txtfile"

[HKEY_CLASSES_ROOT\.log]
@="txtfile"

[HKEY_CLASSES_ROOT\.xml]
@="txtfile"

[HKEY_CLASSES_ROOT\.json]
@="txtfile"

[HKEY_CLASSES_ROOT\.yml]
@="txtfile"

[HKEY_CLASSES_ROOT\.yaml]
@="txtfile"
"#;

// ============================================================================
// Shared Functions
// ============================================================================

/// Apply Wine registry settings to a prefix
///
/// NOTE: This should be called AFTER winetricks has initialized the prefix.
/// Winetricks handles wineboot internally, so we just apply registry settings here.
pub fn apply_wine_registry_settings(
    prefix_path: &std::path::Path,
    proton: &SteamProton,
    log_callback: &impl Fn(String),
    _app_id: Option<u32>,
) -> Result<(), Box<dyn Error>> {
    use std::io::Write;
    use crate::config::AppConfig;
    use crate::logging::{log_error, log_warning};
    use crate::runtime_wrap;

    let tmp_dir = AppConfig::get_tmp_path();
    fs::create_dir_all(&tmp_dir)?;
    let reg_file = tmp_dir.join("wine_settings.reg");

    let mut file = fs::File::create(&reg_file)?;
    file.write_all(WINE_SETTINGS_REG.as_bytes())?;

    let wine_bin = proton.wine_binary().ok_or_else(|| {
        let err_msg = format!(
            "Wine binary not found for Proton '{}' (checked files/bin/wine and dist/bin/wine)",
            proton.name
        );
        log_callback(format!("Error: {}", err_msg));
        err_msg
    })?;

    let wineserver_bin = proton.wineserver_binary().unwrap_or_else(|| {
        wine_bin.with_file_name("wineserver")
    });

    let bin_dir = proton.bin_dir().ok_or_else(|| {
        let err_msg = "Could not determine Proton bin directory";
        log_callback(format!("Error: {}", err_msg));
        err_msg
    })?;

    let path_env = format!(
        "{}:{}",
        bin_dir.to_string_lossy(),
        std::env::var("PATH").unwrap_or_default()
    );

    log_callback("Applying Wine registry settings...".to_string());
    log_install("Running wine regedit...");

    let reg_envs: Vec<(&str, String)> = vec![
        ("WINEPREFIX", prefix_path.display().to_string()),
        ("WINE", wine_bin.display().to_string()),
        ("WINESERVER", wineserver_bin.display().to_string()),
        ("PATH", path_env),
        ("WINEDLLOVERRIDES", "mshtml=d".to_string()),
        ("PROTON_USE_XALIA", "0".to_string()),
    ];
    let regedit_status = runtime_wrap::build_command(&wine_bin, &reg_envs)
        .arg("regedit")
        .arg(&reg_file)
        .status();

    match regedit_status {
        Ok(status) => {
            if status.success() {
                log_callback("Registry settings applied successfully".to_string());
                log_install("Wine registry settings applied successfully");
            } else {
                let msg = format!("regedit exited with code {:?}", status.code());
                log_callback(format!("Warning: {}", msg));
                log_warning(&msg);
            }
        }
        Err(e) => {
            let msg = format!("Failed to run regedit: {}", e);
            log_callback(format!("Error: {}", msg));
            log_error(&msg);
            return Err(msg.into());
        }
    }

    let _ = fs::remove_file(&reg_file);
    Ok(())
}

/// Fetch the latest MO2 release from GitHub
#[cfg(feature = "full")]
pub fn fetch_latest_mo2_release() -> Result<GithubRelease, Box<dyn Error>> {
    let url = "https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest";
    let res = ureq::get(url)
        .set("User-Agent", "NaK-Rust")
        .call()?
        .into_json()?;
    Ok(res)
}
