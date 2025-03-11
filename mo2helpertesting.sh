#!/bin/bash
# -------------------------------------------------------------------
# modorganizer2-helper.sh
# Unified script with NXM handler, Proton setup, and TTW integration
# -------------------------------------------------------------------

# ===== 1. SCRIPT INITIALIZATION =====

# Script metadata
SCRIPT_VERSION="1.2.0"
SCRIPT_DATE="$(date +%Y-%m-%d)"

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

# ===== 2. BASIC UTILITIES =====

# Set up trap to handle errors and cleanup
trap cleanup EXIT INT TERM

# Clear screen and print header
print_header() {
    clear
    echo -e "${color_title}=====================================${color_reset}"
    echo -e "${color_title}    Mod Organizer 2 Linux Helper    ${color_reset}"
    echo -e "${color_title}=====================================${color_reset}"
    echo -e "${color_desc}Version $SCRIPT_VERSION | $SCRIPT_DATE${color_reset}\n"
}

# Print section header
print_section() {
    echo -e "\n${color_header}=== $1 ===${color_reset}"
}

# Format menu option
format_option() {
    local number=$1
    local title=$2
    local description=$3
    echo -e "${color_option}$number. $title${color_reset}"
    echo -e "   ${color_desc}$description${color_reset}"
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

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# ===== 3. LOGGING SYSTEM =====

# Log levels
LOG_LEVEL_INFO=0
LOG_LEVEL_WARNING=1
LOG_LEVEL_ERROR=2
CURRENT_LOG_LEVEL=$LOG_LEVEL_INFO

# Setup log directory and file
setup_logging() {
    # No need to create directory for HOME

    # Check if log rotation needed
    if [ -f "$log_file" ] && [ $(stat -c%s "$log_file") -gt $max_log_size ]; then
        # Rotate logs
        for ((i=$max_log_files-1; i>0; i--)); do
            if [ -f "${log_file}.$((i-1))" ]; then
                mv "${log_file}.$((i-1))" "${log_file}.$i"
            fi
        done

        if [ -f "$log_file" ]; then
            mv "$log_file" "${log_file}.0"
        fi
    fi

    # Create or append to log file
    echo "MO2 Helper Log - $(date)" > "$log_file"
    echo "=============================" >> "$log_file"
}

# Log with level
log() {
    local level=$1
    local message=$2
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")

    # Only log if level is at or above current log level
    if [ $level -ge $CURRENT_LOG_LEVEL ]; then
        local level_text="INFO"
        if [ $level -eq $LOG_LEVEL_WARNING ]; then
            level_text="WARNING"
        elif [ $level -eq $LOG_LEVEL_ERROR ]; then
            level_text="ERROR"
        fi

        echo "[$timestamp] [$level_text] $message" >> "$log_file"

        # Echo errors to stderr
        if [ $level -eq $LOG_LEVEL_ERROR ]; then
            echo -e "${color_red}ERROR: $message${color_reset}" >&2
        fi
    fi
}

# Convenience functions
log_info() {
    log $LOG_LEVEL_INFO "$1"
}

log_warning() {
    log $LOG_LEVEL_WARNING "$1"
}

log_error() {
    log $LOG_LEVEL_ERROR "$1"
}

# Function to display recent log entries
view_logs() {
    echo -e "\n=== Recent Log Entries ==="
    if [ -f "$log_file" ]; then
        echo "Showing last 20 entries from $log_file:"
        echo "----------------------------------------"
        tail -n 20 "$log_file"
        echo "----------------------------------------"
        echo "Full log file: $log_file"
    else
        echo "No log file found at $log_file"
    fi
}

# Export system information to log
log_system_info() {
    log_info "======= System Information ======="
    log_info "OS: $(lsb_release -ds 2>/dev/null || cat /etc/*release 2>/dev/null | head -n1 || uname -om)"
    log_info "Kernel: $(uname -r)"
    log_info "Memory: $(free -h | awk '/^Mem:/ {print $2}')"
    log_info "Disk space: $(df -h / | awk 'NR==2 {print $4}') available"

    # Check for needed dependencies
    for cmd in protontricks flatpak curl jq unzip wget; do
        if command_exists "$cmd"; then
            log_info "$cmd: Installed ($(command -v "$cmd"))"
        else
            log_warning "$cmd: Not installed"
        fi
    done
    log_info "=================================="
}

# ===== 4. CONFIGURATION MANAGEMENT =====

# Create default config if it doesn't exist
create_default_config() {
    mkdir -p "$CONFIG_DIR"

    # Check if config file exists
    if [ ! -f "$CONFIG_FILE" ]; then
        log_info "Creating default configuration file"

        echo "# Mod Organizer 2 Helper Configuration" > "$CONFIG_FILE"
        echo "# Created: $(date)" >> "$CONFIG_FILE"
        echo "" >> "$CONFIG_FILE"

        # Write default values
        for line in "${DEFAULT_CONFIG[@]}"; do
            echo "$line" >> "$CONFIG_FILE"
        done
    fi
}

# Function to get config value
get_config() {
    local key="$1"
    local default_value="$2"

    if [ ! -f "$CONFIG_FILE" ]; then
        create_default_config
    fi

    # Extract value from config file
    local value=$(grep "^$key=" "$CONFIG_FILE" | cut -d= -f2-)

    # Return default if not found or empty
    if [ -z "$value" ]; then
        echo "$default_value"
    else
        echo "$value"
    fi
}

# Function to load cached values from config
load_cached_values() {
    log_info "Loading cached values from config"

    # Load default scaling
    selected_scaling=$(get_config "default_scaling" "96")
    log_info "Loaded default scaling: $selected_scaling"

    # Load preferred game if set
    local preferred_appid=$(get_config "preferred_game_appid" "")
    if [ -n "$preferred_appid" ]; then
        log_info "Found preferred game AppID: $preferred_appid"
    fi

    # Load logging level
    CURRENT_LOG_LEVEL=$(get_config "logging_level" "0")
    log_info "Set logging level to: $CURRENT_LOG_LEVEL"

    # Load show_advanced_options
    show_advanced=$(get_config "show_advanced_options" "false")
    log_info "Advanced options display: $show_advanced"

    # Load advice setting
    show_advice=$(get_config "show_advice" "true")
    log_info "Show advice: $show_advice"
}

# Function to set config value
set_config() {
    local key="$1"
    local value="$2"

    if [ ! -f "$CONFIG_FILE" ]; then
        create_default_config
    fi

    # Check if key exists
    if grep -q "^$key=" "$CONFIG_FILE"; then
        # Update existing key
        sed -i "s/^$key=.*/$key=$value/" "$CONFIG_FILE"
    else
        # Add new key
        echo "$key=$value" >> "$CONFIG_FILE"
    fi

    log_info "Updated configuration: $key=$value"
}

# ===== 5. ERROR HANDLING & PROGRESS TRACKING =====

# Function to handle errors in a standard way
handle_error() {
    local error_message="$1"
    local exit_script=${2:-true}
    local error_code=${3:-1}

    LAST_ERROR="$error_message"
    log_error "$error_message"

    echo -e "\n${color_red}ERROR: $error_message${color_reset}"

    # Show additional help if available
    if [ -n "$4" ]; then
        echo -e "${color_yellow}HELP: $4${color_reset}"
    fi

    # Allow user to view the log
    echo -e "\nWould you like to view the recent log entries to help diagnose the issue?"
    if confirm_action "View logs?"; then
        view_logs
    fi

    if $exit_script; then
        exit $error_code
    fi
}

# Confirmation prompt
confirm_action() {
    local prompt=${1:-"Continue?"}
    while true; do
        read -rp "$prompt [y/n]: " yn
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes (y) or no (n).";;
        esac
    done
}

# Function to check disk space before operations
check_disk_space() {
    local required_mb=$1
    local path=${2:-$HOME}

    log_info "Checking for $required_mb MB of free space in $path"

    # Get available space in MB
    local available_kb=$(df -k "$path" | awk 'NR==2 {print $4}')
    local available_mb=$((available_kb / 1024))

    if [ $available_mb -lt $required_mb ]; then
        handle_error "Insufficient disk space. Need ${required_mb}MB but only ${available_mb}MB available in $path" \
            false
        return 1
    fi

    log_info "Sufficient disk space available: $available_mb MB"
    return 0
}

# Progress bar function
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local completed=$((current * width / total))
    local remaining=$((width - completed))

    # Build progress bar
    local bar="["
    for ((i=0; i<completed; i++)); do
        bar+="#"
    done

    for ((i=0; i<remaining; i++)); do
        bar+="."
    done
    bar+="] $percentage%"

    # Print progress bar (with carriage return to overwrite)
    echo -ne "\r$bar"

    # Print newline if operation is complete
    if [ $current -eq $total ]; then
        echo ""
    fi
}

