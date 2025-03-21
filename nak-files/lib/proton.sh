#!/bin/bash
# -------------------------------------------------------------------
# proton.sh
# Proton-specific functionality for MO2 Helper
# -------------------------------------------------------------------

# Find Proton path in Steam libraries
find_proton_path() {
    local steam_root="$1"
    log_info "Finding Proton path (Steam root: $steam_root)"

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
            log_info "Found Proton path: $proton_candidate"
            echo "$proton_candidate"
            return
        fi
    done

    log_error "Proton - Experimental not found"
    handle_error "Proton - Experimental not found in Steam libraries. Make sure it's installed." false
    return 1
}

# Register MIME handler for nxm:// protocol
register_mime_handler() {
    log_info "Registering NXM MIME handler"
    echo -n "Registering nxm:// handler... "

    if xdg-mime default modorganizer2-nxm-handler.desktop x-scheme-handler/nxm 2>/dev/null ; then
        echo -e "${color_green}Success (via xdg-mime)${color_reset}"
        log_info "Success (via xdg-mime)"
    else
        local mimeapps="$HOME/.config/mimeapps.list"
        [ -f "$mimeapps" ] || touch "$mimeapps"
        sed -i '/x-scheme-handler\/nxm/d' "$mimeapps"
        echo "x-scheme-handler/nxm=modorganizer2-nxm-handler.desktop" >> "$mimeapps"
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        echo -e "${color_green}Manual registration complete!${color_reset}"
        log_info "Manual registration complete"
    fi
}

# Setup NXM handler for Mod Organizer 2
setup_nxm_handler() {
    if [ -z "$selected_appid" ] || [ -z "$selected_name" ]; then
        handle_error "No game selected. Please select a game first." false
        return 1
    fi

    log_info "Setting up NXM handler for $selected_name (AppID: $selected_appid)"

    print_section "NXM Link Handler Setup"
    check_flatpak_steam
    local steam_root=$(get_steam_root)

    local proton_path=$(find_proton_path "$steam_root")
    if [ -z "$proton_path" ]; then
        handle_error "Could not find Proton Experimental. Make sure it's installed in Steam." false
        return 1
    fi

   while true; do
    read_with_tab_completion "Enter FULL path to nxmhandler.exe (or 'b' to go back)" "" "nxmhandler_path"

    # Check if user wants to go back
    if [[ "$nxmhandler_path" == "b" || "$nxmhandler_path" == "B" ]]; then
        log_info "User cancelled NXM handler setup"
        return 1
    fi

    if [ -f "$nxmhandler_path" ]; then
        log_info "Selected nxmhandler.exe: $nxmhandler_path"
        break
    fi

    echo -e "${color_red}File not found!${color_reset} Try again or enter 'b' to go back."
    log_warning "Invalid path: $nxmhandler_path"
done

    steam_compat_data_path="$steam_root/steamapps/compatdata/$selected_appid"
    desktop_file="$HOME/.local/share/applications/modorganizer2-nxm-handler.desktop"

    log_info "Creating desktop file: $desktop_file"
    mkdir -p "$HOME/.local/share/applications"
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

    echo -e "\n${color_green}NXM Handler setup complete!${color_reset}"
    log_info "NXM Handler setup complete"

    return 0
}

