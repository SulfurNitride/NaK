#!/bin/bash
# ===================================================================
# NaK (Linux Modding Helper) - Redesigned with Whiptail UI
# Version: 2.0.0
# ===================================================================

# Script metadata
readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_NAME="NaK - Linux Modding Helper"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color definitions for terminal output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

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

# ===================================================================
# Core Functions
# ===================================================================

# Initialize the script
init() {
    # Create necessary directories
    mkdir -p "$CONFIG_DIR" "$TEMP_DIR"

    # Set up logging
    exec 2> >(tee -a "$LOG_FILE")
    echo "[$(date)] Starting $SCRIPT_NAME v$SCRIPT_VERSION" >> "$LOG_FILE"

    # Check dependencies
    check_dependencies

    # Find Steam root
    STEAM_ROOT=$(find_steam_root)

    # Load configuration
    load_config

    # Trap for cleanup
    trap cleanup EXIT INT TERM
}

# Clean up temporary files
cleanup() {
    rm -rf "$TEMP_DIR"
    echo "[$(date)] Cleanup completed" >> "$LOG_FILE"
}

# Check for required dependencies
check_dependencies() {
    local deps=("whiptail" "curl" "jq" "protontricks")
    local missing=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            # Special case for protontricks (can be flatpak)
            if [[ "$dep" == "protontricks" ]] && flatpak list --app 2>/dev/null | grep -q "com.github.Matoking.protontricks"; then
                PROTONTRICKS_CMD="flatpak run com.github.Matoking.protontricks"
                continue
            fi
            missing+=("$dep")
        fi
    done

    # Set protontricks command if not flatpak
    [[ -z "$PROTONTRICKS_CMD" ]] && PROTONTRICKS_CMD="protontricks"

    if [[ ${#missing[@]} -gt 0 ]]; then
        whiptail --title "Missing Dependencies" --msgbox \
            "Please install: ${missing[*]}\n\nExample:\nsudo apt install ${missing[*]}" 10 60
        exit 1
    fi
}

# Find Steam root directory
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
        source "$CONFIG_FILE"
    else
        # Create default config
        cat > "$CONFIG_FILE" << EOF
# NaK Configuration
DEFAULT_SCALING=96
SHOW_ADVANCED=false
CHECK_UPDATES=true
EOF
    fi
}

# Save configuration value
save_config() {
    local key="$1"
    local value="$2"

    if grep -q "^$key=" "$CONFIG_FILE"; then
        sed -i "s/^$key=.*/$key=$value/" "$CONFIG_FILE"
    else
        echo "$key=$value" >> "$CONFIG_FILE"
    fi
}

# ===================================================================
# UI Functions
# ===================================================================

# Show main menu
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

# Progress bar helper
show_progress() {
    local title="$1"
    local text="$2"
    local percent="$3"

    echo "$percent" | whiptail --gauge "$text" 8 70 0 --title "$title"
}

# ===================================================================
# Game Detection Functions
# ===================================================================

# Get list of Steam games
get_steam_games() {
    local games=()
    local output=$($PROTONTRICKS_CMD -l 2>&1)

    while IFS= read -r line; do
        if [[ "$line" =~ (.*)\(([0-9]+)\) ]]; then
            local name="${BASH_REMATCH[1]}"
            local appid="${BASH_REMATCH[2]}"
            name=$(echo "$name" | xargs) # Trim whitespace

            # Filter out system entries
            if [[ ! "$name" =~ (SteamVR|Proton|Steam Linux Runtime) ]]; then
                games+=("$appid" "$name")
            fi
        fi
    done <<< "$output"

    printf '%s\n' "${games[@]}"
}

# Select a game
select_game() {
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
        # Find the game name
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
# Mod Organizer 2 Functions
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

# Download MO2
download_mo2() {
    local temp_file="$TEMP_DIR/mo2_release.json"

    # Show progress while fetching release info
    {
        echo "10"
        echo "# Fetching latest release info..."

        curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest > "$temp_file"

        echo "30"
        echo "# Parsing release data..."

        local version=$(jq -r '.tag_name' "$temp_file" | sed 's/^v//')
        local download_url=$(jq -r '.assets[] | select(.name | test("^Mod\\.Organizer-[0-9.]+\\.7z$")) | .browser_download_url' "$temp_file")

        if [[ -z "$download_url" ]]; then
            whiptail --title "Error" --msgbox "Could not find MO2 download URL" 8 50
            return 1
        fi

        echo "40"
        echo "# Preparing download..."

        local install_dir=$(whiptail --inputbox "Install directory:" 8 60 "$HOME/ModOrganizer2" 3>&1 1>&2 2>&3)
        [[ -z "$install_dir" ]] && return

        mkdir -p "$install_dir"
        local filename=$(basename "$download_url")
        local archive_path="$TEMP_DIR/$filename"

        echo "50"
        echo "# Downloading MO2 v$version..."

        curl -L -o "$archive_path" "$download_url"

        echo "80"
        echo "# Extracting..."

        # Extract based on available tools
        if command -v 7z &> /dev/null; then
            7z x "$archive_path" -o"$install_dir" -y
        else
            # Fallback to Python py7zr if needed
            install_py7zr_if_needed
            python3 -m py7zr x "$archive_path" "$install_dir"
        fi

        echo "100"
        echo "# Installation complete!"

    } | whiptail --title "Downloading MO2" --gauge "Starting download..." 8 70 0

    whiptail --title "Success" --msgbox "MO2 v$version installed to:\n$install_dir" 10 60

    # Offer to add to Steam
    if whiptail --title "Add to Steam?" --yesno "Add MO2 to Steam as non-Steam game?" 8 50; then
        add_to_steam "Mod Organizer 2" "$install_dir/ModOrganizer.exe"
    fi
}

# ===================================================================
# Proton/Wine Functions
# ===================================================================

install_dependencies() {
    [[ -z "$SELECTED_GAME" ]] && return

    local components=(
        "fontsmooth=rgb"
        "xact"
        "xact_x64"
        "d3dx9_43"
        "d3dcompiler_47"
        "vcrun2022"
        "dotnet8"
    )

    # Add game-specific components
    case "$SELECTED_APPID" in
        22380) # Fallout NV
            components+=("d3dx9")
            ;;
        976620) # Enderal SE
            components+=("d3dx11_43" "d3dcompiler_43" "dotnet6" "dotnet7")
            ;;
    esac

    local total=${#components[@]}
    local count=0

    {
        for comp in "${components[@]}"; do
            ((count++))
            local percent=$((count * 100 / total))
            echo "$percent"
            echo "# Installing $comp..."

            $PROTONTRICKS_CMD --no-bwrap "$SELECTED_APPID" -q "$comp" 2>&1 | tail -n 1
        done
    } | whiptail --title "Installing Dependencies" --gauge "Starting installation..." 8 70 0

    whiptail --title "Complete" --msgbox "Dependencies installed for $SELECTED_GAME" 8 50
}

# ===================================================================
# NXM Handler Functions
# ===================================================================

setup_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    local handler_path=$(whiptail --inputbox "Enter path to nxmhandler.exe:" 10 60 3>&1 1>&2 2>&3)
    [[ -z "$handler_path" || ! -f "$handler_path" ]] && return

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
    update-desktop-database "$HOME/.local/share/applications"

    whiptail --title "Success" --msgbox "NXM handler configured for $SELECTED_GAME" 8 50
}

# Find Proton installation
find_proton_path() {
    local proton_dir="$STEAM_ROOT/steamapps/common/Proton - Experimental/proton"
    if [[ -f "$proton_dir" ]]; then
        echo "$proton_dir"
    else
        # Search in other library folders
        find "$STEAM_ROOT" -name "proton" -path "*/Proton - Experimental/*" 2>/dev/null | head -1
    fi
}

# ===================================================================
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
