#!/bin/bash
# -------------------------------------------------------------------
# ui.sh
# User interface functions for MO2 Helper
# -------------------------------------------------------------------

# Clear screen and print header
# Clear screen and print header
print_header() {
    clear
    echo -e "${color_title}=====================================${color_reset}"
    echo -e "${color_title}     NaK - Linux Modding Helper     ${color_reset}"
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
    local spinstr='-\|/'  # Simple ASCII spinner instead of Unicode characters

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
