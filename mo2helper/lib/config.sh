#!/bin/bash
# -------------------------------------------------------------------
# config.sh
# Configuration management for MO2 Helper
# -------------------------------------------------------------------

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
