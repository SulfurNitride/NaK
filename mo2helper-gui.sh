#!/bin/bash
# -------------------------------------------------------------------
# modorganizer2-helper-gui.sh
# GUI version of MO2 helper using Zenity
# All windows set to 854x480 (480p) resolution
# -------------------------------------------------------------------

# Log file
log_file="$HOME/mo2helper.log"

# Ensure log file exists
echo "MO2 Helper GUI Log - $(date)" > "$log_file"
echo "=============================" >> "$log_file"

# Set standard window dimensions (480p)
WINDOW_WIDTH=854
WINDOW_HEIGHT=480

# Function to log messages
log() {
    echo "[$(date +%T)] $1" >> "$log_file"
}

# Function to show error dialog and exit
show_error() {
    zenity --error --title="MO2 Helper Error" --text="$1" --width=$WINDOW_WIDTH
    log "ERROR: $1"
    exit 1
}

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Check if zenity is installed
if ! command_exists zenity; then
    echo "Error: zenity is not installed. Please install it with your package manager."
    echo "For example: sudo dnf install zenity"
    log "ERROR: zenity not found"
    exit 1
fi

# Common variables
declare -a game_array
protontricks_cmd=""
selected_appid=""
selected_name=""

# Check dependencies
check_dependencies() {
    log "Checking dependencies"

    if ! command_exists protontricks && \
       ! flatpak list --app --columns=application 2>/dev/null | grep -q com.github.Matoking.protontricks; then
        show_error "Protontricks is not installed. Install it with:
Please don't install it with APT or PIPX as there are errors associated with it!
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

# Check for Flatpak Steam
check_flatpak_steam() {
    log "Checking for Flatpak Steam"

    if flatpak list --app --columns=application 2>/dev/null | grep -q 'com.valvesoftware.Steam'; then
        show_error "Detected Steam installed via Flatpak. This script doesn't support Flatpak Steam installations."
    fi
}

# Get Steam installation directory
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

    show_error "Could not find Steam installation in standard locations."
}

# Find Proton Experimental installation
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

    show_error "Proton - Experimental not found. Please install it through Steam."
}

