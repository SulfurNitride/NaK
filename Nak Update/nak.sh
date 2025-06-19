#!/bin/bash
# ===================================================================
# NaK (Linux Modding Helper) - Beautiful Gum UI Version
# Version: 3.0.0
# ===================================================================

# Script metadata
readonly SCRIPT_VERSION="3.0.0"
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

# Gum Theme Setup
export GUM_INPUT_CURSOR_FOREGROUND="#00FF00"
export GUM_INPUT_PROMPT_FOREGROUND="#0080FF"
export GUM_STYLE_FOREGROUND="212"
export GUM_STYLE_BORDER="rounded"
export GUM_CONFIRM_SELECTED_FOREGROUND="230"
export GUM_CHOOSE_CURSOR_FOREGROUND="#00FF00"
export GUM_FILTER_MATCH_FOREGROUND="#00FF00"

# ===================================================================
# Core Functions
# ===================================================================

# Initialize
init() {
    # Create directories
    mkdir -p "$CONFIG_DIR" "$TEMP_DIR"

    # Setup logging
    touch "$LOG_FILE"
    log "Starting $SCRIPT_NAME v$SCRIPT_VERSION"

    # Check for gum
    if [[ ! -f "$GUM_BINARY" ]]; then
        echo "Gum not found. Installing..."
        install_gum
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
    local gum_url="https://github.com/charmbracelet/gum/releases/download/v0.16.1/gum_0.16.1_Linux_x86_64.tar.gz"
    local temp_file="$TEMP_DIR/gum.tar.gz"

    mkdir -p "$SCRIPT_DIR/bin"

    echo "Downloading gum..."
    if curl -L -o "$temp_file" "$gum_url"; then
        tar -xzf "$temp_file" -C "$SCRIPT_DIR/bin" gum
        chmod +x "$GUM_BINARY"
        echo "Gum installed successfully!"
    else
        echo "Failed to download gum. Some features may not work properly."
        sleep 2
    fi
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

# Check dependencies
check_dependencies() {
    local missing=()

    # Check for protontricks
    if command -v protontricks &> /dev/null; then
        PROTONTRICKS_CMD="protontricks"
    elif flatpak list --app 2>/dev/null | grep -q "com.github.Matoking.protontricks"; then
        PROTONTRICKS_CMD="flatpak run com.github.Matoking.protontricks"
    else
        missing+=("protontricks")
    fi

    # Check other dependencies
    for cmd in curl jq 7z; do
        if ! command -v "$cmd" &> /dev/null; then
            # Check alternatives for 7z
            if [[ "$cmd" == "7z" ]]; then
                command -v 7za &> /dev/null || command -v p7zip &> /dev/null || missing+=("p7zip-full")
            else
                missing+=("$cmd")
            fi
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        $GUM_BINARY style --foreground 196 --border double --padding "1 2" \
            "Missing dependencies: ${missing[*]}" \
            "" \
            "Install with: sudo apt install ${missing[*]}"
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

    $GUM_BINARY style --foreground 196 "Steam installation not found!"
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
# UI Functions
# ===================================================================

# Create banner
create_banner() {
    $GUM_BINARY style \
        --foreground "#FF6B6B" \
        --border double \
        --border-foreground "#45B7D1" \
        --align center \
        --width 60 \
        --margin "1 2" \
        --padding "2 4" \
        --bold \
        "$SCRIPT_NAME v$SCRIPT_VERSION"
}

# Show main menu
show_main_menu() {
    while true; do
        clear
        create_banner

        local choice=$($GUM_BINARY choose \
            --cursor.foreground "#00FF00" \
            --selected.foreground "#00FF00" \
            --selected.bold \
            "🎮 Mod Organizer 2 Setup" \
            "🔧 Vortex Setup" \
            "🐧 Limo Setup (Native Linux)" \
            "🏜️  Tale of Two Wastelands" \
            "🛠️  Hoolamike Tools" \
            "🖼️  Sky Texture Optimizer" \
            "🎯 Game-Specific Fixes" \
            "🗑️  Remove NXM Handlers" \
            "📊 View Logs" \
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
            "📊 View Logs") view_logs ;;
            "❌ Exit"|"")
                $GUM_BINARY style --foreground 46 "Thanks for using NaK!"
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
        $GUM_BINARY style --foreground 212 --border normal --padding "1 2" \
            "Mod Organizer 2 Setup"

        local choice=$($GUM_BINARY choose \
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

# Download MO2
download_mo2() {
    log "Starting MO2 download"

    # Get installation directory
    local install_base=$($GUM_BINARY file --directory)
    [[ -z "$install_base" ]] && return

    local install_dir="$install_base/ModOrganizer2"

    # Check if we need to rename
    if [[ -d "$install_dir" ]]; then
        if $GUM_BINARY confirm "Directory exists. Overwrite?"; then
            rm -rf "$install_dir"
        else
            local new_name=$($GUM_BINARY input --placeholder "Enter new directory name" --value "ModOrganizer2_new")
            install_dir="$install_base/$new_name"
        fi
    fi

    # Fetch release info
    local release_info
    release_info=$($GUM_BINARY spin --title "Fetching latest release info..." --show-output -- \
        curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^Mod\\.Organizer-[0-9.]+\\.7z$")) | .browser_download_url')

    if [[ -z "$download_url" ]]; then
        $GUM_BINARY style --foreground 196 "Could not find MO2 download URL!"
        return 1
    fi

    $GUM_BINARY style --foreground 46 "Found MO2 version: $version"

    # Confirm installation
    $GUM_BINARY style --border normal --padding "1 2" \
        "Version: $version" \
        "Install to: $install_dir"

    $GUM_BINARY confirm "Proceed with installation?" || return

    # Download
    local filename="MO2-$version.7z"
    local archive_path="$TEMP_DIR/$filename"

    $GUM_BINARY spin --title "Downloading MO2 v$version..." --show-output -- \
        curl -L -o "$archive_path" "$download_url"

    # Extract
    mkdir -p "$install_dir"

    $GUM_BINARY spin --title "Extracting MO2..." -- \
        7z x "$archive_path" -o"$install_dir" -y

    $GUM_BINARY style --foreground 46 --border double --padding "1 2" \
        "✓ MO2 v$version installed successfully!" \
        "" \
        "Location: $install_dir"

    # Add to Steam?
    if $GUM_BINARY confirm "Add MO2 to Steam?"; then
        add_to_steam "Mod Organizer 2" "$install_dir/ModOrganizer.exe" "$install_dir"
    fi

    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

# Setup existing MO2
setup_existing_mo2() {
    local mo2_exe=$($GUM_BINARY file)
    [[ -z "$mo2_exe" ]] && return

    # Check if user wants to rename
    local exe_name=$(basename "$mo2_exe")
    if [[ "$exe_name" != "ModOrganizer.exe" ]]; then
        $GUM_BINARY style --foreground 196 "Please select ModOrganizer.exe!"
        $GUM_BINARY input --placeholder "Press Enter to continue..."
        return
    fi

    local mo2_dir=$(dirname "$mo2_exe")

    $GUM_BINARY style --foreground 46 --border normal --padding "1 2" \
        "Found MO2 at:" \
        "$mo2_dir"

    if $GUM_BINARY confirm "Add this MO2 to Steam?"; then
        add_to_steam "Mod Organizer 2" "$mo2_exe" "$mo2_dir"
    fi
}

# ===================================================================
# Game Selection
# ===================================================================

select_game() {
    $GUM_BINARY style --foreground 99 "Scanning for games..."

    local games_output=$($PROTONTRICKS_CMD -l 2>&1)
    local -a games=()

    while IFS= read -r line; do
        if [[ "$line" =~ (.*)\(([0-9]+)\) ]]; then
            local name="${BASH_REMATCH[1]}"
            local appid="${BASH_REMATCH[2]}"
            name=$(echo "$name" | xargs)

            if [[ ! "$name" =~ (SteamVR|Proton|Steam Linux Runtime) ]]; then
                games+=("$appid:$name")
            fi
        fi
    done <<< "$games_output"

    if [[ ${#games[@]} -eq 0 ]]; then
        $GUM_BINARY style --foreground 196 "No games found!"
        return 1
    fi

    # Create display array
    local -a display_games=()
    for game in "${games[@]}"; do
        IFS=':' read -r appid name <<< "$game"
        display_games+=("$name [$appid]")
    done

    local selected=$($GUM_BINARY filter --placeholder "Type to search games..." <<< "$(printf '%s\n' "${display_games[@]}")")
    [[ -z "$selected" ]] && return 1

    # Extract appid from selection
    SELECTED_APPID=$(echo "$selected" | grep -oP '\[\K[0-9]+(?=\])')
    SELECTED_GAME=$(echo "$selected" | sed 's/ \[[0-9]*\]$//')

    log "Selected game: $SELECTED_GAME (AppID: $SELECTED_APPID)"
    return 0
}

# ===================================================================
# Dependencies Installation
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

    # Game-specific components
    case "$SELECTED_APPID" in
        22380) components+=("d3dx9") ;; # Fallout NV
        976620) components+=("d3dx11_43" "d3dcompiler_43" "dotnet6" "dotnet7") ;; # Enderal
    esac

    $GUM_BINARY style --border normal --padding "1 2" \
        "Installing dependencies for:" \
        "$SELECTED_GAME"

    $GUM_BINARY confirm "Install ${#components[@]} components?" || return

    # Install with progress
    local total=${#components[@]}
    local current=0

    for comp in "${components[@]}"; do
        ((current++))

        $GUM_BINARY style --foreground 99 "[$current/$total] Installing: $comp"

        $GUM_BINARY spin --title "Installing $comp..." -- \
            $PROTONTRICKS_CMD --no-bwrap "$SELECTED_APPID" -q "$comp"
    done

    # Enable dotfiles visibility
    local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
    if [[ -d "$prefix_path" ]]; then
        $GUM_BINARY spin --title "Enabling hidden files visibility..." -- \
            run_with_proton_wine "$prefix_path" "reg" "add" "HKCU\\Software\\Wine" "/v" "ShowDotFiles" "/d" "Y" "/f"
    fi

    $GUM_BINARY style --foreground 46 --border double --padding "1 2" \
        "✓ Dependencies installed successfully!"

    $GUM_BINARY input --placeholder "Press Enter to continue..."
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

# Find Proton
find_proton_path() {
    find "$STEAM_ROOT" -name "proton" -path "*/Proton - Experimental/*" 2>/dev/null | head -1
}

# ===================================================================
# NXM Handler
# ===================================================================

setup_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    $GUM_BINARY style --border normal --padding "1 2" \
        "Setting up NXM handler for:" \
        "$SELECTED_GAME"

    local handler_path=$($GUM_BINARY file)
    [[ -z "$handler_path" ]] && return

    # Validate file
    if [[ "$(basename "$handler_path")" != "nxmhandler.exe" ]]; then
        if ! $GUM_BINARY confirm "This doesn't look like nxmhandler.exe. Continue anyway?"; then
            return
        fi
    fi

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

    $GUM_BINARY style --foreground 46 --border double --padding "1 2" \
        "✓ NXM handler configured successfully!"

    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

# ===================================================================
# DPI Scaling
# ===================================================================

setup_dpi_scaling() {
    [[ -z "$SELECTED_GAME" ]] && return

    local scale=$($GUM_BINARY choose \
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
            scale=$($GUM_BINARY input --placeholder "Enter DPI value (96-240)" --value "120")
            ;;
        *) return ;;
    esac

    local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"

    $GUM_BINARY spin --title "Applying DPI scaling..." -- bash -c "
        run_with_proton_wine '$prefix_path' reg add 'HKCU\\Control Panel\\Desktop' /v LogPixels /t REG_DWORD /d $scale /f
        run_with_proton_wine '$prefix_path' reg add 'HKCU\\Software\\Wine\\X11 Driver' /v LogPixels /t REG_DWORD /d $scale /f
    "

    $GUM_BINARY style --foreground 46 --border double --padding "1 2" \
        "✓ DPI scaling set to $scale" \
        "" \
        "Restart the application for changes to take effect"

    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Additional Menus (Placeholders)
# ===================================================================

vortex_menu() {
    $GUM_BINARY style --border normal --padding "1 2" \
        "Vortex functionality coming soon!"
    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

limo_menu() {
    $GUM_BINARY style --border normal --padding "1 2" \
        "Limo functionality coming soon!"
    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

ttw_menu() {
    $GUM_BINARY style --border normal --padding "1 2" \
        "TTW functionality coming soon!"
    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

hoolamike_menu() {
    $GUM_BINARY style --border normal --padding "1 2" \
        "Hoolamike functionality coming soon!"
    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

sky_tex_menu() {
    $GUM_BINARY style --border normal --padding "1 2" \
        "Sky Texture Optimizer functionality coming soon!"
    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

game_fixes_menu() {
    while true; do
        clear
        $GUM_BINARY style --foreground 212 --border normal --padding "1 2" \
            "Game-Specific Fixes"

        local choice=$($GUM_BINARY choose \
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

fnv_fixes() {
    local compatdata=$(find_game_compatdata "22380")

    if [[ -n "$compatdata" ]]; then
        $GUM_BINARY style --border double --padding "1 2" \
            "Fallout New Vegas Launch Options:" \
            "" \
            "STEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%"
    else
        $GUM_BINARY style --foreground 196 \
            "Fallout New Vegas not found or not run yet!"
    fi

    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

enderal_fixes() {
    local compatdata=$(find_game_compatdata "976620")

    if [[ -n "$compatdata" ]]; then
        $GUM_BINARY style --border double --padding "1 2" \
            "Enderal SE Launch Options:" \
            "" \
            "STEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%"
    else
        $GUM_BINARY style --foreground 196 \
            "Enderal SE not found or not run yet!"
    fi

    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

bg3_fixes() {
    local compatdata=$(find_game_compatdata "1086940")

    if [[ -n "$compatdata" ]]; then
        $GUM_BINARY style --border double --padding "1 2" \
            "Baldur's Gate 3 Launch Options:" \
            "" \
            "WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%"
    else
        $GUM_BINARY style --foreground 196 \
            "Baldur's Gate 3 not found or not run yet!"
    fi

    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

show_all_advice() {
    $GUM_BINARY style --border double --padding "1 2" \
        "Checking all games..." \
        "This feature is under development"

    $GUM_BINARY input --placeholder "Press Enter to continue..."
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
        $GUM_BINARY style --foreground 46 "✓ Removed $found NXM handler(s)"
    else
        $GUM_BINARY style --foreground 99 "No NXM handlers found"
    fi

    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

view_logs() {
    if [[ -f "$LOG_FILE" ]]; then
        $GUM_BINARY pager < "$LOG_FILE"
    else
        $GUM_BINARY style --foreground 196 "No log file found"
        $GUM_BINARY input --placeholder "Press Enter to continue..."
    fi
}

# ===================================================================
# Utility Functions
# ===================================================================

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

# Add to Steam
add_to_steam() {
    local name="$1"
    local exe_path="$2"
    local start_dir="${3:-$(dirname "$exe_path")}"

    log "Adding $name to Steam"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        $GUM_BINARY style --foreground 196 "Python 3 required to add games to Steam!"
        return 1
    fi

    # Install vdf if needed
    if ! python3 -c "import vdf" 2>/dev/null; then
        $GUM_BINARY spin --title "Installing vdf module..." -- \
            python3 -m pip install --user vdf
    fi

    # Run Python script to add to Steam
    local result=$($GUM_BINARY spin --title "Adding to Steam..." --show-output -- python3 - << EOF
import sys
import os
import vdf
import time

steam_root = "$STEAM_ROOT"
game_name = "$name"
exe_path = "$exe_path"
start_dir = "$start_dir"

app_id = abs(hash(game_name + exe_path)) % 1000000000
shortcuts_path = os.path.join(steam_root, "userdata")

success = False
for user_dir in os.listdir(shortcuts_path):
    shortcuts_file = os.path.join(shortcuts_path, user_dir, "config", "shortcuts.vdf")
    os.makedirs(os.path.dirname(shortcuts_file), exist_ok=True)

    data = {"shortcuts": {}}
    if os.path.exists(shortcuts_file):
        try:
            with open(shortcuts_file, 'rb') as f:
                loaded = vdf.binary_load(f)
                if loaded and "shortcuts" in loaded:
                    data = loaded
        except:
            pass

    # Check if already exists
    exists = False
    for shortcut in data["shortcuts"].values():
        if shortcut.get("AppName") == game_name:
            exists = True
            break

    if not exists:
        idx = str(len(data["shortcuts"]))
        data["shortcuts"][idx] = {
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

        with open(shortcuts_file, 'wb') as f:
            vdf.binary_dump(data, f)

        success = True
        print(f"SUCCESS:{app_id}")

if not success:
    print("ALREADY_EXISTS")
EOF
)

    if [[ "$result" == SUCCESS:* ]]; then
        local app_id="${result#SUCCESS:}"
        $GUM_BINARY style --foreground 46 --border double --padding "1 2" \
            "✓ Added to Steam successfully!" \
            "AppID: $app_id" \
            "" \
            "Restart Steam and set Proton compatibility"
    elif [[ "$result" == "ALREADY_EXISTS" ]]; then
        $GUM_BINARY style --foreground 99 "$name is already in Steam"
    else
        $GUM_BINARY style --foreground 196 "Failed to add to Steam"
    fi

    $GUM_BINARY input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
