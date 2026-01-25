//! Mod manager installation logic (Steam-native)

mod common;
mod compatdata_scanner;
mod mo2;
mod prefix_setup;
mod vortex;

pub use common::{get_available_disk_space, regenerate_nak_tools_scripts, MIN_REQUIRED_DISK_SPACE_GB};
pub use mo2::{install_mo2, setup_existing_mo2};
pub use prefix_setup::{
    apply_dpi, create_game_folders,
    install_all_dependencies, kill_wineserver, launch_dpi_test_app, DPI_PRESETS,
};
pub use vortex::{install_vortex, setup_existing_vortex};

use std::error::Error;
use std::fs;
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use serde::Deserialize;

use crate::logging::log_install;
use crate::steam::SteamProton;

// ============================================================================
// GitHub Release Types (for fetching MO2/Vortex releases)
// ============================================================================

#[derive(Deserialize, Debug, Clone)]
pub struct GithubRelease {
    pub tag_name: String,
    pub assets: Vec<GithubAsset>,
}

#[derive(Deserialize, Debug, Clone)]
pub struct GithubAsset {
    pub name: String,
    pub browser_download_url: String,
}

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
pub fn apply_wine_registry_settings(
    prefix_path: &std::path::Path,
    proton: &SteamProton,
    log_callback: &impl Fn(String),
) -> Result<(), Box<dyn Error>> {
    use std::io::Write;
    use crate::config::AppConfig;
    use crate::logging::{log_error, log_warning};
    use crate::steam::is_flatpak_steam;

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

    // Check if we need to run through Flatpak
    let use_flatpak = is_flatpak_steam();
    if use_flatpak {
        log_install("Flatpak Steam detected - running wine commands through Flatpak");
    }

    // Helper to build wine command - either direct or through flatpak
    let build_wine_cmd = |wine_args: &[&str]| -> std::process::Command {
        if use_flatpak {
            let mut cmd = std::process::Command::new("flatpak");
            cmd.arg("run")
                .arg("--command=bash")
                .arg("com.valvesoftware.Steam")
                .arg("-c");

            // Build the command string to run inside Flatpak
            let wine_path = wine_bin.to_string_lossy();
            let prefix_str = prefix_path.to_string_lossy();
            let wineserver_str = wineserver_bin.to_string_lossy();
            let args_str = wine_args.join(" ");

            let bash_cmd = format!(
                "WINEPREFIX='{}' WINE='{}' WINESERVER='{}' WINEDLLOVERRIDES='mshtml=d' PROTON_USE_XALIA='0' '{}' {}",
                prefix_str, wine_path, wineserver_str, wine_path, args_str
            );
            cmd.arg(bash_cmd);
            cmd
        } else {
            let mut cmd = std::process::Command::new(&wine_bin);
            for arg in wine_args {
                cmd.arg(arg);
            }
            let path_env = format!(
                "{}:{}",
                bin_dir.to_string_lossy(),
                std::env::var("PATH").unwrap_or_default()
            );
            cmd.env("WINEPREFIX", prefix_path)
                .env("WINE", &wine_bin)
                .env("WINESERVER", &wineserver_bin)
                .env("PATH", &path_env)
                .env("LD_LIBRARY_PATH", "/usr/lib:/usr/lib/x86_64-linux-gnu:/lib:/lib/x86_64-linux-gnu")
                .env("WINEDLLOVERRIDES", "mshtml=d")
                .env("PROTON_USE_XALIA", "0");
            cmd
        }
    };

    log_callback("Initializing Wine prefix...".to_string());
    log_install("Initializing Wine prefix with wineboot...");

    let mut wineboot_cmd = build_wine_cmd(&["wineboot", "-u"]);

    match wineboot_cmd.status() {
        Ok(status) => {
            if status.success() {
                log_callback("Prefix initialized successfully".to_string());
            } else {
                let msg = format!("wineboot exited with code {:?}", status.code());
                log_callback(format!("Warning: {}", msg));
                log_warning(&msg);
            }
        }
        Err(e) => {
            let msg = format!("Failed to run wineboot: {}", e);
            log_callback(format!("Error: {}", msg));
            log_error(&msg);
            return Err(msg.into());
        }
    }

    log_callback("Applying Wine registry settings...".to_string());
    log_install("Running wine regedit...");

    let reg_file_str = reg_file.to_string_lossy().to_string();
    let mut regedit_cmd = build_wine_cmd(&["regedit", &reg_file_str]);

    match regedit_cmd.status() {
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
