#!/bin/bash

# --- Texture Optimization Functions ---

# Improved texture optimization function with Cuttlefish integration
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

    # Check for optimization tools - prefer Cuttlefish but fallback to texconv
    local USE_CUTTLEFISH=0
    if [ -n "$CUTTLEFISH_CMD" ] && [ -x "$CUTTLEFISH_CMD" ]; then
        USE_CUTTLEFISH=1
        echo "Using Cuttlefish for texture optimization"
    elif [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
        echo "Cuttlefish not available. Using texconv for texture optimization"
    else
        echo "ERROR: Neither Cuttlefish nor texconv available for texture optimization." | tee -a "$LOG_FILE"
        return 1
    fi

    # Create optimization log file
    local OPTIMIZATION_LOG="$VRAMR_TEMP/logfiles/optimization.log"
    > "$OPTIMIZATION_LOG"
    echo "Texture optimization started at $(date)" >> "$OPTIMIZATION_LOG"
    echo "Primary tool: $([ "$USE_CUTTLEFISH" -eq 1 ] && echo "Cuttlefish" || echo "texconv")" >> "$OPTIMIZATION_LOG"

    # Get count of textures to optimize
    local TEXTURES_TO_OPTIMIZE=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE processed IN (-2, 1);")
    echo "Found $TEXTURES_TO_OPTIMIZE textures to process for optimization"

    if [ "$TEXTURES_TO_OPTIMIZE" -eq 0 ]; then
        echo "No textures found to optimize."
        echo "$(date) No textures found to optimize." >> "$LOG_FILE"
        update_progress 90
        return 0
    fi

    # Create a temp dir for optimization work
    mkdir -p "$VRAMR_TEMP/temp_optimize"

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" optimize_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    # --- Define Internal Helper Function for Optimization using Cuttlefish ---
    _optimize_single_texture_cuttlefish() {
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
        local script_log_path="${10}"

        # Log parameters for debugging
        echo "DEBUG: Processing texture with Cuttlefish: ID=$db_id, Path=$file_rel_path, Type=$type, Target format=$target_format" >> "$script_log_path"

        # Construct full path to the texture
        local file_path="$OUTPUT_TEXTURES_DIR/$file_rel_path"

        # Skip if file doesn't exist
        if [ ! -f "$file_path" ]; then
            echo "Error: File not found: $file_path" >> "$script_log_path"
            # Update progress even on error
            (
                flock -x 200
                current=$(cat "$progress_file" 2>/dev/null || echo 0)
                echo $((current + 1)) > "$progress_file"
            ) 200>"$progress_file.lock"
            return 1
        fi

        # Create a temporary directory for this optimization
        local temp_dir
        temp_dir=$(mktemp -d --tmpdir="$VRAMR_TEMP/temp_optimize" optimize_XXXXXX)

        # Convert texconv BC format to Cuttlefish format
        local cuttlefish_format=""
        case "$target_format" in
            BC1_UNORM)
                cuttlefish_format="BC1_RGB"
                ;;
            BC1_UNORM_SRGB)
                cuttlefish_format="BC1_RGB"
                ;;
            BC4_UNORM)
                cuttlefish_format="BC4"
                ;;
            BC5_UNORM)
                cuttlefish_format="BC5"
                ;;
            BC5_SNORM)
                cuttlefish_format="BC5"
                ;;
            BC7_UNORM)
                cuttlefish_format="BC7"
                ;;
            BC7_UNORM_SRGB)
                cuttlefish_format="BC7"
                ;;
            *)
                # Default to BC7 if format is unknown
                echo "Warning: Unknown target format '$target_format', defaulting to BC7" >> "$script_log_path"
                cuttlefish_format="BC7"
                ;;
        esac

        # Determine format type (normal or srgb)
        local format_type="unorm"
        if [[ "$target_format" == *"SNORM"* ]]; then
            format_type="snorm"
        fi

        # Set sRGB flag for diffuse and material textures
        local srgb_flag=""
        if [[ "$type" == "diffuse" || "$type" == "material" ]] || [[ "$target_format" == *"SRGB"* ]]; then
            srgb_flag="--srgb"
        fi

        # Determine if we need to resize (processed = -2) or just convert format (processed = 1)
        if [ "$processed" -eq 1 ]; then
            # Format conversion only
            echo "Optimizing format only for $file_rel_path to $cuttlefish_format" >> "$script_log_path"

            # Construct Cuttlefish command for format conversion
            local output_file="$temp_dir/$(basename "$file_rel_path")"

            "$CUTTLEFISH_CMD" -i "$file_path" \
                -f "$cuttlefish_format" \
                -t "$format_type" \
                $srgb_flag \
                --file-format dds \
                -o "$output_file" \
                -Q "normal" >> "$script_log_path" 2>&1

            local cuttlefish_exit_code=$?

            if [ "$cuttlefish_exit_code" -eq 0 ] && [ -f "$output_file" ]; then
                # Copy back to original location
                cp "$output_file" "$file_path"
                echo "Successfully optimized $file_rel_path to $cuttlefish_format" >> "$script_log_path"
            else
                echo "Error: Cuttlefish format conversion failed (Exit code: $cuttlefish_exit_code) for $file_rel_path" >> "$script_log_path"
                echo "Attempting fallback with texconv..." >> "$script_log_path"

                # Fallback to texconv if available
                if [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
                    _optimize_single_texture_texconv "$db_id" "$file_rel_path" "$width" "$height" "$processed" "$target_size" "$target_format" "$type" "$progress_file" "$script_log_path"
                else
                    echo "ERROR: No fallback method available. Texture optimization failed." >> "$script_log_path"
                fi
            fi

        elif [ "$processed" -eq -2 ]; then
            # Resize and format conversion
            echo "Resizing and optimizing $file_rel_path from ${width}x${height} to ${target_size} ($cuttlefish_format)" >> "$script_log_path"

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

            # Skip resize if dimensions are unchanged
            local resize_flag=""
            if [[ "$new_width" -ne "$width" || "$new_height" -ne "$height" ]]; then
                resize_flag="-r $new_width $new_height catmull-rom"
            fi

            # Construct full Cuttlefish command
            local output_file="$temp_dir/$(basename "$file_rel_path")"

            "$CUTTLEFISH_CMD" -i "$file_path" \
                $resize_flag \
                -f "$cuttlefish_format" \
                -t "$format_type" \
                $srgb_flag \
                --file-format dds \
                -o "$output_file" \
                -Q "normal" >> "$script_log_path" 2>&1

            local cuttlefish_exit_code=$?

            if [ "$cuttlefish_exit_code" -eq 0 ] && [ -f "$output_file" ]; then
                # Copy back to original location
                cp "$output_file" "$file_path"
                echo "Successfully processed $file_rel_path to ${new_width}x${new_height} $cuttlefish_format" >> "$script_log_path"
            else
                echo "Error: Cuttlefish resize/conversion failed (Exit code: $cuttlefish_exit_code) for $file_rel_path" >> "$script_log_path"
                echo "Attempting fallback with texconv..." >> "$script_log_path"

                # Fallback to texconv if available
                if [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
                    _optimize_single_texture_texconv "$db_id" "$file_rel_path" "$width" "$height" "$processed" "$target_size" "$target_format" "$type" "$progress_file" "$script_log_path"
                else
                    echo "ERROR: No fallback method available. Texture optimization failed." >> "$script_log_path"
                fi
            fi
        fi

        # Clean up temporary directory for this specific texture
        rm -rf "$temp_dir"

        # Update progress using atomic increment
        (
            flock -x 200
            current=$(cat "$progress_file" 2>/dev/null || echo 0)
            echo $((current + 1)) > "$progress_file"
        ) 200>"$progress_file.lock"

        return 0
    }

    # --- Define Internal Helper Function for Optimization using texconv (fallback) ---
    _optimize_single_texture_texconv() {
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
        local script_log_path="${10}"

        # Log parameters for debugging (Use the passed log path)
        echo "DEBUG: Processing texture with texconv: ID=$db_id, Path=$file_rel_path, Type=$type" >> "$script_log_path"

        # Construct full path to the texture
        local file_path="$OUTPUT_TEXTURES_DIR/$file_rel_path"

        # Skip if file doesn't exist
        if [ ! -f "$file_path" ]; then
            echo "Error: File not found: $file_path" >> "$script_log_path"
            # Update progress even on error
            (
                flock -x 200
                current=$(cat "$progress_file" 2>/dev/null || echo 0)
                echo $((current + 1)) > "$progress_file"
            ) 200>"$progress_file.lock"
            return 1
        fi

        # Create a temporary directory for this optimization
        local temp_dir
        temp_dir=$(mktemp -d --tmpdir="$VRAMR_TEMP/temp_optimize" optimize_XXXXXX)

        # Base texconv command flags
        local texconv_base_cmd=("$TEXCONV_CMD" -nologo -y -f "$target_format")

        # Add srgb flag based on type
        if [[ "$type" == "diffuse" || "$type" == "material" ]]; then
            texconv_base_cmd+=("-srgb")
        fi

        # Determine processing approach based on processed flag
        if [ "$processed" -eq 1 ]; then
            # Texture is already correct size, just optimize format if needed
            echo "Optimizing format only for $file_rel_path to $target_format" >> "$script_log_path"

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
        fi

        # Clean up temporary directory for this specific texture
        rm -rf "$temp_dir"

        # Update progress using atomic increment
        (
            flock -x 200
            current=$(cat "$progress_file" 2>/dev/null || echo 0)
            echo $((current + 1)) > "$progress_file"
        ) 200>"$progress_file.lock"

        # Return 0 for success
        return 0
    }

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

    # Extract data using process substitution and call appropriate function based on available tools
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

        # Call the appropriate optimization function based on available tools
        if [ "$USE_CUTTLEFISH" -eq 1 ]; then
            _optimize_single_texture_cuttlefish "$id" "$path" "$width" "$height" "$processed" "$target_size" "$target_format" "$type" "$PROGRESS_FILE" "$OPTIMIZATION_LOG" &
        else
            _optimize_single_texture_texconv "$id" "$path" "$width" "$height" "$processed" "$target_size" "$target_format" "$type" "$PROGRESS_FILE" "$OPTIMIZATION_LOG" &
        fi

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

    # Clean up temporary directory used for outputs
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
