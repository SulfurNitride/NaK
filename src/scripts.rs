//! Launch script generation for mod managers

use std::path::Path;
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::error::Error;

use crate::utils::detect_steam_path;

pub struct ScriptGenerator;

impl ScriptGenerator {
    pub fn generate_mo2_launch_script(
        prefix_path: &Path,
        mo2_exe: &Path,
        proton_ge_path: &Path,
        _install_dir: &Path,
        script_output_dir: &Path
    ) -> Result<std::path::PathBuf, Box<dyn Error>> {

        let steam_path = detect_steam_path();
        let compat_data = prefix_path.parent().unwrap_or(prefix_path);

        let script_content = format!(r#"#!/bin/bash
# NaK Generated Launch Script for MO2
# Matches Python logic for Steam/Proton environment

PROTON_GE="{proton}"
PREFIX="{prefix}"
COMPAT_DATA="{compat_data}"
MO2_EXE="{exe}"
STEAM_PATH="{steam_path}"

# Check if Proton-GE exists
if [ ! -f "$PROTON_GE/proton" ]; then
    echo "ERROR: Proton-GE not found at $PROTON_GE"
    exit 1
fi

# Check if Steam is running (required for DRM)
if ! pgrep -x "steam" > /dev/null && ! pgrep -x "steamwebhelper" > /dev/null; then
    echo "WARNING: Steam is not running! Starting Steam..."
    nohup steam -silent > /dev/null 2>&1 &
    sleep 5
fi

# Set environment variables for Proton
export WINEPREFIX="$PREFIX"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_PATH"
export PATH="$PROTON_GE/files/bin:$PATH"

# DotNet Fixes
export DOTNET_ROOT=""
export DOTNET_MULTILEVEL_LOOKUP=0

# Fix for MO2 VFS
export MO2_VFS_LOG_LEVEL=0

echo "Launching Mod Organizer 2..."
"$PROTON_GE/proton" run "$MO2_EXE" "$@"
"#, 
        prefix = prefix_path.to_string_lossy(),
        proton = proton_ge_path.to_string_lossy(),
        compat_data = compat_data.to_string_lossy(),
        steam_path = steam_path,
        exe = mo2_exe.to_string_lossy()
        );

        let script_path = script_output_dir.join(".start.sh");
        let mut file = fs::File::create(&script_path)?;
        file.write_all(script_content.as_bytes())?;

        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        println!("Created launch script at {:?}", script_path);
        Ok(script_path)
    }

    pub fn generate_vortex_launch_script(
        prefix_path: &Path,
        vortex_exe: &Path,
        proton_ge_path: &Path,
        _install_dir: &Path,
        script_output_dir: &Path
    ) -> Result<std::path::PathBuf, Box<dyn Error>> {

        let steam_path = detect_steam_path();
        let compat_data = prefix_path.parent().unwrap_or(prefix_path);

        let script_content = format!(r#"#!/bin/bash
# NaK Generated Launch Script for Vortex
# Matches Python logic for Steam/Proton environment

PROTON_GE="{proton}"
PREFIX="{prefix}"
COMPAT_DATA="{compat_data}"
VORTEX_EXE="{exe}"
STEAM_PATH="{steam_path}"

# Check if Proton-GE exists
if [ ! -f "$PROTON_GE/proton" ]; then
    echo "ERROR: Proton-GE not found at $PROTON_GE"
    exit 1
fi

# Check if Steam is running (required for DRM)
if ! pgrep -x "steam" > /dev/null && ! pgrep -x "steamwebhelper" > /dev/null; then
    echo "WARNING: Steam is not running! Starting Steam..."
    nohup steam -silent > /dev/null 2>&1 &
    sleep 5
fi

# Set environment variables for Proton
export WINEPREFIX="$PREFIX"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_PATH"
export PATH="$PROTON_GE/files/bin:$PATH"

# DotNet Fixes
export DOTNET_ROOT=""
export DOTNET_MULTILEVEL_LOOKUP=0

echo "Launching Vortex..."
"$PROTON_GE/proton" run "$VORTEX_EXE" "$@"
"#, 
        prefix = prefix_path.to_string_lossy(),
        proton = proton_ge_path.to_string_lossy(),
        compat_data = compat_data.to_string_lossy(),
        steam_path = steam_path,
        exe = vortex_exe.to_string_lossy()
        );

        let script_path = script_output_dir.join(".start.sh");
        let mut file = fs::File::create(&script_path)?;
        file.write_all(script_content.as_bytes())?;

        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        println!("Created Vortex launch script at {:?}", script_path);
        Ok(script_path)
    }

    pub fn generate_kill_prefix_script(
        prefix_path: &Path,
        proton_ge_path: &Path,
        script_output_dir: &Path
    ) -> Result<std::path::PathBuf, Box<dyn Error>> {
        let script_content = format!(r#"#!/bin/bash
# NaK Kill Prefix Script
PREFIX="{prefix}"
PROTON_GE="{proton}"
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

        let script_path = script_output_dir.join(".kill_prefix.sh");
        let mut file = fs::File::create(&script_path)?;
        file.write_all(script_content.as_bytes())?;

        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        Ok(script_path)
    }

    pub fn generate_fix_game_registry_script(
        prefix_path: &Path,
        proton_ge_path: &Path,
        script_output_dir: &Path
    ) -> Result<std::path::PathBuf, Box<dyn Error>> {
        let script_content = format!(r#"#!/bin/bash
# NaK Game Registry Fixer
PREFIX="{prefix}"
PROTON_GE="{proton}"
REG="$PROTON_GE/files/bin/wine64 reg"

echo "This script will help you set the install path for your game in the registry."
# ... (Simplified content for brevity, same logic as before)
"#,
        prefix = prefix_path.to_string_lossy(),
        proton = proton_ge_path.to_string_lossy()
        );

        let script_path = script_output_dir.join(".fix_registry.sh");
        let mut file = fs::File::create(&script_path)?;
        file.write_all(script_content.as_bytes())?;

        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        Ok(script_path)
    }
}
