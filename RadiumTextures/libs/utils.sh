#!/bin/bash

# --- Utility Functions ---

# Set open file limit to avoid "too many open files" errors
set_file_limits() {
    echo "Setting file descriptor limits to avoid 'too many open files' errors..."
    # Try to increase the file descriptor limit
    if ! ulimit -n 100000 2>/dev/null; then
        echo "Warning: Failed to set ulimit -n to 100000. Current limit: $(ulimit -n)"
        echo "This may cause 'too many open files' errors during extraction."
        echo "You might need to run with sudo or adjust system limits in /etc/security/limits.conf"
    else
        echo "Successfully set file descriptor limit to $(ulimit -n)"
    fi
}

# Improved Progress Bar Function
better_progress_bar() {
    local current=$1
    local total=$2
    local width=50
    local title="${3:-Progress}"

    # Calculate percentage and filled width
    local pct=0
    if [ "$total" -gt 0 ]; then
        pct=$((current * 100 / total))
    fi
    local filled=0
    if [ "$total" -gt 0 ]; then
        filled=$((width * current / total))
    fi

    # Create the bar
    local bar=""
    if [ "$filled" -gt 0 ]; then
        bar=$(printf '=%.0s' $(seq 1 $filled))
    fi
    local space=""
    if [ "$width" -gt "$filled" ]; then
        space=$(printf ' %.0s' $(seq 1 $((width - filled))))
    fi

    # Print the bar with a clean format and clear the line first
    printf "\\033[K%-15s [%s%s] %3d%% (%d/%d)\\r" "$title:" "$bar" "$space" "$pct" "$current" "$total"
}

# Update progress function
update_progress() {
    local CURRENT="${1:-0}"
    local TOTAL="${2:-100}"

    # Ensure variables are integers
    CURRENT=$(($CURRENT + 0))
    TOTAL=$(($TOTAL + 0))

    # Prevent division by zero
    if [ "$TOTAL" -le 0 ]; then
        TOTAL=100
    fi

    # Calculate percentage
    local PERCENT=0
    if [ "$CURRENT" -ge 0 ] && [ "$TOTAL" -gt 0 ]; then
        PERCENT=$((CURRENT * 100 / TOTAL))
    fi

    # Sanity check on percentage
    if [ "$PERCENT" -lt 0 ]; then
        PERCENT=0
    fi
    if [ "$PERCENT" -gt 100 ]; then
        PERCENT=100
    fi

    better_progress_bar "$PERCENT" 100 "VRAMr Progress"
    PROGRESS="$PERCENT"
}

# Flush Function - Forces disk writes to complete
flush() {
    sync
    sleep 1
}

# Create atomic increment function - thread-safe counter
atomic_increment() {
    local lockfile="$1.lock"
    local increment_val="${2:-1}"

    (
        flock -x 200
        current=$(cat "$1" 2>/dev/null || echo 0)
        echo $((current + increment_val)) > "$1"
    ) 200>"$lockfile"
}

