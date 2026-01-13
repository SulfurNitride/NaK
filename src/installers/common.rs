//! Common installer utilities shared between MO2 and Vortex
//!
//! This module contains shared logic to reduce code duplication between
//! the MO2 and Vortex installers.

use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use crate::logging::{log_error, log_install, log_warning};

use super::TaskContext;

// Re-export ManagerType from config for use in other installer modules
pub use crate::config::ManagerType;

// ============================================================================
// Shared Installation Errors
// ============================================================================

/// Custom error type for installation operations
#[derive(Debug)]
pub enum InstallError {
    /// User cancelled the operation
    Cancelled,
    /// Executable not found at expected path
    ExeNotFound { exe_name: String, path: String },
    /// Failed to create directory
    DirectoryCreation { path: String, reason: String },
    /// Insufficient disk space
    InsufficientDiskSpace { required_gb: f64, available_gb: f64 },
    /// Steam integration error
    SteamError { reason: String },
    /// Generic error with context
    Other { context: String, reason: String },
}

impl std::fmt::Display for InstallError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            InstallError::Cancelled => write!(f, "Installation cancelled by user"),
            InstallError::ExeNotFound { exe_name, path } => {
                write!(f, "{} not found at path: {}", exe_name, path)
            }
            InstallError::DirectoryCreation { path, reason } => {
                write!(f, "Failed to create directory '{}': {}", path, reason)
            }
            InstallError::InsufficientDiskSpace { required_gb, available_gb } => {
                write!(
                    f,
                    "Insufficient disk space: {:.1}GB required, {:.1}GB available",
                    required_gb, available_gb
                )
            }
            InstallError::SteamError { reason } => {
                write!(f, "Steam integration error: {}", reason)
            }
            InstallError::Other { context, reason } => {
                write!(f, "{}: {}", context, reason)
            }
        }
    }
}

impl std::error::Error for InstallError {}

// ============================================================================
// Post-Installation Setup (Steam-native)
// ============================================================================

/// Performs all post-installation setup tasks for Steam-native integration:
/// - Creates game folders in the prefix
/// - Sets up MO2 Global Instance support (if MO2)
/// - Creates NaK Tools folder with utilities
pub fn finalize_steam_installation_with_tools(
    manager_type: ManagerType,
    prefix_path: &Path,
    install_dir: &Path,
    app_id: u32,
    proton_path: &Path,
    ctx: &TaskContext,
) -> Result<(), InstallError> {
    if ctx.is_cancelled() {
        return Err(InstallError::Cancelled);
    }

    ctx.set_status("Finalizing installation...".to_string());

    // Manager-specific setup
    if manager_type == ManagerType::MO2 {
        setup_mo2_global_instance(prefix_path, install_dir);
    }

    // Create game folders (prevents crashes for games that require them)
    super::create_game_folders(prefix_path);

    // Create NaK Tools folder with utilities (only if we have a valid app_id)
    if app_id > 0 {
        ctx.set_status("Creating NaK Tools folder...".to_string());
        if let Err(e) = create_nak_tools_folder(manager_type, install_dir, prefix_path, app_id, proton_path) {
            log_warning(&format!("Failed to create NaK Tools folder: {}", e));
            // Non-fatal - continue with installation
        }
    }

    log_install(&format!(
        "{} installation finalized (Steam-native)",
        manager_type.display_name()
    ));

    Ok(())
}

// ============================================================================
// MO2-Specific Setup
// ============================================================================

/// Sets up the symlink for MO2 Global Instance support.
/// Symlinks `.../pfx/drive_c/users/<user>/AppData/Local/ModOrganizer` -> `install_dir/Global Instance`
fn setup_mo2_global_instance(prefix_path: &Path, install_dir: &Path) {
    let users_dir = prefix_path.join("drive_c/users");
    let username = find_prefix_username(&users_dir);

    let appdata_local = users_dir.join(&username).join("AppData/Local");
    let mo2_global_path = appdata_local.join("ModOrganizer");
    let target_global_instance = install_dir.join("Global Instance");

    // 1. Ensure target "Global Instance" folder exists
    if !target_global_instance.exists() {
        if let Err(e) = fs::create_dir_all(&target_global_instance) {
            log_error(&format!("Failed to create Global Instance folder: {}", e));
            return;
        }
    }

    // 2. Ensure AppData/Local exists in prefix
    if !appdata_local.exists() {
        if let Err(e) = fs::create_dir_all(&appdata_local) {
            log_error(&format!("Failed to create AppData/Local in prefix: {}", e));
            return;
        }
    }

    // 3. Create symlink
    if mo2_global_path.exists() || fs::symlink_metadata(&mo2_global_path).is_ok() {
        let _ = fs::remove_dir_all(&mo2_global_path);
        let _ = fs::remove_file(&mo2_global_path);
    }

    if let Err(e) = std::os::unix::fs::symlink(&target_global_instance, &mo2_global_path) {
        log_error(&format!("Failed to create Global Instance symlink: {}", e));
    } else {
        log_install("Enabled Global Instance support (symlinked AppData/Local/ModOrganizer)");
    }
}

