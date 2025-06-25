#!/bin/bash
# ===================================================================
# NaK (Linux Modding Helper) - Fixed Edition
# Version: 3.2.0 - Properly fixed UI
# ===================================================================

# Script metadata
readonly SCRIPT_VERSION="3.2.0"
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
declare -g SEVEN_ZIP=""

# Gum download info
readonly GUM_VERSION="0.14.5"
readonly GUM_URL="https://github.com/charmbracelet/gum/releases/download/v${GUM_VERSION}/gum_${GUM_VERSION}_Linux_x86_64.tar.gz"
readonly GUM_DIR="$SCRIPT_DIR/lib/gum"
readonly GUM_ARCHIVE="$GUM_DIR/gum.tar.gz"

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

    # Extract
    echo "📂 Extracting Gum..."
    cd "$GUM_DIR"
    tar -xzf "$GUM_ARCHIVE" || return 1
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

# ===================================================================
# Core Functions
# ===================================================================

init() {
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
            SEVEN_ZIP="$variant"
            break
        fi
    done
    [[ "$has_7z" == "false" ]] && missing+=("p7zip-full")

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "❌ Missing Dependencies"
        echo ""
        echo "Please install: ${missing[*]}"
        echo ""
        echo "Example:"
        echo "sudo apt install ${missing[*]}"
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

    echo "❌ Error: Steam installation not found!"
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
# Print centered header
# ===================================================================

print_centered() {
    local text="$1"
    local width=60
    local padding=$(( (width - ${#text}) / 2 ))
    printf "%*s%s%*s\n" $padding "" "$text" $padding ""
}

print_header() {
    echo "============================================================"
    print_centered "$SCRIPT_NAME v$SCRIPT_VERSION"
    echo "============================================================"
    echo ""
}

# ===================================================================
# Main Menu - Fixed to not have "Choose:" on the right
# ===================================================================

show_main_menu() {
    while true; do
        clear
        print_header

        # Use gum choose WITHOUT the --header option to avoid the "Choose:" text
        echo "Main Menu - Select an option (ESC or Ctrl+C to exit):"
        echo ""

        local choice=$("$GUM_BIN" choose \
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

        # Check if user pressed ESC/Ctrl+C (empty choice)
        if [[ -z "$choice" ]]; then
            break
        fi

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
            "Exit") break ;;
        esac
    done

    clear
    echo "👋 Thanks for using NaK!"
}

# ===================================================================
# MO2 Menu - Fixed
# ===================================================================

mo2_menu() {
    while true; do
        clear
        print_header
        echo "🎯 Mod Organizer 2 Setup"
        echo ""
        echo "Select an option (ESC to go back):"
        echo ""

        local choice=$("$GUM_BIN" choose \
            "Download Latest MO2" \
            "Setup Existing MO2" \
            "Install Dependencies" \
            "Configure NXM Handler" \
            "Configure DPI Scaling")

        # If empty (ESC pressed), go back
        if [[ -z "$choice" ]]; then
            return
        fi

        case "$choice" in
            "Download Latest MO2") download_mo2 ;;
            "Setup Existing MO2") setup_existing_mo2 ;;
            "Install Dependencies") select_game && install_dependencies ;;
            "Configure NXM Handler") select_game && setup_nxm_handler ;;
            "Configure DPI Scaling") select_game && setup_dpi_scaling ;;
        esac
    done
}

