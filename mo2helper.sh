#!/bin/bash
# -------------------------------------------------------------------
# modorganizer2-helper.sh
# Unified script with NXM handler and Proton setup
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
    ')

    if [ -z "$games" ]; then
        echo "No non-Steam games found!"
        exit 1
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
        d3dcompiler_43 d3dx9_43 d3dx9 vkd3d
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

find_fnv_compatdata() {
    local steam_root=$(get_steam_root)
    local steam_paths=("$steam_root")

    # Check libraryfolders.vdf for additional Steam library paths
    libraryfolders="$steam_root/steamapps/libraryfolders.vdf"
    if [ -f "$libraryfolders" ]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && steam_paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    # Search for Fallout New Vegas compatdata in all Steam libraries
    for path in "${steam_paths[@]}"; do
        compatdata_path="$path/steamapps/compatdata/22380"
        if [ -d "$compatdata_path" ]; then
            echo "$compatdata_path"
            return 0
        fi
    done

    # Return empty if not found (no error)
    echo ""
    return 1
}

main_menu() {
    echo -e "\n=== Mod Organizer 2 Linux Helper ==="
    echo "1. Setup NXM Link Handler and Install Dependencies"
    echo "2. Exit"

    while true; do
        read -rp "Select an option (1-2): " choice
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

                # -------------------------------
                # Display ADVICE (not requirements)
                # -------------------------------
                echo -e "\n\033[1;33m=== Optional Game-Specific Advice ===\033[0m"

                # Baldur's Gate 3 (always shown)
                echo -e "\nFor Baldur's Gate 3 modlists, add this to Steam launch options:"
                echo "WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%"

                # Fallout New Vegas (only if compatdata exists)
                fnv_compatdata=$(find_fnv_compatdata)
                if [ -n "$fnv_compatdata" ]; then
                    echo -e "\nFor Fallout New Vegas modlists, add this to Steam launch options:"
                    echo "STEAM_COMPAT_DATA_PATH=\"$fnv_compatdata\" %command%"
                else
                    echo -e "\n\033[90m(Skip Fallout New Vegas advice: not installed or not run yet)\033[0m"
                fi

                return
                ;;
            2)
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
