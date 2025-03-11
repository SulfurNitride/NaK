#!/bin/bash
# -------------------------------------------------------------------
# fallout.sh
# Fallout New Vegas specific functions for MO2 Helper
# -------------------------------------------------------------------

# Fallout New Vegas menu 
fnv_menu() {
    # Set up for Fallout New Vegas (AppID 22380)
    selected_appid="22380"
    selected_name="Fallout New Vegas"

    # Show launch advice specific to FNV
    print_section "Fallout New Vegas Options"
    local steam_root=$(get_steam_root)
    local fnv_compatdata=$(find_game_compatdata "22380" "$steam_root")

    if [ -n "$fnv_compatdata" ]; then
        echo -e "Recommended launch options for Fallout New Vegas and dependencies:"
        echo -e "${color_blue}STEAM_COMPAT_DATA_PATH=\"$fnv_compatdata\" %command%${color_reset}"
        log_info "Displayed FNV launch options"

        # Offer to install FNV dependencies
        echo -e "\nWould you like to install Fallout New Vegas specific dependencies for Mod Organizer 2?"
        if confirm_action "Install dependencies?"; then
            install_fnv_dependencies
        fi
    else
        echo -e "${color_yellow}Fallout New Vegas has not been run yet or is not installed.${color_reset}"
        echo -e "Please run the game at least once through Steam before using these options."
        log_warning "FNV compatdata not found"
    fi

    pause "Press any key to continue..."
}

# Install Fallout New Vegas specific dependencies
install_fnv_dependencies() {
    log_info "Installing Fallout New Vegas specific dependencies"

    print_section "Fallout New Vegas Dependencies"
    echo -e "Installing dependencies required for Fallout New Vegas and TTW"

    # Set up for AppID 22380
    selected_appid="22380"
    selected_name="Fallout New Vegas"

    # Custom dependency list
    components=(
        fontsmooth=rgb
        xact
        xact_x64
        d3dx9_43
        d3dx9
        vcrun2022
    )

    check_dependencies

    # Install using existing function
    install_proton_dependencies

    echo -e "\n${color_green}Fallout New Vegas dependencies installed!${color_reset}"
    echo -e "These dependencies are required for TTW to function properly."

    return 0
}
