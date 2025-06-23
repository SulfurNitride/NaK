#!/bin/bash
# ===================================================================
# NaK (Linux Modding Helper) - Whiptail Edition
# Version: 2.0.2 - Fixed for spaces in paths
# ===================================================================

# Script metadata
readonly SCRIPT_VERSION="2.0.2"
readonly SCRIPT_NAME="NaK - Linux Modding Helper"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Portable Python setup - QUOTED PROPERLY
PORTABLE_PYTHON_URL="https://github.com/bjia56/portable-python/releases/download/cpython-v3.13.1-build.3/python-full-3.13.1-linux-x86_64.zip"
PORTABLE_PYTHON_DIR="$SCRIPT_DIR/lib/portable_python"
PORTABLE_PYTHON_ZIP="$PORTABLE_PYTHON_DIR/python-full.zip"
PORTABLE_PYTHON_EXTRACT_DIR="$PORTABLE_PYTHON_DIR/python-full-3.13.1-linux-x86_64"
PORTABLE_PYTHON_BINARY="$PORTABLE_PYTHON_EXTRACT_DIR/bin/python3"

# Colors for terminal output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# ===================================================================
# Core Functions
# ===================================================================

# Initialize
init() {
    # Create directories
    mkdir -p "$CONFIG_DIR" "$TEMP_DIR" "$SCRIPT_DIR/lib"

    # Setup logging
    exec 2> >(tee -a "$LOG_FILE")
    echo "[$(date)] Starting $SCRIPT_NAME v$SCRIPT_VERSION" >> "$LOG_FILE"

    # Check dependencies
    check_dependencies

    # Find Steam
    STEAM_ROOT=$(find_steam_root)

    # Load config
    load_config

    # Trap cleanup
    trap cleanup EXIT INT TERM
}

# Cleanup
cleanup() {
    rm -rf "$TEMP_DIR"
    echo "[$(date)] Cleanup completed" >> "$LOG_FILE"
}

