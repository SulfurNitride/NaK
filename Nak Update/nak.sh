#!/bin/bash
# ===================================================================
# NaK (Linux Modding Helper) - Gum Edition
# Version: 3.0.0 - Modern TUI with Gum
# ===================================================================

# Script metadata
readonly SCRIPT_VERSION="3.0.0"
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
declare -g DEFAULT_SCALING="96"
declare -g GUM_BIN=""

# Gum download info
readonly GUM_VERSION="0.16.1"
readonly GUM_URL="https://github.com/charmbracelet/gum/releases/download/v${GUM_VERSION}/gum_${GUM_VERSION}_Linux_x86_64.tar.gz"
readonly GUM_DIR="$SCRIPT_DIR/lib/gum"
readonly GUM_ARCHIVE="$GUM_DIR/gum.tar.gz"

# Colors for gum (using their built-in theming)
export GUM_CHOOSE_CURSOR_FOREGROUND="212"
export GUM_CHOOSE_SELECTED_FOREGROUND="212"
export GUM_CHOOSE_HEADER_FOREGROUND="99"
export GUM_SPIN_SPINNER_FOREGROUND="212"
export GUM_SPIN_TITLE_FOREGROUND="99"

# Terminal size check
check_terminal_size() {
    local cols=$(tput cols)
    local lines=$(tput lines)

    if [[ $cols -lt 80 ]] || [[ $lines -lt 24 ]]; then
        echo "Warning: Terminal size is ${cols}x${lines}"
        echo "Recommended minimum: 80x24"
        echo "Some menus may not display correctly."
        read -p "Press Enter to continue anyway..."
    fi
}

# ===================================================================
# Gum Setup
# ===================================================================

setup_gum() {
    echo "Setting up Gum TUI framework..."

    mkdir -p "$GUM_DIR"

    # Check if gum already exists
    if [[ -f "$GUM_DIR/gum" ]] && [[ -x "$GUM_DIR/gum" ]]; then
        GUM_BIN="$GUM_DIR/gum"
        return 0
    fi

    # Download gum
    echo "Downloading Gum v${GUM_VERSION}..."
    if command -v curl &>/dev/null; then
        curl -L -o "$GUM_ARCHIVE" "$GUM_URL" || return 1
    elif command -v wget &>/dev/null; then
        wget -O "$GUM_ARCHIVE" "$GUM_URL" || return 1
    else
        echo "Error: Neither curl nor wget found!"
        return 1
    fi

    # Extract
    echo "Extracting Gum..."
    tar -xzf "$GUM_ARCHIVE" -C "$GUM_DIR" || return 1

    # Clean up
    rm -f "$GUM_ARCHIVE"

    # Make executable
    chmod +x "$GUM_DIR/gum"

    # Verify
    if [[ -x "$GUM_DIR/gum" ]]; then
        GUM_BIN="$GUM_DIR/gum"
        echo "Gum installed successfully!"
        return 0
    else
        echo "Error: Gum installation failed!"
        return 1
    fi
}

# Gum wrapper functions for consistent styling
gum_choose() {
    "$GUM_BIN" choose --height 15 "$@"
}

gum_input() {
    local prompt="$1"
    shift
    "$GUM_BIN" input --prompt "$prompt " --placeholder "$@"
}

gum_confirm() {
    "$GUM_BIN" confirm "$@"
}

gum_spin() {
    "$GUM_BIN" spin --spinner dot --title "$1" -- "${@:2}"
}

gum_style() {
    "$GUM_BIN" style "$@"
}

gum_format() {
    "$GUM_BIN" format "$@"
}

# ===================================================================
# Core Functions
# ===================================================================

init() {
    # Check terminal size
    check_terminal_size

    # Create directories
    mkdir -p "$CONFIG_DIR" "$TEMP_DIR" "$SCRIPT_DIR/lib"

    # Setup logging
    exec 2> >(tee -a "$LOG_FILE")
    echo "[$(date)] Starting $SCRIPT_NAME v$SCRIPT_VERSION" >> "$LOG_FILE"

    # Setup gum
    if ! setup_gum; then
        echo "Failed to set up Gum. Please check your internet connection."
        exit 1
    fi

    # Clear screen
    clear

    # Check dependencies
    check_dependencies

    # Find Steam
    STEAM_ROOT=$(find_steam_root)

    # Load config
    load_config

    # Trap cleanup
    trap cleanup EXIT INT TERM
}

cleanup() {
    rm -rf "$TEMP_DIR"
    echo "[$(date)] Cleanup completed" >> "$LOG_FILE"
}

