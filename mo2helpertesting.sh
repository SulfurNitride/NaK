#!/bin/bash
# -------------------------------------------------------------------
# modorganizer2-helper.sh
# Complete unified script with FNV fixes and Proton initialization
# -------------------------------------------------------------------

# Common variables
declare -a game_array
protontricks_cmd=""
selected_appid=""
selected_name=""

# Dependency checks
check_dependencies() {
    if ! command -v protontricks &> /dev/null && \
       ! flatpak list --app --columns=application | grep -q com.github.Matoking.protontricks; then
        echo "Error: protontricks is not installed. Install it with:"
        echo "  Native: sudo apt install protontricks"
        echo "  Flatpak: flatpak install com.github.Matoking.protontricks"
        exit 1
    fi

    if command -v protontricks &> /dev/null; then
        protontricks_cmd="protontricks"
    else
        protontricks_cmd="flatpak run com.github.Matoking.protontricks"
    fi
}

check_flatpak_steam() {
    if flatpak list --app --columns=application | grep -q 'com.valvesoftware.Steam'; then
        echo "ERROR: Detected Steam installed via Flatpak."
        echo "This script doesn't support Flatpak Steam installations."
        exit 1
    fi
}

get_steam_root() {
    local candidates=(
        "$HOME/.local/share/Steam"
        "$HOME/.steam/steam"
        "$HOME/.steam/debian-installation"
        "/usr/local/steam"
        "/usr/share/steam"
    )

    for candidate in "${candidates[@]}"; do
        if [ -d "$candidate/steamapps" ]; then
            echo "$candidate"
            return
        fi
    done

    echo "Error: Could not find Steam installation in:" >&2
    printf "  - %s\n" "${candidates[@]}" >&2
    exit 1
}