# Check dependencies
check_dependencies() {
    local missing=()

    # Check for whiptail
    if ! command -v whiptail &> /dev/null; then
        echo -e "${RED}Error: whiptail is not installed${NC}"
        echo "Install with: sudo apt install whiptail"
        exit 1
    fi

    # Check protontricks
    if command -v protontricks &> /dev/null; then
        PROTONTRICKS_CMD="protontricks"
    elif flatpak list --app 2>/dev/null | grep -q "com.github.Matoking.protontricks"; then
        PROTONTRICKS_CMD="flatpak run com.github.Matoking.protontricks"
    else
        missing+=("protontricks")
    fi

    # Check other deps
    for cmd in curl jq unzip; do
        command -v "$cmd" &> /dev/null || missing+=("$cmd")
    done

    # Check for 7z
    local has_7z=false
    for variant in 7z 7za 7zr p7zip; do
        if command -v "$variant" &> /dev/null; then
            has_7z=true
            break
        fi
    done
    [[ "$has_7z" == "false" ]] && missing+=("p7zip-full")

    if [[ ${#missing[@]} -gt 0 ]]; then
        whiptail --title "Missing Dependencies" --msgbox \
            "Please install: ${missing[*]}\n\nExample:\nsudo apt install ${missing[*]}" 10 60
        exit 1
    fi
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

    whiptail --title "Error" --msgbox "Steam installation not found!" 8 50
    exit 1
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        # Clean the config file first
        local temp_config=$(mktemp)
        grep -E '^[A-Z_]+=' "$CONFIG_FILE" > "$temp_config" 2>/dev/null || true
        mv "$temp_config" "$CONFIG_FILE"

        # Source cleaned config
        source "$CONFIG_FILE" 2>/dev/null || {
            echo "[$(date)] Config file corrupted, recreating" >> "$LOG_FILE"
            rm -f "$CONFIG_FILE"
            create_default_config
        }
    else
        create_default_config
    fi
}

# Create default config
create_default_config() {
    cat > "$CONFIG_FILE" << EOF
# NaK Configuration
DEFAULT_SCALING=96
SHOW_ADVANCED=false
CHECK_UPDATES=true
EOF
}

# Save configuration
save_config() {
    local key="$1"
    local value="$2"

    # Escape special characters
    value="${value//\"/\\\"}"

    if grep -q "^$key=" "$CONFIG_FILE" 2>/dev/null; then
        sed -i "s/^$key=.*/$key=\"$value\"/" "$CONFIG_FILE"
    else
        echo "$key=\"$value\"" >> "$CONFIG_FILE"
    fi
}

# Setup portable Python - FIXED FOR SPACES
setup_portable_python() {
    echo "[$(date)] Setting up portable Python" >> "$LOG_FILE"

    # Create directory
    mkdir -p "$PORTABLE_PYTHON_DIR"

    # Check if already exists
    if [[ -f "$PORTABLE_PYTHON_BINARY" ]] && [[ -x "$PORTABLE_PYTHON_BINARY" ]]; then
        echo "[$(date)] Python already installed" >> "$LOG_FILE"
        return 0
    fi

    # Download
    echo "Downloading Python..."
    if command -v curl &>/dev/null; then
        curl -L -o "$PORTABLE_PYTHON_ZIP" "$PORTABLE_PYTHON_URL" 2>&1 | tee -a "$LOG_FILE"
    elif command -v wget &>/dev/null; then
        wget -O "$PORTABLE_PYTHON_ZIP" "$PORTABLE_PYTHON_URL" 2>&1 | tee -a "$LOG_FILE"
    else
        echo "[$(date)] No download tool available" >> "$LOG_FILE"
        return 1
    fi

    # Extract
    echo "Extracting Python..."
    unzip -o "$PORTABLE_PYTHON_ZIP" -d "$PORTABLE_PYTHON_DIR" 2>&1 | tee -a "$LOG_FILE"

    # Make executable
    chmod +x "$PORTABLE_PYTHON_BINARY"

    # Cleanup
    rm -f "$PORTABLE_PYTHON_ZIP"

    # Verify
    if [[ -x "$PORTABLE_PYTHON_BINARY" ]]; then
        echo "[$(date)] Python setup complete" >> "$LOG_FILE"
        return 0
    else
        echo "[$(date)] Python setup failed" >> "$LOG_FILE"
        return 1
    fi
}

# Get portable Python - ALWAYS QUOTE
get_portable_python() {
    if [[ ! -f "$PORTABLE_PYTHON_BINARY" ]] || [[ ! -x "$PORTABLE_PYTHON_BINARY" ]]; then
        setup_portable_python || return 1
    fi
    echo "$PORTABLE_PYTHON_BINARY"
    return 0
}

# ===================================================================
# VDF Functions - FIXED FOR SPACES
# ===================================================================

# Install VDF package - PROPERLY QUOTED
install_vdf_package() {
    echo "[$(date)] Installing VDF package" >> "$LOG_FILE"

    local python_bin="$(get_portable_python)"
    if [[ $? -ne 0 ]]; then
        echo "[$(date)] Failed to get Python" >> "$LOG_FILE"
        return 1
    fi

    # Install pip if needed - QUOTED
    if [[ ! -f "$PORTABLE_PYTHON_EXTRACT_DIR/bin/pip" ]]; then
        echo "[$(date)] Installing pip" >> "$LOG_FILE"
        "$python_bin" -m ensurepip --upgrade 2>&1 | tee -a "$LOG_FILE"
    fi

    # Install vdf - QUOTED
    echo "[$(date)] Installing vdf module" >> "$LOG_FILE"
    "$python_bin" -m pip install vdf 2>&1 | tee -a "$LOG_FILE"

    # Verify installation - QUOTED
    if "$python_bin" -c "import vdf" 2>/dev/null; then
        echo "[$(date)] VDF installed successfully" >> "$LOG_FILE"
        return 0
    else
        echo "[$(date)] VDF installation failed" >> "$LOG_FILE"
        return 1
    fi
}

# Check VDF installed - QUOTED
check_vdf_installed() {
    local python_bin="$(get_portable_python)"
    [[ $? -ne 0 ]] && return 1

    "$python_bin" -c "import vdf" 2>/dev/null
}

# ===================================================================
# Add to Steam - FIXED FOR SPACES
# ===================================================================

add_game_to_steam() {
    local game_name="$1"
    local exe_path="$2"
    local start_dir="${3:-$(dirname "$exe_path")}"

    # Setup Python and VDF with progress
    (
        echo "10"
        echo "# Setting up Python environment..."

        local python_bin="$(get_portable_python)"
        if [[ $? -ne 0 ]]; then
            echo "100"
            whiptail --title "Error" --msgbox "Failed to setup Python environment!" 8 50
            return 1
        fi

        echo "50"
        echo "# Installing required modules..."

        if ! check_vdf_installed; then
            install_vdf_package >/dev/null 2>&1
        fi

        echo "100"
        echo "# Ready to add to Steam..."
    ) | whiptail --gauge "Preparing Steam integration..." 8 60 0

    local python_bin="$(get_portable_python)"
    if [[ $? -ne 0 ]]; then
        whiptail --title "Error" --msgbox "Python environment not available!" 8 50
        return 1
    fi

    # Create Python script
    local temp_script=$(mktemp)
    cat > "$temp_script" << 'EOF'
import sys
import os
import vdf
import time

steam_root = sys.argv[1]
game_name = sys.argv[2]
exe_path = sys.argv[3]
start_dir = sys.argv[4]

shortcuts_path = os.path.join(steam_root, "userdata")

if not os.path.exists(shortcuts_path):
    print("ERROR: userdata directory not found")
    sys.exit(1)

user_dirs = [d for d in os.listdir(shortcuts_path) if os.path.isdir(os.path.join(shortcuts_path, d))]
if not user_dirs:
    print("ERROR: No user directories found")
    sys.exit(1)

def generate_app_id(name, exe):
    return abs(hash(name + exe)) % 1000000000

app_id = generate_app_id(game_name, exe_path)
modified = False

for user_dir in user_dirs:
    shortcuts_file = os.path.join(shortcuts_path, user_dir, "config", "shortcuts.vdf")

    if not os.path.exists(os.path.dirname(shortcuts_file)):
        os.makedirs(os.path.dirname(shortcuts_file), exist_ok=True)

    data = {"shortcuts": {}}
    if os.path.exists(shortcuts_file):
        try:
            with open(shortcuts_file, 'rb') as f:
                loaded_data = vdf.binary_load(f)
                if loaded_data and "shortcuts" in loaded_data:
                    data = loaded_data
        except Exception as e:
            print(f"Warning: Could not read existing shortcuts: {e}")

    # Check if already exists
    game_already_added = False
    for idx, shortcut in data.get("shortcuts", {}).items():
        if shortcut.get("AppName") == game_name:
            game_already_added = True
            break

    if game_already_added:
        continue

    # Add new shortcut
    shortcut_index = str(len(data.get("shortcuts", {})))

    if "shortcuts" not in data:
        data["shortcuts"] = {}

    data["shortcuts"][shortcut_index] = {
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

    try:
        with open(shortcuts_file, 'wb') as f:
            vdf.binary_dump(data, f)
        modified = True
        print(f"SUCCESS:{app_id}")
    except Exception as e:
        print(f"ERROR: Failed to write shortcuts: {e}")

if not modified:
    print("ERROR: No changes made")
EOF

    # Run the script - PROPERLY QUOTED
    whiptail --infobox "Adding to Steam..." 8 40
    local output=$("$python_bin" "$temp_script" "$STEAM_ROOT" "$game_name" "$exe_path" "$start_dir" 2>&1)
    rm -f "$temp_script"

    echo "[$(date)] Add to Steam output: $output" >> "$LOG_FILE"

    if [[ "$output" == SUCCESS:* ]]; then
        local appid=${output#SUCCESS:}
        whiptail --title "Success" --msgbox \
            "Added to Steam successfully!\n\nApp ID: $appid\n\nRestart Steam and set Proton compatibility." 12 60
        return 0
    else
        local error_msg="Failed to add to Steam!"
        if [[ "$output" == ERROR:* ]]; then
            error_msg="${output#ERROR: }"
        fi
        whiptail --title "Error" --msgbox "$error_msg" 10 60
        return 1
    fi
}

# ===================================================================
# Main Menu
# ===================================================================

show_main_menu() {
    while true; do
        local choice=$(whiptail --title "$SCRIPT_NAME v$SCRIPT_VERSION" \
            --menu "Choose an option:" 20 70 12 \
            "1" "Mod Organizer 2 Setup" \
            "2" "Vortex Setup" \
            "3" "Limo Setup (Native Linux)" \
            "4" "Tale of Two Wastelands" \
            "5" "Hoolamike Tools" \
            "6" "Sky Texture Optimizer" \
            "7" "Game-Specific Fixes" \
            "8" "Remove NXM Handlers" \
            "9" "Settings" \
            "0" "Exit" \
            3>&1 1>&2 2>&3)

        case $choice in
            1) mo2_menu ;;
            2) vortex_menu ;;
            3) limo_menu ;;
            4) ttw_menu ;;
            5) hoolamike_menu ;;
            6) sky_tex_menu ;;
            7) game_fixes_menu ;;
            8) remove_nxm_handlers ;;
            9) settings_menu ;;
            0|"") exit 0 ;;
        esac
    done
}