# Function to let user select DPI scaling
select_dpi_scaling() {
    log_info "Starting DPI scaling selection"

    # Get stored scaling from config if available
    local default_scaling=$(get_config "default_scaling" "96")

    print_section "DPI Scaling Selection"
    echo -e "Choose a DPI scaling value for Mod Organizer 2:"
    echo -e "${color_desc}Higher values make the UI larger. Recommended for HiDPI displays.${color_reset}\n"

    local scaling_options=(
        "96" "Standard scaling (100%)"
        "120" "Medium scaling (125%)"
        "144" "Large scaling (150%)"
        "192" "Extra large scaling (200%)"
        "Custom" "Enter a custom scaling value"
    )

    # Show menu with scaling options
    for ((i=0; i<${#scaling_options[@]}; i+=2)); do
        local option="${scaling_options[i]}"
        local description="${scaling_options[i+1]}"

        # Highlight default option
        if [ "$option" = "$default_scaling" ]; then
            echo -e "${color_option}$((i/2+1)). $option${color_reset} - $description ${color_green}(Current)${color_reset}"
        else
            echo -e "${color_option}$((i/2+1)). $option${color_reset} - $description"
        fi
    done

    # Get user choice
    local choice
    while true; do
        read -rp $'\nSelect a scaling option (1-'$((${#scaling_options[@]}/2))'): ' choice

        if [[ "$choice" =~ ^[0-9]+$ ]]; then
            if (( choice >= 1 && choice <= ${#scaling_options[@]}/2 )); then
                # Get selected option
                selected_scaling="${scaling_options[((choice-1)*2)]}"

                # If custom, prompt for value
                if [ "$selected_scaling" = "Custom" ]; then
                    while true; do
                        read -rp "Enter custom scaling value (96-240): " selected_scaling
                        if [[ "$selected_scaling" =~ ^[0-9]+$ ]] && (( selected_scaling >= 96 && selected_scaling <= 240 )); then
                            break
                        else
                            echo "Invalid scaling value. Please enter a number between 96 and 240."
                        fi
                    done
                fi

                log_info "Selected DPI scaling: $selected_scaling"
                set_config "default_scaling" "$selected_scaling"
                return 0
            fi
        fi

        echo "Invalid choice. Please try again."
    done
}


# Function to apply DPI scaling to selected game
# Function to apply DPI scaling to selected game
apply_dpi_scaling() {
    log_info "Applying DPI scaling ($selected_scaling) to game: $selected_name (AppID: $selected_appid)"

    if [ -z "$selected_appid" ] || [ -z "$selected_name" ]; then
        handle_error "No game selected. Please select a game first." false
        return 1
    fi

    if [ -z "$selected_scaling" ]; then
        handle_error "No scaling value selected. Please select a scaling value first." false
        return 1
    fi

    # Start progress tracking
    local tracker=$(start_progress_tracking "Applying DPI scaling" 20)

    print_section "Applying DPI Scaling"
    echo -e "Applying ${color_green}$selected_scaling DPI${color_reset} scaling to ${color_blue}$selected_name${color_reset}"

    # Find the prefix path for the selected game
    local steam_root=$(get_steam_root)
    local compatdata_path=$(find_game_compatdata "$selected_appid" "$steam_root")
    local prefix_path="$compatdata_path/pfx"

    log_info "Using compatdata path: $compatdata_path"

    if [ ! -d "$prefix_path" ]; then
        end_progress_tracking "$tracker" false
        handle_error "Could not find Proton prefix at: $prefix_path" false
        return 1
    fi

    update_progress "$tracker" 5 20

    # Create a Windows batch script to apply registry changes silently
    local batch_file=$(mktemp --suffix=.bat)
    TEMP_FILES+=("$batch_file")

    # Write Windows commands to the batch file
    echo "@echo off" > "$batch_file"
    echo "reg add \"HKCU\\Control Panel\\Desktop\" /v LogPixels /t REG_DWORD /d $selected_scaling /f" >> "$batch_file"
    echo "reg add \"HKCU\\Software\\Wine\\X11 Driver\" /v LogPixels /t REG_DWORD /d $selected_scaling /f" >> "$batch_file"
    echo "exit 0" >> "$batch_file"

    update_progress "$tracker" 10 20

    # Copy the batch file to the prefix
    local win_batch_file="$prefix_path/drive_c/temp_dpi.bat"
    mkdir -p "$prefix_path/drive_c/" 2>/dev/null
    cp "$batch_file" "$win_batch_file"
    chmod +x "$win_batch_file"

    log_info "Created batch file: $win_batch_file"

    # Run the batch file with a plain WINEPREFIX call (no GUI)
    echo -e "Applying registry changes silently..."
    log_info "Running batch file to set registry keys"

    WINEPREFIX="$prefix_path" wine cmd /c "C:\\temp_dpi.bat" > /dev/null 2>&1
    local result=$?

    # Clean up temporary batch file in the prefix
    rm -f "$win_batch_file" 2>/dev/null

    update_progress "$tracker" 20 20

    if [ $result -ne 0 ]; then
        end_progress_tracking "$tracker" false
        handle_error "Failed to apply registry changes. Check log for details." false
        return 1
    fi

    echo -e "\n${color_green}DPI scaling successfully applied!${color_reset}"
    echo -e "You need to ${color_yellow}restart Mod Organizer 2${color_reset} for changes to take effect."

    if $show_advice; then
        echo -e "\n${color_header}Tip:${color_reset} If text is too small or too large, try different scaling values."
        echo -e "     For most modern monitors, a value between 120-144 works well."
    fi

    end_progress_tracking "$tracker" true
    return 0
}

# Install Proton dependencies for a selected game
install_proton_dependencies() {
    if [ -z "$selected_appid" ] || [ -z "$selected_name" ]; then
        handle_error "No game selected. Please select a game first." false
        return 1
    fi

    log_info "Installing Proton dependencies for $selected_name (AppID: $selected_appid)"

    # Check if components are defined
    if [ "${#components[@]}" -eq 0 ]; then
        get_game_components "$selected_appid"
    fi

    print_section "Installing Dependencies"
    echo -e "Installing common dependencies for ${color_blue}$selected_name${color_reset}"
    echo -e "This may take some time. Please be patient.\n"

    # Show components to be installed
    echo -e "${color_header}Components to install:${color_reset}"
    for comp in "${components[@]}"; do
        echo -e "- $comp"
    done
    echo ""

    # Confirm installation
    if ! confirm_action "Continue with installation?"; then
        log_info "User canceled installation"
        return 1
    fi

    # Use a temp file for logging protontricks output
    local temp_log=$(mktemp)
    TEMP_FILES+=("$temp_log")

    # Install all components at once with --no-bwrap
    echo -e "\n${color_header}Installing all components...${color_reset}"
    echo -e "This will take several minutes. Please wait..."

    log_info "Running: $protontricks_cmd --no-bwrap $selected_appid -q ${components[*]}"

    # Show a simple spinner animation
    echo -n "Installing "

    # Run the installation in the background
    $protontricks_cmd --no-bwrap "$selected_appid" -q "${components[@]}" > "$temp_log" 2>&1 &
    local pid=$!

    # Simple spinner while waiting
    local chars="/-\|"
    while ps -p $pid > /dev/null; do
        for (( i=0; i<${#chars}; i++ )); do
            echo -en "\b${chars:$i:1}"
            sleep 0.2
        done
    done
    echo -en "\b"

    # Check the result
    wait $pid
    local status=$?

    if [ $status -eq 0 ]; then
        echo -e "\n${color_green}All dependencies installed successfully!${color_reset}"
        log_info "Dependencies installed successfully"
    else
        # Copy the temp log to our log file for debugging
        cat "$temp_log" >> "$log_file"
        log_error "Dependency installation failed with status $status"
        handle_error "Failed to install components. Check log for details." false
        echo -e "\n${color_yellow}Installation may be partially completed.${color_reset}"

        # Show the error from the temp log
        echo -e "\n${color_header}Error details:${color_reset}"
        tail -n 10 "$temp_log"

        # Wait for user to acknowledge the error
        pause "Review the error above and press any key to continue..."
        return 1
    fi

    # Offer some tips
    if $show_advice; then
        echo -e "\n${color_header}What's next?${color_reset}"
        echo -e "1. You can now run Mod Organizer 2 through Steam"
        echo -e "2. Consider setting up the NXM handler for easier mod downloads"
        echo -e "3. If text is too small, configure DPI scaling from the main menu"
        echo -e "4. Press any button to continue"
    fi

    # No need for a pause here since the calling function will pause
    return 0
}
