//! Launch script generation for mod managers
//!
//! This module provides unified script generation for launching mod managers
//! and handling NXM links. Scripts are generated with optional SLR (Steam Linux Runtime)
//! container support.

use std::error::Error;
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use crate::config::AppConfig;
use crate::utils::detect_steam_path;
use crate::wine::runtime;

// ============================================================================
// Path Setup Constants (for portable scripts)
// ============================================================================

/// Path setup block for scripts using Steam Linux Runtime
const PATH_SETUP_SLR: &str = r#"# Derive paths from script location (portable after NaK moves)
SCRIPT_DIR="$(cd "$(dirname "$(realpath "$0")")" && pwd)"
PREFIX="$SCRIPT_DIR/pfx"
COMPAT_DATA="$SCRIPT_DIR"
PROTON_GE="$SCRIPT_DIR/../../ProtonGE/active"
ENTRY_POINT="$SCRIPT_DIR/../../Runtime/SteamLinuxRuntime_sniper/_v2-entry-point"
"#;

/// Path setup block for scripts running directly (no SLR)
const PATH_SETUP_DIRECT: &str = r#"# Derive paths from script location (portable after NaK moves)
SCRIPT_DIR="$(cd "$(dirname "$(realpath "$0")")" && pwd)"
PREFIX="$SCRIPT_DIR/pfx"
COMPAT_DATA="$SCRIPT_DIR"
PROTON_GE="$SCRIPT_DIR/../../ProtonGE/active"
"#;

// ============================================================================
// Script Generator
// ============================================================================

pub struct ScriptGenerator;

impl ScriptGenerator {
    /// Check if we should use Steam Linux Runtime based on config
    fn should_use_slr() -> bool {
        AppConfig::load().use_steam_runtime
    }

    /// Detect if an existing script uses SLR by reading its content
    pub fn script_uses_slr(script_path: &Path) -> Option<bool> {
        let content = fs::read_to_string(script_path).ok()?;
        // Check for SLR-specific markers
        if content.contains("ENTRY_POINT=") && content.contains("--verb=waitforexitandrun") {
            Some(true)
        } else if content.contains("# Running WITHOUT Steam Linux Runtime") {
            Some(false)
        } else if content.contains("PROTON_GE=") {
            // Has proton but no entry point = direct mode
            Some(false)
        } else {
            None
        }
    }

    /// Get common environment variables block for scripts
    fn get_env_block(use_slr: bool) -> String {
        if use_slr {
            r#"# Set environment variables for the Container
export WINEPREFIX="$PREFIX"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_PATH"
export PROTON_DIST_PATH="$PROTON_GE"

# Set GAMEID for protonfixes
export GAMEID="non-steam-game"

# DotNet Fixes
export DOTNET_ROOT=""
export DOTNET_MULTILEVEL_LOOKUP=0
export MO2_VFS_LOG_LEVEL=0

# DXVK Config - Disable Graphics Pipeline Library for compatibility
export DXVK_CONFIG="dxvk.enableGraphicsPipelineLibrary = False""#.to_string()
        } else {
            r#"# Set environment variables
export WINEPREFIX="$PREFIX"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_PATH"

# Set GAMEID for protonfixes
export GAMEID="non-steam-game"

# DotNet Fixes
export DOTNET_ROOT=""
export DOTNET_MULTILEVEL_LOOKUP=0
export MO2_VFS_LOG_LEVEL=0

# DXVK Config - Disable Graphics Pipeline Library for compatibility
export DXVK_CONFIG="dxvk.enableGraphicsPipelineLibrary = False""#.to_string()
        }
    }

