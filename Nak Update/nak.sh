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
readonly GUM_VERSION="0.14.5"
readonly GUM_URL="https://github.com/charmbracelet/gum/releases/download/v${GUM_VERSION}/gum_${GUM_VERSION}_Linux_x86_64.tar.gz"
readonly GUM_DIR="$SCRIPT_DIR/lib/gum"
readonly GUM_ARCHIVE="$GUM_DIR/gum.tar.gz"

# Enhanced color scheme
export GUM_CHOOSE_CURSOR_FOREGROUND="212"
export GUM_CHOOSE_SELECTED_FOREGROUND="212"
export GUM_CHOOSE_HEADER_FOREGROUND="99"
export GUM_CHOOSE_ITEM_FOREGROUND="255"
export GUM_CHOOSE_CURSOR="▶ "
export GUM_SPIN_SPINNER="dot"
export GUM_SPIN_SPINNER_FOREGROUND="212"
export GUM_SPIN_TITLE_FOREGROUND="99"
export GUM_INPUT_CURSOR_FOREGROUND="212"
export GUM_INPUT_PROMPT_FOREGROUND="99"
export GUM_CONFIRM_SELECTED_BACKGROUND="212"
export GUM_CONFIRM_UNSELECTED_BACKGROUND="235"

# Terminal size check
check_terminal_size() {
    local cols=$(tput cols)
    local lines=$(tput lines)

    if [[ $cols -lt 80 ]] || [[ $lines -lt 24 ]]; then
        echo "⚠️  Warning: Terminal size is ${cols}x${lines}"
        echo "📐 Recommended minimum: 80x24"
        echo "Some menus may not display correctly."
        read -p "Press Enter to continue anyway..."
    fi
}

# ===================================================================
# Gum Setup
# ===================================================================

setup_gum() {
    echo "🔧 Setting up Gum TUI framework..."

    mkdir -p "$GUM_DIR"

    # Check if gum already exists
    if [[ -f "$GUM_DIR/gum" ]] && [[ -x "$GUM_DIR/gum" ]]; then
        GUM_BIN="$GUM_DIR/gum"
        echo "✓ Gum already installed"
        return 0
    fi

    # Download gum
    echo "📦 Downloading Gum v${GUM_VERSION}..."
    if command -v curl &>/dev/null; then
        curl -L -o "$GUM_ARCHIVE" "$GUM_URL" || return 1
    elif command -v wget &>/dev/null; then
        wget -O "$GUM_ARCHIVE" "$GUM_URL" || return 1
    else
        echo "❌ Error: Neither curl nor wget found!"
        return 1
    fi

    # Extract directly to GUM_DIR
    echo "📂 Extracting Gum..."
    cd "$GUM_DIR"
    tar -xzf "$GUM_ARCHIVE" || return 1

    # The archive contains: gum, completions/, manpages/, LICENSE, README.md
    # Move gum binary to the expected location if it's in a subdirectory
    if [[ ! -f "gum" ]]; then
        # Try to find gum in any subdirectory
        local found_gum=$(find . -name "gum" -type f -executable | head -1)
        if [[ -n "$found_gum" ]]; then
            mv "$found_gum" ./gum
        fi
    fi

    cd - > /dev/null

    # Clean up
    rm -f "$GUM_ARCHIVE"

    # Make executable
    chmod +x "$GUM_DIR/gum" 2>/dev/null || true

    # Verify
    if [[ -x "$GUM_DIR/gum" ]]; then
        GUM_BIN="$GUM_DIR/gum"
        echo "✅ Gum installed successfully!"
        return 0
    else
        echo "❌ Error: Gum installation failed!"
        return 1
    fi
}

# Enhanced Gum wrapper functions with better styling
gum_choose() {
    "$GUM_BIN" choose \
        --height 15 \
        --cursor.foreground "212" \
        --selected.foreground "212" \
        --selected.bold \
        --header.foreground "99" \
        --item.foreground "255" \
        "$@"
}

