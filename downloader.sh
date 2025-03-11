#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Define install directory
INSTALL_DIR="$HOME/mo2helper"

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
echo -e "${BLUE}Cloning repository to temporary directory...${NC}"
git clone https://github.com/SulfurNitride/Linux-MO2-Helper.git "$TMP_DIR"

# Check if the repository has the expected structure
# First, look for main-script.sh (the user's actual main script name)
if [ -f "$TMP_DIR/main-script.sh" ]; then
    echo -e "${GREEN}Found main script in repository.${NC}"
    cp "$TMP_DIR/main-script.sh" "$INSTALL_DIR/main-script.sh"

    # Copy module files if they exist
    if [ -d "$TMP_DIR/lib" ]; then
        if [ -n "$(ls -A "$TMP_DIR/lib/" 2>/dev/null)" ]; then
            cp "$TMP_DIR/lib/"*.sh "$INSTALL_DIR/lib/" 2>/dev/null || true
        fi

        if [ -d "$TMP_DIR/lib/games" ] && [ -n "$(ls -A "$TMP_DIR/lib/games/" 2>/dev/null)" ]; then
            cp "$TMP_DIR/lib/games/"*.sh "$INSTALL_DIR/lib/games/" 2>/dev/null || true
        fi

        if [ -d "$TMP_DIR/lib/ttw" ] && [ -n "$(ls -A "$TMP_DIR/lib/ttw/" 2>/dev/null)" ]; then
            cp "$TMP_DIR/lib/ttw/"*.sh "$INSTALL_DIR/lib/ttw/" 2>/dev/null || true
        fi
    fi
# Also check for main-script.sh as a fallback
elif [ -f "$TMP_DIR/main-script.sh" ]; then
    echo -e "${GREEN}Found main-script.sh in repository.${NC}"
    cp "$TMP_DIR/main-script.sh" "$INSTALL_DIR/main-script.sh"

    # Copy module files if they exist
    if [ -d "$TMP_DIR/lib" ]; then
        if [ -n "$(ls -A "$TMP_DIR/lib/" 2>/dev/null)" ]; then
            cp "$TMP_DIR/lib/"*.sh "$INSTALL_DIR/lib/" 2>/dev/null || true
        fi

        if [ -d "$TMP_DIR/lib/games" ] && [ -n "$(ls -A "$TMP_DIR/lib/games/" 2>/dev/null)" ]; then
            cp "$TMP_DIR/lib/games/"*.sh "$INSTALL_DIR/lib/games/" 2>/dev/null || true
        fi

        if [ -d "$TMP_DIR/lib/ttw" ] && [ -n "$(ls -A "$TMP_DIR/lib/ttw/" 2>/dev/null)" ]; then
            cp "$TMP_DIR/lib/ttw/"*.sh "$INSTALL_DIR/lib/ttw/" 2>/dev/null || true
        fi
    fi
else
    # Check if this is a different structure (modules in artifacts)
    if [ -d "$TMP_DIR/artifacts" ]; then
        echo -e "${YELLOW}Using artifacts directory structure...${NC}"

        # Create the modular structure
        mkdir -p "$INSTALL_DIR/lib/games" "$INSTALL_DIR/lib/ttw"

        # Copy main script - first look for main-script
        if [ -f "$TMP_DIR/artifacts/main-script.txt" ]; then
            cp "$TMP_DIR/artifacts/main-script.txt" "$INSTALL_DIR/main-script.sh"
        else
            echo -e "${YELLOW}Looking for alternative main script name...${NC}"
            # Try to find it with another name
            MAIN_SCRIPT=$(find "$TMP_DIR/artifacts" -name "*main*.txt" -o -name "*script*.txt" | head -n 1)
            if [ -n "$MAIN_SCRIPT" ]; then
                cp "$MAIN_SCRIPT" "$INSTALL_DIR/main-script.sh"
            else
                echo -e "${RED}Could not find main script!${NC}"
                exit 1
            fi
        fi

        # Copy core modules
        for module in core logging config error ui utils proton; do
            MODULE_FILE=$(find "$TMP_DIR/artifacts" -name "*$module*.txt" | head -n 1)
            if [ -n "$MODULE_FILE" ]; then
                cp "$MODULE_FILE" "$INSTALL_DIR/lib/$module.sh"
            fi
        done

        # Copy game modules
        for module in common fallout enderal bg3; do
            MODULE_FILE=$(find "$TMP_DIR/artifacts" -name "*$module*.txt" | head -n 1)
            if [ -n "$MODULE_FILE" ]; then
                cp "$MODULE_FILE" "$INSTALL_DIR/lib/games/$module.sh"
            fi
        done

        # Copy TTW modules
        for module in installation hoolamike; do
            MODULE_FILE=$(find "$TMP_DIR/artifacts" -name "*$module*.txt" | head -n 1)
            if [ -n "$MODULE_FILE" ]; then
                cp "$MODULE_FILE" "$INSTALL_DIR/lib/ttw/$module.sh"
            fi
        done
    else
        # If it's just a single file
        echo -e "${YELLOW}Looking for a single script file...${NC}"
        SCRIPT_FILE=$(find "$TMP_DIR" -name "*.sh" | head -n 1)
        if [ -n "$SCRIPT_FILE" ]; then
            cp "$SCRIPT_FILE" "$INSTALL_DIR/main-script.sh"
        else
            echo -e "${RED}Could not find any shell scripts in the repository!${NC}"
            exit 1
        fi
    fi
fi

# Make scripts executable (only if they exist)
find "$INSTALL_DIR" -name "*.sh" -exec chmod +x {} \;

# Clean up
rm -rf "$TMP_DIR"

# Verify installation
if [ -f "$INSTALL_DIR/main-script.sh" ]; then
    echo -e "${GREEN}Installation complete!${NC}"

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
    echo -e "${RED}Installation failed. Could not find script in installation directory.${NC}"
    echo -e "${YELLOW}Please check the repository structure and try again.${NC}"
    exit 1
fi
