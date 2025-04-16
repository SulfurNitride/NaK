#!/bin/bash

# RadiumTextures - Complete Skyrim Texture Optimization Script
# Combines working dependency resolution with full texture processing

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
TEXCONV_URL="https://github.com/matyalatte/Texconv-Custom-DLL/releases/download/v0.4.1/TexconvCustomDLL-v0.4.1-Linux-no-deps.tar.bz2"
HOOLAMIKE_URL="https://github.com/Niedzwiedzw/hoolamike/releases/download/v0.15.5/hoolamike-x86_64-unknown-linux-gnu.tar.gz"
PWSH_URL="https://github.com/PowerShell/PowerShell/releases/download/v7.5.0/powershell-7.5.0-linux-x64.tar.gz"
ISPC_URL="https://github.com/ispc/ispc/releases/download/v1.26.0/ispc-v1.26.0-linux.tar.gz"
CUTTLEFISH_URL="https://github.com/akb825/Cuttlefish/releases/download/v2.8.1/cuttlefish-linux.tar.gz"

# --- Define archive names ---
SQLITE_ZIP="sqlite-tools-linux-x64-3490100.zip"
TEXCONV_ARCHIVE="TexconvCustomDLL-v0.4.1-Linux-no-deps.tar.bz2"
HOOLAMIKE_ARCHIVE="hoolamike-x86_64-unknown-linux-gnu.tar.gz"
PWSH_ARCHIVE="powershell-7.5.0-linux-x64.tar.gz"
ISPC_ARCHIVE="ispc-v1.26.0-linux.tar.gz"
CUTTLEFISH_ARCHIVE="cuttlefish-linux.tar.gz"