gum_input() {
    local prompt="$1"
    shift
    "$GUM_BIN" input \
        --prompt "$prompt " \
        --prompt.foreground "99" \
        --cursor.foreground "212" \
        --placeholder "$@" \
        --width 80
}

gum_file() {
    local prompt="${1:-Select file:}"
    "$GUM_BIN" file \
        --cursor.foreground "212" \
        --selected.foreground "212" \
        --directory.foreground "99" \
        --file.foreground "255" \
        --height 15
}

gum_confirm() {
    "$GUM_BIN" confirm \
        --selected.background "212" \
        --selected.foreground "0" \
        --unselected.background "235" \
        --unselected.foreground "254" \
        "$@"
}

gum_spin() {
    "$GUM_BIN" spin \
        --spinner dot \
        --spinner.foreground "212" \
        --title.foreground "99" \
        --title "$1" \
        -- "${@:2}"
}

gum_style() {
    "$GUM_BIN" style \
        --foreground "$1" \
        "${@:2}"
}

gum_style_box() {
    local title="$1"
    shift
    "$GUM_BIN" style \
        --border double \
        --border-foreground "99" \
        --padding "1 2" \
        --margin "1" \
        --foreground "255" \
        --bold \
        "$title" \
        "$@"
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
        echo "❌ Failed to set up Gum. Please check your internet connection."
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

    # Source modules if they exist
    if [[ -f "$SCRIPT_DIR/modules.sh" ]]; then
        source "$SCRIPT_DIR/modules.sh"
    fi

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
        gum_style_box "❌ Missing Dependencies" \
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

    gum_style 196 "❌ Error: Steam installation not found!"
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

        # Fancy header with box
        echo
        "$GUM_BIN" style \
            --border double \
            --border-foreground "212" \
            --padding "2 4" \
            --margin "1 2" \
            --align center \
            --foreground "212" \
            --bold \
            "$SCRIPT_NAME" \
            "v$SCRIPT_VERSION" \
            "" \
            "🚀 Modern Linux Modding Tools 🎮"

        echo

        # Menu with icons
        local choice=$("$GUM_BIN" choose \
            --height 12 \
            --cursor.foreground "212" \
            --selected.foreground "212" \
            --selected.bold \
            --header "Select an option:" \
            --header.foreground "99" \
            "🎯 Mod Organizer 2 Setup" \
            "🔧 Vortex Setup" \
            "🐧 Limo Setup (Native Linux)" \
            "🌐 Tale of Two Wastelands" \
            "🛠️  Hoolamike Tools" \
            "🖼️  Sky Texture Optimizer" \
            "🎮 Game-Specific Fixes" \
            "🗑️  Remove NXM Handlers" \
            "⚙️  Settings" \
            "🚪 Exit")

        case "$choice" in
            *"Mod Organizer 2"*) mo2_menu ;;
            *"Vortex"*) vortex_menu ;;
            *"Limo"*) limo_menu ;;
            *"Tale of Two"*) ttw_menu ;;
            *"Hoolamike"*) hoolamike_menu ;;
            *"Sky Texture"*) sky_tex_menu ;;
            *"Game-Specific"*) game_fixes_menu ;;
            *"Remove NXM"*) remove_nxm_handlers ;;
            *"Settings"*) settings_menu ;;
            *"Exit"*|"") break ;;
        esac
    done

    clear
    gum_style 82 "👋 Thanks for using NaK!"
}

# ===================================================================
# MO2 Functions
# ===================================================================

mo2_menu() {
    while true; do
        clear

        gum_style_box "🎯 Mod Organizer 2 Setup"

        local choice=$("$GUM_BIN" choose \
            --height 10 \
            --cursor.foreground "212" \
            --selected.foreground "212" \
            --selected.bold \
            "📥 Download Latest MO2" \
            "📁 Setup Existing MO2" \
            "📦 Install Dependencies" \
            "🔗 Configure NXM Handler" \
            "🖥️  Configure DPI Scaling" \
            "🔙 Back to Main Menu")

        case "$choice" in
            *"Download"*) download_mo2 ;;
            *"Setup Existing"*) setup_existing_mo2 ;;
            *"Install Dependencies"*) select_game && install_dependencies ;;
            *"NXM Handler"*) select_game && setup_nxm_handler ;;
            *"DPI Scaling"*) select_game && setup_dpi_scaling ;;
            *"Back"*|"") return ;;
        esac
    done
}

