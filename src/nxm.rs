//! NXM URL Handler for Steam-native integration
//!
//! Registers NaK as the system's nxm:// URL handler and routes
//! NXM links to the active mod manager instance via direct Proton launch.
//! If the mod manager isn't running, it launches via Steam first.

use std::error::Error;
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;

use crate::config::AppConfig;
use crate::logging::{log_install, log_warning};

pub struct NxmHandler;

impl NxmHandler {
    /// Get the path to config files
    fn config_dir() -> PathBuf {
        AppConfig::get_config_dir()
    }

    /// Set up the NXM handler system (desktop file and handler script)
    pub fn setup() -> Result<(), Box<dyn Error>> {
        let home = std::env::var("HOME")?;
        let nak_dir = Self::config_dir();
        let script_path = nak_dir.join("nxm_handler.sh");
        let applications_dir = PathBuf::from(format!("{}/.local/share/applications", home));
        let desktop_path = applications_dir.join("nak-nxm-handler.desktop");

        // Ensure directories exist
        fs::create_dir_all(&nak_dir)?;
        fs::create_dir_all(&applications_dir)?;

        // Clean up old NXM handler variations
        let old_handlers = [
            "nxm-handler.desktop",
            "nak_nxm_handler.desktop",
            "NaK-nxm-handler.desktop",
            "nak-nxm.desktop",
        ];
        for old in &old_handlers {
            let old_path = applications_dir.join(old);
            if old_path.exists() {
                let _ = fs::remove_file(&old_path);
            }
        }

        // Create the NXM handler script (Direct Proton launch version)
        let script_content = r##"#!/bin/bash
# NaK Global NXM Handler (Direct Proton Launch)
# Forwards nxm:// links to the active mod manager instance directly via Proton
# This bypasses Steam's URL scheme to avoid the security confirmation dialog
# If the mod manager isn't running, it launches it via Steam first

NAK_CONFIG_DIR="$HOME/.config/nak"
ACTIVE_EXE_FILE="$NAK_CONFIG_DIR/active_nxm_exe"
ACTIVE_PREFIX_FILE="$NAK_CONFIG_DIR/active_nxm_prefix"
ACTIVE_APPID_FILE="$NAK_CONFIG_DIR/active_nxm_appid"
NXM_URL="$1"

# Check if handler is configured
if [ ! -f "$ACTIVE_EXE_FILE" ] || [ ! -f "$ACTIVE_PREFIX_FILE" ]; then
    # Check if only old appid file exists (from old NXM Toggle script)
    if [ -f "$ACTIVE_APPID_FILE" ]; then
        zenity --error --text="NXM handler needs to be reconfigured!\n\nYou have an old NXM configuration.\n\nRun the 'NXM Toggle.sh' script in your mod manager's 'NaK Tools' folder to reconfigure." --title="NaK Update Required"
    else
        zenity --error --text="No active mod manager instance configured!\n\nRun the 'NXM Toggle.sh' script in your mod manager's 'NaK Tools' folder to enable NXM handling." --title="NaK Error"
    fi
    exit 1
fi

NXM_EXE=$(cat "$ACTIVE_EXE_FILE")
WINEPREFIX=$(cat "$ACTIVE_PREFIX_FILE")

if [ -z "$NXM_EXE" ] || [ -z "$WINEPREFIX" ]; then
    zenity --error --text="Invalid NXM configuration!\n\nThe configuration files are empty.\n\nRun the 'NXM Toggle.sh' script in your mod manager's 'NaK Tools' folder to reconfigure." --title="NaK Error"
    exit 1
fi

if [ ! -f "$NXM_EXE" ]; then
    zenity --error --text="NXM handler executable not found!\n\nPath: $NXM_EXE\n\nThe mod manager may have been moved or deleted." --title="NaK Error"
    exit 1
fi

if [ ! -d "$WINEPREFIX" ]; then
    zenity --error --text="Wine prefix not found!\n\nPath: $WINEPREFIX\n\nThe prefix may have been moved or deleted." --title="NaK Error"
    exit 1
fi

# Find Steam path
if [ -d "$HOME/.steam/steam" ]; then
    STEAM_PATH="$HOME/.steam/steam"
elif [ -d "$HOME/.local/share/Steam" ]; then
    STEAM_PATH="$HOME/.local/share/Steam"
else
    zenity --error --text="Steam installation not found!" --title="NaK Error"
    exit 1
fi

# Read Proton path from NXM config
ACTIVE_PROTON_FILE="$NAK_CONFIG_DIR/active_nxm_proton"
PROTON_PATH=""
PROTON_BIN=""

# Function to find alternative Proton if configured one is missing
find_proton() {
    # Search locations: Steam common, user compatibilitytools.d, system compatibilitytools.d
    local search_paths=(
        "$STEAM_PATH/steamapps/common/Proton - Experimental"
        "$STEAM_PATH/compatibilitytools.d"
        "/usr/share/steam/compatibilitytools.d"
        "$STEAM_PATH/steamapps/common"
    )

    for search_dir in "${search_paths[@]}"; do
        [ ! -d "$search_dir" ] && continue

        # Check if this is a direct Proton path (Proton Experimental)
        if [ -f "$search_dir/proton" ]; then
            echo "$search_dir"
            return 0
        fi

        # Search subdirectories for Proton installations
        for dir in "$search_dir"/*/; do
            [ ! -d "$dir" ] && continue
            if [ -f "$dir/proton" ]; then
                # Prefer GE-Proton or versions with "10" in the name (Proton 10+)
                local name=$(basename "$dir")
                if [[ "$name" == *"GE-Proton"* ]] || [[ "$name" == *"Proton"*"10"* ]] || [[ "$name" == *"Experimental"* ]] || [[ "$name" == *"CachyOS"* ]] || [[ "$name" == *"cachy"* ]]; then
                    echo "${dir%/}"
                    return 0
                fi
            fi
        done
    done

    # Last resort: find any Proton
    for search_dir in "${search_paths[@]}"; do
        [ ! -d "$search_dir" ] && continue
        for dir in "$search_dir"/*/; do
            [ -f "$dir/proton" ] && echo "${dir%/}" && return 0
        done
    done

    return 1
}

# Try configured Proton first
if [ -f "$ACTIVE_PROTON_FILE" ]; then
    PROTON_PATH=$(cat "$ACTIVE_PROTON_FILE")
    PROTON_BIN="$PROTON_PATH/proton"
fi

# If configured Proton is missing, search for alternatives
if [ ! -f "$PROTON_BIN" ]; then
    echo "NaK: Configured Proton not found at: $PROTON_PATH"
    echo "NaK: Searching for alternative Proton..."

    ALT_PROTON=$(find_proton)
    if [ -n "$ALT_PROTON" ] && [ -f "$ALT_PROTON/proton" ]; then
        echo "NaK: Found alternative Proton: $ALT_PROTON"
        PROTON_PATH="$ALT_PROTON"
        PROTON_BIN="$PROTON_PATH/proton"
        # Update config for future use
        echo "$PROTON_PATH" > "$ACTIVE_PROTON_FILE"
    else
        zenity --error --text="No Proton installation found!\n\nThe configured Proton was not found and no alternative could be located.\n\nPlease ensure Proton is installed via Steam or run 'NXM Toggle.sh' again." --title="NaK Error"
        exit 1
    fi
fi

# Determine the mod manager type and process name
NXM_DIR=$(dirname "$NXM_EXE")
if [ -f "$NXM_DIR/ModOrganizer.exe" ]; then
    MOD_MANAGER="MO2"
    PROCESS_NAME="ModOrganizer.exe"
    NXM_ARGS=""
elif [ -f "$NXM_DIR/Vortex.exe" ]; then
    MOD_MANAGER="Vortex"
    PROCESS_NAME="Vortex.exe"
    NXM_ARGS="-d"  # Vortex requires -d flag for NXM download handling
else
    MOD_MANAGER="Unknown"
    PROCESS_NAME=""
    NXM_ARGS=""
fi

# Check if mod manager is already running (look for wine process with the exe name)
is_running() {
    pgrep -f "$PROCESS_NAME" > /dev/null 2>&1
}

# If mod manager isn't running, launch it via Steam first
if [ -n "$PROCESS_NAME" ] && ! is_running; then
    echo "NaK: $MOD_MANAGER is not running, launching via Steam..."

    # Read AppID and calculate 64-bit Game ID
    if [ -f "$ACTIVE_APPID_FILE" ]; then
        APPID=$(cat "$ACTIVE_APPID_FILE")
        if [ -n "$APPID" ]; then
            # Convert 32-bit AppID to 64-bit Game ID: (appid << 32) | 0x02000000
            GAME_ID=$(python3 -c "print(($APPID << 32) | 0x02000000)")

            # Launch via Steam
            xdg-open "steam://rungameid/$GAME_ID"

            # Wait for mod manager to start (up to 30 seconds)
            echo "NaK: Waiting for $MOD_MANAGER to start..."
            for i in {1..30}; do
                sleep 1
                if is_running; then
                    echo "NaK: $MOD_MANAGER is now running"
                    echo "NaK: Waiting for $MOD_MANAGER to fully initialize..."
                    sleep 8  # Give it time to fully initialize IPC server
                    break
                fi
            done

            if ! is_running; then
                zenity --warning --text="$MOD_MANAGER may not have started properly.\n\nThe NXM link will still be processed, but you may need to start $MOD_MANAGER manually." --title="NaK Warning"
            fi
        fi
    fi
fi

# Set up environment for Proton
export WINEPREFIX
export STEAM_COMPAT_DATA_PATH="${WINEPREFIX%/pfx}"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_PATH"
export WINEDLLOVERRIDES="winemenubuilder.exe="

# Launch mod manager with NXM link via Proton
echo "NaK: Handling NXM link via Proton..."
echo "  EXE: $NXM_EXE"
echo "  URL: $NXM_URL"
if [ -n "$NXM_ARGS" ]; then
    "$PROTON_BIN" run "$NXM_EXE" $NXM_ARGS "$NXM_URL"
else
    "$PROTON_BIN" run "$NXM_EXE" "$NXM_URL"
fi
"##;

        let mut file = fs::File::create(&script_path)?;
        file.write_all(script_content.as_bytes())?;
        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        // Create Desktop Entry
        // Note: According to XDG spec, Exec paths with special chars should be quoted,
        // but some implementations have issues with quotes. Since our path is in
        // ~/.config/nak/ (no spaces), we don't need quotes.
        let desktop_content = format!(
            r#"[Desktop Entry]
Type=Application
Version=1.1
Name=NaK NXM Handler
GenericName=Nexus Mods Link Handler
Comment=Handle Nexus Mods nxm:// links via NaK
Exec={} %u
Icon=applications-games
Terminal=false
Categories=Game;Utility;
MimeType=x-scheme-handler/nxm;
StartupNotify=false
NoDisplay=false
"#,
            script_path.to_string_lossy()
        );

        let mut dfile = fs::File::create(&desktop_path)?;
        dfile.write_all(desktop_content.as_bytes())?;

        // Update desktop database so the app appears in application pickers
        // This is required for new installations - without it, the app won't
        // show up when users try to select an application to handle nxm:// links
        let db_result = std::process::Command::new("update-desktop-database")
            .arg(&applications_dir)
            .status();

        if let Err(e) = db_result {
            log_warning(&format!("Failed to run update-desktop-database: {}", e));
        }

        // Register MIME type in user's mimeapps.list (XDG standard location)
        // This ensures the handler is set even if xdg-mime has issues
        let mimeapps_path = PathBuf::from(format!("{}/.config/mimeapps.list", home));
        Self::add_mime_association(&mimeapps_path, "x-scheme-handler/nxm", "nak-nxm-handler.desktop");

        // Also try the legacy location some systems still use
        let legacy_mimeapps = applications_dir.join("mimeapps.list");
        Self::add_mime_association(&legacy_mimeapps, "x-scheme-handler/nxm", "nak-nxm-handler.desktop");

        // Register with xdg-mime as well (belt and suspenders approach)
        let status = std::process::Command::new("xdg-mime")
            .arg("default")
            .arg("nak-nxm-handler.desktop")
            .arg("x-scheme-handler/nxm")
            .status();

        match status {
            Ok(s) if s.success() => {
                log_install("NXM Handler registered successfully (Direct Proton)");
            }
            Ok(_) => {
                // xdg-mime failed but we also wrote to mimeapps.list directly
                log_warning("xdg-mime returned error, but handler was registered via mimeapps.list");
            }
            Err(e) => {
                log_warning(&format!("xdg-mime not available ({}), handler registered via mimeapps.list", e));
            }
        }

        // Fix Flatpak browser permissions for NXM handler access
        Self::fix_flatpak_browsers();

        Ok(())
    }

