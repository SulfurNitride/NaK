#!/bin/bash
# -------------------------------------------------------------------
# portablepython.sh
# Portable Python setup for MO2 Helper
# -------------------------------------------------------------------

# Constants for portable Python
PORTABLE_PYTHON_URL="https://github.com/bjia56/portable-python/releases/download/cpython-v3.13.1-build.3/python-full-3.13.1-linux-x86_64.zip"
PORTABLE_PYTHON_DIR="$SCRIPT_DIR/lib/portable_python"
PORTABLE_PYTHON_ZIP="$PORTABLE_PYTHON_DIR/python-full.zip"
PORTABLE_PYTHON_EXTRACT_DIR="$PORTABLE_PYTHON_DIR/python-full-3.13.1-linux-x86_64"
PORTABLE_PYTHON_BINARY="$PORTABLE_PYTHON_EXTRACT_DIR/bin/python3"

# Download and set up portable Python
setup_portable_python() {
    log_info "Setting up portable Python"

    # Create directory if it doesn't exist
    mkdir -p "$PORTABLE_PYTHON_DIR"

    # Check if Python is already extracted
    if [ -f "$PORTABLE_PYTHON_BINARY" ] && [ -x "$PORTABLE_PYTHON_BINARY" ]; then
        log_info "Portable Python already exists at $PORTABLE_PYTHON_BINARY"
        return 0
    fi

    log_info "Downloading portable Python from $PORTABLE_PYTHON_URL"

    # Check for download tools
    local download_tool=""
    if command_exists curl; then
        download_tool="curl -L -o"
    elif command_exists wget; then
        download_tool="wget -O"
    else
        handle_error "Neither curl nor wget is available. Please install one of them." false
        return 1
    fi

    # Download the ZIP file
    if ! $download_tool "$PORTABLE_PYTHON_ZIP" "$PORTABLE_PYTHON_URL"; then
        handle_error "Failed to download portable Python. Check your internet connection." false
        return 1
    fi

    log_info "Extracting portable Python to $PORTABLE_PYTHON_DIR"

    # Check for unzip tool
    if ! command_exists unzip; then
        handle_error "unzip is not available. Please install it with: sudo apt install unzip" false
        return 1
    fi

    # Extract the ZIP file
    if ! unzip -o "$PORTABLE_PYTHON_ZIP" -d "$PORTABLE_PYTHON_DIR"; then
        handle_error "Failed to extract portable Python." false
        return 1
    fi

    # Make sure the Python binary is executable
    if [ -f "$PORTABLE_PYTHON_BINARY" ]; then
        chmod +x "$PORTABLE_PYTHON_BINARY"
    else
        log_error "Python binary not found at expected location: $PORTABLE_PYTHON_BINARY"
        handle_error "Python installation structure is different than expected" false
        return 1
    fi

    # Verify the installation
    if [ ! -x "$PORTABLE_PYTHON_BINARY" ]; then
        handle_error "Portable Python binary not found or not executable." false
        return 1
    fi

    log_info "Portable Python set up successfully at $PORTABLE_PYTHON_BINARY"

    # Remove the ZIP file to save space
    rm -f "$PORTABLE_PYTHON_ZIP"

    return 0
}

# Get the path to the portable Python binary
get_portable_python() {
    # Check if portable Python is set up
    if [ ! -f "$PORTABLE_PYTHON_BINARY" ] || [ ! -x "$PORTABLE_PYTHON_BINARY" ]; then
        # Try to set it up
        if ! setup_portable_python; then
            return 1
        fi
    fi

    # Return the path to the Python binary
    echo "$PORTABLE_PYTHON_BINARY"
    return 0
}