/// Find the username from a Wine prefix users directory
fn find_prefix_username(users_dir: &Path) -> String {
    if let Ok(entries) = fs::read_dir(users_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name != "Public" && name != "root" {
                return name;
            }
        }
    }
    "steamuser".to_string()
}

// ============================================================================
// Disk Space Validation
// ============================================================================

/// Minimum required disk space for a full installation (in GB)
pub const MIN_REQUIRED_DISK_SPACE_GB: f64 = 5.0;

/// Get available disk space at the given path (in GB).
pub fn get_available_disk_space(path: &Path) -> Option<f64> {
    use std::process::Command;

    let output = Command::new("df")
        .arg("-BG")
        .arg(path)
        .output()
        .ok()?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    for line in stdout.lines().skip(1) {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() >= 4 {
            let available_str = parts[3].trim_end_matches('G');
            if let Ok(available) = available_str.parse::<f64>() {
                return Some(available);
            }
        }
    }
    None
}

/// Check if there's sufficient disk space at the given path.
pub fn check_disk_space(path: &Path, required_gb: f64) -> Result<f64, InstallError> {
    match get_available_disk_space(path) {
        Some(available) => {
            if available < required_gb {
                Err(InstallError::InsufficientDiskSpace {
                    required_gb,
                    available_gb: available,
                })
            } else {
                Ok(available)
            }
        }
        None => {
            log_warning("Could not check disk space - df command failed");
            Ok(required_gb)
        }
    }
}

// ============================================================================
// Cancellation Helper
// ============================================================================

/// Check if the task has been cancelled and return an error if so.
#[inline]
pub fn check_cancelled(ctx: &TaskContext) -> Result<(), InstallError> {
    if ctx.is_cancelled() {
        Err(InstallError::Cancelled)
    } else {
        Ok(())
    }
}

// ============================================================================
// NaK Tools Creation (Steam-native)
// ============================================================================

/// Creates NaK utility scripts in the mod manager installation directory.
/// Scripts are placed directly in the root folder alongside the mod manager executable.
/// The NaK Tools subfolder contains the Wine Prefix symlink.
pub fn create_nak_tools_folder(
    manager_type: ManagerType,
    install_dir: &Path,
    prefix_path: &Path,
    app_id: u32,
    proton_path: &Path,
) -> Result<(), InstallError> {
    let manager_name = manager_type.display_name();

    // Create NaK Tools subfolder for Wine Prefix symlink and other resources
    let tools_dir = install_dir.join("NaK Tools");
    fs::create_dir_all(&tools_dir).map_err(|e| InstallError::DirectoryCreation {
        path: tools_dir.display().to_string(),
        reason: e.to_string(),
    })?;

    // 1. Create prefix symlink in NaK Tools folder
    let prefix_link = tools_dir.join("Wine Prefix");
    if prefix_link.exists() || fs::symlink_metadata(&prefix_link).is_ok() {
        let _ = fs::remove_file(&prefix_link);
    }
    if let Err(e) = std::os::unix::fs::symlink(prefix_path, &prefix_link) {
        log_warning(&format!("Failed to create prefix symlink: {}", e));
    } else {
        log_install("Created Wine Prefix symlink");
    }

    // === All scripts go in NaK Tools folder for better organization ===

    // 2. Create Launch script
    let launch_script = generate_steam_launch_script(app_id, manager_name);
    write_script(&tools_dir.join(format!("Launch {}.sh", manager_name)), &launch_script)?;
    log_install(&format!("Created Launch {} script", manager_name));

    // 3. Create NXM Toggle script
    let nxm_script = generate_nxm_toggle_script(app_id, manager_name, install_dir, prefix_path, proton_path);
    write_script(&tools_dir.join("NXM Toggle.sh"), &nxm_script)?;
    log_install("Created NXM Toggle script");

    // 4. Create Fix Game Registry script
    let registry_script = generate_fix_registry_script(manager_name, prefix_path, proton_path);
    write_script(&tools_dir.join("Fix Game Registry.sh"), &registry_script)?;
    log_install("Created Fix Game Registry script");

    // 5. Create Import Saves script
    let import_script = generate_import_saves_script(prefix_path);
    write_script(&tools_dir.join("Import Saves.sh"), &import_script)?;
    log_install("Created Import Saves script");

    // 6. Create Winetricks GUI script
    let winetricks_script = generate_winetricks_gui_script(prefix_path);
    write_script(&tools_dir.join("Winetricks.sh"), &winetricks_script)?;
    log_install("Created Winetricks GUI script");

    log_install(&format!("NaK Tools created in {:?}", install_dir));
    Ok(())
}

