#!/bin/bash
# ===================================================================
# NaK (Linux Modding Helper) - Complete Gum Version
# Version: 3.3.0
# ===================================================================

# Script metadata
readonly SCRIPT_VERSION="3.3.0"
readonly SCRIPT_NAME="NaK - Linux Modding Helper"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly GUM_BINARY="$SCRIPT_DIR/bin/gum"

# Configuration
readonly CONFIG_DIR="$HOME/.config/nak"
readonly CONFIG_FILE="$CONFIG_DIR/config.ini"
readonly LOG_FILE="$HOME/nak.log"
readonly TEMP_DIR="/tmp/nak_$$"

# Global variables
declare -g SELECTED_GAME=""
declare -g SELECTED_APPID=""
declare -g STEAM_ROOT=""
declare -g PROTONTRICKS_CMD=""
declare -g PROTONTRICKS_IS_FLATPAK=false

# Portable Python setup (matching main NaK)
PORTABLE_PYTHON_URL="https://github.com/bjia56/portable-python/releases/download/cpython-v3.13.1-build.3/python-full-3.13.1-linux-x86_64.zip"
PORTABLE_PYTHON_DIR="$SCRIPT_DIR/lib/portable_python"
PORTABLE_PYTHON_ZIP="$PORTABLE_PYTHON_DIR/python-full.zip"
PORTABLE_PYTHON_EXTRACT_DIR="$PORTABLE_PYTHON_DIR/python-full-3.13.1-linux-x86_64"
PORTABLE_PYTHON_BINARY="$PORTABLE_PYTHON_EXTRACT_DIR/bin/python3"

# Default component arrays
declare -a components=()

# Gum styling
export GUM_CHOOSE_CURSOR_FOREGROUND="#00FF00"
export GUM_FILTER_MATCH_FOREGROUND="#00FF00"
export GUM_CHOOSE_SELECTED_FOREGROUND="#FFD700"
export GUM_INPUT_CURSOR_FOREGROUND="#00FF00"

# ===================================================================
# Core Functions
# ===================================================================

# Initialize
init() {
    # Create directories
    mkdir -p "$CONFIG_DIR" "$TEMP_DIR" "$SCRIPT_DIR/bin" "$SCRIPT_DIR/lib"

    # Setup logging
    touch "$LOG_FILE"
    log "Starting $SCRIPT_NAME v$SCRIPT_VERSION"

    # Check for gum and install if needed
    if [[ ! -f "$GUM_BINARY" ]]; then
        echo "Gum not found. Installing..."
        install_gum

        # Verify installation
        if [[ ! -f "$GUM_BINARY" ]]; then
            echo "Error: Gum installation failed"
            echo "Checking if system gum is available..."
            if command -v gum &> /dev/null; then
                echo "Using system gum instead"
                GUM_BINARY="$(command -v gum)"
            else
                echo "No gum found. Please install gum manually:"
                echo "https://github.com/charmbracelet/gum#installation"
                exit 1
            fi
        fi
    fi

    # Check dependencies
    check_dependencies

    # Find Steam
    STEAM_ROOT=$(find_steam_root)

    # Load config
    load_config

    # Trap cleanup
    trap cleanup EXIT INT TERM
}

# Install gum binary
install_gum() {
    local gum_version="0.14.5"
    local gum_url="https://github.com/charmbracelet/gum/releases/download/v${gum_version}/gum_${gum_version}_Linux_x86_64.tar.gz"
    local temp_file="$TEMP_DIR/gum.tar.gz"

    echo "Creating bin directory..."
    mkdir -p "$SCRIPT_DIR/bin"

    echo "Downloading gum v${gum_version}..."
    if curl -L -o "$temp_file" "$gum_url"; then
        echo "Download successful. Extracting..."
        if tar -xzf "$temp_file" -C "$TEMP_DIR"; then
            echo "Extraction successful. Looking for binary..."

            # Find the gum binary in the extracted directory
            local gum_binary=$(find "$TEMP_DIR" -name "gum" -type f -executable 2>/dev/null | head -1)

            if [[ -n "$gum_binary" && -f "$gum_binary" ]]; then
                echo "Found gum binary at: $gum_binary"
                cp "$gum_binary" "$GUM_BINARY"
                chmod +x "$GUM_BINARY"
                echo "Gum installed successfully at: $GUM_BINARY"
            else
                echo "Error: gum binary not found after extraction"
                exit 1
            fi
        else
            echo "Error: Failed to extract gum archive"
            exit 1
        fi
    else
        echo "Failed to download gum. Please check your internet connection."
        exit 1
    fi
}