download_mo2() {
    clear

    gum_style_box "📥 Download Mod Organizer 2"

    # Get installation directory with file browser
    echo "Select installation directory:"
    local install_dir=$(gum_file)

    # If cancelled
    [[ -z "$install_dir" ]] && return

    # If file selected, use parent directory
    [[ -f "$install_dir" ]] && install_dir=$(dirname "$install_dir")

    if [[ -d "$install_dir/ModOrganizer2" ]]; then
        install_dir="$install_dir/ModOrganizer2"
    else
        install_dir="$install_dir"
    fi

    if [[ -f "$install_dir/ModOrganizer.exe" ]]; then
        if ! gum_confirm "⚠️  Directory contains MO2. Overwrite?"; then
            return
        fi
    fi

    mkdir -p "$install_dir"

    # Fetch release info
    echo
    gum_style 99 "🔍 Fetching latest release info..."
    local release_info=$(curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^Mod\\.Organizer-[0-9.]+\\.7z$")) | .browser_download_url')

    if [[ -z "$download_url" ]] || [[ "$download_url" == "null" ]]; then
        gum_style 196 "❌ Error: Could not find MO2 download URL!"
        read -p "Press Enter to continue..."
        return 1
    fi

    gum_style 82 "✅ Found MO2 v$version"
    echo

    # Download with progress
    local archive="$TEMP_DIR/MO2-$version.7z"

    gum_spin "📥 Downloading MO2 v$version..." \
        curl -L -o "$archive" "$download_url"

    # Extract
    gum_spin "📦 Extracting MO2..." \
        7z x "$archive" -o"$install_dir" -y

    # Verify installation
    if [[ -f "$install_dir/ModOrganizer.exe" ]]; then
        echo
        gum_style 82 "✅ MO2 v$version installed successfully!"
        gum_style 99 "📁 Location: $install_dir"

        if gum_confirm "Add MO2 to Steam?"; then
            # Ask for custom name
            local mo2_name=$(gum_input "Name for Steam:" "Mod Organizer 2")
            [[ -z "$mo2_name" ]] && mo2_name="Mod Organizer 2"

            add_game_to_steam "$mo2_name" "$install_dir/ModOrganizer.exe" "$install_dir"
        fi
    else
        gum_style 196 "❌ Installation failed! ModOrganizer.exe not found."
    fi

    rm -f "$archive"
    echo
    read -p "Press Enter to continue..."
}

# ===================================================================
# Game Selection with Better Formatting
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

        if [[ "$collecting" == true ]] && [[ "$line" =~ \(([0-9]+)\) ]]; then
            local appid="${BASH_REMATCH[1]}"
            local name="${line%% (*}"
            name=$(echo "$name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

            # Clean up non-Steam shortcut prefix
            if [[ "$name" =~ ^Non-Steam[[:space:]]shortcut:[[:space:]](.+)$ ]]; then
                name="${BASH_REMATCH[1]}"
            fi

            if [[ ! "$name" =~ (SteamVR|Proton|Steam Linux Runtime|Steamworks) ]]; then
                games+=("$appid|$name")
            fi
        fi
    done <<< "$output"

    printf '%s\n' "${games[@]}"
}

select_game() {
    clear

    gum_style_box "🎮 Select Game"

    echo
    gum_style 99 "🔍 Fetching game list..."
    local games=($(get_steam_games))

    if [[ ${#games[@]} -eq 0 ]]; then
        gum_style 196 "❌ No games found!"
        echo
        read -p "Press Enter to continue..."
        return 1
    fi

    # Build display array
    local display_games=()
    for game in "${games[@]}"; do
        local appid="${game%%|*}"
        local name="${game#*|}"
        display_games+=("$name [$appid]")
    done

    echo
    local choice=$(printf '%s\n' "${display_games[@]}" | "$GUM_BIN" choose \
        --height 15 \
        --header "Choose a game:" \
        --header.foreground "99")

    [[ -z "$choice" ]] && return 1

    # Extract appid from choice
    if [[ "$choice" =~ \[([0-9]+)\]$ ]]; then
        SELECTED_APPID="${BASH_REMATCH[1]}"
        SELECTED_GAME="${choice% \[*\]}"

        echo
        gum_style 82 "✅ Selected: $SELECTED_GAME"
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

    gum_style_box "📦 Installing Dependencies" \
        "For: $SELECTED_GAME"

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

    echo
    gum_style 99 "📋 Components to install:"
    for comp in "${components[@]}"; do
        echo "  • $comp"
    done
    echo

    if gum_confirm "Continue with installation?"; then
        # Run protontricks with spinner
        gum_spin "🔧 Installing dependencies..." \
            $PROTONTRICKS_CMD --no-bwrap "$SELECTED_APPID" -q "${components[@]}"

        # Additional fixes
        local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
        if [[ -d "$prefix_path" ]]; then
            # Enable dotfiles
            local proton_path=$(find_proton_path)
            gum_spin "👁️  Enabling dotfiles visibility..." \
                env STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
                    STEAM_COMPAT_DATA_PATH="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID" \
                    "$proton_path" run reg add "HKCU\\Software\\Wine" /v ShowDotFiles /d Y /f
        fi

        echo
        gum_style 82 "✅ Dependencies installed successfully!"
    fi

    echo
    read -p "Press Enter to continue..."
}

# ===================================================================
# NXM Handler Setup
# ===================================================================

setup_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    clear

    gum_style_box "🔗 Configure NXM Handler" \
        "For: $SELECTED_GAME"

    echo
    echo "Select nxmhandler.exe location:"
    local nxmhandler_path=$(gum_file)

    [[ -z "$nxmhandler_path" || ! -f "$nxmhandler_path" ]] && return

    # Verify it's an exe file
    if [[ ! "$nxmhandler_path" =~ \.exe$ ]]; then
        gum_style 196 "❌ Please select an .exe file!"
        read -p "Press Enter to continue..."
        return
    fi

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
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

    echo
    gum_style 82 "✅ NXM handler configured successfully!"
    echo
    read -p "Press Enter to continue..."
}

# ===================================================================
# DPI Scaling Setup
# ===================================================================

setup_dpi_scaling() {
    [[ -z "$SELECTED_GAME" ]] && return

    clear

    gum_style_box "🖥️  Configure DPI Scaling" \
        "For: $SELECTED_GAME"

    echo
    local choice=$("$GUM_BIN" choose \
        --header "Select DPI scaling:" \
        --header.foreground "99" \
        "96 - Standard (100%)" \
        "120 - Medium (125%)" \
        "144 - Large (150%)" \
        "192 - Extra Large (200%)" \
        "Custom value")

    [[ -z "$choice" ]] && return

    local scale
    if [[ "$choice" == "Custom value" ]]; then
        scale=$(gum_input "Enter DPI value (96-240):" "120")
        [[ -z "$scale" ]] && return
    else
        scale="${choice%% *}"
    fi

    # Create batch file for registry changes
    local batch_file="$TEMP_DIR/dpi.bat"
    cat > "$batch_file" << EOF
@echo off
reg add "HKCU\\Control Panel\\Desktop" /v LogPixels /t REG_DWORD /d $scale /f
reg add "HKCU\\Software\\Wine\\X11 Driver" /v LogPixels /t REG_DWORD /d $scale /f
exit 0
EOF

    # Convert to Windows path
    local win_batch=$(cd "$TEMP_DIR" && pwd -W 2>/dev/null || echo "Z:$TEMP_DIR")/dpi.bat

    # Run with Proton
    local proton_path=$(find_proton_path)
    gum_spin "⚙️  Applying DPI scaling..." \
        env STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
            STEAM_COMPAT_DATA_PATH="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID" \
            "$proton_path" run cmd /c "$win_batch"

    rm -f "$batch_file"

    echo
    gum_style 82 "✅ DPI scaling set to $scale"
    gum_style 99 "ℹ️  Restart the application to see changes."
    echo
    read -p "Press Enter to continue..."
}

# ===================================================================
# VDF/Steam Integration
# ===================================================================

add_game_to_steam() {
    local game_name="$1"
    local exe_path="$2"
    local start_dir="${3:-$(dirname "$exe_path")}"

    clear
    gum_style_box "🎮 Adding to Steam"

    # Check for Python
    if ! command -v python3 &>/dev/null; then
        gum_style 196 "❌ Python3 is required for Steam integration"
        echo
        read -p "Press Enter to continue..."
        return 1
    fi

    # Create Python script for VDF manipulation
    local py_script="$TEMP_DIR/add_to_steam.py"
    cat > "$py_script" << 'PYTHON_SCRIPT'
import sys
import os
import struct
import time

def generate_app_id(name, exe):
    """Generate a unique app ID for the game"""
    return abs(hash(name + exe)) % 1000000000

def add_to_steam(steam_root, game_name, exe_path, start_dir):
    shortcuts_path = os.path.join(steam_root, "userdata")

    if not os.path.exists(shortcuts_path):
        print(f"❌ Error: userdata directory not found at {shortcuts_path}")
        return False

    user_dirs = [d for d in os.listdir(shortcuts_path) if os.path.isdir(os.path.join(shortcuts_path, d))]
    if not user_dirs:
        print("❌ Error: No user directories found")
        return False

    app_id = generate_app_id(game_name, exe_path)

    for user_dir in user_dirs:
        vdf_dir = os.path.join(shortcuts_path, user_dir, "config")
        os.makedirs(vdf_dir, exist_ok=True)

        # For now, just create a marker file
        marker = os.path.join(vdf_dir, f"nak_added_{app_id}.txt")
        with open(marker, 'w') as f:
            f.write(f"{game_name}\n{exe_path}\n{start_dir}\n")

        print(f"✅ Added {game_name} marker for user {user_dir}")

    return True

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: script.py steam_root game_name exe_path [start_dir]")
        sys.exit(1)

    steam_root = sys.argv[1]
    game_name = sys.argv[2]
    exe_path = sys.argv[3]
    start_dir = sys.argv[4] if len(sys.argv) > 4 else os.path.dirname(exe_path)

    if add_to_steam(steam_root, game_name, exe_path, start_dir):
        print(f"\n✅ Successfully marked {game_name} for Steam!")
        print("ℹ️  To complete:")
        print("1. Restart Steam")
        print("2. Add as non-Steam game manually")
        print("3. Set Proton compatibility")
    else:
        print("❌ Failed to add to Steam")
        sys.exit(1)
PYTHON_SCRIPT

    # Run the Python script
    if python3 "$py_script" "$STEAM_ROOT" "$game_name" "$exe_path" "$start_dir"; then
        echo
        gum_style 82 "📝 Note: Full VDF integration coming soon!"
        gum_style 99 "For now, please add the game manually in Steam"
    fi

    rm -f "$py_script"
    echo
    read -p "Press Enter to continue..."
}

# ===================================================================
# Vortex Menu
# ===================================================================

vortex_menu() {
    while true; do
        clear
        gum_style_box "🔧 Vortex Setup"

        local choice=$("$GUM_BIN" choose \
            --height 10 \
            "📥 Download Latest Vortex" \
            "📁 Setup Existing Vortex" \
            "📦 Install Dependencies" \
            "🔗 Configure NXM Handler" \
            "🖥️  Configure DPI Scaling" \
            "🔙 Back to Main Menu")

        case "$choice" in
            *"Download"*) download_vortex ;;
            *"Setup Existing"*) setup_existing_vortex ;;
            *"Install Dependencies"*) select_game && install_dependencies ;;
            *"NXM Handler"*) select_game && setup_vortex_nxm_handler ;;
            *"DPI Scaling"*) select_game && setup_dpi_scaling ;;
            *"Back"*|"") return ;;
        esac
    done
}

