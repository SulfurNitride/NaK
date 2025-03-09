#!/bin/bash
# -------------------------------------------------------------------
# modorganizer2-helper.sh
# Unified script with NXM handler and Proton setup
# -------------------------------------------------------------------

# Log file
log_file="$HOME/mo2helper.log"

# Ensure log file exists
echo "MO2 Helper TUI Log - $(date)" > "$log_file"
echo "=============================" >> "$log_file"

# Common variables
declare -a game_array
protontricks_cmd=""
selected_appid=""
selected_name=""
selected_scaling="96"  # Default scaling value
show_advice=true  # Whether to show game-specific advice

# Function to log messages
log() {
    echo "[$(date +%T)] $1" >> "$log_file"
}

# Function to show error message, log it, and exit
error_exit() {
    echo "ERROR: $1" >&2
    log "ERROR: $1"
    exit 1
}

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Dependency checks
check_dependencies() {
    log "Checking dependencies"

    if ! command_exists protontricks && \
       ! flatpak list --app --columns=application 2>/dev/null | grep -q com.github.Matoking.protontricks; then
        error_exit "Protontricks is not installed. Install it with:
- Native: sudo apt install protontricks
- Flatpak: flatpak install com.github.Matoking.protontricks"
    fi

    if command_exists protontricks; then
        protontricks_cmd="protontricks"
        log "Using native protontricks"
    else
        protontricks_cmd="flatpak run com.github.Matoking.protontricks"
        log "Using flatpak protontricks"
    fi
}

check_flatpak_steam() {
    log "Checking for Flatpak Steam"

    if flatpak list --app --columns=application 2>/dev/null | grep -q 'com.valvesoftware.Steam'; then
        error_exit "Detected Steam installed via Flatpak. This script doesn't support Flatpak Steam installations."
    fi
}

get_steam_root() {
    log "Finding Steam root directory"

    local candidates=(
        "$HOME/.local/share/Steam"
        "$HOME/.steam/steam"
        "$HOME/.steam/debian-installation"
        "/usr/local/steam"
        "/usr/share/steam"
    )

    for candidate in "${candidates[@]}"; do
        if [ -d "$candidate/steamapps" ]; then
            log "Found Steam root: $candidate"
            echo "$candidate"
            return
        fi
    done

    log "ERROR: Could not find Steam installation in standard locations"
    echo "Error: Could not find Steam installation in:" >&2
    printf "  - %s\n" "${candidates[@]}" >&2
    exit 1
}

# Update the get_non_steam_games function
get_non_steam_games() {
    echo "Fetching non-Steam games..."
    log "Fetching non-Steam games"

    # Capture protontricks output with error logging
    local protontricks_output
    if ! protontricks_output=$($protontricks_cmd --list 2>&1); then
        log "ERROR: Failed to run protontricks:"
        log "$protontricks_output"
        error_exit "Failed to run protontricks. Check log for details."
    fi

    log "Protontricks output received, processing"
    log "$protontricks_output"

    # Try a simplified parsing method that's more compatible
    log "Using simplified parsing method"
    local games=""
    while IFS= read -r line; do
        if [[ "$line" =~ "Non-Steam shortcut:" ]]; then
            if [[ "$line" =~ \(([0-9]+)\)$ ]]; then
                appid="${BASH_REMATCH[1]}"
                name=$(echo "$line" | sed -E 's/.*Non-Steam shortcut: (.*) \([0-9]+\)$/\1/')
                log "Found game: $appid:$name"
                games="$games$appid:$name"$'\n'
            fi
        fi
    done <<< "$protontricks_output"

    # Log what we found
    log "Parsed games output:"
    log "$games"

    # Remove trailing newline
    games=$(echo "$games" | sed '/^$/d')

    # Check if we actually found any games
    if [ -z "$games" ]; then
        log "ERROR: No non-Steam games found!"
        error_exit "No non-Steam games found! Make sure you've added non-Steam games to Steam and launched them at least once."
    fi

    IFS=$'\n' read -d '' -ra game_array <<< "$games"

    # Additional check to make sure game array is not empty
    if [ ${#game_array[@]} -eq 0 ]; then
        log "ERROR: Failed to parse any games into the array"
        error_exit "Failed to parse any games into the array."
    else
        log "Successfully found ${#game_array[@]} games"
    fi
}

debug_game_info() {
    log "DEBUG: Found games:"
    for i in "${!game_array[@]}"; do
        log "  [$i] ${game_array[$i]}"
    done
}

select_game() {
    log "Showing game selection menu"
    echo "Non-Steam Games:"
    for i in "${!game_array[@]}"; do
        IFS=':' read -r appid name <<< "${game_array[$i]}"
        printf "%2d. %s (AppID: %s)\n" $((i+1)) "$name" "$appid"
    done

    while true; do
        read -rp "Select a game by number: " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#game_array[@]}" ]; then
            selected_game="${game_array[$((choice-1))]}"
            IFS=':' read -r selected_appid selected_name <<< "$selected_game"
            log "Selected game: $selected_name (AppID: $selected_appid)"
            break
        else
            echo "Invalid choice. Try again."
            log "Invalid selection: $choice"
        fi
    done
}

# New function to select Proton DPI scaling

select_dpi_scaling() {
    log "Showing DPI scaling selection menu"
    echo -e "\n=== Proton DPI Scaling Selection ==="
    echo "Select resolution scaling:"
    echo "1. 96 DPI  (100% - for 1080p)"
    echo "2. 144 DPI (150% - for 1440p)"
    echo "3. 192 DPI (200% - for 4K)"

    while true; do
        read -rp "Select scaling (1-3, default 1): " choice
        case "$choice" in
            ""|"1")
                selected_scaling="96"
                log "Selected scaling: 96 DPI (100%)"
                break
                ;;
            "2")
                selected_scaling="144"
                log "Selected scaling: 144 DPI (150%)"
                break
                ;;
            "3")
                selected_scaling="192"
                log "Selected scaling: 192 DPI (200%)"
                break
                ;;
            *)
                echo "Invalid choice. Try again."
                log "Invalid scaling selection: $choice"
                ;;
        esac
    done
}