    /// Get the entry point check block for SLR mode
    fn get_slr_check_block() -> &'static str {
        r#"
# Check environment
if [ ! -f "$ENTRY_POINT" ]; then
    echo "ERROR: Steam Runtime entry point not found at $ENTRY_POINT"
    exit 1
fi
"#
    }

    /// Get the auto game registry fix block for MO2 portable mode
    /// NOTE: Disabled - auto registry fix was removed as it caused issues for users
    /// with malformed registries or different setups. Users can still run the
    /// standalone game_registry_fix.sh script manually if needed.
    fn get_mo2_registry_fix_block(_use_slr: bool) -> String {
        String::new()
    }

    /// Generate a launch command based on SLR setting
    fn get_launch_command(use_slr: bool, exe_var: &str, extra_args: &str) -> String {
        if use_slr {
            format!(
                r#""$ENTRY_POINT" --verb=waitforexitandrun -- "$PROTON_GE/proton" run "${}" {}"#,
                exe_var, extra_args
            )
        } else {
            format!(r#""$PROTON_GE/proton" run "${}" {}"#, exe_var, extra_args)
        }
    }

    /// Generate a manager launch script (MO2 or Vortex)
    /// If `use_slr_override` is Some, use that value instead of the global config
    /// Scripts use relative paths from their location so they work after NaK is moved
    fn generate_launch_script_with_override(
        _prefix_path: &Path,
        exe: &Path,
        _proton_path: &Path, // No longer used - we use the active symlink
        output_dir: &Path,
        manager_name: &str,
        use_slr_override: Option<bool>,
    ) -> Result<PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let use_slr = use_slr_override.unwrap_or_else(Self::should_use_slr);
        let runtime_entry = runtime::get_entry_point();

        let exe_var_name = if manager_name == "MO2" { "MO2_EXE" } else { "VORTEX_EXE" };
        let comment_name = if manager_name == "MO2" { "MO2" } else { "Vortex" };

        // Only include auto registry fix for MO2 (portable mode)
        let registry_fix_block = if manager_name == "MO2" {
            Self::get_mo2_registry_fix_block(use_slr)
        } else {
            String::new()
        };

        let script_content = if use_slr {
            // Just verify SLR exists during generation (the script uses relative path)
            let _entry_point = runtime_entry.ok_or(
                "Steam Linux Runtime (Sniper) not found! Please download it in Proton Picker or disable it in Settings."
            )?;

            format!(
                r#"#!/bin/bash
# NaK Generated Launch Script for {comment_name}
# Running inside Steam Linux Runtime (Sniper) Container
# Uses active Proton symlink - change Proton in NaK's Proton Picker

{path_setup}
{exe_var_name}='{exe}'
STEAM_PATH='{steam_path}'
{slr_check}
{env_block}
{registry_fix}
echo "Launching {comment_name} (Containerized)..."
{launch_cmd}
"#,
                comment_name = comment_name,
                path_setup = PATH_SETUP_SLR,
                exe_var_name = exe_var_name,
                exe = exe.to_string_lossy(),
                steam_path = steam_path,
                slr_check = Self::get_slr_check_block(),
                env_block = Self::get_env_block(true),
                registry_fix = registry_fix_block,
                launch_cmd = Self::get_launch_command(true, exe_var_name, r#""$@""#)
            )
        } else {
            format!(
                r#"#!/bin/bash
# NaK Generated Launch Script for {comment_name}
# Running WITHOUT Steam Linux Runtime (Direct Proton)
# Uses active Proton symlink - change Proton in NaK's Proton Picker

{path_setup}
{exe_var_name}='{exe}'
STEAM_PATH='{steam_path}'

{env_block}
{registry_fix}
echo "Launching {comment_name} (Direct Proton)..."
{launch_cmd}
"#,
                comment_name = comment_name,
                path_setup = PATH_SETUP_DIRECT,
                exe_var_name = exe_var_name,
                exe = exe.to_string_lossy(),
                steam_path = steam_path,
                env_block = Self::get_env_block(false),
                registry_fix = registry_fix_block,
                launch_cmd = Self::get_launch_command(false, exe_var_name, r#""$@""#)
            )
        };

        Self::write_script(output_dir, "start.sh", &script_content)
    }

    /// Write a script file with proper permissions
    fn write_script(output_dir: &Path, filename: &str, content: &str) -> Result<PathBuf, Box<dyn Error>> {
        let script_path = output_dir.join(filename);
        let mut file = fs::File::create(&script_path)?;
        file.write_all(content.as_bytes())?;

        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        Ok(script_path)
    }

    // ========================================================================
    // Public API - Maintains backward compatibility
    // ========================================================================

    /// Generate NXM handler launch script for MO2
    /// Uses relative paths so it works after NaK is moved
    pub fn generate_mo2_nxm_script(
        _prefix_path: &Path,
        nxm_handler_exe: &Path,
        _proton_ge_path: &Path, // No longer used - we use the active symlink
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let use_slr = Self::should_use_slr();
        let runtime_entry = runtime::get_entry_point();

        let script_content = if use_slr {
            let _entry_point = runtime_entry.ok_or(
                "Steam Linux Runtime (Sniper) not found! Please download it in Proton Picker or disable it in Settings."
            )?;

            format!(
                r#"#!/bin/bash
# NaK Generated NXM Handler Script for MO2
# Running inside Steam Linux Runtime (Sniper) Container
# Uses active Proton symlink - change Proton in NaK's Proton Picker

{path_setup}
NXM_HANDLER='{exe}'
STEAM_PATH='{steam_path}'
{slr_check}
{env_block}

echo "Handling NXM link via MO2 nxmhandler..."
{launch_cmd}
"#,
                path_setup = PATH_SETUP_SLR,
                exe = nxm_handler_exe.to_string_lossy(),
                steam_path = steam_path,
                slr_check = Self::get_slr_check_block(),
                env_block = Self::get_env_block(true),
                launch_cmd = Self::get_launch_command(true, "NXM_HANDLER", r#""$@""#)
            )
        } else {
            format!(
                r#"#!/bin/bash
# NaK Generated NXM Handler Script for MO2
# Running WITHOUT Steam Linux Runtime (Direct Proton)
# Uses active Proton symlink - change Proton in NaK's Proton Picker

{path_setup}
NXM_HANDLER='{exe}'
STEAM_PATH='{steam_path}'

{env_block}

echo "Handling NXM link via MO2 nxmhandler (Direct Proton)..."
{launch_cmd}
"#,
                path_setup = PATH_SETUP_DIRECT,
                exe = nxm_handler_exe.to_string_lossy(),
                steam_path = steam_path,
                env_block = Self::get_env_block(false),
                launch_cmd = Self::get_launch_command(false, "NXM_HANDLER", r#""$@""#)
            )
        };

        Self::write_script(script_output_dir, "nxm_handler.sh", &script_content)
    }

    /// Generate NXM handler launch script for Vortex
    /// Vortex.exe itself handles NXM links when passed as an argument
    /// Uses relative paths so it works after NaK is moved
    pub fn generate_vortex_nxm_script(
        _prefix_path: &Path,
        vortex_exe: &Path,
        _proton_ge_path: &Path, // No longer used - we use the active symlink
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let use_slr = Self::should_use_slr();
        let runtime_entry = runtime::get_entry_point();

        let script_content = if use_slr {
            let _entry_point = runtime_entry.ok_or(
                "Steam Linux Runtime (Sniper) not found! Please download it in Proton Picker or disable it in Settings."
            )?;

            format!(
                r#"#!/bin/bash
# NaK Generated NXM Handler Script for Vortex
# Running inside Steam Linux Runtime (Sniper) Container
# Uses active Proton symlink - change Proton in NaK's Proton Picker

{path_setup}
VORTEX_EXE='{exe}'
STEAM_PATH='{steam_path}'
{slr_check}
{env_block}

echo "Handling NXM link via Vortex..."
{launch_cmd}
"#,
                path_setup = PATH_SETUP_SLR,
                exe = vortex_exe.to_string_lossy(),
                steam_path = steam_path,
                slr_check = Self::get_slr_check_block(),
                env_block = Self::get_env_block(true),
                launch_cmd = Self::get_launch_command(true, "VORTEX_EXE", r#"-d "$@""#)
            )
        } else {
            format!(
                r#"#!/bin/bash
# NaK Generated NXM Handler Script for Vortex
# Running WITHOUT Steam Linux Runtime (Direct Proton)
# Uses active Proton symlink - change Proton in NaK's Proton Picker

{path_setup}
VORTEX_EXE='{exe}'
STEAM_PATH='{steam_path}'

{env_block}

echo "Handling NXM link via Vortex (Direct Proton)..."
{launch_cmd}
"#,
                path_setup = PATH_SETUP_DIRECT,
                exe = vortex_exe.to_string_lossy(),
                steam_path = steam_path,
                env_block = Self::get_env_block(false),
                launch_cmd = Self::get_launch_command(false, "VORTEX_EXE", r#"-d "$@""#)
            )
        };

        Self::write_script(script_output_dir, "nxm_handler.sh", &script_content)
    }

    /// Generate launch script for MO2
    pub fn generate_mo2_launch_script(
        prefix_path: &Path,
        mo2_exe: &Path,
        proton_ge_path: &Path,
        _install_dir: &Path,
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        Self::generate_launch_script_with_override(prefix_path, mo2_exe, proton_ge_path, script_output_dir, "MO2", None)
    }

    /// Generate launch script for MO2 with explicit SLR setting
    pub fn generate_mo2_launch_script_with_slr(
        prefix_path: &Path,
        mo2_exe: &Path,
        proton_ge_path: &Path,
        _install_dir: &Path,
        script_output_dir: &Path,
        use_slr: bool,
    ) -> Result<PathBuf, Box<dyn Error>> {
        Self::generate_launch_script_with_override(prefix_path, mo2_exe, proton_ge_path, script_output_dir, "MO2", Some(use_slr))
    }

    /// Generate launch script for Vortex
    pub fn generate_vortex_launch_script(
        prefix_path: &Path,
        vortex_exe: &Path,
        proton_ge_path: &Path,
        _install_dir: &Path,
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        Self::generate_launch_script_with_override(prefix_path, vortex_exe, proton_ge_path, script_output_dir, "Vortex", None)
    }

    /// Generate launch script for Vortex with explicit SLR setting
    pub fn generate_vortex_launch_script_with_slr(
        prefix_path: &Path,
        vortex_exe: &Path,
        proton_ge_path: &Path,
        _install_dir: &Path,
        script_output_dir: &Path,
        use_slr: bool,
    ) -> Result<PathBuf, Box<dyn Error>> {
        Self::generate_launch_script_with_override(prefix_path, vortex_exe, proton_ge_path, script_output_dir, "Vortex", Some(use_slr))
    }

    /// Generate kill prefix script
    /// Uses relative paths so it works after NaK is moved
    pub fn generate_kill_prefix_script(
        _prefix_path: &Path,
        _proton_ge_path: &Path, // No longer used - we use the active symlink
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        let script_content = r#"#!/bin/bash
# NaK Kill Prefix Script
# Uses active Proton symlink - change Proton in NaK's Proton Picker

# Derive paths from script location (portable after NaK moves)
SCRIPT_DIR="$(cd "$(dirname "$(realpath "$0")")" && pwd)"
PREFIX="$SCRIPT_DIR/pfx"
PROTON_GE="$SCRIPT_DIR/../../ProtonGE/active"
WINESERVER="$PROTON_GE/files/bin/wineserver"

echo "Killing Wine processes for prefix: $PREFIX"

export WINEPREFIX="$PREFIX"

if [ -f "$WINESERVER" ]; then
    "$WINESERVER" -k
else
    wineserver -k
fi

echo "Done."
"#;

        Self::write_script(script_output_dir, ".kill_prefix.sh", script_content)
    }

    /// Get terminal auto-launch block for interactive scripts
    fn get_terminal_relaunch_block() -> &'static str {
        r#"
# Auto-launch in terminal if double-clicked from file manager
if [ ! -t 0 ]; then
    # Not running in a terminal, try to open one
    for term in konsole gnome-terminal xfce4-terminal kitty alacritty xterm; do
        if command -v "$term" &> /dev/null; then
            case "$term" in
                konsole)
                    exec "$term" --hold -e "$0" "$@"
                    ;;
                gnome-terminal)
                    exec "$term" -- "$0" "$@"
                    ;;
                xfce4-terminal)
                    exec "$term" --hold -e "$0" "$@"
                    ;;
                kitty)
                    exec "$term" --hold "$0" "$@"
                    ;;
                alacritty)
                    exec "$term" --hold -e "$0" "$@"
                    ;;
                xterm)
                    exec "$term" -hold -e "$0" "$@"
                    ;;
            esac
        fi
    done
    echo "ERROR: No terminal emulator found. Please run this script from a terminal."
    exit 1
