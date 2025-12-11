//! Launch script generation for mod managers

use std::error::Error;
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

use crate::utils::detect_steam_path;
use crate::wine::runtime;

pub struct ScriptGenerator;

impl ScriptGenerator {
    pub fn generate_mo2_launch_script(
        prefix_path: &Path,
        mo2_exe: &Path,
        proton_ge_path: &Path,
        _install_dir: &Path,
        script_output_dir: &Path,
    ) -> Result<std::path::PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let compat_data = prefix_path.parent().unwrap_or(prefix_path);
        let runtime_entry = runtime::get_entry_point();

        let script_content = if let Some(entry_point) = runtime_entry {
            format!(
                r#"#!/bin/bash
# NaK Generated Launch Script for MO2
# Running inside Steam Linux Runtime (Sniper) Container

PROTON_GE='{proton}'
PREFIX='{prefix}'
MO2_EXE='{exe}'
ENTRY_POINT='{entry}'
STEAM_PATH='{steam_path}'
COMPAT_DATA='{compat_data}'

# Check environment
if [ ! -f "$ENTRY_POINT" ]; then
    echo "ERROR: Steam Runtime entry point not found at $ENTRY_POINT"
    exit 1
fi

# Set environment variables for the Container
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

echo "Launching Mod Organizer 2 (Containerized)..."
"$ENTRY_POINT" --verb=waitforexitandrun -- "$PROTON_GE/proton" run "$MO2_EXE" "$@"
"#,
                prefix = prefix_path.to_string_lossy(),
                proton = proton_ge_path.to_string_lossy(),
                compat_data = compat_data.to_string_lossy(),
                steam_path = steam_path,
                exe = mo2_exe.to_string_lossy(),
                entry = entry_point.to_string_lossy()
            )
        } else {
            return Err("Steam Linux Runtime (Sniper) not found! Please download it in NaK Settings (Proton Picker).".into());
        };