download_mo2() {
    clear
    echo "📥 Download Mod Organizer 2"
    echo "=========================="
    echo ""
    echo "Where would you like to install Mod Organizer 2?"
    echo "(Press TAB for auto-completion, leave empty to cancel)"
    echo ""

    local default_dir="$HOME/ModOrganizer2"
    read -e -p "Install directory [$default_dir]: " install_dir

    # Check if user wants to cancel
    if [[ "$install_dir" == "" ]] && [[ ! -t 0 ]]; then
        return
    fi

    # Use default if empty
    [[ -z "$install_dir" ]] && install_dir="$default_dir"

    # Expand tilde if present
    install_dir="${install_dir/#\~/$HOME}"

    # Ask about creating directory if it doesn't exist
    if [[ ! -d "$install_dir" ]]; then
        echo ""
        read -p "Directory doesn't exist. Create it? [Y/n]: " yn
        case $yn in
            [Nn]* ) return ;;
            * ) mkdir -p "$install_dir" ;;
        esac
    fi

    # Check if it already contains MO2
    if [[ -f "$install_dir/ModOrganizer.exe" ]]; then
        echo ""
        read -p "Directory already contains MO2. Overwrite? [y/N]: " yn
        case $yn in
            [Yy]* ) ;;
            * ) return ;;
        esac
    fi

    # Fetch release info
    echo ""
    echo "Fetching latest release info..."
    local release_info=$(curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest 2>/dev/null)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^Mod\\.Organizer-[0-9.]+\\.7z$")) | .browser_download_url')

    if [[ -z "$download_url" ]] || [[ "$download_url" == "null" ]]; then
        echo "❌ Could not find MO2 download URL!"
        read -p "Press Enter to continue..."
        return 1
    fi

    echo "✅ Found MO2 v$version"
    echo ""

    # Download with progress
    local archive="$TEMP_DIR/MO2-$version.7z"
    echo "Downloading MO2 v$version..."

    if ! curl -L -# -o "$archive" "$download_url"; then
        echo "❌ Download failed!"
        read -p "Press Enter to continue..."
        return 1
    fi

    # Extract
    echo ""
    echo "Extracting MO2..."
    if ! $SEVEN_ZIP x "$archive" -o"$install_dir" -y > /dev/null; then
        echo "❌ Extraction failed!"
        rm -f "$archive"
        read -p "Press Enter to continue..."
        return 1
    fi

    # Verify installation
    if [[ -f "$install_dir/ModOrganizer.exe" ]]; then
        echo ""
        echo "✅ MO2 v$version installed successfully!"
        echo "📁 Location: $install_dir"
        echo ""

        read -p "Add MO2 to Steam? [Y/n]: " yn
        case $yn in
            [Nn]* ) ;;
            * )
                echo ""
                read -e -p "Name for Steam [Mod Organizer 2]: " mo2_name
                [[ -z "$mo2_name" ]] && mo2_name="Mod Organizer 2"
                add_game_to_steam "$mo2_name" "$install_dir/ModOrganizer.exe" "$install_dir"
                ;;
        esac
    else
        echo "❌ Installation failed! ModOrganizer.exe not found."
    fi

    rm -f "$archive"
    echo ""
    read -p "Press Enter to continue..."
}

# ===================================================================
# Game Selection - Fixed to support ESC
# ===================================================================

select_game() {
    clear
    echo "🎮 Select Game"
    echo "============="
    echo ""
    echo "Fetching game list..."

    local games=($(get_steam_games))

    if [[ ${#games[@]} -eq 0 ]]; then
        echo "❌ No games found!"
        echo "Make sure you've run your games at least once through Steam."
        echo ""
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

    echo ""
    echo "Select a game (ESC to cancel):"
    echo ""

    local choice=$(printf '%s\n' "${display_games[@]}" | "$GUM_BIN" choose)

    # Check for ESC/cancel
    if [[ -z "$choice" ]]; then
        return 1
    fi

    # Extract appid from choice
    if [[ "$choice" =~ \[([0-9]+)\]$ ]]; then
        SELECTED_APPID="${BASH_REMATCH[1]}"
        SELECTED_GAME="${choice% \[*\]}"

        echo ""
        echo "✅ Selected: $SELECTED_GAME"
        sleep 1
        return 0
    fi

    return 1
}

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

# ===================================================================
# Other menus with ESC support
# ===================================================================

vortex_menu() {
    while true; do
        clear
        print_header
        echo "🔧 Vortex Setup"
        echo ""
        echo "Select an option (ESC to go back):"
        echo ""

        local choice=$("$GUM_BIN" choose \
            "Download Latest Vortex" \
            "Setup Existing Vortex" \
            "Install Dependencies" \
            "Configure NXM Handler" \
            "Configure DPI Scaling")

        if [[ -z "$choice" ]]; then
            return
        fi

        case "$choice" in
            "Download Latest Vortex") download_vortex ;;
            "Setup Existing Vortex") setup_existing_vortex ;;
            "Install Dependencies") select_game && install_dependencies ;;
            "Configure NXM Handler") select_game && setup_vortex_nxm_handler ;;
            "Configure DPI Scaling") select_game && setup_dpi_scaling ;;
        esac
    done
}