# Setup portable Python (matching main NaK exactly)
setup_portable_python() {
    log "Setting up portable Python"

    # Create directory if it doesn't exist
    mkdir -p "$PORTABLE_PYTHON_DIR"

    # Check if Python is already extracted
    if [ -f "$PORTABLE_PYTHON_BINARY" ] && [ -x "$PORTABLE_PYTHON_BINARY" ]; then
        log "Portable Python already exists at $PORTABLE_PYTHON_BINARY"
        return 0
    fi

    log "Downloading portable Python from $PORTABLE_PYTHON_URL"

    # Check for download tools
    local download_tool=""
    if command -v curl &>/dev/null; then
        download_tool="curl -L -o"
    elif command -v wget &>/dev/null; then
        download_tool="wget -O"
    else
        log "Neither curl nor wget is available"
        return 1
    fi

    # Download the ZIP file
    if ! $download_tool "$PORTABLE_PYTHON_ZIP" "$PORTABLE_PYTHON_URL"; then
        log "Failed to download portable Python"
        return 1
    fi

    log "Extracting portable Python to $PORTABLE_PYTHON_DIR"

    # Check for unzip tool
    if ! command -v unzip &>/dev/null; then
        log "unzip is not available"
        return 1
    fi

    # Extract the ZIP file
    if ! unzip -o "$PORTABLE_PYTHON_ZIP" -d "$PORTABLE_PYTHON_DIR"; then
        log "Failed to extract portable Python"
        return 1
    fi

    # Make sure the Python binary is executable
    if [ -f "$PORTABLE_PYTHON_BINARY" ]; then
        chmod +x "$PORTABLE_PYTHON_BINARY"
    else
        log "Python binary not found at expected location: $PORTABLE_PYTHON_BINARY"
        return 1
    fi

    # Verify the installation
    if [ ! -x "$PORTABLE_PYTHON_BINARY" ]; then
        log "Portable Python binary not found or not executable"
        return 1
    fi

    log "Portable Python set up successfully at $PORTABLE_PYTHON_BINARY"

    # Remove the ZIP file to save space
    rm -f "$PORTABLE_PYTHON_ZIP"

    return 0
}

# Get portable Python path
get_portable_python() {
    # Check if portable Python is set up
    if [ ! -f "$PORTABLE_PYTHON_BINARY" ] || [ ! -x "$PORTABLE_PYTHON_BINARY" ]; then
        # Try to set it up
        if ! setup_portable_python; then
            return 1
        fi
    fi

    # Return the path to the Python binary
    echo "$PORTABLE_PYTHON_BINARY"
    return 0
}

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Cleanup
cleanup() {
    rm -rf "$TEMP_DIR"
    log "Cleanup completed"
}

# Enhanced dependency checking
check_dependencies() {
    local missing=()

    # Detect protontricks with better handling
    if command -v protontricks >/dev/null 2>&1; then
        PROTONTRICKS_CMD="protontricks"
        log "Found native protontricks"
    elif flatpak list --app 2>/dev/null | grep -q "com.github.Matoking.protontricks"; then
        PROTONTRICKS_CMD="flatpak run com.github.Matoking.protontricks"
        PROTONTRICKS_IS_FLATPAK=true
        setup_flatpak_permissions
        log "Found Flatpak protontricks"
    else
        missing+=("protontricks")
    fi

    # Check other dependencies
    for cmd in curl wget jq unzip; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done

    # Check for 7z variants
    local has_7z=false
    for variant in 7z 7za 7zr p7zip; do
        if command -v "$variant" &> /dev/null; then
            has_7z=true
            break
        fi
    done
    [[ "$has_7z" == "false" ]] && missing+=("p7zip-full")

    if [[ ${#missing[@]} -gt 0 ]]; then
        "$GUM_BINARY" style --foreground 196 --border double --padding "1 2" \
            "Missing dependencies: ${missing[*]}" \
            "" \
            "Install with: sudo apt install ${missing[*]}"
        exit 1
    fi
}

# Setup Flatpak permissions
setup_flatpak_permissions() {
    log "Setting up Flatpak permissions for Steam libraries"

    local additional_paths=(
        "/media"
        "/mnt"
        "/opt"
    )

    for path in "${additional_paths[@]}"; do
        if [[ -d "$path" ]]; then
            flatpak override --user --filesystem="$path:ro" com.github.Matoking.protontricks 2>/dev/null || true
        fi
    done
}

# Find Steam root
find_steam_root() {
    local candidates=(
        "$HOME/.local/share/Steam"
        "$HOME/.steam/steam"
        "$HOME/.steam/debian-installation"
    )

    for path in "${candidates[@]}"; do
        if [[ -d "$path/steamapps" ]]; then
            echo "$path"
            return 0
        fi
    done

    "$GUM_BINARY" style --foreground 196 "Steam installation not found!"
    exit 1
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE"
    else
        cat > "$CONFIG_FILE" << EOF
# NaK Configuration
DEFAULT_SCALING=96
SHOW_ADVANCED=false
CHECK_UPDATES=true
SHOW_ADVICE=true
EOF
    fi
}

# Save configuration
save_config() {
    local key="$1"
    local value="$2"

    if grep -q "^$key=" "$CONFIG_FILE" 2>/dev/null; then
        sed -i "s/^$key=.*/$key=$value/" "$CONFIG_FILE"
    else
        echo "$key=$value" >> "$CONFIG_FILE"
    fi
}

# ===================================================================
# Enhanced Protontricks Integration
# ===================================================================

# Safe game list retrieval with timeout
get_game_list_safe() {
    local games_output
    local exit_code

    # Show progress
    "$GUM_BINARY" spin --spinner dot --title "Fetching game list from protontricks..." -- sleep 2

    # Use timeout to prevent hanging
    games_output=$(timeout 30 $PROTONTRICKS_CMD -l 2>&1)
    exit_code=$?

    case $exit_code in
        0) echo "$games_output" ;;
        124)
            "$GUM_BINARY" style --foreground 196 "Protontricks timed out while fetching game list"
            return 1
            ;;
        *)
            "$GUM_BINARY" style --foreground 196 "Failed to get game list: Check logs"
            log "Protontricks error: $games_output"
            return 1
            ;;
    esac
}

