#!/bin/bash
# ===================================================================
# NaK (Linux Modding Helper) - Professional Gum Edition
# Version: 4.0.0 - With proper ESC handling and styling
# ===================================================================

# Script metadata
readonly SCRIPT_VERSION="4.0.0"
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
declare -g TERM_WIDTH=""

# Professional color scheme
readonly COLOR_SUCCESS="#04B575"
readonly COLOR_WARNING="#FFD700"
readonly COLOR_ERROR="#FF6B6B"
readonly COLOR_INFO="#5DADE2"
readonly COLOR_NEUTRAL="#95A5A6"
readonly COLOR_HEADER="#BD93F9"
readonly COLOR_ACCENT="#FF79C6"
readonly COLOR_TEXT="#F8F8F2"

# Gum download info
readonly GUM_VERSION="0.14.5"
readonly GUM_URL="https://github.com/charmbracelet/gum/releases/download/v${GUM_VERSION}/gum_${GUM_VERSION}_Linux_x86_64.tar.gz"
readonly GUM_DIR="$SCRIPT_DIR/lib/gum"
readonly GUM_ARCHIVE="$GUM_DIR/gum.tar.gz"

# ===================================================================
# Initialize terminal and theming
# ===================================================================

setup_terminal() {
    # Get terminal width for responsive design
    TERM_WIDTH=$(tput cols 2>/dev/null || echo 80)

    # Set up consistent gum theming via environment variables
    export GUM_CHOOSE_ITEM_FOREGROUND="$COLOR_NEUTRAL"
    export GUM_CHOOSE_SELECTED_FOREGROUND="$COLOR_SUCCESS"
    export GUM_CHOOSE_CURSOR_FOREGROUND="$COLOR_INFO"
    export GUM_CHOOSE_HEADER_FOREGROUND="$COLOR_HEADER"
    export GUM_CHOOSE_MATCH_FOREGROUND="$COLOR_ACCENT"

    export GUM_INPUT_CURSOR_FOREGROUND="$COLOR_INFO"
    export GUM_INPUT_PLACEHOLDER_FOREGROUND="$COLOR_NEUTRAL"
    export GUM_INPUT_PROMPT_FOREGROUND="$COLOR_HEADER"

    export GUM_CONFIRM_PROMPT_FOREGROUND="$COLOR_HEADER"
    export GUM_CONFIRM_SELECTED_FOREGROUND="$COLOR_SUCCESS"
    export GUM_CONFIRM_UNSELECTED_FOREGROUND="$COLOR_NEUTRAL"

    export GUM_STYLE_BORDER="rounded"
    export GUM_STYLE_BORDER_FOREGROUND="$COLOR_SUCCESS"

    # Handle SIGINT properly
    trap 'exit 130' INT
}

# ===================================================================
# Gum Setup
# ===================================================================

setup_gum() {
    "$GUM_BIN" style \
        --foreground "$COLOR_INFO" \
        --bold \
        "🔧 Setting up Gum TUI framework..."

    mkdir -p "$GUM_DIR"

    # Check if gum already exists
    if [[ -f "$GUM_DIR/gum" ]] && [[ -x "$GUM_DIR/gum" ]]; then
        GUM_BIN="$GUM_DIR/gum"
        "$GUM_BIN" style --foreground "$COLOR_SUCCESS" "✓ Gum already installed"
        return 0
    fi

    # Download gum
    "$GUM_BIN" style --foreground "$COLOR_INFO" "📦 Downloading Gum v${GUM_VERSION}..."
    if command -v curl &>/dev/null; then
        curl -L -o "$GUM_ARCHIVE" "$GUM_URL" || return 1
    elif command -v wget &>/dev/null; then
        wget -O "$GUM_ARCHIVE" "$GUM_URL" || return 1
    else
        echo "❌ Error: Neither curl nor wget found!"
        return 1
    fi

    # Extract
    "$GUM_BIN" style --foreground "$COLOR_INFO" "📂 Extracting Gum..."
    cd "$GUM_DIR"
    tar -xzf "$GUM_ARCHIVE" || return 1
    cd - > /dev/null

    # Clean up and verify
    rm -f "$GUM_ARCHIVE"
    chmod +x "$GUM_DIR/gum" 2>/dev/null || true

    if [[ -x "$GUM_DIR/gum" ]]; then
        GUM_BIN="$GUM_DIR/gum"
        "$GUM_BIN" style --foreground "$COLOR_SUCCESS" "✅ Gum installed successfully!"
        return 0
    else
        echo "❌ Error: Gum installation failed!"
        return 1
    fi
}

