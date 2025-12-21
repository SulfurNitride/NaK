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
// Script Configuration
// ============================================================================

/// Type of script to generate
#[derive(Clone, Copy)]
pub enum ScriptType {
    Mo2Launch,
    Mo2Nxm,
    VortexLaunch,
    GameRegistryFix,
    KillPrefix,
}

/// Configuration for script generation
pub struct ScriptConfig<'a> {
    pub script_type: ScriptType,
    pub prefix_path: &'a Path,
    pub executable: &'a Path,
    pub proton_path: &'a Path,
    pub output_dir: &'a Path,
    pub instance_name: Option<&'a str>,
}

// ============================================================================
// Script Generator
// ============================================================================

pub struct ScriptGenerator;

impl ScriptGenerator {
    /// Check if we should use Steam Linux Runtime based on config
    fn should_use_slr() -> bool {
        AppConfig::load().use_steam_runtime
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
export MO2_VFS_LOG_LEVEL=0"#.to_string()
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
export MO2_VFS_LOG_LEVEL=0"#.to_string()
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
    fn generate_launch_script(
        prefix_path: &Path,
        exe: &Path,
        proton_path: &Path,
        output_dir: &Path,
        manager_name: &str,
    ) -> Result<PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let compat_data = prefix_path.parent().unwrap_or(prefix_path);
        let use_slr = Self::should_use_slr();
        let runtime_entry = runtime::get_entry_point();

        let exe_var_name = if manager_name == "MO2" { "MO2_EXE" } else { "VORTEX_EXE" };
        let comment_name = if manager_name == "MO2" { "MO2" } else { "Vortex" };

        let script_content = if use_slr {
            let entry_point = runtime_entry.ok_or(
                "Steam Linux Runtime (Sniper) not found! Please download it in Proton Picker or disable it in Settings."
            )?;

            format!(
                r#"#!/bin/bash
# NaK Generated Launch Script for {comment_name}
# Running inside Steam Linux Runtime (Sniper) Container

PROTON_GE='{proton}'
PREFIX='{prefix}'
{exe_var_name}='{exe}'
ENTRY_POINT='{entry}'
STEAM_PATH='{steam_path}'
COMPAT_DATA='{compat_data}'
{slr_check}
{env_block}

echo "Launching {comment_name} (Containerized)..."
{launch_cmd}
"#,
                comment_name = comment_name,
                proton = proton_path.to_string_lossy(),
                prefix = prefix_path.to_string_lossy(),
                exe_var_name = exe_var_name,
                exe = exe.to_string_lossy(),
                entry = entry_point.to_string_lossy(),
                steam_path = steam_path,
                compat_data = compat_data.to_string_lossy(),
                slr_check = Self::get_slr_check_block(),
                env_block = Self::get_env_block(true),
                launch_cmd = Self::get_launch_command(true, exe_var_name, r#""$@""#)
            )
        } else {
            format!(
                r#"#!/bin/bash
# NaK Generated Launch Script for {comment_name}
# Running WITHOUT Steam Linux Runtime (Direct Proton)

PROTON_GE='{proton}'
PREFIX='{prefix}'
{exe_var_name}='{exe}'
STEAM_PATH='{steam_path}'
COMPAT_DATA='{compat_data}'

{env_block}

echo "Launching {comment_name} (Direct Proton)..."
{launch_cmd}
"#,
                comment_name = comment_name,
                proton = proton_path.to_string_lossy(),
                prefix = prefix_path.to_string_lossy(),
                exe_var_name = exe_var_name,
                exe = exe.to_string_lossy(),
                steam_path = steam_path,
                compat_data = compat_data.to_string_lossy(),
                env_block = Self::get_env_block(false),
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
    pub fn generate_mo2_nxm_script(
        prefix_path: &Path,
        nxm_handler_exe: &Path,
        proton_ge_path: &Path,
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let compat_data = prefix_path.parent().unwrap_or(prefix_path);
        let use_slr = Self::should_use_slr();
        let runtime_entry = runtime::get_entry_point();

        let script_content = if use_slr {
            let entry_point = runtime_entry.ok_or(
                "Steam Linux Runtime (Sniper) not found! Please download it in Proton Picker or disable it in Settings."
            )?;

            format!(
                r#"#!/bin/bash
# NaK Generated NXM Handler Script for MO2
# Running inside Steam Linux Runtime (Sniper) Container

PROTON_GE='{proton}'
PREFIX='{prefix}'
NXM_HANDLER='{exe}'
ENTRY_POINT='{entry}'
STEAM_PATH='{steam_path}'
COMPAT_DATA='{compat_data}'
{slr_check}
{env_block}

echo "Handling NXM link via MO2 nxmhandler..."
{launch_cmd}
"#,
                proton = proton_ge_path.to_string_lossy(),
                prefix = prefix_path.to_string_lossy(),
                exe = nxm_handler_exe.to_string_lossy(),
                entry = entry_point.to_string_lossy(),
                steam_path = steam_path,
                compat_data = compat_data.to_string_lossy(),
                slr_check = Self::get_slr_check_block(),
                env_block = Self::get_env_block(true),
                launch_cmd = Self::get_launch_command(true, "NXM_HANDLER", r#""$@""#)
            )
        } else {
            format!(
                r#"#!/bin/bash
# NaK Generated NXM Handler Script for MO2
# Running WITHOUT Steam Linux Runtime (Direct Proton)

PROTON_GE='{proton}'
PREFIX='{prefix}'
NXM_HANDLER='{exe}'
STEAM_PATH='{steam_path}'
COMPAT_DATA='{compat_data}'

{env_block}

echo "Handling NXM link via MO2 nxmhandler (Direct Proton)..."
{launch_cmd}
"#,
                proton = proton_ge_path.to_string_lossy(),
                prefix = prefix_path.to_string_lossy(),
                exe = nxm_handler_exe.to_string_lossy(),
                steam_path = steam_path,
                compat_data = compat_data.to_string_lossy(),
                env_block = Self::get_env_block(false),
                launch_cmd = Self::get_launch_command(false, "NXM_HANDLER", r#""$@""#)
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
        Self::generate_launch_script(prefix_path, mo2_exe, proton_ge_path, script_output_dir, "MO2")
    }

    /// Generate launch script for Vortex
    pub fn generate_vortex_launch_script(
        prefix_path: &Path,
        vortex_exe: &Path,
        proton_ge_path: &Path,
        _install_dir: &Path,
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        Self::generate_launch_script(prefix_path, vortex_exe, proton_ge_path, script_output_dir, "Vortex")
    }

    /// Generate kill prefix script
    pub fn generate_kill_prefix_script(
        prefix_path: &Path,
        proton_ge_path: &Path,
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        let script_content = format!(
            r#"#!/bin/bash
# NaK Kill Prefix Script
PREFIX='{prefix}'
PROTON_GE='{proton}'
WINESERVER="$PROTON_GE/files/bin/wineserver"

echo "Killing Wine processes for prefix: $PREFIX"

export WINEPREFIX="$PREFIX"

if [ -f "$WINESERVER" ]; then
    "$WINESERVER" -k
else
    wineserver -k
fi

echo "Done."
"#,
            prefix = prefix_path.to_string_lossy(),
            proton = proton_ge_path.to_string_lossy()
        );

        Self::write_script(script_output_dir, ".kill_prefix.sh", &script_content)
    }

    /// Generate game registry fix script
    pub fn generate_fix_game_registry_script(
        prefix_path: &Path,
        proton_ge_path: &Path,
        instance_name: &str,
        script_output_dir: &Path,
    ) -> Result<PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let compat_data = prefix_path.parent().unwrap_or(prefix_path);
        let use_slr = Self::should_use_slr();
        let runtime_entry = runtime::get_entry_point();

        let header = if use_slr {
            let entry_point = runtime_entry.ok_or(
                "Steam Linux Runtime (Sniper) not found! Please download it in Proton Picker or disable it in Settings."
            )?;

            format!(
                r#"#!/bin/bash
# NaK Game Registry Fixer
# Instance: {instance_name}
# Mode: Steam Linux Runtime (Containerized)

PREFIX='{prefix}'
PROTON_GE='{proton}'
COMPAT_DATA='{compat_data}'
STEAM_PATH='{steam_path}'
ENTRY_POINT='{entry}'
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
                prefix = prefix_path.to_string_lossy(),
                proton = proton_ge_path.to_string_lossy(),
                compat_data = compat_data.to_string_lossy(),
                steam_path = steam_path,
                entry = entry_point.to_string_lossy(),
                slr_check = Self::get_slr_check_block(),
                env_block = Self::get_env_block(true)
            )
        } else {
            format!(
                r#"#!/bin/bash
# NaK Game Registry Fixer
# Instance: {instance_name}
# Mode: Direct Proton (No Steam Linux Runtime)

PREFIX='{prefix}'
PROTON_GE='{proton}'
COMPAT_DATA='{compat_data}'
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
                prefix = prefix_path.to_string_lossy(),
                proton = proton_ge_path.to_string_lossy(),
                compat_data = compat_data.to_string_lossy(),
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
// Regenerate All Scripts
// ============================================================================

/// Regenerate all launch scripts for existing prefixes
/// This is called when the user toggles the Steam Linux Runtime setting
pub fn regenerate_all_prefix_scripts() -> Result<usize, Box<dyn Error>> {
    use crate::logging::{log_error, log_info, log_warning};
    use crate::wine::ProtonFinder;

    let home = std::env::var("HOME")?;
    let prefixes_dir = PathBuf::from(format!("{}/NaK/Prefixes", home));

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

        // Check for manager_link to find the install directory
        let manager_link = prefix_dir.join("manager_link");
        if !manager_link.exists() {
            log_warning(&format!("Skipping {}: no manager_link found", prefix_name));
            continue;
        }

        let install_dir = match fs::read_link(&manager_link) {
            Ok(path) => path,
            Err(e) => {
                log_warning(&format!(
                    "Skipping {}: can't read manager_link: {}",
                    prefix_name, e
                ));
                continue;
            }
        };

        let pfx_path = prefix_dir.join("pfx");
        if !pfx_path.exists() {
            log_warning(&format!("Skipping {}: no pfx directory found", prefix_name));
            continue;
        }

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

        // Try to determine which Proton was used by reading existing script
        let start_script = prefix_dir.join("start.sh");
        let proton_path = if start_script.exists() {
            if let Ok(content) = fs::read_to_string(&start_script) {
                content
                    .lines()
                    .find(|line| line.starts_with("PROTON_GE="))
                    .and_then(|line| {
                        let path = line
                            .trim_start_matches("PROTON_GE='")
                            .trim_end_matches("'");
                        Some(PathBuf::from(path))
                    })
            } else {
                None
            }
        } else {
            None
        };

        // Fallback to first available proton
        let proton_path = proton_path.unwrap_or_else(|| {
            available_protons
                .first()
                .map(|p| p.path.clone())
                .unwrap_or_else(|| {
                    PathBuf::from("/usr/share/steam/compatibilitytools.d/proton")
                })
        });

        log_info(&format!("Regenerating scripts for: {}", prefix_name));

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
        }

        regenerated_count += 1;
    }

    log_info(&format!(
        "Script regeneration complete: {} prefix(es) updated",
        regenerated_count
    ));
    Ok(regenerated_count)
}