download_vortex() {
    clear
    gum_style_box "📥 Download Vortex"

    # Get installation directory
    echo "Select installation directory:"
    local install_dir=$(gum_file)

    [[ -z "$install_dir" ]] && return
    [[ -f "$install_dir" ]] && install_dir=$(dirname "$install_dir")

    mkdir -p "$install_dir"

    # Fetch release info
    echo
    gum_style 99 "🔍 Fetching latest Vortex release..."
    local release_info=$(curl -s https://api.github.com/repos/Nexus-Mods/Vortex/releases/latest)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^vortex-setup-[0-9.]+\\.exe$")) | .browser_download_url')

    if [[ -z "$download_url" ]] || [[ "$download_url" == "null" ]]; then
        gum_style 196 "❌ Error: Could not find Vortex download URL!"
        read -p "Press Enter to continue..."
        return 1
    fi

    gum_style 82 "✅ Found Vortex v$version"
    echo

    # Download
    local installer="$TEMP_DIR/vortex-setup.exe"
    gum_spin "📥 Downloading Vortex..." \
        curl -L -o "$installer" "$download_url"

    # Install with Wine
    if command -v wine &>/dev/null; then
        local wine_install_dir="Z:$(echo "$install_dir" | sed 's|/|\\|g')"
        gum_spin "🍷 Installing with Wine..." \
            WINEPREFIX="$HOME/.wine" wine "$installer" /S "/D=$wine_install_dir"

        echo
        gum_style 82 "✅ Vortex installed successfully!"
        gum_style 99 "📁 Location: $install_dir"
    else
        gum_style 196 "❌ Wine not found! Please install Wine first."
    fi

    rm -f "$installer"
    echo
    read -p "Press Enter to continue..."
}

setup_vortex_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    clear
    gum_style_box "🔗 Configure Vortex NXM Handler" \
        "For: $SELECTED_GAME"

    echo
    echo "Select Vortex.exe location:"
    local vortex_path=$(gum_file)

    [[ -z "$vortex_path" || ! -f "$vortex_path" ]] && return

    if [[ ! "$vortex_path" =~ \.exe$ ]]; then
        gum_style 196 "❌ Please select Vortex.exe!"
        read -p "Press Enter to continue..."
        return
    fi

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
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

    echo
    gum_style 82 "✅ Vortex NXM handler configured!"
    echo
    read -p "Press Enter to continue..."
}