# ===================================================================
# UI Components with proper styling
# ===================================================================

show_header() {
    local title="${1:-$SCRIPT_NAME}"
    local width=$((TERM_WIDTH > 70 ? 70 : TERM_WIDTH - 4))

    clear
    "$GUM_BIN" style \
        --foreground "$COLOR_HEADER" \
        --bold \
        --align center \
        --width "$width" \
        --margin "1 0" \
        --border double \
        --border-foreground "$COLOR_ACCENT" \
        "$title$(echo -e '\n')Version $SCRIPT_VERSION"
}

show_section() {
    local title="$1"
    "$GUM_BIN" style \
        --foreground "$COLOR_INFO" \
        --bold \
        --margin "1 0" \
        "► $title"
}

show_success() {
    "$GUM_BIN" style \
        --foreground "$COLOR_SUCCESS" \
        --bold \
        "✅ $1"
}

show_error() {
    "$GUM_BIN" style \
        --foreground "$COLOR_ERROR" \
        --bold \
        "❌ $1"
}

show_warning() {
    "$GUM_BIN" style \
        --foreground "$COLOR_WARNING" \
        --bold \
        "⚠️  $1"
}

show_info() {
    "$GUM_BIN" style \
        --foreground "$COLOR_INFO" \
        "ℹ️  $1"
}

# Improved confirm with better styling
confirm_action() {
    local message="${1:-Continue?}"
    "$GUM_BIN" confirm \
        --prompt.foreground "$COLOR_HEADER" \
        --selected.background "$COLOR_SUCCESS" \
        "$message"
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

    # First, check if we can use echo with gum styling
    if command -v gum &>/dev/null; then
        GUM_BIN="gum"
    else
        GUM_BIN="echo"  # Fallback for initial setup
    fi

    # Setup terminal theming
    setup_terminal

    # Setup gum if needed
    if [[ "$GUM_BIN" == "echo" ]]; then
        # gum is not found system-wide, so let's try to set it up.
        if ! setup_gum; then
            # If the setup function fails, show an error and exit.
            echo "❌ Failed to set up Gum. Please check your internet connection."
            exit 1
        fi
    fi

    # Clear screen and show header
    show_header

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
        show_error "Missing Dependencies"
        echo ""
        show_info "Please install: ${missing[*]}"
        echo ""
        "$GUM_BIN" style --foreground "$COLOR_WARNING" "Example:"
        "$GUM_BIN" style --foreground "$COLOR_INFO" "sudo apt install ${missing[*]}"
        exit 1
    fi
}

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

    show_error "Steam installation not found!"
    exit 1
}

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
# Main Menu with proper ESC handling
# ===================================================================

show_main_menu() {
    while true; do
        show_header "NaK Main Menu"

        # Create styled header for the menu
        local menu_header=$("$GUM_BIN" style \
            --foreground "$COLOR_TEXT" \
            --faint \
            "Select an option • ESC to exit • ↑↓ to navigate")

        # Show menu with proper header
        local choice=$("$GUM_BIN" choose \
            --header "$menu_header" \
            --height 15 \
            "🎮 Mod Organizer 2 Setup" \
            "🔧 Vortex Setup" \
            "🐧 Limo Setup (Native Linux)" \
            "🌐 Tale of Two Wastelands" \
            "🛠️  Hoolamike Tools" \
            "🖼️  Sky Texture Optimizer" \
            "🎯 Game-Specific Fixes" \
            "🗑️  Remove NXM Handlers" \
            "⚙️  Settings" \
            "🚪 Exit")

        # Handle exit codes properly
        local exit_code=$?
        case $exit_code in
            0) ;; # User made a selection
            1) # ESC pressed
                clear
                show_info "Thanks for using NaK!"
                exit 0
                ;;
            130) # Ctrl+C
                exit 130
                ;;
            *) # Other error
                show_error "An error occurred (exit code: $exit_code)"
                exit $exit_code
                ;;
        esac

        # Process selection
        case "$choice" in
            "🎮 Mod Organizer 2 Setup") mo2_menu ;;
            "🔧 Vortex Setup") vortex_menu ;;
            "🐧 Limo Setup"*) limo_menu ;;
            "🌐 Tale of Two Wastelands") ttw_menu ;;
            "🛠️  Hoolamike Tools") hoolamike_menu ;;
            "🖼️  Sky Texture Optimizer") sky_tex_menu ;;
            "🎯 Game-Specific Fixes") game_fixes_menu ;;
            "🗑️  Remove NXM Handlers") remove_nxm_handlers ;;
            "⚙️  Settings") settings_menu ;;
            "🚪 Exit")
                clear
                show_info "Thanks for using NaK!"
                exit 0
                ;;
        esac
    done
}

