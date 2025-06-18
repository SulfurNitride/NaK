#!/bin/bash
# ===================================================================
# NaK Modules - Consolidated functionality
# This file should be sourced by the main script
# ===================================================================

# ===================================================================
# Vortex Functions
# ===================================================================

vortex_menu() {
    while true; do
        local choice=$(whiptail --title "Vortex Setup" \
            --menu "Choose an option:" 16 60 8 \
            "1" "Download Latest Vortex" \
            "2" "Setup Existing Vortex" \
            "3" "Install Dependencies" \
            "4" "Configure NXM Handler" \
            "5" "Configure DPI Scaling" \
            "B" "Back to Main Menu" \
            3>&1 1>&2 2>&3)

        case $choice in
            1) download_vortex ;;
            2) setup_existing_vortex ;;
            3) select_game && install_dependencies ;;
            4) select_game && setup_vortex_nxm_handler ;;
            5) select_game && setup_dpi_scaling ;;
            B|"") return ;;
        esac
    done
}

download_vortex() {
    local temp_file="$TEMP_DIR/vortex_release.json"

    {
        echo "10"; echo "# Fetching latest release info..."
        curl -s https://api.github.com/repos/Nexus-Mods/Vortex/releases/latest > "$temp_file"

        echo "30"; echo "# Parsing release data..."
        local version=$(jq -r '.tag_name' "$temp_file" | sed 's/^v//')
        local download_url=$(jq -r '.assets[] | select(.name | test("^vortex-setup-[0-9.]+\\.exe$")) | .browser_download_url' "$temp_file")

        [[ -z "$download_url" ]] && { whiptail --title "Error" --msgbox "Could not find Vortex download URL" 8 50; return 1; }

        echo "40"; echo "# Preparing download..."
        local install_dir=$(whiptail --inputbox "Install directory:" 8 60 "$HOME/Vortex" 3>&1 1>&2 2>&3)
        [[ -z "$install_dir" ]] && return

        mkdir -p "$install_dir"
        local installer="$TEMP_DIR/vortex-setup.exe"

        echo "50"; echo "# Downloading Vortex v$version..."
        curl -L -o "$installer" "$download_url"

        echo "80"; echo "# Installing with Wine..."
        if command -v wine &> /dev/null; then
            WINEPREFIX="$HOME/.wine" wine "$installer" /S "/D=Z:$(echo "$install_dir" | sed 's|/|\\|g')"
        else
            whiptail --title "Error" --msgbox "Wine not found. Please install Wine first." 8 50
            return 1
        fi

        echo "100"; echo "# Installation complete!"
    } | whiptail --title "Downloading Vortex" --gauge "Starting download..." 8 70 0

    whiptail --title "Success" --msgbox "Vortex v$version installed to:\n$install_dir" 10 60

    if whiptail --title "Add to Steam?" --yesno "Add Vortex to Steam as non-Steam game?" 8 50; then
        add_to_steam "Vortex" "$install_dir/Vortex.exe"
    fi
}

setup_vortex_nxm_handler() {
    [[ -z "$SELECTED_GAME" ]] && return

    local vortex_path=$(whiptail --inputbox "Enter path to Vortex.exe:" 10 60 3>&1 1>&2 2>&3)
    [[ -z "$vortex_path" || ! -f "$vortex_path" ]] && return

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
    update-desktop-database "$HOME/.local/share/applications"

    whiptail --title "Success" --msgbox "NXM handler configured for Vortex" 8 50
}

# ===================================================================
# Limo Functions
# ===================================================================

limo_menu() {
    whiptail --title "Limo Setup" --msgbox \
        "Limo is a Linux-native mod manager.\n\nThis tool will install dependencies for your game prefixes to work with Limo." \
        10 60

    if select_game; then
        install_dependencies

        local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"
        whiptail --title "Success" --msgbox \
            "Dependencies installed for $SELECTED_GAME\n\nPrefix path:\n$prefix_path" \
            12 70
    fi
}

# ===================================================================
# Tale of Two Wastelands Functions
# ===================================================================