/// Write a script file with executable permissions
fn write_script(path: &Path, content: &str) -> Result<(), InstallError> {
    let mut file = fs::File::create(path).map_err(|e| InstallError::Other {
        context: "Script creation".to_string(),
        reason: e.to_string(),
    })?;

    file.write_all(content.as_bytes()).map_err(|e| InstallError::Other {
        context: "Script writing".to_string(),
        reason: e.to_string(),
    })?;

    let mut perms = fs::metadata(path).map_err(|e| InstallError::Other {
        context: "Script permissions".to_string(),
        reason: e.to_string(),
    })?.permissions();
    perms.set_mode(0o755);
    fs::set_permissions(path, perms).map_err(|e| InstallError::Other {
        context: "Script permissions".to_string(),
        reason: e.to_string(),
    })?;

    Ok(())
}

/// Generate Fix Game Registry script for Steam-native installs
fn generate_fix_registry_script(manager_name: &str, prefix_path: &Path, proton_path: &Path) -> String {
    let prefix_str = prefix_path.display();
    let proton_str = proton_path.display();
    format!(r#"#!/bin/bash
# NaK Fix Game Registry Script
# For Steam-native {} installation
#
# This script helps fix game installation paths in the Wine registry
# so that {} can properly detect installed games.

# Terminal auto-launch if double-clicked
if [ ! -t 0 ]; then
    for term in konsole gnome-terminal xfce4-terminal kitty alacritty xterm; do
        if command -v "$term" &> /dev/null; then
            case "$term" in
                konsole) exec "$term" --hold -e "$0" "$@" ;;
                gnome-terminal) exec "$term" -- "$0" "$@" ;;
                xfce4-terminal) exec "$term" --hold -e "$0" "$@" ;;
                kitty) exec "$term" --hold "$0" "$@" ;;
                alacritty) exec "$term" --hold -e "$0" "$@" ;;
                xterm) exec "$term" -hold -e "$0" "$@" ;;
            esac
        fi
    done
    echo "ERROR: No terminal found. Run from terminal."
    exit 1
fi

PREFIX="{}"
PROTON_PATH="{}"
WINE_BIN="$PROTON_PATH/files/bin/wine"

# Check if Proton wine exists
if [ ! -x "$WINE_BIN" ]; then
    echo "ERROR: Proton wine not found at: $WINE_BIN"
    echo "The Proton installation may have been moved or deleted."
    exit 1
fi

echo "=================================================="
echo "NaK Game Registry Fixer"
echo "Prefix: $PREFIX"
echo "=================================================="
echo ""

# Game configurations
declare -a GAMES=(
    "Enderal|Software\\SureAI\\Enderal|Install_Path"
    "Enderal Special Edition|Software\\SureAI\\Enderal SE|installed path"
    "Fallout 3|Software\\Bethesda Softworks\\Fallout3|Installed Path"
    "Fallout 4|Software\\Bethesda Softworks\\Fallout4|Installed Path"
    "Fallout 4 VR|Software\\Bethesda Softworks\\Fallout 4 VR|Installed Path"
    "Fallout New Vegas|Software\\Bethesda Softworks\\FalloutNV|Installed Path"
    "Morrowind|Software\\Bethesda Softworks\\Morrowind|Installed Path"
    "Oblivion|Software\\Bethesda Softworks\\Oblivion|Installed Path"
    "Skyrim|Software\\Bethesda Softworks\\Skyrim|Installed Path"
    "Skyrim Special Edition|Software\\Bethesda Softworks\\Skyrim Special Edition|Installed Path"
    "Skyrim VR|Software\\Bethesda Softworks\\Skyrim VR|Installed Path"
    "Starfield|Software\\Bethesda Softworks\\Starfield|Installed Path"
)