apply_dpi_scaling() {
    log "Applying DPI scaling $selected_scaling to AppID $selected_appid"
    echo -e "\n=== Applying Proton DPI Scaling ==="
    echo "Setting Proton DPI scaling to $selected_scaling for $selected_name..."

    # Convert decimal DPI value to hex for registry
    local hex_dpi=$(printf '%x' "$selected_scaling")
    log "Created registry file with DPI value $selected_scaling (hex: $hex_dpi)"

    # Get Steam root and Proton path using existing functions
    local steam_root=$(get_steam_root)
    local proton_path=$(find_proton_path "$steam_root")

    # Create a temporary .reg file
    local reg_file="/tmp/dpi_scaling.reg"

    # Create registry file content
    cat > "$reg_file" << EOF
Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\\Control Panel\\Desktop]
"LogPixels"=dword:000000${hex_dpi}

[HKEY_CURRENT_USER\\Control Panel\\Desktop\\WindowMetrics]
"AppliedDPI"=dword:000000${hex_dpi}
EOF

    # Set up the Steam compat data path
    local compat_data_path="$steam_root/steamapps/compatdata/$selected_appid"

    # Use the proton command with the right environment variables to silently import registry
    log "Running: STEAM_COMPAT_DATA_PATH=$compat_data_path $proton_path run regedit /s $reg_file"

    if STEAM_COMPAT_CLIENT_INSTALL_PATH="$steam_root" STEAM_COMPAT_DATA_PATH="$compat_data_path" "$proton_path" run regedit /s "$reg_file" > /tmp/mo2helper_dpi.log 2>&1; then
        echo "Successfully imported DPI scaling registry values! Please Note: You might need to open the application twice!!!"
        log "DPI scaling registry values imported"
    else
        status=$?
        cat /tmp/mo2helper_dpi.log >> "$log_file"
        log "DPI scaling import failed with status $status"
        error_exit "Failed to import DPI scaling. Check $log_file for details."
    fi
}

find_proton_path() {
    local steam_root="$1"
    log "Finding Proton path (Steam root: $steam_root)"

    local steam_paths=("$steam_root")

    libraryfolders="$steam_root/steamapps/libraryfolders.vdf"
    if [ -f "$libraryfolders" ]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && steam_paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    for path in "${steam_paths[@]}"; do
        proton_candidate="$path/steamapps/common/Proton - Experimental/proton"
        if [ -f "$proton_candidate" ]; then
            log "Found Proton path: $proton_candidate"
            echo "$proton_candidate"
            return
        fi
    done

    log "ERROR: Proton - Experimental not found"
    echo "Error: Proton - Experimental not found in:" >&2
    printf "  - %s\n" "${steam_paths[@]/%//steamapps/common/Proton - Experimental/proton}" >&2
    exit 1
}

