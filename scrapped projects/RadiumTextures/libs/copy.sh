#!/bin/bash

# --- Texture Copy Functions ---

# SIMPLIFIED: Ultra-parallel copy function with NO duplicate checking
ultra_parallel_copy() {
    echo "$(date) Copying Loose Textures with maximum CPU utilization..." >> "$LOG_FILE"
    echo "Starting ultra-parallel texture copy using $THREAD_COUNT threads..."
    update_progress 40

    # Create required directories
    mkdir -p "$VRAMR_TEMP/Output/textures"
    mkdir -p "$VRAMR_TEMP/logfiles"

    # Initialize log file
    local COPY_LOG="$VRAMR_TEMP/logfiles/copy_progress.log"
    > "$COPY_LOG"
    echo "Texture copy started at $(date)" >> "$COPY_LOG"

    # Find all DDS files
    echo "Finding all DDS files (this may take a while)..."
    local TEMP_DDS_LIST=$(mktemp --tmpdir="$TEMP_DIR" dds_list.XXXXXX)

    # Find game DDS files
    if [ -d "$GAME_DIR/textures" ]; then
        echo "Scanning game directory '$GAME_DIR/textures' for DDS files..."
        find "$GAME_DIR/textures" -type f -iname "*.dds" -print0 > "$TEMP_DDS_LIST" 2>> "$LOG_FILE"
    else
        echo "Warning: Game textures directory not found: $GAME_DIR/textures" >> "$LOG_FILE"
    fi

    # Find mod DDS files
    if [ -d "$MODS_DIR" ]; then
        echo "Scanning mods directory '$MODS_DIR' for DDS files..."
        find "$MODS_DIR" -path "*/textures/*.dds" -type f -print0 >> "$TEMP_DDS_LIST" 2>> "$LOG_FILE"
    else
         echo "Warning: Mods directory not found: $MODS_DIR" >> "$LOG_FILE"
    fi

    # Count total files (null-terminated)
    local TOTAL_FILES=$(tr -d -c '\0' < "$TEMP_DDS_LIST" | wc -c)
    echo "Found $TOTAL_FILES DDS files to copy"
    echo "Found $TOTAL_FILES DDS files to potentially copy" >> "$LOG_FILE"

    if [ "$TOTAL_FILES" -eq 0 ]; then
        echo "No DDS files found to copy!"
        echo "$(date) No DDS files found to copy." >> "$LOG_FILE"
        rm -f "$TEMP_DDS_LIST"
        update_progress 55
        return
    fi

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" copy_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    # Monitor function
    monitor_copy_progress() {
        local total=$1
        local progress_file=$2
        local start_time=$(date +%s)
        local last_copied=0
        local last_time=$start_time
        local bc_installed=$(command -v bc)

        while true; do
            sleep 1
            local current_copied=$(cat "$progress_file" 2>/dev/null || echo 0)
            local current_time=$(date +%s)
            local elapsed_time=$((current_time - start_time))
            local time_diff=$((current_time - last_time))

            # Check if parent is running
            if ! ps -p $$ > /dev/null; then
                break
            fi

            local is_integer=0
            [[ "$current_copied" =~ ^[0-9]+$ ]] && is_integer=1

            if [ "$is_integer" -eq 1 ] && [ "$current_copied" -ge "$total" ]; then
                better_progress_bar "$current_copied" "$total" "Texture Copy"
                break
            fi

            if [ "$time_diff" -gt 0 ]; then
                local files_diff=$((current_copied - last_copied))
                local speed_str=""
                if [ -n "$bc_installed" ] && [ "$files_diff" -gt 0 ]; then
                    local speed=$(echo "scale=2; $files_diff / $time_diff" | bc)
                    speed_str=", ${speed} files/sec"
                fi

                better_progress_bar "$current_copied" "$total" "Texture Copy"

                last_copied=$current_copied
                last_time=$current_time
            fi
        done

        local final_copied=$(cat "$progress_file" 2>/dev/null || echo "$total")
        better_progress_bar "$final_copied" "$total" "Texture Copy"
        echo ""
    }

    # Start progress monitor
    monitor_copy_progress "$TOTAL_FILES" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # SIMPLIFIED: Direct copy approach without duplicate checking
    # Export necessary variables for the sub-process script
    export PROGRESS_FILE GAME_DIR VRAMR_TEMP LOG_FILE

    echo "Processing files in batches..."

    # Create a simple copy script that handles a single file
    local COPY_SCRIPT=$(mktemp --tmpdir="$TEMP_DIR" copy_script.XXXXXX)
    cat > "$COPY_SCRIPT" << 'EOF'
#!/bin/bash
# Simple direct copy script - no duplicate checking

# Use exported environment variables
src_file="$1" # $1 is the only argument now (filename)
# progress_file, game_dir, output_dir, log_file are from environment

# Determine relative path
rel_path=""
if [[ "$src_file" == "$GAME_DIR/textures/"* ]]; then
    rel_path="${src_file#$GAME_DIR/textures/}"
elif [[ "$src_file" == *"/textures/"* ]]; then
    rel_path="${src_file#*textures/}"
else
    rel_path="$(basename "$src_file")"
fi

# Create destination path
dest_dir="$VRAMR_TEMP/Output/textures/$(dirname "$rel_path")"
dest_path="$dest_dir/$(basename "$rel_path")"

# Create destination directory
mkdir -p "$dest_dir"

# Copy the file - overwrite if exists
if cp -f "$src_file" "$dest_path" 2>> "$LOG_FILE"; then
    # Update progress (atomically)
    (
        flock -x 200
        current=$(cat "$PROGRESS_FILE" 2>/dev/null || echo 0)
        echo $((current + 1)) > "$PROGRESS_FILE"
    ) 200>"$PROGRESS_FILE.lock"
else
    echo "Error copying $src_file to $dest_path" >> "$LOG_FILE"
    # Still increment counter so we don't hang
    (
        flock -x 200
        current=$(cat "$PROGRESS_FILE" 2>/dev/null || echo 0)
        echo $((current + 1)) > "$PROGRESS_FILE"
    ) 200>"$PROGRESS_FILE.lock"
fi
EOF

    # Make script executable
    chmod +x "$COPY_SCRIPT"

    # Process files from the null-terminated list using parallel
    if command -v parallel &> /dev/null; then
        echo "Using GNU parallel for file processing..."
        # Parallel passes only the input line ({}) as $1
        tr '\0' '\n' < "$TEMP_DDS_LIST" | parallel -j "$THREAD_COUNT" "$COPY_SCRIPT" {}
    else
        echo "GNU parallel not found, using xargs..."
        # xargs passes only the input file ({}) as $1
        xargs -0 -n 1 -P "$THREAD_COUNT" -I {} "$COPY_SCRIPT" {} < "$TEMP_DDS_LIST"
    fi

    # Wait for all copy operations to complete
    wait

    # Wait for monitor to finish
    wait $MONITOR_PID 2>/dev/null || true

    # Final counts
    local final_count=$(cat "$PROGRESS_FILE" 2>/dev/null || echo "$TOTAL_FILES")
    better_progress_bar "$final_count" "$TOTAL_FILES" "Texture Copy"
    echo ""

    # Count actual files in destination
    local total_copied_check=$(find "$VRAMR_TEMP/Output/textures" -type f -iname "*.dds" | wc -l)

    # Note about overlapping files
    echo "Parallel copy complete. Found $TOTAL_FILES files, copied $total_copied_check files to destination."
    echo "Note: Files from different sources with the same relative path will overwrite each other."
    echo "$(date) Texture copying complete - $total_copied_check files copied (no duplicate detection)." >> "$LOG_FILE"

    # Cleanup
    rm -f "$TEMP_DDS_LIST" "$PROGRESS_FILE" "$PROGRESS_FILE.lock" "$COPY_SCRIPT"

    # Remove empty directories
    find "$VRAMR_TEMP/Output/textures" -type d -empty -delete 2>/dev/null || true

    update_progress 55
}