fi
"#
    }

    /// Generate game registry fix script
    /// Uses relative paths so it works after NaK is moved
    pub fn generate_fix_game_registry_script(
        _prefix_path: &Path,
        _proton_ge_path: &Path, // No longer used - we use the active symlink
        instance_name: &str,
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let use_slr = Self::should_use_slr();
        let runtime_entry = runtime::get_entry_point();
        let terminal_block = Self::get_terminal_relaunch_block();

        let header = if use_slr {
            let _entry_point = runtime_entry.ok_or(
                "Steam Linux Runtime (Sniper) not found! Please download it in Proton Picker or disable it in Settings."
            )?;

            format!(
                r#"#!/bin/bash
# NaK Game Registry Fixer
# Instance: {instance_name}
# Mode: Steam Linux Runtime (Containerized)
# Uses active Proton symlink - change Proton in NaK's Proton Picker
{terminal_block}
{path_setup}
STEAM_PATH='{steam_path}'
USE_SLR=1

echo "=================================================="
echo "NaK Game Registry Fixer"
echo "Instance: {instance_name}"
echo "=================================================="
echo ""
{slr_check}
{env_block}

# Function to run proton command
run_proton() {{
    "$ENTRY_POINT" --verb=waitforexitandrun -- "$PROTON_GE/proton" run "$@"
}}
"#,
                instance_name = instance_name,
                terminal_block = terminal_block,
                path_setup = PATH_SETUP_SLR,
                steam_path = steam_path,
                slr_check = Self::get_slr_check_block(),
                env_block = Self::get_env_block(true)
            )
        } else {
            format!(
                r#"#!/bin/bash
# NaK Game Registry Fixer
# Instance: {instance_name}
# Mode: Direct Proton (No Steam Linux Runtime)
# Uses active Proton symlink - change Proton in NaK's Proton Picker
{terminal_block}
{path_setup}
STEAM_PATH='{steam_path}'
USE_SLR=0

echo "=================================================="
echo "NaK Game Registry Fixer"
echo "Instance: {instance_name}"
echo "=================================================="
echo ""

{env_block}

# Function to run proton command
run_proton() {{
    "$PROTON_GE/proton" run "$@"
}}
"#,
                instance_name = instance_name,
                terminal_block = terminal_block,
                path_setup = PATH_SETUP_DIRECT,
                steam_path = steam_path,
                env_block = Self::get_env_block(false)
            )
        };

        let full_script = format!("{}{}", header, REGISTRY_FIX_BODY);
        Self::write_script(script_output_dir, "game_registry_fix.sh", &full_script)
    }
}