# Check dependencies
check_dependencies() {
    local missing=()

    # Check protontricks
    if command -v protontricks &> /dev/null; then
        PROTONTRICKS_CMD="protontricks"
    elif flatpak list --app 2>/dev/null | grep -q "com.github.Matoking.protontricks"; then
        PROTONTRICKS_CMD="flatpak run com.github.Matoking.protontricks"
    else
        missing+=("protontricks")
    fi

    # Check other deps
    for cmd in curl jq unzip wget; do
        command -v "$cmd" &> /dev/null || missing+=("$cmd")
    done

    # Check for 7z
    local has_7z=false
    for variant in 7z 7za 7zr p7zip; do
        if command -v "$variant" &>/dev/null; then
            has_7z=true
            break
        fi
    done
    [[ "$has_7z" == "false" ]] && missing+=("p7zip-full")

    if [[ ${#missing[@]} -gt 0 ]]; then
        gum_style \
            --foreground 196 \
            --border double \
            --border-foreground 196 \
            --padding "1 2" \
            --margin "1" \
            "Missing Dependencies" \
            "" \
            "Please install: ${missing[*]}" \
            "" \
            "Example:" \
            "sudo apt install ${missing[*]}"
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

    gum_style --foreground 196 "Error: Steam installation not found!"
    exit 1
}

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE" 2>/dev/null || create_default_config
    else
        create_default_config
    fi
}

create_default_config() {
    cat > "$CONFIG_FILE" << EOF
# NaK Configuration
DEFAULT_SCALING=96
CHECK_UPDATES=true
EOF
}

# ===================================================================
# Main Menu
# ===================================================================

show_main_menu() {
    while true; do
        clear

        # Header
        gum_style \
            --foreground 212 \
            --border double \
            --border-foreground 99 \
            --padding "1 2" \
            --margin "1" \
            --align center \
            "$SCRIPT_NAME v$SCRIPT_VERSION" \
            "Modern Linux Modding Tools"

        # Menu
        local choice=$(gum_choose \
            "Mod Organizer 2 Setup" \
            "Vortex Setup" \
            "Limo Setup (Native Linux)" \
            "Tale of Two Wastelands" \
            "Hoolamike Tools" \
            "Sky Texture Optimizer" \
            "Game-Specific Fixes" \
            "Remove NXM Handlers" \
            "Settings" \
            "Exit")

        case "$choice" in
            "Mod Organizer 2 Setup") mo2_menu ;;
            "Vortex Setup") vortex_menu ;;
            "Limo Setup"*) limo_menu ;;
            "Tale of Two Wastelands") ttw_menu ;;
            "Hoolamike Tools") hoolamike_menu ;;
            "Sky Texture Optimizer") sky_tex_menu ;;
            "Game-Specific Fixes") game_fixes_menu ;;
            "Remove NXM Handlers") remove_nxm_handlers ;;
            "Settings") settings_menu ;;
            "Exit"|"") exit 0 ;;
        esac
    done
}

# ===================================================================
# MO2 Functions
# ===================================================================

mo2_menu() {
    while true; do
        clear

        gum_style \
            --foreground 212 \
            --border rounded \
            --padding "1 2" \
            --margin "1" \
            "Mod Organizer 2 Setup"

        local choice=$(gum_choose \
            "Download Latest MO2" \
            "Setup Existing MO2" \
            "Install Dependencies" \
            "Configure NXM Handler" \
            "Configure DPI Scaling" \
            "Back to Main Menu")

        case "$choice" in
            "Download Latest MO2") download_mo2 ;;
            "Setup Existing MO2") setup_existing_mo2 ;;
            "Install Dependencies") select_game && install_dependencies ;;
            "Configure NXM Handler") select_game && setup_nxm_handler ;;
            "Configure DPI Scaling") select_game && setup_dpi_scaling ;;
            "Back"*|"") return ;;
        esac
    done
}

