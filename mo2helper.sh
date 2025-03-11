#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Define install directory
INSTALL_DIR="$HOME/mo2helper"

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

# Check if mo2helper directory already exists
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}MO2 Helper is already installed at $INSTALL_DIR${NC}"
    echo -e "Would you like to update to the latest version? This will delete the existing installation."
    read -p "Update MO2 Helper? [y/N]: " update_response
    if [[ "$update_response" =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Removing existing installation...${NC}"
        rm -rf "$INSTALL_DIR"
    else
        echo -e "Update canceled. Exiting."
        exit 0
    fi
fi

echo -e "${BLUE}Installing MO2 Helper...${NC}"

# Create directories if they don't exist
mkdir -p "$INSTALL_DIR/lib/games" "$INSTALL_DIR/lib/ttw"

# Clone the repository to a temporary location
TMP_DIR=$(mktemp -d)
echo -ne "${BLUE}Downloading files...${NC} "
# Run git clone in the background
git clone -q https://github.com/SulfurNitride/Linux-MO2-Helper.git "$TMP_DIR" &
# Get the process ID
GIT_PID=$!
# Show spinner while git clone is running
spinner $GIT_PID
echo -e "${GREEN}Done!${NC}"

# Process the repository quietly
echo -ne "${BLUE}Setting up MO2 Helper...${NC} "

# Run the installation in the background and capture output
{
    # Look for modules in the repository structure
    find "$TMP_DIR" -type f -name "*.sh" > /tmp/mo2helper_files.txt

    # Check if the repository has mo2helper directory (most likely structure based on paste)
    if [ -d "$TMP_DIR/mo2helper" ] && [ -f "$TMP_DIR/mo2helper/main-script.sh" ]; then
        # Copy modular structure from mo2helper directory
        cp "$TMP_DIR/mo2helper/main-script.sh" "$INSTALL_DIR/main-script.sh"

        if [ -d "$TMP_DIR/mo2helper/lib" ]; then
            cp "$TMP_DIR/mo2helper/lib/"*.sh "$INSTALL_DIR/lib/" 2>/dev/null || true

            if [ -d "$TMP_DIR/mo2helper/lib/games" ]; then
                cp "$TMP_DIR/mo2helper/lib/games/"*.sh "$INSTALL_DIR/lib/games/" 2>/dev/null || true
            fi

            if [ -d "$TMP_DIR/mo2helper/lib/ttw" ]; then
                cp "$TMP_DIR/mo2helper/lib/ttw/"*.sh "$INSTALL_DIR/lib/ttw/" 2>/dev/null || true
            fi
        fi
    else
        # Use the last resort method if structure isn't as expected
        # Copy main script
        MAIN_SCRIPT=$(find "$TMP_DIR" -name "main-script.sh" -o -name "main-script.sh" | head -n 1)
        if [ -n "$MAIN_SCRIPT" ]; then
            cp "$MAIN_SCRIPT" "$INSTALL_DIR/main-script.sh"
        else
            SCRIPT_FILE=$(find "$TMP_DIR" -name "*.sh" | head -n 1)
            if [ -n "$SCRIPT_FILE" ]; then
                cp "$SCRIPT_FILE" "$INSTALL_DIR/main-script.sh"
            fi
        fi

        # Core modules
        for module in core logging config error ui utils proton; do
            MODULE_FILE=$(find "$TMP_DIR" -name "$module.sh" | head -n 1)
            if [ -n "$MODULE_FILE" ]; then
                cp "$MODULE_FILE" "$INSTALL_DIR/lib/$module.sh"
            fi
        done

        # Game modules
        for module in common fallout enderal bg3; do
            MODULE_FILE=$(find "$TMP_DIR" -name "$module.sh" | head -n 1)
            if [ -n "$MODULE_FILE" ]; then
                cp "$MODULE_FILE" "$INSTALL_DIR/lib/games/$module.sh"
            fi
        done

        # TTW modules
        for module in installation hoolamike; do
            MODULE_FILE=$(find "$TMP_DIR" -name "$module.sh" | head -n 1)
            if [ -n "$MODULE_FILE" ]; then
                cp "$MODULE_FILE" "$INSTALL_DIR/lib/ttw/$module.sh"
            fi
        done
    fi

    # Check if we need a combined script as fallback
    if [ ! -f "$INSTALL_DIR/lib/core.sh" ] || [ ! -f "$INSTALL_DIR/lib/logging.sh" ]; then
        COMBINED_FILE=$(find "$TMP_DIR" -name "*combined*.sh" -o -name "*all*.sh" -o -name "mo2helperupdated.sh" | head -n 1)
        if [ -n "$COMBINED_FILE" ]; then
            cp "$COMBINED_FILE" "$INSTALL_DIR/main-script.sh"
        fi
    fi

    # Make scripts executable
    find "$INSTALL_DIR" -name "*.sh" -exec chmod +x {} \; 2>/dev/null

    # Count installed files to verify success
    INSTALLED_FILES=$(find "$INSTALL_DIR" -type f | wc -l)
    echo "$INSTALLED_FILES" > /tmp/mo2helper_installed.txt

} &>/tmp/mo2helper_install.log &

INSTALL_PID=$!
spinner $INSTALL_PID

# Check if installation succeeded
if [ -f "$INSTALL_DIR/main-script.sh" ]; then
    # Count how many files were installed
    INSTALLED_COUNT=$(cat /tmp/mo2helper_installed.txt)
    echo -e "${GREEN}Done!${NC}"
    echo -e "${GREEN}Successfully installed MO2 Helper with $INSTALLED_COUNT files.${NC}"
else
    echo -e "${RED}Failed!${NC}"
    echo -e "${RED}Installation failed. Here's what went wrong:${NC}"
    cat /tmp/mo2helper_install.log
    echo -e "${YELLOW}Please check the repository structure and try again.${NC}"
    rm -f /tmp/mo2helper_files.txt /tmp/mo2helper_installed.txt /tmp/mo2helper_install.log
    rm -rf "$TMP_DIR"
    exit 1
fi

# Clean up
rm -f /tmp/mo2helper_files.txt /tmp/mo2helper_installed.txt /tmp/mo2helper_install.log
rm -rf "$TMP_DIR"

# Verify installation
if [ -f "$INSTALL_DIR/main-script.sh" ]; then

    # Ask to run the script automatically
    echo -e "Would you like to run MO2 Helper now?"
    read -p "Run now? [Y/n]: " run_response
    if [[ "$run_response" =~ ^[Yy]$ ]] || [[ -z "$run_response" ]]; then
        echo -e "${BLUE}Starting MO2 Helper...${NC}"
        exec "$INSTALL_DIR/main-script.sh"
    else
        echo -e "You can run the script later with: ${BLUE}$INSTALL_DIR/main-script.sh${NC}"
        if [[ "$response" =~ ^[Yy]$ ]]; then
            echo -e "Or simply type: ${BLUE}mo2helper${NC}"
        fi
    fi
else
    echo -e "${RED}Installation failed. Script not found in installation directory.${NC}"
    echo -e "${YELLOW}Please check the repository structure and try again.${NC}"
    exit 1
fi
