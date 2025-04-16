#!/bin/bash

# --- Enhanced BSA Extraction using hoolamike with CSV Priority Order ---
# Modified extract_bsa_files function to respect mod load order from CSV
extract_bsa_files() {
    echo "$(date) Starting BSA extraction with hoolamike..." >> "$LOG_FILE"

    # Temporarily limit threads for BSA extraction to half of nproc
    local original_thread_count=$THREAD_COUNT
    local bsa_thread_limit=$((DEFAULT_THREADS / 2)) # Use DEFAULT_THREADS calculated earlier
    # Ensure at least 1 thread
    if [ "$bsa_thread_limit" -lt 1 ]; then
        bsa_thread_limit=1
    fi
    # Ask user about thread count for BSA extraction
    echo "--------------------------------------------------"
    echo "BSA Extraction Thread Configuration"
    echo "Total system threads detected: $DEFAULT_THREADS"
    echo "Recommended threads for BSA extraction (half): $bsa_thread_limit"
    read -t 10 -p "Press Enter to use $bsa_thread_limit threads, or enter a number (e.g., 4): [${bsa_thread_limit}] " user_bsa_threads

    # Validate user input
    if [[ -n "$user_bsa_threads" && "$user_bsa_threads" =~ ^[1-9][0-9]*$ ]]; then
        bsa_thread_limit="$user_bsa_threads"
        echo "Using $bsa_thread_limit threads for BSA extraction (User specified)."
    elif [[ -z "$user_bsa_threads" ]]; then
        echo "No input received, using recommended $bsa_thread_limit threads."
    else
        echo "Invalid input '$user_bsa_threads'. Using recommended $bsa_thread_limit threads."
    fi
    echo "--------------------------------------------------"

    echo "Starting BSA extraction using hoolamike with $bsa_thread_limit parallel processes..."
    update_progress 25

    # Verify hoolamike is available
    if [ -z "$HOOLAMIKE_CMD" ] || [ ! -x "$HOOLAMIKE_CMD" ]; then
        echo "ERROR: Hoolamike command not found or not executable: $HOOLAMIKE_CMD" | tee -a "$LOG_FILE"
        return 1
    fi

    # Array to store all extraction PIDs for waiting
    EXTRACT_PIDS=()
    RUNNING_EXTRACTIONS=0

    # First, generate the mod order CSV if it doesn't exist
    # This now uses our inline function that's much faster
    generate_mod_order_csv
    local HAS_MOD_ORDER_CSV=0
    if [ -f "$VRAMR_TEMP/ActiveModListOrder.csv" ]; then
        HAS_MOD_ORDER_CSV=1
        echo "Found mod order CSV. Will extract BSA files respecting mod load order." | tee -a "$LOG_FILE"
    else
        echo "No mod order CSV found. Will extract BSA files in the order they are found." | tee -a "$LOG_FILE"
    fi

    # Create a directory to track extraction progress
    local EXTRACTION_LOG="$VRAMR_TEMP/logfiles/bsa_extraction.log"
    > "$EXTRACTION_LOG"
    echo "BSA extraction started at $(date)" >> "$EXTRACTION_LOG"

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" extract_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    # Create a list of BSA files
    local BSA_FILES_LIST=$(mktemp --tmpdir="$TEMP_DIR" bsa_files.XXXXXX)
    > "$BSA_FILES_LIST"

    # Function to extract a single BSA file
    extract_single_bsa() {
        local BSA_FILE="$1"
        local OUTPUT_DIR="$2"
        local PROGRESS_FILE="$3"
        local EXTRACTION_LOG="$4"
        local BSA_NAME=$(basename "$BSA_FILE")
        local ORIGINAL_DIR=$(pwd) # Store original directory

        # Create a unique subdirectory in TEMP_DIR for temporary extraction
        local UNIQUE_EXTRACT_DIR=$(mktemp -d --tmpdir="$TEMP_DIR" bsa_extract_XXXXXX)
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to create temporary directory for $BSA_NAME" | tee -a "$EXTRACTION_LOG"
            atomic_increment "$PROGRESS_FILE" # Increment progress even on failure
            return 1
        fi

        echo "Extracting BSA: $BSA_NAME into $UNIQUE_EXTRACT_DIR" >> "$EXTRACTION_LOG"

        # Change to the unique directory
        cd "$UNIQUE_EXTRACT_DIR" || {
            echo "ERROR: Failed to cd into $UNIQUE_EXTRACT_DIR for $BSA_NAME" | tee -a "$EXTRACTION_LOG"
            rmdir "$UNIQUE_EXTRACT_DIR" # Clean up dir if cd failed
            cd "$ORIGINAL_DIR"
            atomic_increment "$PROGRESS_FILE"
            return 1
        }

        # Run hoolamike to extract the BSA into the current directory
        if [ "$VERBOSE" -eq 1 ]; then
            # Verbose output - Redirect to extraction log
            echo "VERBOSE: Running hoolamike for $BSA_NAME..." >> "$EXTRACTION_LOG"
            "$HOOLAMIKE_CMD" archive extract-all "$BSA_FILE" >> "$EXTRACTION_LOG" 2>&1
        else
            # Quiet output - Redirect to /dev/null
            "$HOOLAMIKE_CMD" archive extract-all "$BSA_FILE" > /dev/null 2>&1
        fi
        local HOOLAMIKE_EXIT_CODE=$?

        # Change back to original directory immediately after extraction
        cd "$ORIGINAL_DIR" || {
            echo "CRITICAL ERROR: Failed to cd back to original directory from $UNIQUE_EXTRACT_DIR" | tee -a "$EXTRACTION_LOG"
            # Cannot reliably clean up UNIQUE_EXTRACT_DIR here
            atomic_increment "$PROGRESS_FILE"
            return 1 # Indicate failure
        }

        if [ "$HOOLAMIKE_EXIT_CODE" -ne 0 ]; then
            echo "ERROR: Failed to extract $BSA_NAME (hoolamike exit code: $HOOLAMIKE_EXIT_CODE)" | tee -a "$EXTRACTION_LOG"
        else
            # Only copy .dds files to the output directory if extraction succeeded
            local extracted_textures_dir="$UNIQUE_EXTRACT_DIR/textures"
            if [ -d "$extracted_textures_dir" ]; then
                # Create target base directory if it doesn't exist
                mkdir -p "$OUTPUT_DIR/textures"

                # Find and copy all .dds files, preserving structure
                find "$extracted_textures_dir" -type f -iname "*.dds" -print0 | \
                while IFS= read -r -d $'\0' dds_file; do
                    # Get relative path from the *extracted* textures directory
                    local rel_path="${dds_file#$extracted_textures_dir/}"
                    # Create the full target directory path
                    local target_dir="$OUTPUT_DIR/textures/$(dirname "$rel_path")"
                    # Handle case where dirname is '.'
                    if [[ "$target_dir" == "$OUTPUT_DIR/textures/." ]]; then
                         target_dir="$OUTPUT_DIR/textures"
                    fi
                    mkdir -p "$target_dir"
                    # Copy the file
                    cp "$dds_file" "$target_dir/"
                done

                local DDS_COUNT=$(find "$extracted_textures_dir" -type f -iname "*.dds" | wc -l)
                echo "Copied $DDS_COUNT .dds files from $BSA_NAME" >> "$EXTRACTION_LOG"
            else
                echo "No textures directory found in extracted contents of $BSA_NAME" >> "$EXTRACTION_LOG"
            fi
        fi

        # Clean up the unique extraction directory
        rm -rf "$UNIQUE_EXTRACT_DIR"

        # Update progress atomically
        atomic_increment "$PROGRESS_FILE"
    }

    # Monitor extract progress
    monitor_extract_progress() {
        local total=$1
        local progress_file=$2

        while true; do
            sleep 1
            local current=$(cat "$progress_file" 2>/dev/null || echo 0)

            # Check if we're done
            if [ "$current" -ge "$total" ]; then
                better_progress_bar "$current" "$total" "BSA Extract"
                break
            fi

            # Check if parent process is still running
            if ! ps -p $$ > /dev/null; then
                break
            fi

            better_progress_bar "$current" "$total" "BSA Extract"
        done
        echo "" # New line after progress bar
    }

    # Process BSA files according to mod order if CSV is available
    if [ "$HAS_MOD_ORDER_CSV" -eq 1 ]; then
        # First add game directory BSAs (lowest priority)
        echo "Adding game directory BSA files (lowest priority)..."
        find "$GAME_DIR" -type f -name "*.bsa" 2>/dev/null | while read -r bsa_file; do
            if [ -f "$bsa_file" ]; then
                echo "$bsa_file" >> "$BSA_FILES_LIST"
                if [ "$VERBOSE" -eq 1 ]; then
                    echo "Found BSA (Game): $bsa_file"
                fi
            fi
        done

        # Now process BSAs according to mod order CSV (higher priority overwrites lower)
        echo "Processing mod BSA files according to load order..."

        # Skip header line and process in forward order (lower index = higher priority)
        # Major optimization: use a faster way to parse the CSV file
        # Read the whole file, skip first line, and process remaining lines
        if [ -f "$VRAMR_TEMP/ActiveModListOrder.csv" ]; then
            tail -n +2 "$VRAMR_TEMP/ActiveModListOrder.csv" | while IFS=, read -r index mod_name active mod_path; do
                # Remove quotes from mod_path if present
                mod_path="${mod_path%\"}"
                mod_path="${mod_path#\"}"
                mod_path="${mod_path%\'}"
                mod_path="${mod_path#\'}"

                # Trim leading/trailing whitespace
                mod_path="$(echo "$mod_path" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

                if [ -d "$mod_path" ]; then
                    # Find all BSA files in this mod directory
                    find "$mod_path" -type f -name "*.bsa" 2>/dev/null | while read -r bsa_file; do
                        if [ -f "$bsa_file" ]; then
                            echo "$bsa_file" >> "$BSA_FILES_LIST"
                            if [ "$VERBOSE" -eq 1 ]; then
                                echo "Found BSA (Mod priority $index): $bsa_file"
                            fi
                        fi
                    done
                fi
            done
        fi
    else
        # Fallback mode: Find BSA files in different locations without respecting order
        echo "Using fallback BSA discovery mode (no load order)..."

        # Find game directory BSAs
        if [ -d "$GAME_DIR" ]; then
            echo "Searching for BSA files in: $GAME_DIR (Game)"
            find "$GAME_DIR" -type f -name "*.bsa" 2>/dev/null | while read -r bsa_file; do
                if [ -f "$bsa_file" ]; then
                    echo "$bsa_file" >> "$BSA_FILES_LIST"
                    if [ "$VERBOSE" -eq 1 ]; then
                        echo "Found BSA (Game): $bsa_file"
                    fi
                fi
            done
        fi

        # Find BSA files in mods directory (no specific order)
        if [ -d "$MODS_DIR" ]; then
            echo "Searching for BSA files in: $MODS_DIR (Mods)"
            find "$MODS_DIR" -type f -name "*.bsa" 2>/dev/null | while read -r bsa_file; do
                if [ -f "$bsa_file" ]; then
                    echo "$bsa_file" >> "$BSA_FILES_LIST"
                    if [ "$VERBOSE" -eq 1 ]; then
                        echo "Found BSA (Mod): $bsa_file"
                    fi
                fi
            done
        fi
    fi

    # Count total BSA files
    local TOTAL_BSA_FILES=$(wc -l < "$BSA_FILES_LIST")
    echo "Total BSA files found: $TOTAL_BSA_FILES"

    if [ "$TOTAL_BSA_FILES" -eq 0 ]; then
        echo "No BSA files found to extract!"
        echo "$(date) No BSA files found to extract." >> "$LOG_FILE"
        rm -f "$BSA_FILES_LIST"
        update_progress 30
        return 0
    fi

    # Start the progress monitor
    monitor_extract_progress "$TOTAL_BSA_FILES" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # Extract BSA files in the order they appear in the BSA_FILES_LIST
    # (which now respects mod load order if CSV is available)
    echo "Extracting $TOTAL_BSA_FILES BSA files in priority order (max $bsa_thread_limit at once)..."

    # Process each BSA file
    while IFS= read -r bsa_file; do
        if [ -f "$bsa_file" ]; then
            # Run the extraction in background
            extract_single_bsa "$bsa_file" "$VRAMR_TEMP/Output" "$PROGRESS_FILE" "$EXTRACTION_LOG" &

            # Store the PID of the background process
            local PID=$!
            EXTRACT_PIDS+=($PID)
            RUNNING_EXTRACTIONS=$((RUNNING_EXTRACTIONS + 1))

            # If we've reached the max parallel extractions, wait for one to finish
            if [ $RUNNING_EXTRACTIONS -ge $bsa_thread_limit ]; then
                wait -n  # Wait for any child process to exit
                RUNNING_EXTRACTIONS=$((RUNNING_EXTRACTIONS - 1))
            fi
        fi
    done < "$BSA_FILES_LIST"

    # Wait for all extraction processes to finish
    for pid in "${EXTRACT_PIDS[@]}"; do
        wait $pid 2>/dev/null || true
    done

    # Wait for the monitor to finish
    wait $MONITOR_PID 2>/dev/null || true

    # Count the actual number of extracted files
    local DDS_COUNT=$(find "$VRAMR_TEMP/Output/textures" -type f -name "*.dds" | wc -l)
    echo "BSA extraction complete. Extracted $DDS_COUNT DDS files from $TOTAL_BSA_FILES BSA archives."
    echo "$(date) BSA extraction complete. Extracted $DDS_COUNT DDS files." >> "$LOG_FILE"

    # Clean up
    rm -f "$BSA_FILES_LIST" "$PROGRESS_FILE" "$PROGRESS_FILE.lock"

    update_progress 30
    flush

    # Restore original thread count
    THREAD_COUNT=$original_thread_count
    echo "Restored thread count to $THREAD_COUNT for subsequent operations."
    return 0
}