# Spinner animation for long-running tasks
spinner() {
    local pid=$1
    local message=${2:-"Processing..."}
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

    while [ "$(ps a | awk '{print $1}' | grep -w $pid)" ]; do
        local temp=${spinstr#?}
        printf "\r[%c] %s" "$spinstr" "$message"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
    done
    printf "\r    \r"
}

# Function to track and report progress of a time-consuming operation
start_progress_tracking() {
    local operation_name="$1"
    local expected_duration=${2:-60}  # Default 60 seconds

    CURRENT_OPERATION="$operation_name"
    local start_time=$(date +%s)
    local tracker_file="/tmp/mo2helper_progress_$$"

    # Add to temp files for cleanup
    TEMP_FILES+=("$tracker_file")

    # Write start time to tracker file
    echo "$start_time" > "$tracker_file"
    echo "$expected_duration" >> "$tracker_file"
    echo "$operation_name" >> "$tracker_file"

    log_info "Started operation: $operation_name (expected duration: ${expected_duration}s)"

    # Return the tracker file path for later use
    echo "$tracker_file"
}

# Update progress
update_progress() {
    local tracker_file="$1"
    local current_step="$2"
    local total_steps="$3"

    if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
        return 0
    fi

    local tracker_file="$1"
    local current_step="$2"
    local total_steps="$3"

    if [ ! -f "$tracker_file" ]; then
        return 1
    fi

    # Update tracker file with progress info
    echo "$current_step" >> "$tracker_file"
    echo "$total_steps" >> "$tracker_file"

    # Calculate and show progress
    local percentage=$((current_step * 100 / total_steps))
    local start_time=$(head -n 1 "$tracker_file")
    local expected_duration=$(sed -n '2p' "$tracker_file")
    local operation_name=$(sed -n '3p' "$tracker_file")
    local current_time=$(date +%s)
    local elapsed=$((current_time - start_time))

    # Estimate remaining time
    local remaining=0
    if [ $current_step -gt 0 ]; then
        remaining=$(( (elapsed * total_steps / current_step) - elapsed ))
    else
        remaining=$expected_duration
    fi

    # Format times
    local elapsed_fmt=$(printf "%02d:%02d" $((elapsed/60)) $((elapsed%60)))
    local remaining_fmt=$(printf "%02d:%02d" $((remaining/60)) $((remaining%60)))

    # Show progress
    echo -ne "\r[$percentage%] $operation_name - Elapsed: $elapsed_fmt, Remaining: $remaining_fmt"

    if [ $current_step -eq $total_steps ]; then
        echo -e "\n${color_green}Completed: $operation_name${color_reset}"
        log_info "Completed operation: $operation_name (took ${elapsed}s)"
    fi
}

# Function to end progress tracking
end_progress_tracking() {
    local tracker_file="$1"
    local success=${2:-true}

    if [ ! -f "$tracker_file" ]; then
        return 1
    fi

    local start_time=$(head -n 1 "$tracker_file")
    local operation_name=$(sed -n '3p' "$tracker_file")
    local current_time=$(date +%s)
    local elapsed=$((current_time - start_time))

    # Format elapsed time
    local elapsed_fmt=$(printf "%02d:%02d" $((elapsed/60)) $((elapsed%60)))

    if $success; then
        echo -e "\n${color_green}Completed: $operation_name in $elapsed_fmt${color_reset}"
        log_info "Successfully completed operation: $operation_name (took ${elapsed}s)"
    else
        echo -e "\n${color_red}Failed: $operation_name after $elapsed_fmt${color_reset}"
        log_error "Failed operation: $operation_name (took ${elapsed}s)"
    fi

    CURRENT_OPERATION=""
    rm -f "$tracker_file"
}

# ===== 6. MENU SYSTEM =====

# Display a notification with optional timeout
notify() {
    local message="$1"
    local wait_for_key=true

    if [ -n "$2" ]; then
        wait_for_key="$2"
    fi

    echo -e "\n${color_yellow}$message${color_reset}"

    if [ "$wait_for_key" = true ]; then
        echo -e "\nPress any key to continue..."
        read -n 1 -s
    fi
}

# Function to pause and wait for user to press a key
pause() {
    local message=${1:-"Press any key to continue..."}
    echo -e "\n${color_desc}$message${color_reset}"
    read -n 1 -s
}

# Improved menu function with back option and descriptions
display_menu() {
    local title=$1
    shift
    local options=("$@")
    local choice

    print_section "$title"

    # Display menu options with descriptions
    for ((i=0; i<${#options[@]}; i+=2)); do
        if [[ "$choice" =~ ^[0-9]+$ ]]; then
            # Last option is "back" or "exit"
            echo ""
        fi
        format_option "$((i/2+1))" "${options[i]}" "${options[i+1]}"
    done

    # Calculate the maximum valid option number
    local max_option=$(( ${#options[@]} / 2 ))

    # Get user choice
    while true; do
        read -rp $'\nSelect an option (1-'$max_option'): ' choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= max_option )); then
            return $choice
        else
            echo "Invalid choice. Please try again."
        fi
    done
}

# Select from a list with pagination
select_from_list() {
    local title=$1
    shift
    local items=("$@")
    local page_size=10
    # Global variable to store selection
    SELECTION_RESULT=0

    if [ ${#items[@]} -eq 0 ]; then
        echo "No items to display."
        SELECTION_RESULT=0
        return 0
    fi

    local total_items=${#items[@]}
    local total_pages=$(( (total_items + page_size - 1) / page_size ))
    local current_page=1
    local choice

    while true; do
        print_section "$title (Page $current_page of $total_pages)"

        # Calculate start and end for current page
        local start=$(( (current_page - 1) * page_size + 1 ))
        local end=$(( current_page * page_size ))
        if (( end > ${#items[@]} )); then
            end=${#items[@]}
        fi

        # Display items for current page
        for ((i=start-1; i<end; i++)); do
            echo -e "${color_option}$((i+1)).${color_reset} ${items[i]}"
        done

        echo -e "\n${color_desc}[n] Next page | [p] Previous page | [b] Back${color_reset}"

        read -rp "Selection: " choice

        case "$choice" in
            [0-9]*)
                if (( choice >= start && choice <= end )); then
                    SELECTION_RESULT=$choice
                    return 0
                else
                    echo "Invalid selection. Please choose a number from the current page."
                fi
                ;;
            [nN])
                if (( current_page < total_pages )); then
                    ((current_page++))
                else
                    echo "Already on the last page."
                fi
                ;;
            [pP])
                if (( current_page > 1 )); then
                    ((current_page--))
                else
                    echo "Already on the first page."
                fi
                ;;
            [bB])
                SELECTION_RESULT=0
                return 0
                ;;
            *)
                echo "Invalid input. Try again."
                ;;
        esac
    done
}

# ===== 7. CORE FUNCTIONALITY (ORIGINAL SCRIPT) =====

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
        read -rp "Enter FULL path to nxmhandler.exe: " nxmhandler_path
        if [ -f "$nxmhandler_path" ]; then
            log_info "Selected nxmhandler.exe: $nxmhandler_path"
            break
        fi
        echo -e "${color_red}File not found!${color_reset} Try again."
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

# Function to show error message, log it, and exit
error_exit() {
    handle_error "$1" true 1
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
    local prefix_path="${steam_root}/steamapps/compatdata/${selected_appid}/pfx"

    if [ ! -d "$prefix_path" ]; then
        end_progress_tracking "$tracker" false
        handle_error "Could not find Proton prefix at: $prefix_path" false
        return 1
    fi

    update_progress "$tracker" 5 20

    # Registry file path
    local reg_file=$(mktemp)
    TEMP_FILES+=("$reg_file")

    # Create registry file content
    cat > "$reg_file" << EOF
Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\Control Panel\Desktop]
"LogPixels"=dword:$(printf "%08x" $selected_scaling)

[HKEY_CURRENT_USER\Software\Wine\X11 Driver]
"LogPixels"=$selected_scaling
EOF

    update_progress "$tracker" 10 20

    # Apply registry changes
    WINEPREFIX="$prefix_path" wine regedit "$reg_file" &>/dev/null
    local result=$?

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
        echo -e "Press any button to continue"
    fi

    end_progress_tracking "$tracker" true
    return 0
}

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

get_non_steam_games() {
    print_section "Fetching Non-Steam Games"
    log_info "Fetching non-Steam games"

    # Check for cached games
    if [ "$(get_config "auto_detect_games" "true")" == "true" ]; then
        local cached_games=$(get_config "detected_games" "")
        if [ -n "$cached_games" ]; then
            log_info "Using cached game list"
            IFS=';' read -ra game_array <<< "$cached_games"
            if [ ${#game_array[@]} -gt 0 ]; then
                echo "Found ${#game_array[@]} cached non-Steam games."
                return 0
            fi
        fi
    fi

    # Start progress tracking
    local tracker=$(start_progress_tracking "Scanning for non-Steam games" 30)

    echo "Scanning for non-Steam games..."
    local protontricks_output
    if ! protontricks_output=$($protontricks_cmd --list 2>&1); then
        end_progress_tracking "$tracker" false
        error_exit "Failed to run protontricks. Check log for details."
    fi

    local games=""
    local count=0
    while IFS= read -r line; do
        if [[ "$line" =~ "Non-Steam shortcut:" ]]; then
            if [[ "$line" =~ \(([0-9]+)\)$ ]]; then
                appid="${BASH_REMATCH[1]}"
                name=$(echo "$line" | sed -E 's/.*Non-Steam shortcut: (.*) \([0-9]+\)$/\1/')
                games+="$appid:$name"$'\n'
                ((count++))
                update_progress "$tracker" "$count" "20"  # Estimate about 20 games
            fi
        fi
    done <<< "$protontricks_output"

    IFS=$'\n' read -d '' -ra game_array <<< "$games"
    end_progress_tracking "$tracker" true

    if [ ${#game_array[@]} -eq 0 ]; then
        error_exit "No non-Steam games found! Make sure you've added non-Steam games to Steam and launched them at least once."
    fi

    # Cache the results
    if [ "$(get_config "auto_detect_games" "true")" == "true" ]; then
        local game_list=""
        for game in "${game_array[@]}"; do
            game_list+="$game;"
        done

        set_config "detected_games" "$game_list"
        log_info "Cached ${#game_array[@]} detected games"
    fi

    echo "Found ${#game_array[@]} non-Steam games."
    return 0
}

get_game_components() {
    local appid="$1"
    case "$appid" in
        22380)
            components=(
                fontsmooth=rgb
                xact
                xact_x64
                d3dx9_43
                d3dx9
                vcrun2022
            )
            ;;
        976620)  # Enderal Special Edition
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
            ;;
        *)
            components=(
                fontsmooth=rgb
                xact
                xact_x64
                vcrun2022
                dotnet6
                dotnet7
                dotnet8
                d3dcompiler_47
                d3dx11_43
                d3dcompiler_43
                d3dx9_43
                d3dx9
                vkd3d
            )
            ;;
    esac
}

# Modified select_game function to allow choosing different games

select_game() {
    log_info "Showing game selection menu"

    # If there's only one game, select it automatically
    if [ ${#game_array[@]} -eq 1 ]; then
        selected_game="${game_array[0]}"
        IFS=':' read -r selected_appid selected_name <<< "$selected_game"
        get_game_components "$selected_appid"
        log_info "Auto-selected only game: $selected_name (AppID: $selected_appid)"
        notify "Selected game: $selected_name" 2
        return 0
    fi

    # Build an array of just the game names for display
    local display_games=()

    for game in "${game_array[@]}"; do
        IFS=':' read -r appid name <<< "$game"
        display_games+=("$name (AppID: $appid)")
    done

    # Show selection menu with the full game list immediately
    print_section "Game Selection"
    echo "Please select a game:"

    select_from_list "Available Non-Steam Games" "${display_games[@]}"
    local choice=$SELECTION_RESULT

    if [ $choice -eq 0 ]; then
        log_info "User canceled game selection"
        return 1
    fi

    selected_game="${game_array[$((choice-1))]}"
    IFS=':' read -r selected_appid selected_name <<< "$selected_game"
    get_game_components "$selected_appid"
    log_info "Selected game: $selected_name (AppID: $selected_appid)"

    # Save as preferred game (for future use in other functions)
    set_config "preferred_game_appid" "$selected_appid"

    notify "Selected game: $selected_name" 2
    return 0
}


# ===== 8. REDESIGNED MENU SYSTEM =====

# Main menu structure
main_menu() {
    while true; do
        print_header

        display_menu "Main Menu" \
            "Mod Organizer Setup" "Set up MO2 with Proton, NXM handler, and dependencies" \
            "TTW Installation" "Download and set up Tale of Two Wastelands tools" \
            "Game-Specific Info" "Fallout NV, Enderal, BG3 Info Here!" \
            "System Utilities" "View logs, check system compatibility" \
            "Exit" "Quit the application"

        local choice=$?

        case $choice in
            1) mo2_setup_menu ;;
            2) ttw_installation_menu ;;
            3) game_specific_menu ;;
            4) system_utilities_menu ;;
            5)
                log_info "User exited application"
                echo -e "\n${color_green}Thank you for using the MO2 Helper!${color_reset}"
                exit 0
                ;;
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
                select_game
                install_proton_dependencies
                # Use pause instead of timed notify
                pause "Basic dependencies installation complete!"
                ;;
            2)
                check_dependencies
                get_non_steam_games
                select_game
                setup_nxm_handler
                pause "NXM handler configured successfully!"
                ;;
            3)
                check_dependencies
                get_non_steam_games
                select_game
                select_dpi_scaling
                apply_dpi_scaling
                pause "DPI scaling applied successfully!"
                ;;
            4) return ;;
        esac
    done
}

# TTW installation submenu
ttw_installation_menu() {
    while true; do
        print_header

        display_menu "Tale of Two Wastelands Setup" \
            "Download Hoolamike" "Download and setup Hoolamike for TTW installation" \
            "Install TTW Dependencies" "Install FNV-specific Proton dependencies for TTW" \
            "Run Hoolamike" "Execute TTW installation with Hoolamike" \
            "View TTW Documentation" "View TTW installation guides and documentation" \
            "Back to Main Menu" "Return to the main menu"

        local choice=$?

        case $choice in
            1) download_hoolamike ;;
            2) install_fnv_dependencies ;;
            3) run_hoolamike "tale-of-two-wastelands" ;;
            4) view_ttw_docs ;;
            5) return ;;
        esac
    done
}