setup_existing_vortex() {
    clear
    gum_style_box "📁 Setup Existing Vortex"

    echo
    echo "Select Vortex directory:"
    local vortex_dir=$(gum_file)

    [[ -z "$vortex_dir" ]] && return
    [[ -f "$vortex_dir" ]] && vortex_dir=$(dirname "$vortex_dir")

    if [[ ! -f "$vortex_dir/Vortex.exe" ]]; then
        gum_style 196 "❌ Vortex.exe not found!"
        echo
        read -p "Press Enter to continue..."
        return
    fi

    echo
    gum_style 82 "✅ Found Vortex at: $vortex_dir"

    if gum_confirm "Add to Steam?"; then
        local name=$(gum_input "Name for Steam:" "Vortex")
        [[ -z "$name" ]] && name="Vortex"
        add_game_to_steam "$name" "$vortex_dir/Vortex.exe" "$vortex_dir"
    fi
}

# ===================================================================
# Other Menus
# ===================================================================

limo_menu() {
    clear
    gum_style_box "🐧 Limo Setup" \
        "" \
        "Native Linux Mod Manager"

    echo
    gum_style 99 "Limo is a Linux-native mod manager."
    echo

    if gum_confirm "Configure a game for Limo?"; then
        if select_game; then
            install_dependencies
            local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
            echo
            gum_style 82 "✅ Game configured for Limo!"
            gum_style 99 "Prefix: $prefix_path"
        fi
    fi

    echo
    read -p "Press Enter to continue..."
}

