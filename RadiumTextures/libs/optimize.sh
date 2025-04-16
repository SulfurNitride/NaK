#!/bin/bash

# --- Texture Optimization Functions ---

# Improved texture optimization function
optimize_textures() {
    echo "$(date) Starting texture optimization..." >> "$LOG_FILE"
    echo "Starting texture optimization process..."
    update_progress 80

    local DB_FILE="$VRAMR_TEMP/Output/VRAMr.db"
    local OUTPUT_TEXTURES_DIR="$VRAMR_TEMP/Output/textures"

    # Check dependencies
    if [ -z "$SQLITE_CMD" ] || [ ! -x "$SQLITE_CMD" ]; then
        echo "ERROR: SQLite command not found or not executable: $SQLITE_CMD" | tee -a "$LOG_FILE"
        return 1
    fi

    if [ ! -f "$DB_FILE" ]; then
        echo "ERROR: Database file not found: $DB_FILE. Cannot optimize." | tee -a "$LOG_FILE"
        return 1
    fi

    # Create optimization log file
    local OPTIMIZATION_LOG="$VRAMR_TEMP/logfiles/optimization.log"
    > "$OPTIMIZATION_LOG"
    echo "Texture optimization started at $(date)" >> "$OPTIMIZATION_LOG"

    # Get count of textures to optimize
    local TEXTURES_TO_OPTIMIZE=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE processed IN (-2, 1);")
    echo "Found $TEXTURES_TO_OPTIMIZE textures to process for optimization"

    if [ "$TEXTURES_TO_OPTIMIZE" -eq 0 ]; then
        echo "No textures found to optimize."
        echo "$(date) No textures found to optimize." >> "$LOG_FILE"
        update_progress 90
        return 0
    fi

    # Create a temp dir for optimization work (still needed for texconv output)
    mkdir -p "$VRAMR_TEMP/temp_optimize"

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" optimize_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    # --- Define Internal Helper Function for Optimization ---
    _optimize_single_texture() {
        # Arguments: id, path, width, height, processed, target_size, target_format, type, progress_file, log_path
        local db_id="$1"
        local file_rel_path="$2"
        local width="$3"
        local height="$4"
        local processed="$5"
        local target_size="$6"
        local target_format="$7"
        local type="$8"
        local progress_file="$9"
        local script_log_path="${10}" # Renamed from optimization_log for clarity within function

        # --- Add Arg Check Here ---
        echo "DEBUG: _optimize_single_texture received target_format argument: [$target_format]" >> "$script_log_path"
        # --- End Arg Check ---

        # Log parameters for debugging (Use the passed log path)
        echo "DEBUG: Processing texture: ID=$db_id, Path=$file_rel_path, Type=$type" >> "$script_log_path"

        # Construct full path to the texture (OUTPUT_TEXTURES_DIR is exported, accessible here)
        local file_path="$OUTPUT_TEXTURES_DIR/$file_rel_path"

        # Skip if file doesn't exist (Use the passed log path)
        if [ ! -f "$file_path" ]; then
            echo "Error: File not found: $file_path" >> "$script_log_path"
            # Update progress even on error - Use atomic_increment from parent scope
            (
                flock -x 200
                current=$(cat "$progress_file" 2>/dev/null || echo 0)
                echo $((current + 1)) > "$progress_file"
            ) 200>"$progress_file.lock"
            # Return 1 to indicate error to caller if needed, though it's backgrounded
            return 1
        fi

        # Create a temporary directory for this optimization (VRAMR_TEMP is exported)
        local temp_dir
        temp_dir=$(mktemp -d --tmpdir="$VRAMR_TEMP/temp_optimize" optimize_XXXXXX)
        # No need to mkdir -p, mktemp does that

        # Base texconv command flags (TEXCONV_CMD is exported)
        local texconv_base_cmd=("$TEXCONV_CMD" -nologo -y -f "$target_format")

        # Add srgb flag based on type
        if [[ "$type" == "diffuse" || "$type" == "material" ]]; then
            texconv_base_cmd+=("-srgb")
        fi

        # Determine processing approach based on processed flag (Use the passed log path)
        if [ "$processed" -eq 1 ]; then
            # Texture is already correct size, just optimize format if needed
            echo "Optimizing format only for $file_rel_path to $target_format" >> "$script_log_path"

            # Use texconv for format conversion
            if [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
                # Run texconv for conversion
                "${texconv_base_cmd[@]}" -o "$temp_dir" "$file_path" >> "$script_log_path" 2>&1
                local texconv_exit_code=$?

                if [ "$texconv_exit_code" -eq 0 ]; then
                    # Find the output file
                    local output_file
                    output_file=$(find "$temp_dir" -type f -name "*.dds" | head -1)
                    if [ -n "$output_file" ]; then
                        # Copy back to original location
                        cp "$output_file" "$file_path"
                        echo "Successfully optimized $file_rel_path to $target_format" >> "$script_log_path"
                    else
                        echo "Error: No output file found for $file_rel_path after format optimization" >> "$script_log_path"
                    fi
                else
                    echo "Error: texconv format conversion failed (Exit code: $texconv_exit_code) for $file_rel_path" >> "$script_log_path"
                fi
            else
                echo "Warning: texconv not available for format conversion of $file_rel_path" >> "$script_log_path"
            fi

        elif [ "$processed" -eq -2 ]; then
            # Texture needs to be resized and optimized
            echo "Resizing and optimizing $file_rel_path from ${width}x${height} to ${target_size} ($target_format)" >> "$script_log_path"

            # Calculate aspect ratio for proper resizing
            local new_width=$width
            local new_height=$height
            local max_dim=$(( width > height ? width : height ))

            if [[ "$max_dim" -gt "$target_size" ]]; then
                if [[ "$width" -ge "$height" ]]; then
                    # Width is larger or square
                    new_width=$target_size
                    if [[ "$width" -ne 0 ]]; then
                        # Use awk for aspect ratio calculation
                        local aspect_ratio
                        aspect_ratio=$(awk -v h="$height" -v w="$width" 'BEGIN { printf "%.6f", h / w }')
                        # Use awk for calculating new height and round to integer
                        new_height=$(awk -v ts="$target_size" -v ar="$aspect_ratio" 'BEGIN { printf "%d", ts * ar }')
                    else
                        new_height=0 # Handle error
                    fi
                    # Ensure height is multiple of 4
                    new_height=$(( (new_height + 3) & ~3 ))
                    if [[ "$new_height" -eq 0 ]]; then new_height=4; fi
                else
                    # Height is larger
                    new_height=$target_size
                    if [[ "$height" -ne 0 ]]; then
                         # Use awk for aspect ratio calculation
                         local aspect_ratio
                         aspect_ratio=$(awk -v w="$width" -v h="$height" 'BEGIN { printf "%.6f", w / h }')
                         # Use awk for calculating new width and round to integer
                         new_width=$(awk -v ts="$target_size" -v ar="$aspect_ratio" 'BEGIN { printf "%d", ts * ar }')
                    else
                         new_width=0 # Handle error
                    fi
                    # Ensure width is multiple of 4
                    new_width=$(( (new_width + 3) & ~3 ))
                    if [[ "$new_width" -eq 0 ]]; then new_width=4; fi
                fi
                echo "  -> Calculated new dimensions: ${new_width}x${new_height}" >> "$script_log_path"
            else
                 echo "  -> Dimensions ${width}x${height} are already within target ${target_size}. Skipping resize." >> "$script_log_path"
                 new_width=$width
                 new_height=$height
            fi

            # Use texconv for resizing and format conversion
            if [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
                # Add resize flags if dimensions changed
                local resize_flags=()
                if [[ "$new_width" -ne "$width" || "$new_height" -ne "$height" ]]; then
                     resize_flags=("-w" "$new_width" "-h" "$new_height")
                     resize_flags+=("-if" "BOX") # Add filter for resizing
                fi

                # Run texconv for conversion
                "${texconv_base_cmd[@]}" "${resize_flags[@]}" -o "$temp_dir" "$file_path" >> "$script_log_path" 2>&1
                local texconv_exit_code=$?

                if [ "$texconv_exit_code" -eq 0 ]; then
                    # Find the output file
                    local output_file
                    output_file=$(find "$temp_dir" -type f -name "*.dds" | head -1)
                    if [ -n "$output_file" ]; then
                        # Copy back to original location
                        cp "$output_file" "$file_path"
                        echo "Successfully processed $file_rel_path to ${new_width}x${new_height} $target_format" >> "$script_log_path"
                    else
                        echo "Error: No output file found for $file_rel_path after resize/optimize" >> "$script_log_path"
                    fi
                else
                    echo "Error: texconv resize/conversion failed (Exit code: $texconv_exit_code) for $file_rel_path" >> "$script_log_path"
                fi
            else
                echo "Warning: texconv not available for resizing $file_rel_path" >> "$script_log_path"
            fi
        fi

        # Clean up temporary directory for this specific texture
        rm -rf "$temp_dir"

        # Update progress using atomic increment from parent scope
        (
            flock -x 200
            current=$(cat "$progress_file" 2>/dev/null || echo 0)
            echo $((current + 1)) > "$progress_file"
        ) 200>"$progress_file.lock"

        # Return 0 for success
        return 0
    } # --- End of _optimize_single_texture function definition ---

    # Show progress monitor
    monitor_optimize_progress() {
        local total=$1
        local progress_file=$2
        while true; do
            sleep 1
            local current=$(cat "$progress_file" 2>/dev/null || echo 0)
            if [ "$current" -ge "$total" ]; then
                better_progress_bar "$current" "$total" "Optimization"
                break
            fi
            if ! ps -p $$ > /dev/null; then break; fi
            better_progress_bar "$current" "$total" "Optimization"
        done
        echo ""
    }

    # Start progress monitor
    monitor_optimize_progress "$TEXTURES_TO_OPTIMIZE" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # Extract data using process substitution and call internal function
    echo "Querying database and processing textures..."

    while IFS=$'\t' read -r id path width height processed target_size target_format type || [[ -n "$type" ]]; do
        # Validate data before passing to optimization function
        if [ -z "$path" ]; then
            echo "Warning: Empty path found for texture ID $id. Skipping." | tee -a "$OPTIMIZATION_LOG"
            # Increment progress directly here for skipped items
            (
                flock -x 200
                current=$(cat "$PROGRESS_FILE" 2>/dev/null || echo 0)
                echo $((current + 1)) > "$PROGRESS_FILE"
            ) 200>"$PROGRESS_FILE.lock"
            continue
        fi

        # Call the internal function directly in the background
        _optimize_single_texture "$id" "$path" "$width" "$height" "$processed" "$target_size" "$target_format" "$type" "$PROGRESS_FILE" "$OPTIMIZATION_LOG" &

        # Control parallelism - Adjusted job control
        RUNNING_JOBS=$(jobs -p | wc -l) # Count running PIDs
        while [ "$RUNNING_JOBS" -ge "$THREAD_COUNT" ]; do
            wait -n # Wait for any background job to finish
            RUNNING_JOBS=$(jobs -p | wc -l)
        done
    done < <("$SQLITE_CMD" -separator $'\t' "$DB_FILE" "SELECT id, path, width, height, processed, optimize_target_size, optimize_target_format, type FROM textures WHERE processed IN (-2, 1);")

    # Wait for all remaining background jobs to complete
    wait

    # Wait for monitor to finish
    wait $MONITOR_PID 2>/dev/null || true

    # Clean up temporary directory used for texconv outputs
    rm -rf "$VRAMR_TEMP/temp_optimize"

    # Final statistics
    local final_count=$(cat "$PROGRESS_FILE" 2>/dev/null || echo "$TEXTURES_TO_OPTIMIZE")
    echo "Optimization complete. Processed $final_count textures."
    echo "$(date) Optimization complete. Processed $final_count textures." >> "$LOG_FILE"

    # Cleanup progress file
    rm -f "$PROGRESS_FILE" "$PROGRESS_FILE.lock"

    update_progress 90
    return 0
}