echo "Which game do you want to fix the registry for?"
echo ""
for i in "${{!GAMES[@]}}"; do
    game_name=$(echo "${{GAMES[$i]}}" | cut -d'|' -f1)
    echo "  $((i+1)). $game_name"
done
echo ""
read -p "Enter number (1-${{#GAMES[@]}}): " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${{#GAMES[@]}}" ]; then
    echo "ERROR: Invalid selection"
    exit 1
fi

selected="${{GAMES[$((choice-1))]}}"
GAME_NAME=$(echo "$selected" | cut -d'|' -f1)
REG_PATH=$(echo "$selected" | cut -d'|' -f2)
VALUE_NAME=$(echo "$selected" | cut -d'|' -f3)

echo ""
echo "Selected: $GAME_NAME"
echo ""
echo "Enter the LINUX path to the game installation:"
echo "(e.g., /home/user/.steam/steam/steamapps/common/Skyrim Special Edition)"
read -r -p "Game path: " GAME_PATH

if [ ! -d "$GAME_PATH" ]; then
    echo "WARNING: Directory does not exist. Continue anyway? (y/n)"
    read -r confirm
    if [ "$confirm" != "y" ]; then
        exit 1
    fi
fi

# Convert to Wine path
WINE_PATH_DISPLAY="Z:${{GAME_PATH//\//\\}}"
# Double backslashes for .reg file format
WINE_PATH_REG="Z:${{GAME_PATH//\//\\\\}}"

echo ""
echo "=================================================="
echo "Registry Fix Details"
echo "=================================================="
echo "Game: $GAME_NAME"
echo "Linux Path: $GAME_PATH"
echo "Wine Path: $WINE_PATH_DISPLAY"
echo "Registry Key: HKLM\\$REG_PATH"
echo "Value: $VALUE_NAME"
echo "=================================================="
echo ""
read -p "Apply this fix? (y/n): " apply

if [ "$apply" != "y" ]; then
    echo "Cancelled."
    exit 0
fi

# Create .reg file
REG_FILE=$(mktemp --suffix=.reg)
cat > "$REG_FILE" << EOF
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\$REG_PATH]
"$VALUE_NAME"="$WINE_PATH_REG"

[HKEY_LOCAL_MACHINE\\SOFTWARE\\Wow6432Node\\${{REG_PATH#Software\\}}]
"$VALUE_NAME"="$WINE_PATH_REG"
EOF

echo "Applying registry fix..."
WINEPREFIX="$PREFIX" "$WINE_BIN" regedit "$REG_FILE" 2>/dev/null

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Registry fix applied successfully!"
else
    echo ""
    echo "✗ Registry fix may have failed. Check manually."
fi

rm -f "$REG_FILE"
echo ""
echo "Done! You may need to restart {} for changes to take effect."
"#, manager_name, manager_name, prefix_str, proton_str, manager_name)
}

/// Generate NXM Toggle script
fn generate_nxm_toggle_script(app_id: u32, manager_name: &str, install_dir: &Path, prefix_path: &Path, proton_path: &Path) -> String {
    let install_str = install_dir.display();
    let prefix_str = prefix_path.display();
    let proton_str = proton_path.display();

    // Determine the NXM handler exe based on manager type
    let nxm_exe = if manager_name == "MO2" {
        format!("{}/nxmhandler.exe", install_str)
    } else {
        format!("{}/Vortex.exe", install_str)
    };

    format!(r#"#!/bin/bash
# NaK NXM Toggle Script
# For Steam-native {} installation (AppID: {})
#
# This script toggles NXM link handling for this mod manager instance.
# When enabled, clicking nxm:// links will open this instance.

# Terminal auto-launch if double-clicked
if [ ! -t 0 ]; then
    for term in konsole gnome-terminal xfce4-terminal kitty alacritty xterm; do
        if command -v "$term" &> /dev/null; then
            case "$term" in
                konsole) exec "$term" --hold -e "$0" "$@" ;;
                gnome-terminal) exec "$term" -- "$0" "$@" ;;
                xfce4-terminal) exec "$term" --hold -e "$0" "$@" ;;
                kitty) exec "$term" --hold "$0" "$@" ;;
                alacritty) exec "$term" --hold -e "$0" "$@" ;;
                xterm) exec "$term" -hold -e "$0" "$@" ;;
            esac
        fi
    done
    echo "ERROR: No terminal found. Run from terminal."
    exit 1