// ============================================================================
// Registry Fix Script Body (shared)
// ============================================================================

const REGISTRY_FIX_BODY: &str = r#"
# Game registry configurations
# Format: "Game Name|Registry Path|Value Name"
declare -a GAMES=(
    "Enderal|Software\SureAI\Enderal|Install_Path"
    "Enderal Special Edition|Software\SureAI\Enderal SE|installed path"
    "Fallout 3|Software\Bethesda Softworks\Fallout3|Installed Path"
    "Fallout 4|Software\Bethesda Softworks\Fallout4|Installed Path"
    "Fallout 4 VR|Software\Bethesda Softworks\Fallout 4 VR|Installed Path"
    "Fallout New Vegas|Software\Bethesda Softworks\FalloutNV|Installed Path"
    "Morrowind|Software\Bethesda Softworks\Morrowind|Installed Path"
    "Oblivion|Software\Bethesda Softworks\Oblivion|Installed Path"
    "Skyrim|Software\Bethesda Softworks\Skyrim|Installed Path"
    "Skyrim Special Edition|Software\Bethesda Softworks\Skyrim Special Edition|Installed Path"
    "Skyrim VR|Software\Bethesda Softworks\Skyrim VR|Installed Path"
    "Starfield|Software\Bethesda Softworks\Starfield|Installed Path"
)