# Function to find game compatdata for a specific game
find_game_compatdata() {
    local appid="$1"
    local steam_root="$2"
    local steam_paths=("$steam_root")

    # Check libraryfolders.vdf for additional Steam library paths
    libraryfolders="$steam_root/steamapps/libraryfolders.vdf"
    if [ -f "$libraryfolders" ]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && steam_paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    # Search for compatdata in all Steam libraries
    for path in "${steam_paths[@]}"; do
        compatdata_path="$path/steamapps/compatdata/$appid"
        if [ -d "$compatdata_path" ]; then
            echo "$compatdata_path"
            return 0
        fi
    done

    # Return empty if not found
    echo ""
    return 1
}

# Consolidated function for finding game-specific compatdata
find_enderal_compatdata() {
    find_game_compatdata "976620" "$(get_steam_root)"
}

find_fnv_compatdata() {
    find_game_compatdata "22380" "$(get_steam_root)"
}

find_bg3_compatdata() {
    find_game_compatdata "1086940" "$(get_steam_root)"
}

# Generate game advice text
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
    else
        echo -e "\n${color_yellow}(Skip FNV advice: not installed or not run yet)${color_reset}"
        log_info "Skipped FNV advice (no compatdata found)"
    fi

    # Enderal advice
    if [ -n "$enderal_compatdata" ]; then
        echo -e "\nFor Enderal modlists:"
        echo -e "  ${color_blue}STEAM_COMPAT_DATA_PATH=\"$enderal_compatdata\" %command%${color_reset}"
        log_info "Provided Enderal advice (found compatdata)"
    else
        echo -e "\n${color_yellow}(Skip Enderal advice: not installed or not run yet)${color_reset}"
        log_info "Skipped Enderal advice (no compatdata found)"
    fi

    pause "Press any key to continue..."
}

