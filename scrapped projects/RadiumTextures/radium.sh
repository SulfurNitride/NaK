#!/bin/bash

# RadiumTextures - Simplified Skyrim Texture Optimization Script
# Modified to use ImageMagick for texture analysis and optimization

# --- Get absolute paths ---
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LIBS_DIR="$SCRIPT_DIR/libs"
PORTABLE_DIR="$LIBS_DIR/portable"

# Create portable directory
mkdir -p "$PORTABLE_DIR"

echo "============ RadiumTextures ============"
echo "Script directory: $SCRIPT_DIR"
echo "Libraries directory: $LIBS_DIR"
echo "Portable directory: $PORTABLE_DIR"
echo "========================================"

# Check if libraries directory exists
if [ ! -d "$LIBS_DIR" ]; then
    echo "ERROR: Libraries directory not found: $LIBS_DIR"
    echo "Make sure you're running this script from the correct location."
    exit 1
fi

# --- Define URLs and paths for dependencies ---
SQLITE_URL="https://sqlite.org/2025/sqlite-tools-linux-x64-3490100.zip"
MAGICK_URL="https://imagemagick.org/archive/binaries/magick"
BSATOOL_URL="https://downloads.openmw.org/linux/generic/openmw-0.48.0-Linux-64Bit.tar.gz"

# --- Define archive names ---
SQLITE_ZIP="sqlite-tools-linux-x64-3490100.zip"
BSATOOL_ARCHIVE="openmw-0.48.0-Linux-64Bit.tar.gz"

# --- Source configuration from config.sh ---
CONFIG_PATH="$LIBS_DIR/config.sh"
if [ -f "$CONFIG_PATH" ]; then
    echo "Loading configuration from: $CONFIG_PATH"
    source "$CONFIG_PATH"

    # Ensure the libraries are in the correct location FIRST
    SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
    LIBS_DIR="$SCRIPT_DIR/libs"

    # NOW force the correct portable directory path after sourcing and confirming LIBS_DIR
    PORTABLE_DIR="$LIBS_DIR/portable"

    # --- Define portable binary paths NOW that PORTABLE_DIR is set ---
    PORTABLE_SQLITE_BIN="$PORTABLE_DIR/sqlite3"
    PORTABLE_MAGICK_BIN="$PORTABLE_DIR/magick"
    PORTABLE_BSATOOL_BIN="$LIBS_DIR/bsatool"
    PORTABLE_BSATOOL_DIR="$LIBS_DIR"

    # --- Set default texture resolution values if not already defined ---
    # These are critical for the optimization process
    DIFFUSE=${DIFFUSE:-2048}  # Default to 2048 if not set
    NORMAL=${NORMAL:-1024}    # Default to 1024 if not set
    PARALLAX=${PARALLAX:-512} # Default to 512 if not set
    MATERIAL=${MATERIAL:-512} # Default to 512 if not set
    PRESET=${PRESET:-"Optimum"} # Default preset name

    echo "Texture resolution targets: Diffuse=$DIFFUSE, Normal=$NORMAL, Parallax=$PARALLAX, Material=$MATERIAL"
else
    echo "ERROR: Configuration file not found: $CONFIG_PATH"
    exit 1
fi

# --- Create a temporary directory for script operations ---
# Use the TEMP_DIR defined in config.sh if it's valid, otherwise create our own
if [ -z "$TEMP_DIR" ] || [ ! -d "$TEMP_DIR" ]; then
    TEMP_DIR=$(mktemp -d --tmpdir="$SCRIPT_DIR" radium_temp.XXXXXX)
    echo "Created temporary directory: $TEMP_DIR"
fi

