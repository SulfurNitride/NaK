#!/bin/bash
# -------------------------------------------------------------------
# bg3.sh
# Baldur's Gate 3 specific functions for MO2 Helper
# -------------------------------------------------------------------

# Baldur's Gate 3 menu
bg3_menu() {
    # Set up for Baldur's Gate 3 (AppID 1086940)
    selected_appid="1086940"
    selected_name="Baldur's Gate 3"

    # Show launch advice specific to BG3
    print_section "Baldur's Gate 3 Options"
    local steam_root=$(get_steam_root)
    local bg3_compatdata=$(find_game_compatdata "1086940" "$steam_root")

    if [ -n "$bg3_compatdata" ]; then
        echo -e "Recommended launch options for Baldur's Gate 3:"
        echo -e "${color_blue}WINEDLLOVERRIDES=\"DWrite.dll=n,b\" %command%${color_reset}"
        log_info "Displayed BG3 launch options"
    else
        echo -e "${color_yellow}Baldur's Gate 3 has not been run yet or is not installed.${color_reset}"
        echo -e "Please run the game at least once through Steam before using these options."
        log_warning "BG3 compatdata not found"
    fi

    pause "Press any key to continue..."
}