generate_mod_order_csv() {
    if [ -f "$VRAMR_TEMP/ActiveModListOrder.csv" ]; then
        echo "Found existing mod order CSV at $VRAMR_TEMP/ActiveModListOrder.csv"
        return 0
    fi

    echo "No mod order CSV found. Generating one directly..."
    local output_csv="$VRAMR_TEMP/ActiveModListOrder.csv"
    local log_csv="$VRAMR_TEMP/logfiles/csv_generation.log"
    mkdir -p "$(dirname "$log_csv")"
    > "$log_csv"

    # Check if we have a valid mods directory
    if [ -z "$MODS_DIR" ] || [ ! -d "$MODS_DIR" ]; then
        echo "WARNING: Mods directory not found or not specified: $MODS_DIR" | tee -a "$log_csv"
        return 1
    fi

    # Locate modlist.txt
    local modlist_file=""
    local base_dir=$(dirname "$MODS_DIR")
    local profile_name=$(basename "$base_dir")

    # Try standard MO2 path first
    modlist_file="$base_dir/profiles/$profile_name/modlist.txt"

    # Check if file exists
    if [ ! -f "$modlist_file" ]; then
        echo "WARNING: Could not find modlist.txt at expected path: $modlist_file" | tee -a "$log_csv"

        # Search in profiles directory
        if [ -d "$base_dir/profiles" ]; then
            echo "Searching for modlist.txt in profiles directory..." | tee -a "$log_csv"

            # Find first modlist.txt in any profile
            for profile_dir in "$base_dir"/profiles/*/; do
                if [ -d "$profile_dir" ]; then
                    if [ -f "$profile_dir/modlist.txt" ]; then
                        modlist_file="$profile_dir/modlist.txt"
                        echo "Found modlist.txt at: $modlist_file" | tee -a "$log_csv"
                        break
                    fi
                fi
            done
        fi
    fi

    # Final check for modlist file
    if [ ! -f "$modlist_file" ]; then
        echo "ERROR: Could not find modlist.txt file. Cannot generate mod order CSV." | tee -a "$log_csv"
        return 1
    fi

    echo "Using modlist file: $modlist_file" | tee -a "$log_csv"

    # Create CSV header
    echo "ModActivationIndex,ModName,IsModActive,ModPath" > "$output_csv"

    # Pre-cache all mod directories (major optimization)
    local mod_dirs=()
    if [ -d "$MODS_DIR" ]; then
        echo "Caching mod directories from: $MODS_DIR..." | tee -a "$log_csv"
        while IFS= read -r -d '' dir; do
            if [ -d "$dir" ]; then
                mod_dirs+=("$dir")
            fi
        done < <(find "$MODS_DIR" -maxdepth 1 -type d -print0)
    fi
    echo "Cached ${#mod_dirs[@]} mod directories" | tee -a "$log_csv"

    # Read modlist.txt and extract enabled mods
    local temp_modlist=$(mktemp)
    tr -d '\r' < "$modlist_file" > "$temp_modlist"

    # Extract enabled mods and store in array
    local mod_names=()
    while IFS= read -r line; do
        # Check if it's an enabled mod (starts with +)
        if [[ "$line" == +* ]]; then
            # Remove the + prefix and trim whitespace
            local mod_name=$(echo "${line:1}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

            # Skip empty lines and separator lines
            if [[ -n "$mod_name" && "$mod_name" != "---"* ]]; then
                mod_names+=("$mod_name")
            fi
        fi
    done < "$temp_modlist"
    rm -f "$temp_modlist"

    # Process mods in reverse order (bottom-up = higher priority)
    local mod_count=${#mod_names[@]}
    echo "Processing $mod_count mods in reversed order (bottom-up priority)..." | tee -a "$log_csv"

    # Process in reverse order (highest priority first = lowest index)
    local index=0
    for ((i=${#mod_names[@]}-1; i>=0; i--)); do
        local mod_name="${mod_names[i]}"

        # Try to find matching directory efficiently
        local mod_dir=""
        local mod_name_lower=$(echo "$mod_name" | tr '[:upper:]' '[:lower:]')

        # Fast matching using pre-cached directories
        for dir in "${mod_dirs[@]}"; do
            local dir_basename=$(basename "$dir")
            local dir_basename_lower=$(echo "$dir_basename" | tr '[:upper:]' '[:lower:]')

            # Exact match (case-insensitive)
            if [ "$dir_basename_lower" = "$mod_name_lower" ]; then
                mod_dir="$dir"
                break
            fi
        done

        # Add to CSV with or without path
        if [ -n "$mod_dir" ]; then
            echo "$index,$mod_name,true,$mod_dir" >> "$output_csv"
            if [ "$VERBOSE" -eq 1 ]; then
                echo "  Added mod [$index]: $mod_name -> $mod_dir" | tee -a "$log_csv"
            fi
        else
            echo "$index,$mod_name,true,\"\"" >> "$output_csv"
            if [ "$VERBOSE" -eq 1 ]; then
                echo "  Added mod [$index]: $mod_name (no matching directory found)" | tee -a "$log_csv"
            fi
        fi

        # Increment index
        index=$((index + 1))
    done

    # Verify CSV was created successfully
    if [ -f "$output_csv" ]; then
        local csv_entries=$(($(wc -l < "$output_csv") - 1))
        if [ $csv_entries -gt 0 ]; then
            echo "Successfully created CSV with $csv_entries entries" | tee -a "$log_csv"
            echo "CSV file: $output_csv"
            echo "DEBUG: CSV Found. Will attempt prioritized copy."
            return 0
        else
            echo "ERROR: CSV file has no entries (only header)" | tee -a "$log_csv"
        fi
    else
        echo "ERROR: CSV file was not created" | tee -a "$log_csv"
    fi

    echo "DEBUG: CSV NOT Found. Will use simple parallel copy."
    return 1
}
