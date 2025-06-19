#!/bin/bash
# ===================================================================
# NaK (Linux Modding Helper) - Complete Version with Gum UI
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

# Default component list
declare -a components=()

# Gum Theme Setup - Centered and styled
export GUM_INPUT_CURSOR_FOREGROUND="#00FF00"
export GUM_INPUT_PROMPT_FOREGROUND="#0080FF"
export GUM_STYLE_FOREGROUND="212"
export GUM_STYLE_BORDER="rounded"
export GUM_CONFIRM_SELECTED_FOREGROUND="230"
export GUM_CHOOSE_CURSOR_FOREGROUND="#00FF00"
export GUM_FILTER_MATCH_FOREGROUND="#00FF00"
export GUM_STYLE_ALIGN="center"
export GUM_CHOOSE_SELECTED_FOREGROUND="#FFD700"

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
                echo "Contents of temp directory:"
                find "$TEMP_DIR" -type f -ls
                exit 1
            fi
        else
            echo "Error: Failed to extract gum archive"
            exit 1
        fi
    else
        echo "Failed to download gum. Please check your internet connection."
        echo "You can manually download from: $gum_url"
        exit 1
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
        "$GUM_BINARY" style --foreground 196 --border double --padding "1 2" --align center \
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

    "$GUM_BINARY" style --foreground 196 --align center "Steam installation not found!"
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
# UI Functions
# ===================================================================

# Create banner
create_banner() {
    "$GUM_BINARY" style \
        --foreground "#FF6B6B" \
        --border double \
        --border-foreground "#45B7D1" \
        --align center \
        --width 70 \
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
            "⚙️  Settings") settings_menu ;;
            "📊 View Logs") view_logs ;;
            "❌ Exit"|"")
                "$GUM_BINARY" style --foreground 46 --align center "Thanks for using NaK!"
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
        "$GUM_BINARY" style --foreground 212 --border normal --padding "1 2" --align center \
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