# Parse and format game names properly
parse_games_enhanced() {
    local games_raw="$1"
    local -a games_array=()
    local collecting=false

    while IFS= read -r line; do
        # Start collecting after "Found the following games:"
        if [[ "$line" == "Found the following games:"* ]]; then
            collecting=true
            continue
        fi

        # Stop at note line
        if [[ "$line" == "To run Protontricks"* ]]; then
            break
        fi

        # Parse game entries - Fixed regex to handle all game name formats
        if [[ "$collecting" == true ]] && [[ "$line" =~ ^[[:space:]]*(.+)[[:space:]]\(([0-9]+)\)[[:space:]]*$ ]]; then
            local game_name="${BASH_REMATCH[1]}"
            local app_id="${BASH_REMATCH[2]}"

            # Trim whitespace
            game_name=$(echo "$game_name" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

            # Skip system entries
            if [[ ! "$game_name" =~ (SteamVR|Proton|Steam Linux Runtime) ]]; then
                games_array+=("$app_id|$game_name")
            fi
        fi
    done <<< "$games_raw"

    printf '%s\n' "${games_array[@]}"
}

# Format long game names intelligently
format_game_name() {
    local name="$1"
    local max_width="${2:-60}"

    if [[ ${#name} -gt $max_width ]]; then
        # Use middle truncation for better identification
        local prefix_len=$(( (max_width - 3) / 2 ))
        local suffix_len=$(( max_width - 3 - prefix_len ))
        echo "${name:0:$prefix_len}...${name: -$suffix_len}"
    else
        echo "$name"
    fi
}

# Enhanced game selection
select_game() {
    local games_output
    games_output=$(get_game_list_safe) || return 1

    local games_parsed=($(parse_games_enhanced "$games_output"))

    if [[ ${#games_parsed[@]} -eq 0 ]]; then
        "$GUM_BINARY" style --foreground 196 "No games found!"
        return 1
    fi

    # Format for gum choose
    local menu_items=()
    for game_entry in "${games_parsed[@]}"; do
        IFS='|' read -r app_id game_name <<< "$game_entry"
        local formatted_name=$(format_game_name "$game_name" 50)
        menu_items+=("[$app_id] $formatted_name")
    done

    local choice=$("$GUM_BINARY" choose --height 15 --header "Select a game:" "${menu_items[@]}")

    if [[ -n "$choice" ]]; then
        # Extract app ID from choice
        SELECTED_APPID=$(echo "$choice" | sed -n 's/^\[\([0-9]*\)\].*/\1/p')

        # Find full game name
        for game_entry in "${games_parsed[@]}"; do
            IFS='|' read -r app_id game_name <<< "$game_entry"
            if [[ "$app_id" == "$SELECTED_APPID" ]]; then
                SELECTED_GAME="$game_name"
                break
            fi
        done

        log "Selected game: $SELECTED_GAME (AppID: $SELECTED_APPID)"
        return 0
    fi

    return 1
}

# ===================================================================
# VDF Functions (from main NaK)
# ===================================================================

# Install vdf package
install_vdf_package() {
    log "Installing vdf Python package"

    # Get the portable Python binary
    local python_bin=$(get_portable_python)
    if [ $? -ne 0 ]; then
        log "Failed to set up portable Python"
        return 1
    fi

    # Create the pip directory if it doesn't exist
    local pip_dir="$PORTABLE_PYTHON_EXTRACT_DIR/bin"
    if [ ! -f "$pip_dir/pip" ]; then
        log "Pip not found in expected location, installing pip"
        $python_bin -m ensurepip --upgrade
    fi

    # Install vdf package
    log "Installing vdf Python package..."
    if ! $python_bin -m pip install vdf; then
        log "Failed to install vdf Python package"
        return 1
    fi

    log "vdf Python package installed successfully"
    return 0
}

# Check if vdf is installed
check_vdf_installed() {
    log "Checking if vdf Python package is installed"

    # Get the portable Python binary
    local python_bin=$(get_portable_python)
    if [ $? -ne 0 ]; then
        return 1
    fi

    # Check if the vdf package is installed
    if ! $python_bin -c "import vdf" 2>/dev/null; then
        log "vdf Python package is not installed"
        return 1
    fi

    log "vdf Python package is already installed"
    return 0
}

# Add to Steam (using main NaK's approach)
add_game_to_steam() {
    local game_name="$1"
    local exe_path="$2"
    local start_dir="${3:-$(dirname "$exe_path")}"

    log "Adding $game_name to Steam"

    # Check if vdf is installed, install if needed
    if ! check_vdf_installed; then
        "$GUM_BINARY" spin --spinner dot --title "Installing Python VDF module..." -- install_vdf_package
        if [ $? -ne 0 ]; then
            "$GUM_BINARY" style --foreground 196 "Failed to install VDF module"
            return 1
        fi
    fi

    # Get the Python binary
    local python_bin=$(get_portable_python)
    if [ $? -ne 0 ]; then
        "$GUM_BINARY" style --foreground 196 "Failed to set up Python"
        return 1
    fi

    # Create Python script (from main NaK)
    local temp_script=$(mktemp)
    cat > "$temp_script" << 'EOF'
import sys
import os
import vdf
import time

# Command line arguments
steam_root = sys.argv[1]
game_name = sys.argv[2]
exe_path = sys.argv[3]
start_dir = sys.argv[4]

# Define the path to the shortcuts.vdf file
shortcuts_path = os.path.join(steam_root, "userdata")

# Check if userdata directory exists
if not os.path.exists(shortcuts_path):
    print(f"Error: userdata directory not found at {shortcuts_path}")
    sys.exit(1)

# Find user directories
user_dirs = [d for d in os.listdir(shortcuts_path) if os.path.isdir(os.path.join(shortcuts_path, d))]
if not user_dirs:
    print(f"Error: No user directories found in {shortcuts_path}")
    sys.exit(1)

# Generate a unique app ID for the game
def generate_app_id(name, exe):
    return abs(hash(name + exe)) % 1000000000

app_id = generate_app_id(game_name, exe_path)

# Flag to track if we modified any files
modified = False

# Process each user directory
for user_dir in user_dirs:
    shortcuts_file = os.path.join(shortcuts_path, user_dir, "config", "shortcuts.vdf")

    # Check if shortcuts.vdf exists, create directories if needed
    if not os.path.exists(os.path.dirname(shortcuts_file)):
        os.makedirs(os.path.dirname(shortcuts_file), exist_ok=True)

    # Try to load existing shortcuts.vdf if it exists
    data = {"shortcuts": {}}
    if os.path.exists(shortcuts_file):
        try:
            with open(shortcuts_file, 'rb') as f:
                data = vdf.binary_load(f)
                if data is None:
                    data = {"shortcuts": {}}
                elif "shortcuts" not in data:
                    data["shortcuts"] = {}
        except Exception as e:
            print(f"Warning: Could not read {shortcuts_file}: {e}")
            # Create a new file if we can't read the existing one
            data = {"shortcuts": {}}

    # Check if the game is already in the shortcuts
    game_already_added = False
    for idx, shortcut in data["shortcuts"].items():
        if "AppName" in shortcut and shortcut["AppName"] == game_name:
            print(f"Game '{game_name}' is already in shortcuts.vdf for user {user_dir}")
            game_already_added = True
            break

    if game_already_added:
        continue

    # Add the new game
    shortcut_index = len(data["shortcuts"])

    # Create the new shortcut entry
    data["shortcuts"][str(shortcut_index)] = {
        "appid": app_id,
        "AppName": game_name,
        "Exe": f'"{exe_path}"',
        "StartDir": f'"{start_dir}"',
        "icon": "",
        "ShortcutPath": "",
        "LaunchOptions": "",
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "LastPlayTime": int(time.time())
    }

    # Write the updated shortcuts.vdf file
    try:
        with open(shortcuts_file, 'wb') as f:
            vdf.binary_dump(data, f)
        print(f"Added '{game_name}' to shortcuts.vdf for user {user_dir}")
        modified = True
    except Exception as e:
        print(f"Error writing to {shortcuts_file}: {e}")
        continue

if modified:
    print(f"Game '{game_name}' added to Steam with AppID {app_id}")
    print(f"APPID:{app_id}")
    sys.exit(0)
else:
    print("No changes were made to any shortcuts.vdf files")
    sys.exit(1)
EOF

    # Run the Python script
    log "Running VDF editor script to add game to Steam"
    local output
    if ! output=$($python_bin "$temp_script" "$STEAM_ROOT" "$game_name" "$exe_path" "$start_dir" 2>&1); then
        "$GUM_BINARY" style --foreground 196 "Failed to add game to Steam"
        log "Error output: $output"
        rm -f "$temp_script"
        return 1
    fi

    # Extract the appid from the output
    local appid
    appid=$(echo "$output" | grep "APPID:" | cut -d':' -f2)

    if [ -n "$appid" ]; then
        log "Game was added to Steam with AppID: $appid"
        "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" \
            "✓ Added to Steam successfully!" \
            "" \
            "App ID: $appid" \
            "" \
            "Restart Steam and set Proton compatibility."
    else
        log "Game was added but couldn't determine AppID"
        "$GUM_BINARY" style --foreground 99 "Game was added but couldn't determine AppID"
    fi

    rm -f "$temp_script"
    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
    return 0
}

# ===================================================================
# Main Menu
# ===================================================================

show_main_menu() {
    while true; do
        clear
        "$GUM_BINARY" style --foreground 212 --border double --padding "1 2" --bold \
            "$SCRIPT_NAME v$SCRIPT_VERSION"

        local choice=$("$GUM_BINARY" choose \
            --cursor.foreground "#00FF00" \
            --selected.foreground "#FFD700" \
            --selected.bold \
            --height 15 \
            "🎮 Mod Organizer 2 Setup" \
            "🔧 Vortex Setup" \
            "🐧 Limo Setup (Native Linux)" \
            "🏜️  Tale of Two Wastelands" \
            "🛠️  Hoolamike Tools" \
            "🖼️  Sky Texture Optimizer" \
            "🎯 Game-Specific Fixes" \
            "🗑️  Remove NXM Handlers" \
            "⚙️  Settings" \
            "❌ Exit")

        case "$choice" in
            "🎮 Mod Organizer 2 Setup") mo2_menu ;;
            "🔧 Vortex Setup") vortex_menu ;;
            "🐧 Limo Setup"*) limo_menu ;;
            "🏜️  Tale of Two Wastelands") ttw_menu ;;
            "🛠️  Hoolamike Tools") hoolamike_menu ;;
            "🖼️  Sky Texture Optimizer") sky_tex_menu ;;
            "🎯 Game-Specific Fixes") game_fixes_menu ;;
            "🗑️  Remove NXM Handlers") remove_nxm_handlers ;;
            "⚙️  Settings") settings_menu ;;
            "❌ Exit"|"")
                "$GUM_BINARY" style --foreground 46 "Thanks for using NaK!"
                exit 0
                ;;
        esac
    done
}