fi

APP_ID={}
MANAGER_NAME="{}"
NXM_EXE="{}"
PREFIX_PATH="{}"
PROTON_PATH="{}"
NAK_CONFIG_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/nak"
ACTIVE_APPID_FILE="$NAK_CONFIG_DIR/active_nxm_appid"
ACTIVE_EXE_FILE="$NAK_CONFIG_DIR/active_nxm_exe"
ACTIVE_PREFIX_FILE="$NAK_CONFIG_DIR/active_nxm_prefix"
ACTIVE_PROTON_FILE="$NAK_CONFIG_DIR/active_nxm_proton"

echo "=================================================="
echo "NaK NXM Handler Toggle"
echo "Manager: $MANAGER_NAME"
echo "Steam AppID: $APP_ID"
echo "=================================================="
echo ""

enable_nxm() {{
    mkdir -p "$NAK_CONFIG_DIR"
    echo "$APP_ID" > "$ACTIVE_APPID_FILE"
    echo "$NXM_EXE" > "$ACTIVE_EXE_FILE"
    echo "$PREFIX_PATH" > "$ACTIVE_PREFIX_FILE"
    echo "$PROTON_PATH" > "$ACTIVE_PROTON_FILE"
    echo ""
    echo "✓ NXM handling enabled for this instance"
}}

disable_nxm() {{
    rm -f "$ACTIVE_APPID_FILE" "$ACTIVE_EXE_FILE" "$ACTIVE_PREFIX_FILE" "$ACTIVE_PROTON_FILE"
    echo ""
    echo "✓ NXM handling disabled for this instance"
}}

# Check current status
if [ -f "$ACTIVE_APPID_FILE" ]; then
    CURRENT_APPID=$(cat "$ACTIVE_APPID_FILE")
    if [ "$CURRENT_APPID" == "$APP_ID" ]; then
        echo "Status: ENABLED (this instance handles NXM links)"
        echo ""
        echo "Options:"
        echo "  1. Disable NXM handling for this instance"
        echo "  2. Keep enabled"
        read -p "Choice (1-2): " choice

        if [ "$choice" == "1" ]; then
            disable_nxm
        else
            echo "Keeping NXM handling enabled."
        fi
    else
        echo "Status: DISABLED (another instance handles NXM: AppID $CURRENT_APPID)"
        echo ""
        echo "Options:"
        echo "  1. Enable NXM handling for THIS instance (disables other)"
        echo "  2. Keep current setting"
        read -p "Choice (1-2): " choice

        if [ "$choice" == "1" ]; then
            enable_nxm
        else
            echo "Keeping current setting."
        fi
    fi
else
    echo "Status: DISABLED (no instance handles NXM links)"
    echo ""
    echo "Options:"
    echo "  1. Enable NXM handling for this instance"
    echo "  2. Keep disabled"
    read -p "Choice (1-2): " choice

    if [ "$choice" == "1" ]; then
        enable_nxm
        echo ""
        echo "Make sure the NXM handler is installed. Run NaK and check Settings."
    else
        echo "Keeping NXM handling disabled."
    fi
fi

echo ""
echo "Done!"
"#, manager_name, app_id, app_id, manager_name, nxm_exe, prefix_str, proton_str)
}

