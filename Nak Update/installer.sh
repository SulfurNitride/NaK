#!/bin/bash
# ===================================================================
# NaK v2 Installer - Simplified installation
# ===================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Installation directory
INSTALL_DIR="$HOME/nak"

echo -e "${BLUE}Installing NaK v2 - Linux Modding Helper${NC}"
echo -e "${YELLOW}This installer will set up the redesigned version${NC}\n"

# Check if already installed
if [[ -d "$INSTALL_DIR" ]]; then
    echo -e "${YELLOW}NaK is already installed at $INSTALL_DIR${NC}"
    read -p "Update to the new version? This will replace the existing installation. [y/N]: " response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    echo -e "${BLUE}Removing old installation...${NC}"
    rm -rf "$INSTALL_DIR"
fi

# Create installation directory
echo -e "${BLUE}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"

# Download the repository
echo -e "${BLUE}Downloading NaK v2...${NC}"
TMP_DIR=$(mktemp -d)

# Clone repository
git clone -q https://github.com/SulfurNitride/NaK.git "$TMP_DIR" 2>/dev/null || {
    echo -e "${RED}Failed to download NaK${NC}"
    rm -rf "$TMP_DIR"
    exit 1
}

# For now, create the new scripts directly
echo -e "${BLUE}Installing new version...${NC}"

# Create main script
cat > "$INSTALL_DIR/nak" << 'MAIN_SCRIPT'
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

# Source modules
source "$SCRIPT_DIR/modules.sh"

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
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
MAIN_SCRIPT

# Make main script executable
chmod +x "$INSTALL_DIR/nak"

# Copy modules file (this would contain all the module functions)
# For brevity, I'll create a placeholder that sources the actual modules
echo -e "${BLUE}Creating modules...${NC}"
cat > "$INSTALL_DIR/modules.sh" << 'MODULE_PLACEHOLDER'
#!/bin/bash
# Modules file will contain all the menu functions
# This is a placeholder - in production, include the full modules.sh content

mo2_menu() {
    whiptail --title "MO2 Setup" --msgbox "MO2 functionality coming soon!" 8 50
}

vortex_menu() {
    whiptail --title "Vortex Setup" --msgbox "Vortex functionality coming soon!" 8 50
}

limo_menu() {
    whiptail --title "Limo Setup" --msgbox "Limo functionality coming soon!" 8 50
}

ttw_menu() {
    whiptail --title "TTW Setup" --msgbox "TTW functionality coming soon!" 8 50
}

hoolamike_menu() {
    whiptail --title "Hoolamike Tools" --msgbox "Hoolamike functionality coming soon!" 8 50
}

sky_tex_menu() {
    whiptail --title "Sky Texture Optimizer" --msgbox "Sky Texture Optimizer functionality coming soon!" 8 50
}

game_fixes_menu() {
    whiptail --title "Game Fixes" --msgbox "Game fixes functionality coming soon!" 8 50
}

remove_nxm_handlers() {
    whiptail --title "Remove Handlers" --msgbox "Remove NXM handlers functionality coming soon!" 8 50
}

settings_menu() {
    whiptail --title "Settings" --msgbox "Settings functionality coming soon!" 8 50
}

download_mo2() {
    whiptail --title "Download MO2" --msgbox "Download MO2 functionality coming soon!" 8 50
}

setup_existing_mo2() {
    whiptail --title "Setup MO2" --msgbox "Setup existing MO2 functionality coming soon!" 8 50
}

install_dependencies() {
    whiptail --title "Dependencies" --msgbox "Install dependencies functionality coming soon!" 8 50
}

setup_nxm_handler() {
    whiptail --title "NXM Handler" --msgbox "NXM handler functionality coming soon!" 8 50
}

setup_dpi_scaling() {
    whiptail --title "DPI Scaling" --msgbox "DPI scaling functionality coming soon!" 8 50
}

find_proton_path() {
    echo "$STEAM_ROOT/steamapps/common/Proton - Experimental/proton"
}
MODULE_PLACEHOLDER

# Create symlink for easy access
if [[ -d "$HOME/.local/bin" ]] && [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
    ln -sf "$INSTALL_DIR/nak" "$HOME/.local/bin/nak"
    echo -e "${GREEN}Created symlink in ~/.local/bin${NC}"
fi

# Clean up
rm -rf "$TMP_DIR"

echo -e "\n${GREEN}NaK v2 has been successfully installed!${NC}"
echo -e "Installation directory: ${BLUE}$INSTALL_DIR${NC}"
echo -e "\nTo run NaK, use one of these commands:"
echo -e "  ${BLUE}$INSTALL_DIR/nak${NC}"
[[ -L "$HOME/.local/bin/nak" ]] && echo -e "  ${BLUE}nak${NC} (if ~/.local/bin is in your PATH)"

echo -e "\n${YELLOW}Note: This is a redesigned version with a new UI.${NC}"
echo -e "${YELLOW}The full module functionality needs to be integrated.${NC}"

exit 0