game_fixes_menu() {
    while true; do
        clear
        print_header
        echo "🎮 Game-Specific Fixes"
        echo ""
        echo "Select an option (ESC to go back):"
        echo ""

        local choice=$("$GUM_BIN" choose \
            "Fallout New Vegas" \
            "Enderal Special Edition" \
            "Baldur's Gate 3" \
            "All Games Advice")

        if [[ -z "$choice" ]]; then
            return
        fi

        case "$choice" in
            "Fallout New Vegas") fnv_fixes ;;
            "Enderal Special Edition") enderal_fixes ;;
            "Baldur's Gate 3") bg3_fixes ;;
            "All Games Advice") show_all_games_advice ;;
        esac
    done
}

settings_menu() {
    while true; do
        clear
        print_header
        echo "⚙️  Settings"
        echo ""
        echo "Select an option (ESC to go back):"
        echo ""

        local choice=$("$GUM_BIN" choose \
            "Default DPI Scaling: $DEFAULT_SCALING" \
            "Check for Updates: $CHECK_UPDATES" \
            "View Logs")

        if [[ -z "$choice" ]]; then
            return
        fi

        case "$choice" in
            "Default DPI"*)
                echo ""
                read -p "Default DPI scaling [$DEFAULT_SCALING]: " new_dpi
                if [[ -n "$new_dpi" ]]; then
                    DEFAULT_SCALING="$new_dpi"
                    sed -i "s/DEFAULT_SCALING=.*/DEFAULT_SCALING=$new_dpi/" "$CONFIG_FILE"
                fi
                ;;
            "Check for Updates"*)
                if [[ "$CHECK_UPDATES" == "true" ]]; then
                    CHECK_UPDATES="false"
                else
                    CHECK_UPDATES="true"
                fi
                sed -i "s/CHECK_UPDATES=.*/CHECK_UPDATES=$CHECK_UPDATES/" "$CONFIG_FILE"
                ;;
            "View Logs")
                clear
                echo "📋 Recent Logs"
                echo "============="
                echo ""
                if [[ -f "$LOG_FILE" ]]; then
                    tail -n 30 "$LOG_FILE"
                else
                    echo "No logs found"
                fi
                echo ""
                read -p "Press Enter to continue..."
                ;;
        esac
    done
}

# ===================================================================
# Simplified implementations for other functions
# ===================================================================

install_dependencies() {
    [[ -z "$SELECTED_GAME" ]] && return

    clear
    echo "📦 Installing Dependencies"
    echo "========================="
    echo "For: $SELECTED_GAME"
    echo ""

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
    for comp in "${components[@]}"; do
        echo "  • $comp"
    done
    echo ""

    read -p "Continue with installation? [Y/n]: " yn
    case $yn in
        [Nn]* ) return ;;
    esac

    # Run protontricks
    echo ""
    echo "Installing dependencies..."
    echo "This may take several minutes. Please be patient."
    echo ""

    if $PROTONTRICKS_CMD --no-bwrap "$SELECTED_APPID" -q "${components[@]}"; then
        echo ""
        echo "✅ Dependencies installed successfully!"
    else
        echo ""
        echo "⚠️  Some dependencies may have failed to install."
        echo "This is often normal - some components may already be installed."
    fi

    echo ""
    read -p "Press Enter to continue..."
}

setup_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    clear
    echo "🔗 Configure NXM Handler"
    echo "======================="
    echo "For: $SELECTED_GAME"
    echo ""
    echo "Enter the path to nxmhandler.exe:"
    echo "(Press TAB for auto-completion, leave empty to cancel)"
    echo ""

    read -e -p "nxmhandler.exe path: " nxmhandler_path

    [[ -z "$nxmhandler_path" ]] && return
    nxmhandler_path="${nxmhandler_path/#\~/$HOME}"

    if [[ ! -f "$nxmhandler_path" ]]; then
        echo "❌ File not found!"
        read -p "Press Enter to continue..."
        return
    fi

    # Verify it's an exe file
    if [[ ! "$nxmhandler_path" =~ \.exe$ ]]; then
        echo "❌ Please select an .exe file!"
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

    echo ""
    echo "✅ NXM handler configured successfully!"
    echo ""
    read -p "Press Enter to continue..."
}

