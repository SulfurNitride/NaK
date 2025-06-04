#!/bin/bash
# -------------------------------------------------------------------
# hoolamike.sh
# Hoolamike integration for MO2 Helper - Updated with dynamic MPI detection
# -------------------------------------------------------------------

# Function to find the actual MPI file in the Hoolamike directory
find_mpi_file() {
    local hoolamike_dir="$HOME/Hoolamike"
    
    # Look for any .mpi file in the directory
    local mpi_files=($(find "$hoolamike_dir" -maxdepth 1 -name "*.mpi" 2>/dev/null))
    
    if [ ${#mpi_files[@]} -eq 0 ]; then
        log_info "No MPI file found in $hoolamike_dir"
        return 1
    elif [ ${#mpi_files[@]} -eq 1 ]; then
        # Only one MPI file found, use it
        local mpi_filename=$(basename "${mpi_files[0]}")
        log_info "Found MPI file: $mpi_filename"
        echo "$mpi_filename"
        return 0
    else
        # Multiple MPI files found, let user choose
        log_info "Multiple MPI files found, prompting user to choose"
        echo -e "${color_yellow}Multiple MPI files found:${color_reset}"
        
        local i=1
        for mpi in "${mpi_files[@]}"; do
            echo -e "$i. $(basename "$mpi")"
            ((i++))
        done
        
        while true; do
            read -rp "Select MPI file to use (1-${#mpi_files[@]}): " choice
            if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#mpi_files[@]} )); then
                local selected_mpi=$(basename "${mpi_files[$((choice-1))]}")
                log_info "User selected MPI file: $selected_mpi"
                echo "$selected_mpi"
                return 0
            else
                echo "Invalid choice. Please try again."
            fi
        done
    fi
}

# Function to update the MPI file path in existing config
update_mpi_file_in_config() {
    local config_file="$HOME/Hoolamike/hoolamike.yaml"
    
    if [ ! -f "$config_file" ]; then
        log_warning "Config file not found: $config_file"
        return 1
    fi
    
    # Find the actual MPI file
    local mpi_filename
    if mpi_filename=$(find_mpi_file); then
        log_info "Updating config with MPI file: $mpi_filename"
        
        # Create a backup
        cp "$config_file" "${config_file}.bak.$(date +%s)"
        
        # Update the MPI file path in the config
        sed -i "s|path_to_ttw_mpi_file:.*|path_to_ttw_mpi_file: \"./$mpi_filename\"|" "$config_file"
        
        echo -e "${color_green}Updated TTW MPI file path in config: $mpi_filename${color_reset}"
        log_info "Successfully updated MPI file path in config"
        return 0
    else
        log_warning "No MPI file found to update in config"
        return 1
    fi
}

# Generate Hoolamike configuration file
generate_hoolamike_config() {
    log_info "Generating hoolamike.yaml config"
    local config_path="$HOME/Hoolamike/hoolamike.yaml"

    # Find game directories
    local steam_root=$(get_steam_root)
    
    # Find game directories - only store those that actually exist
    local found_games=""
    local game_configs=""
    
    # Check for each game and only add it if found
    local fallout3_dir=$(find_game_directory "Fallout 3 goty" "$steam_root")
    if [ -n "$fallout3_dir" ]; then
        game_configs+="  Fallout3:\n    root_directory: \"$fallout3_dir\"\n"
        found_games+="Fallout 3: $fallout3_dir\n"
    fi
    
    local fnv_dir=$(find_game_directory "Fallout New Vegas" "$steam_root")
    if [ -n "$fnv_dir" ]; then
        game_configs+="  FalloutNewVegas:\n    root_directory: \"$fnv_dir\"\n"
        found_games+="Fallout NV: $fnv_dir\n"
    fi
    
    local enderal_dir=$(find_game_directory "Enderal Special Edition" "$steam_root")
    if [ -n "$enderal_dir" ]; then
        game_configs+="  EnderalSpecialEdition:\n    root_directory: \"$enderal_dir\"\n"
        found_games+="Enderal Special Edition: $enderal_dir\n"
    fi
    
    local skyrim_se_dir=$(find_game_directory "Skyrim Special Edition" "$steam_root")
    if [ -n "$skyrim_se_dir" ]; then
        game_configs+="  SkyrimSpecialEdition:\n    root_directory: \"$skyrim_se_dir\"\n"
        found_games+="Skyrim Special Edition: $skyrim_se_dir\n"
    fi
    
    local fallout4_dir=$(find_game_directory "Fallout 4" "$steam_root")
    if [ -n "$fallout4_dir" ]; then
        game_configs+="  Fallout4:\n    root_directory: \"$fallout4_dir\"\n"
        found_games+="Fallout 4: $fallout4_dir\n"
    fi
    
    local starfield_dir=$(find_game_directory "Starfield" "$steam_root")
    if [ -n "$starfield_dir" ]; then
        game_configs+="  Starfield:\n    root_directory: \"$starfield_dir\"\n"
        found_games+="Starfield: $starfield_dir\n"
    fi
    
    local oblivion_dir=$(find_game_directory "Oblivion" "$steam_root")
    if [ -n "$oblivion_dir" ]; then
        game_configs+="  Oblivion:\n    root_directory: \"$oblivion_dir\"\n"
        found_games+="Oblivion: $oblivion_dir\n"
    fi
    
    local bg3_dir=$(find_game_directory "Baldurs Gate 3" "$steam_root")
    if [ -n "$bg3_dir" ]; then
        game_configs+="  BaldursGate3:\n    root_directory: \"$bg3_dir\"\n"
        found_games+="Baldur's Gate 3: $bg3_dir\n"
    fi

    # Find Fallout New Vegas compatdata
    local fnv_compatdata=$(find_fnv_compatdata)
    local userprofile_path=""

    if [ -n "$fnv_compatdata" ]; then
        userprofile_path="${fnv_compatdata}/pfx/drive_c/users/steamuser/Documents/My Games/FalloutNV/"
        log_info "Found FNV compatdata userprofile path: $userprofile_path"
    else
        log_warning "FNV compatdata not found"
    fi

    # If no games were found, add a comment to the YAML section
    if [ -z "$game_configs" ]; then
        game_configs="  # No games detected. Add game paths manually if needed.\n"
    fi

    # Try to find an existing MPI file for the TTW section
    local mpi_filename
    if mpi_filename=$(find_mpi_file); then
        log_info "Using existing MPI file: $mpi_filename"
    else
        log_info "No MPI file found, using placeholder"
        mpi_filename="YOUR_TTW_MPI_FILE.mpi"
    fi

    # Create default config with found paths
    cat > "$config_path" << EOF
# Auto-generated hoolamike.yaml
# Edit paths if not detected correctly

downloaders:
  downloads_directory: "$HOME/Hoolamike/Mod_Downloads"
  nexus:
    api_key: "YOUR_API_KEY_HERE"

installation:
  wabbajack_file_path: "./wabbajack"
  installation_path: "$HOME/ModdedGames"

games:
$(echo -e "$game_configs")
fixup:
  game_resolution: 2560x1440

extras:
  tale_of_two_wastelands:
    path_to_ttw_mpi_file: "./$mpi_filename"
    variables:
      DESTINATION: "./TTW_Output"
EOF

    # Only add USERPROFILE if it was found
    if [ -n "$userprofile_path" ]; then
        echo "      USERPROFILE: \"$userprofile_path\"" >> "$config_path"
    fi

    log_info "hoolamike.yaml created at $config_path"
    echo -e "\n${color_green}Generated hoolamike.yaml with detected games:${color_reset}"
    
    if [ -n "$found_games" ]; then
        echo -e "$found_games"
    else
        echo -e "${color_yellow}No games were detected.${color_reset}"
        echo -e "You will need to manually edit the config file to add your game paths."
    fi
    
    if [ "$mpi_filename" != "YOUR_TTW_MPI_FILE.mpi" ]; then
        echo -e "\n${color_green}Found TTW MPI file: $mpi_filename${color_reset}"
    else
        echo -e "\n${color_yellow}No TTW MPI file found yet.${color_reset}"
        echo -e "Place your TTW .mpi file in $HOME/Hoolamike/ and the config will be updated automatically."
    fi
    
    echo -e "\n${color_yellow}Edit the file to complete configuration:${color_reset}"
    echo -e "${color_blue}nano $config_path${color_reset}"
}

# Configure Wabbajack settings for a specific modlist
configure_wabbajack_settings() {
    local config_file="$1"
    
    # Information about where to find Wabbajack files
    echo -e "\n${color_header}Where to Find Wabbajack Modlists${color_reset}"
    echo -e "Before continuing, you'll need a .wabbajack file. You can find these at:"
    echo -e "1. ${color_blue}https://build.wabbajack.org/authored_files${color_reset} - Official Wabbajack modlist repository"
    echo -e "2. ${color_blue}https://www.nexusmods.com/${color_reset} - Some modlist authors publish on Nexus Mods"
    echo -e "3. Various Discord communities for specific modlists"
    echo -e "\n${color_yellow}NOTE:${color_reset} Download the .wabbajack file first, then continue.\n"

    # Ask for Wabbajack file
    local wabbajack_path=""
    while true; do
        read_with_tab_completion "Enter path to Wabbajack file (.wabbajack)" "" "wabbajack_path"

        if [ -f "$wabbajack_path" ]; then
            log_info "Selected Wabbajack file: $wabbajack_path"
            break
        else
            echo -e "${color_yellow}File not found: $wabbajack_path${color_reset}"
            if ! confirm_action "Try again?"; then
                log_info "User cancelled Wabbajack installation"
                return 1
            fi
        fi
    done

    # Get modlist name from the filename for better user experience
    local modlist_name=$(basename "$wabbajack_path" .wabbajack)
    echo -e "Installing modlist: ${color_green}$modlist_name${color_reset}"

    # Get downloads directory
    local current_downloads_dir=$(grep -A2 "downloaders:" "$config_file" | grep "downloads_directory:" | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -z "$current_downloads_dir" ] || [[ "$current_downloads_dir" == *"YOUR"* ]]; then
        current_downloads_dir="$HOME/Downloads"
    fi

    echo -e "\n${color_header}Downloads Directory${color_reset}"
    echo -e "This is where mod files will be downloaded from Nexus/other sources."
    echo -e "Enter downloads directory [default: $current_downloads_dir]: "
    read -r direct_downloads_dir
    if [ -n "$direct_downloads_dir" ]; then
        downloads_dir="${direct_downloads_dir/#\~/$HOME}"
    else
        downloads_dir="$current_downloads_dir"
    fi

    # Create downloads directory if it doesn't exist
    if [ ! -d "$downloads_dir" ]; then
        echo -e "${color_yellow}Downloads directory does not exist.${color_reset}"
        if confirm_action "Create directory?"; then
            mkdir -p "$downloads_dir"
            log_info "Created downloads directory: $downloads_dir"
        fi
    fi

    # Get installation path
    local current_install_path=$(grep -A2 "installation:" "$config_file" | grep "installation_path:" | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -z "$current_install_path" ] || [[ "$current_install_path" == *"YOUR"* ]]; then
        current_install_path="$HOME/ModdedGames/$modlist_name"
    fi

    echo -e "\n${color_header}Installation Path${color_reset}"
    echo -e "This is where the modded game will be installed."
    echo -e "Enter installation path [default: $current_install_path]: "
    read -r direct_install_path
    if [ -n "$direct_install_path" ]; then
        install_path="${direct_install_path/#\~/$HOME}"
    else
        install_path="$current_install_path"
    fi

    # Create installation directory if it doesn't exist
    if [ ! -d "$install_path" ]; then
        echo -e "${color_yellow}Installation directory does not exist.${color_reset}"
        if confirm_action "Create directory?"; then
            mkdir -p "$install_path"
            log_info "Created installation directory: $install_path"
        fi
    fi

    # Get Nexus API key
    local current_api_key=$(grep -A3 "downloaders:" "$config_file" | grep "api_key:" | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -z "$current_api_key" ] || [ "$current_api_key" == "YOUR_API_KEY_HERE" ]; then
        echo -e "\n${color_header}Nexus API Key${color_reset}"
        echo -e "${color_yellow}A Nexus Mods API key is helpful even for non-premium installations.${color_reset}"
        echo -e "You can get one from: ${color_blue}https://www.nexusmods.com/users/myaccount?tab=api${color_reset}"
        read -rp "Enter Nexus API key (or leave empty): " api_key

        if [ -z "$api_key" ]; then
            echo -e "${color_yellow}No API key provided. Using placeholder value.${color_reset}"
            api_key="YOUR_API_KEY_HERE"
        fi
    else
        echo -e "\n${color_header}Nexus API Key${color_reset}"
        echo -e "Nexus API key found in configuration."
        if confirm_action "Use existing API key?"; then
            echo -e "Using existing API key."
            api_key="$current_api_key"
        else
            read -rp "Enter new Nexus API key (or leave empty): " api_key
            if [ -z "$api_key" ]; then
                api_key="YOUR_API_KEY_HERE"  # Use placeholder if nothing entered
            fi
        fi
    fi

    # Get game resolution
    local current_resolution=$(grep -A1 "fixup:" "$config_file" | grep "game_resolution:" | awk '{print $2}')
    if [ -z "$current_resolution" ]; then
        current_resolution="1920x1080"
    fi

    echo -e "\n${color_header}Game Resolution${color_reset}"
    echo -e "This sets the resolution for the modded game."
    echo -e "Common resolutions: 1920x1080 (1080p), 2560x1440 (1440p), 3840x2160 (4K)"
    read -rp "Enter game resolution [default: $current_resolution]: " input
    if [ -n "$input" ]; then
        game_resolution="$input"
    else
        game_resolution="$current_resolution"
    fi

    # Create a backup of the original config
    cp "$config_file" "${config_file}.bak.$(date +%s)"
    log_info "Backed up original config"

    # Preserve game paths from existing config
    log_info "Extracting existing game paths from configuration"
    local game_section=""
    local capture=false
    
    while IFS= read -r line; do
        if [[ "$line" == "games:"* ]]; then
            capture=true
            game_section="games:\n"
        elif [[ "$capture" == true ]]; then
            if [[ "$line" == "fixup:"* ]]; then
                capture=false
            else
                game_section+="$line\n"
            fi
        fi
    done < "$config_file"
    
    # If no game section was found, add a comment
    if [ -z "$game_section" ] || [ "$game_section" == "games:\n" ]; then
        game_section="games:\n  # No games configured. Add them manually if needed.\n"
    fi

    # Try to find the current MPI file or use existing one from config
    local mpi_filename
    if mpi_filename=$(find_mpi_file); then
        log_info "Using found MPI file: $mpi_filename"
    else
        # Try to extract existing MPI filename from config
        local existing_mpi=$(grep "path_to_ttw_mpi_file:" "$config_file" | sed -E 's/.*"\.\/([^"]+)".*/\1/')
        if [ -n "$existing_mpi" ] && [ "$existing_mpi" != "YOUR_TTW_MPI_FILE.mpi" ]; then
            mpi_filename="$existing_mpi"
            log_info "Using existing MPI filename from config: $mpi_filename"
        else
            mpi_filename="YOUR_TTW_MPI_FILE.mpi"
            log_info "No MPI file found, using placeholder"
        fi
    fi

    # Write a new configuration file
    cat > "$config_file" << EOF
# Auto-generated hoolamike.yaml
# Updated by NaK Helper on $(date)

downloaders:
  downloads_directory: "$downloads_dir"
  nexus:
    api_key: "$api_key"

installation:
  wabbajack_file_path: "$wabbajack_path"
  installation_path: "$install_path"

$(echo -e "$game_section")
fixup:
  game_resolution: $game_resolution

extras:
  tale_of_two_wastelands:
    path_to_ttw_mpi_file: "./$mpi_filename"
    variables:
      DESTINATION: "./TTW_Output"
EOF

    # Only add USERPROFILE if it was found in the backup
    local userprofile_path=$(grep "USERPROFILE:" "$config_file.bak."* 2>/dev/null | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -n "$userprofile_path" ]; then
        echo "      USERPROFILE: \"$userprofile_path\"" >> "$config_file"
    fi

    # Now show the updated configuration summary
    echo -e "\n${color_header}Configuration Summary${color_reset}"
    echo -e "Wabbajack file: ${color_green}$wabbajack_path${color_reset}"
    echo -e "Downloads directory: ${color_green}$downloads_dir${color_reset}"
    echo -e "Installation path: ${color_green}$install_path${color_reset}"
    echo -e "Game resolution: ${color_green}$game_resolution${color_reset}"
    
    if [ "$mpi_filename" != "YOUR_TTW_MPI_FILE.mpi" ]; then
        echo -e "TTW MPI file: ${color_green}$mpi_filename${color_reset}"
    else
        echo -e "TTW MPI file: ${color_yellow}Not configured yet${color_reset}"
    fi

    if ! confirm_action "Apply these settings and continue?"; then
        echo -e "\n${color_yellow}Installation canceled.${color_reset}"
        log_info "User cancelled Wabbajack installation after configuration"
        return 1
    fi

    return 0
}

# Download and install Hoolamike
download_hoolamike() {
    log_info "Starting hoolamike download"

    print_section "Download Hoolamike"

    # Check for dependencies
    if ! check_download_dependencies; then
        handle_error "Required dependencies missing for download" false
        return 1
    fi

    # Create directory in home folder
    local hoolamike_dir="$HOME/Hoolamike"

    # Check if Hoolamike is already installed
    if [ -d "$hoolamike_dir" ]; then
        echo -e "${color_yellow}Hoolamike is already installed at $hoolamike_dir${color_reset}"
        echo -e "Would you like to update to the latest version? This will delete the existing installation."
        if confirm_action "Update Hoolamike?"; then
            echo -e "${color_blue}Removing existing installation...${color_reset}"
            rm -rf "$hoolamike_dir"
            log_info "Removed existing Hoolamike installation for update"
        else
            echo -e "Update canceled."
            log_info "User canceled Hoolamike update"
            return 0
        fi
    fi

    # Create the directory (needed again in case it was deleted)
    mkdir -p "$hoolamike_dir"

    echo -e "Fetching latest release information from GitHub..."
    log_info "Fetching latest release info from GitHub"

    # Start progress tracking
    local tracker=$(start_progress_tracking "Downloading Hoolamike" 60)

    # Get latest release info
    local release_info
    if ! release_info=$(curl -s https://api.github.com/repos/Niedzwiedzw/hoolamike/releases/latest); then
        end_progress_tracking "$tracker" false
        handle_error "Failed to fetch release information from GitHub. Check your internet connection." false
        return 1
    fi

    update_progress "$tracker" 10 100

    # Extract download URL for the binary
    local download_url
    download_url=$(echo "$release_info" | jq -r '.assets[] | select(.name | test("hoolamike.*linux"; "i")) | .browser_download_url')

    if [ -z "$download_url" ]; then
        end_progress_tracking "$tracker" false
        handle_error "No suitable asset found in the latest release. Please check https://github.com/Niedzwiedzw/hoolamike manually." false
        return 1
    fi

    local filename=$(basename "$download_url")
    local version=$(echo "$release_info" | jq -r .tag_name)

    echo -e "Found latest version: ${color_green}$version${color_reset}"
    echo -e "Downloading and extracting to $hoolamike_dir..."
    log_info "Downloading version $version from $download_url"

    update_progress "$tracker" 20 100

    # Download and extract directly to target directory
    if ! (cd "$hoolamike_dir" && curl -L "$download_url" | tar -xz); then
        end_progress_tracking "$tracker" false
        handle_error "Failed to download or extract hoolamike. Check your internet connection." false
        return 1
    fi

    update_progress "$tracker" 70 100

    # Generate config file
    generate_hoolamike_config

    update_progress "$tracker" 90 100

    # Store version in config
    set_config "hoolamike_version" "$version"

    end_progress_tracking "$tracker" true

    print_section "Manual Steps Required"
    echo -e "${color_yellow}You need to download the TTW MPI file:${color_reset}"
    echo -e "1. Open in browser: ${color_blue}https://mod.pub/ttw/133/files${color_reset}"
    echo -e "2. Download the latest 'TTW_*.7z' file"
    echo -e "3. Extract the .mpi file from the archive"
    echo -e "4. Copy the .mpi file to: ${color_blue}$hoolamike_dir/${color_reset}"
    echo -e "\n${color_green}The script will automatically detect and use whatever MPI file you place there!${color_reset}"

    echo -e "\n${color_green}Hoolamike setup completed!${color_reset}"
    echo -e "You can now configure your mod setup in:"
    echo -e "${color_blue}$hoolamike_dir/hoolamike.yaml${color_reset}"

    return 0
}

# Execute Hoolamike with a specific command showing direct terminal output
run_hoolamike() {
    local command="$1"
    local summary_log="$HOME/hoolamike_summary.log"

    # Check if hoolamike exists
    if [ ! -f "$HOME/Hoolamike/hoolamike" ]; then
        handle_error "Hoolamike is not installed. Please install it first." false
        return 1
    fi

    # Before running TTW installation, make sure the MPI file path is current
    if [ "$command" == "tale-of-two-wastelands" ]; then
        echo -e "${color_yellow}Checking for TTW MPI file...${color_reset}"
        if update_mpi_file_in_config; then
            echo -e "${color_green}MPI file configuration updated.${color_reset}"
        else
            echo -e "${color_yellow}No MPI file found or config update failed.${color_reset}"
            echo -e "Make sure you have placed a TTW .mpi file in $HOME/Hoolamike/"
            if ! confirm_action "Continue anyway?"; then
                return 1
            fi
        fi
    fi

    print_section "Running Hoolamike"
    echo -e "Starting ${color_blue}$command${color_reset} operation with Hoolamike"
    echo -e "${color_yellow}This may take a very long time (up to several hours)${color_reset}"
    echo -e "Showing live output below - this helps you track progress:"

    # Set start time for summary log
    echo "[$(date)] Starting hoolamike $command" > "$summary_log"

    # Change directory to Hoolamike
    cd "$HOME/Hoolamike" || {
        log_error "Failed to enter Hoolamike directory"
        return 1
    }

    # Increase file limit for better performance
    if ! ulimit -n 64556 > /dev/null 2>&1; then
        log_warning "Failed to set ulimit. Performance may be affected."
    fi

    # Run directly (no pipes) to preserve interactive terminal environment
    ./hoolamike "$command"
    local exit_status=$?

    # Append final status to summary log
    echo "[$(date)] Hoolamike $command completed with status $exit_status" >> "$summary_log"

    # Return to original directory
    cd - > /dev/null

    # Error handling
    if [ $exit_status -ne 0 ]; then
        handle_error "Hoolamike execution failed with status $exit_status. Check terminal output for details." false
        return 1
    fi

    log_info "Hoolamike execution completed for $command."

    # Fix ModOrganizer.ini paths after installation
    if [ "$command" == "install" ] || [[ "$command" == wabbajack* ]]; then
        fix_modorganizer_paths
    fi

    echo -e "\n${color_green}Hoolamike $command completed successfully!${color_reset}"

    return 0
}

# Simplified function for non-premium Wabbajack installation
install_wabbajack_modlist_nonpremium() {
    print_section "Install Wabbajack Modlist (Non-Premium Option)"
    echo -e "${color_yellow}This option is for users without a Nexus Mods Premium account.${color_reset}"
    echo -e "You will need to manually download files through your browser when prompted.\n"

    local hoolamike_dir="$HOME/Hoolamike"
    local config_file="$hoolamike_dir/hoolamike.yaml"

    # Check if Hoolamike is installed
    if [ ! -f "$hoolamike_dir/hoolamike" ]; then
        handle_error "Hoolamike is not installed. Please install it first." false
        return 1
    fi

    # Check if config file exists
    if [ ! -f "$config_file" ]; then
        handle_error "Hoolamike configuration file not found. Please run 'Download/Update Hoolamike' first." false
        return 1
    fi

    log_info "Starting Wabbajack non-premium modlist installation setup"

    # Ask for browser
    echo -e "${color_header}Select Your Web Browser${color_reset}"
    echo -e "The browser will be used to download files from Nexus."
    echo -e "Common browsers: firefox, brave, chrome, chromium, waterfox, vivaldi"
    read -rp "Enter your browser name: " browser_name

    if [ -z "$browser_name" ]; then
        echo -e "${color_yellow}No browser specified. Using 'firefox' as default.${color_reset}"
        browser_name="firefox"
    fi

    log_info "Selected browser: $browser_name"

    # Configure Wabbajack file and settings
    if ! configure_wabbajack_settings "$config_file"; then
        return 1
    fi

    # Run the browser-based installation
    echo -e "\n${color_yellow}This process may take a long time depending on the modlist size.${color_reset}"
    echo -e "Your browser will open automatically when manual downloads are needed."

    if confirm_action "Start Wabbajack installation now?"; then
        cd "$HOME/Hoolamike" || {
            log_error "Failed to enter Hoolamike directory"
            return 1
        }

        # Run the handle-nxm command with browser option
        ./hoolamike handle-nxm --use-browser "$browser_name"
        local exit_status=$?

        # Check if installation succeeded
        if [ $exit_status -eq 0 ]; then
            echo -e "\n${color_green}Wabbajack modlist installation completed!${color_reset}"
            echo -e "You can now launch the game through Mod Organizer 2."
            echo -e "\n${color_yellow}Important:${color_reset} Some modlists may require additional setup."
            echo -e "Check the modlist documentation for any post-installation steps."
        else
            echo -e "\n${color_red}Wabbajack installation failed.${color_reset}"
            echo -e "Check the logs for more information."
        fi
    else
        echo -e "\nYou can run the installation later by selecting this option again."
        echo -e "Your configuration has been saved."
    fi

    return 0
}

# Premium install function
install_wabbajack_modlist() {
    print_section "Install Wabbajack Modlist (Premium Option)"
    echo -e "${color_yellow}This option requires a Nexus Mods Premium account for automatic downloads.${color_reset}"
    echo -e "If you don't have a premium account, please use the 'Non-Premium Installation' option instead.\n"

    local hoolamike_dir="$HOME/Hoolamike"
    local config_file="$hoolamike_dir/hoolamike.yaml"

    # Check if Hoolamike is installed
    if [ ! -f "$hoolamike_dir/hoolamike" ]; then
        handle_error "Hoolamike is not installed. Please install it first." false
        return 1
    fi

    # Check if config file exists
    if [ ! -f "$config_file" ]; then
        handle_error "Hoolamike configuration file not found. Please run 'Download/Update Hoolamike' first." false
        return 1
    fi

    log_info "Starting Wabbajack premium modlist installation setup"

    # Configure Wabbajack file and settings
    if ! configure_wabbajack_settings "$config_file"; then
        return 1
    fi

    # Run the installation
    echo -e "\n${color_yellow}This process may take a long time depending on the modlist size.${color_reset}"
    echo -e "Large modlists can take several hours and need a stable internet connection."

    if confirm_action "Start Wabbajack installation now?"; then
        run_hoolamike "install"

        # Check if installation succeeded
        if [ $? -eq 0 ]; then
            echo -e "\n${color_green}Wabbajack modlist installation completed!${color_reset}"
            echo -e "You can now launch the game through Mod Organizer 2."
            echo -e "\n${color_yellow}Important:${color_reset} Some modlists may require additional setup."
            echo -e "Check the modlist documentation for any post-installation steps."
        else
            echo -e "\n${color_red}Wabbajack installation failed.${color_reset}"
            echo -e "Check the logs for more information."
        fi
    else
        echo -e "\nYou can run the installation later by selecting this option again."
        echo -e "Your configuration has been saved."
    fi

    return 0
}

# Function to help users edit their hoolamike.yaml config directly
edit_hoolamike_config() {
    print_section "Edit Hoolamike Configuration"

    local hoolamike_dir="$HOME/Hoolamike"
    local config_file="$hoolamike_dir/hoolamike.yaml"

    # Check if Hoolamike is installed
    if [ ! -f "$hoolamike_dir/hoolamike" ]; then
        handle_error "Hoolamike is not installed. Please install it first." false
        return 1
    fi

    # Check if config file exists
    if [ ! -f "$config_file" ]; then
        handle_error "Hoolamike configuration file not found." false
        return 1
    fi

    # Detect available text editors
    local editors=()
    local editor_cmds=("nano" "vim" "vi" "emacs" "gedit" "kate" "mousepad" "pluma")

    for cmd in "${editor_cmds[@]}"; do
        if command_exists "$cmd"; then
            editors+=("$cmd")
        fi
    done

    if [ ${#editors[@]} -eq 0 ]; then
        handle_error "No text editor found. Please install nano: sudo apt install nano" false
        return 1
    fi

    # Default to first available editor
    local editor="${editors[0]}"

    # If more than one editor is available, let user choose
    if [ ${#editors[@]} -gt 1 ]; then
        echo -e "Available text editors:"
        for i in "${!editors[@]}"; do
            echo -e "$((i+1)). ${editors[$i]}"
        done

        while true; do
            read -rp "Select editor (1-${#editors[@]}) [default: 1]: " choice

            if [ -z "$choice" ]; then
                choice=1
                break
            elif [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#editors[@]}" ]; then
                break
            else
                echo -e "${color_yellow}Invalid choice. Please try again.${color_reset}"
            fi
        done

        editor="${editors[$((choice-1))]}"
    fi

    echo -e "Opening configuration file with $editor..."
    log_info "Editing hoolamike.yaml with $editor"

    # Create a backup before editing
    cp "$config_file" "${config_file}.edit-bak"

    # Open the file in the selected editor
    $editor "$config_file"

    echo -e "\n${color_green}Configuration file updated.${color_reset}"
    echo -e "You can now use Hoolamike with the updated configuration."

    return 0
}

# Function to fix path formats in ModOrganizer.ini
fix_modorganizer_paths() {
    print_section "Fixing ModOrganizer Paths"
    echo -e "Checking for ModOrganizer.ini to fix path formats..."
    log_info "Searching for ModOrganizer.ini to fix Windows paths"

    # Get installation path from config file
    local config_file="$HOME/Hoolamike/hoolamike.yaml"
    local install_path=$(grep -A2 "installation:" "$config_file" | grep "installation_path:" | sed -E 's/.*"([^"]+)".*/\1/')

    if [ -z "$install_path" ]; then
        echo -e "${color_yellow}Could not determine installation path from config.${color_reset}"
        log_warning "Failed to determine installation path from hoolamike.yaml"

        # Ask user for path
        read -rp "Enter the modlist installation path: " install_path
        if [ -z "$install_path" ]; then
            echo -e "${color_yellow}No path provided. Skipping path fix.${color_reset}"
            log_warning "User did not provide installation path. Skipping path fix."
            return 1
        fi
    fi

    # Expand tilde if present
    install_path="${install_path/#\~/$HOME}"
    log_info "Installation path: $install_path"

    # Find all ModOrganizer.ini files recursively in the installation path
    # Using a while loop with find to properly handle paths with spaces
    local mo_ini_files=()
    while IFS= read -r -d $'\0' file; do
        mo_ini_files+=("$file")
    done < <(find "$install_path" -name "ModOrganizer.ini" -print0 2>/dev/null)

    if [ ${#mo_ini_files[@]} -eq 0 ]; then
        echo -e "${color_yellow}No ModOrganizer.ini files found in \"$install_path\"${color_reset}"
        log_warning "No ModOrganizer.ini files found in $install_path"
        return 1
    fi

    echo -e "Found ${#mo_ini_files[@]} ModOrganizer.ini files to process."
    log_info "Found ${#mo_ini_files[@]} ModOrganizer.ini files to process"

    for ini_file in "${mo_ini_files[@]}"; do
        echo -e "Processing: ${color_blue}\"$ini_file\"${color_reset}"
        log_info "Processing file: $ini_file"

        # Create a backup of the original file
        cp -- "$ini_file" "${ini_file}.bak"
        log_info "Created backup: ${ini_file}.bak"

        # Create a temporary file for processing
        local tmp_file=$(mktemp)
        TEMP_FILES+=("$tmp_file")

        # Replace // with Z:/
        sed 's|//|Z:/|g' -- "$ini_file" > "$tmp_file"

        # Replace /\\ with Z:\\ (using awk for better handling of backslashes)
        awk '{gsub(/\/\\\\/,"Z:\\\\"); print}' "$tmp_file" > "$ini_file"
        
        # Remove any line containing download_directory=
        if grep -q "download_directory=" "$ini_file"; then
            log_info "Removing download_directory line from $ini_file"
            grep -v "download_directory=" "$ini_file" > "$tmp_file"
            cp -- "$tmp_file" "$ini_file"
            echo -e "${color_green}✓ Removed download_directory line from: \"$ini_file\"${color_reset}"
        fi

        echo -e "${color_green}✓ Fixed paths in: \"$ini_file\"${color_reset}"
        log_info "Fixed paths in: $ini_file"
    done

    echo -e "\n${color_green}Path fixing completed successfully!${color_reset}"
    echo -e "${color_yellow}Note:${color_reset} If you encounter any issues with the game, you can restore the original files from the .bak backups."
    log_info "Path fixing completed successfully"

    return 0
}

# Wait for MPI file to be placed in the hoolamike directory
wait_for_mpi_file() {
    local hoolamike_dir="$HOME/Hoolamike"
    local wait_time=0
    local timeout=6000000  # 10000 minutes

    print_section "Waiting for TTW MPI File"
    echo -e "MPI File can be found here https://mod.pub/ttw/133/files"
    echo -e "Waiting for you to download and place the TTW MPI file in:"
    echo -e "${color_blue}$hoolamike_dir/${color_reset}"
    echo -e "\nPress Ctrl+C at any time to cancel..."

    # Wait for MPI file with timeout
    while [ $wait_time -lt $timeout ]; do
        # Check for any .mpi file
        if ls "$hoolamike_dir"/*.mpi >/dev/null 2>&1; then
            local found_mpi_file=$(find_mpi_file)
            if [ -n "$found_mpi_file" ]; then
                log_info "Found MPI file: $found_mpi_file"
                echo -e "\n${color_green}Detected MPI file: $found_mpi_file${color_reset}"
                
                # Update the config file with the new MPI file
                update_mpi_file_in_config
                
                return 0
            fi
        fi

        # Show progress every 15 seconds
        if (( wait_time % 15 == 0 )); then
            echo -n "."
        fi

        sleep 1
        ((wait_time++))
    done

    # Timeout occurred
    handle_error "Timed out waiting for MPI file. Please try again after downloading the file." false
    return 1
}

# Function to run custom Hoolamike commands
run_custom_hoolamike_command() {
    print_section "Run Custom Hoolamike Command"

    local hoolamike_dir="$HOME/Hoolamike"

    # Check if Hoolamike is installed
    if [ ! -f "$hoolamike_dir/hoolamike" ]; then
        handle_error "Hoolamike is not installed. Please install it first." false
        return 1
    fi

    echo -e "${color_header}Available Hoolamike Commands:${color_reset}"
    echo -e "1. hoolamike - Show help"
    echo -e "2. hoolamike wabbajack [file.wabbajack] - Install a Wabbajack modlist"
    echo -e "3. hoolamike tale-of-two-wastelands - Install TTW"
    echo -e "4. hoolamike version - Show version"
    echo -e "5. Other custom command"

    read -rp "Select a command (1-5): " choice

    local command=""
    case $choice in
        1) command="" ;;
        2)
            read_with_tab_completion "Enter path to Wabbajack file" "" "wj_path"
            command="wabbajack \"$wj_path\""
            ;;
        3) command="tale-of-two-wastelands" ;;
        4) command="version" ;;
        5)
            read -rp "Enter custom command: " command
            ;;
        *)
            echo -e "${color_yellow}Invalid choice.${color_reset}"
            return 1
            ;;
    esac

    echo -e "\nRunning: ${color_blue}hoolamike $command${color_reset}"
    if confirm_action "Execute this command?"; then
        run_hoolamike "$command"

        echo -e "\n${color_green}Command execution completed.${color_reset}"
        pause "Press any key to continue..."
    else
        echo -e "\n${color_yellow}Command cancelled.${color_reset}"
    fi

    return 0
}