# --- Portable binary paths will be defined *after* config sourcing ---
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
    PORTABLE_TEXCONV_BIN="$PORTABLE_DIR/texconv"
    PORTABLE_HOOLAMIKE_BIN="$PORTABLE_DIR/hoolamike"
    # PORTABLE_FD_BIN="$PORTABLE_DIR/fd" # Assuming fd might be added later
    PWSH_PORTABLE_DIR="$PORTABLE_DIR/powershell_portable" # Dir for PS content
    PORTABLE_PWSH_BIN="$PWSH_PORTABLE_DIR/pwsh" # Default executable path inside dir
    PORTABLE_ISPC_BIN="$PORTABLE_DIR/ispc"
    PORTABLE_ISPC_DIR="$PORTABLE_DIR/ispc_files"
    PORTABLE_CUTTLEFISH_DIR="$PORTABLE_DIR/cuttlefish_files" # Dir for Cuttlefish content
    PORTABLE_CUTTLEFISH_BIN="$PORTABLE_CUTTLEFISH_DIR/bin/cuttlefish" # Default executable path inside dir

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
    MAGICK_CMD=$(command -v magick || command -v convert)
    if [ -n "$MAGICK_CMD" ] && [ -x "$MAGICK_CMD" ]; then
        echo "Found system ImageMagick: $MAGICK_CMD"
    else
        echo "Installing portable ImageMagick..."
        MAGICK_CMD="$PORTABLE_MAGICK_BIN"

        if [ ! -f "$MAGICK_CMD" ]; then
            if command -v wget &>/dev/null; then
                wget -q "$MAGICK_URL" -O "$MAGICK_CMD"
            elif command -v curl &>/dev/null; then
                curl -s "$MAGICK_URL" -o "$MAGICK_CMD"
            else
                echo "WARNING: Neither wget nor curl found. Cannot download ImageMagick."
                MAGICK_CMD=""
            fi

            if [ -n "$MAGICK_CMD" ] && [ -f "$MAGICK_CMD" ]; then
                chmod +x "$MAGICK_CMD"
                echo "Installed portable ImageMagick: $MAGICK_CMD"
            else
                echo "WARNING: Failed to download ImageMagick."
                MAGICK_CMD=""
            fi
        else
            echo "Found existing portable ImageMagick: $MAGICK_CMD"
            # Ensure it's executable
            chmod +x "$MAGICK_CMD"
        fi
    fi

    # --- Handle Texconv ---
    TEXCONV_CMD=$(command -v texconv)
    if [ -n "$TEXCONV_CMD" ] && [ -x "$TEXCONV_CMD" ]; then
        echo "Found system Texconv: $TEXCONV_CMD"
    else
        echo "Installing portable Texconv..."
        TEXCONV_CMD="$PORTABLE_TEXCONV_BIN"

        if [ ! -f "$TEXCONV_CMD" ]; then
            if command -v wget &>/dev/null; then
                wget -q "$TEXCONV_URL" -O "$TEMP_DIR/$TEXCONV_ARCHIVE"
            elif command -v curl &>/dev/null; then
                curl -s -L "$TEXCONV_URL" -o "$TEMP_DIR/$TEXCONV_ARCHIVE"
            else
                echo "ERROR: Neither wget nor curl found. Cannot download Texconv."
                return 1
            fi

            if [ ! -f "$TEMP_DIR/$TEXCONV_ARCHIVE" ]; then
                echo "ERROR: Failed to download Texconv archive."
                return 1
            fi

            # Extract Texconv
            echo "Extracting Texconv..."
            mkdir -p "$TEMP_DIR/texconv_extract"
            tar -xjf "$TEMP_DIR/$TEXCONV_ARCHIVE" -C "$TEMP_DIR/texconv_extract"

            # Find Texconv binary
            TEXCONV_EXTRACT=$(find "$TEMP_DIR/texconv_extract" -name "texconv" -type f -executable | head -n 1)
            if [ -n "$TEXCONV_EXTRACT" ]; then
                cp "$TEXCONV_EXTRACT" "$TEXCONV_CMD"
                chmod +x "$TEXCONV_CMD"

                # Also look for libtexconv.so
                TEXCONV_LIB=$(find "$TEMP_DIR/texconv_extract" -name "libtexconv.so" -type f | head -n 1)
                if [ -n "$TEXCONV_LIB" ]; then
                    cp "$TEXCONV_LIB" "$PORTABLE_DIR/libtexconv.so"
                    echo "Copied libtexconv.so to $PORTABLE_DIR"
                fi

                echo "Installed portable Texconv: $TEXCONV_CMD"
            else
                echo "ERROR: Could not find texconv binary in the archive."
                return 1
            fi

            # Clean up
            rm -rf "$TEMP_DIR/texconv_extract" "$TEMP_DIR/$TEXCONV_ARCHIVE"
        else
            echo "Found existing portable Texconv: $TEXCONV_CMD"
            # Ensure it's executable
            chmod +x "$TEXCONV_CMD"
        fi
    fi

    # --- Handle PowerShell ---
    PwshCmd=$(command -v pwsh)
    if [ -n "$PwshCmd" ] && [ -x "$PwshCmd" ]; then
        echo "Found system PowerShell: $PwshCmd"
        # Use system pwsh if available
        PORTABLE_PWSH_BIN=$PwshCmd
    else
        echo "Installing portable PowerShell..."
        PORTABLE_PWSH_BIN="$PORTABLE_DIR/pwsh"

        if [ ! -f "$PORTABLE_PWSH_BIN" ]; then
            if command -v wget &>/dev/null; then
                wget -q "$PWSH_URL" -O "$TEMP_DIR/$PWSH_ARCHIVE"
            elif command -v curl &>/dev/null; then
                curl -s -L "$PWSH_URL" -o "$TEMP_DIR/$PWSH_ARCHIVE"
            else
                echo "ERROR: Neither wget nor curl found. Cannot download PowerShell."
                return 1
            fi

            if [ ! -f "$TEMP_DIR/$PWSH_ARCHIVE" ]; then
                echo "ERROR: Failed to download PowerShell archive."
                return 1
            fi

            # Extract PowerShell
            echo "Extracting PowerShell..."
            # Create a specific directory for PowerShell contents
            mkdir -p "$PWSH_PORTABLE_DIR"
            # Extract directly into the target portable directory
            if ! tar -xzf "$TEMP_DIR/$PWSH_ARCHIVE" -C "$PWSH_PORTABLE_DIR"; then
                 echo "ERROR: Failed to extract PowerShell archive."
                 rm -rf "$PWSH_PORTABLE_DIR" # Clean up partial extraction
                 return 1
            fi

            # Find PowerShell binary anywhere within the extracted directory (don't require executable flag initially)
            PWSH_EXTRACT=$(find "$PWSH_PORTABLE_DIR" -name "pwsh" -type f | head -n 1)
            if [ -n "$PWSH_EXTRACT" ]; then
                 # Binary found. Update the variable and make it executable.
                 PORTABLE_PWSH_BIN="$PWSH_EXTRACT"
                 echo "Found PowerShell binary at: $PORTABLE_PWSH_BIN"
                 chmod +x "$PORTABLE_PWSH_BIN"
                 # Verify it's executable now
                 if [ -x "$PORTABLE_PWSH_BIN" ]; then
                    echo "Installed and marked portable PowerShell executable: $PORTABLE_PWSH_BIN"
                 else
                    echo "ERROR: Failed to make PowerShell binary executable at $PORTABLE_PWSH_BIN"
                    rm -rf "$PWSH_PORTABLE_DIR"
                    return 1
                 fi
            else
                echo "ERROR: Could not find pwsh binary in the archive."
                # Clean up the potentially empty dir
                rm -rf "$PWSH_PORTABLE_DIR"
                return 1
            fi

            # Clean up archive
            rm -f "$TEMP_DIR/$PWSH_ARCHIVE"
        else
            echo "Found existing portable PowerShell: $PORTABLE_PWSH_BIN"
            # Ensure it's executable
            chmod +x "$PORTABLE_PWSH_BIN"
        fi
    fi

    # --- Handle ISPC ---
    ISPC_CMD=$(command -v ispc)
    if [ -n "$ISPC_CMD" ] && [ -x "$ISPC_CMD" ]; then
        echo "Found system ISPC: $ISPC_CMD"
    else
        echo "Installing portable ISPC..."
        ISPC_CMD="$PORTABLE_ISPC_BIN"

        if [ ! -f "$ISPC_CMD" ]; then
            if command -v wget &>/dev/null; then
                wget -q "$ISPC_URL" -O "$TEMP_DIR/$ISPC_ARCHIVE"
            elif command -v curl &>/dev/null; then
                curl -s -L "$ISPC_URL" -o "$TEMP_DIR/$ISPC_ARCHIVE"
            else
                echo "ERROR: Neither wget nor curl found. Cannot download ISPC."
                return 1
            fi

            if [ ! -f "$TEMP_DIR/$ISPC_ARCHIVE" ]; then
                echo "ERROR: Failed to download ISPC archive."
                return 1
            fi

            # Extract ISPC
            echo "Extracting ISPC..."
            mkdir -p "$TEMP_DIR/ispc_extract"
            tar -xzf "$TEMP_DIR/$ISPC_ARCHIVE" -C "$TEMP_DIR/ispc_extract"

            # Find ISPC binary - first look in bin subdirectory
            ISPC_EXTRACT=$(find "$TEMP_DIR/ispc_extract" -path "*/bin/ispc" -type f | head -n 1)
            if [ -z "$ISPC_EXTRACT" ]; then
                # If not found in bin, try a more general search
                ISPC_EXTRACT=$(find "$TEMP_DIR/ispc_extract" -name "ispc" -type f | head -n 1)
            fi

            if [ -n "$ISPC_EXTRACT" ]; then
                cp "$ISPC_EXTRACT" "$ISPC_CMD"
                chmod +x "$ISPC_CMD"

                # Create directory for additional files
                mkdir -p "$PORTABLE_ISPC_DIR"

                echo "Installed portable ISPC: $ISPC_CMD"
            else
                echo "ERROR: Could not find ispc binary in the archive."
                return 1
            fi

            # Clean up
            rm -rf "$TEMP_DIR/ispc_extract" "$TEMP_DIR/$ISPC_ARCHIVE"
        else
            echo "Found existing portable ISPC: $ISPC_CMD"
            # Ensure it's executable
            chmod +x "$ISPC_CMD"
        fi
    fi

    # --- Handle Cuttlefish ---
    CUTTLEFISH_CMD=$(command -v cuttlefish)
    if [ -n "$CUTTLEFISH_CMD" ] && [ -x "$CUTTLEFISH_CMD" ]; then
        echo "Found system Cuttlefish: $CUTTLEFISH_CMD"
    else
        echo "Installing portable Cuttlefish..."
        CUTTLEFISH_CMD="$PORTABLE_CUTTLEFISH_BIN"

        if [ ! -f "$CUTTLEFISH_CMD" ]; then
            # First attempt - standard URL
            echo "Attempting to download Cuttlefish from primary URL..."
            if command -v wget &>/dev/null; then
                wget -q "$CUTTLEFISH_URL" -O "$TEMP_DIR/$CUTTLEFISH_ARCHIVE"
            elif command -v curl &>/dev/null; then
                curl -s -L "$CUTTLEFISH_URL" -o "$TEMP_DIR/$CUTTLEFISH_ARCHIVE"
            else
                echo "ERROR: Neither wget nor curl found. Cannot download Cuttlefish."
                return 1
            fi

            # Check if the download is valid
            if [ ! -f "$TEMP_DIR/$CUTTLEFISH_ARCHIVE" ] || [ ! -s "$TEMP_DIR/$CUTTLEFISH_ARCHIVE" ]; then
                echo "Primary download failed or produced empty file. Trying alternative URL..."
                # Alternative URL - GitHub releases
                CUTTLEFISH_ALT_URL="https://github.com/GPSnoopy/ScreenSpaceReflections/releases/download/v2.0.0/cuttlefish-linux.tar.gz"

                if command -v wget &>/dev/null; then
                    wget -q "$CUTTLEFISH_ALT_URL" -O "$TEMP_DIR/$CUTTLEFISH_ARCHIVE"
                elif command -v curl &>/dev/null; then
                    curl -s -L "$CUTTLEFISH_ALT_URL" -o "$TEMP_DIR/$CUTTLEFISH_ARCHIVE"
                fi

                # If still not valid, try a second alternative
                if [ ! -f "$TEMP_DIR/$CUTTLEFISH_ARCHIVE" ] || [ ! -s "$TEMP_DIR/$CUTTLEFISH_ARCHIVE" ]; then
                    echo "Alternative download also failed. Trying a different approach..."
                    # Clone and build from source approach - simulated here
                    echo "ERROR: Could not download Cuttlefish binary."
                    echo "Skipping Cuttlefish installation - we'll fall back to texconv for optimization."
                    # Skip the rest of Cuttlefish installation
                    rm -f "$TEMP_DIR/$CUTTLEFISH_ARCHIVE" 2>/dev/null
                    return 0
                fi
            fi

            # Test the archive before extracting
            if ! gzip -t "$TEMP_DIR/$CUTTLEFISH_ARCHIVE" 2>/dev/null; then
                echo "WARNING: Downloaded archive appears to be corrupted. Skipping Cuttlefish installation."
                rm -f "$TEMP_DIR/$CUTTLEFISH_ARCHIVE"
                return 0
            fi

            # Extract Cuttlefish
            echo "Extracting Cuttlefish..."
            mkdir -p "$TEMP_DIR/cuttlefish_extract"

            # Use -k to keep going even if there are errors
            if ! tar -xzf "$TEMP_DIR/$CUTTLEFISH_ARCHIVE" -C "$TEMP_DIR/cuttlefish_extract"; then
                echo "WARNING: Issues extracting the Cuttlefish archive. Trying to continue anyway..."
            fi

            # Find the Cuttlefish binary within the extracted directory
            CUTTLEFISH_EXTRACT_BIN=$(find "$TEMP_DIR/cuttlefish_extract" -path "*/bin/cuttlefish" -type f -executable | head -n 1)

            if [ -n "$CUTTLEFISH_EXTRACT_BIN" ]; then
                # Determine the base directory of the extraction (e.g., the 'cuttlefish' folder)
                EXTRACTED_CUTTLEFISH_BASE=$(dirname "$(dirname "$CUTTLEFISH_EXTRACT_BIN")")

                if [ -d "$EXTRACTED_CUTTLEFISH_BASE" ]; then
                    # Create the target directory for all Cuttlefish files
                    mkdir -p "$PORTABLE_CUTTLEFISH_DIR"

                    # Copy all contents from the extracted base directory
                    echo "Copying Cuttlefish files from $EXTRACTED_CUTTLEFISH_BASE to $PORTABLE_CUTTLEFISH_DIR..."
                    if cp -a "$EXTRACTED_CUTTLEFISH_BASE"/* "$PORTABLE_CUTTLEFISH_DIR/"; then
                        # Set the command path to the binary inside the portable directory
                        CUTTLEFISH_CMD="$PORTABLE_CUTTLEFISH_DIR/bin/cuttlefish"

                        # Ensure the binary is executable (it should be already, but double-check)
                        if [ -f "$CUTTLEFISH_CMD" ]; then
                           chmod +x "$CUTTLEFISH_CMD"
                           echo "Installed portable Cuttlefish (full package): $CUTTLEFISH_CMD"
                        else
                           echo "WARNING: Cuttlefish binary not found at expected location after copy: $CUTTLEFISH_CMD"
                           echo "Will use texconv for optimization instead."
                           CUTTLEFISH_CMD="" # Clear the command path
                        fi
                    else
                        echo "ERROR: Failed to copy Cuttlefish files to $PORTABLE_CUTTLEFISH_DIR."
                        echo "Will use texconv for optimization instead."
                        CUTTLEFISH_CMD="" # Clear the command path
                    fi
                else
                    echo "WARNING: Could not determine Cuttlefish base directory from binary path: $CUTTLEFISH_EXTRACT_BIN"
                    echo "Will use texconv for optimization instead."
                    CUTTLEFISH_CMD="" # Clear the command path
                fi
            else
                echo "WARNING: Could not find executable cuttlefish binary in the archive (searched for */bin/cuttlefish)."
                echo "Will use texconv for optimization instead."
                CUTTLEFISH_CMD="" # Clear the command path
            fi

            # Clean up extraction directory (keep archive for debugging if needed, or remove)
            rm -rf "$TEMP_DIR/cuttlefish_extract" # "$TEMP_DIR/$CUTTLEFISH_ARCHIVE"
        else
            # Check if the existing portable Cuttlefish is the full setup or just the old binary
            if [ -f "$PORTABLE_CUTTLEFISH_DIR/bin/cuttlefish" ] && [ -x "$PORTABLE_CUTTLEFISH_DIR/bin/cuttlefish" ]; then
                 CUTTLEFISH_CMD="$PORTABLE_CUTTLEFISH_DIR/bin/cuttlefish"
                 echo "Found existing portable Cuttlefish (full package): $CUTTLEFISH_CMD"
                 chmod +x "$CUTTLEFISH_CMD" # Ensure executable
            elif [ -f "$PORTABLE_CUTTLEFISH_BIN" ] && [ -x "$PORTABLE_CUTTLEFISH_BIN" ]; then
                 # If only the old single binary exists, treat it as not found to trigger re-download/extraction of the full package
                 echo "Found old standalone portable Cuttlefish binary. Attempting to install full package..."
                 rm -f "$PORTABLE_CUTTLEFISH_BIN" # Remove the old binary
                 # Force re-evaluation by clearing the command variable and recursively calling or letting the loop continue
                 CUTTLEFISH_CMD="" # Clear the command path to retry install logic if this were in a loop/function call again
                 # Since it's not easily recursive here, we might need manual cleanup or accept it will redownload next time.
                 # For now, just warn and proceed without Cuttlefish for this run if full package isn't there.
                 echo "Full Cuttlefish package not found. Will attempt install on next run or use texconv."

            else
                 echo "No existing portable Cuttlefish found."
                 CUTTLEFISH_CMD=""
            fi
        fi
    fi

    # --- Handle Hoolamike (for BSA extraction) ---
    echo "Installing portable Hoolamike (BSA Extractor)..."
    HOOLAMIKE_CMD="$PORTABLE_HOOLAMIKE_BIN"

    if [ ! -f "$HOOLAMIKE_CMD" ]; then
        if command -v wget &>/dev/null; then
            wget -q "$HOOLAMIKE_URL" -O "$TEMP_DIR/$HOOLAMIKE_ARCHIVE"
        elif command -v curl &>/dev/null; then
            curl -s -L "$HOOLAMIKE_URL" -o "$TEMP_DIR/$HOOLAMIKE_ARCHIVE"
        else
            echo "ERROR: Neither wget nor curl found. Cannot download Hoolamike."
            return 1
        fi

        if [ ! -f "$TEMP_DIR/$HOOLAMIKE_ARCHIVE" ]; then
            echo "ERROR: Failed to download Hoolamike archive."
            return 1
        fi

        # Extract Hoolamike
        echo "Extracting Hoolamike..."
        mkdir -p "$TEMP_DIR/hoolamike_extract"
        tar -xzf "$TEMP_DIR/$HOOLAMIKE_ARCHIVE" -C "$TEMP_DIR/hoolamike_extract"

        # Find Hoolamike binary
        HOOLAMIKE_EXTRACT=$(find "$TEMP_DIR/hoolamike_extract" -name "hoolamike" -type f | head -n 1)
        if [ -n "$HOOLAMIKE_EXTRACT" ]; then
            cp "$HOOLAMIKE_EXTRACT" "$HOOLAMIKE_CMD"
            chmod +x "$HOOLAMIKE_CMD"

            # Look for and copy any .d files
            find "$TEMP_DIR/hoolamike_extract" -name "*.d" -type f -exec cp {} "$PORTABLE_DIR/" \;

            echo "Installed portable Hoolamike: $HOOLAMIKE_CMD"
        else
            echo "ERROR: Could not find hoolamike binary in the archive."
            return 1
        fi

        # Clean up
        rm -rf "$TEMP_DIR/hoolamike_extract" "$TEMP_DIR/$HOOLAMIKE_ARCHIVE"
    else
        echo "Found existing portable Hoolamike: $HOOLAMIKE_CMD"
        # Ensure it's executable
        chmod +x "$HOOLAMIKE_CMD"
    fi

    # Update dependency resolution return handling
    echo "Dependency resolution complete."
    echo "SQLite: $SQLITE_CMD"
    echo "ImageMagick: $MAGICK_CMD"
    echo "Texconv: $TEXCONV_CMD"
    echo "ISPC: $ISPC_CMD"
    if [ -f "$CUTTLEFISH_CMD" ] && [ -x "$CUTTLEFISH_CMD" ]; then
        echo "Cuttlefish: $CUTTLEFISH_CMD"
    else
        echo "Cuttlefish: Not available (will use Texconv for optimization)"
        # Make sure we have Texconv as a fallback
        if [ ! -f "$TEXCONV_CMD" ] || [ ! -x "$TEXCONV_CMD" ]; then
            echo "ERROR: Neither Cuttlefish nor Texconv are available for texture optimization."
            return 1
        fi
    fi
    echo "Hoolamike: $HOOLAMIKE_CMD"

    return 0
}
export PWSH_CMD
echo "PowerShell command being used: $PWSH_CMD"