    /// Add a MIME type association to a mimeapps.list file
    fn add_mime_association(path: &PathBuf, mime_type: &str, desktop_file: &str) {
        // Read existing content or start fresh
        let content = fs::read_to_string(path).unwrap_or_default();

        let entry = format!("{}={}", mime_type, desktop_file);
        let section_header = "[Default Applications]";

        // Check if already correctly set
        if content.contains(&entry) {
            return;
        }

        let new_content = if content.contains(section_header) {
            // Section exists - check if mime type is already there
            let mut lines: Vec<&str> = content.lines().collect();
            let mut found = false;
            let mut in_section = false;

            for line in &mut lines {
                if line.starts_with('[') {
                    in_section = *line == section_header;
                } else if in_section && line.starts_with(&format!("{}=", mime_type)) {
                    // Update existing entry - but we can't mutate through &str
                    found = true;
                    break;
                }
            }

            if found {
                // Replace the existing entry
                content
                    .lines()
                    .map(|line| {
                        if line.starts_with(&format!("{}=", mime_type)) {
                            entry.clone()
                        } else {
                            line.to_string()
                        }
                    })
                    .collect::<Vec<_>>()
                    .join("\n")
            } else {
                // Add entry after section header
                content.replace(section_header, &format!("{}\n{}", section_header, entry))
            }
        } else {
            // No section - add it
            if content.is_empty() {
                format!("{}\n{}\n", section_header, entry)
            } else {
                format!("{}\n\n{}\n{}\n", content.trim_end(), section_header, entry)
            }
        };

        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }

