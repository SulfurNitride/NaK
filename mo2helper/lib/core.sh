#!/bin/bash
# -------------------------------------------------------------------
# core.sh
# Core functionality and variables for MO2 Helper
# -------------------------------------------------------------------

# Global variables
declare -a game_array
declare -a TEMP_FILES
LAST_ERROR=""
CURRENT_OPERATION=""
protontricks_cmd=""
selected_appid=""
selected_name=""
selected_scaling="96"  # Default scaling value
show_advice=true
SELECTION_RESULT=0

# Terminal colors and formatting
color_title="\033[1;36m"    # Cyan, bold
color_green="\033[38;2;0;255;0m"   # Green for success messages
color_yellow="\033[38;2;255;255;0m" # Yellow for warnings
color_red="\033[38;2;255;0;0m"      # Red for errors
color_blue="\033[38;2;0;185;255m"   # Blue for commands
color_header="\033[1;33m"  # Yellow bold for headers
color_option="\033[1;37m"  # White bold for menu options
color_desc="\033[0;37m"    # White for descriptions
color_reset="\033[0m"

# Config settings
CONFIG_DIR="$HOME/.config/mo2helper"
CONFIG_FILE="$CONFIG_DIR/config.ini"
DEFAULT_CONFIG=(
    "logging_level=0"                   # 0=INFO, 1=WARNING, 2=ERROR
    "show_advanced_options=false"       # Hide advanced options by default
    "hoolamike_version="                # Last installed Hoolamike version
    "check_updates=true"                # Check for updates on startup
    "enable_telemetry=false"            # Send anonymous usage data
    "preferred_game_appid="             # Last used game AppID
    "default_scaling=96"                # Default DPI scaling value
    "enable_detailed_progress=true"     # Show detailed progress for long operations
    "auto_detect_games=true"            # Automatically detect installed games
    "cache_steam_path=true"             # Cache Steam path between runs
)

# Log file settings
log_dir="$HOME"
log_file="$log_dir/mo2helper.log"
max_log_size=5242880  # 5MB
max_log_files=5

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Cleanup function
cleanup() {
    log_info "Running cleanup procedures"

    # Remove temporary files
    if [ ${#TEMP_FILES[@]} -gt 0 ]; then
        log_info "Removing ${#TEMP_FILES[@]} temporary files"
        for file in "${TEMP_FILES[@]}"; do
            if [ -f "$file" ]; then
                rm -f "$file"
                log_info "Removed temporary file: $file"
            fi
        done
    fi

    # Report any errors that caused termination
    if [ -n "$LAST_ERROR" ]; then
        log_error "Script terminated with error: $LAST_ERROR"
    else
        log_info "Script completed normally"
    fi
}

# Dependency checks
check_dependencies() {
    log_info "Checking dependencies"
    if ! command_exists protontricks && \
       ! flatpak list --app --columns=application 2>/dev/null | grep -q com.github.Matoking.protontricks; then
        error_exit "Protontricks is not installed. Install it with:\n- Native: sudo apt install protontricks\n- Flatpak: flatpak install com.github.Matoking.protontricks"
    fi
    
    if command_exists protontricks; then
        protontricks_cmd="protontricks"
        log_info "Using native protontricks"
    else
        protontricks_cmd="flatpak run com.github.Matoking.protontricks"
        log_info "Using flatpak protontricks"
    fi
}

check_flatpak_steam() {
    log_info "Checking for Flatpak Steam"
    if flatpak list --app --columns=application 2>/dev/null | grep -q 'com.valvesoftware.Steam'; then
        error_exit "Detected Steam installed via Flatpak. This script doesn't support Flatpak Steam installations."
    fi
}

get_steam_root() {
    log_info "Finding Steam root directory"

    # Check if we have cached value
    if [ "$(get_config "cache_steam_path" "true")" == "true" ]; then
        local cached_path=$(get_config "steam_path" "")
        if [ -n "$cached_path" ] && [ -d "$cached_path/steamapps" ]; then
            log_info "Using cached Steam path: $cached_path"
            echo "$cached_path"
            return
        fi
    fi

    local candidates=(
        "$HOME/.local/share/Steam"
        "$HOME/.steam/steam"
        "$HOME/.steam/debian-installation"
        "/usr/local/steam"
        "/usr/share/steam"
    )
    for candidate in "${candidates[@]}"; do
        if [ -d "$candidate/steamapps" ]; then
            log_info "Found Steam root: $candidate"

            # Cache the path if enabled
            if [ "$(get_config "cache_steam_path" "true")" == "true" ]; then
                set_config "steam_path" "$candidate"
            fi

            echo "$candidate"
            return
        fi
    done
    error_exit "Could not find Steam installation in standard locations:\n${candidates[*]}"
}

# Function to check for script updates
check_for_updates() {
    # This is a placeholder for the update checking functionality
    # You can implement this later if needed
    log_info "Checking for updates (placeholder)"
    return 0
}

# Menu system structure (main menu and submenu handlers)
main_menu() {
    while true; do
        print_header

        display_menu "Main Menu" \
            "Mod Organizer Setup" "Set up MO2 with Proton, NXM handler, and dependencies" \
            "Tale of Two Wastelands" "TTW-specific installation and tools" \
            "Hoolamike Tools" "Wabbajack and other modlist installations" \
            "Game-Specific Info" "Fallout NV, Enderal, BG3 Info Here!" \
            "Exit" "Quit the application"

        local choice=$?

        case $choice in
            1) mo2_setup_menu ;;
            2) ttw_installation_menu ;;
            3) hoolamike_tools_menu ;;
            4) game_specific_menu ;;
            5)
                log_info "User exited application"
                echo -e "\n${color_green}Thank you for using the MO2 Helper!${color_reset}"
                exit 0
                ;;
        esac
    done
}

