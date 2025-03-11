#!/bin/bash
# -------------------------------------------------------------------
# error.sh
# Error handling functions for MO2 Helper
# -------------------------------------------------------------------

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

# Function to show error message, log it, and exit
error_exit() {
    handle_error "$1" true 1
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