register_mime_handler() {
    log "Registering NXM MIME handler"
    echo -n "Registering nxm:// handler... "

    if xdg-mime default modorganizer2-nxm-handler.desktop x-scheme-handler/nxm 2>/dev/null ; then
        echo "Success (via xdg-mime)"
        log "Success (via xdg-mime)"
    else
        local mimeapps="$HOME/.config/mimeapps.list"
        [ -f "$mimeapps" ] || touch "$mimeapps"
        sed -i '/x-scheme-handler\/nxm/d' "$mimeapps"
        echo "x-scheme-handler/nxm=modorganizer2-nxm-handler.desktop" >> "$mimeapps"
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        echo "Manual registration complete!"
        log "Manual registration complete"
    fi
}

setup_nxm_handler() {
    log "Setting up NXM handler for $selected_name (AppID: $selected_appid)"
    echo -e "\n=== NXM Link Handler Setup ==="
    check_flatpak_steam
    local steam_root=$(get_steam_root)
    local proton_path=$(find_proton_path "$steam_root")

    while true; do
        read -rp "Enter FULL path to nxmhandler.exe: " nxmhandler_path
        if [ -f "$nxmhandler_path" ]; then
            log "Selected nxmhandler.exe: $nxmhandler_path"
            break
        fi
        echo "File not found! Try again."
        log "Invalid path: $nxmhandler_path"
    done

    steam_compat_data_path="$steam_root/steamapps/compatdata/$selected_appid"
    desktop_file="$HOME/.local/share/applications/modorganizer2-nxm-handler.desktop"

    log "Creating desktop file: $desktop_file"
    cat << EOF > "$desktop_file"
[Desktop Entry]
Type=Application
Categories=Game;
Exec=bash -c 'env "STEAM_COMPAT_CLIENT_INSTALL_PATH=$steam_root" "STEAM_COMPAT_DATA_PATH=$steam_compat_data_path" "$proton_path" run "$nxmhandler_path" "%u"'
Name=Mod Organizer 2 NXM Handler
MimeType=x-scheme-handler/nxm;
NoDisplay=true
EOF

    chmod +x "$desktop_file"
    register_mime_handler
    echo -e "\nNXM Handler setup complete!"
    log "NXM Handler setup complete"
}

install_proton_dependencies() {
    log "Installing dependencies for $selected_name (AppID: $selected_appid)"
    echo -e "\n=== Proton Dependency Installation ==="

    components=(
        fontsmooth=rgb xact xact_x64 vcrun2022 dotnet6
        dotnet7 dotnet8 d3dcompiler_47 d3dx11_43
        d3dcompiler_43 d3dx9_43 d3dx9 vkd3d
    )

    echo "Installing components for $selected_name (AppID: $selected_appid)..."
    echo "This may take several minutes..."
    log "Running: $protontricks_cmd --no-bwrap $selected_appid -q ${components[*]}"

    if $protontricks_cmd --no-bwrap "$selected_appid" -q "${components[@]}" > /tmp/mo2helper_install.log 2>&1; then
        echo "Successfully installed components!"
        log "Dependencies installed successfully"
    else
        status=$?
        cat /tmp/mo2helper_install.log >> "$log_file"
        log "Dependency installation failed with status $status"
        error_exit "Failed to install components. Check $log_file for details."
    fi
}

# Function to find game compatdata for a specific game
find_game_compatdata() {
    local appid="$1"
    local steam_root="$2"
    local steam_paths=("$steam_root")

    # Check libraryfolders.vdf for additional Steam library paths
    libraryfolders="$steam_root/steamapps/libraryfolders.vdf"
    if [ -f "$libraryfolders" ]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && steam_paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    # Search for compatdata in all Steam libraries
    for path in "${steam_paths[@]}"; do
        compatdata_path="$path/steamapps/compatdata/$appid"
        if [ -d "$compatdata_path" ]; then
            echo "$compatdata_path"
            return 0
        fi
    done

    # Return empty if not found
    echo ""
    return 1
}

# Consolidated function for finding game-specific compatdata
find_enderal_compatdata() {
    find_game_compatdata "976620" "$(get_steam_root)"
}