# Individual game menus
fnv_menu() {
    # Set up for Fallout New Vegas (AppID 22380)
    selected_appid="22380"
    selected_name="Fallout New Vegas"

    # Show launch advice specific to FNV
    print_section "Fallout New Vegas Options"
    local steam_root=$(get_steam_root)
    local fnv_compatdata=$(find_game_compatdata "22380" "$steam_root")

    if [ -n "$fnv_compatdata" ]; then
        echo -e "Recommended launch options for Fallout New Vegas:"
        echo -e "${color_blue}STEAM_COMPAT_DATA_PATH=\"$fnv_compatdata\" %command%${color_reset}"
        log_info "Displayed FNV launch options"
    else
        echo -e "${color_yellow}Fallout New Vegas has not been run yet or is not installed.${color_reset}"
        echo -e "Please run the game at least once through Steam before using these options."
        log_warning "FNV compatdata not found"
    fi

    pause "Press any key to continue..."
}

enderal_menu() {
    # Set up for Enderal SE (AppID 976620)
    selected_appid="976620"
    selected_name="Enderal Special Edition"

    # Show launch advice specific to Enderal
    print_section "Enderal Special Edition Options"
    local steam_root=$(get_steam_root)
    local enderal_compatdata=$(find_game_compatdata "976620" "$steam_root")

    if [ -n "$enderal_compatdata" ]; then
        echo -e "Recommended launch options for Enderal Special Edition:"
        echo -e "${color_blue}STEAM_COMPAT_DATA_PATH=\"$enderal_compatdata\" %command%${color_reset}"
        log_info "Displayed Enderal launch options"
    else
        echo -e "${color_yellow}Enderal has not been run yet or is not installed.${color_reset}"
        echo -e "Please run the game at least once through Steam before using these options."
        log_warning "Enderal compatdata not found"
    fi

    pause "Press any key to continue..."
}

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