ttw_menu() {
    clear
    gum_style_box "🌐 Tale of Two Wastelands" \
        "" \
        "🚧 Coming Soon! 🚧"

    echo
    gum_style 214 "TTW functionality is being implemented..."
    echo
    read -p "Press Enter to continue..."
}

hoolamike_menu() {
    clear
    gum_style_box "🛠️  Hoolamike Tools" \
        "" \
        "🚧 Coming Soon! 🚧"

    echo
    gum_style 214 "Hoolamike functionality is being implemented..."
    echo
    read -p "Press Enter to continue..."
}

sky_tex_menu() {
    clear
    gum_style_box "🖼️  Sky Texture Optimizer" \
        "" \
        "🚧 Coming Soon! 🚧"

    echo
    gum_style 214 "Sky Texture Optimizer functionality is being implemented..."
    echo
    read -p "Press Enter to continue..."
}

game_fixes_menu() {
    while true; do
        clear
        gum_style_box "🎮 Game-Specific Fixes"

        local choice=$("$GUM_BIN" choose \
            --height 10 \
            "🔫 Fallout New Vegas" \
            "🏔️  Enderal Special Edition" \
            "🐉 Baldur's Gate 3" \
            "📋 All Games Advice" \
            "🔙 Back")

        case "$choice" in
            *"Fallout"*) fnv_fixes ;;
            *"Enderal"*) enderal_fixes ;;
            *"Baldur"*) bg3_fixes ;;
            *"All Games"*) show_all_games_advice ;;
            *"Back"*|"") return ;;
        esac
    done
}