setup_dpi_scaling() {
    [[ -z "$SELECTED_GAME" ]] && return

    clear
    echo "🖥️  Configure DPI Scaling"
    echo "======================="
    echo "For: $SELECTED_GAME"
    echo ""
    echo "Select DPI scaling (ESC to cancel):"
    echo ""

    local choice=$("$GUM_BIN" choose \
        "96 - Standard (100%)" \
        "120 - Medium (125%)" \
        "144 - Large (150%)" \
        "192 - Extra Large (200%)" \
        "Custom value")

    [[ -z "$choice" ]] && return

    local scale
    if [[ "$choice" == "Custom value" ]]; then
        echo ""
        read -p "Enter DPI value (96-240): " scale
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

    # Run with Proton
    local proton_path=$(find_proton_path)
    echo ""
    echo "Applying DPI scaling..."

    if env STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
        STEAM_COMPAT_DATA_PATH="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID" \
        "$proton_path" run cmd /c "Z:$batch_file" > /dev/null 2>&1; then

        echo ""
        echo "✅ DPI scaling set to $scale"
        echo "ℹ️  Restart the application to see changes."
    else
        echo ""
        echo "❌ Failed to apply DPI scaling"
    fi

    rm -f "$batch_file"
    echo ""
    read -p "Press Enter to continue..."
}

# Other stub functions
setup_existing_mo2() {
    clear
    echo "📁 Setup Existing MO2"
    echo "===================="
    echo ""
    echo "Enter the path to your existing MO2 installation:"
    echo "(Press TAB for auto-completion, leave empty to cancel)"
    echo ""

    read -e -p "MO2 directory: " mo2_dir

    [[ -z "$mo2_dir" ]] && return
    mo2_dir="${mo2_dir/#\~/$HOME}"

    if [[ ! -d "$mo2_dir" ]]; then
        echo "❌ Directory not found!"
        echo ""
        read -p "Press Enter to continue..."
        return
    fi

    if [[ ! -f "$mo2_dir/ModOrganizer.exe" ]]; then
        echo "❌ ModOrganizer.exe not found in this directory!"
        echo ""
        read -p "Press Enter to continue..."
        return
    fi

    echo ""
    echo "✅ Found MO2 at: $mo2_dir"

    read -p "Add to Steam? [Y/n]: " yn
    case $yn in
        [Nn]* ) ;;
        * )
            echo ""
            read -e -p "Name for Steam [Mod Organizer 2]: " mo2_name
            [[ -z "$mo2_name" ]] && mo2_name="Mod Organizer 2"
            add_game_to_steam "$mo2_name" "$mo2_dir/ModOrganizer.exe" "$mo2_dir"
            ;;
    esac
}

add_game_to_steam() {
    local game_name="$1"
    local exe_path="$2"
    local start_dir="${3:-$(dirname "$exe_path")}"

    echo ""
    echo "Adding to Steam..."
    echo ""
    echo "ℹ️  Please add the game manually to Steam:"
    echo "1. Open Steam"
    echo "2. Go to Games → Add a Non-Steam Game"
    echo "3. Browse and add: $exe_path"
    echo "4. Right-click the game → Properties"
    echo "5. Enable Proton compatibility"

    echo ""
    read -p "Press Enter when done..."
}

download_vortex() {
    clear
    echo "📥 Download Vortex"
    echo "=================="
    echo ""
    echo "Vortex download is not yet implemented."
    echo ""
    read -p "Press Enter to continue..."
}

setup_existing_vortex() {
    clear
    echo "📁 Setup Existing Vortex"
    echo "======================="
    echo ""
    echo "Vortex setup is not yet implemented."
    echo ""
    read -p "Press Enter to continue..."
}

setup_vortex_nxm_handler() {
    clear
    echo "🔗 Configure Vortex NXM Handler"
    echo "==============================="
    echo ""
    echo "Vortex NXM handler is not yet implemented."
    echo ""
    read -p "Press Enter to continue..."
}