# Download MO2
download_mo2() {
    log "Starting MO2 download"

    # Show info about MO2
    "$GUM_BINARY" style --border normal --padding "1 2" --align center \
        "Mod Organizer 2 Download" \
        "" \
        "This will download the latest MO2 release from GitHub"

    # Get installation directory using file picker
    "$GUM_BINARY" style --foreground 99 --align center "Select installation directory:"
    local install_base=$("$GUM_BINARY" file --directory)
    [[ -z "$install_base" ]] && return

    local install_dir="$install_base/ModOrganizer2"

    # Check if directory exists
    if [[ -d "$install_dir" ]]; then
        if "$GUM_BINARY" confirm "Directory exists. Overwrite?"; then
            rm -rf "$install_dir"
        else
            local new_name=$("$GUM_BINARY" input --placeholder "Enter new directory name" --value "ModOrganizer2_new")
            install_dir="$install_base/$new_name"
        fi
    fi

    # Fetch release info
    local release_info
    release_info=$("$GUM_BINARY" spin --spinner dot --title "Fetching latest release info..." --show-output -- \
        curl -s https://api.github.com/repos/ModOrganizer2/modorganizer/releases/latest)

    local version=$(echo "$release_info" | jq -r '.tag_name' | sed 's/^v//')
    local download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^Mod\\.Organizer-[0-9.]+\\.7z$")) | .browser_download_url')

    if [[ -z "$download_url" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "Could not find MO2 download URL!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return 1
    fi

    "$GUM_BINARY" style --foreground 46 --align center "Found MO2 version: $version"

    # Confirm installation
    "$GUM_BINARY" style --border normal --padding "1 2" --align center \
        "Ready to install:" \
        "" \
        "Version: $version" \
        "Location: $install_dir"

    "$GUM_BINARY" confirm "Proceed with installation?" || return

    # Download
    local filename="MO2-$version.7z"
    local archive_path="$TEMP_DIR/$filename"

    "$GUM_BINARY" spin --spinner dot --title "Downloading MO2 v$version..." --show-output -- \
        curl -L -o "$archive_path" "$download_url"

    # Extract
    mkdir -p "$install_dir"

    "$GUM_BINARY" spin --spinner dot --title "Extracting MO2..." -- \
        7z x "$archive_path" -o"$install_dir" -y

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
        "✓ MO2 v$version installed successfully!" \
        "" \
        "Location: $install_dir"

    # Add to Steam?
    if "$GUM_BINARY" confirm "Add MO2 to Steam?"; then
        add_to_steam "Mod Organizer 2" "$install_dir/ModOrganizer.exe" "$install_dir"
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Setup existing MO2
setup_existing_mo2() {
    "$GUM_BINARY" style --foreground 99 --align center "Select ModOrganizer.exe:"
    local mo2_exe=$("$GUM_BINARY" file)
    [[ -z "$mo2_exe" ]] && return

    # Validate selection
    if [[ "$(basename "$mo2_exe")" != "ModOrganizer.exe" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "Please select ModOrganizer.exe!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    local mo2_dir=$(dirname "$mo2_exe")

    "$GUM_BINARY" style --foreground 46 --border normal --padding "1 2" --align center \
        "Found MO2 at:" \
        "$mo2_dir"

    if "$GUM_BINARY" confirm "Add this MO2 to Steam?"; then
        add_to_steam "Mod Organizer 2" "$mo2_exe" "$mo2_dir"
    fi
}

# ===================================================================
# Vortex Functions
# ===================================================================

vortex_menu() {
    while true; do
        clear
        "$GUM_BINARY" style --foreground 212 --border normal --padding "1 2" --align center \
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
        "$GUM_BINARY" style --foreground 196 --align center "Could not find Vortex download URL!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return 1
    fi

    "$GUM_BINARY" style --foreground 46 --align center "Found Vortex version: $version"

    # Get installation directory
    "$GUM_BINARY" style --foreground 99 --align center "Enter installation directory:"
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
        "$GUM_BINARY" style --foreground 99 --align center "Installing with system Wine..."
        WINEPREFIX="$HOME/.wine" wine "$installer" /S "/D=Z:$(echo "$install_dir" | sed 's|/|\\|g')"
    else
        # Use Proton
        if select_game; then
            local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
            "$GUM_BINARY" style --foreground 99 --align center "Installing with Proton..."
            run_with_proton_wine "$prefix_path" "$installer" "/S" "/D=Z:$(echo "$install_dir" | sed 's|/|\\|g')"
        else
            "$GUM_BINARY" style --foreground 196 --align center "Wine not found and no game selected for Proton!"
            "$GUM_BINARY" input --placeholder "Press Enter to continue..."
            return 1
        fi
    fi

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
        "✓ Vortex v$version installed!" \
        "" \
        "Location: $install_dir"

    if "$GUM_BINARY" confirm "Add Vortex to Steam?"; then
        add_to_steam "Vortex" "$install_dir/Vortex.exe" "$install_dir"
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Setup existing Vortex
setup_existing_vortex() {
    "$GUM_BINARY" style --foreground 99 --align center "Select Vortex.exe:"
    local vortex_exe=$("$GUM_BINARY" file)
    [[ -z "$vortex_exe" ]] && return

    if [[ "$(basename "$vortex_exe")" != "Vortex.exe" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "Please select Vortex.exe!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    local vortex_dir=$(dirname "$vortex_exe")

    "$GUM_BINARY" style --foreground 46 --border normal --padding "1 2" --align center \
        "Found Vortex at:" \
        "$vortex_dir"

    if "$GUM_BINARY" confirm "Add this Vortex to Steam?"; then
        add_to_steam "Vortex" "$vortex_exe" "$vortex_dir"
    fi
}

# Setup Vortex NXM handler
setup_vortex_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    "$GUM_BINARY" style --border normal --padding "1 2" --align center \
        "Setting up NXM handler for Vortex" \
        "Using: $SELECTED_GAME"

    "$GUM_BINARY" style --foreground 99 --align center "Select Vortex.exe:"
    local vortex_path=$("$GUM_BINARY" file)
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

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
        "✓ Vortex NXM handler configured!"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Limo Functions
# ===================================================================

limo_menu() {
    "$GUM_BINARY" style --border normal --padding "1 2" --align center \
        "Limo Setup" \
        "" \
        "Limo is a Linux-native mod manager" \
        "This will install dependencies for your game prefixes"

    if select_game; then
        install_dependencies

        local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
        "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
            "✓ Dependencies installed for $SELECTED_GAME" \
            "" \
            "Prefix path:" \
            "$prefix_path"

        if "$GUM_BINARY" confirm "Configure another game for Limo?"; then
            limo_menu
        fi
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Tale of Two Wastelands Functions
# ===================================================================

ttw_menu() {
    while true; do
        clear

        # Check Hoolamike status
        local hoolamike_status="❌ Not Installed"
        [[ -f "$HOME/Hoolamike/hoolamike" ]] && hoolamike_status="✅ Installed"

        "$GUM_BINARY" style --foreground 212 --border normal --padding "1 2" --align center \
            "Tale of Two Wastelands Setup" \
            "" \
            "Hoolamike: $hoolamike_status"

        local choice=$("$GUM_BINARY" choose \
            --height 10 \
            "🚀 Automated TTW Setup (All Steps)" \
            "📥 Download/Update Hoolamike" \
            "💉 Install FNV Dependencies" \
            "🎮 Run TTW Installation" \
            "📚 View Documentation" \
            "⬅️  Back to Main Menu")

        case "$choice" in
            "🚀 Automated TTW Setup"*) automated_ttw_setup ;;
            "📥 Download/Update Hoolamike") download_hoolamike ;;
            "💉 Install FNV Dependencies") install_fnv_dependencies ;;
            "🎮 Run TTW Installation") run_ttw_installation ;;
            "📚 View Documentation") view_ttw_docs ;;
            "⬅️  Back"*|"") return ;;
        esac
    done
}

# Download Hoolamike
download_hoolamike() {
    local hoolamike_dir="$HOME/Hoolamike"

    if [[ -d "$hoolamike_dir" ]]; then
        if ! "$GUM_BINARY" confirm "Hoolamike exists. Update to latest version?"; then
            return
        fi
        rm -rf "$hoolamike_dir"
    fi

    mkdir -p "$hoolamike_dir"

    # Fetch latest release
    local release_url=$("$GUM_BINARY" spin --spinner dot --title "Fetching latest release..." --show-output -- \
        curl -s https://api.github.com/repos/Niedzwiedzw/hoolamike/releases/latest | \
        jq -r '.assets[] | select(.name | test("hoolamike.*linux"; "i")) | .browser_download_url')

    if [[ -z "$release_url" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "Could not find Hoolamike download!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return 1
    fi

    # Download and extract
    "$GUM_BINARY" spin --spinner dot --title "Downloading Hoolamike..." -- bash -c "
        cd '$hoolamike_dir' && curl -L '$release_url' | tar -xz
    "

    # Generate config
    generate_hoolamike_config

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
        "✓ Hoolamike installed successfully!" \
        "" \
        "Next steps:" \
        "1. Download TTW .mpi file from:" \
        "   https://mod.pub/ttw/133/files" \
        "2. Place in: $hoolamike_dir" \
        "3. Run TTW installation"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Generate Hoolamike config
generate_hoolamike_config() {
    local config_file="$HOME/Hoolamike/hoolamike.yaml"

    # Find game directories
    local fo3_dir=$(find_game_dir "Fallout 3 goty")
    local fnv_dir=$(find_game_dir "Fallout New Vegas")

    cat > "$config_file" << EOF
# Auto-generated hoolamike.yaml
downloaders:
  downloads_directory: "$HOME/Hoolamike/Mod_Downloads"
  nexus:
    api_key: "YOUR_API_KEY_HERE"

installation:
  wabbajack_file_path: "./wabbajack"
  installation_path: "$HOME/ModdedGames"

games:
EOF

    [[ -n "$fo3_dir" ]] && cat >> "$config_file" << EOF
  Fallout3:
    root_directory: "$fo3_dir"
EOF

    [[ -n "$fnv_dir" ]] && cat >> "$config_file" << EOF
  FalloutNewVegas:
    root_directory: "$fnv_dir"
EOF

    cat >> "$config_file" << EOF

fixup:
  game_resolution: 1920x1080

extras:
  tale_of_two_wastelands:
    path_to_ttw_mpi_file: "./YOUR_TTW_MPI_FILE.mpi"
    variables:
      DESTINATION: "./TTW_Output"
EOF

    log "Generated hoolamike.yaml"
}

# Install FNV dependencies
install_fnv_dependencies() {
    SELECTED_APPID="22380"
    SELECTED_GAME="Fallout New Vegas"

    components=(
        fontsmooth=rgb
        xact
        xact_x64
        d3dx9_43
        d3dx9
        vcrun2022
    )

    "$GUM_BINARY" style --border normal --padding "1 2" --align center \
        "Installing Fallout New Vegas dependencies" \
        "" \
        "Required for TTW to function properly"

    install_dependencies
}

# Run TTW installation
run_ttw_installation() {
    if [[ ! -f "$HOME/Hoolamike/hoolamike" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "Hoolamike not installed!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    # Check for MPI file
    if ! ls "$HOME/Hoolamike"/*.mpi &>/dev/null; then
        "$GUM_BINARY" style --foreground 196 --border normal --padding "1 2" --align center \
            "No TTW .mpi file found!" \
            "" \
            "Download from: https://mod.pub/ttw/133/files" \
            "Place in: $HOME/Hoolamike/"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    cd "$HOME/Hoolamike"
    ./hoolamike tale-of-two-wastelands

    "$GUM_BINARY" style --foreground 46 --align center "TTW installation completed!"
    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# View TTW documentation
view_ttw_docs() {
    "$GUM_BINARY" style --border double --padding "1 2" --align center \
        "Tale of Two Wastelands Resources" \
        "" \
        "Official Website:" \
        "https://taleoftwowastelands.com/" \
        "" \
        "Installation Guide:" \
        "https://taleoftwowastelands.com/wiki_ttw/get-started/" \
        "" \
        "TTW Discord:" \
        "https://discord.gg/taleoftwowastelands" \
        "" \
        "Requirements:" \
        "- Fallout 3 GOTY Edition" \
        "- Fallout New Vegas Ultimate Edition" \
        "- TTW .mpi installer file" \
        "" \
        "Linux Tips:" \
        "- Install FNV dependencies first" \
        "- Run both games once before TTW" \
        "- Installation can take 2-4 hours"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Automated TTW setup
automated_ttw_setup() {
    "$GUM_BINARY" style --border normal --padding "1 2" --align center \
        "Automated TTW Setup" \
        "" \
        "This will:" \
        "1. Download Hoolamike" \
        "2. Install FNV dependencies" \
        "3. Wait for TTW .mpi file" \
        "4. Run TTW installation" \
        "" \
        "This process takes several hours!"

    "$GUM_BINARY" confirm "Start automated setup?" || return

    # Run each step
    download_hoolamike
    install_fnv_dependencies

    # Check for MPI
    if ! ls "$HOME/Hoolamike"/*.mpi &>/dev/null; then
        "$GUM_BINARY" style --foreground 99 --align center \
            "Waiting for TTW .mpi file..." \
            "Download from: https://mod.pub/ttw/133/files" \
            "Place in: $HOME/Hoolamike/"

        # Wait loop
        while ! ls "$HOME/Hoolamike"/*.mpi &>/dev/null; do
            sleep 5
            if ! "$GUM_BINARY" confirm --default=false --timeout=5s "Still waiting... Continue?"; then
                return
            fi
        done
    fi

    run_ttw_installation
}

# ===================================================================
# Hoolamike Tools Functions
# ===================================================================

hoolamike_menu() {
    while true; do
        clear

        local hoolamike_status="❌ Not Installed"
        [[ -f "$HOME/Hoolamike/hoolamike" ]] && hoolamike_status="✅ Installed"

        "$GUM_BINARY" style --foreground 212 --border normal --padding "1 2" --align center \
            "Hoolamike Mod Tools" \
            "" \
            "Hoolamike: $hoolamike_status"

        local choice=$("$GUM_BINARY" choose \
            --height 10 \
            "📥 Download/Update Hoolamike" \
            "💎 Install Wabbajack List (Premium)" \
            "🌐 Install Wabbajack List (Browser)" \
            "📝 Edit Configuration" \
            "⬅️  Back to Main Menu")

        case "$choice" in
            "📥 Download/Update Hoolamike") download_hoolamike ;;
            "💎 Install Wabbajack List"*) install_wabbajack_premium ;;
            "🌐 Install Wabbajack List"*) install_wabbajack_browser ;;
            "📝 Edit Configuration") edit_hoolamike_config ;;
            "⬅️  Back"*|"") return ;;
        esac
    done
}

# Install Wabbajack modlist (Premium)
install_wabbajack_premium() {
    if [[ ! -f "$HOME/Hoolamike/hoolamike" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "Hoolamike not installed!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    "$GUM_BINARY" style --foreground 99 --align center "Select .wabbajack file:"
    local wj_file=$("$GUM_BINARY" file)
    [[ -z "$wj_file" ]] && return

    # Update config
    local config="$HOME/Hoolamike/hoolamike.yaml"
    sed -i "s|wabbajack_file_path:.*|wabbajack_file_path: \"$wj_file\"|" "$config"

    # Get downloads directory
    local downloads_dir=$("$GUM_BINARY" input --placeholder "Downloads directory" --value "$HOME/Downloads")
    sed -i "s|downloads_directory:.*|downloads_directory: \"$downloads_dir\"|" "$config"

    # Get API key
    local api_key=$("$GUM_BINARY" input --placeholder "Nexus API key (get from nexusmods.com/users/myaccount?tab=api)")
    [[ -n "$api_key" ]] && sed -i "s|api_key:.*|api_key: \"$api_key\"|" "$config"

    cd "$HOME/Hoolamike"
    ./hoolamike install

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Install Wabbajack modlist (Browser)
install_wabbajack_browser() {
    if [[ ! -f "$HOME/Hoolamike/hoolamike" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "Hoolamike not installed!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    local browser=$("$GUM_BINARY" input --placeholder "Browser name (firefox, chrome, etc)" --value "firefox")
    [[ -z "$browser" ]] && return

    "$GUM_BINARY" style --foreground 99 --align center "Select .wabbajack file:"
    local wj_file=$("$GUM_BINARY" file)
    [[ -z "$wj_file" ]] && return

    # Update config
    local config="$HOME/Hoolamike/hoolamike.yaml"
    sed -i "s|wabbajack_file_path:.*|wabbajack_file_path: \"$wj_file\"|" "$config"

    cd "$HOME/Hoolamike"
    ./hoolamike handle-nxm --use-browser "$browser"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# Edit Hoolamike config
edit_hoolamike_config() {
    local config="$HOME/Hoolamike/hoolamike.yaml"

    if [[ ! -f "$config" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "Config not found!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    # Find editor
    local editor=""
    for e in nano vim vi emacs; do
        command -v $e &>/dev/null && { editor=$e; break; }
    done

    if [[ -z "$editor" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "No text editor found!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return
    fi

    $editor "$config"
}

# ===================================================================
# Sky Texture Optimizer Functions
# ===================================================================

sky_tex_menu() {
    "$GUM_BINARY" style --border normal --padding "1 2" --align center \
        "Sky Texture Optimizer" \
        "" \
        "Optimizes Skyrim textures to improve performance" \
        "while maintaining visual quality"

    "$GUM_BINARY" confirm "Download and run Sky Texture Optimizer?" || return

    download_sky_tex_opti
}

# Download Sky Texture Optimizer
download_sky_tex_opti() {
    local tools_dir="$SCRIPT_DIR/downloaded_tools/sky-tex-opti"
    rm -rf "$tools_dir"
    mkdir -p "$tools_dir"

    # Fetch latest release
    local download_url=$("$GUM_BINARY" spin --spinner dot --title "Fetching latest release..." --show-output -- \
        curl -s https://api.github.com/repos/BenHUET/sky-tex-opti/releases/latest | \
        jq -r '.assets[] | select(.name | test("sky-tex-opti_linux-x64.zip")) | .browser_download_url')

    if [[ -z "$download_url" ]]; then
        "$GUM_BINARY" style --foreground 196 --align center "Could not find download URL!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
        return 1
    fi

    # Download and extract
    local temp_zip="$TEMP_DIR/sky-tex-opti.zip"
    "$GUM_BINARY" spin --spinner dot --title "Downloading Sky Texture Optimizer..." -- \
        curl -L -o "$temp_zip" "$download_url"

    "$GUM_BINARY" spin --spinner dot --title "Extracting..." -- bash -c "
        unzip -o '$temp_zip' -d '$TEMP_DIR' && \
        cp -r '$TEMP_DIR/sky-tex-opti_linux-x64/'* '$tools_dir/' && \
        chmod +x '$tools_dir/sky-tex-opti'
    "

    # Get paths
    "$GUM_BINARY" style --foreground 99 --align center "Enter MO2 profile path (containing modlist.txt):"
    local mo2_profile=$("$GUM_BINARY" input --placeholder "e.g., /path/to/MO2/profiles/YourProfile")
    [[ -z "$mo2_profile" ]] && return

    "$GUM_BINARY" style --foreground 99 --align center "Enter output directory for optimized textures:"
    local output_dir=$("$GUM_BINARY" input --placeholder "$HOME/SkyrimOptimizedTextures" --value "$HOME/SkyrimOptimizedTextures")
    [[ -z "$output_dir" ]] && { output_dir="$HOME/SkyrimOptimizedTextures"; }

    mkdir -p "$output_dir"

    "$GUM_BINARY" style --foreground 99 --align center \
        "Running optimization..." \
        "This may take a long time depending on texture count"

    cd "$tools_dir"
    ./sky-tex-opti --profile "$mo2_profile" --output "$output_dir" --settings default.json

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
        "✓ Texture optimization complete!" \
        "" \
        "Optimized textures saved to:" \
        "$output_dir" \
        "" \
        "Create a new mod in MO2 and copy these textures" \
        "Place at the bottom of your load order"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Game-Specific Fixes Functions
# ===================================================================

game_fixes_menu() {
    while true; do
        clear
        "$GUM_BINARY" style --foreground 212 --border normal --padding "1 2" --align center \
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
        "$GUM_BINARY" style --border double --padding "1 2" --align center \
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
                components=(
                    fontsmooth=rgb
                    xact
                    xact_x64
                    d3dx9_43
                    d3dx9
                    vcrun2022
                )
                install_dependencies
                ;;
            "🔗 Configure NXM Handler") setup_nxm_handler ;;
            "🖥️  Configure DPI Scaling") setup_dpi_scaling ;;
        esac
    else
        "$GUM_BINARY" style --foreground 196 --align center \
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
        "$GUM_BINARY" style --border double --padding "1 2" --align center \
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
                install_dependencies
                ;;
            "🔗 Configure NXM Handler") setup_nxm_handler ;;
            "🖥️  Configure DPI Scaling") setup_dpi_scaling ;;
        esac
    else
        "$GUM_BINARY" style --foreground 196 --align center \
            "Enderal SE not found or not run yet!"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
    fi
}

# Baldur's Gate 3 fixes
bg3_fixes() {
    local compatdata=$(find_game_compatdata "1086940")

    if [[ -n "$compatdata" ]]; then
        "$GUM_BINARY" style --border double --padding "1 2" --align center \
            "Baldur's Gate 3 Launch Options:" \
            "" \
            "WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%"
    else
        "$GUM_BINARY" style --foreground 196 --align center \
            "Baldur's Gate 3 not found or not run yet!"
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
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

    "$GUM_BINARY" style --border double --padding "1 2" --align center \
        "Game-Specific Launch Options" \
        "" \
        "$advice"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Game Selection
# ===================================================================

select_game() {
    "$GUM_BINARY" style --foreground 99 --align center "Scanning for games..."

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
        "$GUM_BINARY" style --foreground 196 --align center "No games found!"
        return 1
    fi

    # Create display array
    local -a display_games=()
    for game in "${games[@]}"; do
        IFS=':' read -r appid name <<< "$game"
        display_games+=("$name [$appid]")
    done

    local selected=$("$GUM_BINARY" filter --placeholder "Type to search games..." \
        --indicator="▶" \
        --indicator.foreground="46" \
        --match.foreground="46" \
        <<< "$(printf '%s\n' "${display_games[@]}")")

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

    # Set default components if not already set
    if [[ ${#components[@]} -eq 0 ]]; then
        components=(
            fontsmooth=rgb
            xact
            xact_x64
            d3dx9_43
            d3dcompiler_47
            vcrun2022
            dotnet8
        )
    fi

    "$GUM_BINARY" style --border normal --padding "1 2" --align center \
        "Installing dependencies for:" \
        "$SELECTED_GAME" \
        "" \
        "Components: ${#components[@]}"

    "$GUM_BINARY" confirm "Install dependencies?" || return

    # Install with progress
    local total=${#components[@]}
    local current=0

    for comp in "${components[@]}"; do
        ((current++))

        "$GUM_BINARY" style --foreground 99 --align center "[$current/$total] Installing: $comp"

        "$GUM_BINARY" spin --spinner dot --title "Installing $comp..." -- \
            $PROTONTRICKS_CMD --no-bwrap "$SELECTED_APPID" -q "$comp"
    done

    # Enable dotfiles visibility
    local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
    if [[ -d "$prefix_path" ]]; then
        "$GUM_BINARY" spin --spinner dot --title "Enabling hidden files visibility..." -- \
            run_with_proton_wine "$prefix_path" "reg" "add" "HKCU\\Software\\Wine" "/v" "ShowDotFiles" "/d" "Y" "/f"
    fi

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
        "✓ Dependencies installed successfully!"

    # Reset components array for next use
    components=()

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
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

    "$GUM_BINARY" style --border normal --padding "1 2" --align center \
        "Setting up NXM handler for:" \
        "$SELECTED_GAME"

    "$GUM_BINARY" style --foreground 99 --align center "Select nxmhandler.exe:"
    local handler_path=$("$GUM_BINARY" file)
    [[ -z "$handler_path" ]] && return

    # Validate file
    if [[ "$(basename "$handler_path")" != "nxmhandler.exe" ]]; then
        if ! "$GUM_BINARY" confirm "This doesn't look like nxmhandler.exe. Continue anyway?"; then
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

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
        "✓ NXM handler configured successfully!"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# DPI Scaling
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
        '$(declare -f run_with_proton_wine)'
        STEAM_ROOT='$STEAM_ROOT'
        run_with_proton_wine '$prefix_path' reg add 'HKCU\\Control Panel\\Desktop' /v LogPixels /t REG_DWORD /d $scale /f
        run_with_proton_wine '$prefix_path' reg add 'HKCU\\Software\\Wine\\X11 Driver' /v LogPixels /t REG_DWORD /d $scale /f
    "

    "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
        "✓ DPI scaling set to $scale" \
        "" \
        "Restart the application for changes to take effect"

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Settings Menu
# ===================================================================

settings_menu() {
    while true; do
        clear
        "$GUM_BINARY" style --foreground 212 --border normal --padding "1 2" --align center \
            "Settings"

        local default_scaling=$(grep "DEFAULT_SCALING=" "$CONFIG_FILE" | cut -d= -f2)
        local show_advice=$(grep "SHOW_ADVICE=" "$CONFIG_FILE" | cut -d= -f2)

        local choice=$("$GUM_BINARY" choose \
            --height 10 \
            "🖥️  Default DPI Scaling: $default_scaling" \
            "💡 Show Advice: $show_advice" \
            "📊 View Configuration" \
            "🔄 Reset Configuration" \
            "⬅️  Back to Main Menu")

        case "$choice" in
            "🖥️  Default DPI"*)
                local new_dpi=$("$GUM_BINARY" input --placeholder "Enter default DPI (96-240)" --value "$default_scaling")
                [[ -n "$new_dpi" ]] && save_config "DEFAULT_SCALING" "$new_dpi"
                ;;
            "💡 Show Advice"*)
                if [[ "$show_advice" == "true" ]]; then
                    save_config "SHOW_ADVICE" "false"
                else
                    save_config "SHOW_ADVICE" "true"
                fi
                ;;
            "📊 View Configuration")
                "$GUM_BINARY" style --border normal --padding "1 2" --align center \
                    "Current Configuration" \
                    "" \
                    "$(cat "$CONFIG_FILE")"
                "$GUM_BINARY" input --placeholder "Press Enter to continue..."
                ;;
            "🔄 Reset Configuration")
                if "$GUM_BINARY" confirm "Reset configuration to defaults?"; then
                    rm -f "$CONFIG_FILE"
                    load_config
                    "$GUM_BINARY" style --foreground 46 --align center "Configuration reset!"
                    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
                fi
                ;;
            "⬅️  Back"*|"") return ;;
        esac
    done
}

# ===================================================================
# Utility Functions
# ===================================================================

# Remove NXM handlers
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
        "$GUM_BINARY" style --foreground 46 --align center "✓ Removed $found NXM handler(s)"
    else
        "$GUM_BINARY" style --foreground 99 --align center "No NXM handlers found"
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# View logs
view_logs() {
    if [[ -f "$LOG_FILE" ]]; then
        "$GUM_BINARY" pager < "$LOG_FILE"
    else
        "$GUM_BINARY" style --foreground 196 --align center "No log file found"
        "$GUM_BINARY" input --placeholder "Press Enter to continue..."
    fi
}

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

# Find game directory
find_game_dir() {
    local game_name="$1"
    local paths=("$STEAM_ROOT")

    # Check library folders
    local libraryfolders="$STEAM_ROOT/steamapps/libraryfolders.vdf"
    if [[ -f "$libraryfolders" ]]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    # Search for game directory
    for path in "${paths[@]}"; do
        local game_dir="$path/steamapps/common/$game_name"
        [[ -d "$game_dir" ]] && echo "$game_dir" && return 0
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
        "$GUM_BINARY" style --foreground 196 --align center "Python 3 required to add games to Steam!"
        return 1
    fi

    # Install vdf if needed
    if ! python3 -c "import vdf" 2>/dev/null; then
        "$GUM_BINARY" spin --spinner dot --title "Installing vdf module..." -- \
            python3 -m pip install --user vdf
    fi

    # Run Python script to add to Steam
    local result=$("$GUM_BINARY" spin --spinner dot --title "Adding to Steam..." --show-output -- python3 - << EOF
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
        "$GUM_BINARY" style --foreground 46 --border double --padding "1 2" --align center \
            "✓ Added to Steam successfully!" \
            "AppID: $app_id" \
            "" \
            "Restart Steam and set Proton compatibility"
    elif [[ "$result" == "ALREADY_EXISTS" ]]; then
        "$GUM_BINARY" style --foreground 99 --align center "$name is already in Steam"
    else
        "$GUM_BINARY" style --foreground 196 --align center "Failed to add to Steam"
    fi

    "$GUM_BINARY" input --placeholder "Press Enter to continue..."
}

# ===================================================================
# Main Execution
# ===================================================================

# Initialize and run
init
show_main_menu