# ===================================================================
# MO2 Menu with better styling
# ===================================================================

mo2_menu() {
    while true; do
        show_header "Mod Organizer 2 Setup"

        local menu_header=$("$GUM_BIN" style \
            --foreground "$COLOR_TEXT" \
            --faint \
            "Configure MO2 for Linux • ESC to go back")

        local choice=$("$GUM_BIN" choose \
            --header "$menu_header" \
            --height 10 \
            "📥 Download Latest MO2" \
            "📁 Setup Existing MO2" \
            "📦 Install Dependencies" \
            "🔗 Configure NXM Handler" \
            "🖥️  Configure DPI Scaling")

        # Handle ESC
        [[ $? -eq 1 ]] && return

        case "$choice" in
            "📥 Download Latest MO2") download_mo2 ;;
            "📁 Setup Existing MO2") setup_existing_mo2 ;;
            "📦 Install Dependencies") select_game && install_dependencies ;;
            "🔗 Configure NXM Handler") select_game && setup_nxm_handler ;;
            "🖥️  Configure DPI Scaling") select_game && setup_dpi_scaling ;;
        esac
    done
}

# ===================================================================
# Game Selection with better UX
# ===================================================================

select_game() {
    show_header "Game Selection"

    show_info "Fetching game list..."

    local games=($(get_steam_games))

    if [[ ${#games[@]} -eq 0 ]]; then
        show_error "No games found!"
        show_warning "Make sure you've run your games at least once through Steam."
        echo ""
        "$GUM_BIN" input --placeholder "Press Enter to continue..."
        return 1
    fi

    # Build display array
    local display_games=()
    for game in "${games[@]}"; do
        local appid="${game%%|*}"
        local name="${game#*|}"
        display_games+=("$name [$appid]")
    done

    local menu_header=$("$GUM_BIN" style \
        --foreground "$COLOR_TEXT" \
        --faint \
        "Select a game • Type to filter • ESC to cancel")

    local choice=$(printf '%s\n' "${display_games[@]}" | \
        "$GUM_BIN" choose \
        --header "$menu_header" \
        --height 15)

    # Handle ESC
    [[ $? -eq 1 ]] && return 1

    # Extract appid from choice
    if [[ "$choice" =~ \[([0-9]+)\]$ ]]; then
        SELECTED_APPID="${BASH_REMATCH[1]}"
        SELECTED_GAME="${choice% \[*\]}"

        show_success "Selected: $SELECTED_GAME"
        sleep 0.5
        return 0
    fi

    return 1
}

# ===================================================================
# Download MO2 with progress feedback
# ===================================================================

download_mo2() {
    show_header "Download Mod Organizer 2"

    show_section "Installation Directory"

    local default_dir="$HOME/ModOrganizer2"
    local install_dir=$("$GUM_BIN" input \
        --placeholder "Install directory (TAB for completion)" \
        --value "$default_dir" \
        --prompt.foreground "$COLOR_HEADER" \
        --prompt "> ")

    # Handle ESC/empty
    [[ -z "$install_dir" ]] && return

    # Expand tilde
    install_dir="${install_dir/#\~/$HOME}"

    # Check directory
    if [[ ! -d "$install_dir" ]]; then
        if confirm_action "Directory doesn't exist. Create it?"; then
            mkdir -p "$install_dir"
        else
            return
        fi
    fi

    # Check existing installation
    if [[ -f "$install_dir/ModOrganizer.exe" ]]; then
        if ! confirm_action "Directory already contains MO2. Overwrite?"; then
            return
        fi
    fi

    # Fetch release info with spinner
    show_info "Fetching latest release info..."

    local release_info=$(curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest 2>/dev/null &)
    "$GUM_BIN" spin --spinner dots --title "Contacting GitHub..." -- sleep 2
    wait

    release_info=$(curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest 2>/dev/null)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^Mod\\.Organizer-[0-9.]+\\.7z$")) | .browser_download_url')

    if [[ -z "$download_url" ]] || [[ "$download_url" == "null" ]]; then
        show_error "Could not find MO2 download URL!"
        "$GUM_BIN" input --placeholder "Press Enter to continue..."
        return 1
    fi

    show_success "Found MO2 v$version"

    # Download with progress
    local archive="$TEMP_DIR/MO2-$version.7z"

    # Use gum spin for download progress
    curl -L -o "$archive" "$download_url" 2>&1 | \
        "$GUM_BIN" spin --spinner meter --title "Downloading MO2 v$version..." --

    # Extract with spinner
    "$GUM_BIN" spin --spinner dots --title "Extracting MO2..." -- \
        $SEVEN_ZIP x "$archive" -o"$install_dir" -y > /dev/null

    # Verify installation
    if [[ -f "$install_dir/ModOrganizer.exe" ]]; then
        show_success "MO2 v$version installed successfully!"
        show_info "Location: $install_dir"

        if confirm_action "Add MO2 to Steam?"; then
            local mo2_name=$("$GUM_BIN" input \
                --placeholder "Name for Steam" \
                --value "Mod Organizer 2" \
                --prompt "> ")

            [[ -n "$mo2_name" ]] && add_game_to_steam "$mo2_name" "$install_dir/ModOrganizer.exe" "$install_dir"
        fi
    else
        show_error "Installation failed! ModOrganizer.exe not found."
    fi

    rm -f "$archive"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Other menus with consistent styling
# ===================================================================

game_fixes_menu() {
    while true; do
        show_header "Game-Specific Fixes"

        local menu_header=$("$GUM_BIN" style \
            --foreground "$COLOR_TEXT" \
            --faint \
            "Game-specific tweaks and fixes • ESC to go back")

        local choice=$("$GUM_BIN" choose \
            --header "$menu_header" \
            --height 10 \
            "🔫 Fallout New Vegas" \
            "🏔️  Enderal Special Edition" \
            "🐉 Baldur's Gate 3" \
            "📋 All Games Advice")

        [[ $? -eq 1 ]] && return

        case "$choice" in
            "🔫 Fallout New Vegas") fnv_fixes ;;
            "🏔️  Enderal Special Edition") enderal_fixes ;;
            "🐉 Baldur's Gate 3") bg3_fixes ;;
            "📋 All Games Advice") show_all_games_advice ;;
        esac
    done
}