/// Generate Steam launch script (for manual use outside Steam)
fn generate_steam_launch_script(app_id: u32, manager_name: &str) -> String {
    // Convert 32-bit AppID to 64-bit Game ID (required for non-Steam shortcuts)
    // Formula: (appid << 32) | 0x02000000
    let game_id: u64 = ((app_id as u64) << 32) | 0x02000000;

    format!(r#"#!/bin/bash
# NaK Steam Launch Script for {}
# Launches via Steam using the 64-bit game ID format for non-Steam shortcuts
#
# Use this to manually launch the mod manager through Steam.
# This is equivalent to clicking Play in Steam.

# 64-bit Game ID (required for non-Steam shortcuts)
GAME_ID={}

echo "Launching {} via Steam..."
xdg-open "steam://rungameid/$GAME_ID"
"#, manager_name, game_id, manager_name)
}

/// Generate Import Saves script
fn generate_import_saves_script(prefix_path: &Path) -> String {
    let prefix_str = prefix_path.display();
    format!(r#"#!/bin/bash
# NaK Import Saves Script
# Imports game saves from your Steam game prefix into this mod manager prefix.
#
# This creates symlinks so your saves are shared between the game's Steam prefix
# and this mod manager prefix.

# Terminal auto-launch if double-clicked
if [ ! -t 0 ]; then
    for term in konsole gnome-terminal xfce4-terminal kitty alacritty xterm; do
        if command -v "$term" &> /dev/null; then
            case "$term" in
                konsole) exec "$term" --hold -e "$0" "$@" ;;
                gnome-terminal) exec "$term" -- "$0" "$@" ;;
                xfce4-terminal) exec "$term" --hold -e "$0" "$@" ;;
                kitty) exec "$term" --hold "$0" "$@" ;;
                alacritty) exec "$term" --hold -e "$0" "$@" ;;
                xterm) exec "$term" -hold -e "$0" "$@" ;;
            esac
        fi
    done
    echo "ERROR: No terminal found. Run from terminal."
    exit 1
fi

PREFIX_PATH="{}"

echo "=================================================="
echo "NaK Import Saves from Steam"
echo "=================================================="
echo ""
echo "This will symlink your game saves/configs from your"
echo "Steam game prefix into this mod manager prefix."
echo ""
echo "Prefix: $PREFIX_PATH"
echo ""

# Game configurations (Display Name|My Games Folder|Steam App ID)
declare -a GAMES=(
    "Enderal|Enderal|933480"
    "Enderal Special Edition|Enderal Special Edition|976620"
    "Fallout 3|Fallout3|22300"
    "Fallout 4|Fallout4|377160"
    "Fallout 4 VR|Fallout4VR|611660"
    "Fallout New Vegas|FalloutNV|22380"
    "Morrowind|Morrowind|22320"
    "Oblivion|Oblivion|22330"
    "Skyrim|Skyrim|72850"
    "Skyrim Special Edition|Skyrim Special Edition|489830"
    "Skyrim VR|Skyrim VR|611670"
    "Starfield|Starfield|1716740"
)

# Find Steam path
find_steam_path() {{
    local paths=(
        "$HOME/.steam/steam"
        "$HOME/.local/share/Steam"
        "$HOME/.var/app/com.valvesoftware.Steam/.steam/steam"
    )
    for p in "${{paths[@]}}"; do
        if [ -d "$p" ]; then
            echo "$p"
            return 0
        fi
    done
    return 1
}}

STEAM_PATH=$(find_steam_path)
if [ -z "$STEAM_PATH" ]; then
    echo "ERROR: Could not find Steam installation"
    exit 1
fi
echo "Found Steam at: $STEAM_PATH"
echo ""

echo "Which game's saves do you want to import?"
echo ""
for i in "${{!GAMES[@]}}"; do
    display_name=$(echo "${{GAMES[$i]}}" | cut -d'|' -f1)
    echo "  $((i+1)). $display_name"