get_non_steam_games() {
    echo "Fetching non-Steam games..."
    games=$($protontricks_cmd --list | grep -E "Non-Steam shortcut:|^[0-9]+" | awk '
        /Non-Steam shortcut:/ {
            split($0, a, /: /);
            match(a[2], /(.*) \(([0-9]+)\)/, matches);
            if (matches[2] != "") {
                printf "%s:%s\n", matches[2], matches[1]
            }
        }
        /^[0-9]+/ {
            if ($1 == "22380") {
                printf "22380:Fallout New Vegas (Steam)\n"
            }
        }
    ')

    if [ -z "$games" ]; then
        echo "No non-Steam games found!"
        exit 1
    fi

    if ! grep -q "22380:" <<< "$games"; then
        games+=$'\n22380:Fallout New Vegas (Steam)'
    fi

    IFS=$'\n' read -d '' -ra game_array <<< "$games"
}

select_game() {
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
            break
        else
            echo "Invalid choice. Try again."
        fi
    done
}

find_proton_path() {
    local steam_root=$(get_steam_root)
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
            echo "$proton_candidate"
            return
        fi
    done

    echo "Error: Proton - Experimental not found in:" >&2
    printf "  - %s\n" "${steam_paths[@]/%//steamapps/common/Proton - Experimental/proton}" >&2
    exit 1
}

register_mime_handler() {
    echo -n "Registering nxm:// handler... "
    if xdg-mime default modorganizer2-nxm-handler.desktop x-scheme-handler/nxm 2>/dev/null ; then
        echo "Success (via xdg-mime)"
    else
        local mimeapps="$HOME/.config/mimeapps.list"
        [ -f "$mimeapps" ] || touch "$mimeapps"
        sed -i '/x-scheme-handler\/nxm/d' "$mimeapps"
        echo "x-scheme-handler/nxm=modorganizer2-nxm-handler.desktop" >> "$mimeapps"
        update-desktop-database "$HOME/.local/share/applications"
        echo "Manual registration complete!"
    fi
}

setup_nxm_handler() {
    echo -e "\n=== NXM Link Handler Setup ==="
    check_flatpak_steam
    local steam_root=$(get_steam_root)
    local proton_path=$(find_proton_path)

    while true; do
        read -rp "Enter FULL path to nxmhandler.exe: " nxmhandler_path
        [ -f "$nxmhandler_path" ] && break
        echo "File not found! Try again."
    done

    steam_compat_data_path="$steam_root/steamapps/compatdata/$selected_appid"
    desktop_file="$HOME/.local/share/applications/modorganizer2-nxm-handler.desktop"

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
}

install_proton_dependencies() {
    echo -e "\n=== Proton Dependency Installation ==="
    components=(
        fontsmooth=rgb xact xact_x64 vcrun2022 dotnet6
        dotnet7 dotnet8 d3dcompiler_47 d3dx11_43
        d3dcompiler_43 d3dx9_43 d3dx9 dwrite=native
    )

    echo "Installing components for $selected_name (AppID: $selected_appid)..."
    echo "This may take several minutes..."

    if $protontricks_cmd --no-bwrap "$selected_appid" -q "${components[@]}"; then
        echo "Successfully installed components!"
    else
        echo "Error: Failed to install components."
        exit 1
    fi
}

configure_fnv_launch() {
    echo -e "\n=== Fallout New Vegas MO2 Launcher Setup ==="
    selected_appid="22380"
    selected_name="Fallout New Vegas (Steam)"

    # Prompt for Proton dependencies
    read -rp "Would you like to install Proton dependencies for $selected_name? (y/n) " dep_choice
    if [[ "$dep_choice" =~ ^[Yy] ]]; then
        install_proton_dependencies
    fi

    local steam_root=$(get_steam_root)
    local proton_path=$(find_proton_path)

    # Multi-library game detection
    local game_path
    local library_path
    local steam_paths=("$steam_root")
    libraryfolders="$steam_root/steamapps/libraryfolders.vdf"

    if [ -f "$libraryfolders" ]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && steam_paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    # Find game installation and its library path
    for path in "${steam_paths[@]}"; do
        candidate="$path/steamapps/common/Fallout New Vegas"
        if [ -f "$candidate/FalloutNV.exe" ]; then
            game_path="$candidate"
            library_path="${candidate%/steamapps/common/Fallout New Vegas*}"
            break
        fi
    done

    if [ -z "$game_path" ]; then
        echo "Error: Fallout New Vegas installation not found in:"
        printf "  - %s/steamapps/common/Fallout New Vegas\n" "${steam_paths[@]}"
        return 1
    fi

    # MO2 path validation
    local mo2_path
    while true; do
        read -rp "Enter FULL path to ModOrganizer.exe: " mo2_path
        mo2_path=$(realpath "$mo2_path")
        if [ -f "$mo2_path" ]; then
            break
        else
            echo "Error: ModOrganizer.exe not found at: $mo2_path"
        fi
    done

    if [ -z "$library_path" ]; then
        echo "ERROR: Failed to find Steam library path for Fallout New Vegas!"
        exit 1
    fi

    compat_dir="$library_path/steamapps/compatdata/$selected_appid"

    # Define launch_script FIRST
    local launch_script="$HOME/.local/bin/fnv-mo2-launcher"

    # THEN create its directory
    mkdir -p "$(dirname "$launch_script")" || {
        echo "Error: Failed to create directory for launcher script!"
        exit 1
    }

    # Add compatibility directory verification
    if [ ! -d "$compat_dir" ]; then
        echo "WARNING: Proton prefix not found at: $compat_dir"
        echo "A new prefix will be created on first launch."
    fi

    cat << EOF > "$launch_script"
#!/bin/bash
# Force-resolve paths at launch time
STEAM_ROOT=\$(get_steam_root)
export STEAM_COMPAT_DATA_PATH="$compat_dir"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="\$STEAM_ROOT"
export WINEPREFIX="\$STEAM_COMPAT_DATA_PATH/pfx"

# Fix permissions for Steam runtime binaries
find "\$STEAM_RUNTIME" -name "steam-launch-wrapper" -exec chmod +x {} \;

# Wine path translation workaround
export WINEESYNC=1
export WINEFSYNC=1
export WINEDEBUG=-all
export WINEARCH=win64

# Proton initialization
validate_paths() {
    PROTON_PATH="$proton_path"
    if [ ! -f "\$PROTON_PATH" ]; then
        echo "ERROR: Proton missing at \$PROTON_PATH!"
        exit 1
    fi

    MO2_PATH="$mo2_path"
    if [ ! -f "\$MO2_PATH" ]; then
        echo "ERROR: ModOrganizer.exe missing at \$MO2_PATH!"
        exit 1
    fi
}

# Create prefix if missing
if [ ! -d "\$STEAM_COMPAT_DATA_PATH" ]; then
    echo "Initializing Proton prefix..."
    mkdir -p "\$STEAM_COMPAT_DATA_PATH"
    "$proton_path" run notepad.exe &>/dev/null
    sleep 5
fi

validate_paths

# Launch command
cd "\$(dirname "\$MO2_PATH")"
"\$PROTON_PATH" run ./ModOrganizer.exe
EOF

    chmod +x "$launch_script"

    # Create desktop entry
    local desktop_file="$HOME/.local/share/applications/mo2-fnv.desktop"
    cat << EOF > "$desktop_file"
[Desktop Entry]
Type=Application
Name=MO2 - Fallout New Vegas
Exec=env STEAM_COMPAT_MOUNTS="/mnt:/home" $launch_script
Icon=steam_icon_$selected_appid
Categories=Game;
Terminal=false
EOF

    read -rp "Would you like to associate NXM links for Fallout New Vegas? (y/n) " associate_nxm
    if [[ "$associate_nxm" =~ ^[Yy] ]]; then
        echo -e "\n=== NXM Handler Setup for Fallout New Vegas ==="
        while true; do
            read -rp "Enter FULL path to nxmhandler.exe: " nxmhandler_path
            [ -f "$nxmhandler_path" ] && break
            echo "File not found! Try again."
        done

        # Use the CORRECT library path where FNV was found
        steam_compat_data_path="$library_path/steamapps/compatdata/$selected_appid"
        desktop_file="$HOME/.local/share/applications/modorganizer2-nxm-handler.desktop"

        cat << EOF > "$desktop_file"
[Desktop Entry]
Type=Application
Categories=Game;
Exec=bash -c 'env "STEAM_COMPAT_CLIENT_INSTALL_PATH=$steam_root" "STEAM_COMPAT_DATA_PATH=$steam_compat_data_path" "$proton_path" run "$nxmhandler_path" "%u"'
Name=Mod Organizer 2 NXM Handler (FNV)
MimeType=x-scheme-handler/nxm;
NoDisplay=true
EOF

        chmod +x "$desktop_file"
        register_mime_handler
    fi

    echo -e "\n=== Final Fixes Required ==="
    echo "1. In Steam Launch Options:"
    echo "   \"$launch_script\" %command%"
}

main_menu() {
    echo -e "\n=== Mod Organizer 2 Linux Helper ==="
    echo "1. Setup NXM Link Handler and Install Dependencies"
    echo "2. Configure Fallout New Vegas MO2 Launch and Install Dependencies"
    echo "3. Exit"

    while true; do
        read -rp "Select an option (1-3): " choice
        case $choice in
            1)
                check_dependencies
                get_non_steam_games
                select_game
                setup_nxm_handler
                read -rp "Would you like to install Proton dependencies for $selected_name? (y/n) " dep_choice
                if [[ "$dep_choice" =~ ^[Yy] ]]; then
                    install_proton_dependencies
                fi
                return
                ;;
            2)
                check_dependencies
                configure_fnv_launch  # Now includes dependency installation prompt
                return
                ;;
            3)
                exit 0
                ;;
            *)
                echo "Invalid option. Try again."
                ;;
        esac
    done
}

while true; do
    main_menu
    read -rp "Would you like to perform another action? (y/n) " continue
    [[ "$continue" =~ ^[Yy] ]] || break
done

echo -e "\nAll operations completed successfully!"
