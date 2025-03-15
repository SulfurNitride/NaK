#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Define install directory
INSTALL_DIR="$HOME/nak"

# Progress spinner function
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    echo -n "   "
    while [ "$(ps a | awk '{print $1}' | grep -w $pid)" ]; do
        local temp=${spinstr#?}
        printf "\b\b\b[%c] " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
    done
    printf "\b\b\b   \b\b\b"
}

# Check if nak directory already exists
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}NaK is already installed at $INSTALL_DIR${NC}"
    echo -e "Would you like to update to the latest version? This will delete the existing installation."
    read -p "Update NaK? [y/N]: " update_response
    if [[ "$update_response" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Removing existing installation...${NC}"
        rm -rf "$INSTALL_DIR"
    else
        echo -e "Update canceled. Exiting."
        exit 0
    fi
fi

echo -e "${BLUE}Installing NaK...${NC}"

# Create directories if they don't exist
mkdir -p "$INSTALL_DIR/lib/games" "$INSTALL_DIR/lib/ttw" 2>/dev/null

# Clone the repository to a temporary location
TMP_DIR=$(mktemp -d)
echo -ne "${BLUE}Downloading files...${NC} "

# Suppress all git output completely
{
    git clone -q https://github.com/SulfurNitride/NaK.git "$TMP_DIR" 2>/dev/null
} &
GIT_PID=$!
spinner $GIT_PID
echo -e "${GREEN}Done!${NC}"

# Installation process
echo -ne "${BLUE}Setting up NaK...${NC} "

{
    # Look for files in various possible locations
    local found_files=0

    # Check for nak-files structure
    if [ -d "$TMP_DIR/nak-files" ] && [ -f "$TMP_DIR/nak-files/main-script.sh" ]; then
        echo "DEBUG: Found structure in nak-files directory"
        # Copy main script
        cp "$TMP_DIR/nak-files/main-script.sh" "$INSTALL_DIR/main-script.sh" 2>/dev/null

        # Copy the library files
        mkdir -p "$INSTALL_DIR/lib"
        cp -r "$TMP_DIR/nak-files/lib/"* "$INSTALL_DIR/lib/" 2>/dev/null

        found_files=1
    # Check for mo2helper structure (legacy)
    elif [ -d "$TMP_DIR/mo2helper" ] && [ -f "$TMP_DIR/mo2helper/main-script.sh" ]; then
        echo "DEBUG: Found structure in mo2helper directory"
        # Copy main script
        cp "$TMP_DIR/mo2helper/main-script.sh" "$INSTALL_DIR/main-script.sh" 2>/dev/null

        # Copy the library files
        mkdir -p "$INSTALL_DIR/lib"
        cp -r "$TMP_DIR/mo2helper/lib/"* "$INSTALL_DIR/lib/" 2>/dev/null

        found_files=1
    # Check for files directly in root
    elif [ -f "$TMP_DIR/main-script.sh" ]; then
        echo "DEBUG: Found structure in repository root"
        cp "$TMP_DIR/main-script.sh" "$INSTALL_DIR/main-script.sh" 2>/dev/null

        if [ -d "$TMP_DIR/lib" ]; then
            cp -r "$TMP_DIR/lib/"* "$INSTALL_DIR/lib/" 2>/dev/null
        fi

        found_files=1
    fi

    # Desperate search if no expected structure found
    if [ $found_files -eq 0 ]; then
        echo "DEBUG: No standard structure found, searching for files..."
        # Find main script
        main_script=$(find "$TMP_DIR" -name "main-script.sh" | head -1)
        if [ -n "$main_script" ]; then
            cp "$main_script" "$INSTALL_DIR/main-script.sh" 2>/dev/null

            # Try to find lib directory relative to main script
            script_dir=$(dirname "$main_script")
            if [ -d "$script_dir/lib" ]; then
                cp -r "$script_dir/lib/"* "$INSTALL_DIR/lib/" 2>/dev/null
            fi
        else
            echo "WARNING: Could not find main-script.sh in any location"
        fi
    fi

    # Make scripts executable
    chmod +x "$INSTALL_DIR"/*.sh 2>/dev/null
    find "$INSTALL_DIR" -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null

    # Update config paths
    if [ -f "$INSTALL_DIR/lib/core.sh" ]; then
        # Update config path in core.sh if needed
        sed -i 's|CONFIG_DIR="$HOME/.config/mo2helper"|CONFIG_DIR="$HOME/.config/nak"|g' "$INSTALL_DIR/lib/core.sh"
    fi

    # Create config directory if it doesn't exist
    mkdir -p "$HOME/.config/nak"

    # Migrate settings if needed
    if [ -d "$HOME/.config/mo2helper" ] && [ ! -f "$HOME/.config/nak/config.ini" ]; then
        cp -r "$HOME/.config/mo2helper/"* "$HOME/.config/nak/" 2>/dev/null
    fi

    # Count files installed for verification
    installed_files=$(find "$INSTALL_DIR" -type f | wc -l)
    echo "$installed_files" > /tmp/nak_count.txt

    # Debug final structure
    echo "DEBUG: Installed files:"
    find "$INSTALL_DIR" -type f | sort
} #&>/tmp/nak_install.log

INSTALL_PID=$!
spinner $INSTALL_PID

# Check if installation succeeded
if [ -f "$INSTALL_DIR/main-script.sh" ]; then
    echo -e "${GREEN}Done!${NC}"
    INSTALLED_COUNT=$(cat /tmp/nak_count.txt 2>/dev/null || echo "several")
    echo -e "${GREEN}Successfully installed NaK with $INSTALLED_COUNT files.${NC}"

    # If only one file was installed, something is wrong
    if [ "$INSTALLED_COUNT" -eq 1 ]; then
        echo -e "${YELLOW}Warning: Only the main script was installed. Installation may be incomplete.${NC}"
        echo -e "Check the installation log at /tmp/nak_install.log for details."
    fi
else
    echo -e "${RED}Failed!${NC}"
    echo -e "${RED}Installation failed. Could not install required files.${NC}"
    echo -e "Check the installation log at /tmp/nak_install.log for details."
    cat /tmp/nak_install.log
    rm -f /tmp/nak_count.txt
    rm -rf "$TMP_DIR" 2>/dev/null
    exit 1
fi

# Clean up
rm -f /tmp/nak_count.txt
rm -rf "$TMP_DIR" 2>/dev/null

echo -e "Would you like to run NaK now?"
read -p "Run now? [Y/n]: " run_response
if [[ "$run_response" =~ ^[Yy]$ ]] || [[ -z "$run_response" ]]; then
    echo -e "${BLUE}Starting NaK...${NC}"

    # IMPORTANT: We use bash to run the script instead of exec
    # This prevents potential recursion issues
    bash "$INSTALL_DIR/main-script.sh"

    # Exit immediately after running to prevent continuing this script
    exit 0
else
    echo -e "You can run the script later with: ${BLUE}$INSTALL_DIR/main-script.sh${NC}"
    echo -e "Or simply type: ${BLUE}nak${NC} (if ~/.local/bin is in your PATH)"
fi

exit 0