# ===================================================================
# MO2 Functions
# ===================================================================

mo2_menu() {
    while true; do
        clear
        "$GUM_BINARY" style --foreground 212 --border normal --padding "1 2" \
            "Mod Organizer 2 Setup"

        local choice=$("$GUM_BINARY" choose \
            --height 10 \
            "📥 Download Latest MO2" \
            "📁 Setup Existing MO2" \
            "💉 Install Dependencies" \
            "🔗 Configure NXM Handler" \
            "🖥️  Configure DPI Scaling" \
            "⬅️  Back to Main Menu")

        case "$choice" in
            "📥 Download Latest MO2") download_mo2 ;;
            "📁 Setup Existing MO2") setup_existing_mo2 ;;
            "💉 Install Dependencies") select_game && install_dependencies ;;
            "🔗 Configure NXM Handler") select_game && setup_nxm_handler ;;
            "🖥️  Configure DPI Scaling") select_game && setup_dpi_scaling ;;
            "⬅️  Back"*|"") return ;;
        esac
    done
}

# Download MO2 with progress
download_mo2() {
    log "Starting MO2 download"

    # Get installation directory
    "$GUM_BINARY" style --foreground 99 "Enter installation directory:"
    local install_dir=$("$GUM_BINARY" input --placeholder "$HOME/ModOrganizer2" --value "$HOME/ModOrganizer2")
    [[ -z "$install_dir" ]] && install_dir="$HOME/ModOrganizer2"

    # Expand tilde
    install_dir="${install_dir/#\~/$HOME}"

    # Check if exists
    if [[ -d "$install_dir" ]]; then
        if "$GUM_BINARY" confirm "Directory exists. Overwrite?"; then
            rm -rf "$install_dir"
        else
            return
        fi
    fi

    # Fetch release info
    local release_info
    release_info=$("$GUM_BINARY" spin --spinner dot --title "Fetching latest release info..." --show-output -- \
        curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^Mod\\.Organizer-[0-9.]+\\.7z$")) | .browser_download_url')

    if [[ -z "$download_url" ]]; then
        "$GUM_BINARY" style --foreground 196 "Could not find MO2 download URL!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return 1
    fi

    "$GUM_BINARY" style --foreground 46 "Found MO2 version: $version"

    # Download
    local filename="MO2-$version.7z"
    local archive_path="$TEMP_DIR/$filename"

    "$GUM_BINARY" spin --spinner dot --title "Downloading MO2 v$version..." -- \
        curl -L -o "$archive_path" "$download_url"

    # Extract
    mkdir -p "$install_dir"

    "$GUM_BINARY" spin --spinner dot --title "Extracting MO2..." -- \
        7z x "$archive_path" -o"$install_dir" -y

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" \
        "✓ MO2 v$version installed successfully!" \
        "" \
        "Location: $install_dir"

    # Add to Steam?
    if "$GUM_BINARY" confirm "Add MO2 to Steam?"; then
        add_game_to_steam "Mod Organizer 2" "$install_dir/ModOrganizer.exe" "$install_dir"
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Setup existing MO2
setup_existing_mo2() {
    "$GUM_BINARY" style --foreground 99 "Enter path to MO2 directory:"
    local mo2_dir=$("$GUM_BINARY" input --placeholder "e.g., /home/user/ModOrganizer2")
    [[ -z "$mo2_dir" ]] && return

    # Expand tilde
    mo2_dir="${mo2_dir/#\~/$HOME}"

    if [[ ! -f "$mo2_dir/ModOrganizer.exe" ]]; then
        "$GUM_BINARY" style --foreground 196 "ModOrganizer.exe not found in that directory!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    "$GUM_BINARY" style --foreground 46 --border normal --padding "1 2" \
        "Found MO2 at:" \
        "$mo2_dir"

    if "$GUM_BINARY" confirm "Add this MO2 to Steam?"; then
        add_game_to_steam "Mod Organizer 2" "$mo2_dir/ModOrganizer.exe" "$mo2_dir"
    fi
}

# ===================================================================
# Vortex Functions
# ===================================================================

vortex_menu() {
    while true; do
        clear
        "$GUM_BINARY" style --foreground 212 --border normal --padding "1 2" \
            "Vortex Setup"

        local choice=$("$GUM_BINARY" choose \
            --height 10 \
            "📥 Download Latest Vortex" \
            "📁 Setup Existing Vortex" \
            "💉 Install Dependencies" \
            "🔗 Configure NXM Handler" \
            "🖥️  Configure DPI Scaling" \
            "⬅️  Back to Main Menu")

        case "$choice" in
            "📥 Download Latest Vortex") download_vortex ;;
            "📁 Setup Existing Vortex") setup_existing_vortex ;;
            "💉 Install Dependencies") select_game && install_dependencies ;;
            "🔗 Configure NXM Handler") select_game && setup_vortex_nxm_handler ;;
            "🖥️  Configure DPI Scaling") select_game && setup_dpi_scaling ;;
            "⬅️  Back"*|"") return ;;
        esac
    done
}

