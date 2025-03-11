#!/bin/bash
# -------------------------------------------------------------------
# enderal.sh
# Enderal Special Edition specific functions for MO2 Helper
# -------------------------------------------------------------------

# Enderal Special Edition menu
enderal_menu() {
    # Set up for Enderal SE (AppID 976620)
    selected_appid="976620"
    selected_name="Enderal Special Edition"

    # Show launch advice specific to Enderal
    print_section "Enderal Special Edition Options"
    local steam_root=$(get_steam_root)
    local enderal_compatdata=$(find_game_compatdata "976620" "$steam_root")

    if [ -n "$enderal_compatdata" ]; then
        echo -e "Recommended launch options for Enderal Special Edition and dependencies:"
        echo -e "${color_blue}STEAM_COMPAT_DATA_PATH=\"$enderal_compatdata\" %command%${color_reset}"
        log_info "Displayed Enderal launch options"

        # Offer to install Enderal dependencies
        echo -e "\nWould you like to install Enderal specific dependencies for modding?"
        if confirm_action "Install dependencies?"; then
            # Set components for Enderal before installing
            components=(
                fontsmooth=rgb
                xact
                xact_x64
                d3dx11_43
                d3dcompiler_43
                d3dcompiler_47
                vcrun2022
                dotnet6
                dotnet7
                dotnet8
            )
            install_proton_dependencies
        fi
    else
        echo -e "${color_yellow}Enderal has not been run yet or is not installed.${color_reset}"
        echo -e "Please run the game at least once through Steam before using these options."
        log_warning "Enderal compatdata not found"
    fi

    pause "Press any key to continue..."
}