ttw_menu() {
    while true; do
        local hoolamike_status="Not Installed"
        [[ -f "$HOME/Hoolamike/hoolamike" ]] && hoolamike_status="Installed"

        local choice=$(whiptail --title "Tale of Two Wastelands Setup" \
            --menu "Hoolamike: $hoolamike_status\n\nChoose an option:" 16 60 7 \
            "1" "Automated TTW Setup (All Steps)" \
            "2" "Download/Update Hoolamike" \
            "3" "Install FNV Dependencies" \
            "4" "Run TTW Installation" \
            "5" "View Documentation" \
            "B" "Back to Main Menu" \
            3>&1 1>&2 2>&3)

        case $choice in
            1) automated_ttw_setup ;;
            2) download_hoolamike ;;
            3) install_fnv_dependencies ;;
            4) run_ttw_installation ;;
            5) view_ttw_docs ;;
            B|"") return ;;
        esac
    done
}

download_hoolamike() {
    local hoolamike_dir="$HOME/Hoolamike"

    if [[ -d "$hoolamike_dir" ]]; then
        if ! whiptail --title "Hoolamike Exists" --yesno "Update existing installation?" 8 50; then
            return
        fi
        rm -rf "$hoolamike_dir"
    fi

    mkdir -p "$hoolamike_dir"

    {
        echo "20"; echo "# Fetching latest release..."
        local release_url=$(curl -s https://api.github.com/repos/Niedzwiedzw/hoolamike/releases/latest | \
            jq -r '.assets[] | select(.name | test("hoolamike.*linux"; "i")) | .browser_download_url')

        echo "50"; echo "# Downloading..."
        cd "$hoolamike_dir" && curl -L "$release_url" | tar -xz

        echo "80"; echo "# Generating config..."
        generate_hoolamike_config

        echo "100"; echo "# Complete!"
    } | whiptail --title "Downloading Hoolamike" --gauge "Starting..." 8 70 0

    whiptail --title "Success" --msgbox \
        "Hoolamike installed!\n\nNext steps:\n1. Download TTW .mpi file\n2. Place in $hoolamike_dir\n3. Run TTW installation" \
        12 60
}

generate_hoolamike_config() {
    local config_file="$HOME/Hoolamike/hoolamike.yaml"
    local downloads_dir="$HOME/Hoolamike/Mod_Downloads"
    local install_dir="$HOME/ModdedGames"

    # Find game paths
    local fo3_dir=$(find_game_dir "Fallout 3 goty")
    local fnv_dir=$(find_game_dir "Fallout New Vegas")

    cat > "$config_file" << EOF
# Auto-generated hoolamike.yaml
downloaders:
  downloads_directory: "$downloads_dir"
  nexus:
    api_key: "YOUR_API_KEY_HERE"

installation:
  wabbajack_file_path: "./wabbajack"
  installation_path: "$install_dir"

games:
EOF

    [[ -n "$fo3_dir" ]] && echo "  Fallout3:" >> "$config_file" && echo "    root_directory: \"$fo3_dir\"" >> "$config_file"
    [[ -n "$fnv_dir" ]] && echo "  FalloutNewVegas:" >> "$config_file" && echo "    root_directory: \"$fnv_dir\"" >> "$config_file"

    echo "" >> "$config_file"
    echo "fixup:" >> "$config_file"
    echo "  game_resolution: 1920x1080" >> "$config_file"
    echo "" >> "$config_file"
    echo "extras:" >> "$config_file"
    echo "  tale_of_two_wastelands:" >> "$config_file"
    echo "    path_to_ttw_mpi_file: \"./YOUR_TTW_MPI_FILE.mpi\"" >> "$config_file"
    echo "    variables:" >> "$config_file"
    echo "      DESTINATION: \"./TTW_Output\"" >> "$config_file"
}

install_fnv_dependencies() {
    SELECTED_APPID="22380"
    SELECTED_GAME="Fallout New Vegas"

    whiptail --title "FNV Dependencies" --msgbox \
        "Installing dependencies for Fallout New Vegas modding and TTW." 8 60

    install_dependencies
}

