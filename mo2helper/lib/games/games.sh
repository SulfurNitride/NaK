#!/bin/bash
# -------------------------------------------------------------------
# common.sh
# Common game-related functions for MO2 Helper
# -------------------------------------------------------------------

# Generate game advice text for all detected games
generate_advice() {
    log_info "Generating game advice"
    local steam_root=$(get_steam_root)

    # Check for specific games
    bg3_compatdata=$(find_game_compatdata "1086940" "$steam_root")
    fnv_compatdata=$(find_game_compatdata "22380" "$steam_root")
    enderal_compatdata=$(find_game_compatdata "976620" "$steam_root")

    print_section "Game-Specific Launch Options"

    # BG3 advice
    if [ -n "$bg3_compatdata" ]; then
        echo -e "\nFor Baldur's Gate 3 modlists:"
        echo -e "  ${color_blue}WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%${color_reset}"
        log_info "Provided BG3 advice (found compatdata)"
    else
        echo -e "\n${color_yellow}(Skip BG3 advice: not installed or not run yet)${color_reset}"
        log_info "Skipped BG3 advice (no compatdata found)"
    fi

    # FNV advice
    if [ -n "$fnv_compatdata" ]; then
        echo -e "\nFor Fallout New Vegas modlists:"
        echo -e "  ${color_blue}STEAM_COMPAT_DATA_PATH=\"$fnv_compatdata\" %command%${color_reset}"
        log_info "Provided FNV advice (found compatdata)"

        # Offer to set up FNV
        echo -e "\nWould you like to set up Fallout New Vegas for Mod Organizer 2?"
        if confirm_action "Set up FNV?"; then
            fnv_menu
        fi
    else
        echo -e "\n${color_yellow}(Skip FNV advice: not installed or not run yet)${color_reset}"
        log_info "Skipped FNV advice (no compatdata found)"
    fi

    # Enderal advice
    if [ -n "$enderal_compatdata" ]; then
        echo -e "\nFor Enderal modlists:"
        echo -e "  ${color_blue}STEAM_COMPAT_DATA_PATH=\"$enderal_compatdata\" %command%${color_reset}"
        log_info "Provided Enderal advice (found compatdata)"

        # Offer to set up Enderal
        echo -e "\nWould you like to set up Enderal for Mod Organizer 2?"
        if confirm_action "Set up Enderal?"; then
            enderal_menu
        fi
    else
        echo -e "\n${color_yellow}(Skip Enderal advice: not installed or not run yet)${color_reset}"
        log_info "Skipped Enderal advice (no compatdata found)"
    fi

    pause "Press any key to continue..."
}

# Game-specific actions menu for any selected game
game_specific_actions() {
    print_section "Launch Options for $selected_name"

    if [ -z "$selected_appid" ] || [ -z "$selected_name" ]; then
        echo -e "${color_yellow}No game selected.${color_reset}"
        return 1
    fi

    local steam_root=$(get_steam_root)
    local compatdata=$(find_game_compatdata "$selected_appid" "$steam_root")

    if [ -n "$compatdata" ]; then
        echo -e "Recommended launch options for $selected_name:"
        echo -e "${color_blue}STEAM_COMPAT_DATA_PATH=\"$compatdata\" %command%${color_reset}"
        log_info "Displayed launch options for $selected_name"
    else
        echo -e "${color_yellow}$selected_name has not been run yet or compatdata not found.${color_reset}"
        echo -e "Please run the game at least once through Steam before using these options."
        log_warning "Compatdata not found for $selected_name"
    fi

    pause "Press any key to continue..."
}