# ===== 9. TTW INTEGRATION =====

# Find a specific game directory in Steam libraries
find_game_directory() {
    local game_name="$1"
    local steam_root="$2"
    local steam_paths=("$steam_root")

    log_info "Looking for game directory: $game_name"

    # Get additional library paths from libraryfolders.vdf
    local libraryfolders="$steam_root/steamapps/libraryfolders.vdf"
    if [ -f "$libraryfolders" ]; then
        while read -r line; do
            [[ "$line" == *\"path\"* ]] && steam_paths+=("$(echo "$line" | awk -F'"' '{print $4}')")
        done < "$libraryfolders"
    fi

    # Search through all steam libraries
    for path in "${steam_paths[@]}"; do
        local candidate="$path/steamapps/common/$game_name"
        if [ -d "$candidate" ]; then
            log_info "Found game directory: $candidate"
            echo "$candidate"
            return 0
        fi
    done

    log_warning "Could not find game directory: $game_name"
    return 1
}

# Check for dependencies needed for downloading
check_download_dependencies() {
    log_info "Checking download dependencies"

    local missing_deps=()

    if ! command_exists curl; then
        missing_deps+=("curl")
    fi

    if ! command_exists jq; then
        missing_deps+=("jq")
    fi

    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${color_yellow}Missing required dependencies: ${missing_deps[*]}${color_reset}"
        echo -e "Please install them with:"
        echo -e "${color_blue}sudo apt install ${missing_deps[*]}${color_reset}"
        log_warning "Missing dependencies: ${missing_deps[*]}"
        return 1
    fi

    log_info "All download dependencies are installed"
    return 0
}

# Generate Hoolamike configuration file
generate_hoolamike_config() {
    log_info "Generating hoolamike.yaml config"
    local config_path="$HOME/Hoolamike/hoolamike.yaml"

    # Find game directories
    local steam_root=$(get_steam_root)
    local fallout3_dir=$(find_game_directory "Fallout 3 goty" "$steam_root")
    local fnv_dir=$(find_game_directory "Fallout New Vegas" "$steam_root")

    # Find Fallout New Vegas compatdata
    local fnv_compatdata=$(find_game_compatdata "22380" "$steam_root")
    local userprofile_path=""

    if [ -n "$fnv_compatdata" ]; then
        userprofile_path="${fnv_compatdata}/pfx/drive_c/users/steamuser/Documents/My Games/FalloutNV/"
        log_info "Found FNV compatdata userprofile path: $userprofile_path"
    else
        log_warning "FNV compatdata not found"
    fi

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
    root_directory: "${fallout3_dir:-/path/to/Fallout 3 goty}"
  FalloutNewVegas:
    root_directory: "${fnv_dir:-/path/to/Fallout New Vegas}"

fixup:
  game_resolution: 2560x1440

extras:
  tale_of_two_wastelands:
    path_to_ttw_mpi_file: "./Tale of Two Wastelands 3.3.3b.mpi"
    variables:
      DESTINATION: "./TTW_Output"
      USERPROFILE: "${userprofile_path:-/path/to/steamapps/compatdata/22380/pfx/drive_c/users/steamuser/Documents/My Games/FalloutNV/}"
EOF

    log_info "hoolamike.yaml created at $config_path"
    echo -e "\n${color_green}Generated hoolamike.yaml with detected paths:${color_reset}"
    echo -e "Fallout 3: ${fallout3_dir:-Not found}"
    echo -e "Fallout NV: ${fnv_dir:-Not found}"
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

# Check if TTW is already installed
check_ttw_installation() {
    local hoolamike_dir="$HOME/Hoolamike"
    local ttw_output_dir="$hoolamike_dir/TTW_Output"

    if [ -d "$ttw_output_dir" ] && [ -f "$ttw_output_dir/TTW_Data/TTW_Main.esm" ]; then
        return 0  # TTW is installed
    else
        return 1  # TTW is not installed
    fi
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

# Enhanced TTW installation menu
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
            "Download Hoolamike" "Download and setup Hoolamike for TTW installation" \
            "Install FNV Dependencies" "Install Fallout New Vegas Proton dependencies" \
            "Run TTW Installation" "Execute TTW installation with Hoolamike" \
            "View TTW Documentation" "View TTW installation guides and documentation" \
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
                install_fnv_dependencies
                pause "Press any key to continue..."
                ;;
            3)
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
            4)
                view_ttw_docs
                ;;
            5)
                return
                ;;
        esac
    done
}

# ===== 10. SCRIPT INITIALIZATION ======

# Initialize
setup_logging
create_default_config
load_cached_values
log_info "Starting MO2 Helper version $SCRIPT_VERSION"
log_system_info

# Welcome message
print_header
echo -e "Welcome to the Mod Organizer 2 Linux Helper!"
echo -e "This script will help you set up and configure Mod Organizer 2 for Linux."
echo -e "\nPress any key to start..."
read -n 1

# Check for updates if enabled
if [ "$(get_config "check_updates" "true")" == "true" ]; then
    check_for_updates
fi

# Main program loop
main_menu

# This point should never be reached
exit 0