limo_menu() {
    clear
    echo "🐧 Limo Setup"
    echo "============="
    echo ""
    echo "Limo is a Linux-native mod manager."
    echo ""

    read -p "Configure a game for Limo? [Y/n]: " yn
    case $yn in
        [Nn]* ) return ;;
    esac

    if select_game; then
        install_dependencies
        local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
        echo ""
        echo "✅ Game configured for Limo!"
        echo "Prefix: $prefix_path"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

ttw_menu() {
    clear
    echo "🌐 Tale of Two Wastelands"
    echo "========================"
    echo ""
    echo "TTW functionality is not yet implemented."
    echo ""
    read -p "Press Enter to continue..."
}

hoolamike_menu() {
    clear
    echo "🛠️  Hoolamike Tools"
    echo "=================="
    echo ""
    echo "Hoolamike functionality is not yet implemented."
    echo ""
    read -p "Press Enter to continue..."
}

sky_tex_menu() {
    clear
    echo "🖼️  Sky Texture Optimizer"
    echo "========================"
    echo ""
    echo "Sky Texture Optimizer functionality is not yet implemented."
    echo ""
    read -p "Press Enter to continue..."
}

fnv_fixes() {
    clear
    echo "🔫 Fallout New Vegas Fixes"
    echo "=========================="
    echo ""

    local compatdata="$STEAM_ROOT/steamapps/compatdata/22380"
    if [[ -d "$compatdata" ]]; then
        echo "Recommended launch options:"
        echo ""
        echo "STEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%"
        echo ""

        read -p "Install FNV dependencies? [Y/n]: " yn
        case $yn in
            [Nn]* ) ;;
            * )
                SELECTED_APPID="22380"
                SELECTED_GAME="Fallout New Vegas"
                install_dependencies
                ;;
        esac
    else
        echo "❌ Fallout New Vegas not installed or not run yet"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

enderal_fixes() {
    clear
    echo "🏔️  Enderal Special Edition Fixes"
    echo "================================"
    echo ""

    local compatdata="$STEAM_ROOT/steamapps/compatdata/976620"
    if [[ -d "$compatdata" ]]; then
        echo "Recommended launch options:"
        echo ""
        echo "STEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%"
        echo ""

        read -p "Install Enderal dependencies? [Y/n]: " yn
        case $yn in
            [Nn]* ) ;;
            * )
                SELECTED_APPID="976620"
                SELECTED_GAME="Enderal Special Edition"
                install_dependencies
                ;;
        esac
    else
        echo "❌ Enderal SE not installed or not run yet"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

bg3_fixes() {
    clear
    echo "🐉 Baldur's Gate 3 Fixes"
    echo "======================="
    echo ""
    echo "Recommended launch options:"
    echo ""
    echo "WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%"
    echo ""
    read -p "Press Enter to continue..."
}

show_all_games_advice() {
    clear
    echo "📋 All Games Launch Options"
    echo "=========================="
    echo ""

    # Check each game
    if [[ -d "$STEAM_ROOT/steamapps/compatdata/22380" ]]; then
        echo "Fallout New Vegas:"
        echo "STEAM_COMPAT_DATA_PATH=\"$STEAM_ROOT/steamapps/compatdata/22380\" %command%"
        echo ""
    fi

    if [[ -d "$STEAM_ROOT/steamapps/compatdata/976620" ]]; then
        echo "Enderal SE:"
        echo "STEAM_COMPAT_DATA_PATH=\"$STEAM_ROOT/steamapps/compatdata/976620\" %command%"
        echo ""
    fi

    echo "Baldur's Gate 3:"
    echo "WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%"

    echo ""
    read -p "Press Enter to continue..."
}

remove_nxm_handlers() {
    clear
    echo "🗑️  Remove NXM Handlers"
    echo "======================"
    echo ""

    local found=0
    for handler in "$HOME/.local/share/applications"/*nxm-handler.desktop; do
        if [[ -f "$handler" ]]; then
            rm -f "$handler"
            ((found++))
            echo "Removed: $(basename "$handler")"
        fi
    done

    if [[ $found -gt 0 ]]; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        echo ""
        echo "✅ Removed $found NXM handler(s)"
    else
        echo "ℹ️  No NXM handlers found"
    fi

    echo ""
    read -p "Press Enter to continue..."
}

# Helper function
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

# ===================================================================
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