fnv_fixes() {
    clear
    gum_style_box "🔫 Fallout New Vegas Fixes"

    local compatdata="$STEAM_ROOT/steamapps/compatdata/22380"
    if [[ -d "$compatdata" ]]; then
        echo
        gum_style 99 "📋 Recommended launch options:"
        echo
        echo "STEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%"
        echo

        if gum_confirm "Install FNV dependencies?"; then
            SELECTED_APPID="22380"
            SELECTED_GAME="Fallout New Vegas"
            install_dependencies
        fi
    else
        gum_style 196 "❌ Fallout New Vegas not installed or not run yet"
    fi

    echo
    read -p "Press Enter to continue..."
}

enderal_fixes() {
    clear
    gum_style_box "🏔️  Enderal Special Edition Fixes"

    local compatdata="$STEAM_ROOT/steamapps/compatdata/976620"
    if [[ -d "$compatdata" ]]; then
        echo
        gum_style 99 "📋 Recommended launch options:"
        echo
        echo "STEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%"
        echo

        if gum_confirm "Install Enderal dependencies?"; then
            SELECTED_APPID="976620"
            SELECTED_GAME="Enderal Special Edition"
            install_dependencies
        fi
    else
        gum_style 196 "❌ Enderal SE not installed or not run yet"
    fi

    echo
    read -p "Press Enter to continue..."
}

bg3_fixes() {
    clear
    gum_style_box "🐉 Baldur's Gate 3 Fixes"

    echo
    gum_style 99 "📋 Recommended launch options:"
    echo
    echo "WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%"
    echo
    read -p "Press Enter to continue..."
}

show_all_games_advice() {
    clear
    gum_style_box "📋 All Games Launch Options"

    echo

    # Check each game
    if [[ -d "$STEAM_ROOT/steamapps/compatdata/22380" ]]; then
        gum_style 99 "🔫 Fallout New Vegas:"
        echo "STEAM_COMPAT_DATA_PATH=\"$STEAM_ROOT/steamapps/compatdata/22380\" %command%"
        echo
    fi

    if [[ -d "$STEAM_ROOT/steamapps/compatdata/976620" ]]; then
        gum_style 99 "🏔️  Enderal SE:"
        echo "STEAM_COMPAT_DATA_PATH=\"$STEAM_ROOT/steamapps/compatdata/976620\" %command%"
        echo
    fi

    gum_style 99 "🐉 Baldur's Gate 3:"
    echo "WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%"

    echo
    read -p "Press Enter to continue..."
}