# --- Source remaining libraries ---
# Now that we've defined the paths, we can safely source the necessary library files
echo "Loading utility libraries..."

UTILS_PATH="$LIBS_DIR/utils.sh"
if [ -f "$UTILS_PATH" ]; then
    echo "Loading utilities: $UTILS_PATH"
    source "$UTILS_PATH"
else
    echo "ERROR: Required utilities file not found: $UTILS_PATH"
    exit 1
fi

EXTRACT_PATH="$LIBS_DIR/extract.sh"
if [ -f "$EXTRACT_PATH" ]; then
    echo "Loading extraction module: $EXTRACT_PATH"
    source "$EXTRACT_PATH"
else
    echo "ERROR: Required extraction file not found: $EXTRACT_PATH"
    exit 1
fi

COPY_PATH="$LIBS_DIR/copy.sh"
if [ -f "$COPY_PATH" ]; then
    echo "Loading copy module: $COPY_PATH"
    source "$COPY_PATH"
else
    echo "ERROR: Required copy file not found: $COPY_PATH"
    exit 1
fi

PROCESS_PATH="$LIBS_DIR/process.sh"
if [ -f "$PROCESS_PATH" ]; then
    echo "Loading processing module: $PROCESS_PATH"
    source "$PROCESS_PATH"