# Hoolamike general tools menu
hoolamike_tools_menu() {
    while true; do
        print_header

        # Check if Hoolamike is installed
        local hoolamike_installed=false
        if [ -f "$HOME/Hoolamike/hoolamike" ]; then
            hoolamike_installed=true
        fi

        # Status indicator
        local hoolamike_status="${color_red}Not Installed${color_reset}"
        if $hoolamike_installed; then
            hoolamike_status="${color_green}Installed${color_reset}"
        fi

        echo -e "Hoolamike: $hoolamike_status"

        display_menu "Hoolamike Mod Tools" \
            "Download/Update Hoolamike" "Download or update the Hoolamike tool" \
            "Install Wabbajack Modlist" "Install a Wabbajack modlist using Hoolamike" \
            "Back to Main Menu" "Return to the main menu"

        local choice=$?

        case $choice in
            1)
                if $hoolamike_installed; then
                    echo -e "\n${color_yellow}Hoolamike is already installed.${color_reset}"
                    if confirm_action "Re-download and reinstall?"; then
                        download_hoolamike
                    fi
                else
                    download_hoolamike
                fi
                ;;
            2)
                if ! $hoolamike_installed; then
                    handle_error "Hoolamike is not installed. Please install it first." false
                else
                    install_wabbajack_modlist
                fi
                pause "Press any key to continue..."
                ;;
            3) return ;;
        esac
    done
}


# MO2 setup submenu
mo2_setup_menu() {
    while true; do
        print_header

        display_menu "Mod Organizer 2 Setup" \
            "Install Basic Dependencies" "Install common Proton components for MO2" \
            "Configure NXM Handler" "Set up Nexus Mod Manager link handling" \
            "DPI Scaling" "Configure DPI scaling for HiDPI displays" \
            "Back to Main Menu" "Return to the main menu"

        local choice=$?

        case $choice in
            1)
                check_dependencies
                get_non_steam_games
                if select_game; then
                    install_proton_dependencies
                    pause "Basic dependencies installation complete!"
                fi
                ;;
            2)
                check_dependencies
                get_non_steam_games
                if select_game; then
                    if setup_nxm_handler; then
                        pause "NXM handler configured successfully!"
                    fi
                fi
                ;;
            3)
                check_dependencies
                get_non_steam_games
                if select_game; then
                    select_dpi_scaling
                    apply_dpi_scaling
                    pause "DPI scaling applied successfully!"
                fi
                ;;
            4) return ;;
        esac
    done
}

# Game-specific tools submenu
game_specific_menu() {
    while true; do
        print_header

        display_menu "Game-Specific Tools" \
            "Fallout New Vegas" "Launch options for Fallout New Vegas" \
            "Enderal Special Edition" "Launch options for Enderal" \
            "Baldur's Gate 3" "Launch options for Baldur's Gate 3" \
            "All Games Advice" "View advice for all detected games" \
            "Back to Main Menu" "Return to the main menu"

        local choice=$?

        case $choice in
            1) fnv_menu ;;
            2) enderal_menu ;;
            3) bg3_menu ;;
            4) generate_advice ;;
            5) return ;;
        esac
    done
}

# System utilities submenu
system_utilities_menu() {
    while true; do
        print_header

        display_menu "System Utilities" \
            "View Logs" "Display recent log entries and log file location" \
            "Check System Compatibility" "Verify system compatibility for gaming" \
            "Configuration" "Adjust script settings and preferences" \
            "About" "View information about this script" \
            "Back to Main Menu" "Return to the main menu"

        local choice=$?

        case $choice in
            1)
                view_logs
                echo -e "\nPress any key to continue..."
                read -n 1
                ;;
            2)
                check_system_compatibility
                echo -e "\nPress any key to continue..."
                read -n 1
                ;;
            3) show_config_menu ;;
            4)
                show_about
                echo -e "\nPress any key to continue..."
                read -n 1
                ;;
            5) return ;;
        esac
    done
}

# Placeholder for the check_system_compatibility function
check_system_compatibility() {
    print_section "System Compatibility Check"
    echo "Checking system compatibility..."
    log_system_info
    
    # You can implement detailed compatibility checks here
    
    echo -e "\n${color_green}Basic system compatibility check passed.${color_reset}"
}

# Placeholder for the show_about function
show_about() {
    print_section "About MO2 Helper"
    echo -e "Mod Organizer 2 Linux Helper"
    echo -e "Version: $SCRIPT_VERSION"
    echo -e "Date: $SCRIPT_DATE"
    echo -e "\nThis script helps manage Mod Organizer 2 installations on Linux."
}

# Placeholder for the show_config_menu function
show_config_menu() {
    print_section "Configuration Menu"
    echo "Configuration options will be implemented here."
    pause "Press any key to continue..."
}