echo "Which Bethesda game are you modding?"
echo ""
for i in "${!GAMES[@]}"; do
    game_name=$(echo "${GAMES[$i]}" | cut -d'|' -f1)
    echo "  $((i+1)). $game_name"
done
echo ""
read -p "Enter number (1-${#GAMES[@]}): " choice

# Validate input
if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#GAMES[@]}" ]; then
    echo "ERROR: Invalid selection"
    exit 1
fi

# Get selected game info
selected_game="${GAMES[$((choice-1))]}"
GAME_NAME=$(echo "$selected_game" | cut -d'|' -f1)
REG_PATH=$(echo "$selected_game" | cut -d'|' -f2)
VALUE_NAME=$(echo "$selected_game" | cut -d'|' -f3)

echo ""
echo "Selected: $GAME_NAME"
echo ""

# Ask for game installation path (with retry loop)
while true; do
    echo "Where is $GAME_NAME installed?"
    echo "Enter the LINUX path (e.g., /home/user/.steam/steam/steamapps/common/Skyrim Special Edition)"
    echo ""
    read -r -p "Game path: " GAME_PATH_LINUX

    # Validate path exists
    if [ -d "$GAME_PATH_LINUX" ]; then
        break
    else
        echo ""
        echo "WARNING: Directory does not exist: $GAME_PATH_LINUX"
        read -r -p "Try again? (y/n): " retry_choice
        if [ "$retry_choice" != "y" ] && [ "$retry_choice" != "Y" ]; then
            echo "Cancelled."
            exit 1
        fi
        echo ""
    fi
done

# Convert Linux path to Wine path (Z:\...)
# Replace / with \
WINE_PATH="Z:${GAME_PATH_LINUX//\//\\}"

echo ""
echo "=================================================="
echo "Registry Fix Details"
echo "=================================================="
echo "Game: $GAME_NAME"
echo "Linux Path: $GAME_PATH_LINUX"
echo "Wine Path: $WINE_PATH"
echo "Registry Key: HKLM\\${REG_PATH}"
echo "Value Name: $VALUE_NAME"
echo "=================================================="
echo ""
read -p "Apply this registry fix? (y/n): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "Applying registry fix..."
echo ""

# Function to set registry value
set_registry() {
    local reg_key="$1"
    local reg_flag="$2"

    echo "Setting: $reg_key ($reg_flag)"
    run_proton reg add "HKLM\\$reg_key" /v "$VALUE_NAME" /d "$WINE_PATH" /f $reg_flag

    if [ $? -eq 0 ]; then
        echo "  ✓ Success"
        return 0
    else
        echo "  ✗ Failed"
        return 1
    fi
}

# Apply registry fix to both 32-bit and 64-bit views
success_count=0

# 32-bit registry view
set_registry "$REG_PATH" "/reg:32"
[ $? -eq 0 ] && ((success_count++))

# 64-bit registry view (Wow6432Node)
# Use ! as sed delimiter to handle backslashes safely
WOW64_PATH=$(echo "$REG_PATH" | sed 's!^Software\\!SOFTWARE\\Wow6432Node\\!')
set_registry "$WOW64_PATH" "/reg:64"
[ $? -eq 0 ] && ((success_count++))

echo ""
echo "=================================================="
if [ $success_count -eq 2 ]; then
    echo "✓ Registry fix applied successfully!"
    echo ""
    echo "The game installation path has been set in the registry."
elif [ $success_count -gt 0 ]; then
    echo "⚠ Registry fix partially applied ($success_count/2 succeeded)"
else
    echo "✗ Registry fix failed"
fi
echo "=================================================="

# Offer to verify the registry
echo ""
read -p "Would you like to verify the registry values? (y/n): " verify_choice

if [ "$verify_choice" == "y" ] || [ "$verify_choice" == "Y" ]; then
    echo ""
    echo "Verifying registry..."
    echo ""

    # 32-bit check
    run_proton reg query "HKLM\\${REG_PATH}" /v "$VALUE_NAME" /reg:32 > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "  ✓ 32-bit Key: FOUND"
    else
        echo "  ✗ 32-bit Key: NOT FOUND"
    fi

    # 64-bit check
    run_proton reg query "HKLM\\${WOW64_PATH}" /v "$VALUE_NAME" /reg:64 > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "  ✓ 64-bit Key: FOUND"
    else
        echo "  ✗ 64-bit Key: NOT FOUND"
    fi
fi