# Download Vortex
download_vortex() {
    log "Starting Vortex download"

    # Fetch release info
    local release_info
    release_info=$("$GUM_BINARY" spin --spinner dot --title "Fetching latest release info..." --show-output -- \
        curl -s https://api.github.com/repos/Nexus-Mods/Vortex/releases/latest)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^vortex-setup-[0-9.]+\\.exe$")) | .browser_download_url')

    if [[ -z "$download_url" ]]; then
        "$GUM_BINARY" style --foreground 196 "Could not find Vortex download URL!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return 1
    fi

    "$GUM_BINARY" style --foreground 46 "Found Vortex version: $version"

    # Get installation directory
    "$GUM_BINARY" style --foreground 99 "Enter installation directory:"
    local install_dir=$("$GUM_BINARY" input --placeholder "$HOME/Vortex" --value "$HOME/Vortex")
    [[ -z "$install_dir" ]] && install_dir="$HOME/Vortex"

    # Expand tilde
    install_dir="${install_dir/#\~/$HOME}"

    # Create directory
    mkdir -p "$install_dir"

    # Download installer
    local installer="$TEMP_DIR/vortex-setup.exe"
    "$GUM_BINARY" spin --spinner dot --title "Downloading Vortex v$version..." -- \
        curl -L -o "$installer" "$download_url"

    # Install with Wine or Proton
    if command -v wine &> /dev/null; then
        "$GUM_BINARY" style --foreground 99 "Installing with system Wine..."
        WINEPREFIX="$HOME/.wine" wine "$installer" /S "/D=Z:$(echo "$install_dir" | sed 's|/|\\|g')"
    else
        # Use Proton
        if select_game; then
            local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
            "$GUM_BINARY" style --foreground 99 "Installing with Proton..."
            run_with_proton_wine "$prefix_path" "$installer" "/S" "/D=Z:$(echo "$install_dir" | sed 's|/|\\|g')"
        else
            "$GUM_BINARY" style --foreground 196 "Wine not found and no game selected for Proton!"
            "$GUM_BINARY" input --placeholder "Press Enter to continue..."
            return 1
        fi
    fi

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" \
        "✓ Vortex v$version installed!" \
        "" \
        "Location: $install_dir"

    if "$GUM_BINARY" confirm "Add Vortex to Steam?"; then
        add_game_to_steam "Vortex" "$install_dir/Vortex.exe" "$install_dir"
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Setup existing Vortex
setup_existing_vortex() {
    "$GUM_BINARY" style --foreground 99 "Enter path to Vortex directory:"
    local vortex_dir=$("$GUM_BINARY" input --placeholder "e.g., /home/user/Vortex")
    [[ -z "$vortex_dir" ]] && return

    # Expand tilde
    vortex_dir="${vortex_dir/#\~/$HOME}"

    if [[ ! -f "$vortex_dir/Vortex.exe" ]]; then
        "$GUM_BINARY" style --foreground 196 "Vortex.exe not found in that directory!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    "$GUM_BINARY" style --foreground 46 --border normal --padding "1 2" \
        "Found Vortex at:" \
        "$vortex_dir"

    if "$GUM_BINARY" confirm "Add this Vortex to Steam?"; then
        add_game_to_steam "Vortex" "$vortex_dir/Vortex.exe" "$vortex_dir"
    fi
}

# Setup Vortex NXM handler
setup_vortex_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    "$GUM_BINARY" style --border normal --padding "1 2" \
        "Setting up NXM handler for Vortex" \
        "Using: $SELECTED_GAME"

    "$GUM_BINARY" style --foreground 99 "Enter path to Vortex.exe:"
    local vortex_path=$("$GUM_BINARY" input --placeholder "e.g., /home/user/Vortex/Vortex.exe")
    [[ -z "$vortex_path" ]] && return

    local proton_path=$(find_proton_path)
    local compat_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID"
    local desktop_file="$HOME/.local/share/applications/vortex-nxm-handler.desktop"

    mkdir -p "$(dirname "$desktop_file")"

    cat > "$desktop_file" << EOF
[Desktop Entry]
Type=Application
Categories=Game;
Exec=bash -c 'env "STEAM_COMPAT_CLIENT_INSTALL_PATH=$STEAM_ROOT" "STEAM_COMPAT_DATA_PATH=$compat_path" "$proton_path" run "$vortex_path" -d "%u"'
Name=Vortex NXM Handler
MimeType=x-scheme-handler/nxm;x-scheme-handler/nxm-protocol;
NoDisplay=true
EOF

    chmod +x "$desktop_file"
    xdg-mime default vortex-nxm-handler.desktop x-scheme-handler/nxm
    xdg-mime default vortex-nxm-handler.desktop x-scheme-handler/nxm-protocol
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" \
        "✓ Vortex NXM handler configured!"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Limo Functions
# ===================================================================

limo_menu() {
    "$GUM_BINARY" style --border normal --padding "1 2" \
        "Limo Setup" \
        "" \
        "Limo is a Linux-native mod manager" \
        "This will install dependencies for your game prefixes"

    if "$GUM_BINARY" confirm "Configure a game for Limo?"; then
        configure_games_for_limo
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Configure games for Limo
configure_games_for_limo() {
    if select_game; then
        install_dependencies

        local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
        "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" \
            "✓ Dependencies installed for $SELECTED_GAME" \
            "" \
            "Prefix path:" \
            "$prefix_path"

        if "$GUM_BINARY" confirm "Configure another game for Limo?"; then
            configure_games_for_limo
        fi
    fi
}

# ===================================================================
# Dependencies Installation
# ===================================================================

install_dependencies() {
    [[ -z "$SELECTED_GAME" ]] && return

    # Get components based on game
    get_game_components "$SELECTED_APPID"

    "$GUM_BINARY" style --border normal --padding "1 2" \
        "Installing dependencies for:" \
        "$SELECTED_GAME" \
        "" \
        "Components: ${#components[@]}"

    "$GUM_BINARY" confirm "Install dependencies?" || return

    # Install each component
    for comp in "${components[@]}"; do
        "$GUM_BINARY" spin --spinner dot --title "Installing $comp..." -- \
            $PROTONTRICKS_CMD --no-bwrap "$SELECTED_APPID" -q "$comp"
    done

    # Enable dotfiles visibility
    local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
    if [[ -d "$prefix_path" ]]; then
        "$GUM_BINARY" spin --spinner dot --title "Enabling hidden files visibility..." -- \
            run_with_proton_wine "$prefix_path" "reg" "add" "HKCU\\Software\\Wine" "/v" "ShowDotFiles" "/d" "Y" "/f"
    fi

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" \
        "✓ Dependencies installed successfully!"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Get components for specific games
get_game_components() {
    local appid="$1"
    components=()  # Reset array

    case "$appid" in
        22380)  # Fallout New Vegas
            components=(
                fontsmooth=rgb
                xact
                xact_x64
                d3dx9_43
                d3dx9
                vcrun2022
            )
            ;;
        976620)  # Enderal Special Edition
            components=(
                fontsmooth=rgb
                xact
                xact_x64
                d3dx11_43
                d3dcompiler_43
                d3dcompiler_46
                d3dcompiler_47
                vcrun2022
                dotnet6
                dotnet7
                dotnet8
                winhttp
            )
            ;;
        *)  # Default for all other games
            components=(
                fontsmooth=rgb
                xact
                xact_x64
                vcrun2022
                dotnet6
                dotnet7
                dotnet8
                d3dcompiler_47
                d3dx11_43
                d3dcompiler_43
                d3dx9_43
                d3dx9
                vkd3d
            )
            ;;
    esac
}

# ===================================================================
# Game-Specific Fixes
# ===================================================================

game_fixes_menu() {
    while true; do
        clear
        "$GUM_BINARY" style --foreground 212 --border normal --padding "1 2" \
            "Game-Specific Fixes"

        local choice=$("$GUM_BINARY" choose \
            --height 10 \
            "🏜️  Fallout New Vegas" \
            "🏔️  Enderal Special Edition" \
            "🎲 Baldur's Gate 3" \
            "📋 All Games Advice" \
            "⬅️  Back to Main Menu")

        case "$choice" in
            "🏜️  Fallout New Vegas") fnv_fixes ;;
            "🏔️  Enderal Special Edition") enderal_fixes ;;
            "🎲 Baldur's Gate 3") bg3_fixes ;;
            "📋 All Games Advice") show_all_advice ;;
            "⬅️  Back"*|"") return ;;
        esac
    done
}

