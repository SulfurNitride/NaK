#!/bin/bash
# -------------------------------------------------------------------
# logging.sh
# Logging system for MO2 Helper
# -------------------------------------------------------------------

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
