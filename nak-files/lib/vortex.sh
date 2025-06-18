#!/bin/bash
# -------------------------------------------------------------------
# vortex.sh
# Functions for downloading and installing Vortex
# -------------------------------------------------------------------

# Function to download and install the latest Vortex release
download_vortex() {
    log_info "Starting Vortex download and installation process"

    print_section "Download and Install Vortex"

    # Check for required dependencies
    if ! check_download_dependencies; then
        handle_error "Required dependencies missing for download" false
        return 1
    fi

    # Check if system Wine is available as a fallback
    local use_system_wine=false
    if command_exists wine; then
        use_system_wine=true
        echo -e "${color_green}System Wine detected. Will use it for installation.${color_reset}"
    fi

    local tracker=$(start_progress_tracking "Downloading Vortex" 120)

    # Fetch the latest release info from GitHub
    echo -e "Fetching latest release information from GitHub..."
    local release_info
    if ! release_info=$(curl -s https://api.github.com/repos/Nexus-Mods/Vortex/releases/latest); then
        end_progress_tracking "$tracker" false
        handle_error "Failed to fetch release information from GitHub. Check your internet connection." false
        return 1
    fi

    update_progress "$tracker" 10 100

    # Extract release version
    local version=$(echo "$release_info" | jq -r '.tag_name')
    version=${version#v}  # Remove 'v' prefix if present

    echo -e "Latest version: ${color_green}$version${color_reset}"

    # Find the correct asset (vortex-setup-*.exe)
    local download_url
    download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("^vortex-setup-[0-9.]+\\.exe$")) | .browser_download_url')

    if [ -z "$download_url" ]; then
        end_progress_tracking "$tracker" false
        handle_error "Could not find appropriate vortex-setup-*.exe asset in the latest release" false
        return 1
    fi

    local filename=$(basename "$download_url")
    echo -e "Found asset: ${color_blue}$filename${color_reset}"

    update_progress "$tracker" 20 100

    # Create a temporary directory for the download
    local temp_dir=$(mktemp -d)
    TEMP_FILES+=("$temp_dir")
    local temp_file="$temp_dir/$filename"

    # Download the file
    echo -e "\nDownloading Vortex v$version..."
    echo -e "From: ${color_blue}$download_url${color_reset}"
    echo -e "To: ${color_blue}$temp_file${color_reset}"

    if ! curl -L -o "$temp_file" "$download_url"; then
        end_progress_tracking "$tracker" false
        handle_error "Failed to download Vortex. Check your internet connection." false
        return 1
    fi

    update_progress "$tracker" 50 100

    # Ask user where to install Vortex
    echo -e "\nWhere would you like to install Vortex?"
    read_with_tab_completion "Install to directory" "$HOME/Vortex" "install_dir"

    # Create the directory if it doesn't exist
    if [ ! -d "$install_dir" ]; then
        echo -e "Directory doesn't exist. Creating it..."
        mkdir -p "$install_dir"
        if [ $? -ne 0 ]; then
            end_progress_tracking "$tracker" false
            handle_error "Failed to create directory: $install_dir" false
            return 1
        fi
    fi

    # Convert Linux path to proper Wine path (Z:\path\with\backslashes)
    # Replace forward slashes with backslashes and add Z: prefix
    local wine_install_dir="Z:$(echo "$install_dir" | sed 's|/|\\|g')"

    # If we have system Wine, use it directly
    if $use_system_wine; then
        update_progress "$tracker" 60 100
        echo -e "\nInstalling Vortex to $install_dir using system Wine..."
        echo -e "This may take a few minutes. Please be patient."
        echo -e "Wine path: ${color_blue}$wine_install_dir${color_reset}"

        # Use Wine to run the installer silently
        WINEPREFIX="$HOME/.wine" wine "$temp_file" /S "/D=$wine_install_dir"
        local result=$?

        # Clean up temporary files
        rm -rf "$temp_dir" 2>/dev/null

        if [ $result -ne 0 ]; then
            end_progress_tracking "$tracker" false
            handle_error "Failed to install Vortex. Wine installation exited with code $result." false
            return 1
        fi
    else
        # We need to use Proton - which requires a prefix
        echo -e "\n${color_yellow}No system Wine found. We need to select a game to use its Proton prefix.${color_reset}"
        check_dependencies
        get_all_steam_games
        if ! select_game; then
            end_progress_tracking "$tracker" false
            handle_error "No game selected. A game is needed to use its Proton prefix." false
            return 1
        fi

        # Find the prefix path for the selected game
        local steam_root=$(get_steam_root)
        local compatdata_path=$(find_game_compatdata "$selected_appid" "$steam_root")
        local prefix_path="$compatdata_path/pfx"

        if [ ! -d "$prefix_path" ]; then
            end_progress_tracking "$tracker" false
            handle_error "Could not find Proton prefix at: $prefix_path" false
            return 1
        fi

        update_progress "$tracker" 60 100

        # Install Vortex using the selected game's Proton prefix
        echo -e "\nInstalling Vortex to $install_dir using $selected_name's Proton prefix..."
        echo -e "This may take a few minutes. Please be patient."
        echo -e "Wine path: ${color_blue}$wine_install_dir${color_reset}"

        # Run the installer with the existing run_with_proton_wine function
        run_with_proton_wine "$prefix_path" "$temp_file" "/S" "/D=$wine_install_dir"

        local result=$?

        # Clean up temporary files
        rm -rf "$temp_dir" 2>/dev/null

        if [ $result -ne 0 ]; then
            end_progress_tracking "$tracker" false
            handle_error "Failed to install Vortex. Installation exited with code $result." false
            return 1
        fi
    fi

    update_progress "$tracker" 90 100
    end_progress_tracking "$tracker" true

    # Check if installed successfully
    if [ ! -f "$install_dir/Vortex.exe" ]; then
        echo -e "\n${color_yellow}Warning: Vortex.exe was not found at the expected location.${color_reset}"
        echo -e "It's possible the installation completed but with a different structure."
        echo -e "Please check $install_dir to verify the installation."
    else
        echo -e "\n${color_green}Vortex v$version has been successfully installed to:${color_reset}"
        echo -e "${color_blue}$install_dir${color_reset}"
    fi

    # Ask if user wants to add to Steam
    echo -e "\nWould you like to add Vortex to Steam as a non-Steam game?"
    if confirm_action "Add to Steam?"; then
        add_vortex_to_steam "$install_dir"
    fi

    return 0
}

# Setup NXM handler for Vortex
setup_vortex_nxm_handler() {
    if [ -z "$selected_appid" ] || [ -z "$selected_name" ]; then
        handle_error "No game selected. Please select a game first." false
        return 1
    fi

    log_info "Setting up NXM handler for Vortex using $selected_name (AppID: $selected_appid)"

    print_section "Vortex NXM Link Handler Setup"
    check_flatpak_steam
    local steam_root=$(get_steam_root)

    local proton_path=$(find_proton_path "$steam_root")
    if [ -z "$proton_path" ]; then
        handle_error "Could not find Proton Experimental. Make sure it's installed in Steam." false
        return 1
    fi

    while true; do
        read_with_tab_completion "Enter FULL path to Vortex.exe (or 'b' to go back)" "" "vortex_path"

        # Check if user wants to go back
        if [[ "$vortex_path" == "b" || "$vortex_path" == "B" ]]; then
            log_info "User cancelled Vortex NXM handler setup"
            return 1
        fi

        if [ -f "$vortex_path" ]; then
            log_info "Selected Vortex.exe: $vortex_path"
            break
        fi

        echo -e "${color_red}File not found!${color_reset} Try again or enter 'b' to go back."
        log_warning "Invalid path: $vortex_path"
    done

    steam_compat_data_path="$steam_root/steamapps/compatdata/$selected_appid"
    desktop_file="$HOME/.local/share/applications/vortex-nxm-handler.desktop"

    log_info "Creating desktop file: $desktop_file"
    mkdir -p "$HOME/.local/share/applications"
    cat << EOF > "$desktop_file"
[Desktop Entry]
Type=Application
Categories=Game;
Exec=bash -c 'env "STEAM_COMPAT_CLIENT_INSTALL_PATH=$steam_root" "STEAM_COMPAT_DATA_PATH=$steam_compat_data_path" "$proton_path" run "$vortex_path" "-d" "%u"'
Name=Vortex NXM Handler
MimeType=x-scheme-handler/nxm;x-scheme-handler/nxm-protocol;
NoDisplay=true
EOF

    chmod +x "$desktop_file"

    # Register both nxm and nxm-protocol handlers
    echo -n "Registering nxm:// and nxm-protocol:// handlers... "

    # Register for nxm
    if xdg-mime default vortex-nxm-handler.desktop x-scheme-handler/nxm 2>/dev/null ; then
        echo -e "${color_green}Success for nxm${color_reset}"
        log_info "Success (via xdg-mime) for nxm"
    else
        local mimeapps="$HOME/.config/mimeapps.list"
        [ -f "$mimeapps" ] || touch "$mimeapps"
        sed -i '/x-scheme-handler\/nxm/d' "$mimeapps"
        echo "x-scheme-handler/nxm=vortex-nxm-handler.desktop" >> "$mimeapps"
        echo -e "${color_green}Manual registration for nxm complete${color_reset}"
        log_info "Manual registration complete for nxm"
    fi

    # Register for nxm-protocol
    if xdg-mime default vortex-nxm-handler.desktop x-scheme-handler/nxm-protocol 2>/dev/null ; then
        echo -e "${color_green}Success for nxm-protocol${color_reset}"
        log_info "Success (via xdg-mime) for nxm-protocol"
    else
        local mimeapps="$HOME/.config/mimeapps.list"
        [ -f "$mimeapps" ] || touch "$mimeapps"
        sed -i '/x-scheme-handler\/nxm-protocol/d' "$mimeapps"
        echo "x-scheme-handler/nxm-protocol=vortex-nxm-handler.desktop" >> "$mimeapps"
        echo -e "${color_green}Manual registration for nxm-protocol complete${color_reset}"
        log_info "Manual registration complete for nxm-protocol"
    fi

    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

    echo -e "\n${color_green}Vortex NXM Handler setup complete!${color_reset}"
    log_info "Vortex NXM Handler setup complete"

    return 0
}

# Function to add Vortex to Steam
add_vortex_to_steam() {
    local vortex_dir="$1"

    if [ -z "$vortex_dir" ] || [ ! -d "$vortex_dir" ]; then
        handle_error "Invalid Vortex directory" false
        return 1
    fi

    local vortex_exe="$vortex_dir/Vortex.exe"

    if [ ! -f "$vortex_exe" ]; then
        handle_error "Vortex.exe not found in $vortex_dir" false
        return 1
    fi

    print_section "Add Vortex to Steam"

    # Ask for custom name
    echo -e "What name would you like to use for Vortex in Steam?"
    read -rp "Name [Vortex]: " vortex_name

    # Use default name if none provided
    if [ -z "$vortex_name" ]; then
        vortex_name="Vortex"
    fi

    # Add to Steam using our vdf.sh function
    echo -e "\nAdding ${color_blue}$vortex_name${color_reset} to Steam..."
    local appid=$(add_game_to_steam "$vortex_name" "$vortex_exe" "$vortex_dir")

    if [ $? -eq 0 ] && [ -n "$appid" ]; then
        echo -e "\n${color_green}Successfully added Vortex to Steam!${color_reset}"
        echo -e "AppID: ${color_blue}$appid${color_reset}"
        echo -e "\nImportant: You should now:"
        echo -e "1. Restart Steam to see the newly added game"
        echo -e "2. Right-click on Vortex in Steam → Properties"
        echo -e "3. Check 'Force the use of a specific Steam Play compatibility tool'"
        echo -e "4. Select 'Proton Experimental' from the dropdown menu"

        return 0
    else
        handle_error "Failed to add Vortex to Steam" false
        return 1
    fi
}

# Function to set up Vortex from an existing installation
setup_existing_vortex() {
    print_section "Set Up Existing Vortex"

    echo -e "Please specify the location of your existing Vortex installation."
    read_with_tab_completion "Vortex directory" "" "vortex_dir"

    if [ -z "$vortex_dir" ]; then
        handle_error "No directory specified" false
        return 1
    fi

    if [ ! -d "$vortex_dir" ]; then
        handle_error "Directory does not exist: $vortex_dir" false
        return 1
    fi

    local vortex_exe="$vortex_dir/Vortex.exe"

    if [ ! -f "$vortex_exe" ]; then
        handle_error "Vortex.exe not found in $vortex_dir" false
        return 1
    fi

    echo -e "\n${color_green}Found Vortex.exe in: ${color_reset}${color_blue}$vortex_dir${color_reset}"

    # Ask if user wants to add to Steam
    echo -e "\nWould you like to add this Vortex installation to Steam as a non-Steam game?"
    if confirm_action "Add to Steam?"; then
        add_vortex_to_steam "$vortex_dir"
    fi

    return 0
}