# Fallout New Vegas fixes
fnv_fixes() {
    SELECTED_APPID="22380"
    SELECTED_GAME="Fallout New Vegas"

    local compatdata=$(find_game_compatdata "$SELECTED_APPID")

    if [[ -n "$compatdata" ]]; then
        "$GUM_BINARY" style --border double --padding "1 2" \
            "Fallout New Vegas Launch Options:" \
            "" \
            "STEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%"

        local choice=$("$GUM_BINARY" choose \
            "💉 Install Dependencies" \
            "🔗 Configure NXM Handler" \
            "🖥️  Configure DPI Scaling" \
            "⬅️  Back")

        case "$choice" in
            "💉 Install Dependencies")
                get_game_components "$SELECTED_APPID"
                install_dependencies
                ;;
            "🔗 Configure NXM Handler") setup_nxm_handler ;;
            "🖥️  Configure DPI Scaling") setup_dpi_scaling ;;
        esac
    else
        "$GUM_BINARY" style --foreground 196 \
            "Fallout New Vegas not found or not run yet!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
    fi
}

# Enderal fixes
enderal_fixes() {
    SELECTED_APPID="976620"
    SELECTED_GAME="Enderal Special Edition"

    local compatdata=$(find_game_compatdata "$SELECTED_APPID")

    if [[ -n "$compatdata" ]]; then
        "$GUM_BINARY" style --border double --padding "1 2" \
            "Enderal SE Launch Options:" \
            "" \
            "STEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%"

        local choice=$("$GUM_BINARY" choose \
            "💉 Install Dependencies" \
            "🔗 Configure NXM Handler" \
            "🖥️  Configure DPI Scaling" \
            "⬅️  Back")

        case "$choice" in
            "💉 Install Dependencies")
                get_game_components "$SELECTED_APPID"
                install_dependencies
                ;;
            "🔗 Configure NXM Handler") setup_nxm_handler ;;
            "🖥️  Configure DPI Scaling") setup_dpi_scaling ;;
        esac
    else
        "$GUM_BINARY" style --foreground 196 \
            "Enderal SE not found or not run yet!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
    fi
}