settings_menu() {
    while true; do
        show_header "Settings"

        local menu_header=$("$GUM_BIN" style \
            --foreground "$COLOR_TEXT" \
            --faint \
            "Configure NaK • ESC to go back")

        local choice=$("$GUM_BIN" choose \
            --header "$menu_header" \
            --height 10 \
            "🖥️  Default DPI Scaling: $DEFAULT_SCALING" \
            "🔄 Check for Updates: $CHECK_UPDATES" \
            "📋 View Logs")

        [[ $? -eq 1 ]] && return

        case "$choice" in
            "🖥️  Default DPI"*)
                local new_dpi=$("$GUM_BIN" input \
                    --placeholder "Default DPI scaling" \
                    --value "$DEFAULT_SCALING" \
                    --prompt "> ")

                if [[ -n "$new_dpi" ]]; then
                    DEFAULT_SCALING="$new_dpi"
                    sed -i "s/DEFAULT_SCALING=.*/DEFAULT_SCALING=$new_dpi/" "$CONFIG_FILE"
                    show_success "DPI scaling updated to $new_dpi"
                fi
                ;;
            "🔄 Check for Updates"*)
                if [[ "$CHECK_UPDATES" == "true" ]]; then
                    CHECK_UPDATES="false"
                else
                    CHECK_UPDATES="true"
                fi
                sed -i "s/CHECK_UPDATES=.*/CHECK_UPDATES=$CHECK_UPDATES/" "$CONFIG_FILE"
                show_success "Update checking set to $CHECK_UPDATES"
                ;;
            "📋 View Logs")
                show_header "Recent Logs"
                if [[ -f "$LOG_FILE" ]]; then
                    tail -n 30 "$LOG_FILE" | "$GUM_BIN" pager
                else
                    show_warning "No logs found"
                fi
                ;;
        esac
    done
}

# ===================================================================
# Implementation stubs with proper styling
# ===================================================================

