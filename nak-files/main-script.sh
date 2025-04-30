#!/bin/bash
# -------------------------------------------------------------------
# nak.sh
# Unified script with NXM handler, Proton setup, and TTW integration
# Main entry point that sources all modules
# -------------------------------------------------------------------

# Script metadata
SCRIPT_VERSION="1.4.0"
SCRIPT_DATE="$(date +%Y-%m-%d)"

# Define script directory to find modules
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LIB_DIR="$SCRIPT_DIR/lib"

# Source core modules first
source "$LIB_DIR/logging.sh"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/error.sh"
source "$LIB_DIR/utils.sh"
source "$LIB_DIR/ui.sh"
source "$LIB_DIR/proton.sh"
source "$LIB_DIR/portablepython.sh"
source "$LIB_DIR/vdf.sh"
source "$LIB_DIR/mo2download.sh"
source "$LIB_DIR/sky-tex-opti.sh"

# Source game modules
source "$LIB_DIR/games/games.sh"
source "$LIB_DIR/games/fallout.sh"
source "$LIB_DIR/games/enderal.sh"
source "$LIB_DIR/games/bg3.sh"

# Source TTW modules
source "$LIB_DIR/ttw/hoolamike.sh"
source "$LIB_DIR/ttw/installation.sh"

source "$LIB_DIR/core.sh"
# ===== SCRIPT INITIALIZATION ======

# Initialize
setup_logging
create_default_config
load_cached_values
log_info "Starting NaK version $SCRIPT_VERSION"
log_system_info

# Welcome message
print_header
echo -e "Welcome to NaK - The Mod Organizer 2 Linux Helper!"
echo -e "This script will help you set up and configure Mod Organizer 2 for Linux."
echo -e "\nPress any key to start..."
read -n 1

# Check for updates if enabled
if [ "$(get_config "check_updates" "true")" == "true" ]; then
    check_for_updates
fi

# Set up trap to handle errors and cleanup
trap cleanup EXIT INT TERM

# Main program loop
main_menu

# This point should never be reached
exit 0
