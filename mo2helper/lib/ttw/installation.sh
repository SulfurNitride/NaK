#!/bin/bash
# -------------------------------------------------------------------
# installation.sh
# TTW installation functions for MO2 Helper
# -------------------------------------------------------------------

# TTW installation menu
ttw_installation_menu() {
    while true; do
        print_header

        # Check if Hoolamike is installed
        local hoolamike_installed=false
        if [ -f "$HOME/Hoolamike/hoolamike" ]; then
            hoolamike_installed=true
        fi

        # Check if TTW is installed
        local ttw_installed=false
        if check_ttw_installation; then
            ttw_installed=true
        fi

        # Status indicators
        local hoolamike_status="${color_red}Not Installed${color_reset}"
        if $hoolamike_installed; then
            hoolamike_status="${color_green}Installed${color_reset}"
        fi

        local ttw_status="${color_red}Not Installed${color_reset}"
        if $ttw_installed; then
            ttw_status="${color_green}Installed${color_reset}"
        fi

        echo -e "Hoolamike: $hoolamike_status"
        echo -e "TTW: $ttw_status"

        display_menu "Tale of Two Wastelands Setup" \
            "Automated TTW Setup" "Complete automated installation (all steps at once)" \
            "Download Hoolamike" "Download and setup Hoolamike for TTW installation" \
            "Install FNV Dependencies" "Install Fallout New Vegas Proton dependencies" \
            "Run TTW Installation" "Execute TTW installation with Hoolamike" \
            "View TTW Documentation" "View TTW installation guides and documentation" \
            "Back to Main Menu" "Return to the main menu"

        local choice=$?

        case $choice in
            1)
                automated_ttw_setup
                ;;
            2)
                if $hoolamike_installed; then
                    echo -e "\n${color_yellow}Hoolamike is already installed.${color_reset}"
                    if confirm_action "Re-download and reinstall?"; then
                        download_hoolamike
                    fi
                else
                    download_hoolamike
                fi
                ;;
            3)
                install_fnv_dependencies
                pause "Press any key to continue..."
                ;;
            4)
                if ! $hoolamike_installed; then
                    handle_error "Hoolamike is not installed. Please install it first." false
                else
                    if ! ls "$HOME/Hoolamike"/*.mpi >/dev/null 2>&1; then
                        echo -e "${color_yellow}No TTW MPI file detected.${color_reset}"
                        if confirm_action "Wait for MPI file?"; then
                            if wait_for_mpi_file; then
                                run_hoolamike "tale-of-two-wastelands"
                            fi
                        fi
                    else
                        run_hoolamike "tale-of-two-wastelands"
                    fi
                fi
                pause "Press any key to continue..."
                ;;
            5)
                view_ttw_docs
                ;;
            6)
                return
                ;;
        esac
    done
}

# Check if TTW is already installed
check_ttw_installation() {
    log_info "TTW installation check disabled"
    return 1  # Always return 'not installed'
}

# View TTW documentation
view_ttw_docs() {
    print_section "Tale of Two Wastelands Documentation"

    echo -e "Tale of Two Wastelands (TTW) combines Fallout 3 and Fallout New Vegas into one game."
    echo -e "\n${color_header}Official Resources:${color_reset}"
    echo -e "- Official Website: ${color_blue}https://taleoftwowastelands.com/${color_reset}"
    echo -e "- Installation Guide: ${color_blue}https://taleoftwowastelands.com/wiki_ttw/get-started/${color_reset}"
    echo -e "- TTW Discord: ${color_blue}https://discord.gg/taleoftwowastelands${color_reset}"

    echo -e "\n${color_header}Using Hoolamike:${color_reset}"
    echo -e "- GitHub Repository: ${color_blue}https://github.com/Niedzwiedzw/hoolamike${color_reset}"
    echo -e "- Configuration Guide: ${color_blue}https://github.com/Niedzwiedzw/hoolamike/blob/main/README.md${color_reset}"

    echo -e "\n${color_header}Requirements:${color_reset}"
    echo -e "1. Original copies of Fallout 3 GOTY and Fallout New Vegas Ultimate Edition"
    echo -e "2. Both games must be installed and have run at least once"
    echo -e "3. The TTW MPI installer file (download from the TTW website)"

    echo -e "\n${color_header}Linux-Specific Tips:${color_reset}"
    echo -e "- Make sure you've installed the FNV dependencies through this tool"
    echo -e "- Be patient, the installation can take several hours"

    pause "Press any key to return to the TTW menu..."
    return 0
}

# Wait for MPI file to be placed in the hoolamike directory
wait_for_mpi_file() {
    local hoolamike_dir="$HOME/Hoolamike"
    local wait_time=0
    local timeout=6000000  # 10000 minutes

    print_section "Waiting for TTW MPI File"
    echo -e "Waiting for you to download and place the TTW MPI file in:"
    echo -e "${color_blue}$hoolamike_dir/${color_reset}"
    echo -e "\nPress Ctrl+C at any time to cancel..."

    # Wait for MPI file with timeout
    while [ $wait_time -lt $timeout ]; do
        # Check for any .mpi file
        if ls "$hoolamike_dir"/*.mpi >/dev/null 2>&1; then
            mpi_file=$(ls "$hoolamike_dir"/*.mpi | head -n1)
            log_info "Found MPI file: $mpi_file"
            echo -e "\n${color_green}Detected MPI file: $(basename "$mpi_file")${color_reset}"
            return 0
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

# Automated TTW setup (all steps in one)
automated_ttw_setup() {
    print_section "Automated TTW Installation"
    echo -e "This will perform a complete setup of Tale of Two Wastelands:"
    echo -e "1. Download and install Hoolamike tool"
    echo -e "2. Install Fallout New Vegas Proton dependencies"
    echo -e "3. Wait for TTW MPI file (if needed)"
    echo -e "4. Run the TTW installation process"
    echo -e "\n${color_yellow}NOTE: This process will take a long time to complete!${color_reset}"

    if ! confirm_action "Start complete TTW setup?"; then
        echo -e "\n${color_yellow}Setup canceled.${color_reset}"
        return 1
    fi

    # Step 1: Check dependencies
    check_dependencies
    if ! check_download_dependencies; then
        handle_error "Required dependencies missing for download" false
        return 1
    fi

    # Step 2: Download Hoolamike if not already installed
    local hoolamike_dir="$HOME/Hoolamike"
    local hoolamike_installed=false

    if [ -f "$hoolamike_dir/hoolamike" ]; then
        hoolamike_installed=true
        echo -e "\n${color_green}✓ Hoolamike already installed${color_reset}"
        log_info "Hoolamike already installed, skipping download"
    else
        echo -e "\n${color_header}Step 1: Downloading Hoolamike${color_reset}"
        download_hoolamike
        if [ ! -f "$hoolamike_dir/hoolamike" ]; then
            handle_error "Hoolamike download failed" false
            return 1
        fi
    fi

    # Step 3: Install Fallout New Vegas dependencies
    echo -e "\n${color_header}Step 2: Installing Fallout New Vegas dependencies${color_reset}"
    install_fnv_dependencies

    # Step 4: Check for MPI file and wait if needed
    echo -e "\n${color_header}Step 3: Checking for TTW MPI file${color_reset}"
    if ! ls "$hoolamike_dir"/*.mpi >/dev/null 2>&1; then
        echo -e "${color_yellow}No TTW MPI file detected.${color_reset}"
        echo -e "You need to download the TTW installer file (.mpi) from:"
        echo -e "${color_blue}https://mod.pub/ttw/133/files${color_reset}"
        echo -e "Download the latest 'TTW_*.7z' file and extract the .mpi file"
        echo -e "Then place the .mpi file in: ${color_blue}$hoolamike_dir/${color_reset}"

        if confirm_action "Wait for MPI file?"; then
            if ! wait_for_mpi_file; then
                handle_error "Failed waiting for MPI file" false
                return 1
            fi
        else
            echo -e "\n${color_yellow}Setup paused. Run again after downloading the MPI file.${color_reset}"
            return 1
        fi
    else
        echo -e "${color_green}✓ TTW MPI file found${color_reset}"
    fi

    # Step 5: Run TTW installation with Hoolamike
    echo -e "\n${color_header}Step 4: Installing Tale of Two Wastelands${color_reset}"
    echo -e "${color_yellow}This will take a VERY long time (potentially hours)${color_reset}"
    if ! confirm_action "Ready to begin TTW installation?"; then
        echo -e "\n${color_yellow}Installation canceled.${color_reset}"
        return 1
    fi

    run_hoolamike "tale-of-two-wastelands"

    # Final completion message
    echo -e "\n${color_green}=====================================${color_reset}"
    echo -e "${color_green}Tale of Two Wastelands setup complete!${color_reset}"
    echo -e "${color_green}=====================================${color_reset}"

    pause "Press any key to return to the main menu..."
    return 0
}