echo ""
echo "Done!"
"#;

// ============================================================================
// Fix Symlinks After Move
// ============================================================================

/// Fix all symlinks after NaK data folder is moved to a new location
/// This updates:
/// - manager_link in each prefix (points to mod manager install dir)
/// - Convenience symlinks in mod manager folders (Launch MO2, Kill Prefix, etc.)
/// - active_nxm_game global symlink
pub fn fix_symlinks_after_move() -> Result<usize, Box<dyn Error>> {
    use crate::logging::{log_error, log_info, log_warning};

    let config = AppConfig::load();
    let prefixes_dir = config.get_prefixes_path();
    let data_path = config.get_data_path();

    if !prefixes_dir.exists() {
        return Ok(0);
    }

    let mut fixed_count = 0;

    for entry in fs::read_dir(&prefixes_dir)? {
        let entry = entry?;
        let prefix_dir = entry.path();

        if !prefix_dir.is_dir() {
            continue;
        }

        let prefix_name = prefix_dir
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("unknown");

        let pfx_path = prefix_dir.join("pfx");
        if !pfx_path.exists() {
            log_warning(&format!("Skipping {}: no pfx directory found", prefix_name));
            continue;
        }

        // Try to find install directory - first try manager_link (for external installs), then search
        let manager_link = prefix_dir.join("manager_link");
        let install_dir = if manager_link.exists() || fs::symlink_metadata(&manager_link).is_ok() {
            // Try to read the link - if target exists (even external), use it
            match fs::read_link(&manager_link) {
                Ok(path) if path.exists() => Some(path),
                _ => {
                    // Link is broken, search for install dir inside prefix
                    find_mod_manager_install_dir(&pfx_path)
                }
            }
        } else {
            // No manager_link, search for install dir inside prefix
            find_mod_manager_install_dir(&pfx_path)
        };

        if let Some(install_dir) = install_dir {
            let is_mo2 = install_dir.join("ModOrganizer.exe").exists();
            let is_vortex = install_dir.join("Vortex.exe").exists();
            if manager_link.exists() || fs::symlink_metadata(&manager_link).is_ok() {
                let _ = fs::remove_file(&manager_link);
            }
            if let Err(e) = std::os::unix::fs::symlink(&install_dir, &manager_link) {
                log_error(&format!(
                    "Failed to update manager_link for {}: {}",
                    prefix_name, e
                ));
                continue;
            }

            // Update convenience symlinks in the mod manager folder
            let script_path = prefix_dir.join("start.sh");
            let kill_script = prefix_dir.join(".kill_prefix.sh");
            let reg_script = prefix_dir.join("game_registry_fix.sh");
            let nxm_script = prefix_dir.join("nxm_handler.sh");

            // Helper to create symlink with error logging
            let create_link = |target: &Path, link_name: &str| {
                let link_path = install_dir.join(link_name);
                // Remove existing (broken or not)
                if fs::symlink_metadata(&link_path).is_ok() {
                    if let Err(e) = fs::remove_file(&link_path) {
                        log_warning(&format!(
                            "Failed to remove old symlink {}: {}", link_path.display(), e
                        ));
                        return;
                    }
                }
                // Create new symlink
                if let Err(e) = std::os::unix::fs::symlink(target, &link_path) {
                    log_warning(&format!(
                        "Failed to create symlink {} -> {}: {}",
                        link_path.display(), target.display(), e
                    ));
                }
            };

            if is_mo2 {
                create_link(&script_path, "Launch MO2");
                create_link(&kill_script, "Kill MO2 Prefix");
                create_link(&reg_script, "Fix Game Registry");
                if nxm_script.exists() {
                    create_link(&nxm_script, "Handle NXM");
                }
            } else if is_vortex {
                create_link(&script_path, "Launch Vortex");
                create_link(&kill_script, "Kill Vortex Prefix");
                create_link(&reg_script, "Fix Game Registry");
                if nxm_script.exists() {
                    create_link(&nxm_script, "Handle NXM");
                }
            }

            log_info(&format!("Fixed symlinks for: {}", prefix_name));
            fixed_count += 1;
        } else {
            log_warning(&format!(
                "Skipping {}: couldn't find mod manager install directory",
                prefix_name
            ));
        }
    }

    // Fix active_nxm_game symlink if it exists and is broken
    let active_nxm = data_path.join("active_nxm_game");
    if fs::symlink_metadata(&active_nxm).is_ok() {
        // Read the old target
        if let Ok(old_target) = fs::read_link(&active_nxm) {
            // Extract just the prefix name from the old path
            if let Some(prefix_name) = old_target.file_name() {
                let new_target = prefixes_dir.join(prefix_name);
                if new_target.exists() {
                    let _ = fs::remove_file(&active_nxm);
                    if let Err(e) = std::os::unix::fs::symlink(&new_target, &active_nxm) {
                        log_error(&format!("Failed to update active_nxm_game: {}", e));
                    } else {
                        log_info("Updated active_nxm_game symlink");
                    }
                }
            }
        }
    }

    log_info(&format!(
        "Symlink fix complete: {} prefix(es) updated",
        fixed_count
    ));
    Ok(fixed_count)
}

