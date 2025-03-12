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
  downloads_directory: "$HOME/Downloads"
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

    # Ask user if they want to install FNV dependencies
    echo -e "\nWould you like to install Fallout New Vegas Proton dependencies now?"
    if confirm_action "Install FNV dependencies?"; then
        install_fnv_dependencies
    fi

    return 0
}

# Execute Hoolamike with a specific command
run_hoolamike() {
    local command="$1"
    local summary_log="$HOME/hoolamike_summary.log"
    local temp_log=$(mktemp)
    TEMP_FILES+=("$temp_log")

    # Check if hoolamike exists
    if [ ! -f "$HOME/Hoolamike/hoolamike" ]; then
        handle_error "Hoolamike is not installed. Please install it first." false
        return 1
    fi

    print_section "Running Hoolamike"
    echo -e "Starting ${color_blue}$command${color_reset} operation with Hoolamike"
    echo -e "${color_yellow}This may take a very long time (up to several hours)${color_reset}"

    # Set start time for summary log
    echo "[$(date)] Starting hoolamike $command" > "$summary_log"

    # Start progress tracking
    local tracker=$(start_progress_tracking "Hoolamike $command" 3600)  # Estimate 1 hour

    # Create a unique ID for this run
    local run_id="hoolamike_$(date +%s)"

    # Start Hoolamike in the background
    (
        cd "$HOME/Hoolamike" || {
            log_error "Failed to enter Hoolamike directory"
            return 1
        }

        # Increase file limit
        if ! ulimit -n 64556 > /dev/null 2>&1; then
            log_warning "Failed to set ulimit. Performance may be affected."
        fi

        # Execute Hoolamike
        ./hoolamike "$command" > "$temp_log" 2>&1
        echo "HOOLAMIKE_EXIT_CODE=$?" > "/tmp/${run_id}.exit"
    ) &

    local pid=$!

    # Show spinner while waiting
    echo -e "\n${color_header}Processing Tale of Two Wastelands...${color_reset}"
    spinner $pid "Installing TTW components (this will take a long time)"

    # Check exit status
    local exit_status=1
    if [ -f "/tmp/${run_id}.exit" ]; then
        source "/tmp/${run_id}.exit"
        exit_status=$HOOLAMIKE_EXIT_CODE
        rm -f "/tmp/${run_id}.exit"
    fi

    # Filter the output and save to summary log
    grep -v "handling_asset\|voice\|sound\|textures\|\[OK\]\|updated templated value\|variable_found\|resolve_variable\|MAGICALLY\|hoolamike::extensions" "$temp_log" >> "$summary_log"

    # Add the last few lines for debugging
    echo "---- Last 20 lines of output ----" >> "$summary_log"
    tail -n 20 "$temp_log" >> "$summary_log"

    end_progress_tracking "$tracker" true

    # Error handling
    if [ $exit_status -ne 0 ]; then
        echo "[$(date)] Hoolamike $command failed with status $exit_status" >> "$summary_log"
        handle_error "Hoolamike execution failed with status $exit_status. Check $summary_log for details." false
        return 1
    fi

    echo "[$(date)] Completed hoolamike $command successfully" >> "$summary_log"
    log_info "Hoolamike execution completed for $command. See $summary_log for details."

    echo -e "\n${color_green}Hoolamike $command completed successfully!${color_reset}"
    echo -e "A summary log is available at: $summary_log"

    return 0
}