else
    echo "ERROR: Required processing file not found: $PROCESS_PATH"
    exit 1
fi

OPTIMIZE_PATH="$LIBS_DIR/optimize.sh"
if [ -f "$OPTIMIZE_PATH" ]; then
    echo "Loading optimization module: $OPTIMIZE_PATH"
    source "$OPTIMIZE_PATH"
else
    echo "ERROR: Required optimization file not found: $OPTIMIZE_PATH"
    exit 1
fi

CLEANUP_PATH="$LIBS_DIR/cleanup.sh"
if [ -f "$CLEANUP_PATH" ]; then
    echo "Loading cleanup module: $CLEANUP_PATH"
    source "$CLEANUP_PATH"
else
    echo "ERROR: Required cleanup file not found: $CLEANUP_PATH"
    exit 1
fi

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

    # Generate Mod Order CSV using PowerShell
    echo "Step 3: Generating mod order CSV..."
    generate_mod_order_csv

    # Extract BSA files
    echo "Step 4: Extracting BSA files..."
    extract_bsa_files

    # Copy loose textures
    echo "Step 5: Copying loose textures..."
    # Check if we should use prioritized copy based on CSV
    if [ -f "$VRAMR_TEMP/ActiveModListOrder.csv" ]; then
        echo "Using prioritized texture copy based on mod order CSV..."
        prioritized_texture_copy
    else
        echo "Using ultra-parallel texture copy (no mod order CSV found)..."
        ultra_parallel_copy
    fi

    # Process exclusions
    echo "Step 6: Processing exclusions..."
    linux_native_exclusions

    # Analyze textures
    echo "Step 7: Analyzing textures..."
    if ! linux_native_analyze; then
        echo "Warning: Standard texture analysis failed. Trying safe mode..."
        if ! analyze_textures_safely; then
            echo "ERROR: Texture analysis failed even in safe mode. Exiting."
            exit 1
        fi
    fi

    # Filter textures based on preset
    echo "Step 8: Filtering textures..."
    linux_native_filter

    # Delete skipped textures
    echo "Step 9: Deleting skipped textures..."
    delete_skipped_textures

    # Optimize textures
    echo "Step 10: Optimizing textures..."
    optimize_textures

    # Run quality control checks
    echo "Step 11: Running quality control..."
    quality_control

    # Final cleanup
    echo "Step 12: Final cleanup..."
    final_cleanup

    echo "====================================="
    echo "RadiumTextures process complete!"
    echo "====================================="
    return 0
}

# --- Run the main function ---
main "$@"