/// Find the mod manager installation directory inside a prefix
fn find_mod_manager_install_dir(pfx_path: &Path) -> Option<PathBuf> {
    // Common locations to search
    let search_dirs = [
        "drive_c/modding tools",
        "drive_c/Modding Tools",
        "drive_c/MO2",
        "drive_c/Mod Organizer 2",
        "drive_c/Vortex",
        "drive_c/Program Files",
        "drive_c/Program Files (x86)",
        "drive_c/users",
    ];

    for search_dir in &search_dirs {
        let dir_path = pfx_path.join(search_dir);
        if dir_path.exists() {
            // Search for ModOrganizer.exe or Vortex.exe
            if let Some(found) = search_for_exe(&dir_path, "ModOrganizer.exe", 3) {
                return Some(found);
            }
            if let Some(found) = search_for_exe(&dir_path, "Vortex.exe", 3) {
                return Some(found);
            }
        }
    }

    None
}

/// Recursively search for an executable up to max_depth levels
fn search_for_exe(dir: &Path, exe_name: &str, max_depth: usize) -> Option<PathBuf> {
    if max_depth == 0 {
        return None;
    }

    // Check current directory
    let exe_path = dir.join(exe_name);
    if exe_path.exists() {
        return Some(dir.to_path_buf());
    }

    // Search subdirectories
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                if let Some(found) = search_for_exe(&path, exe_name, max_depth - 1) {
                    return Some(found);
                }
            }
        }
    }

    None
}

// ============================================================================
// Regenerate All Scripts
// ============================================================================

