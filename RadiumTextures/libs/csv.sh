#!/bin/bash

# Priority-Correct MO2 CSV Generator (Reversed Order)
# This version correctly assigns priority values so that mods at the bottom of modlist.txt
# have higher priority (lower index numbers) in the CSV file

# Configuration variables
GAME_DIR=""
MODS_DIR=""
OUTPUT_DIR=""
MODLIST_FILE=""  # Will be constructed based on MODS_DIR
LOG_FILE=""

# Function to log messages
log_message() {
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] $1"
    if [ -n "$LOG_FILE" ]; then
        echo "[$timestamp] $1" >> "$LOG_FILE"
    fi
}

# Display usage information
show_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --game-dir PATH     Set Skyrim Data directory"
    echo "  --mods-dir PATH     Set mods directory"
    echo "  --output-dir PATH   Set output directory"
    echo "  --modlist-file PATH Directly specify the modlist.txt file (optional)"
    echo "  -h, --help          Show this help message"
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        key="$1"
        case $key in
            --game-dir)
            GAME_DIR="$2"; shift; shift ;;
            --mods-dir)
            MODS_DIR="$2"; shift; shift ;;
            --output-dir)
            OUTPUT_DIR="$2"; shift; shift ;;
            --modlist-file)
            MODLIST_FILE="$2"; shift; shift ;;
            -h|--help)
            show_usage; exit 0 ;;
            *)
            echo "Unknown option: $1" >&2
            show_usage; exit 1 ;;
        esac
    done
}