install_dependencies() {
    [[ -z "$SELECTED_GAME" ]] && return

    show_header "Installing Dependencies"
    show_section "For: $SELECTED_GAME"

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

    show_info "Components to install:"
    for comp in "${components[@]}"; do
        echo "  • $comp"
    done

    if ! confirm_action "Continue with installation?"; then
        return
    fi

    # Run protontricks with spinner
    "$GUM_BIN" spin --spinner dots --title "Installing dependencies..." -- \
        $PROTONTRICKS_CMD --no-bwrap "$SELECTED_APPID" -q "${components[@]}"

    if [[ $? -eq 0 ]]; then
        show_success "Dependencies installed successfully!"
    else
        show_warning "Some dependencies may have failed to install."
        show_info "This is often normal - some components may already be installed."
    fi

    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

setup_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    show_header "Configure NXM Handler"
    show_section "For: $SELECTED_GAME"

    local nxmhandler_path=$("$GUM_BIN" file \
        --all \
        --file \
        --directory false \
        ".")

    [[ -z "$nxmhandler_path" ]] && return
    nxmhandler_path="${nxmhandler_path/#\~/$HOME}"

    if [[ ! -f "$nxmhandler_path" ]]; then
        show_error "File not found!"
        "$GUM_BIN" input --placeholder "Press Enter to continue..."
        return
    fi

    if [[ ! "$nxmhandler_path" =~ \.exe$ ]]; then
        show_error "Please select an .exe file!"
        "$GUM_BIN" input --placeholder "Press Enter to continue..."
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

    show_success "NXM handler configured successfully!"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

setup_dpi_scaling() {
    [[ -z "$SELECTED_GAME" ]] && return

    show_header "Configure DPI Scaling"
    show_section "For: $SELECTED_GAME"

    local menu_header=$("$GUM_BIN" style \
        --foreground "$COLOR_TEXT" \
        --faint \
        "Select DPI scaling • ESC to cancel")

    local choice=$("$GUM_BIN" choose \
        --header "$menu_header" \
        "96 - Standard (100%)" \
        "120 - Medium (125%)" \
        "144 - Large (150%)" \
        "192 - Extra Large (200%)" \
        "Custom value")

    [[ $? -eq 1 ]] && return

    local scale
    if [[ "$choice" == "Custom value" ]]; then
        scale=$("$GUM_BIN" input \
            --placeholder "Enter DPI value (96-240)" \
            --prompt "> ")
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

    "$GUM_BIN" spin --spinner dots --title "Applying DPI scaling..." -- \
        env STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
            STEAM_COMPAT_DATA_PATH="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID" \
            "$proton_path" run cmd /c "Z:$batch_file"

    if [[ $? -eq 0 ]]; then
        show_success "DPI scaling set to $scale"
        show_info "Restart the application to see changes."
    else
        show_error "Failed to apply DPI scaling"
    fi

    rm -f "$batch_file"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

# Other stub implementations...
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

# Placeholder functions with proper styling
setup_existing_mo2() {
    show_header "Setup Existing MO2"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

vortex_menu() {
    show_header "Vortex Setup"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

limo_menu() {
    show_header "Limo Setup"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

ttw_menu() {
    show_header "Tale of Two Wastelands"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

hoolamike_menu() {
    show_header "Hoolamike Tools"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

sky_tex_menu() {
    show_header "Sky Texture Optimizer"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

fnv_fixes() {
    show_header "Fallout New Vegas Fixes"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

enderal_fixes() {
    show_header "Enderal Special Edition Fixes"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

bg3_fixes() {
    show_header "Baldur's Gate 3 Fixes"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

show_all_games_advice() {
    show_header "All Games Advice"
    show_warning "This feature is not yet implemented"
    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

remove_nxm_handlers() {
    show_header "Remove NXM Handlers"

    local found=0
    for handler in "$HOME/.local/share/applications"/*nxm-handler.desktop; do
        if [[ -f "$handler" ]]; then
            rm -f "$handler"
            ((found++))
            show_info "Removed: $(basename "$handler")"
        fi
    done

    if [[ $found -gt 0 ]]; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        show_success "Removed $found NXM handler(s)"
    else
        show_info "No NXM handlers found"
    fi

    "$GUM_BIN" input --placeholder "Press Enter to continue..."
}

add_game_to_steam() {
    local game_name="$1"
    local exe_path="$2"
    local start_dir="${3:-$(dirname "$exe_path")}"

    show_info "Please add the game manually to Steam:"
    "$GUM_BIN" style \
        --border normal \
        --padding "1 2" \
        --margin "1" \
        --border-foreground "$COLOR_INFO" \
        "1. Open Steam
2. Go to Games → Add a Non-Steam Game
3. Browse and add: $exe_path
4. Right-click the game → Properties
5. Enable Proton compatibility"

    "$GUM_BIN" input --placeholder "Press Enter when done..."
}

# ===================================================================
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