# BG3 fixes
bg3_fixes() {
    local compatdata=$(find_game_compatdata "1086940")

    if [[ -n "$compatdata" ]]; then
        "$GUM_BINARY" style --border double --padding "1 2" \
            "Baldur's Gate 3 Launch Options:" \
            "" \
            "WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%"
    else
        "$GUM_BINARY" style --foreground 196 \
            "Baldur's Gate 3 not found or not run yet!"
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# NXM Handler Setup
# ===================================================================

setup_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    "$GUM_BINARY" style --border normal --padding "1 2" \
        "Setting up NXM handler for:" \
        "$SELECTED_GAME"

    "$GUM_BINARY" style --foreground 99 "Enter path to nxmhandler.exe:"
    local handler_path=$("$GUM_BINARY" input --placeholder "e.g., /path/to/MO2/nxmhandler.exe")
    [[ -z "$handler_path" ]] && return

    local proton_path=$(find_proton_path)
    local compat_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID"
    local desktop_file="$HOME/.local/share/applications/mo2-nxm-handler.desktop"

    mkdir -p "$(dirname "$desktop_file")"

    cat > "$desktop_file" << EOF
[Desktop Entry]
Type=Application
Categories=Game;
Exec=bash -c 'env "STEAM_COMPAT_CLIENT_INSTALL_PATH=$STEAM_ROOT" "STEAM_COMPAT_DATA_PATH=$compat_path" "$proton_path" run "$handler_path" "%u"'
Name=MO2 NXM Handler
MimeType=x-scheme-handler/nxm;
NoDisplay=true
EOF

    chmod +x "$desktop_file"
    xdg-mime default mo2-nxm-handler.desktop x-scheme-handler/nxm
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" \
        "✓ NXM handler configured successfully!"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# DPI Scaling Setup
# ===================================================================

setup_dpi_scaling() {
    [[ -z "$SELECTED_GAME" ]] && return

    local scale=$("$GUM_BINARY" choose \
        "96 - Standard (100%)" \
        "120 - Medium (125%)" \
        "144 - Large (150%)" \
        "192 - Extra Large (200%)" \
        "Custom")

    case "$scale" in
        "96 -"*) scale=96 ;;
        "120 -"*) scale=120 ;;
        "144 -"*) scale=144 ;;
        "192 -"*) scale=192 ;;
        "Custom")
            scale=$("$GUM_BINARY" input --placeholder "Enter DPI value (96-240)" --value "120")
            ;;
        *) return ;;
    esac

    local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"

    "$GUM_BINARY" spin --spinner dot --title "Applying DPI scaling..." -- bash -c "
        run_with_proton_wine '$prefix_path' reg add 'HKCU\\Control Panel\\Desktop' /v LogPixels /t REG_DWORD /d $scale /f
        run_with_proton_wine '$prefix_path' reg add 'HKCU\\Software\\Wine\\X11 Driver' /v LogPixels /t REG_DWORD /d $scale /f
    "

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" \
        "✓ DPI scaling set to $scale" \
        "" \
        "Restart the application for changes to take effect"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Helper Functions