        let script_path = script_output_dir.join("start.sh");
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
        script_output_dir: &Path,
    ) -> Result<std::path::PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let compat_data = prefix_path.parent().unwrap_or(prefix_path);
        let runtime_entry = runtime::get_entry_point();

        let script_content = if let Some(entry_point) = runtime_entry {
            format!(
                r#"#!/bin/bash
# NaK Generated Launch Script for Vortex
# Running inside Steam Linux Runtime (Sniper) Container

PROTON_GE='{proton}'
PREFIX='{prefix}'
VORTEX_EXE='{exe}'
ENTRY_POINT='{entry}'
STEAM_PATH='{steam_path}'
COMPAT_DATA='{compat_data}'

# Check environment
if [ ! -f "$ENTRY_POINT" ]; then
    echo "ERROR: Steam Runtime entry point not found at $ENTRY_POINT"
    exit 1
fi

# Set environment variables for the Container
export WINEPREFIX="$PREFIX"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_PATH"
export PROTON_DIST_PATH="$PROTON_GE"

# Set GAMEID for protonfixes
export GAMEID="non-steam-game"

# DotNet Fixes
export DOTNET_ROOT=""
export DOTNET_MULTILEVEL_LOOKUP=0

echo "Launching Vortex (Containerized)..."
"$ENTRY_POINT" --verb=waitforexitandrun -- "$PROTON_GE/proton" run "$VORTEX_EXE" "$@"
"#,
                prefix = prefix_path.to_string_lossy(),
                proton = proton_ge_path.to_string_lossy(),
                compat_data = compat_data.to_string_lossy(),
                steam_path = steam_path,
                exe = vortex_exe.to_string_lossy(),
                entry = entry_point.to_string_lossy()
            )
        } else {
            return Err("Steam Linux Runtime (Sniper) not found! Please download it in NaK Settings (Proton Picker).".into());
        };

        let script_path = script_output_dir.join("start.sh");
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
        script_output_dir: &Path,
    ) -> Result<std::path::PathBuf, Box<dyn Error>> {
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
        instance_name: &str,
        script_output_dir: &Path,
    ) -> Result<std::path::PathBuf, Box<dyn Error>> {
        let steam_path = detect_steam_path();
        let compat_data = prefix_path.parent().unwrap_or(prefix_path);
        let runtime_entry = runtime::get_entry_point();

        // Check if we have the runtime, use it if possible, else error
        let entry_point = if let Some(ep) = runtime_entry {
            ep
        } else {
             return Err("Steam Linux Runtime (Sniper) not found.".into());
        };

        let script_content = format!(
            r#"#!/bin/bash
# NaK Game Registry Fixer
# Instance: {instance_name}

PREFIX='{prefix}'
PROTON_GE='{proton}'
COMPAT_DATA='{compat_data}'
STEAM_PATH='{steam_path}'
ENTRY_POINT='{entry}'

echo "=================================================="
echo "NaK Game Registry Fixer"
echo "Instance: {instance_name}"
echo "=================================================="
echo ""

# Check environment
if [ ! -f "$ENTRY_POINT" ]; then
    echo "ERROR: Steam Runtime entry point not found at $ENTRY_POINT"
    exit 1
fi

# Set environment variables for the Container
export WINEPREFIX="$PREFIX"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_PATH"
export PROTON_DIST_PATH="$PROTON_GE"
export GAMEID="non-steam-game"

# DotNet Fixes
export DOTNET_ROOT=""
export DOTNET_MULTILEVEL_LOOKUP=0

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
for i in "${{!GAMES[@]}}"; do
    game_name=$(echo "${{GAMES[$i]}}" | cut -d'|' -f1)
    echo "  $((i+1)). $game_name"
done
echo ""
read -p "Enter number (1-${{#GAMES[@]}}): " choice

# Validate input
if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${{#GAMES[@]}}" ]; then
    echo "ERROR: Invalid selection"
    exit 1
fi

# Get selected game info
selected_game="${{GAMES[$((choice-1))]}}"
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
WINE_PATH="Z:${{GAME_PATH_LINUX//\//\\}}"

echo ""
echo "=================================================="
echo "Registry Fix Details"
echo "=================================================="
echo "Game: $GAME_NAME"
echo "Linux Path: $GAME_PATH_LINUX"
echo "Wine Path: $WINE_PATH"
echo "Registry Key: HKLM\\${{REG_PATH}}"
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

# Function to set registry value using Container
set_registry() {{
    local reg_key="$1"
    local reg_flag="$2"

    echo "Setting: $reg_key ($reg_flag)"
    # Run reg.exe inside the container
    "$ENTRY_POINT" --verb=waitforexitandrun -- "$PROTON_GE/proton" run reg add "HKLM\\$reg_key" /v "$VALUE_NAME" /d "$WINE_PATH" /f $reg_flag

    if [ $? -eq 0 ]; then
        echo "  ✓ Success"
        return 0
    else
        echo "  ✗ Failed"
        return 1
    fi
}}

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
    "$ENTRY_POINT" --verb=waitforexitandrun -- "$PROTON_GE/proton" run reg query "HKLM\\${{REG_PATH}}" /v "$VALUE_NAME" /reg:32 > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "  ✓ 32-bit Key: FOUND"
    else
        echo "  ✗ 32-bit Key: NOT FOUND"
    fi

    # 64-bit check
    "$ENTRY_POINT" --verb=waitforexitandrun -- "$PROTON_GE/proton" run reg query "HKLM\\${{WOW64_PATH}}" /v "$VALUE_NAME" /reg:64 > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "  ✓ 64-bit Key: FOUND"
    else
        echo "  ✗ 64-bit Key: NOT FOUND"
    fi
fi

echo ""
echo "Done!"
"#,
            prefix = prefix_path.to_string_lossy(),
            proton = proton_ge_path.to_string_lossy(),
            compat_data = compat_data.to_string_lossy(),
            steam_path = steam_path,
            instance_name = instance_name,
            entry = entry_point.to_string_lossy()
        );

        let script_path = script_output_dir.join("game_registry_fix.sh");
        let mut file = fs::File::create(&script_path)?;
        file.write_all(script_content.as_bytes())?;

        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;

        println!("Created game registry fix script at {:?}", script_path);
        Ok(script_path)
    }
}