# --- Dependency Resolution Function ---
# --- Improved dependency resolution function ---
resolve_dependencies() {
    echo "Resolving dependencies..."

    # --- Handle SQLite ---
    SQLITE_CMD=$(command -v sqlite3)
    if [ -n "$SQLITE_CMD" ] && [ -x "$SQLITE_CMD" ]; then
        echo "Found system SQLite: $SQLITE_CMD"
    else
        echo "Installing portable SQLite..."
        SQLITE_CMD="$PORTABLE_SQLITE_BIN"

        if [ ! -f "$SQLITE_CMD" ]; then
            if command -v wget &>/dev/null; then
                wget -q "$SQLITE_URL" -O "$TEMP_DIR/$SQLITE_ZIP"
            elif command -v curl &>/dev/null; then
                curl -s "$SQLITE_URL" -o "$TEMP_DIR/$SQLITE_ZIP"
            else
                echo "ERROR: Neither wget nor curl found. Cannot download SQLite."
                return 1
            fi

            if [ ! -f "$TEMP_DIR/$SQLITE_ZIP" ]; then
                echo "ERROR: Failed to download SQLite."
                return 1
            fi

            # Extract SQLite
            echo "Extracting SQLite..."
            mkdir -p "$TEMP_DIR/sqlite_extract"
            unzip -q "$TEMP_DIR/$SQLITE_ZIP" -d "$TEMP_DIR/sqlite_extract"

            # Find SQLite binary
            SQLITE_EXTRACT=$(find "$TEMP_DIR/sqlite_extract" -name "sqlite3" -type f | head -n 1)
            if [ -n "$SQLITE_EXTRACT" ]; then
                cp "$SQLITE_EXTRACT" "$SQLITE_CMD"
                chmod +x "$SQLITE_CMD"
                echo "Installed portable SQLite: $SQLITE_CMD"
            else
                echo "ERROR: Could not find sqlite3 binary in the archive."
                return 1
            fi

            # Clean up
            rm -rf "$TEMP_DIR/sqlite_extract" "$TEMP_DIR/$SQLITE_ZIP"
        else
            echo "Found existing portable SQLite: $SQLITE_CMD"
            # Ensure it's executable
            chmod +x "$SQLITE_CMD"
        fi
    fi

    # --- Handle ImageMagick ---
    PORTABLE_MAGICK_CMD="$PORTABLE_MAGICK_BIN"
    SYSTEM_MAGICK_CMD=$(command -v magick) # Find system magick

    echo "Setting up portable ImageMagick..."
    # Always download/overwrite the portable version
    echo "Downloading portable ImageMagick from $MAGICK_URL (ensuring specific version)..."
    if command -v wget &>/dev/null; then
        wget "$MAGICK_URL" -O "$PORTABLE_MAGICK_CMD"
    elif command -v curl &>/dev/null; then
        curl -L "$MAGICK_URL" -o "$PORTABLE_MAGICK_CMD"
    else
        echo "ERROR: Neither wget nor curl found. Cannot download ImageMagick."
        rm -f "$PORTABLE_MAGICK_CMD"
        # Indicate failure but don't exit yet, system version might exist
        PORTABLE_MAGICK_CMD=""
    fi

    if [ -f "$PORTABLE_MAGICK_CMD" ]; then
        chmod +x "$PORTABLE_MAGICK_CMD"
        # Basic check if it's executable
        if ! [ -x "$PORTABLE_MAGICK_CMD" ]; then
             echo "ERROR: Downloaded ImageMagick is not executable: $PORTABLE_MAGICK_CMD"
             rm -f "$PORTABLE_MAGICK_CMD" # Clean up bad download
             PORTABLE_MAGICK_CMD=""
        else
             echo "Successfully downloaded portable ImageMagick to $PORTABLE_MAGICK_CMD"
             # Set the primary command to the portable one initially
             MAGICK_CMD="$PORTABLE_MAGICK_CMD"
        fi
    else
        echo "Warning: Failed to download portable ImageMagick."
        PORTABLE_MAGICK_CMD="" # Mark portable as failed
    fi

    # If portable failed or doesn't exist, check system version
    if [ -z "$MAGICK_CMD" ]; then
        if [ -n "$SYSTEM_MAGICK_CMD" ] && [ -x "$SYSTEM_MAGICK_CMD" ]; then
            echo "Found and using system ImageMagick: $SYSTEM_MAGICK_CMD"
            MAGICK_CMD="$SYSTEM_MAGICK_CMD"
        else
             echo "ERROR: Portable ImageMagick failed, and no functional system ImageMagick found."
             return 1 # Critical failure if neither works
        fi
    fi

    # --- Handle BSA Tool ---
    echo "Installing portable BSA Tool..."
    BSATOOL_CMD="$PORTABLE_BSATOOL_BIN"

    if [ ! -f "$BSATOOL_CMD" ]; then
        if command -v wget &>/dev/null; then
            wget -q "$BSATOOL_URL" -O "$TEMP_DIR/$BSATOOL_ARCHIVE"
        elif command -v curl &>/dev/null; then
            curl -s -L "$BSATOOL_URL" -o "$TEMP_DIR/$BSATOOL_ARCHIVE"
        else
            echo "ERROR: Neither wget nor curl found. Cannot download BSA Tool."
            return 1
        fi

        if [ ! -f "$TEMP_DIR/$BSATOOL_ARCHIVE" ]; then
            echo "ERROR: Failed to download BSA Tool archive."
            return 1
        fi

        # Extract BSA Tool
        echo "Extracting BSA Tool..."
        mkdir -p "$TEMP_DIR/bsatool_extract"
        tar -xzf "$TEMP_DIR/$BSATOOL_ARCHIVE" -C "$TEMP_DIR/bsatool_extract"

        # Find BSA Tool binaries and libraries
        BSATOOL_EXTRACT=$(find "$TEMP_DIR/bsatool_extract" -name "bsatool" -type f -executable | head -n 1)
        BSATOOL_X86_64_EXTRACT=$(find "$TEMP_DIR/bsatool_extract" -name "bsatool.x86_64" -type f -executable | head -n 1)

        if [ -n "$BSATOOL_EXTRACT" ] && [ -n "$BSATOOL_X86_64_EXTRACT" ]; then
            mkdir -p "$PORTABLE_BSATOOL_DIR"
            cp "$BSATOOL_EXTRACT" "$BSATOOL_CMD"
            cp "$BSATOOL_X86_64_EXTRACT" "$PORTABLE_BSATOOL_DIR/bsatool.x86_64"
            chmod +x "$BSATOOL_CMD"
            chmod +x "$PORTABLE_BSATOOL_DIR/bsatool.x86_64"

            # Copy required lib files
            mkdir -p "$PORTABLE_BSATOOL_DIR/lib"
            BSATOOL_LIB_DIR=$(find "$TEMP_DIR/bsatool_extract" -name "lib" -type d | head -n 1)

            if [ -n "$BSATOOL_LIB_DIR" ]; then
                cp -r "$BSATOOL_LIB_DIR"/* "$PORTABLE_BSATOOL_DIR/lib/"
                echo "Copied lib files to $PORTABLE_BSATOOL_DIR/lib/"
            else
                echo "WARNING: Could not find lib directory for BSA Tool."
            fi

            echo "Installed portable BSA Tool: $BSATOOL_CMD"
        else
            echo "ERROR: Could not find required BSA Tool binaries in the archive."
            return 1
        fi

        # Clean up
        rm -rf "$TEMP_DIR/bsatool_extract" "$TEMP_DIR/$BSATOOL_ARCHIVE"
    else
        echo "Found existing portable BSA Tool: $BSATOOL_CMD"
        # Ensure it's executable
        chmod +x "$BSATOOL_CMD"
    fi

    # Verify dependencies
    echo "Dependency resolution complete."
    echo "SQLite: $SQLITE_CMD"
    # Report which Magick is initially selected
    if [ "$MAGICK_CMD" == "$PORTABLE_MAGICK_CMD" ]; then
        echo "ImageMagick: $MAGICK_CMD (Portable - preferred)"
    elif [ "$MAGICK_CMD" == "$SYSTEM_MAGICK_CMD" ]; then
        echo "ImageMagick: $MAGICK_CMD (System - fallback)"
    else
        echo "ImageMagick: Not configured!" # Should not happen if logic is correct
    fi
    echo "BSA Tool: $BSATOOL_CMD"

    # Verify that we have all required tools (including a working Magick CMD)
    if [ -z "$SQLITE_CMD" ] || [ ! -x "$SQLITE_CMD" ]; then
        echo "ERROR: SQLite command not found or not executable."
        return 1
    fi

    if [ -z "$MAGICK_CMD" ] || [ ! -x "$MAGICK_CMD" ]; then
        echo "ERROR: ImageMagick command not found or not executable."
        return 1
    fi

    if [ -z "$BSATOOL_CMD" ] || [ ! -x "$BSATOOL_CMD" ]; then
        echo "ERROR: BSA Tool command not found or not executable."
        return 1
    fi

    return 0
}

# --- Source utils.sh ---
UTILS_PATH="$LIBS_DIR/utils.sh"
if [ -f "$UTILS_PATH" ]; then
    echo "Loading utilities: $UTILS_PATH"
    source "$UTILS_PATH"
else
    echo "ERROR: Required utilities file not found: $UTILS_PATH"
    exit 1
fi

# --- Modified extract.sh functionality ---
# Extract BSA files using bsatool
extract_bsa_files() {
    echo "$(date) Starting BSA extraction with bsatool..." >> "$LOG_FILE"

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

    echo "Starting BSA extraction using bsatool with $bsa_thread_limit parallel processes..."
    update_progress 25

    # Verify bsatool is available
    if [ -z "$BSATOOL_CMD" ] || [ ! -x "$BSATOOL_CMD" ]; then
        echo "ERROR: BSA Tool command not found or not executable: $BSATOOL_CMD" | tee -a "$LOG_FILE"
        return 1
    fi

    # Export library path for bsatool
    if [ -d "$PORTABLE_BSATOOL_DIR/lib" ]; then
        export LD_LIBRARY_PATH="$LIBS_DIR/lib:$LD_LIBRARY_PATH"
        echo "Set LD_LIBRARY_PATH to include $PORTABLE_BSATOOL_DIR/lib"
    fi

    # Array to store all extraction PIDs for waiting
    EXTRACT_PIDS=()
    RUNNING_EXTRACTIONS=0

    # Generate the mod order CSV if it doesn't exist
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

    # Function to extract and process a single mod (both BSA and loose files)
    process_single_mod() {
        local MOD_NAME="$1"
        local MOD_PATH="$2"
        local MOD_INDEX="$3"
        local OUTPUT_DIR="$4"
        local PROGRESS_FILE="$5"
        local EXTRACTION_LOG="$6"

        echo "Processing mod [$MOD_INDEX]: $MOD_NAME ($MOD_PATH)" | tee -a "$EXTRACTION_LOG"

        # Skip if mod path is empty or doesn't exist
        if [ -z "$MOD_PATH" ] || [ ! -d "$MOD_PATH" ]; then
            echo "  Skipping mod (invalid path): $MOD_NAME" | tee -a "$EXTRACTION_LOG"
            atomic_increment "$PROGRESS_FILE"
            return 0
        fi

        # 1. First extract any BSA files in this mod
        local BSA_COUNT=0
        find "$MOD_PATH" -type f -name "*.bsa" 2>/dev/null | while read -r bsa_file; do
            if [ -f "$bsa_file" ]; then
                BSA_COUNT=$((BSA_COUNT + 1))
                local BSA_NAME=$(basename "$bsa_file")
                echo "  Extracting BSA [$BSA_COUNT]: $BSA_NAME" | tee -a "$EXTRACTION_LOG"

                # Create a unique subdirectory for temporary extraction
                local UNIQUE_EXTRACT_DIR=$(mktemp -d --tmpdir="$TEMP_DIR" bsa_extract_XXXXXX)

                # Run bsatool to extract the BSA
                if [ "$VERBOSE" -eq 1 ]; then
                    "$BSATOOL_CMD" extractall "$bsa_file" "$UNIQUE_EXTRACT_DIR" >> "$EXTRACTION_LOG" 2>&1
                else
                    "$BSATOOL_CMD" extractall "$bsa_file" "$UNIQUE_EXTRACT_DIR" > /dev/null 2>&1
                fi
                local BSATOOL_EXIT_CODE=$?

                if [ "$BSATOOL_EXIT_CODE" -ne 0 ]; then
                    echo "  ERROR: Failed to extract $BSA_NAME (bsatool exit code: $BSATOOL_EXIT_CODE)" | tee -a "$EXTRACTION_LOG"
                else
                    # Copy extracted textures to output directory
                    local extracted_textures_dir="$UNIQUE_EXTRACT_DIR/textures"
                    if [ -d "$extracted_textures_dir" ]; then
                        # Create output textures directory if needed
                        mkdir -p "$OUTPUT_DIR/textures"

                        # Copy all DDS files, preserving directory structure
                        # Use cp -al for hard linking when possible
                        if find "$extracted_textures_dir" -type f -name "*.dds" | grep -q .; then
                            if cp -al "$extracted_textures_dir"/* "$OUTPUT_DIR/textures/" 2>/dev/null; then
                                echo "  Successfully copied textures from $BSA_NAME using hard links" | tee -a "$EXTRACTION_LOG"
                            else
                                # Fallback to regular copy if hard linking fails
                                cp -a "$extracted_textures_dir"/* "$OUTPUT_DIR/textures/" 2>/dev/null
                                echo "  Copied textures from $BSA_NAME (hard links failed, used regular copy)" | tee -a "$EXTRACTION_LOG"
                            fi

                            local DDS_COUNT=$(find "$extracted_textures_dir" -type f -name "*.dds" | wc -l)
                            echo "  Found $DDS_COUNT DDS files in $BSA_NAME" | tee -a "$EXTRACTION_LOG"
                        else
                            echo "  No DDS files found in $BSA_NAME" | tee -a "$EXTRACTION_LOG"
                        fi
                    else
                        echo "  No textures directory found in $BSA_NAME" | tee -a "$EXTRACTION_LOG"
                    fi
                fi

                # Clean up temporary extraction directory
                rm -rf "$UNIQUE_EXTRACT_DIR"
            fi
        done

        # 2. Now copy any loose texture files from this mod
        if [ -d "$MOD_PATH/textures" ]; then
            echo "  Copying loose texture files from: $MOD_NAME" | tee -a "$EXTRACTION_LOG"

            # Create output textures directory if needed
            mkdir -p "$OUTPUT_DIR/textures"

            # Try hard linking first, fall back to regular copy
            if find "$MOD_PATH/textures" -type f -name "*.dds" | grep -q .; then
                if cp -al "$MOD_PATH/textures"/* "$OUTPUT_DIR/textures/" 2>/dev/null; then
                    echo "  Successfully copied loose textures using hard links" | tee -a "$EXTRACTION_LOG"
                else
                    # Fallback to regular copy
                    cp -a "$MOD_PATH/textures"/* "$OUTPUT_DIR/textures/" 2>/dev/null
                    echo "  Copied loose textures (hard links failed, used regular copy)" | tee -a "$EXTRACTION_LOG"
                fi

                local LOOSE_DDS_COUNT=$(find "$MOD_PATH/textures" -type f -name "*.dds" | wc -l)
                echo "  Found $LOOSE_DDS_COUNT loose DDS files" | tee -a "$EXTRACTION_LOG"
            else
                echo "  No loose DDS files found" | tee -a "$EXTRACTION_LOG"
            fi
        else
            echo "  No loose textures directory found for this mod" | tee -a "$EXTRACTION_LOG"
        fi

        # Update progress
        atomic_increment "$PROGRESS_FILE"
        return 0
    }

    # Monitor extraction progress
    monitor_extract_progress() {
        local total=$1
        local progress_file=$2

        while true; do
            sleep 1
            local current=$(cat "$progress_file" 2>/dev/null || echo 0)

            # Check if we're done
            if [ "$current" -ge "$total" ]; then
                better_progress_bar "$current" "$total" "Mod Processing"
                break
            fi

            # Check if parent process is still running
            if ! ps -p $$ > /dev/null; then
                break
            fi

            better_progress_bar "$current" "$total" "Mod Processing"
        done
        echo "" # New line after progress bar
    }

    # Process all mods
    if [ "$HAS_MOD_ORDER_CSV" -eq 1 ]; then
        # Initialize counters for game files
        local GAME_FILES_PROCESSED=0

        # 1. Process game files first (lowest priority)
        if [ -d "$GAME_DIR" ]; then
            echo "Processing base game files (lowest priority)..." | tee -a "$EXTRACTION_LOG"

            # Process game BSA files
            find "$GAME_DIR" -type f -name "*.bsa" 2>/dev/null | while read -r bsa_file; do
                if [ -f "$bsa_file" ]; then
                    local BSA_NAME=$(basename "$bsa_file")
                    echo "Extracting game BSA: $BSA_NAME" | tee -a "$EXTRACTION_LOG"

                    # Create a unique subdirectory for temporary extraction
                    local UNIQUE_EXTRACT_DIR=$(mktemp -d --tmpdir="$TEMP_DIR" bsa_extract_XXXXXX)

                    # Run bsatool to extract the BSA
                    if [ "$VERBOSE" -eq 1 ]; then
                        "$BSATOOL_CMD" extractall "$bsa_file" "$UNIQUE_EXTRACT_DIR" >> "$EXTRACTION_LOG" 2>&1
                    else
                        "$BSATOOL_CMD" extractall "$bsa_file" "$UNIQUE_EXTRACT_DIR" > /dev/null 2>&1
                    fi
                    local BSATOOL_EXIT_CODE=$?

                    if [ "$BSATOOL_EXIT_CODE" -ne 0 ]; then
                        echo "ERROR: Failed to extract game BSA $BSA_NAME (bsatool exit code: $BSATOOL_EXIT_CODE)" | tee -a "$EXTRACTION_LOG"
                    else
                        # Copy extracted textures to output directory
                        local extracted_textures_dir="$UNIQUE_EXTRACT_DIR/textures"
                        if [ -d "$extracted_textures_dir" ]; then
                            # Create output textures directory if needed
                            mkdir -p "$VRAMR_TEMP/Output/textures"

                            # Copy all DDS files, preserving directory structure
                            if find "$extracted_textures_dir" -type f -name "*.dds" | grep -q .; then
                                if cp -al "$extracted_textures_dir"/* "$VRAMR_TEMP/Output/textures/" 2>/dev/null; then
                                    echo "Successfully copied game textures from $BSA_NAME using hard links" | tee -a "$EXTRACTION_LOG"
                                else
                                    # Fallback to regular copy if hard linking fails
                                    cp -a "$extracted_textures_dir"/* "$VRAMR_TEMP/Output/textures/" 2>/dev/null
                                    echo "Copied game textures from $BSA_NAME (hard links failed, used regular copy)" | tee -a "$EXTRACTION_LOG"
                                fi

                                local DDS_COUNT=$(find "$extracted_textures_dir" -type f -name "*.dds" | wc -l)
                                echo "Found $DDS_COUNT DDS files in game BSA $BSA_NAME" | tee -a "$EXTRACTION_LOG"
                                GAME_FILES_PROCESSED=$((GAME_FILES_PROCESSED + DDS_COUNT))
                            else
                                echo "No DDS files found in game BSA $BSA_NAME" | tee -a "$EXTRACTION_LOG"
                            fi
                        else
                            echo "No textures directory found in game BSA $BSA_NAME" | tee -a "$EXTRACTION_LOG"
                        fi
                    fi

                    # Clean up temporary extraction directory
                    rm -rf "$UNIQUE_EXTRACT_DIR"
                fi
            done

            # Process loose game texture files
            if [ -d "$GAME_DIR/textures" ]; then
                echo "Copying loose game texture files..." | tee -a "$EXTRACTION_LOG"

                # Create output textures directory if needed
                mkdir -p "$VRAMR_TEMP/Output/textures"

                # Try hard linking first, fall back to regular copy
                if find "$GAME_DIR/textures" -type f -name "*.dds" | grep -q .; then
                    if cp -al "$GAME_DIR/textures"/* "$VRAMR_TEMP/Output/textures/" 2>/dev/null; then
                        echo "Successfully copied loose game textures using hard links" | tee -a "$EXTRACTION_LOG"
                    else
                        # Fallback to regular copy
                        cp -a "$GAME_DIR/textures"/* "$VRAMR_TEMP/Output/textures/" 2>/dev/null
                        echo "Copied loose game textures (hard links failed, used regular copy)" | tee -a "$EXTRACTION_LOG"
                    fi

                    local LOOSE_DDS_COUNT=$(find "$GAME_DIR/textures" -type f -name "*.dds" | wc -l)
                    echo "Found $LOOSE_DDS_COUNT loose game DDS files" | tee -a "$EXTRACTION_LOG"
                    GAME_FILES_PROCESSED=$((GAME_FILES_PROCESSED + LOOSE_DDS_COUNT))
                else
                    echo "No loose game DDS files found" | tee -a "$EXTRACTION_LOG"
                fi
            else
                echo "No loose game textures directory found" | tee -a "$EXTRACTION_LOG"
            fi

            echo "Processed $GAME_FILES_PROCESSED game files" | tee -a "$EXTRACTION_LOG"
        fi

        # 2. Now process mods from CSV (respecting load order)
        echo "Processing mods according to load order from CSV..." | tee -a "$EXTRACTION_LOG"

        # Count total mods for progress tracking
        local TOTAL_MODS=$(tail -n +2 "$VRAMR_TEMP/ActiveModListOrder.csv" | wc -l)
        echo "Found $TOTAL_MODS mods in CSV" | tee -a "$EXTRACTION_LOG"

        # Start progress monitor
        monitor_extract_progress "$TOTAL_MODS" "$PROGRESS_FILE" &
        local MONITOR_PID=$!

        # Process mods in parallel (respecting thread limit)
        local MOD_INDEX=0
        tail -n +2 "$VRAMR_TEMP/ActiveModListOrder.csv" | while IFS=, read -r index mod_name active mod_path; do
            # Remove quotes from mod_path if present
            mod_path="${mod_path%\"}"
            mod_path="${mod_path#\"}"
            mod_path="${mod_path%\'}"
            mod_path="${mod_path#\'}"

            # Trim leading/trailing whitespace
            mod_path="$(echo "$mod_path" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
            MOD_INDEX=$((MOD_INDEX + 1))

            # Process this mod (BSA and loose files)
            process_single_mod "$mod_name" "$mod_path" "$MOD_INDEX" "$VRAMR_TEMP/Output" "$PROGRESS_FILE" "$EXTRACTION_LOG" &

            # Store PID and count
            local PID=$!
            EXTRACT_PIDS+=($PID)
            RUNNING_EXTRACTIONS=$((RUNNING_EXTRACTIONS + 1))

            # Limit parallel extractions
            if [ $RUNNING_EXTRACTIONS -ge $bsa_thread_limit ]; then
                wait -n  # Wait for any child process to exit
                RUNNING_EXTRACTIONS=$((RUNNING_EXTRACTIONS - 1))
            fi
        done
    else
        # Fallback: Just find all BSA files and extract them
        echo "No mod order CSV found. Extracting all BSA files without respecting load order..." | tee -a "$EXTRACTION_LOG"

        # Find all BSA files
        local ALL_BSA_FILES=()
        if [ -d "$GAME_DIR" ]; then
            while IFS= read -r -d '' bsa_file; do
                ALL_BSA_FILES+=("$bsa_file")
            done < <(find "$GAME_DIR" -type f -name "*.bsa" -print0 2>/dev/null)
        fi

        if [ -d "$MODS_DIR" ]; then
            while IFS= read -r -d '' bsa_file; do
                ALL_BSA_FILES+=("$bsa_file")
            done < <(find "$MODS_DIR" -type f -name "*.bsa" -print0 2>/dev/null)
        fi

        # Count for progress tracking
        local TOTAL_BSA_FILES=${#ALL_BSA_FILES[@]}
        echo "Found $TOTAL_BSA_FILES BSA files to extract" | tee -a "$EXTRACTION_LOG"

        # Start progress monitor
        monitor_extract_progress "$TOTAL_BSA_FILES" "$PROGRESS_FILE" &
        local MONITOR_PID=$!

        # Process each BSA file
        for bsa_file in "${ALL_BSA_FILES[@]}"; do
            local BSA_NAME=$(basename "$bsa_file")
            echo "Extracting BSA: $BSA_NAME" | tee -a "$EXTRACTION_LOG"

            # Create a unique subdirectory for temporary extraction
            local UNIQUE_EXTRACT_DIR=$(mktemp -d --tmpdir="$TEMP_DIR" bsa_extract_XXXXXX)

            # Run bsatool to extract the BSA in background
            (
                if [ "$VERBOSE" -eq 1 ]; then
                    "$BSATOOL_CMD" extractall "$bsa_file" "$UNIQUE_EXTRACT_DIR" >> "$EXTRACTION_LOG" 2>&1
                else
                    "$BSATOOL_CMD" extractall "$bsa_file" "$UNIQUE_EXTRACT_DIR" > /dev/null 2>&1
                fi
                local BSATOOL_EXIT_CODE=$?

                if [ "$BSATOOL_EXIT_CODE" -ne 0 ]; then
                    echo "ERROR: Failed to extract $BSA_NAME (bsatool exit code: $BSATOOL_EXIT_CODE)" | tee -a "$EXTRACTION_LOG"
                else
                    # Copy extracted textures to output directory
                    local extracted_textures_dir="$UNIQUE_EXTRACT_DIR/textures"
                    if [ -d "$extracted_textures_dir" ]; then
                        # Create output textures directory if needed
                        mkdir -p "$VRAMR_TEMP/Output/textures"

                        # Copy all DDS files, preserving directory structure
                        if find "$extracted_textures_dir" -type f -name "*.dds" | grep -q .; then
                            if cp -al "$extracted_textures_dir"/* "$VRAMR_TEMP/Output/textures/" 2>/dev/null; then
                                echo "Successfully copied textures from $BSA_NAME using hard links" | tee -a "$EXTRACTION_LOG"
                            else
                                # Fallback to regular copy if hard linking fails
                                cp -a "$extracted_textures_dir"/* "$VRAMR_TEMP/Output/textures/" 2>/dev/null
                                echo "Copied textures from $BSA_NAME (hard links failed, used regular copy)" | tee -a "$EXTRACTION_LOG"
                            fi

                            local DDS_COUNT=$(find "$extracted_textures_dir" -type f -name "*.dds" | wc -l)
                            echo "Found $DDS_COUNT DDS files in $BSA_NAME" | tee -a "$EXTRACTION_LOG"
                        else
                            echo "No DDS files found in $BSA_NAME" | tee -a "$EXTRACTION_LOG"
                        fi
                    else
                        echo "No textures directory found in $BSA_NAME" | tee -a "$EXTRACTION_LOG"
                    fi
                fi

                # Clean up temporary extraction directory
                rm -rf "$UNIQUE_EXTRACT_DIR"

                # Update progress
                atomic_increment "$PROGRESS_FILE"
            ) &

            # Store PID and count
            local PID=$!
            EXTRACT_PIDS+=($PID)
            RUNNING_EXTRACTIONS=$((RUNNING_EXTRACTIONS + 1))

            # Limit parallel extractions
            if [ $RUNNING_EXTRACTIONS -ge $bsa_thread_limit ]; then
                wait -n  # Wait for any child process to exit
                RUNNING_EXTRACTIONS=$((RUNNING_EXTRACTIONS - 1))
            fi
        done

        # Now process loose files
        echo "Processing loose texture files..." | tee -a "$EXTRACTION_LOG"
        if [ -d "$GAME_DIR/textures" ]; then
            echo "Copying game loose textures..." | tee -a "$EXTRACTION_LOG"
            mkdir -p "$VRAMR_TEMP/Output/textures"
            cp -a "$GAME_DIR/textures"/* "$VRAMR_TEMP/Output/textures/" 2>/dev/null
        fi

        if [ -d "$MODS_DIR" ]; then
            find "$MODS_DIR" -path "*/textures" -type d | while read -r textures_dir; do
                echo "Copying loose textures from: $textures_dir" | tee -a "$EXTRACTION_LOG"
                mkdir -p "$VRAMR_TEMP/Output/textures"
                cp -a "$textures_dir"/* "$VRAMR_TEMP/Output/textures/" 2>/dev/null
            done
        fi
    fi

    # Wait for all extraction processes to finish
    for pid in "${EXTRACT_PIDS[@]}"; do
        wait $pid 2>/dev/null || true
    done

    # Wait for the monitor to finish
    wait $MONITOR_PID 2>/dev/null || true

    # Count the actual number of extracted files
    local DDS_COUNT=$(find "$VRAMR_TEMP/Output/textures" -type f -name "*.dds" | wc -l)
    echo "Processing complete. Extracted/copied $DDS_COUNT DDS files."
    echo "$(date) Processing complete. Extracted/copied $DDS_COUNT DDS files." >> "$LOG_FILE"

    # Clean up
    rm -f "$PROGRESS_FILE" "$PROGRESS_FILE.lock"

    update_progress 55
    flush

    # Restore original thread count
    THREAD_COUNT=$original_thread_count
    echo "Restored thread count to $THREAD_COUNT for subsequent operations."
    return 0
}

# --- Process exclusions using native Linux tools ---
process_exclusions() {
    echo "$(date) Processing Exclusions with Native Linux Tools..." >> "$LOG_FILE"
    echo "Processing exclusion patterns with native Linux tools..."
    update_progress 55

    # Define Exclusion Patterns
    shopt -s extglob nocaseglob

    # File pattern exclusions
    local file_exclusions=(
        '*_color.dds' '*_emissive.dds' '*_normal.dds' '*_opengl.dds' 'icewall*.dds'
        '*drj*.dds' '*envmask.dds' '*_g.dds' '*_s.dds' '*_sk.dds' '*_b.dds'
        '*_a.dds' '*_e.dds' '*_h.dds'
        'pot_n.dds' 'tg_field_rocks.dds' 'tg_field_rocks_n.dds' 'tg_snow_pebbles.dds'
        'tg_snow_pebbles_n.dds' 'clgorehowl*.dds' 'woodcut.dds' 'woodcut_n.dds'
        'dummy.dds' '*lod*_p.dds' 'default_n.dds' 'basket01.dds'
    )

    # Directory exclusions - fixed to use substring matches without trailing slashes
    local dir_exclusions=(
        "/!_Rudy_Misc" "/!SR" "/!!SR" "/interface" "/effects03/newmiller/jewels2"
        "/littlebaron" "/luxonbeacon" "/landscape/mountains" "/landscape/rocks"
        "/terrain" "/lod" "/DynDOLOD" "/LODGen"
    )

    local EXCLUSIONS_LOG="$VRAMR_TEMP/logfiles/exclusions.log"
    > "$EXCLUSIONS_LOG"
    local OUTPUT_TEXTURES_DIR="$VRAMR_TEMP/Output/textures"

    # Find all DDS files in output
    echo "Scanning for files to exclude in $OUTPUT_TEXTURES_DIR..."
    local ALL_FILES_LIST=$(mktemp --tmpdir="$TEMP_DIR" exclude_files.XXXXXX)
    find "$OUTPUT_TEXTURES_DIR" -type f -iname "*.dds" -print0 > "$ALL_FILES_LIST"
    local TOTAL_FILES=$(tr -d -c '\0' < "$ALL_FILES_LIST" | wc -c)
    echo "Found $TOTAL_FILES DDS files to process for exclusions"

    if [ "$TOTAL_FILES" -eq 0 ]; then
        echo "No DDS files found in output to exclude."
        echo "$(date) No DDS files found in output to exclude." >> "$LOG_FILE"
        rm -f "$ALL_FILES_LIST"
        update_progress 60
        return
    fi

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" exclude_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    local EXCLUDED_COUNT_FILE=$(mktemp --tmpdir="$TEMP_DIR" exclude_count.XXXXXX)
    echo "0" > "$EXCLUDED_COUNT_FILE"
    touch "$EXCLUDED_COUNT_FILE.lock"

    # Progress monitor
    monitor_exclusion_progress() {
        local total=$1
        local progress_file=$2
        while true; do
            sleep 1
            local current_processed=$(cat "$progress_file" 2>/dev/null || echo 0)
            # Ensure current_processed has a value
            current_processed=${current_processed:-0}
            if [ "$current_processed" -ge "$total" ]; then
                better_progress_bar "$current_processed" "$total" "Exclusions"
                break
            fi
            if ! ps -p $$ > /dev/null; then break; fi
            better_progress_bar "$current_processed" "$total" "Exclusions"
        done
        local final_processed=$(cat "$progress_file" 2>/dev/null || echo "$total")
        # Ensure final_processed has a value
        final_processed=${final_processed:-$total}
        better_progress_bar "$final_processed" "$total" "Exclusions"
        echo ""
    }

    monitor_exclusion_progress "$TOTAL_FILES" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # Create a simple exclusion script
    local EXCLUSION_SCRIPT=$(mktemp --tmpdir="$TEMP_DIR" exclusion_script.XXXXXX)

    # Write the file pattern exclusions to a file
    local FILE_PATTERNS_FILE=$(mktemp --tmpdir="$TEMP_DIR" file_patterns.XXXXXX)
    for pattern in "${file_exclusions[@]}"; do
        echo "$pattern" >> "$FILE_PATTERNS_FILE"
    done

    # Write the directory pattern exclusions to a file
    local DIR_PATTERNS_FILE=$(mktemp --tmpdir="$TEMP_DIR" dir_patterns.XXXXXX)
    for pattern in "${dir_exclusions[@]}"; do
        echo "$pattern" >> "$DIR_PATTERNS_FILE"
    done

    # Write the exclusion script
    cat > "$EXCLUSION_SCRIPT" << 'EOF'
#!/bin/bash
# Simple exclusion script

file="$1"
progress_file="$2"
excluded_count_file="$3"
exclusions_log="$4"
output_dir="$5"
file_patterns_file="$6"
dir_patterns_file="$7"
log_file="$8"

filename=$(basename "$file")
rel_path="${file#$output_dir/}"
excluded=0

# Check file patterns
while IFS= read -r pattern; do
    if [[ "$filename" == $pattern ]]; then
        excluded=1
        break
    fi
done < "$file_patterns_file"

# Check directory patterns if not already excluded
if [ "$excluded" -eq 0 ]; then
    while IFS= read -r pattern; do
        if [[ "/$rel_path" == *"$pattern"* ]]; then
            excluded=1
            break
        fi
    done < "$dir_patterns_file"
fi

# Remove if excluded
if [ "$excluded" -eq 1 ]; then
    if rm -f "$file" 2>/dev/null; then
        echo "Excluded: $rel_path" >> "$exclusions_log"
        # Increment excluded count
        (
            flock -x 201
            current=$(cat "$excluded_count_file" 2>/dev/null || echo 0)
            echo $((current + 1)) > "$excluded_count_file"
        ) 201>"$excluded_count_file.lock"
    else
        echo "Error removing excluded file: $file" >> "$log_file"
    fi
fi

# Update progress
(
    flock -x 200
    current=$(cat "$progress_file" 2>/dev/null || echo 0)
    echo $((current + 1)) > "$progress_file"
) 200>"$progress_file.lock"
EOF

    # Make script executable
    chmod +x "$EXCLUSION_SCRIPT"

    # Process files using either parallel or xargs
    if command -v parallel &> /dev/null; then
        echo "Using GNU parallel for exclusion processing..."
        tr '\0' '\n' < "$ALL_FILES_LIST" | \
        parallel -j "$THREAD_COUNT" "$EXCLUSION_SCRIPT" "{}" "$PROGRESS_FILE" "$EXCLUDED_COUNT_FILE" "$EXCLUSIONS_LOG" "$OUTPUT_TEXTURES_DIR" "$FILE_PATTERNS_FILE" "$DIR_PATTERNS_FILE" "$LOG_FILE"
    else
        echo "GNU parallel not found, using xargs..."
        xargs -0 -n 1 -P "$THREAD_COUNT" -I {} "$EXCLUSION_SCRIPT" {} "$PROGRESS_FILE" "$EXCLUDED_COUNT_FILE" "$EXCLUSIONS_LOG" "$OUTPUT_TEXTURES_DIR" "$FILE_PATTERNS_FILE" "$DIR_PATTERNS_FILE" "$LOG_FILE" < "$ALL_FILES_LIST"
    fi

    # Wait for all exclusion operations to complete
    wait

    # Wait for monitor
    wait $MONITOR_PID 2>/dev/null || true

    # Final counts
    local EXCLUDED_COUNT=$(cat "$EXCLUDED_COUNT_FILE")
    local PROCESSED_COUNT=$(cat "$PROGRESS_FILE")

    # Ensure final progress bar is 100%
    if [ "$PROCESSED_COUNT" -ge "$TOTAL_FILES" ]; then
        better_progress_bar "$TOTAL_FILES" "$TOTAL_FILES" "Exclusions"
        echo ""
    fi

    shopt -u extglob nocaseglob

    echo "Exclusion processing complete!"
    echo "Total files processed: $PROCESSED_COUNT"
    echo "Files excluded: $EXCLUDED_COUNT"
    echo "$(date) Exclusion processing complete. $EXCLUDED_COUNT files excluded." >> "$LOG_FILE"

    # Cleanup
    rm -f "$ALL_FILES_LIST" "$PROGRESS_FILE" "$PROGRESS_FILE.lock" "$EXCLUDED_COUNT_FILE" "$EXCLUDED_COUNT_FILE.lock"
    rm -f "$EXCLUSION_SCRIPT" "$FILE_PATTERNS_FILE" "$DIR_PATTERNS_FILE"

    # Remove empty directories
    find "$OUTPUT_TEXTURES_DIR" -type d -empty -delete 2>/dev/null || true

    update_progress 60
}

# --- Improved texture analysis function with better DDS header parsing ---
analyze_textures() {
    echo "$(date) Analyzing textures with direct DDS header parsing..." >> "$LOG_FILE"
    echo "Starting texture analysis with direct DDS header parsing..."
    update_progress 60

    local DB_FILE="$VRAMR_TEMP/Output/VRAMr.db"
    local OUTPUT_TEXTURES_DIR="$VRAMR_TEMP/Output/textures"
    echo "Creating texture database at $DB_FILE"

    # Check critical dependencies
    if [ -z "$SQLITE_CMD" ] || [ ! -x "$SQLITE_CMD" ]; then
        echo "ERROR: SQLite command not found or not executable: $SQLITE_CMD" | tee -a "$LOG_FILE"
        return 1
    fi

    # Initialize SQLite database with performance optimizations
    rm -f "$DB_FILE" "$DB_FILE-journal" "$DB_FILE-wal" "$DB_FILE-shm"

    "$SQLITE_CMD" "$DB_FILE" <<EOL
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = 10000;
PRAGMA page_size = 4096;
CREATE TABLE textures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    format TEXT,
    category TEXT,
    type TEXT,
    processed INTEGER DEFAULT 0,
    optimize_target_format TEXT,
    optimize_target_size INTEGER
);
CREATE INDEX idx_textures_path ON textures(path);
CREATE INDEX idx_textures_filename ON textures(filename);
CREATE INDEX idx_textures_type ON textures(type);
CREATE INDEX idx_textures_category ON textures(category);
CREATE INDEX idx_textures_processed ON textures(processed);
EOL

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to initialize SQLite database $DB_FILE" | tee -a "$LOG_FILE"
        return 1
    fi

    # Find texture files
    echo "Finding all DDS files in output directory for analysis..."
    local TEXTURE_FILES_LIST=$(mktemp --tmpdir="$TEMP_DIR" analyze_files.XXXXXX)
    find "$OUTPUT_TEXTURES_DIR" -type f -iname "*.dds" -print0 > "$TEXTURE_FILES_LIST"
    local TOTAL_FILES=$(tr -d -c '\0' < "$TEXTURE_FILES_LIST" | wc -c)
    echo "Found $TOTAL_FILES DDS files to analyze"

    if [ "$TOTAL_FILES" -eq 0 ]; then
        echo "No texture files found to analyze!"
        echo "$(date) No texture files found in output to analyze." >> "$LOG_FILE"
        rm -f "$TEXTURE_FILES_LIST"
        update_progress 69
        return 0
    fi

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" analyze_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    # Temporary SQL file
    local SQL_FILE=$(mktemp --tmpdir="$TEMP_DIR" analysis_sql.XXXXXX)
    echo "BEGIN TRANSACTION;" > "$SQL_FILE"
    touch "$SQL_FILE.lock"

    local ANALYSIS_LOG="$VRAMR_TEMP/logfiles/analysis.log"
    > "$ANALYSIS_LOG"

    # Progress monitor (unchanged)
    monitor_analysis_progress() {
        local total=$1
        local progress_file=$2
        while true; do
            sleep 1
            local current_analyzed=$(cat "$progress_file" 2>/dev/null || echo 0)
            # Ensure current_analyzed has a value
            current_analyzed=${current_analyzed:-0}
            if [ "$current_analyzed" -ge "$total" ]; then
                better_progress_bar "$current_analyzed" "$total" "Analysis"
                break
            fi
            if ! ps -p $$ > /dev/null; then break; fi
            better_progress_bar "$current_analyzed" "$total" "Analysis"
        done
        local final_analyzed=$(cat "$progress_file" 2>/dev/null || echo "$total")
        # Ensure final_analyzed has a value
        final_analyzed=${final_analyzed:-$total}
        better_progress_bar "$final_analyzed" "$total" "Analysis"
        echo ""
    }

    monitor_analysis_progress "$TOTAL_FILES" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # Create improved analysis script with proper DDS header parsing
    local ANALYSIS_SCRIPT=$(mktemp --tmpdir="$TEMP_DIR" analysis_script.XXXXXX)

    # Export the path to ImageMagick for use in the script
    export MAGICK_CMD

    cat > "$ANALYSIS_SCRIPT" << 'EOF'
#!/bin/bash
# Improved texture analysis script with direct DDS header parsing

file="$1"
progress_file="$2"
output_dir="$3"
analysis_log="$4"
sql_file="$5"
# MAGICK_CMD is exported from parent

# Get relative path and filename
rel_path="${file#$output_dir/}"
filename="$(basename "$file")"

# Initialize variables
width=0
height=0
format="unknown"
parsed_correctly=0

# Method 1: Direct DDS header parsing
if [ -f "$file" ] && [ -s "$file" ]; then
    # Check DDS magic bytes (first 4 bytes should be "DDS ")
    magic=$(dd if="$file" bs=4 count=1 2>/dev/null | xxd -p | tr -d '\n')

    if [ "$magic" = "44445320" ]; then  # "DDS " in hex
        # Extract height (bytes 12-15)
        height_hex=$(dd if="$file" bs=1 skip=12 count=4 2>/dev/null | xxd -p | tr -d '\n')

        # Convert from little-endian hex to decimal
        if [ ${#height_hex} -eq 8 ]; then
            # Reverse byte order for little-endian
            height_rev="${height_hex:6:2}${height_hex:4:2}${height_hex:2:2}${height_hex:0:2}"
            height=$((16#$height_rev))
        fi

        # Extract width (bytes 16-19)
        width_hex=$(dd if="$file" bs=1 skip=16 count=4 2>/dev/null | xxd -p | tr -d '\n')

        # Convert from little-endian hex to decimal
        if [ ${#width_hex} -eq 8 ]; then
            # Reverse byte order for little-endian
            width_rev="${width_hex:6:2}${width_hex:4:2}${width_hex:2:2}${width_hex:0:2}"
            width=$((16#$width_rev))
        fi

        # Validate dimensions
        if [ "$width" -gt 0 ] && [ "$width" -lt 16384 ] && [ "$height" -gt 0 ] && [ "$height" -lt 16384 ]; then
            format="DDS_HEADER"
            parsed_correctly=1
            echo "Success: Direct header parsing of $file: ${width}x${height}" >> "$analysis_log"
        fi
    fi
fi

# Method 2: Use ImageMagick if header parsing failed
if [ "$parsed_correctly" -eq 0 ] && [ -n "$MAGICK_CMD" ] && [ -x "$MAGICK_CMD" ]; then
    # Use identify to get dimensions
    dimensions=$("$MAGICK_CMD" identify -format "%wx%h" "$file" 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$dimensions" ]; then
        # Parse dimensions (format is typically WIDTHxHEIGHT)
        if [[ "$dimensions" =~ ^([0-9]+)x([0-9]+)$ ]]; then
            width="${BASH_REMATCH[1]}"
            height="${BASH_REMATCH[2]}"
            format="DDS_MAGICK"
            parsed_correctly=1
            echo "Success: ImageMagick parsed $file: ${width}x${height}" >> "$analysis_log"
        fi
    else
        echo "Warning: ImageMagick identify failed for $file" >> "$analysis_log"
    fi
fi

# Method 3: Fallback to file size estimation
if [ "$parsed_correctly" -eq 0 ]; then
    # Get file size
    file_size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)

    # Make educated guess based on file size
    if [ -n "$file_size" ]; then
        if [ "$file_size" -lt 65536 ]; then
            width=256; height=256; # Small texture
        elif [ "$file_size" -lt 262144 ]; then
            width=512; height=512; # Medium texture
        elif [ "$file_size" -lt 1048576 ]; then
            width=1024; height=1024; # Large texture
        elif [ "$file_size" -lt 4194304 ]; then
            width=2048; height=2048; # Very large texture
        else
            width=4096; height=4096; # Huge texture
        fi
        format="DDS_SIZE_ESTIMATED"
        parsed_correctly=1
        echo "Warning: Using size estimation for $file ($file_size bytes): ${width}x${height}" >> "$analysis_log"
    else
        # Last resort fallback
        width=512; height=512;
        format="DDS_DEFAULT"
        echo "Warning: All methods failed for $file. Using default size: ${width}x${height}" >> "$analysis_log"
    fi
fi

# Determine texture type based on filename
lower_filename=$(echo "$filename" | tr '[:upper:]' '[:lower:]')
lower_path=$(echo "$rel_path" | tr '[:upper:]' '[:lower:]')

# More accurate texture type detection based on filename patterns
type="other"
if [[ "$lower_filename" =~ (_n\.dds$|_normal\.dds$) ]]; then
    type="normal"
elif [[ "$lower_filename" =~ (_d\.dds$|_diffuse\.dds$|_albedo\.dds$) ]]; then
    type="diffuse"
elif [[ "$lower_filename" =~ (_p\.dds$|_parallax\.dds$|_height\.dds$) ]]; then
    type="parallax"
elif [[ "$lower_filename" =~ (_m\.dds$|_material\.dds$|_masks\.dds$|_specular\.dds$|_s\.dds$) ]]; then
    type="material"
elif [[ "$lower_filename" =~ (_g\.dds$|_glow\.dds$|_emissive\.dds$|_e\.dds$) ]]; then
    type="material" # Consider glow/emissive as material maps
elif [[ "$lower_filename" =~ (_sk\.dds$|_skin\.dds$) ]]; then
    type="skin"
fi

# Determine category from path
category="misc"
if [[ "$lower_path" == */architecture/* ]]; then
    category="architecture"
elif [[ "$lower_path" == */landscape/* || "$lower_path" == */terrain/* ]]; then
    category="landscape"
elif [[ "$lower_path" == */clutter/* ]]; then
    category="clutter"
elif [[ "$lower_path" == */actors/* || "$lower_path" == */character/* || "$lower_path" == */creatures/* ]]; then
    category="actors"
elif [[ "$lower_path" == */weapons/* ]]; then
    category="weapons"
elif [[ "$lower_path" == */armor/* ]]; then
    category="armor"
elif [[ "$lower_path" == */clothing/* ]]; then
    category="clothing"
elif [[ "$lower_path" == */effects/* ]]; then
    category="effects"
elif [[ "$lower_path" == */sky/* ]]; then
    category="sky"
elif [[ "$lower_path" == */interface/* ]]; then
    category="interface"
elif [[ "$lower_path" == */textures/lod/* || "$lower_path" == */terrain/lod/* ]]; then
    category="lod"
fi

# Prepare variables for SQL
sql_rel_path="$rel_path"
sql_filename="$filename"
sql_format="$format"
sql_category="$category"
sql_type="$type"

# Escape single quotes for SQL
sql_rel_path=$(echo "$sql_rel_path" | sed "s/'/''/g")
sql_filename=$(echo "$sql_filename" | sed "s/'/''/g")
sql_format=$(echo "$sql_format" | sed "s/'/''/g")
sql_category=$(echo "$sql_category" | sed "s/'/''/g")
sql_type=$(echo "$sql_type" | sed "s/'/''/g")

# Generate SQL and append to file
(
    flock -x 200
    echo "INSERT INTO textures (path, filename, width, height, format, category, type) VALUES ('$sql_rel_path', '$sql_filename', $width, $height, '$sql_format', '$sql_category', '$sql_type');" >> "$sql_file"
) 200>"$sql_file.lock"

# Update progress
(
    flock -x 201
    current=$(cat "$progress_file" 2>/dev/null || echo 0)
    echo $((current + 1)) > "$progress_file"
) 201>"$progress_file.lock"
EOF

    # Make script executable
    chmod +x "$ANALYSIS_SCRIPT"

    # Process files using either parallel or xargs
    if command -v parallel &>/dev/null; then
        echo "Using GNU parallel for texture analysis..."
        tr '\0' '\n' < "$TEXTURE_FILES_LIST" | \
        parallel -j "$THREAD_COUNT" "$ANALYSIS_SCRIPT" {} "$PROGRESS_FILE" "$OUTPUT_TEXTURES_DIR" "$ANALYSIS_LOG" "$SQL_FILE"
    else
        echo "GNU parallel not found, using xargs..."
        xargs -0 -n 1 -P "$THREAD_COUNT" -I {} "$ANALYSIS_SCRIPT" {} "$PROGRESS_FILE" "$OUTPUT_TEXTURES_DIR" "$ANALYSIS_LOG" "$SQL_FILE" < "$TEXTURE_FILES_LIST"
    fi

    # Wait for all analysis operations to complete
    wait

    # Wait for monitor
    wait $MONITOR_PID 2>/dev/null || true

    # Finalize SQL file and import to database
    echo "COMMIT;" >> "$SQL_FILE"

    # Import SQL data into database
    echo "Importing analysis data into database ($DB_FILE)..."
    "$SQLITE_CMD" "$DB_FILE" < "$SQL_FILE"

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to execute SQL commands in $DB_FILE." | tee -a "$LOG_FILE"
        return 1
    fi

    # Display stats
    local analyzed_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures;")
    echo "Texture analysis complete. Analyzed $analyzed_count textures."
    echo "Database created at: $DB_FILE"
    echo "$(date) Texture analysis complete - $analyzed_count textures analyzed." >> "$LOG_FILE"

    # Display analysis method statistics if verbose mode
    if [ "$VERBOSE" -eq 1 ]; then
        local header_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE format = 'DDS_HEADER';")
        local magick_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE format = 'DDS_MAGICK';")
        local estimated_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE format = 'DDS_SIZE_ESTIMATED';")
        local default_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE format = 'DDS_DEFAULT';")

        echo "Analysis Method Statistics:"
        echo "  - Direct DDS header parsing: $header_count textures"
        echo "  - ImageMagick identification: $magick_count textures"
        echo "  - Size estimation fallback: $estimated_count textures"
        echo "  - Default fallback: $default_count textures"

        echo "Analysis Method Statistics:" >> "$LOG_FILE"
        echo "  - Direct DDS header parsing: $header_count textures" >> "$LOG_FILE"
        echo "  - ImageMagick identification: $magick_count textures" >> "$LOG_FILE"
        echo "  - Size estimation fallback: $estimated_count textures" >> "$LOG_FILE"
        echo "  - Default fallback: $default_count textures" >> "$LOG_FILE"
    fi

    # Cleanup
    rm -f "$TEXTURE_FILES_LIST" "$PROGRESS_FILE" "$PROGRESS_FILE.lock" "$SQL_FILE" "$SQL_FILE.lock" "$ANALYSIS_SCRIPT"

    update_progress 69
    return 0
}

# --- Analyze textures safely (using ImageMagick with reduced threads) ---
analyze_textures_safely() {
    echo "$(date) Analyzing textures (safe mode)..." >> "$LOG_FILE"
    echo "Analyzing textures (using safe mode - 1 thread)..."

    local original_threads=$THREAD_COUNT
    THREAD_COUNT=1
    analyze_textures
    local exit_code=$?
    THREAD_COUNT=$original_threads

    if [ $exit_code -eq 0 ]; then
        echo "Texture analysis (safe mode) complete."
        echo "$(date) Texture analysis (safe mode) complete." >> "$LOG_FILE"
    else
         echo "Texture analysis (safe mode) failed. See logs."
         echo "$(date) Texture analysis (safe mode) failed." >> "$LOG_FILE"
    fi
    return $exit_code
}

# --- Native filtering implementation with optimized sizes ---
filter_textures() {
    echo "$(date) Filtering textures based on preset: $PRESET..." >> "$LOG_FILE"
    echo "Filtering textures based on preset: $PRESET (Exclusions handled previously)"
    update_progress 69

    local DB_FILE="$VRAMR_TEMP/Output/VRAMr.db"

    # Check for resolved SQLite command
    if [ -z "$SQLITE_CMD" ] || [ ! -x "$SQLITE_CMD" ]; then
        echo "ERROR: SQLite command not found or not executable: $SQLITE_CMD" | tee -a "$LOG_FILE"
        return 1
    fi

    if [ ! -f "$DB_FILE" ]; then
        echo "ERROR: Database file not found: $DB_FILE. Cannot filter." | tee -a "$LOG_FILE"
        return 1
    fi

    echo "Applying filters for Preset: $PRESET (D:$DIFFUSE N:$NORMAL P:$PARALLAX M:$MATERIAL)"

    # Filtering logic: Mark for resize (-2) or keep (1) based ONLY on dimensions vs preset.
    # Files that don't match a type or weren't excluded previously will be marked to keep (1).
    "$SQLITE_CMD" "$DB_FILE" <<EOL
-- Enable foreign keys and optimize processing
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;

-- Begin transaction for faster processing
BEGIN TRANSACTION;

-- Update diffuse textures
UPDATE textures SET
    processed = CASE
        WHEN width > $DIFFUSE OR height > $DIFFUSE THEN -2 -- Mark for downscale
        ELSE 1 -- Keep as is (at or below target)
    END,
    optimize_target_size = $DIFFUSE,
    optimize_target_format = 'diffuse'
WHERE type = 'diffuse';

-- Update normal textures
UPDATE textures SET
    processed = CASE
        WHEN width > $NORMAL OR height > $NORMAL THEN -2 -- Mark for downscale
        ELSE 1 -- Keep as is (at or below target)
    END,
    optimize_target_size = $NORMAL,
    optimize_target_format = 'normal'
WHERE type = 'normal';

-- Update parallax textures
UPDATE textures SET
    processed = CASE
        WHEN width > $PARALLAX OR height > $PARALLAX THEN -2 -- Mark for downscale
        ELSE 1 -- Keep as is (at or below target)
    END,
    optimize_target_size = $PARALLAX,
    optimize_target_format = 'parallax'
WHERE type = 'parallax';

-- Update material textures
UPDATE textures SET
    processed = CASE
        WHEN width > $MATERIAL OR height > $MATERIAL THEN -2 -- Mark for downscale
        ELSE 1 -- Keep as is (at or below target)
    END,
    optimize_target_size = $MATERIAL,
    optimize_target_format = 'material'
WHERE type = 'material';

-- REMOVED: Skip rules based on category, _glow.dds, and small dimensions.
-- Exclusions based on path/filename should have been handled by process_exclusions already.

-- Final catch-all: Mark any remaining unprocessed textures (e.g., type='other' or not matching above) to be kept.
-- If they weren't excluded earlier and don't need resizing based on a known type, keep them.
UPDATE textures SET processed = 1 WHERE processed = 0;

-- Commit all changes
COMMIT;
EOL

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to apply filters to database $DB_FILE" | tee -a "$LOG_FILE"
        return 1
    fi

    # Generate detailed statistics
    local filter_stats=$("$SQLITE_CMD" "$DB_FILE" "
SELECT
    'Total textures: ' || COUNT(*) AS statistics,
    'To resize: ' || SUM(CASE WHEN processed = -2 THEN 1 ELSE 0 END) AS to_resize,
    'To keep as-is: ' || SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) AS to_keep,
    'To skip: ' || SUM(CASE WHEN processed = -1 THEN 1 ELSE 0 END) AS to_skip,
    'By Type:' AS type_header,
    '  Diffuse: ' || SUM(CASE WHEN type = 'diffuse' THEN 1 ELSE 0 END) AS diffuse_count,
    '  Normal: ' || SUM(CASE WHEN type = 'normal' THEN 1 ELSE 0 END) AS normal_count,
    '  Parallax: ' || SUM(CASE WHEN type = 'parallax' THEN 1 ELSE 0 END) AS parallax_count,
    '  Material: ' || SUM(CASE WHEN type = 'material' THEN 1 ELSE 0 END) AS material_count,
    '  Other: ' || SUM(CASE WHEN type = 'other' THEN 1 ELSE 0 END) AS other_count,
    'Target Dimensions:' AS dimensions_header,
    '  Diffuse: ' || $DIFFUSE || 'px' AS diffuse_dim,
    '  Normal: ' || $NORMAL || 'px' AS normal_dim,
    '  Parallax: ' || $PARALLAX || 'px' AS parallax_dim,
    '  Material: ' || $MATERIAL || 'px' AS material_dim
FROM textures;
")

    echo "Filtering complete. Statistics:"
    echo "$filter_stats" | sed 's/|/\n/g'
    echo "$(date) Filtering complete with preset $PRESET" >> "$LOG_FILE"
    echo "$filter_stats" | sed 's/|/\n/g' >> "$LOG_FILE"

    update_progress 74
    return 0
}

# --- Delete textures marked as "skipped" or "keep as-is" ---
delete_skipped_textures() {
    echo "$(date) Deleting skipped and keep-as-is textures..." >> "$LOG_FILE"
    echo "Deleting textures marked to be skipped or kept as-is (leaving only those to be resized)..."
    update_progress 75 # Start progress for this step

    local DB_FILE="$VRAMR_TEMP/Output/VRAMr.db"
    local OUTPUT_TEXTURES_DIR="$VRAMR_TEMP/Output/textures"

    # Check dependencies
    if [ -z "$SQLITE_CMD" ] || [ ! -x "$SQLITE_CMD" ]; then
        echo "ERROR: SQLite command not found or not executable: $SQLITE_CMD" | tee -a "$LOG_FILE"
        return 1
    fi

    if [ ! -f "$DB_FILE" ]; then
        echo "ERROR: Database file not found: $DB_FILE. Cannot delete skipped files." | tee -a "$LOG_FILE"
        return 1
    fi

    local DELETE_LOG="$VRAMR_TEMP/logfiles/skipped_deletion.log"
    > "$DELETE_LOG"
    echo "Skipped/Keep-as-is texture deletion started at $(date)" >> "$DELETE_LOG"

    # Get count of textures to delete (skipped OR keep-as-is)
    local TEXTURES_TO_DELETE=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE processed = -1 OR processed = 1;")
    echo "Found $TEXTURES_TO_DELETE textures marked to be skipped or kept as-is and will be deleted" | tee -a "$DELETE_LOG"

    if [ "$TEXTURES_TO_DELETE" -eq 0 ]; then
        echo "No textures marked for deletion found."
        echo "$(date) No textures marked for deletion found." >> "$LOG_FILE"
        update_progress 80 # Progress update even if nothing to delete
        return 0
    fi

    # Create list of files to delete
    local DELETE_LIST_FILE=$(mktemp --tmpdir="$TEMP_DIR" delete_list.XXXXXX)
    # Select paths where processed is -1 OR 1, use printf '%s\0' for null termination
    "$SQLITE_CMD" "$DB_FILE" "SELECT path FROM textures WHERE processed = -1 OR processed = 1;" | while IFS= read -r line; do
        printf '%s\0' "$line"
    done > "$DELETE_LIST_FILE"

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" delete_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

    # Progress monitor
    monitor_delete_progress() {
        local total=$1
        local progress_file=$2
        while true; do
            sleep 1
            local current_processed=$(cat "$progress_file" 2>/dev/null || echo 0)
            current_processed=${current_processed:-0}
            if [ "$current_processed" -ge "$total" ]; then
                better_progress_bar "$current_processed" "$total" "Deleting Skipped"
                break
            fi
            if ! ps -p $$ > /dev/null; then break; fi # Check parent process
            better_progress_bar "$current_processed" "$total" "Deleting Skipped"
        done
        local final_processed=$(cat "$progress_file" 2>/dev/null || echo "$total")
        final_processed=${final_processed:-$total}
        better_progress_bar "$final_processed" "$total" "Deleting Skipped"
        echo ""
    }

    monitor_delete_progress "$TEXTURES_TO_DELETE" "$PROGRESS_FILE" &
    local MONITOR_PID=$!

    # Create deletion script
    local DELETE_SCRIPT=$(mktemp --tmpdir="$TEMP_DIR" delete_script.XXXXXX)
    cat > "$DELETE_SCRIPT" << 'EOF'
#!/bin/bash
rel_path="$1"
progress_file="$2"
output_textures_dir="$3"
delete_log="$4"

file_to_delete="$output_textures_dir/$rel_path"

if [ -f "$file_to_delete" ]; then
    if rm -f "$file_to_delete"; then
        echo "Deleted: $rel_path" >> "$delete_log"
    else
        echo "Error deleting: $file_to_delete" >> "$delete_log"
    fi
else
    echo "Skipped deletion (not found): $file_to_delete" >> "$delete_log"
fi

# Update progress atomically
(
    flock -x 200
    current=$(cat "$progress_file" 2>/dev/null || echo 0)
    echo $((current + 1)) > "$progress_file"
) 200>"$progress_file.lock"
EOF

    # Make script executable
    chmod +x "$DELETE_SCRIPT"

    # Process using parallel or xargs (using null-terminated list)
    if command -v parallel &>/dev/null; then
        echo "Using GNU parallel for deleting skipped files..."
        cat "$DELETE_LIST_FILE" | parallel -0 -j "$THREAD_COUNT" "$DELETE_SCRIPT" {} "$PROGRESS_FILE" "$OUTPUT_TEXTURES_DIR" "$DELETE_LOG"
    else
        echo "GNU parallel not found, using xargs..."
        xargs -0 -P "$THREAD_COUNT" -I {} "$DELETE_SCRIPT" {} "$PROGRESS_FILE" "$OUTPUT_TEXTURES_DIR" "$DELETE_LOG" < "$DELETE_LIST_FILE"
    fi

    # Wait for all delete operations
    wait

    # Wait for monitor
    wait $MONITOR_PID 2>/dev/null || true

    local final_count=$(cat "$PROGRESS_FILE" 2>/dev/null || echo "$TEXTURES_TO_DELETE")
    echo "Deletion of skipped/kept textures complete. Processed $final_count files." | tee -a "$DELETE_LOG"
    echo "$(date) Deletion of skipped/kept textures complete. Processed $final_count files." >> "$LOG_FILE"

    # Cleanup
    rm -f "$DELETE_LIST_FILE" "$PROGRESS_FILE" "$PROGRESS_FILE.lock" "$DELETE_SCRIPT"

    # Remove empty directories potentially left behind
    find "$OUTPUT_TEXTURES_DIR" -type d -empty -delete 2>/dev/null || true

    update_progress 80 # Update progress after this step
    return 0
}


# --- Streamlined texture optimization function with ImageMagick ---
optimize_textures() {
    echo "$(date) Starting texture optimization with ImageMagick..." >> "$LOG_FILE"
    echo "Starting texture optimization using ImageMagick..."
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

    # --- Runtime ImageMagick Check REMOVED ---
    # MAGICK_CMD should be set by resolve_dependencies (preferring portable, falling back to system)
    # We will rely on the LD_LIBRARY_PATH unset logic within the loop for the portable version.
    echo "Proceeding with optimization using ImageMagick: $MAGICK_CMD"
    echo "(Portable: $PORTABLE_MAGICK_CMD, System: $SYSTEM_MAGICK_CMD)"

    # If MAGICK_CMD is somehow empty here, it's an error from resolve_dependencies
    if [ -z "$MAGICK_CMD" ]; then
        echo "ERROR: No valid ImageMagick command configured by resolve_dependencies. Cannot optimize." | tee -a "$LOG_FILE"
        return 1
    fi

    # Create optimization log file
    local OPTIMIZATION_LOG="$VRAMR_TEMP/logfiles/optimization.log"
    > "$OPTIMIZATION_LOG"
    echo "Texture optimization started at $(date) using $MAGICK_CMD" >> "$OPTIMIZATION_LOG"

    # Create a temporary file to store IDs of successfully processed textures
    local SUCCESS_IDS_FILE=$(mktemp --tmpdir="$TEMP_DIR" success_ids.XXXXXX)
    touch "$SUCCESS_IDS_FILE.lock"

    # Get count of textures to optimize - focus ONLY on textures marked for resizing (-2)
    local TEXTURES_TO_OPTIMIZE=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE processed = -2;")
    echo "Found $TEXTURES_TO_OPTIMIZE textures to resize and optimize using $MAGICK_CMD" | tee -a "$OPTIMIZATION_LOG"

    if [ "$TEXTURES_TO_OPTIMIZE" -eq 0 ]; then
        echo "No textures require resizing. Optimization complete."
        echo "$(date) No textures require resizing. Optimization complete." >> "$LOG_FILE"
        update_progress 90
        return 0
    fi

    # Create a temp dir for optimization work
    mkdir -p "$VRAMR_TEMP/temp_optimize"

    # Progress tracking
    local PROGRESS_FILE=$(mktemp --tmpdir="$TEMP_DIR" optimize_progress.XXXXXX)
    echo "0" > "$PROGRESS_FILE"
    touch "$PROGRESS_FILE.lock"

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

    # Process textures in parallel
    echo "Processing $TEXTURES_TO_OPTIMIZE textures using $THREAD_COUNT threads..."

    # Query database for textures that need resizing
    "$SQLITE_CMD" -separator $'\t' "$DB_FILE" "SELECT id, path, optimize_target_size FROM textures WHERE processed = -2;" | \
    while IFS=$'\t' read -r id path target_size; do
        # Skip if no path
        if [ -z "$path" ]; then
            echo "Warning: Empty path for texture ID $id" >> "$OPTIMIZATION_LOG"
            atomic_increment "$PROGRESS_FILE"
            continue
        fi

        # Full path to texture file
        local texture_path="$OUTPUT_TEXTURES_DIR/$path"

        # Skip if file doesn't exist
        if [ ! -f "$texture_path" ]; then
            echo "Warning: Texture file not found: $texture_path" >> "$OPTIMIZATION_LOG"
            atomic_increment "$PROGRESS_FILE"
            continue
        fi

        # Process in background
        (
            # Temporary output path
            local temp_output="$VRAMR_TEMP/temp_optimize/$(basename "$path")"

            # Log operation
            echo "Optimizing texture: $path to target size $target_size using $MAGICK_CMD" >> "$OPTIMIZATION_LOG"

            # Construct the command with potential LD_LIBRARY_PATH unset for portable version
            local magick_run_cmd
            if [ "$MAGICK_CMD" == "$PORTABLE_MAGICK_CMD" ]; then
                # Unset LD_LIBRARY_PATH for the portable AppImage
                echo "(Using portable magick, unsetting LD_LIBRARY_PATH for execution)" >> "$OPTIMIZATION_LOG"
                magick_run_cmd=(env -u LD_LIBRARY_PATH "$MAGICK_CMD")
            else
                # Use system magick directly
                magick_run_cmd=("$MAGICK_CMD")
            fi

            # Run ImageMagick resize command
            if "${magick_run_cmd[@]}" "$texture_path" -resize "${target_size}x${target_size}\>" "$temp_output" 2>> "$OPTIMIZATION_LOG"; then
                # Check if output file was created successfully
                if [ -f "$temp_output" ] && [ -s "$temp_output" ]; then
                    # Copy back to original location
                    if cp "$temp_output" "$texture_path"; then
                        echo "✓ Successfully optimized: $path" >> "$OPTIMIZATION_LOG"

                        # Append successful ID to the list for batch update
                        ( flock -x 200; echo "$id" >> "$SUCCESS_IDS_FILE" ) 200>"$SUCCESS_IDS_FILE.lock"

                        # REMOVED direct database update:
                        # "$SQLITE_CMD" "$DB_FILE" "UPDATE textures SET processed = 2 WHERE id = $id;"
                    else
                        echo "✗ Failed to copy optimized texture back: $path" >> "$OPTIMIZATION_LOG"
                    fi
                    # Clean up temp file
                    rm -f "$temp_output"
                else
                    echo "✗ ImageMagick produced no output for: $path" >> "$OPTIMIZATION_LOG"
                fi
            else
                echo "✗ ImageMagick failed to optimize: $path (Command: ${magick_run_cmd[*]} $texture_path ...)" >> "$OPTIMIZATION_LOG"
            fi

            # Update progress
            atomic_increment "$PROGRESS_FILE"
        ) &

        # Limit number of parallel jobs
        while [ "$(jobs -p | wc -l)" -ge "$THREAD_COUNT" ]; do
            sleep 0.1
            wait -n 2>/dev/null || true
        done
    done

    # Wait for all remaining jobs to complete
    wait

    # Wait for progress monitor to finish
    wait $MONITOR_PID 2>/dev/null || true

    # --- Batch Database Update ---
    echo "Performing batch update on database for successfully optimized textures..."
    if [ -s "$SUCCESS_IDS_FILE" ]; then
        # Construct the WHERE clause for the batch update
        # Read IDs, join with comma, ensure no trailing comma
        local ids_to_update=$(paste -sd, "$SUCCESS_IDS_FILE")

        if [ -n "$ids_to_update" ]; then
            echo "Updating IDs: ${ids_to_update:0:100}..." # Log first few IDs
            if ! "$SQLITE_CMD" "$DB_FILE" "UPDATE textures SET processed = 2 WHERE id IN ($ids_to_update);"; then
                echo "ERROR: Failed to perform batch database update! Database might be inconsistent." | tee -a "$LOG_FILE"
                # Consider adding more robust error handling here if needed
            else
                echo "Batch database update successful." | tee -a "$LOG_FILE"
            fi
        else
             echo "No successful IDs found in the temp file for batch update." | tee -a "$LOG_FILE"
        fi
    else
        echo "No textures were successfully optimized, skipping batch database update." | tee -a "$LOG_FILE"
    fi
    # --- End Batch Update ---

    # Clean up temporary directory and success ID file
    rm -rf "$VRAMR_TEMP/temp_optimize"
    rm -f "$SUCCESS_IDS_FILE" "$SUCCESS_IDS_FILE.lock"

    # Final statistics (Now read count from DB AFTER batch update)
    local success_count=$("$SQLITE_CMD" "$DB_FILE" "SELECT COUNT(*) FROM textures WHERE processed = 2;")
    local final_count=$(cat "$PROGRESS_FILE" 2>/dev/null || echo "$TEXTURES_TO_OPTIMIZE")

    echo "Optimization complete. Processed $final_count textures, successfully optimized and updated $success_count in DB." | tee -a "$LOG_FILE"
    echo "$(date) Optimization complete. Processed $final_count textures, successfully optimized $success_count." >> "$LOG_FILE"

    # Cleanup progress file
    rm -f "$PROGRESS_FILE" "$PROGRESS_FILE.lock"

    update_progress 90
    return 0
}

# --- Quality control checks ---
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

# --- Final cleanup function ---
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
        echo "RadiumTextures Native Linux Summary"
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
    echo "RadiumTextures process completed successfully!"
    echo ""
    echo "====================================================================="
    echo "RadiumTextures Output is ready in: $FINAL_OUTPUT_DIR"
    echo "Put this folder into your mod manager"
    echo "====================================================================="

    return 0
}

# --- Main function to start the process ---
main() {
    echo "====================================="
    echo "RadiumTextures - Skyrim Texture Optimizer"
    echo "====================================="

    # Set file limits
    echo "Setting file descriptor limits..."
    set_file_limits

    # Resolve dependencies
    echo "Step 1: Resolving dependencies..."
    if ! resolve_dependencies; then
        echo "ERROR: Failed to resolve required dependencies. Exiting."
        exit 1
    fi

    # Initialize script and parse arguments
    echo "Step 2: Initializing script settings..."
    initialize_script "$@"

    # Generate Mod Order CSV
    echo "Step 3: Generating mod order CSV..."
    generate_mod_order_csv

    # Extract BSA files and copy loose textures
    echo "Step 4: Processing BSA files and loose textures..."
    extract_bsa_files

    # Process exclusions
    echo "Step 5: Processing exclusions..."
    process_exclusions

    # Analyze textures
    echo "Step 6: Analyzing textures..."
    if ! analyze_textures; then
        echo "Warning: Standard texture analysis failed. Trying safe mode..."
        if ! analyze_textures_safely; then
            echo "ERROR: Texture analysis failed even in safe mode. Exiting."
            exit 1
        fi
    fi

    # Filter textures based on preset
    echo "Step 7: Filtering textures..."
    filter_textures

    # Delete skipped textures
    echo "Step 8: Deleting skipped textures..."
    delete_skipped_textures

    # Optimize textures
    echo "Step 9: Optimizing textures..."
    optimize_textures

    # Run quality control checks
    echo "Step 10: Running quality control..."
    quality_control

    # Final cleanup
    echo "Step 11: Final cleanup..."
    final_cleanup

    echo "====================================="
    echo "RadiumTextures process complete!"
    echo "====================================="
    return 0
}

# --- Run the main function ---
main "$@"