# Ask for input if not provided via command line
get_user_paths() {
    if [ -z "$GAME_DIR" ]; then
        read -e -p "Enter path to Skyrim Data directory: " GAME_DIR
    fi

    # Verify Skyrim Data directory
    if [ ! -d "$GAME_DIR" ]; then
        echo "ERROR: Skyrim Data directory not found: $GAME_DIR"
        exit 1
    fi

    if [ -z "$MODS_DIR" ]; then
        read -e -p "Enter path to Mods directory: " MODS_DIR
    fi

    # Verify Mods directory
    if [ ! -d "$MODS_DIR" ]; then
        echo "WARNING: Mods directory not found: $MODS_DIR"
    fi

    if [ -z "$OUTPUT_DIR" ]; then
        read -e -p "Enter path for output directory: " OUTPUT_DIR
    fi

    # Expand tilde if present
    OUTPUT_DIR="${OUTPUT_DIR/#\~/$HOME}"

    # Ensure output directory exists
    mkdir -p "$OUTPUT_DIR"

    # Create log file
    LOG_FILE="$OUTPUT_DIR/csv_generator.log"
    > "$LOG_FILE"

    # Set default modlist.txt path if not specified
    if [ -z "$MODLIST_FILE" ]; then
        # Try to construct the path based on MO2 conventions
        local BASE_DIR=$(dirname "$MODS_DIR")
        local MO2_PROFILE=$(basename "$BASE_DIR")

        # MO2 structure: .../ModlistName/mods and .../ModlistName/profiles/ModlistName/modlist.txt
        MODLIST_FILE="$BASE_DIR/profiles/$(basename "$BASE_DIR")/modlist.txt"

        log_message "Auto-detected modlist path: $MODLIST_FILE"

        # Verify if it exists
        if [ ! -f "$MODLIST_FILE" ]; then
            log_message "WARNING: Auto-detected modlist.txt not found: $MODLIST_FILE"

            # Try alternate locations
            if [ -d "$BASE_DIR/profiles" ]; then
                log_message "Searching for modlist.txt in profiles directory..."

                # Find the first modlist.txt file in any profile
                for PROFILE_DIR in "$BASE_DIR"/profiles/*/; do
                    if [ -d "$PROFILE_DIR" ]; then
                        if [ -f "$PROFILE_DIR/modlist.txt" ]; then
                            MODLIST_FILE="$PROFILE_DIR/modlist.txt"
                            log_message "Found modlist.txt in profile: $MODLIST_FILE"
                            break
                        fi
                    fi
                done
            fi
        fi
    fi

    # Final verification of the modlist file
    if [ ! -f "$MODLIST_FILE" ]; then
        log_message "ERROR: modlist.txt file not found: $MODLIST_FILE"
        log_message "Please specify the correct path to modlist.txt with --modlist-file"
        exit 1
    fi

    log_message "Paths configured:"
    log_message "  Game Directory: $GAME_DIR"
    log_message "  Mods Directory: $MODS_DIR"
    log_message "  Output Directory: $OUTPUT_DIR"
    log_message "  Modlist File: $MODLIST_FILE"
}

# Generate CSV from modlist.txt
generate_csv() {
    local output_csv="$OUTPUT_DIR/ActiveModListOrder.csv"
    log_message "Generating CSV: $output_csv"

    # Check that file exists
    if [ ! -f "$MODLIST_FILE" ]; then
        log_message "ERROR: Modlist file not found: $MODLIST_FILE"
        return 1
    fi

    # Create CSV header
    echo "ModActivationIndex,ModName,IsModActive,ModPath" > "$output_csv"

    # Create a temporary file with Unix line endings
    TEMP_FILE=$(mktemp)
    tr -d '\r' < "$MODLIST_FILE" > "$TEMP_FILE"

    # Count total lines and enabled mods
    local total_lines=$(wc -l < "$TEMP_FILE")
    local enabled_count=$(grep -c '^\+' "$TEMP_FILE" || echo 0)
    log_message "Total lines in modlist: $total_lines"
    log_message "Enabled mods: $enabled_count"

    # Extract all enabled mods to a temporary array
    log_message "Extracting enabled mods..."
    local TEMP_MODS_FILE=$(mktemp)
    grep '^\+' "$TEMP_FILE" | while read -r line; do
        # Remove the + prefix and trim whitespace
        local mod_name=$(echo "$line" | sed 's/^+//' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

        # Skip empty lines and separator lines
        if [[ -n "$mod_name" && "$mod_name" != "---"* ]]; then
            echo "$mod_name" >> "$TEMP_MODS_FILE"
        fi
    done

    # Count enabled mods for indexing
    local MOD_COUNT=$(wc -l < "$TEMP_MODS_FILE")
    log_message "Found $MOD_COUNT enabled mods to process"

    # Process mods in REVERSE order (from bottom to top)
    log_message "Processing mods in reversed order (bottom-up priority)..."
    local index=0
    tac "$TEMP_MODS_FILE" | while read -r mod_name; do
        # Try to find matching directory
        local mod_dir=""

        # Check for direct match
        if [ -d "$MODS_DIR/$mod_name" ]; then
            mod_dir="$MODS_DIR/$mod_name"
        else
            # Try case-insensitive matching
            for dir in "$MODS_DIR"/*; do
                if [ -d "$dir" ]; then
                    local dir_name=$(basename "$dir")
                    if [ "${dir_name,,}" = "${mod_name,,}" ]; then
                        mod_dir="$dir"
                        break
                    fi
                fi
            done

            # If still not found, try partial matching
            if [ -z "$mod_dir" ]; then
                for dir in "$MODS_DIR"/*; do
                    if [ -d "$dir" ]; then
                        local dir_name=$(basename "$dir")
                        if [[ "${dir_name,,}" == *"${mod_name,,}"* || "${mod_name,,}" == *"${dir_name,,}"* ]]; then
                            mod_dir="$dir"
                            break
                        fi
                    fi
                done
            fi
        fi

        # Add to CSV with or without path
        if [ -n "$mod_dir" ]; then
            echo "$index,$mod_name,true,$mod_dir" >> "$output_csv"
            log_message "  Added mod [$index]: $mod_name -> $mod_dir"
        else
            echo "$index,$mod_name,true,\"\"" >> "$output_csv"
            log_message "  Added mod [$index]: $mod_name (no matching directory found)"
        fi

        # Increment index
        index=$((index + 1))
    done

    # Clean up
    rm -f "$TEMP_FILE" "$TEMP_MODS_FILE"

    # Check if CSV was created with entries
    if [ -f "$output_csv" ]; then
        local csv_entries=$(($(wc -l < "$output_csv") - 1))
        if [ $csv_entries -gt 0 ]; then
            log_message "Successfully created CSV with $csv_entries entries"
            log_message "CSV file: $output_csv"
            log_message "Priority order is correct (mods at bottom of modlist.txt have lower indexes)"
            return 0
        else
            log_message "ERROR: CSV file has no entries (only header)"
            return 1
        fi
    else
        log_message "ERROR: CSV file was not created"
        return 1
    fi
}

# Main function
main() {
    echo "Priority-Correct MO2 CSV Generator"
    echo "================================="

    parse_arguments "$@"
    get_user_paths

    if generate_csv; then
        echo "✅ CSV generated successfully at: $OUTPUT_DIR/ActiveModListOrder.csv"
        echo "  Priority order is correct: mods at bottom of list have lower indexes (higher priority)"
        exit 0
    else
        echo "❌ CSV generation failed. Check log file: $LOG_FILE"
        exit 1
    fi
}

# Run main function
main "$@"