download_mo2() {
    clear

    # Get installation directory with tab completion
    local install_dir=$(gum_input "Installation directory:" "$HOME/ModOrganizer2")
    [[ -z "$install_dir" ]] && return

    # Expand tilde
    install_dir="${install_dir/#\~/$HOME}"

    if [[ -d "$install_dir" ]]; then
        if ! gum_confirm "Directory exists. Overwrite?"; then
            return
        fi
        rm -rf "$install_dir"
    fi

    mkdir -p "$install_dir"

    # Fetch release info
    echo "Fetching latest release info..."
    local release_info=$(curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^Mod\\.Organizer-[0-9.]+\\.7z$")) | .browser_download_url')

    if [[ -z "$download_url" ]] || [[ "$download_url" == "null" ]]; then
        gum_style --foreground 196 "Error: Could not find MO2 download URL!"
        read -p "Press Enter to continue..."
        return 1
    fi

    # Download with progress
    local archive="$TEMP_DIR/MO2-$version.7z"

    gum_spin "Downloading MO2 v$version..." \
        curl -L -o "$archive" "$download_url"

    # Extract
    gum_spin "Extracting MO2..." \
        7z x "$archive" -o"$install_dir" -y

    # Verify installation
    if [[ -f "$install_dir/ModOrganizer.exe" ]]; then
        gum_style --foreground 82 "MO2 v$version installed successfully!"
        echo "Location: $install_dir"

        if gum_confirm "Add MO2 to Steam?"; then
            # Ask for custom name
            local mo2_name=$(gum_input "Name for Steam:" "Mod Organizer 2")
            [[ -z "$mo2_name" ]] && mo2_name="Mod Organizer 2"

            add_game_to_steam "$mo2_name" "$install_dir/ModOrganizer.exe" "$install_dir"
        fi
    else
        gum_style --foreground 196 "Installation failed! ModOrganizer.exe not found."
    fi

    rm -f "$archive"
    read -p "Press Enter to continue..."
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
                    games+=("$appid:$name")
                fi
            fi
        fi
    done <<< "$output"

    printf '%s\n' "${games[@]}"
}

select_game() {
    clear

    gum_style \
        --foreground 99 \
        --border rounded \
        --padding "1 2" \
        "Select Game"

    echo "Fetching game list..."
    local games=($(get_steam_games))

    if [[ ${#games[@]} -eq 0 ]]; then
        gum_style --foreground 196 "No games found!"
        read -p "Press Enter to continue..."
        return 1
    fi

    # Build display array
    local display_games=()
    for game in "${games[@]}"; do
        local appid="${game%%:*}"
        local name="${game#*:}"
        display_games+=("$name [$appid]")
    done

    local choice=$(printf '%s\n' "${display_games[@]}" | gum_choose)
    [[ -z "$choice" ]] && return 1

    # Extract appid from choice
    if [[ "$choice" =~ \[([0-9]+)\]$ ]]; then
        SELECTED_APPID="${BASH_REMATCH[1]}"
        SELECTED_GAME="${choice% \[*\]}"

        gum_style --foreground 82 "Selected: $SELECTED_GAME"
        sleep 1
        return 0
    fi

    return 1
}

# ===================================================================
# Dependency Installation
# ===================================================================

install_dependencies() {
    [[ -z "$SELECTED_GAME" ]] && return

    clear

    gum_style \
        --foreground 99 \
        --border rounded \
        --padding "1 2" \
        "Installing Dependencies for $SELECTED_GAME"

    local components=(
        fontsmooth=rgb
        xact
        xact_x64
        d3dx9_43
        d3dx9
        vcrun2022
        dotnet6
        dotnet7
        dotnet8
        d3dcompiler_47
        d3dx11_43
    )

    # Special components for specific games
    if [[ "$SELECTED_APPID" == "22380" ]]; then  # FNV
        components=(fontsmooth=rgb xact xact_x64 d3dx9_43 d3dx9 vcrun2022)
    elif [[ "$SELECTED_APPID" == "976620" ]]; then  # Enderal
        components+=(winhttp)
    fi

    echo "Components to install:"
    printf '%s\n' "${components[@]}"
    echo ""

    if gum_confirm "Continue with installation?"; then
        # Run protontricks with spinner
        gum_spin "Installing dependencies..." \
            $PROTONTRICKS_CMD --no-bwrap "$SELECTED_APPID" -q "${components[@]}"

        # Additional fixes
        local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
        if [[ -d "$prefix_path" ]]; then
            # Enable dotfiles
            local proton_path=$(find_proton_path)
            gum_spin "Enabling dotfiles visibility..." \
                env STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
                    STEAM_COMPAT_DATA_PATH="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID" \
                    "$proton_path" run reg add "HKCU\\Software\\Wine" /v ShowDotFiles /d Y /f
        fi

        gum_style --foreground 82 "Dependencies installed successfully!"
    fi

    read -p "Press Enter to continue..."
}

# ===================================================================
# NXM Handler Setup
# ===================================================================

setup_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    clear

    gum_style \
        --foreground 99 \
        --border rounded \
        --padding "1 2" \
        "Configure NXM Handler for $SELECTED_GAME"

    local nxmhandler_path=$(gum_input "Path to nxmhandler.exe:")
    [[ -z "$nxmhandler_path" || ! -f "$nxmhandler_path" ]] && return

    local proton_path=$(find_proton_path)
    local compat_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID"
    local desktop_file="$HOME/.local/share/applications/mo2-nxm-handler.desktop"

    mkdir -p "$(dirname "$desktop_file")"

    cat > "$desktop_file" << EOF
[Desktop Entry]
Type=Application
Categories=Game;
Exec=bash -c 'env "STEAM_COMPAT_CLIENT_INSTALL_PATH=$STEAM_ROOT" "STEAM_COMPAT_DATA_PATH=$compat_path" "$proton_path" run "$nxmhandler_path" "%u"'
Name=Mod Organizer 2 NXM Handler
MimeType=x-scheme-handler/nxm;
NoDisplay=true
EOF

    chmod +x "$desktop_file"
    xdg-mime default mo2-nxm-handler.desktop x-scheme-handler/nxm
    update-desktop-database "$HOME/.local/share/applications"

    gum_style --foreground 82 "NXM handler configured successfully!"
    read -p "Press Enter to continue..."
}

# ===================================================================
# DPI Scaling Setup
# ===================================================================

setup_dpi_scaling() {
    [[ -z "$SELECTED_GAME" ]] && return

    clear

    gum_style \
        --foreground 99 \
        --border rounded \
        --padding "1 2" \
        "Configure DPI Scaling for $SELECTED_GAME"

    local scales=("96 - Standard (100%)" "120 - Medium (125%)" "144 - Large (150%)" "192 - Extra Large (200%)")

    local choice=$(printf '%s\n' "${scales[@]}" | gum_choose)
    [[ -z "$choice" ]] && return

    # Extract number from choice
    local scale="${choice%% *}"

    # Create batch file for registry changes
    local batch_file="$TEMP_DIR/dpi.bat"
    cat > "$batch_file" << EOF
@echo off
reg add "HKCU\\Control Panel\\Desktop" /v LogPixels /t REG_DWORD /d $scale /f
reg add "HKCU\\Software\\Wine\\X11 Driver" /v LogPixels /t REG_DWORD /d $scale /f
exit 0
EOF

    # Run with Proton
    local proton_path=$(find_proton_path)
    gum_spin "Applying DPI scaling..." \
        env STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
            STEAM_COMPAT_DATA_PATH="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID" \
            "$proton_path" run cmd /c "$(winepath -w "$batch_file")"

    rm -f "$batch_file"

    gum_style --foreground 82 "DPI scaling set to $scale"
    echo "Restart the application to see changes."
    read -p "Press Enter to continue..."
}

# ===================================================================
# Other Menu Stubs
# ===================================================================

vortex_menu() {
    gum_style --foreground 214 "Vortex functionality coming soon!"
    read -p "Press Enter to continue..."
}

limo_menu() {
    gum_style --foreground 214 "Limo functionality coming soon!"
    read -p "Press Enter to continue..."
}

ttw_menu() {
    gum_style --foreground 214 "TTW functionality coming soon!"
    read -p "Press Enter to continue..."
}

hoolamike_menu() {
    gum_style --foreground 214 "Hoolamike functionality coming soon!"
    read -p "Press Enter to continue..."
}

sky_tex_menu() {
    gum_style --foreground 214 "Sky Texture Optimizer coming soon!"
    read -p "Press Enter to continue..."
}

game_fixes_menu() {
    gum_style --foreground 214 "Game fixes coming soon!"
    read -p "Press Enter to continue..."
}

remove_nxm_handlers() {
    local found=0
    for handler in "$HOME/.local/share/applications"/*nxm-handler.desktop; do
        [[ -f "$handler" ]] && rm -f "$handler" && ((found++))
    done

    if [[ $found -gt 0 ]]; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null
        gum_style --foreground 82 "Removed $found NXM handler(s)"
    else
        gum_style --foreground 214 "No NXM handlers found"
    fi

    read -p "Press Enter to continue..."
}

settings_menu() {
    gum_style --foreground 214 "Settings menu coming soon!"
    read -p "Press Enter to continue..."
}

# ===================================================================
# Helper Functions
# ===================================================================

find_proton_path() {
    find "$STEAM_ROOT" -name "proton" -path "*/Proton - Experimental/*" 2>/dev/null | head -1
}

setup_existing_mo2() {
    clear

    local mo2_dir=$(gum_input "Path to MO2 directory:")
    [[ -z "$mo2_dir" ]] && return

    mo2_dir="${mo2_dir/#\~/$HOME}"

    if [[ ! -f "$mo2_dir/ModOrganizer.exe" ]]; then
        gum_style --foreground 196 "ModOrganizer.exe not found!"
        read -p "Press Enter to continue..."
        return
    fi

    gum_style --foreground 82 "Found MO2 at: $mo2_dir"

    if gum_confirm "Add to Steam?"; then
        local mo2_name=$(gum_input "Name for Steam:" "Mod Organizer 2")
        [[ -z "$mo2_name" ]] && mo2_name="Mod Organizer 2"

        add_game_to_steam "$mo2_name" "$mo2_dir/ModOrganizer.exe" "$mo2_dir"
    fi
}

add_game_to_steam() {
    # Stub for now
    gum_style --foreground 214 "Add to Steam functionality coming soon!"
    echo "Would add: $1"
    read -p "Press Enter to continue..."
}

# ===================================================================
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
