#!/bin/bash

# --- Enhanced BSA Extraction using hoolamike ---
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

    # Find BSA files in different locations
    find_bsa_files() {
        local SEARCH_DIR="$1"
        local FILES_LIST="$2"
        local LABEL="$3"

        if [ ! -d "$SEARCH_DIR" ]; then
            echo "Warning: Directory does not exist: $SEARCH_DIR" | tee -a "$LOG_FILE"
            return
        fi

        echo "Searching for BSA files in: $SEARCH_DIR ($LABEL)"

        # Use find to locate BSA files recursively
        local FOUND_COUNT=0
        find "$SEARCH_DIR" -type f -name "*.bsa" 2>/dev/null | while read -r bsa_file; do
            if [ -f "$bsa_file" ]; then
                echo "$bsa_file" >> "$FILES_LIST"
                FOUND_COUNT=$((FOUND_COUNT + 1))
                if [ "$VERBOSE" -eq 1 ]; then
                    echo "Found BSA ($LABEL): $bsa_file"
                fi
            fi
        done

        echo "Found $FOUND_COUNT BSA files in $LABEL"
        echo "Found $FOUND_COUNT BSA files in $LABEL" >> "$LOG_FILE"
    }

    # Create a list of BSA files
    local BSA_FILES_LIST=$(mktemp --tmpdir="$TEMP_DIR" bsa_files.XXXXXX)
    > "$BSA_FILES_LIST"

    # Find BSA files in game directory
    find_bsa_files "$GAME_DIR" "$BSA_FILES_LIST" "Game Directory"

    # Find BSA files in mods directory if it exists
    if [ -d "$MODS_DIR" ]; then
        find_bsa_files "$MODS_DIR" "$BSA_FILES_LIST" "Mods Directory"
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

    # Create a directory to track extraction progress
    local EXTRACTION_LOG="$VRAMR_TEMP/logfiles/bsa_extraction.log"
    > "$EXTRACTION_LOG"
    echo "BSA extraction started at $(date)" >> "$EXTRACTION_LOG"

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" extract_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    # Function to extract a single BSA file
    extract_single_bsa() {
        local BSA_FILE="$1"
        local OUTPUT_DIR="$2"
        local PROGRESS_FILE="$3"
        local EXTRACTION_LOG="$4"
        local BSA_NAME=$(basename "$BSA_FILE")
        local ORIGINAL_DIR=$(pwd) # Store original directory

        # Create a unique subdirectory in TEMP_DIR for temporary extraction
        # Simplify template to avoid issues with filename characters or length
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

    # Start the progress monitor
    monitor_extract_progress "$TOTAL_BSA_FILES" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # Extract BSA files in parallel
    echo "Extracting $TOTAL_BSA_FILES BSA files in parallel (max $bsa_thread_limit at once)..."

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