# NEW: Prioritized texture copy based on CSV order
prioritized_texture_copy() {
    echo "$(date) Starting prioritized texture copy..." >> "$LOG_FILE"
    echo "Starting prioritized texture copy using $THREAD_COUNT threads..."
    update_progress 40 # Initial progress update

    # Output and log directories
    local OUTPUT_TEXTURES_DIR="$VRAMR_TEMP/Output/textures"
    local LOG_FILES_DIR="$VRAMR_TEMP/logfiles"
    mkdir -p "$OUTPUT_TEXTURES_DIR"
    mkdir -p "$LOG_FILES_DIR"
    local COPY_LOG="$LOG_FILES_DIR/prioritized_copy.log"
    > "$COPY_LOG"
    echo "Prioritized texture copy started at $(date)" >> "$COPY_LOG"

    # --- Export variables needed by the copy script ---
    export GAME_DIR MODS_DIR VRAMR_TEMP LOG_FILE

    # --- Create the Helper Copy Script (VRAMr Logic) ---
    local COPY_SCRIPT=$(mktemp --tmpdir="$TEMP_DIR" copy_script_prio.XXXXXX)
    cat > "$COPY_SCRIPT" << 'EOF'
#!/bin/bash
# Helper script for prioritized copy (using exported GAME_DIR, MODS_DIR, VRAMR_TEMP, LOG_FILE)

src_file="$1" # Full path to source DDS file
# GAME_DIR, MODS_DIR, VRAMR_TEMP, LOG_FILE are from environment

# Function to debug path processing if VERBOSE is enabled
debug_path() {
    if [ "${VERBOSE:-0}" -eq 1 ]; then
        echo "DEBUG PATH: $1" >> "$LOG_FILE"
    fi
}

# Determine relative path based on source (VRAMr logic), handling case
rel_path=""
shopt -s nocasematch # Enable case-insensitive matching for [[ ... ]]

# Check if it's a game file first (case-insensitive)
if [[ "$src_file" == "$GAME_DIR/textures/"* ]]; then
    rel_path="${src_file#$GAME_DIR/textures/}" # Use lowercase for removal
    debug_path "GAME_DIR match: $rel_path"
elif [[ "$src_file" == "$GAME_DIR/Textures/"* ]]; then
    rel_path="${src_file#$GAME_DIR/Textures/}" # Use capitalized for removal
    debug_path "GAME_DIR match (capital T): $rel_path"
else
    # More complex case: Any mod path with textures/ or Textures/ in it
    # We need to find the textures/ or Textures/ directory and ONLY keep what comes after

    # First convert all path separators to a special token we can split on
    normalized_path=$(echo "$src_file" | tr '/' '|')

    # Init variables
    capture_mode=0
    result=""

    # Process each path component
    IFS='|' read -ra path_parts <<< "$normalized_path"
    for part in "${path_parts[@]}"; do
        # Convert to lowercase for case-insensitive comparison
        lower_part=$(echo "$part" | tr '[:upper:]' '[:lower:]')

        # If we find "textures", start capturing everything after it
        if [ "$lower_part" = "textures" ]; then
            capture_mode=1
            continue  # Skip the "textures" directory itself
        fi

        # If in capture mode, add this part to our result
        if [ $capture_mode -eq 1 ]; then
            if [ -n "$result" ]; then
                result="$result/$part"
            else
                result="$part"
            fi
        fi
    done

    # If we found a textures directory and captured something after it
    if [ $capture_mode -eq 1 ] && [ -n "$result" ]; then
        rel_path="$result"
        debug_path "TEXTURES match: $rel_path"
    else
        # Fallback: Use filename only if path doesn't contain textures/ or Textures/
        rel_path="$(basename "$src_file")"
        debug_path "FALLBACK to basename: $rel_path"
        echo "Warning: Using fallback relative path (basename) for '$src_file' because no [Tt]extures/ path component was found." >> "$LOG_FILE"
    fi
fi

shopt -u nocasematch # Disable case-insensitive matching

# Ensure VRAMR_TEMP is set
if [[ -z "$VRAMR_TEMP" ]]; then
     echo "Error: VRAMR_TEMP environment variable not set in copy script." >> "$LOG_FILE"
     exit 1 # Cannot proceed without output base
fi

# Check if rel_path is empty
if [[ -z "$rel_path" ]]; then
    echo "Error: Calculated relative path is empty for '$src_file'. Skipping copy." >> "$LOG_FILE"
    exit 1 # Indicate error
fi

# Create destination path using VRAMR_TEMP
dest_base="$VRAMR_TEMP/Output/textures"
dest_dir="$dest_base/$(dirname "$rel_path")"
# Handle cases where dirname is '.' (e.g., file in root of textures dir)
if [[ "$dest_dir" == "$dest_base/." ]]; then
    dest_dir="$dest_base"
fi
dest_path="$dest_dir/$(basename "$rel_path")"


# Create destination directory if it doesn't exist
mkdir -p "$dest_dir"

# Copy the file - overwrite if exists
if ! cp -f "$src_file" "$dest_path" 2>> "$LOG_FILE"; then
    echo "Error copying $src_file to $dest_path" >> "$LOG_FILE"
fi
EOF
    chmod +x "$COPY_SCRIPT"

    # --- 1. Copy Base Game Textures (Lowest Priority) ---
    local GAME_TEXTURES_DIR="$GAME_DIR/textures"
    echo "Processing base game textures from: $GAME_TEXTURES_DIR"
    if [ -d "$GAME_TEXTURES_DIR" ]; then
        local game_files_list=$(mktemp --tmpdir="$TEMP_DIR" find_game_dds.XXXXXX)
        # Use find to locate game files (fd alternative removed for simplicity/consistency)
        echo "Using find to find game textures..."
        find "$GAME_TEXTURES_DIR" -type f -iname "*.dds" -print0 > "$game_files_list"

        # Process the list if not empty
        if [ -s "$game_files_list" ]; then
            # Use parallel or xargs with the simplified call
            if command -v parallel &> /dev/null; then
                parallel -0 -j "$THREAD_COUNT" "$COPY_SCRIPT" {} < "$game_files_list"
            else
                xargs -0 -n 1 -P "$THREAD_COUNT" -I {} "$COPY_SCRIPT" {} < "$game_files_list"
            fi
            wait # Wait for parallel jobs to finish
        fi
        local game_files_found=$(tr -d -c '\0' < "$game_files_list" | wc -c) # Count null terminators
        rm -f "$game_files_list"
        echo "Copied approximately $game_files_found base game textures." | tee -a "$COPY_LOG"
    else
        echo "Warning: Base game textures directory not found: $GAME_TEXTURES_DIR" | tee -a "$COPY_LOG"
    fi
    update_progress 45 # Update progress after game files

    # --- 2. Process Mod Textures based on CSV ---
    local CSV_PATH="$VRAMR_TEMP/ActiveModListOrder.csv"
    if [ ! -f "$CSV_PATH" ]; then
        echo "ERROR: Mod order CSV not found at $CSV_PATH. Cannot perform prioritized copy." | tee -a "$LOG_FILE" "$COPY_LOG"
        # Cleanup copy script
        rm -f "$COPY_SCRIPT"
        return 1 # Indicate failure
    fi

    echo "Processing mods based on $CSV_PATH (higher priority mods overwrite lower)..."
    local total_mods=0
    local mods_processed=0
    # MODS_DIR is already exported above

    # Count lines skipping header
    total_mods=$(($(wc -l < "$CSV_PATH") - 1))
    if [ "$total_mods" -lt 0 ]; then total_mods=0; fi
    echo "Found $total_mods mods listed in CSV." | tee -a "$COPY_LOG"
    local LOG_INTERVAL=10 # Log every N mods

    # Read CSV, skip header, handle potential CRLF line endings and quotes
    tail -n +2 "$CSV_PATH" | tr -d '\r' | while IFS=',' read -r index name active mod_path; do
        # Trim leading/trailing whitespace and quotes from mod_path
        mod_path=$(echo "$mod_path" | sed -e 's/^[[:space:]"\"]*//' -e 's/[[:space:]"\"]*$//')

        # Log current mod being processed (conditionally)
        if [[ $(( (mods_processed + 1) % LOG_INTERVAL )) -eq 0 || $((mods_processed + 1)) -eq $total_mods ]]; then
            echo "Processing Mod [$((mods_processed + 1))/$total_mods]: $name"
        fi

        if [ -z "$mod_path" ]; then
            echo "Warning: Skipping row with empty mod path (Index: $index, Name: $name)" | tee -a "$COPY_LOG"
            continue
        fi

        # Check if mod directory exists
        if [ ! -d "$mod_path" ]; then
             echo "Warning: Mod directory not found for '$name' at '$mod_path'. Skipping." | tee -a "$COPY_LOG"
             mods_processed=$((mods_processed + 1))
             continue # Skip to the next mod
        fi

        # Find and process ALL DDS files within the mod directory (Reduced logging)
        echo "Processing Mod [$((mods_processed + 1))/$total_mods]: $name (searching entire directory for .dds)"
        local mod_files_found=0
        local temp_find_list=$(mktemp --tmpdir="$TEMP_DIR" find_mod_dds.XXXXXX)
        # Use find to locate mod files
        find "$mod_path" -type f -iname "*.dds" -print0 > "$temp_find_list"

        # Check if any files were found before running parallel/xargs
        if [ -s "$temp_find_list" ]; then # -s checks if file exists and is not empty
             # Use parallel or xargs with the simplified call
            if command -v parallel &> /dev/null; then
                 parallel -0 -j "$THREAD_COUNT" "$COPY_SCRIPT" {} < "$temp_find_list"
             else
                  xargs -0 -n 1 -P "$THREAD_COUNT" -I {} "$COPY_SCRIPT" {} < "$temp_find_list"
             fi
             wait # Wait for this mod's jobs
             mod_files_found=$(tr -d -c '\0' < "$temp_find_list" | wc -c) # Count null terminators
             echo "  - Found and processed $mod_files_found DDS files for '$name'." >> "$COPY_LOG"
        else
            echo "  - No DDS files found anywhere within mod directory for '$name'." >> "$COPY_LOG"
        fi
        rm -f "$temp_find_list"

        # Update progress after each mod
        mods_processed=$((mods_processed + 1))
        local current_progress=$((45 + (mods_processed * 10 / total_mods) )) # Scale progress from 45 to 55
        if [ "$current_progress" -gt 55 ]; then current_progress=55; fi
        if [ "$total_mods" -eq 0 ]; then current_progress=55; fi # Handle division by zero if no mods
        update_progress "$current_progress"

    done # End of CSV loop

    echo "Finished processing mods from CSV." | tee -a "$COPY_LOG"

    # Final file count check
    local total_copied_check=$(find "$OUTPUT_TEXTURES_DIR" -type f -iname "*.dds" -print0 | tr -d -c '\0' | wc -c || echo 0)
    echo "Prioritized copy complete. Final count in output directory: $total_copied_check files." | tee -a "$COPY_LOG"
    echo "$(date) Prioritized texture copying complete - $total_copied_check files copied." >> "$LOG_FILE"

    # Cleanup
    rm -f "$COPY_SCRIPT"
    find "$OUTPUT_TEXTURES_DIR" -type d -empty -delete 2>/dev/null || true

    update_progress 55 # Ensure progress hits 55
    return 0 # Indicate success
}
