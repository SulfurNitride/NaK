#!/bin/bash
# -------------------------------------------------------------------
# hoolamike.sh
# Hoolamike integration for MO2 Helper
# -------------------------------------------------------------------

# Generate Hoolamike configuration file
generate_hoolamike_config() {
    log_info "Generating hoolamike.yaml config"
    local config_path="$HOME/Hoolamike/hoolamike.yaml"

    # Find game directories
    local steam_root=$(get_steam_root)
    local fallout3_dir=$(find_game_directory "Fallout 3 goty" "$steam_root")
    local fnv_dir=$(find_game_directory "Fallout New Vegas" "$steam_root")
    
    # Find additional game directories
    local enderal_dir=$(find_game_directory "Enderal Special Edition" "$steam_root")
    local skyrim_se_dir=$(find_game_directory "Skyrim Special Edition" "$steam_root")
    local fallout4_dir=$(find_game_directory "Fallout 4" "$steam_root")
    local starfield_dir=$(find_game_directory "Starfield" "$steam_root")
    local oblivion_dir=$(find_game_directory "Oblivion" "$steam_root")
    local bg3_dir=$(find_game_directory "Baldurs Gate 3" "$steam_root")

    # Find Fallout New Vegas compatdata
    local fnv_compatdata=$(find_fnv_compatdata)
    local userprofile_path=""

    if [ -n "$fnv_compatdata" ]; then
        userprofile_path="${fnv_compatdata}/pfx/drive_c/users/steamuser/Documents/My Games/FalloutNV/"
        log_info "Found FNV compatdata userprofile path: $userprofile_path"
    else
        log_warning "FNV compatdata not found"
    fi

    # Set fallback paths
    local fallout3_fallback="/path/to/Fallout 3 goty"
    local fnv_fallback="/path/to/Fallout New Vegas"
    local enderal_fallback="/path/to/Enderal Special Edition"
    local skyrimse_fallback="/path/to/Skyrim Special Edition"
    local fallout4_fallback="/path/to/Fallout 4"
    local starfield_fallback="/path/to/Starfield"
    local oblivion_fallback="/path/to/Oblivion"
    local bg3_fallback="/path/to/Baldur's Gate 3"
    local userprofile_fallback="/path/to/steamapps/compatdata/22380/pfx/drive_c/users/steamuser/Documents/My Games/FalloutNV/"

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
  Fallout3:
    root_directory: "${fallout3_dir:-$fallout3_fallback}"
  FalloutNewVegas:
    root_directory: "${fnv_dir:-$fnv_fallback}"
  EnderalSpecialEdition:
    root_directory: "${enderal_dir:-$enderal_fallback}"
  SkyrimSpecialEdition:
    root_directory: "${skyrim_se_dir:-$skyrimse_fallback}"
  Fallout4:
    root_directory: "${fallout4_dir:-$fallout4_fallback}"
  Starfield:
    root_directory: "${starfield_dir:-$starfield_fallback}"
  Oblivion:
    root_directory: "${oblivion_dir:-$oblivion_fallback}"
  BaldursGate3:
    root_directory: "${bg3_dir:-$bg3_fallback}"

fixup:
  game_resolution: 2560x1440

extras:
  tale_of_two_wastelands:
    path_to_ttw_mpi_file: "./Tale of Two Wastelands 3.3.3b.mpi"
    variables:
      DESTINATION: "./TTW_Output"
      USERPROFILE: "${userprofile_path:-$userprofile_fallback}"
EOF

    log_info "hoolamike.yaml created at $config_path"
    echo -e "\n${color_green}Generated hoolamike.yaml with detected paths:${color_reset}"
    echo -e "Fallout 3: ${fallout3_dir:-Not found}"
    echo -e "Fallout NV: ${fnv_dir:-Not found}"
    echo -e "Enderal Special Edition: ${enderal_dir:-Not found}"
    echo -e "Skyrim Special Edition: ${skyrim_se_dir:-Not found}"
    echo -e "Fallout 4: ${fallout4_dir:-Not found}"
    echo -e "Starfield: ${starfield_dir:-Not found}"
    echo -e "Oblivion: ${oblivion_dir:-Not found}"
    echo -e "Baldur's Gate 3: ${bg3_dir:-Not found}"
    echo -e "FNV User Profile: ${userprofile_path:-Not found}"
    echo -e "\n${color_yellow}Edit the file to complete configuration:${color_reset}"
    echo -e "${color_blue}nano $config_path${color_reset}"
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
    # This is the key - we're executing hoolamike directly, not through any pipes
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
    local mo_ini_files=($(find "$install_path" -name "ModOrganizer.ini" 2>/dev/null))
    
    if [ ${#mo_ini_files[@]} -eq 0 ]; then
        echo -e "${color_yellow}No ModOrganizer.ini files found in $install_path${color_reset}"
        log_warning "No ModOrganizer.ini files found in $install_path"
        return 1
    fi
    
    echo -e "Found ${#mo_ini_files[@]} ModOrganizer.ini files to process."
    log_info "Found ${#mo_ini_files[@]} ModOrganizer.ini files to process"
    
    for ini_file in "${mo_ini_files[@]}"; do
        echo -e "Processing: ${color_blue}$ini_file${color_reset}"
        log_info "Processing file: $ini_file"
        
        # Create a backup of the original file
        cp "$ini_file" "${ini_file}.bak"
        log_info "Created backup: ${ini_file}.bak"
        
        # Create a temporary file for processing
        local tmp_file=$(mktemp)
        TEMP_FILES+=("$tmp_file")
        
        # Replace // with Z:/
        sed 's|//|Z:/|g' "$ini_file" > "$tmp_file"
        
        # Replace /\\ with Z:\\ (using awk for better handling of backslashes)
        awk '{gsub(/\/\\\\/,"Z:\\\\"); print}' "$tmp_file" > "$ini_file"
        
        echo -e "${color_green}✓ Fixed paths in: $ini_file${color_reset}"
        log_info "Fixed paths in: $ini_file"
    done
    
    echo -e "\n${color_green}Path fixing completed successfully!${color_reset}"
    echo -e "${color_yellow}Note:${color_reset} If you encounter any issues with the game, you can restore the original files from the .bak backups."
    log_info "Path fixing completed successfully"
    
    return 0
}
# Install a Wabbajack modlist
install_wabbajack_modlist() {
    print_section "Install Wabbajack Modlist"
    
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
    
    log_info "Starting Wabbajack modlist installation setup"
    
    # Information about where to find Wabbajack files
    echo -e "${color_header}Where to Find Wabbajack Modlists${color_reset}"
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
    read_with_tab_completion "Enter downloads directory" "$current_downloads_dir" "downloads_dir"
    if [ -n "$input" ]; then
        downloads_dir="${input/#\~/$HOME}"
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
    read_with_tab_completion "Enter installation path" "$current_install_path" "install_path"
    if [ -n "$input" ]; then
        install_path="${input/#\~/$HOME}"
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
        echo -e "${color_yellow}A Nexus Mods API key is required for automatic downloads.${color_reset}"
        echo -e "You can get one from: ${color_blue}https://www.nexusmods.com/users/myaccount?tab=api${color_reset}"
        read -rp "Enter Nexus API key: " api_key
        
        if [ -z "$api_key" ]; then
            echo -e "${color_yellow}No API key provided. You may need to download mods manually.${color_reset}"
            if ! confirm_action "Continue without API key?"; then
                log_info "User cancelled Wabbajack installation due to missing API key"
                return 1
            fi
            api_key="YOUR_API_KEY_HERE"
        fi
    else
        echo -e "\n${color_header}Nexus API Key${color_reset}"
        echo -e "Nexus API key found in configuration."
        if confirm_action "Use existing API key?"; then
            echo -e "Using existing API key."
            api_key="$current_api_key"
        else
            read -rp "Enter new Nexus API key: " api_key
            if [ -z "$api_key" ]; then
                api_key="$current_api_key"  # Keep existing if nothing entered
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
    
    # Summarize changes
    echo -e "\n${color_header}Configuration Summary${color_reset}"
    echo -e "Wabbajack file: ${color_green}$wabbajack_path${color_reset}"
    echo -e "Downloads directory: ${color_green}$downloads_dir${color_reset}"
    echo -e "Installation path: ${color_green}$install_path${color_reset}"
    echo -e "Game resolution: ${color_green}$game_resolution${color_reset}"
    
    if ! confirm_action "Apply these settings and start installation?"; then
        echo -e "\n${color_yellow}Installation canceled.${color_reset}"
        log_info "User cancelled Wabbajack installation after configuration"
        return 1
    fi
    
    # Update the configuration file
    log_info "Updating Hoolamike configuration for Wabbajack installation"
    echo -e "\n${color_blue}Updating configuration...${color_reset}"
    
    # Create a backup of the original config
    cp "$config_file" "${config_file}.wabbajack-bak"
    log_info "Backed up original config to ${config_file}.wabbajack-bak"
    
    # Update the config file with sed (safer than rewriting the whole file)
    # Update downloads directory
    sed -i "s|downloads_directory:.*|downloads_directory: \"$downloads_dir\"|" "$config_file"
    
    # Update Nexus API key
    sed -i "s|api_key:.*|api_key: \"$api_key\"|" "$config_file"
    
    # Update Wabbajack file path
    sed -i "s|wabbajack_file_path:.*|wabbajack_file_path: \"$wabbajack_path\"|" "$config_file"
    
    # Update installation path
    sed -i "s|installation_path:.*|installation_path: \"$install_path\"|" "$config_file"
    
    # Update game resolution - ensure the fixup section exists
    if grep -q "fixup:" "$config_file"; then
        sed -i "/fixup:/,/^[a-z]/ s|game_resolution:.*|game_resolution: $game_resolution|" "$config_file"
    else
        # Add fixup section if it doesn't exist
        echo -e "\nfixup:\n  game_resolution: $game_resolution" >> "$config_file"
    fi
    
    log_info "Hoolamike configuration updated for Wabbajack installation"
    
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