        let _ = fs::write(path, new_content);
    }

    /// Fix Flatpak browser permissions for NXM handling
    ///
    /// Flatpak browsers are sandboxed and can't launch external scripts or access
    /// removable media by default. This adds the necessary overrides.
    pub fn fix_flatpak_browsers() {
        const FLATPAK_BROWSERS: &[&str] = &[
            "com.brave.Browser",
            "com.google.Chrome",
            "org.chromium.Chromium",
            "com.github.nickvergessen.nickvergessen_chromium",
            "org.mozilla.firefox",
            "one.ablaze.floorp",
            "net.waterfox.waterfox",
            "app.zen_browser.zen",
        ];

        // Check if flatpak command exists
        let flatpak_check = std::process::Command::new("flatpak")
            .arg("--version")
            .output();

        if flatpak_check.is_err() {
            // Flatpak not installed, nothing to do
            return;
        }

        // Get list of installed flatpaks
        let installed = match std::process::Command::new("flatpak")
            .args(["list", "--app", "--columns=application"])
            .output()
        {
            Ok(output) => String::from_utf8_lossy(&output.stdout).to_string(),
            Err(_) => return,
        };

        let mut fixed_count = 0;

        for browser_id in FLATPAK_BROWSERS {
            if installed.contains(browser_id) {
                // Apply the necessary overrides
                let result = std::process::Command::new("flatpak")
                    .args([
                        "override",
                        "--user",
                        browser_id,
                        "--filesystem=home",
                        "--filesystem=/run/media/",
                        "--talk-name=org.freedesktop.portal.*",
                    ])
                    .status();

                if let Ok(status) = result {
                    if status.success() {
                        log_install(&format!("Fixed Flatpak permissions for {}", browser_id));
                        fixed_count += 1;
                    }
                }
            }
        }

        if fixed_count > 0 {
            log_install(&format!(
                "Applied Flatpak NXM handler permissions to {} browser(s)",
                fixed_count
            ));
        }
    }
}