find_fnv_compatdata() {
    find_game_compatdata "22380" "$(get_steam_root)"
}

find_bg3_compatdata() {
    find_game_compatdata "1086940" "$(get_steam_root)"
}

# Generate game advice text
generate_advice() {
    log "Generating game advice"
    local steam_root=$(get_steam_root)

    # Check for specific games
    bg3_compatdata=$(find_game_compatdata "1086940" "$steam_root")
    fnv_compatdata=$(find_game_compatdata "22380" "$steam_root")
    enderal_compatdata=$(find_game_compatdata "976620" "$steam_root")

    # Add these color variables
    color_cmd="\033[38;2;0;185;255m"  # #00b9ff for commands
    color_header="\033[1;33m\033[4m"  # Yellow underline for header
    color_skip="\033[90m"             # Gray for skip messages
    color_reset="\033[0m"

    echo -e "\n${color_header}=== Game-Specific Launch Options ===${color_reset}"

    # BG3 advice
    if [ -n "$bg3_compatdata" ]; then
        echo -e "\nFor Baldur's Gate 3 modlists:"
        echo -e "  ${color_cmd}WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%${color_reset}"
        log "Provided BG3 advice (found compatdata)"
    else
        echo -e "\n${color_skip}(Skip BG3 advice: not installed or not run yet)${color_reset}"
        log "Skipped BG3 advice (no compatdata found)"
    fi

    # FNV advice
    if [ -n "$fnv_compatdata" ]; then
        echo -e "\nFor Fallout New Vegas modlists:"
        echo -e "  ${color_cmd}STEAM_COMPAT_DATA_PATH=\"$fnv_compatdata\" %command%${color_reset}"
        log "Provided FNV advice (found compatdata)"
    else
        echo -e "\n${color_skip}(Skip FNV advice: not installed or not run yet)${color_reset}"
        log "Skipped FNV advice (no compatdata found)"
    fi

    # Enderal advice
    if [ -n "$enderal_compatdata" ]; then
        echo -e "\nFor Enderal modlists:"
        echo -e "  ${color_cmd}STEAM_COMPAT_DATA_PATH=\"$enderal_compatdata\" %command%${color_reset}"
        log "Provided Enderal advice (found compatdata)"
    else
        echo -e "\n${color_skip}(Skip Enderal advice: not installed or not run yet)${color_reset}"
        log "Skipped Enderal advice (no compatdata found)"
    fi

    # DPI scaling advice section removed since it's redundant
}

action_submenu() {
    log "Showing action submenu for $selected_name"

    while true; do
        echo -e "\n=== Action Selection for $selected_name ==="
        echo "1. Install Proton dependencies"
        echo "2. Setup NXM handling"
        echo "3. Set Proton DPI scaling"
        echo "4. Proceed to advice"
        read -rp "Select an option (1-4): " sub_choice

        case "$sub_choice" in
            1)
                install_proton_dependencies
                ;;
            2)
                setup_nxm_handler
                ;;
            3)
                select_dpi_scaling
                apply_dpi_scaling
                ;;
            4)
                log "Exiting submenu to show advice"
                generate_advice
                ;;
            *)
                echo "Invalid option. Try again."
                log "Invalid submenu option: $sub_choice"
                ;;
        esac
    done
}

main_menu() {
    log "Displaying main menu"
    echo -e "\n=== Mod Organizer 2 Linux Helper ==="
    echo "1. Setup NXM Link Handler and/or Install Dependencies"
    echo "2. Exit"

    while true; do
        read -rp "Select an option (1-2): " choice
        case $choice in
            1)
                log "Option 1 selected: Setup/Install"
                check_dependencies
                get_non_steam_games
                debug_game_info
                select_game
                action_submenu
                return
                ;;
            2)
                log "Option 2 selected: Exit"
                exit 0
                ;;
            *)
                echo "Invalid option. Try again."
                log "Invalid menu option: $choice"
                ;;
        esac
    done
}

# Main script starts here
log "Starting MO2 Helper TUI"

while true; do
    main_menu
    read -rp "Would you like to perform another action? (y/n) " continue
    log "Continue prompt response: $continue"
    [[ "$continue" =~ ^[Yy] ]] || break
done

echo -e "\nAll operations completed successfully!"
log "All operations completed successfully"