# ===================================================================
# MO2 Functions
# ===================================================================

mo2_menu() {
    while true; do
        local choice=$(whiptail --title "Mod Organizer 2 Setup" \
            --menu "Choose an option:" 16 60 8 \
            "1" "Download Latest MO2" \
            "2" "Setup Existing MO2" \
            "3" "Install Dependencies" \
            "4" "Configure NXM Handler" \
            "5" "Configure DPI Scaling" \
            "B" "Back to Main Menu" \
            3>&1 1>&2 2>&3)

        case $choice in
            1) download_mo2 ;;
            2) setup_existing_mo2 ;;
            3) select_game && install_dependencies ;;
            4) select_game && setup_nxm_handler ;;
            5) select_game && setup_dpi_scaling ;;
            B|"") return ;;
        esac
    done
}

# Download MO2 with proper progress
download_mo2() {
    local install_dir=$(whiptail --inputbox "Installation directory:" 8 60 "$HOME/ModOrganizer2" 3>&1 1>&2 2>&3)
    [[ -z "$install_dir" ]] && return

    # Expand tilde
    install_dir="${install_dir/#\~/$HOME}"

    if [[ -d "$install_dir" ]]; then
        if ! whiptail --yesno "Directory exists. Overwrite?" 8 50; then
            return
        fi
        rm -rf "$install_dir"
    fi

    mkdir -p "$install_dir"

    # Get release info
    whiptail --infobox "Fetching latest release info..." 8 40
    local release_info=$(curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^Mod\\.Organizer-[0-9.]+\\.7z$")) | .browser_download_url')

    if [[ -z "$download_url" ]] || [[ "$download_url" == "null" ]]; then
        whiptail --title "Error" --msgbox "Could not find MO2 download URL!" 8 50
        return 1
    fi

    # Download with progress
    local archive="$TEMP_DIR/MO2-$version.7z"

    # Use curl with progress callback
    (
        curl -L -o "$archive" "$download_url" 2>&1 | \
        grep --line-buffered "%" | \
        sed -u -e "s,.*\([0-9]\+\)%.*,\1," | \
        whiptail --gauge "Downloading MO2 v$version..." 8 70 0
    )

    # Extract
    whiptail --infobox "Extracting MO2..." 8 40

    # Find 7z command
    local extract_cmd=""
    for cmd in 7z 7za 7zr; do
        if command -v "$cmd" &>/dev/null; then
            extract_cmd="$cmd"
            break
        fi
    done

    if [[ -z "$extract_cmd" ]]; then
        whiptail --title "Error" --msgbox "7-Zip not found! Install with: sudo apt install p7zip-full" 8 60
        return 1
    fi

    # Extract to install directory
    $extract_cmd x "$archive" -o"$install_dir" -y >/dev/null 2>&1

    # Verify installation
    if [[ -f "$install_dir/ModOrganizer.exe" ]]; then
        whiptail --title "Success" --msgbox "MO2 v$version installed to:\n$install_dir" 10 60

        if whiptail --yesno "Add MO2 to Steam?" 8 50; then
            add_game_to_steam "Mod Organizer 2" "$install_dir/ModOrganizer.exe" "$install_dir"
        fi
    else
        whiptail --title "Error" --msgbox "Installation failed! ModOrganizer.exe not found." 8 50
    fi

    # Cleanup
    rm -f "$archive"
}

# ===================================================================
# Game Selection
# ===================================================================

get_steam_games() {
    local games=()
    local output=$($PROTONTRICKS_CMD -l 2>&1)
    local collecting=false

    while IFS= read -r line; do
        if [[ "$line" == "Found the following games:"* ]]; then
            collecting=true
            continue
        fi

        if [[ "$line" == "To run Protontricks"* ]]; then
            break
        fi

        if [[ "$collecting" == true ]]; then
            if [[ "$line" =~ ^[[:space:]]*(.+)[[:space:]]\(([0-9]+)\)[[:space:]]*$ ]]; then
                local name="${BASH_REMATCH[1]}"
                local appid="${BASH_REMATCH[2]}"

                name=$(echo "$name" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

                if [[ "$name" =~ ^Non-Steam[[:space:]]shortcut:[[:space:]](.+)$ ]]; then
                    name="${BASH_REMATCH[1]}"
                fi

                if [[ ! "$name" =~ (SteamVR|Proton|Steam Linux Runtime) ]]; then
                    games+=("$appid" "$name")
                fi
            fi
        fi
    done <<< "$output"

    printf '%s\n' "${games[@]}"
}

select_game() {
    whiptail --infobox "Fetching game list..." 8 40
    local games=($(get_steam_games))

    if [[ ${#games[@]} -eq 0 ]]; then
        whiptail --title "Error" --msgbox "No games found!" 8 50
        return 1
    fi

    local choice=$(whiptail --title "Select Game" \
        --menu "Choose a game:" 20 70 12 \
        "${games[@]}" \
        3>&1 1>&2 2>&3)

    if [[ -n "$choice" ]]; then
        SELECTED_APPID="$choice"
        for ((i=0; i<${#games[@]}; i+=2)); do
            if [[ "${games[i]}" == "$choice" ]]; then
                SELECTED_GAME="${games[i+1]}"
                break
            fi
        done
        return 0
    fi
    return 1
}

# ===================================================================
# Other menu functions (placeholders)
# ===================================================================

setup_existing_mo2() {
    local mo2_dir=$(whiptail --inputbox "Path to MO2 directory:" 10 60 3>&1 1>&2 2>&3)
    [[ -z "$mo2_dir" ]] && return

    mo2_dir="${mo2_dir/#\~/$HOME}"

    if [[ ! -f "$mo2_dir/ModOrganizer.exe" ]]; then
        whiptail --title "Error" --msgbox "ModOrganizer.exe not found!" 8 50
        return
    fi

    whiptail --title "Success" --msgbox "Found MO2 at:\n$mo2_dir" 8 60

    if whiptail --yesno "Add to Steam?" 8 50; then
        add_game_to_steam "Mod Organizer 2" "$mo2_dir/ModOrganizer.exe" "$mo2_dir"
    fi
}

install_dependencies() {
    whiptail --title "Dependencies" --msgbox "Dependencies installation coming soon!" 8 50
}

setup_nxm_handler() {
    whiptail --title "NXM Handler" --msgbox "NXM handler setup coming soon!" 8 50
}

setup_dpi_scaling() {
    whiptail --title "DPI Scaling" --msgbox "DPI scaling setup coming soon!" 8 50
}

vortex_menu() {
    whiptail --title "Vortex" --msgbox "Vortex functionality coming soon!" 8 50
}

limo_menu() {
    whiptail --title "Limo" --msgbox "Limo functionality coming soon!" 8 50
}

ttw_menu() {
    whiptail --title "TTW" --msgbox "TTW functionality coming soon!" 8 50
}

hoolamike_menu() {
    whiptail --title "Hoolamike" --msgbox "Hoolamike functionality coming soon!" 8 50
}

sky_tex_menu() {
    whiptail --title "Sky Texture" --msgbox "Sky Texture Optimizer coming soon!" 8 50
}

game_fixes_menu() {
    whiptail --title "Game Fixes" --msgbox "Game fixes coming soon!" 8 50
}

remove_nxm_handlers() {
    local found=0
    for handler in "$HOME/.local/share/applications"/*nxm-handler.desktop; do
        [[ -f "$handler" ]] && rm -f "$handler" && ((found++))
    done

    if [[ $found -gt 0 ]]; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null
        whiptail --title "Success" --msgbox "Removed $found NXM handler(s)" 8 50
    else
        whiptail --title "Info" --msgbox "No NXM handlers found" 8 50
    fi
}

settings_menu() {
    whiptail --title "Settings" --msgbox "Settings menu coming soon!" 8 50
}

find_proton_path() {
    find "$STEAM_ROOT" -name "proton" -path "*/Proton - Experimental/*" 2>/dev/null | head -1
}

# ===================================================================
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