# ===================================================================

# Find game compatdata
find_game_compatdata() {
    local appid="$1"
    local paths=("$STEAM_ROOT")

    # Check library folders
    local libraryfolders="$STEAM_ROOT/steamapps/libraryfolders.vdf"
    if [[ -f "$libraryfolders" ]]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    # Search for compatdata
    for path in "${paths[@]}"; do
        local compatdata="$path/steamapps/compatdata/$appid"
        [[ -d "$compatdata" ]] && echo "$compatdata" && return 0
    done

    return 1
}

# Find Proton path
find_proton_path() {
    find "$STEAM_ROOT" -name "proton" -path "*/Proton - Experimental/*" 2>/dev/null | head -1
}

# Run with Proton Wine
run_with_proton_wine() {
    local prefix_path="$1"
    local command="$2"
    shift 2

    local proton_path=$(find_proton_path)

    env STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
        STEAM_COMPAT_DATA_PATH="$(dirname "$prefix_path")" \
        "$proton_path" run "$command" "$@"
}

# Show all game advice
show_all_advice() {
    local advice=""

    # Check each game
    local fnv_compat=$(find_game_compatdata "22380")
    [[ -n "$fnv_compat" ]] && advice+="Fallout New Vegas:
STEAM_COMPAT_DATA_PATH=\"$fnv_compat\" %command%

"

    local enderal_compat=$(find_game_compatdata "976620")
    [[ -n "$enderal_compat" ]] && advice+="Enderal SE:
STEAM_COMPAT_DATA_PATH=\"$enderal_compat\" %command%

"

    local bg3_compat=$(find_game_compatdata "1086940")
    [[ -n "$bg3_compat" ]] && advice+="Baldur's Gate 3:
WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%

"

    if [[ -z "$advice" ]]; then
        advice="No games detected. Run the games at least once through Steam."
    fi

    "$GUM_BINARY" style --border double --padding "1 2" \
        "Game-Specific Launch Options" \
        "" \
        "$advice"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Placeholder functions (to be implemented)
# ===================================================================

ttw_menu() {
    "$GUM_BINARY" style --foreground 99 "TTW setup coming soon!"
    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

hoolamike_menu() {
    "$GUM_BINARY" style --foreground 99 "Hoolamike tools coming soon!"
    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

sky_tex_menu() {
    "$GUM_BINARY" style --foreground 99 "Sky Texture Optimizer coming soon!"
    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

settings_menu() {
    "$GUM_BINARY" style --foreground 99 "Settings menu coming soon!"
    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

remove_nxm_handlers() {
    local handlers=(
        "$HOME/.local/share/applications/mo2-nxm-handler.desktop"
        "$HOME/.local/share/applications/vortex-nxm-handler.desktop"
        "$HOME/.local/share/applications/modorganizer2-nxm-handler.desktop"
    )

    local found=0
    for handler in "${handlers[@]}"; do
        [[ -f "$handler" ]] && rm -f "$handler" && ((found++))
    done

    if [[ $found -gt 0 ]]; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null
        "$GUM_BINARY" style --foreground 46 "✓ Removed $found NXM handler(s)"
    else
        "$GUM_BINARY" style --foreground 99 "No NXM handlers found"
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
