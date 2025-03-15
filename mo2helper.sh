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
echo -ne "${BLUE}Setting up MO2 Helper...${NC} "

{
    # If structured correctly in mo2helper subdirectory (matches your paste)
    if [ -d "$TMP_DIR/mo2helper" ] && [ -f "$TMP_DIR/mo2helper/main-script.sh" ]; then
        # Copy main script
        cp "$TMP_DIR/mo2helper/main-script.sh" "$INSTALL_DIR/main-script.sh" 2>/dev/null

        # Copy the library files
        find "$TMP_DIR/mo2helper/lib" -name "*.sh" -exec cp {} "$INSTALL_DIR/lib/" 2>/dev/null \;

        # Copy game modules
        find "$TMP_DIR/mo2helper/lib/games" -name "*.sh" -exec cp {} "$INSTALL_DIR/lib/games/" 2>/dev/null \;

        # Copy TTW modules
        find "$TMP_DIR/mo2helper/lib/ttw" -name "*.sh" -exec cp {} "$INSTALL_DIR/lib/ttw/" 2>/dev/null \;
    else
        # Fallback - look for any scripts
        if [ -f "$TMP_DIR/main-script.sh" ]; then
            cp "$TMP_DIR/main-script.sh" "$INSTALL_DIR/main-script.sh" 2>/dev/null
        else
            # Desperate search
            find "$TMP_DIR" -name "*.sh" | head -n 1 | xargs -I{} cp {} "$INSTALL_DIR/main-script.sh" 2>/dev/null
        fi
    fi

    # Make scripts executable
    chmod +x "$INSTALL_DIR"/*.sh 2>/dev/null
    find "$INSTALL_DIR" -name "*.sh" -exec chmod +x {} \; 2>/dev/null

    # Count files installed for verification
    find "$INSTALL_DIR" -type f | wc -l > /tmp/mo2helper_count.txt
} &>/dev/null

INSTALL_PID=$!
spinner $INSTALL_PID

# Check if installation succeeded
if [ -f "$INSTALL_DIR/main-script.sh" ]; then
    echo -e "${GREEN}Done!${NC}"
    INSTALLED_COUNT=$(cat /tmp/mo2helper_count.txt 2>/dev/null || echo "several")
    echo -e "${GREEN}Successfully installed MO2 Helper with $INSTALLED_COUNT files.${NC}"
else
    echo -e "${RED}Failed!${NC}"
    echo -e "${RED}Installation failed. Could not install required files.${NC}"
    rm -f /tmp/mo2helper_count.txt
    rm -rf "$TMP_DIR" 2>/dev/null
    exit 1
fi

# Clean up
rm -f /tmp/mo2helper_count.txt
rm -rf "$TMP_DIR" 2>/dev/null

# Ask to run the script
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