# Get list of non-Steam games from protontricks
get_non_steam_games() {
    echo "Fetching non-Steam games..." | tee -a "$log_file"

    # Capture protontricks output with error logging
    local protontricks_output
    if ! protontricks_output=$($protontricks_cmd --list 2>&1); then
        echo "Error running protontricks:" >> "$log_file"
        echo "$protontricks_output" >> "$log_file"
        exit 1
    fi
    echo "Protontricks output received, processing" | tee -a "$log_file"
    echo "$protontricks_output" >> "$log_file"

    # Try a simplified parsing method that's more compatible
    echo "Using simplified parsing method" | tee -a "$log_file"
    local games=""
    while IFS= read -r line; do
        if [[ "$line" =~ "Non-Steam shortcut:" ]]; then
            if [[ "$line" =~ \(([0-9]+)\)$ ]]; then
                appid="${BASH_REMATCH[1]}"
                name=$(echo "$line" | sed -E 's/.*Non-Steam shortcut: (.*) \([0-9]+\)$/\1/')
                echo "Found game: $appid:$name" | tee -a "$log_file"
                games="$games$appid:$name"$'\n'
            fi
        fi
    done <<< "$protontricks_output"

    # Log what we found
    echo "Parsed games output:" | tee -a "$log_file"
    echo "$games" | tee -a "$log_file"

    # Remove trailing newline
    games=$(echo "$games" | sed '/^$/d')

    # Check if we actually found any games
    if [ -z "$games" ]; then
        echo "ERROR: No non-Steam games found! Make sure you've added non-Steam games to Steam and launched them at least once." | tee -a "$log_file"
        exit 1
    fi

    IFS=$'\n' read -d '' -ra game_array <<< "$games"

    # Additional check to make sure game array is not empty
    if [ ${#game_array[@]} -eq 0 ]; then
        echo "ERROR: Failed to parse any games into the array." | tee -a "$log_file"
        exit 1
    else
        echo "Successfully found ${#game_array[@]} games" | tee -a "$log_file"
    fi
}

debug_game_info() {
    echo "DEBUG: Found games:" >> "$log_file"
    for i in "${!game_array[@]}"; do
        echo "  [$i] ${game_array[$i]}" >> "$log_file"
    done
}

# Find compatdata for a specific game
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

# Register NXM MIME handler
register_mime_handler() {
    log "Registering NXM MIME handler"

    if xdg-mime default modorganizer2-nxm-handler.desktop x-scheme-handler/nxm 2>/dev/null ; then
        log "Success (via xdg-mime)"
        return 0
    else
        local mimeapps="$HOME/.config/mimeapps.list"
        [ -f "$mimeapps" ] || touch "$mimeapps"
        sed -i '/x-scheme-handler\/nxm/d' "$mimeapps"
        echo "x-scheme-handler/nxm=modorganizer2-nxm-handler.desktop" >> "$mimeapps"
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        log "Manual registration complete"
        return 0
    fi
}

# Setup NXM handler for selected game
setup_nxm_handler() {
    log "Setting up NXM handler for $selected_name (AppID: $selected_appid)"

    # Ask for nxmhandler.exe path
    nxmhandler_path=$(zenity --file-selection --title="Select nxmhandler.exe" --file-filter="*.exe" --width=$WINDOW_WIDTH --height=$WINDOW_HEIGHT)

    if [ -z "$nxmhandler_path" ]; then
        log "NXM handler setup cancelled"
        return 1
    fi

    if [ ! -f "$nxmhandler_path" ]; then
        show_error "Selected file does not exist: $nxmhandler_path"
    fi

    log "Selected nxmhandler.exe: $nxmhandler_path"

    # Create desktop file
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

    zenity --info --title="MO2 Helper" --text="NXM Handler setup complete!" --width=$WINDOW_WIDTH
    return 0
}

# Install Proton dependencies for selected game
install_proton_dependencies() {
    log "Installing dependencies for $selected_name (AppID: $selected_appid)"

    components=(
        fontsmooth=rgb xact xact_x64 vcrun2022 dotnet6
        dotnet7 dotnet8 d3dcompiler_47 d3dx11_43
        d3dcompiler_43 d3dx9_43 d3dx9 vkd3d
    )

    # Show confirmation dialog
    if ! zenity --question --title="MO2 Helper" --text="Install dependencies for $selected_name?\n\nThis may take several minutes." --width=$WINDOW_WIDTH; then
        log "Dependency installation cancelled"
        return 1
    fi

    # Show progress dialog
    (
        echo "0"; echo "# Starting installation..."

        # Run protontricks
        log "Running: $protontricks_cmd --no-bwrap $selected_appid -q ${components[*]}"

        # Start protontricks in background and monitor output
        $protontricks_cmd --no-bwrap "$selected_appid" -q "${components[@]}" > /tmp/mo2helper_install.log 2>&1 &
        pid=$!

        # Show progress while process is running
        progress=10
        while kill -0 $pid 2>/dev/null; do
            if [ $progress -lt 90 ]; then
                progress=$((progress + 1))
                echo $progress
                echo "# Installing components... Please wait."
                sleep 1
            else
                echo 90
                echo "# Installation in progress... This may take a while."
                sleep 2
            fi
        done

        # Check if process completed successfully
        wait $pid
        status=$?

        if [ $status -eq 0 ]; then
            echo "100"; echo "# Installation completed successfully!"
            log "Dependencies installed successfully"
        else
            echo "100"; echo "# Installation failed. Check log for details."
            log "Dependency installation failed with status $status"
            # Copy output to log
            cat /tmp/mo2helper_install.log >> "$log_file"
        fi
    ) | zenity --progress --title="MO2 Helper" --text="Installing dependencies..." --percentage=0 --auto-close --width=$WINDOW_WIDTH --height=$WINDOW_HEIGHT

    # Check result
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        zenity --info --title="MO2 Helper" --text="Dependencies installed successfully!" --width=$WINDOW_WIDTH
        return 0
    else
        zenity --error --title="MO2 Helper" --text="Failed to install dependencies. Check $log_file for details." --width=$WINDOW_WIDTH
        return 1
    fi
}

# Generate game advice text
generate_advice() {
    log "Generating game advice"

    # Check for specific games
    bg3_compatdata=$(find_game_compatdata "1086940" "$steam_root")
    fnv_compatdata=$(find_game_compatdata "22380" "$steam_root")
    enderal_compatdata=$(find_game_compatdata "976620" "$steam_root")

    # Build advice text with proper newlines (no escape sequences)
    advice_text="=== Game-Specific Launch Options ===

"
    # BG3 advice
    if [ -n "$bg3_compatdata" ]; then
        advice_text+="For Baldur's Gate 3 modlists:
  WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%

"
    else
        advice_text+="(Skip BG3 advice: not installed or not run yet)

"
    fi

    # FNV advice
    if [ -n "$fnv_compatdata" ]; then
        advice_text+="For Fallout New Vegas modlists:
  STEAM_COMPAT_DATA_PATH=\"$fnv_compatdata\" %command%

"
    else
        advice_text+="(Skip FNV advice: not installed or not run yet)

"
    fi

    # Enderal advice
    if [ -n "$enderal_compatdata" ]; then
        advice_text+="For Enderal modlists:
  STEAM_COMPAT_DATA_PATH=\"$enderal_compatdata\" %command%

"
    else
        advice_text+="(Skip Enderal advice: not installed or not run yet)

"
    fi
    echo "$advice_text"
}

# Show game advice
show_advice() {
    advice_text=$(generate_advice)
    echo "$advice_text" | zenity --text-info --title="MO2 Helper - Game Advice" --width=$WINDOW_WIDTH --height=$WINDOW_HEIGHT --font="monospace"
}

# Select a game from the list - FIXED VERSION
select_game() {
    log "Showing game selection dialog"

    # Create arrays for zenity list
    local appids=()
    local names=()

    # Populate arrays from game_array
    for game in "${game_array[@]}"; do
        IFS=':' read -r appid name <<< "$game"
        appids+=("$appid")
        names+=("$name")
    done

    # Log game count
    log "Prepared ${#appids[@]} games for selection dialog"

    # Build zenity command with all games explicitly listed
    cmd=("zenity" "--list" "--title=MO2 Helper - Select Game" "--width=$WINDOW_WIDTH" "--height=$WINDOW_HEIGHT"
         "--text=Select a non-Steam game:" "--column=AppID" "--column=Game Name" "--print-column=1")

    # Add each game to the command
    for i in "${!appids[@]}"; do
        cmd+=("${appids[$i]}" "${names[$i]}")
    done

    # Run the command and capture output
    selection=$("${cmd[@]}")

    # Check if selection was made
    if [ -z "$selection" ]; then
        log "Game selection cancelled"
        return 1
    fi

    selected_appid="$selection"

    # Find the name for the selected AppID
    for i in "${!appids[@]}"; do
        if [ "${appids[$i]}" = "$selected_appid" ]; then
            selected_name="${names[$i]}"
            break
        fi
    done

    log "Selected game: $selected_name (AppID: $selected_appid)"

    # Show success message
    zenity --info --title="MO2 Helper" --text="Selected: $selected_name (AppID: $selected_appid)" --width=$WINDOW_WIDTH
    return 0
}

# Main menu
main_menu() {
    while true; do
        choice=$(zenity --list --title="MO2 Helper" --text="Mod Organizer 2 Linux Helper" \
                --column="Option" --column="Description" \
                "select" "Select Non-Steam Game" \
                "deps" "Install Proton Dependencies" \
                "nxm" "Setup NXM Link Handler" \
                "advice" "Show Game-Specific Advice" \
                "exit" "Exit" \
                --width=$WINDOW_WIDTH --height=$WINDOW_HEIGHT)

        case "$choice" in
            "select")
                select_game
                ;;
            "deps")
                if [ -z "$selected_appid" ]; then
                    zenity --info --title="MO2 Helper" --text="Please select a game first" --width=$WINDOW_WIDTH
                else
                    install_proton_dependencies
                fi
                ;;
            "nxm")
                if [ -z "$selected_appid" ]; then
                    zenity --info --title="MO2 Helper" --text="Please select a game first" --width=$WINDOW_WIDTH
                else
                    setup_nxm_handler
                fi
                ;;
            "advice")
                show_advice
                ;;
            "exit"|"")
                log "Exiting application"
                exit 0
                ;;
        esac
    done
}

# Main script starts here
log "Starting MO2 Helper GUI"

# Check if zenity is available
if ! command_exists zenity; then
    echo "Error: zenity is not installed. This script requires zenity for the GUI."
    log "Error: zenity not found"
    exit 1
fi

# Show welcome message
zenity --info --title="MO2 Helper" --text="Welcome to MO2 Helper GUI!\n\nThis tool helps set up Mod Organizer 2 on Linux." --width=$WINDOW_WIDTH

# Initialize
check_dependencies
check_flatpak_steam
steam_root=$(get_steam_root)
proton_path=$(find_proton_path "$steam_root")

# Get list of games and show main menu
get_non_steam_games
debug_game_info
main_menu
