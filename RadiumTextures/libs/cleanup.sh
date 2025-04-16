#!/bin/bash

# --- Quality Control and Cleanup Functions ---

# Quality control function
quality_control() {
    echo "$(date) Running quality control checks..." >> "$LOG_FILE"
    echo "Running quality control checks on optimized textures..."
    update_progress 90

    local OUTPUT_TEXTURES_DIR="$VRAMR_TEMP/Output/textures"

    # Check if output textures directory exists
    if [ ! -d "$OUTPUT_TEXTURES_DIR" ]; then
        echo "ERROR: Output textures directory not found: $OUTPUT_TEXTURES_DIR" | tee -a "$LOG_FILE"
        return 1
    fi

    # Quality control log file
    local QC_LOG="$VRAMR_TEMP/logfiles/quality_control.log"
    > "$QC_LOG"
    echo "Quality control started at $(date)" >> "$QC_LOG"

    # First, check for empty files
    echo "Checking for empty or corrupted DDS files..."
    local empty_files=0
    find "$OUTPUT_TEXTURES_DIR" -type f -name "*.dds" -size 0 -print0 | while IFS= read -r -d $'\0' file; do
        echo "Warning: Empty file found: ${file#$OUTPUT_TEXTURES_DIR/}" | tee -a "$QC_LOG"
        empty_files=$((empty_files + 1))
        # Delete empty files
        rm -f "$file"
    done

    # Check for small files (likely corrupted)
    local small_files=0
    find "$OUTPUT_TEXTURES_DIR" -type f -name "*.dds" -size -128c -print0 | while IFS= read -r -d $'\0' file; do
        echo "Warning: Suspiciously small file found: ${file#$OUTPUT_TEXTURES_DIR/}" | tee -a "$QC_LOG"
        small_files=$((small_files + 1))
        # Don't delete these automatically as they might be valid tiny textures
    done

    # Validate a sample of DDS files with ImageMagick
    echo "Validating a sample of DDS files..."
    local sample_size=100
    local total_files=$(find "$OUTPUT_TEXTURES_DIR" -type f -name "*.dds" | wc -l)
    local corrupt_files=0

    if [ "$total_files" -gt 0 ]; then
        # Only sample if there are many files, otherwise check all
        if [ "$total_files" -gt "$sample_size" ]; then
            echo "Taking a sample of $sample_size files from $total_files total..."
            local sample_files=$(find "$OUTPUT_TEXTURES_DIR" -type f -name "*.dds" | sort -R | head -n "$sample_size")
        else
            echo "Checking all $total_files files..."
            local sample_files=$(find "$OUTPUT_TEXTURES_DIR" -type f -name "*.dds")
        fi

        # Check each file in the sample
        echo "$sample_files" | while read -r file; do
            if [ -n "$MAGICK_CMD" ] && [ -x "$MAGICK_CMD" ]; then
                if ! "$MAGICK_CMD" identify -quiet "$file" &>/dev/null; then
                    echo "Warning: Possible corrupted file: ${file#$OUTPUT_TEXTURES_DIR/}" | tee -a "$QC_LOG"
                    corrupt_files=$((corrupt_files + 1))
                fi
            elif [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
                # Use texconv as fallback validation
                if ! "$TEXCONV_CMD" -nologo -y -noprompt -noout -o "$TEMP_DIR" "$file" &>/dev/null; then
                    echo "Warning: Possible corrupted file: ${file#$OUTPUT_TEXTURES_DIR/}" | tee -a "$QC_LOG"
                    corrupt_files=$((corrupt_files + 1))
                fi
            fi
        done
    fi

    # Write QC summary
    echo "Quality control check completed at $(date)" >> "$QC_LOG"
    echo "Total files checked: $total_files" >> "$QC_LOG"
    echo "Empty files found and removed: $empty_files" >> "$QC_LOG"
    echo "Suspiciously small files found: $small_files" >> "$QC_LOG"
    echo "Potentially corrupted files detected in sample: $corrupt_files" >> "$QC_LOG"

    # Final QC report
    echo "Quality control complete!"
    echo "  - Total textures: $total_files"
    echo "  - Empty files removed: $empty_files"
    echo "  - Suspiciously small files: $small_files"
    echo "  - Potentially corrupted files: $corrupt_files"

    echo "$(date) Quality control complete. $empty_files empty files removed." >> "$LOG_FILE"

    update_progress 95
    return 0
}

# Final cleanup function
final_cleanup() {
    echo "$(date) Running final cleanup..." >> "$LOG_FILE"
    echo "Running final cleanup and preparing output..."
    update_progress 95

    # Final output directory names
    local FINAL_OUTPUT_DIR="$VRAMR_TEMP/DragNDropThisFolderIntoModManager"

    # Rename Output directory to final name
    if [ -d "$VRAMR_TEMP/Output" ]; then
        mv "$VRAMR_TEMP/Output" "$FINAL_OUTPUT_DIR"
        echo "Renamed output directory to: $FINAL_OUTPUT_DIR"
    else
        echo "Warning: Output directory not found for renaming!"
        mkdir -p "$FINAL_OUTPUT_DIR"
        if [ -d "$VRAMR_TEMP/Output/textures" ]; then
            mv "$VRAMR_TEMP/Output/textures" "$FINAL_OUTPUT_DIR/"
        fi
    fi

    # Create VRAMr output marker file
    echo "Creating VRAMr output marker file..."
    echo "VRAMr Output Directory - Created $(date)" > "$FINAL_OUTPUT_DIR/VRAMrOutput.tmp"

    # Remove database files
    echo "Removing database files..."
    find "$FINAL_OUTPUT_DIR" -name "*.db" -delete
    find "$FINAL_OUTPUT_DIR" -name "*.db-*" -delete

    # Remove empty directories
    echo "Cleaning up empty directories..."
    find "$FINAL_OUTPUT_DIR" -type d -empty -delete 2>/dev/null || true

    # Create summary log
    local SUMMARY_LOG="$VRAMR_TEMP/logfiles/summary.log"
    {
        echo "VRAMr Native Linux Summary"
        echo "=========================="
        echo "Completed at: $(date)"
        echo "Output Directory: $FINAL_OUTPUT_DIR"
        echo "Preset Used: $PRESET (D:$DIFFUSE N:$NORMAL P:$PARALLAX M:$MATERIAL)"
        echo ""
        echo "File Counts:"
        echo "  - Total DDS Files: $(find "$FINAL_OUTPUT_DIR" -type f -name "*.dds" | wc -l)"
        echo ""
        echo "All logs available in: $VRAMR_TEMP/logfiles/"
    } > "$SUMMARY_LOG"

    # Copy summary to output directory
    cp "$SUMMARY_LOG" "$FINAL_OUTPUT_DIR/VRAMr_Summary.txt"

    echo "Final cleanup complete!"
    echo "$(date) Final cleanup complete. Output ready in: $FINAL_OUTPUT_DIR" >> "$LOG_FILE"

    update_progress 100
    echo "VRAMr process completed successfully!"
    echo ""
    echo "====================================================================="
    echo "VRAMr Output is ready in: $FINAL_OUTPUT_DIR"
    echo "Put this folder into your mod manager"
    echo "====================================================================="

    return 0
}