# Function to generate mod order CSV without PowerShell
generate_mod_order_csv() {
    if [ ! -f "$VRAMR_TEMP/ActiveModListOrder.csv" ]; then
        echo "No mod order CSV found. Attempting to generate it..."

        # Check for PowerShell first (legacy method)
        if [ -n "$PWSH_CMD" ] && [ -x "$PWSH_CMD" ]; then
            echo "Running external PowerShell script to generate mod load order CSV..."
            # PowerShell-based generation code here (your existing code)
            # ...
        else
            echo "PowerShell not available. Using native Bash method to generate mod order CSV..."

            # Create the CSV file
            local CSV_FILE="$VRAMR_TEMP/ActiveModListOrder.csv"
            echo "ModActivationIndex,ModName,IsModActive,ModPath" > "$CSV_FILE"

            # Check if MODS_DIR is set and exists
            if [ -z "$MODS_DIR" ] || [ ! -d "$MODS_DIR" ]; then
                echo "ERROR: Mods directory not specified or not found: $MODS_DIR" | tee -a "$LOG_FILE"
                return 1
            fi

            # First, try to find a plugins.txt file which might contain load order information
            local PLUGINS_FILE=""
            local BASE_DIR=$(dirname "$MODS_DIR")

            # Common locations for plugins.txt in MO2/Vortex setups
            potential_locations=(
                "$BASE_DIR/profiles/*/plugins.txt"
                "$BASE_DIR/profiles/*/loadorder.txt"
                "$BASE_DIR/profiles/*/modlist.txt"
                "$HOME/.local/share/Skyrim Special Edition/plugins.txt"
                "$HOME/.local/share/Steam/steamapps/compatdata/*/pfx/drive_c/users/steamuser/AppData/Local/Skyrim Special Edition/plugins.txt"
            )

            # Try to find a plugins file
            for pattern in "${potential_locations[@]}"; do
                for file in $pattern; do
                    if [ -f "$file" ]; then
                        PLUGINS_FILE="$file"
                        echo "Found potential load order file: $PLUGINS_FILE"
                        break 2
                    fi
                done
            done

            # If no plugins file found, just use directory order
            if [ -z "$PLUGINS_FILE" ]; then
                echo "No load order file found. Using directory listing order..."

                # List all directories in MODS_DIR and add them to CSV
                local index=0
                find "$MODS_DIR" -maxdepth 1 -type d -not -path "$MODS_DIR" | sort | while read -r mod_dir; do
                    if [ -d "$mod_dir" ]; then
                        local mod_name=$(basename "$mod_dir")
                        echo "$index,$mod_name,true,$mod_dir" >> "$CSV_FILE"
                        index=$((index + 1))
                    fi
                done
            else
                # Use the plugins file to determine order
                echo "Using load order from: $PLUGINS_FILE"

                # Process the plugins file
                local index=0
                # First, handle lines that start with '*' or '+' (active mods in some formats)
                grep -E '^\*|^\+' "$PLUGINS_FILE" 2>/dev/null | while read -r line; do
                    # Remove the leading * or + and any trailing whitespace
                    local mod_name=$(echo "$line" | sed -e 's/^[*+]//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

                    # Skip blank lines
                    if [ -z "$mod_name" ]; then continue; fi

                    # Try to find this mod in MODS_DIR
                    local found=0
                    for mod_dir in "$MODS_DIR"/*; do
                        if [ -d "$mod_dir" ]; then
                            local dir_name=$(basename "$mod_dir")
                            # If the mod directory name contains the plugin name or vice versa
                            if [[ "$dir_name" == *"$mod_name"* ]] || [[ "$mod_name" == *"$dir_name"* ]]; then
                                echo "$index,$dir_name,true,$mod_dir" >> "$CSV_FILE"
                                index=$((index + 1))
                                found=1
                                break
                            fi
                        fi
                    done

                    # If no matching directory found, add to CSV anyway with empty path
                    if [ $found -eq 0 ]; then
                        echo "$index,$mod_name,true,\"\"" >> "$CSV_FILE"
                        index=$((index + 1))
                    fi
                done

                # If no entries were found with * or +, try without markers
                if [ $index -eq 0 ]; then
                    cat "$PLUGINS_FILE" | grep -v '^#' | while read -r mod_name; do
                        # Skip blank lines
                        if [ -z "$mod_name" ]; then continue; fi

                        # Trim whitespace
                        mod_name=$(echo "$mod_name" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

                        # Try to find this mod in MODS_DIR
                        local found=0
                        for mod_dir in "$MODS_DIR"/*; do
                            if [ -d "$mod_dir" ]; then
                                local dir_name=$(basename "$mod_dir")
                                # If the mod directory name contains the plugin name or vice versa
                                if [[ "$dir_name" == *"$mod_name"* ]] || [[ "$mod_name" == *"$dir_name"* ]]; then
                                    echo "$index,$dir_name,true,$mod_dir" >> "$CSV_FILE"
                                    index=$((index + 1))
                                    found=1
                                    break
                                fi
                            fi
                        done

                        # If no matching directory found, add to CSV anyway with empty path
                        if [ $found -eq 0 ]; then
                            echo "$index,$mod_name,true,\"\"" >> "$CSV_FILE"
                            index=$((index + 1))
                        fi
                    done
                fi

                # If still no entries, fall back to directory listing
                if [ $index -eq 0 ]; then
                    echo "Could not parse load order from file. Falling back to directory listing..."
                    find "$MODS_DIR" -maxdepth 1 -type d -not -path "$MODS_DIR" | sort | while read -r mod_dir; do
                        if [ -d "$mod_dir" ]; then
                            local mod_name=$(basename "$mod_dir")
                            echo "$index,$mod_name,true,$mod_dir" >> "$CSV_FILE"
                            index=$((index + 1))
                        fi
                    done
                fi
            fi

            # Count entries in the CSV (subtract 1 for header)
            local entry_count=$(($(wc -l < "$CSV_FILE") - 1))
            echo "Generated mod order CSV with $entry_count entries at $CSV_FILE"

            # Validate the CSV has entries
            if [ $entry_count -eq 0 ]; then
                echo "ERROR: Generated CSV file has no entries. Cannot proceed." | tee -a "$LOG_FILE"
                rm -f "$CSV_FILE"
                return 1
            fi
        fi
    else
        echo "Found existing mod order CSV at $VRAMR_TEMP/ActiveModListOrder.csv"
    fi

    # Debug: Check CSV status before copy choice
    echo "DEBUG: Checking for CSV at '$VRAMR_TEMP/ActiveModListOrder.csv'"
    if [ -f "$VRAMR_TEMP/ActiveModListOrder.csv" ]; then
        echo "DEBUG: CSV Found. Will attempt prioritized copy."
        return 0
    else
        echo "DEBUG: CSV NOT Found. Script cannot continue without CSV."
        echo "DEBUG: Value of VRAMR_TEMP is '$VRAMR_TEMP'"
        echo "DEBUG: Value of PWSH_CMD is '$PWSH_CMD'"
        return 1
    fi
}