run_ttw_installation() {
    if [[ ! -f "$HOME/Hoolamike/hoolamike" ]]; then
        whiptail --title "Error" --msgbox "Hoolamike not installed!" 8 50
        return
    fi

    if ! ls "$HOME/Hoolamike"/*.mpi &>/dev/null; then
        whiptail --title "Missing MPI" --msgbox \
            "No TTW .mpi file found!\n\nDownload from: https://mod.pub/ttw/133/files\nPlace in: $HOME/Hoolamike/" \
            10 60
        return
    fi

    cd "$HOME/Hoolamike"
    ./hoolamike tale-of-two-wastelands
}

# ===================================================================
# Hoolamike Tools Functions
# ===================================================================

hoolamike_menu() {
    while true; do
        local hoolamike_status="Not Installed"
        [[ -f "$HOME/Hoolamike/hoolamike" ]] && hoolamike_status="Installed"

        local choice=$(whiptail --title "Hoolamike Tools" \
            --menu "Hoolamike: $hoolamike_status\n\nChoose an option:" 16 60 6 \
            "1" "Download/Update Hoolamike" \
            "2" "Install Wabbajack List (Premium)" \
            "3" "Install Wabbajack List (Browser)" \
            "4" "Edit Configuration" \
            "B" "Back to Main Menu" \
            3>&1 1>&2 2>&3)

        case $choice in
            1) download_hoolamike ;;
            2) install_wabbajack_premium ;;
            3) install_wabbajack_browser ;;
            4) edit_hoolamike_config ;;
            B|"") return ;;
        esac
    done
}

install_wabbajack_premium() {
    [[ ! -f "$HOME/Hoolamike/hoolamike" ]] && { whiptail --title "Error" --msgbox "Hoolamike not installed!" 8 50; return; }

    local wj_file=$(whiptail --inputbox "Path to .wabbajack file:" 10 60 3>&1 1>&2 2>&3)
    [[ -z "$wj_file" || ! -f "$wj_file" ]] && return

    # Update config
    local config="$HOME/Hoolamike/hoolamike.yaml"
    sed -i "s|wabbajack_file_path:.*|wabbajack_file_path: \"$wj_file\"|" "$config"

    cd "$HOME/Hoolamike"
    ./hoolamike install
}

install_wabbajack_browser() {
    [[ ! -f "$HOME/Hoolamike/hoolamike" ]] && { whiptail --title "Error" --msgbox "Hoolamike not installed!" 8 50; return; }

    local browser=$(whiptail --inputbox "Browser name (firefox, chrome, etc):" 10 60 "firefox" 3>&1 1>&2 2>&3)
    [[ -z "$browser" ]] && return

    local wj_file=$(whiptail --inputbox "Path to .wabbajack file:" 10 60 3>&1 1>&2 2>&3)
    [[ -z "$wj_file" || ! -f "$wj_file" ]] && return

    # Update config
    local config="$HOME/Hoolamike/hoolamike.yaml"
    sed -i "s|wabbajack_file_path:.*|wabbajack_file_path: \"$wj_file\"|" "$config"

    cd "$HOME/Hoolamike"
    ./hoolamike handle-nxm --use-browser "$browser"
}

edit_hoolamike_config() {
    local config="$HOME/Hoolamike/hoolamike.yaml"
    [[ ! -f "$config" ]] && { whiptail --title "Error" --msgbox "Config not found!" 8 50; return; }

    # Find available editor
    local editor=""
    for e in nano vim vi emacs; do
        command -v $e &>/dev/null && { editor=$e; break; }
    done

    [[ -z "$editor" ]] && { whiptail --title "Error" --msgbox "No text editor found!" 8 50; return; }

    $editor "$config"
}

# ===================================================================
# Sky Texture Optimizer Functions
# ===================================================================

sky_tex_menu() {
    whiptail --title "Sky Texture Optimizer" --msgbox \
        "Sky Texture Optimizer reduces texture sizes to improve performance.\n\nYou'll need:\n- MO2 profile path\n- Output directory for optimized textures" \
        12 60

    download_sky_tex_opti
}

download_sky_tex_opti() {
    local tools_dir="$SCRIPT_DIR/downloaded_tools/sky-tex-opti"

    {
        echo "20"; echo "# Fetching latest release..."
        local download_url=$(curl -s https://api.github.com/repos/BenHUET/sky-tex-opti/releases/latest | \
            jq -r '.assets[] | select(.name | test("sky-tex-opti_linux-x64.zip")) | .browser_download_url')

        echo "50"; echo "# Downloading..."
        mkdir -p "$tools_dir"
        local temp_zip="$TEMP_DIR/sky-tex-opti.zip"
        curl -L -o "$temp_zip" "$download_url"

        echo "80"; echo "# Extracting..."
        unzip -o "$temp_zip" -d "$TEMP_DIR"
        cp -r "$TEMP_DIR/sky-tex-opti_linux-x64/"* "$tools_dir/"
        chmod +x "$tools_dir/sky-tex-opti"

        echo "100"; echo "# Complete!"
    } | whiptail --title "Downloading Sky Texture Optimizer" --gauge "Starting..." 8 70 0

    # Get paths
    local mo2_profile=$(whiptail --inputbox "MO2 profile path:" 10 60 3>&1 1>&2 2>&3)
    [[ -z "$mo2_profile" ]] && return

    local output_dir=$(whiptail --inputbox "Output directory:" 10 60 "$HOME/SkyrimOptimizedTextures" 3>&1 1>&2 2>&3)
    [[ -z "$output_dir" ]] && return

    mkdir -p "$output_dir"
    cd "$tools_dir"
    ./sky-tex-opti --profile "$mo2_profile" --output "$output_dir" --settings default.json
}

# ===================================================================
# Game-Specific Fixes Functions
# ===================================================================

game_fixes_menu() {
    while true; do
        local choice=$(whiptail --title "Game-Specific Fixes" \
            --menu "Choose a game:" 14 60 6 \
            "1" "Fallout New Vegas" \
            "2" "Enderal Special Edition" \
            "3" "Baldur's Gate 3" \
            "4" "All Games Advice" \
            "B" "Back to Main Menu" \
            3>&1 1>&2 2>&3)

        case $choice in
            1) fnv_fixes ;;
            2) enderal_fixes ;;
            3) bg3_fixes ;;
            4) show_all_game_advice ;;
            B|"") return ;;
        esac
    done
}

fnv_fixes() {
    SELECTED_APPID="22380"
    SELECTED_GAME="Fallout New Vegas"

    local compatdata=$(find_game_compatdata "$SELECTED_APPID")
    if [[ -z "$compatdata" ]]; then
        whiptail --title "FNV Not Found" --msgbox "Fallout New Vegas not installed or not run yet." 8 50
        return
    fi

    whiptail --title "FNV Launch Options" --msgbox \
        "Recommended launch options:\n\nSTEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%" \
        10 70

    if whiptail --title "Install Dependencies?" --yesno "Install FNV modding dependencies?" 8 50; then
        install_dependencies
    fi
}

enderal_fixes() {
    SELECTED_APPID="976620"
    SELECTED_GAME="Enderal Special Edition"

    local compatdata=$(find_game_compatdata "$SELECTED_APPID")
    if [[ -z "$compatdata" ]]; then
        whiptail --title "Enderal Not Found" --msgbox "Enderal SE not installed or not run yet." 8 50
        return
    fi

    whiptail --title "Enderal Launch Options" --msgbox \
        "Recommended launch options:\n\nSTEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%" \
        10 70

    if whiptail --title "Install Dependencies?" --yesno "Install Enderal modding dependencies?" 8 50; then
        install_dependencies
    fi
}

bg3_fixes() {
    SELECTED_APPID="1086940"
    SELECTED_GAME="Baldur's Gate 3"

    local compatdata=$(find_game_compatdata "$SELECTED_APPID")
    if [[ -z "$compatdata" ]]; then
        whiptail --title "BG3 Not Found" --msgbox "Baldur's Gate 3 not installed or not run yet." 8 50
        return
    fi

    whiptail --title "BG3 Launch Options" --msgbox \
        "Recommended launch options:\n\nWINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%" \
        10 70
}

show_all_game_advice() {
    local advice="Game-Specific Launch Options:\n\n"

    # Check each game
    local fnv_compat=$(find_game_compatdata "22380")
    [[ -n "$fnv_compat" ]] && advice+="Fallout New Vegas:\nSTEAM_COMPAT_DATA_PATH=\"$fnv_compat\" %command%\n\n"

    local enderal_compat=$(find_game_compatdata "976620")
    [[ -n "$enderal_compat" ]] && advice+="Enderal SE:\nSTEAM_COMPAT_DATA_PATH=\"$enderal_compat\" %command%\n\n"

    local bg3_compat=$(find_game_compatdata "1086940")
    [[ -n "$bg3_compat" ]] && advice+="Baldur's Gate 3:\nWINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%\n\n"

    whiptail --title "All Games Advice" --msgbox "$advice" 20 70
}

# ===================================================================
# Settings Functions
# ===================================================================

settings_menu() {
    while true; do
        local choice=$(whiptail --title "Settings" \
            --menu "Configure NaK:" 14 60 5 \
            "1" "Default DPI Scaling: $DEFAULT_SCALING" \
            "2" "Show Advanced Options: $SHOW_ADVANCED" \
            "3" "Check Updates: $CHECK_UPDATES" \
            "4" "View Logs" \
            "B" "Back to Main Menu" \
            3>&1 1>&2 2>&3)

        case $choice in
            1)
                local new_dpi=$(whiptail --inputbox "Default DPI scaling:" 8 60 "$DEFAULT_SCALING" 3>&1 1>&2 2>&3)
                [[ -n "$new_dpi" ]] && save_config "DEFAULT_SCALING" "$new_dpi" && DEFAULT_SCALING="$new_dpi"
                ;;
            2)
                if [[ "$SHOW_ADVANCED" == "true" ]]; then
                    save_config "SHOW_ADVANCED" "false" && SHOW_ADVANCED="false"
                else
                    save_config "SHOW_ADVANCED" "true" && SHOW_ADVANCED="true"
                fi
                ;;
            3)
                if [[ "$CHECK_UPDATES" == "true" ]]; then
                    save_config "CHECK_UPDATES" "false" && CHECK_UPDATES="false"
                else
                    save_config "CHECK_UPDATES" "true" && CHECK_UPDATES="true"
                fi
                ;;
            4)
                if [[ -f "$LOG_FILE" ]]; then
                    whiptail --title "Recent Logs" --textbox "$LOG_FILE" 20 70
                else
                    whiptail --title "No Logs" --msgbox "No log file found." 8 50
                fi
                ;;
            B|"") return ;;
        esac
    done
}

# ===================================================================
# Utility Functions
# ===================================================================

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
        update-desktop-database "$HOME/.local/share/applications"
        whiptail --title "Success" --msgbox "Removed $found NXM handler(s)" 8 50
    else
        whiptail --title "Info" --msgbox "No NXM handlers found" 8 50
    fi
}

setup_dpi_scaling() {
    [[ -z "$SELECTED_GAME" ]] && return

    local scales=("96" "Standard (100%)" "120" "Medium (125%)" "144" "Large (150%)" "192" "Extra Large (200%)")

    local choice=$(whiptail --title "DPI Scaling" \
        --menu "Select scaling for $SELECTED_GAME:" 14 60 4 \
        "${scales[@]}" \
        3>&1 1>&2 2>&3)

    [[ -z "$choice" ]] && return

    local prefix_path="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID/pfx"

    # Create batch file for registry changes
    local batch_file="$TEMP_DIR/dpi.bat"
    cat > "$batch_file" << EOF
@echo off
reg add "HKCU\\Control Panel\\Desktop" /v LogPixels /t REG_DWORD /d $choice /f
reg add "HKCU\\Software\\Wine\\X11 Driver" /v LogPixels /t REG_DWORD /d $choice /f
exit 0
EOF

    # Run with Proton
    local proton_path=$(find_proton_path)
    env STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT" \
        STEAM_COMPAT_DATA_PATH="$STEAM_ROOT/steamapps/compatdata/$SELECTED_APPID" \
        "$proton_path" run "$batch_file"

    whiptail --title "Success" --msgbox "DPI scaling set to $choice for $SELECTED_GAME" 8 50
}

find_game_compatdata() {
    local appid="$1"
    local steam_paths=("$STEAM_ROOT")

    # Check libraryfolders.vdf for additional paths
    local libraryfolders="$STEAM_ROOT/steamapps/libraryfolders.vdf"
    if [[ -f "$libraryfolders" ]]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && steam_paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    # Search for compatdata
    for path in "${steam_paths[@]}"; do
        local compatdata="$path/steamapps/compatdata/$appid"
        [[ -d "$compatdata" ]] && echo "$compatdata" && return 0
    done

    return 1
}

find_game_dir() {
    local game_name="$1"
    local steam_paths=("$STEAM_ROOT")

    # Check libraryfolders.vdf
    local libraryfolders="$STEAM_ROOT/steamapps/libraryfolders.vdf"
    if [[ -f "$libraryfolders" ]]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && steam_paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    # Search for game directory
    for path in "${steam_paths[@]}"; do
        local game_dir="$path/steamapps/common/$game_name"
        [[ -d "$game_dir" ]] && echo "$game_dir" && return 0
    done

    return 1
}

add_to_steam() {
    local name="$1"
    local exe_path="$2"
    local start_dir=$(dirname "$exe_path")

    # Simple VDF addition using Python if available
    if command -v python3 &>/dev/null; then
        python3 - << EOF
import os
import struct
import time

shortcuts_path = "$STEAM_ROOT/userdata"
for user_dir in os.listdir(shortcuts_path):
    vdf_path = os.path.join(shortcuts_path, user_dir, "config", "shortcuts.vdf")
    if os.path.exists(vdf_path):
        # For simplicity, just notify user
        print(f"Please manually add {name} to Steam")
        print(f"Executable: {exe_path}")
        break
EOF
    fi

    whiptail --title "Add to Steam" --msgbox \
        "Please add manually to Steam:\n\nName: $name\nExecutable: $exe_path\n\nThen set Proton compatibility." \
        12 60
}

setup_existing_mo2() {
    local mo2_dir=$(whiptail --inputbox "Path to existing MO2 installation:" 10 60 3>&1 1>&2 2>&3)
    [[ -z "$mo2_dir" || ! -d "$mo2_dir" ]] && return

    if [[ ! -f "$mo2_dir/ModOrganizer.exe" ]]; then
        whiptail --title "Error" --msgbox "ModOrganizer.exe not found in directory" 8 50
        return
    fi

    whiptail --title "Success" --msgbox "Found MO2 at:\n$mo2_dir" 8 60

    if whiptail --title "Add to Steam?" --yesno "Add MO2 to Steam?" 8 50; then
        add_to_steam "Mod Organizer 2" "$mo2_dir/ModOrganizer.exe"
    fi
}

setup_existing_vortex() {
    local vortex_dir=$(whiptail --inputbox "Path to existing Vortex installation:" 10 60 3>&1 1>&2 2>&3)
    [[ -z "$vortex_dir" || ! -d "$vortex_dir" ]] && return

    if [[ ! -f "$vortex_dir/Vortex.exe" ]]; then
        whiptail --title "Error" --msgbox "Vortex.exe not found in directory" 8 50
        return
    fi

    whiptail --title "Success" --msgbox "Found Vortex at:\n$vortex_dir" 8 60

    if whiptail --title "Add to Steam?" --yesno "Add Vortex to Steam?" 8 50; then
        add_to_steam "Vortex" "$vortex_dir/Vortex.exe"
    fi
}

view_ttw_docs() {
    whiptail --title "TTW Documentation" --msgbox \
"Tale of Two Wastelands Resources:

Official Website:
https://taleoftwowastelands.com/

Installation Guide:
https://taleoftwowastelands.com/wiki_ttw/get-started/

TTW Discord:
https://discord.gg/taleoftwowastelands

Requirements:
- Fallout 3 GOTY Edition
- Fallout New Vegas Ultimate Edition
- TTW .mpi installer file

Linux Tips:
- Install FNV dependencies first
- Run both games once before TTW
- Installation can take 2-4 hours" 20 70
}

automated_ttw_setup() {
    whiptail --title "Automated TTW Setup" --msgbox \
        "This will:\n1. Download Hoolamike\n2. Install FNV dependencies\n3. Wait for TTW .mpi file\n4. Run TTW installation\n\nThis process takes several hours!" \
        12 60

    if ! whiptail --title "Continue?" --yesno "Start automated TTW setup?" 8 50; then
        return
    fi

    # Run each step
    download_hoolamike
    install_fnv_dependencies

    # Check for MPI
    if ! ls "$HOME/Hoolamike"/*.mpi &>/dev/null; then
        whiptail --title "MPI Required" --msgbox \
            "Please download TTW .mpi file from:\nhttps://mod.pub/ttw/133/files\n\nPlace in: $HOME/Hoolamike/\n\nThen run TTW installation again." \
            12 60
        return
    fi

    run_ttw_installation
}

install_py7zr_if_needed() {
    if ! python3 -c "import py7zr" 2>/dev/null; then
        python3 -m pip install --user py7zr
    fi
}