/// Regenerate all launch scripts for existing prefixes
/// This is called when the user toggles the Steam Linux Runtime setting
/// Also fixes broken symlinks and recreates convenience symlinks
pub fn regenerate_all_prefix_scripts() -> Result<usize, Box<dyn Error>> {
    use crate::logging::{log_error, log_info, log_warning};
    use crate::wine::ProtonFinder;

    let config = AppConfig::load();
    let prefixes_dir = config.get_prefixes_path();

    if !prefixes_dir.exists() {
        return Ok(0);
    }

    let mut regenerated_count = 0;
    let proton_finder = ProtonFinder::new();
    let available_protons = proton_finder.find_all();

    for entry in fs::read_dir(&prefixes_dir)? {
        let entry = entry?;
        let prefix_dir = entry.path();

        if !prefix_dir.is_dir() {
            continue;
        }

        let prefix_name = prefix_dir
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("unknown");

        let pfx_path = prefix_dir.join("pfx");
        if !pfx_path.exists() {
            log_warning(&format!("Skipping {}: no pfx directory found", prefix_name));
            continue;
        }

        // Try to find install directory - first try manager_link, then search
        let manager_link = prefix_dir.join("manager_link");
        let install_dir = if manager_link.exists() || fs::symlink_metadata(&manager_link).is_ok() {
            // Try to read the link
            match fs::read_link(&manager_link) {
                Ok(path) if path.exists() => Some(path),
                _ => {
                    // Link is broken, search for install dir
                    find_mod_manager_install_dir(&pfx_path)
                }
            }
        } else {
            // No manager_link, search for install dir
            find_mod_manager_install_dir(&pfx_path)
        };

        let install_dir = match install_dir {
            Some(dir) => dir,
            None => {
                log_warning(&format!(
                    "Skipping {}: couldn't find mod manager install directory",
                    prefix_name
                ));
                continue;
            }
        };

        // Determine mod manager type
        let is_mo2 = install_dir.join("ModOrganizer.exe").exists();
        let is_vortex = install_dir.join("Vortex.exe").exists();

        if !is_mo2 && !is_vortex {
            log_warning(&format!(
                "Skipping {}: can't determine mod manager type",
                prefix_name
            ));
            continue;
        }

        // Update manager_link to point to the correct location
        if manager_link.exists() || fs::symlink_metadata(&manager_link).is_ok() {
            let _ = fs::remove_file(&manager_link);
        }
        if let Err(e) = std::os::unix::fs::symlink(&install_dir, &manager_link) {
            log_warning(&format!("Failed to update manager_link for {}: {}", prefix_name, e));
        }

        // Fallback to first available proton (scripts use relative path to active symlink anyway)
        let proton_path = available_protons
            .first()
            .map(|p| p.path.clone())
            .unwrap_or_else(|| PathBuf::from("/usr/share/steam/compatibilitytools.d/proton"));

        log_info(&format!("Regenerating scripts for: {}", prefix_name));

        // Helper to create symlink with error logging (defined once, used for MO2 and Vortex)
        fn create_convenience_link(target: &Path, link_dir: &Path, link_name: &str) {
            let link_path = link_dir.join(link_name);
            // Remove existing (broken or not)
            if fs::symlink_metadata(&link_path).is_ok() {
                if let Err(e) = fs::remove_file(&link_path) {
                    crate::logging::log_warning(&format!(
                        "Failed to remove old symlink {}: {}", link_path.display(), e
                    ));
                    return;
                }
            }
            // Create new symlink
            if let Err(e) = std::os::unix::fs::symlink(target, &link_path) {
                crate::logging::log_warning(&format!(
                    "Failed to create symlink {} -> {}: {}",
                    link_path.display(), target.display(), e
                ));
            }
        }

        if is_mo2 {
            let mo2_exe = install_dir.join("ModOrganizer.exe");

            if let Err(e) = ScriptGenerator::generate_mo2_launch_script(
                &pfx_path,
                &mo2_exe,
                &proton_path,
                &install_dir,
                &prefix_dir,
            ) {
                log_error(&format!(
                    "Failed to regenerate MO2 launch script for {}: {}",
                    prefix_name, e
                ));
                continue;
            }

            // Kill prefix script
            if let Err(e) = ScriptGenerator::generate_kill_prefix_script(
                &pfx_path,
                &proton_path,
                &prefix_dir,
            ) {
                log_error(&format!(
                    "Failed to regenerate kill prefix script for {}: {}",
                    prefix_name, e
                ));
            }

            // NXM handler script
            let nxm_handler_exe = install_dir.join("nxmhandler.exe");
            if nxm_handler_exe.exists() {
                if let Err(e) = ScriptGenerator::generate_mo2_nxm_script(
                    &pfx_path,
                    &nxm_handler_exe,
                    &proton_path,
                    &prefix_dir,
                ) {
                    log_error(&format!(
                        "Failed to regenerate NXM script for {}: {}",
                        prefix_name, e
                    ));
                }
            }

            // Registry fix script
            if let Err(e) = ScriptGenerator::generate_fix_game_registry_script(
                &pfx_path,
                &proton_path,
                prefix_name,
                &prefix_dir,
            ) {
                log_error(&format!(
                    "Failed to regenerate registry script for {}: {}",
                    prefix_name, e
                ));
            }

            // Recreate convenience symlinks in MO2 folder
            let script_path = prefix_dir.join("start.sh");
            let kill_script = prefix_dir.join(".kill_prefix.sh");
            let reg_script = prefix_dir.join("game_registry_fix.sh");
            let nxm_script = prefix_dir.join("nxm_handler.sh");

            create_convenience_link(&script_path, &install_dir, "Launch MO2");
            create_convenience_link(&kill_script, &install_dir, "Kill MO2 Prefix");
            create_convenience_link(&reg_script, &install_dir, "Fix Game Registry");
            if nxm_script.exists() {
                create_convenience_link(&nxm_script, &install_dir, "Handle NXM");
            }
        } else if is_vortex {
            let vortex_exe = install_dir.join("Vortex.exe");

            if let Err(e) = ScriptGenerator::generate_vortex_launch_script(
                &pfx_path,
                &vortex_exe,
                &proton_path,
                &install_dir,
                &prefix_dir,
            ) {
                log_error(&format!(
                    "Failed to regenerate Vortex launch script for {}: {}",
                    prefix_name, e
                ));
                continue;
            }

            // Kill prefix script
            if let Err(e) = ScriptGenerator::generate_kill_prefix_script(
                &pfx_path,
                &proton_path,
                &prefix_dir,
            ) {
                log_error(&format!(
                    "Failed to regenerate kill prefix script for {}: {}",
                    prefix_name, e
                ));
            }

            // Registry fix script
            if let Err(e) = ScriptGenerator::generate_fix_game_registry_script(
                &pfx_path,
                &proton_path,
                prefix_name,
                &prefix_dir,
            ) {
                log_error(&format!(
                    "Failed to regenerate registry script for {}: {}",
                    prefix_name, e
                ));
            }

            // NXM handler script (Vortex.exe handles NXM links directly)
            if let Err(e) = ScriptGenerator::generate_vortex_nxm_script(
                &pfx_path,
                &vortex_exe,
                &proton_path,
                &prefix_dir,
            ) {
                log_error(&format!(
                    "Failed to regenerate NXM script for {}: {}",
                    prefix_name, e
                ));
            }

            // Recreate convenience symlinks in Vortex folder
            let script_path = prefix_dir.join("start.sh");
            let kill_script = prefix_dir.join(".kill_prefix.sh");
            let reg_script = prefix_dir.join("game_registry_fix.sh");
            let nxm_script = prefix_dir.join("nxm_handler.sh");

            create_convenience_link(&script_path, &install_dir, "Launch Vortex");
            create_convenience_link(&kill_script, &install_dir, "Kill Vortex Prefix");
            create_convenience_link(&reg_script, &install_dir, "Fix Game Registry");
            if nxm_script.exists() {
                create_convenience_link(&nxm_script, &install_dir, "Handle NXM");
            }
        }

        regenerated_count += 1;
    }

    log_info(&format!(
        "Script regeneration complete: {} prefix(es) updated",
        regenerated_count
    ));
    Ok(regenerated_count)
}