done
echo ""
read -p "Enter number (1-${{#GAMES[@]}}): " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${{#GAMES[@]}}" ]; then
    echo "ERROR: Invalid selection"
    exit 1
fi

selected="${{GAMES[$((choice-1))]}}"
DISPLAY_NAME=$(echo "$selected" | cut -d'|' -f1)
FOLDER_NAME=$(echo "$selected" | cut -d'|' -f2)
APP_ID=$(echo "$selected" | cut -d'|' -f3)

echo ""
echo "Selected: $DISPLAY_NAME (App ID: $APP_ID)"

# Find game prefix
STEAM_PREFIX=""
for lib in "$STEAM_PATH/steamapps" "$STEAM_PATH"/steamapps/libraryfolders.vdf; do
    check_path="$STEAM_PATH/steamapps/compatdata/$APP_ID/pfx"
    if [ -d "$check_path" ]; then
        STEAM_PREFIX="$check_path"
        break
    fi
done

# Also check library folders
if [ -z "$STEAM_PREFIX" ] && [ -f "$STEAM_PATH/steamapps/libraryfolders.vdf" ]; then
    while IFS= read -r line; do
        if [[ "$line" =~ \"path\".*\"(.*)\" ]]; then
            lib_path="${{BASH_REMATCH[1]}}"
            check_path="$lib_path/steamapps/compatdata/$APP_ID/pfx"
            if [ -d "$check_path" ]; then
                STEAM_PREFIX="$check_path"
                break
            fi
        fi
    done < "$STEAM_PATH/steamapps/libraryfolders.vdf"
fi

if [ -z "$STEAM_PREFIX" ]; then
    echo "ERROR: Could not find Steam prefix for $DISPLAY_NAME"
    echo "Make sure you've run the game at least once via Steam."
    exit 1
fi

echo "Found game prefix: $STEAM_PREFIX"

# Get usernames
get_username() {{
    local prefix="$1"
    for entry in "$prefix/drive_c/users"/*; do
        name=$(basename "$entry")
        if [ "$name" != "Public" ] && [ "$name" != "root" ]; then
            echo "$name"
            return
        fi
    done
    echo "steamuser"
}}

STEAM_USER=$(get_username "$STEAM_PREFIX")
TARGET_USER=$(get_username "$PREFIX_PATH")

SOURCE_DIR="$STEAM_PREFIX/drive_c/users/$STEAM_USER/Documents/My Games/$FOLDER_NAME"
TARGET_DIR="$PREFIX_PATH/drive_c/users/$TARGET_USER/Documents/My Games/$FOLDER_NAME"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: No saves found at: $SOURCE_DIR"
    exit 1
fi

echo ""
echo "Source: $SOURCE_DIR"
echo "Target: $TARGET_DIR"
echo ""
read -p "Create symlink? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo "Cancelled."
    exit 0
fi

# Remove existing target if it's a directory or symlink
if [ -L "$TARGET_DIR" ]; then
    rm "$TARGET_DIR"
elif [ -d "$TARGET_DIR" ]; then
    echo "Target exists. Remove it? (y/n)"
    read -r remove
    if [ "$remove" == "y" ]; then
        rm -rf "$TARGET_DIR"
    else
        echo "Cancelled."
        exit 0
    fi
fi

mkdir -p "$(dirname "$TARGET_DIR")"
ln -s "$SOURCE_DIR" "$TARGET_DIR"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Successfully linked $DISPLAY_NAME saves!"
else
    echo "✗ Failed to create symlink"
    exit 1
fi

echo ""
echo "Done!"
"#, prefix_str)
}

/// Generate Winetricks GUI script for Steam-native installs
fn generate_winetricks_gui_script(prefix_path: &Path) -> String {
    let prefix_str = prefix_path.display();
    format!(r#"#!/bin/bash
# NaK Winetricks GUI Script
#
# Opens the Winetricks GUI for this mod manager's Wine prefix.
# Use this to install additional Windows components or DLLs.

PREFIX="{}"
NAK_CONFIG_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/nak"
NAK_WINETRICKS="$NAK_CONFIG_DIR/bin/winetricks"

# Find winetricks - prefer NaK's bundled version (auto-updated)
if [ -x "$NAK_WINETRICKS" ]; then
    WINETRICKS_BIN="$NAK_WINETRICKS"
    echo "Using NaK bundled winetricks"
elif command -v winetricks &> /dev/null; then
    WINETRICKS_BIN="winetricks"
    echo "Using system winetricks"
else
    echo "ERROR: winetricks is not available."
    echo ""
    echo "NaK should have downloaded winetricks automatically."
    echo "If this persists, try restarting NaK or install manually:"
    echo "  - Arch/CachyOS: sudo pacman -S winetricks"
    echo "  - Ubuntu/Debian: sudo apt install winetricks"
    echo "  - Fedora: sudo dnf install winetricks"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

if [ ! -d "$PREFIX" ]; then
    echo "ERROR: Wine prefix not found at: $PREFIX"
    echo "The prefix may not have been created yet."
    echo "Try launching the mod manager through Steam first."
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Opening Winetricks GUI for prefix:"
echo "$PREFIX"
echo ""

WINEPREFIX="$PREFIX" "$WINETRICKS_BIN" --gui
"#, prefix_str)
}