remove_nxm_handlers() {
    clear
    gum_style_box "🗑️  Remove NXM Handlers"

    echo
    local found=0
    for handler in "$HOME/.local/share/applications"/*nxm-handler.desktop; do
        if [[ -f "$handler" ]]; then
            rm -f "$handler"
            ((found++))
            gum_style 99 "🗑️  Removed: $(basename "$handler")"
        fi
    done

    if [[ $found -gt 0 ]]; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        echo
        gum_style 82 "✅ Removed $found NXM handler(s)"
    else
        gum_style 214 "ℹ️  No NXM handlers found"
    fi

    echo
    read -p "Press Enter to continue..."
}

settings_menu() {
    while true; do
        clear
        gum_style_box "⚙️  Settings"

        local choice=$("$GUM_BIN" choose \
            --height 10 \
            "🖥️  Default DPI Scaling: $DEFAULT_SCALING" \
            "🔄 Check for Updates: $CHECK_UPDATES" \
            "📋 View Logs" \
            "🔙 Back")

        case "$choice" in
            *"DPI"*)
                local new_dpi=$(gum_input "Default DPI scaling:" "$DEFAULT_SCALING")
                if [[ -n "$new_dpi" ]]; then
                    DEFAULT_SCALING="$new_dpi"
                    sed -i "s/DEFAULT_SCALING=.*/DEFAULT_SCALING=$new_dpi/" "$CONFIG_FILE"
                fi
                ;;
            *"Updates"*)
                if [[ "$CHECK_UPDATES" == "true" ]]; then
                    CHECK_UPDATES="false"
                else
                    CHECK_UPDATES="true"
                fi
                sed -i "s/CHECK_UPDATES=.*/CHECK_UPDATES=$CHECK_UPDATES/" "$CONFIG_FILE"
                ;;
            *"Logs"*)
                clear
                gum_style_box "📋 Recent Logs"
                echo
                if [[ -f "$LOG_FILE" ]]; then
                    tail -n 30 "$LOG_FILE"
                else
                    gum_style 214 "No logs found"
                fi
                echo
                read -p "Press Enter to continue..."
                ;;
            *"Back"*|"") return ;;
        esac
    done
}

# ===================================================================
# Helper Functions
# ===================================================================

find_proton_path() {
    local proton_experimental="$STEAM_ROOT/steamapps/common/Proton - Experimental/proton"
    if [[ -f "$proton_experimental" ]]; then
        echo "$proton_experimental"
        return 0
    fi

    # Try other Proton versions
    local proton_path=$(find "$STEAM_ROOT/steamapps/common" -name "proton" -path "*/Proton*/proton" 2>/dev/null | sort -V | tail -1)
    if [[ -n "$proton_path" ]]; then
        echo "$proton_path"
        return 0
    fi

    return 1
}

setup_existing_mo2() {
    clear
    gum_style_box "📁 Setup Existing MO2"

    echo
    echo "Select MO2 directory:"
    local mo2_dir=$(gum_file)

    [[ -z "$mo2_dir" ]] && return

    # If file selected, use parent directory
    [[ -f "$mo2_dir" ]] && mo2_dir=$(dirname "$mo2_dir")

    if [[ ! -f "$mo2_dir/ModOrganizer.exe" ]]; then
        gum_style 196 "❌ ModOrganizer.exe not found!"
        echo
        read -p "Press Enter to continue..."
        return
    fi

    echo
    gum_style 82 "✅ Found MO2 at: $mo2_dir"

    if gum_confirm "Add to Steam?"; then
        local mo2_name=$(gum_input "Name for Steam:" "Mod Organizer 2")
        [[ -z "$mo2_name" ]] && mo2_name="Mod Organizer 2"

        add_game_to_steam "$mo2_name" "$mo2_dir/ModOrganizer.exe" "$mo2_dir"
    fi
}

# ===================================================================
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
