#!/bin/bash

# VRAMr Native Linux Implementation
# Main orchestration script

# Use relative paths since libs is in the same directory as this script
PORTABLE_DIR="./libs/portable"
mkdir -p "$PORTABLE_DIR"
echo "Portable binaries will be stored in: $PORTABLE_DIR"

# Source all component scripts using relative paths
source ./libs/config.sh
source ./libs/utils.sh
source ./libs/deps.sh
source ./libs/extract.sh
source ./libs/copy.sh
source ./libs/process.sh
source ./libs/optimize.sh
source ./libs/cleanup.sh

# --- Main Script Flow ---

echo "Starting VRAMr Native Script..."

# --- CRITICAL: Initialize configuration first ---
# This will parse command-line arguments and prompt for paths
initialize_script "$@"

# --- 0. Check Dependencies ---
echo "Checking for dependencies..."
if ! command -v awk &> /dev/null; then
    echo "ERROR: 'awk' command not found. This script requires 'awk' for floating-point calculations."
    exit 1
fi

# --- 1. Set file descriptor limits ---
set_file_limits

# --- 2. Resolve dependencies (system or portable binaries) ---
resolve_dependencies
if [ $? -ne 0 ]; then
    echo "Failed to resolve critical dependencies. Aborting."
    exit 1
fi

# --- 3. Generate Mod Order CSV using PowerShell if needed ---
generate_mod_order_csv

# --- 4. BSA Extraction ---
extract_bsa_files
flush

# --- 5. Loose Texture Copy ---
# Use prioritized copy if the CSV exists, otherwise fall back to simple copy
if [ -f "$VRAMR_TEMP/ActiveModListOrder.csv" ]; then
    echo "Attempting prioritized texture copy based on mod load order..."
    prioritized_texture_copy
    if [ $? -ne 0 ]; then
        echo "Prioritized texture copy failed, falling back to simple parallel copy..."
        ultra_parallel_copy
    fi
else
    echo "CSV file not found, using simple parallel texture copy..."
    ultra_parallel_copy
fi
flush

# --- 6. Process Exclusions ---
linux_native_exclusions
flush

# --- 7. Texture Analysis ---
echo "Ensuring old database is removed..."
rm -f "$VRAMR_TEMP/Output/VRAMr.db" "$VRAMR_TEMP/Output/VRAMr.db-journal" # Remove DB and potential journal
linux_native_analyze
if [ $? -ne 0 ]; then
    echo "Texture Analysis failed. Attempting safe mode analysis..."
    analyze_textures_safely
    if [ $? -ne 0 ]; then
        echo "Safe mode analysis also failed. Aborting."
        exit 1
    fi
fi
flush

# --- 8. Filtering ---
linux_native_filter
flush

# --- 8b. Delete Skipped Textures ---
delete_skipped_textures
if [ $? -ne 0 ]; then
    echo "Deletion of skipped textures failed. Continuing with optimization..."
    # Not necessarily fatal, so we can continue
fi
flush

# --- 9. Optimization ---
optimize_textures
flush

# --- 10. Quality Control ---
quality_control
flush

# --- 11. Final Cleanup ---
final_cleanup

# Clean up temp directory
echo "Cleaning up temporary files..."
# Ensure TEMP_PS1_FILE is removed if it was created
if [ -n "$TEMP_PS1_FILE" ] && [ -f "$TEMP_PS1_FILE" ]; then
    rm -f "$TEMP_PS1_FILE"
fi
rm -rf "$TEMP_DIR"

echo "VRAMr Native Script completed successfully!"
exit 0
