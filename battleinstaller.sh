#!/bin/bash
# -------------------------------------------------------------------
# battleinstaller.sh
# Script to download Battle.net installer and run it with Proton Experimental Wine
# -------------------------------------------------------------------

# Terminal colors
COLOR_GREEN="\033[0;32m"
COLOR_YELLOW="\033[0;33m"
COLOR_RED="\033[0;31m"
COLOR_BLUE="\033[0;34m"
COLOR_RESET="\033[0m"

# --- User Configuration ---
# INSTALL_TARGET_DIR="/home/luke/Goonbob" # Linux path where Battle.net will be installed
# ------------------------

# Function to check for and kill a process
kill_process_if_running() {
    local process_name="$1"
    echo -e "${COLOR_YELLOW}Checking if '$process_name' process started automatically...${COLOR_RESET}"
    local pid
    pid=$(pgrep -f "$process_name")

    if [ -n "$pid" ]; then
        echo -e "${COLOR_YELLOW}'$process_name' process(es) found (PIDs: $pid). Terminating...${COLOR_RESET}"
        # Loop through each PID found and kill it
        for individual_pid in $pid; do
            kill "$individual_pid" 2>/dev/null
        done
        sleep 2 # Give processes a moment to terminate gracefully

        # Check if any are still running and force kill if necessary
        local remaining_pids
        remaining_pids=$(pgrep -f "$process_name")
        if [ -n "$remaining_pids" ]; then
             echo -e "${COLOR_YELLOW}Some '$process_name' processes did not terminate gracefully. Sending SIGKILL...${COLOR_RESET}"
             for individual_pid in $remaining_pids; do
                echo -e "${COLOR_YELLOW}Force killing PID: $individual_pid${COLOR_RESET}"
                kill -9 "$individual_pid" 2>/dev/null
             done
             sleep 1
        fi
        echo -e "${COLOR_GREEN}Termination attempt for '$process_name' complete.${COLOR_RESET}"
    else
        echo -e "${COLOR_GREEN}'$process_name' process not found running.${COLOR_RESET}"
    fi
}

# Function to find Proton Experimental across Steam libraries
find_proton_experimental() {
    echo -e "${COLOR_BLUE}Searching for Proton Experimental in Steam libraries...${COLOR_RESET}"
    local vdf_paths=(
        "$HOME/.local/share/Steam/steamapps/libraryfolders.vdf"
        "$HOME/.steam/steam/steamapps/libraryfolders.vdf"
    )
    local steam_libraries=("$HOME/.local/share/Steam") # Always check default location
    local library_vdf=""

    # Find the libraryfolders.vdf
    for path in "${vdf_paths[@]}"; do
        if [ -f "$path" ]; then
            library_vdf="$path"
            break
        fi
    done

    # Parse VDF if found
    if [ -n "$library_vdf" ]; then
        echo -e "Found libraryfolders.vdf at: $library_vdf"
        # Extract paths using grep and awk (handles paths with spaces)
        while IFS= read -r line; do
             # Extract path between the second set of quotes
             if [[ $line =~ \"path\"[[:space:]]+\"([^\"]+)\" ]]; then
                 steam_libraries+=("${BASH_REMATCH[1]}")
             fi
        done < <(grep '"path"' "$library_vdf")
    else
        echo -e "${COLOR_YELLOW}libraryfolders.vdf not found in standard locations. Checking only default Steam directory.${COLOR_RESET}"
    fi

    echo -e "Checking libraries:" 
    printf '%s\n' "${steam_libraries[@]}"

    # Search for Proton Experimental in each library
    for library in "${steam_libraries[@]}"; do
        local potential_proton_dir="$library/steamapps/common/Proton - Experimental"
        if [ -d "$potential_proton_dir" ]; then
            echo -e "${COLOR_GREEN}Found Proton Experimental at: $potential_proton_dir${COLOR_RESET}"
            PROTON_DIR="$potential_proton_dir"
            WINE_PATH="$PROTON_DIR/files/bin/wine"
            PROTON_RUN_SCRIPT="$PROTON_DIR/proton"
            # Basic validation
            if [ -f "$WINE_PATH" ] && [ -f "$PROTON_RUN_SCRIPT" ]; then
                return 0 # Success
            else
                echo -e "${COLOR_RED}Found directory, but missing wine/proton executables inside: $PROTON_DIR${COLOR_RESET}"
            fi
        fi
    done

    echo -e "${COLOR_RED}Error: Proton Experimental installation not found in any detected Steam library.${COLOR_RESET}"
    echo -e "Please ensure Proton Experimental is installed via Steam."
    return 1 # Failure
}

# Fixed paths based on your system - Now detected dynamically
# PROTON_DIR="$HOME/.local/share/Steam/steamapps/common/Proton - Experimental"
# WINE_PATH="$PROTON_DIR/files/bin/wine"
# PROTON_RUN_SCRIPT="$PROTON_DIR/proton"

echo -e "${COLOR_BLUE}===== Battle.net Launcher Setup =====${COLOR_RESET}"
echo -e "This script will download the Battle.net installer and run it with Proton Experimental."

# Get installation path from user
echo -e "\n${COLOR_BLUE}Where should Battle.net be installed?${COLOR_RESET}"
echo -e "Please provide the full desired Linux path."
read -e -p "Install path (Default: $HOME/Games/Battle.net): " INSTALL_TARGET_DIR
# Set default if empty
INSTALL_TARGET_DIR=${INSTALL_TARGET_DIR:-$HOME/Games/Battle.net}
echo -e "${COLOR_GREEN}Battle.net will be installed to: $INSTALL_TARGET_DIR${COLOR_RESET}"

# Detect Proton Experimental
if ! find_proton_experimental; then
    exit 1
fi

# Validate paths (executables are checked within find_proton_experimental now)
# if [ ! -d "$PROTON_DIR" ]; then
#     echo -e "${COLOR_RED}Cannot find Proton Experimental at: $PROTON_DIR${COLOR_RESET}"
#     exit 1
# fi

# if [ ! -f "$WINE_PATH" ]; then
#     echo -e "${COLOR_RED}Cannot find wine executable at: $WINE_PATH${COLOR_RESET}"
#     exit 1
# fi

# if [ ! -f "$PROTON_RUN_SCRIPT" ]; then
#     echo -e "${COLOR_RED}Cannot find Proton run script at: $PROTON_RUN_SCRIPT${COLOR_RESET}"
#     exit 1
# fi

echo -e "${COLOR_GREEN}Using Proton Experimental from: $PROTON_DIR${COLOR_RESET}"
echo -e "${COLOR_GREEN}Found wine executable: $WINE_PATH${COLOR_RESET}"
echo -e "${COLOR_GREEN}Found Proton run script: $PROTON_RUN_SCRIPT${COLOR_RESET}"

# Make wine executable
chmod +x "$WINE_PATH"

# Create a permanent directory for Battle.net
BATTLENET_DIR="$HOME/.battlenet"
WINEPREFIX="$BATTLENET_DIR/prefix"
INSTALLER="$BATTLENET_DIR/Battle.net-Setup.exe"
INSTALLER_URL="https://downloader.battle.net/download/getInstaller?os=win&installer=Battle.net-Setup.exe"

# Ensure target install directory exists (optional, Battle.net installer might do this)
mkdir -p "$INSTALL_TARGET_DIR"

# Create directories for prefix (still needed for Proton setup)
mkdir -p "$WINEPREFIX"

# Download the installer
echo -e "\n${COLOR_BLUE}Downloading Battle.net installer...${COLOR_RESET}"
if command -v curl &> /dev/null; then
    curl -L -o "$INSTALLER" "$INSTALLER_URL"
elif command -v wget &> /dev/null; then
    wget -O "$INSTALLER" "$INSTALLER_URL"
else
    echo -e "${COLOR_RED}Neither curl nor wget found. Please install one of them.${COLOR_RESET}"
    exit 1
fi

if [ ! -f "$INSTALLER" ]; then
    echo -e "${COLOR_RED}Failed to download installer.${COLOR_RESET}"
    exit 1
fi

echo -e "${COLOR_GREEN}Download complete!${COLOR_RESET}"

# Run the installer using proton run
echo -e "\n${COLOR_BLUE}Running Battle.net installer with Proton run script...${COLOR_RESET}"
echo -e "${COLOR_YELLOW}Please follow the installation instructions in the installer window.${COLOR_RESET}"
echo -e "${COLOR_YELLOW}The installer may take a few minutes to appear, please be patient.${COLOR_RESET}"

# Set required environment variables
export STEAM_COMPAT_DATA_PATH="$WINEPREFIX"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam"

# Run the installer using proton run
echo -e "Executing: STEAM_COMPAT_DATA_PATH=\"$WINEPREFIX\" \"$PROTON_RUN_SCRIPT\" run \"$INSTALLER\" --locale=enUS --installpath=\"Z:$INSTALL_TARGET_DIR\""
STEAM_COMPAT_DATA_PATH="$WINEPREFIX" "$PROTON_RUN_SCRIPT" run "$INSTALLER" --locale=enUS --installpath="Z:$INSTALL_TARGET_DIR"
INSTALL_STATUS=$?

# Check if Battle.net processes started automatically and kill them (looping attempts)
echo -e "${COLOR_BLUE}Attempting to terminate lingering Battle.net processes (3 attempts)...${COLOR_RESET}"
for i in {1..3}; do
    echo -e "${COLOR_YELLOW}--- Attempt $i ---${COLOR_RESET}"
    kill_process_if_running "Agent.exe"
    kill_process_if_running "Battle.net.exe"
    kill_process_if_running "CrBrowserMain"

    # Check if any are still running before sleeping
    agent_pid=$(pgrep -f "Agent.exe")
    bnet_pid=$(pgrep -f "Battle.net.exe")
    browser_pid=$(pgrep -f "CrBrowserMain")

    if [ -z "$agent_pid" ] && [ -z "$bnet_pid" ] && [ -z "$browser_pid" ]; then
        echo -e "${COLOR_GREEN}All targeted processes terminated.${COLOR_RESET}"
        break # Exit loop early if all processes are gone
    fi

    if [ $i -lt 3 ]; then
      echo -e "${COLOR_YELLOW}Waiting 1 second before next attempt...${COLOR_RESET}"
      sleep 1
    fi
done

# Final check after loops
agent_pid=$(pgrep -f "Agent.exe")
bnet_pid=$(pgrep -f "Battle.net.exe")
browser_pid=$(pgrep -f "CrBrowserMain")
if [ -n "$agent_pid" ] || [ -n "$bnet_pid" ] || [ -n "$browser_pid" ]; then
    echo -e "${COLOR_RED}Warning: Some Battle.net processes may still be running.${COLOR_RESET}"
fi

# Check installer exit status (optional continuation)
if [ $INSTALL_STATUS -ne 0 ]; then
    echo -e "${COLOR_RED}The installer encountered an error (status code: $INSTALL_STATUS).${COLOR_RESET}"
    echo -e "Would you like to continue anyway? (yes/no)"
    read -p "> " continue_anyway

    if [[ "$continue_anyway" != "yes" && "$continue_anyway" != "y" ]]; then
        echo -e "${COLOR_RED}Operation cancelled based on installer error. Exiting.${COLOR_RESET}"
        exit 1
    fi
fi

# Define launcher path based on specified install directory
LAUNCHER_PATH="$INSTALL_TARGET_DIR/Battle.net/Battle.net Launcher.exe"

# Display instructions for adding to Steam
echo -e "\n${COLOR_BLUE}Adding Battle.net Launcher to Steam...${COLOR_RESET}"

echo -e "\n${COLOR_GREEN}Battle.net installation finished. The prefix was created at $WINEPREFIX${COLOR_RESET}"
echo -e "\n${COLOR_YELLOW}To add it to Steam, follow these steps:${COLOR_RESET}"
echo -e "1. Open Steam"
echo -e "2. Click 'Games' in the menu -> 'Add a Non-Steam Game to My Library'"
echo -e "3. Browse to: $LAUNCHER_PATH"
echo -e "4. After adding, right-click on Battle.net Launcher in your Steam library"
echo -e "5. Select Properties"
echo -e "6. In the Compatibility tab, check 'Force the use of a specific Steam Play compatibility tool'"
echo -e "7. Select Proton Experimental from the dropdown menu"

# Cleanup
echo -e "
${COLOR_BLUE}Cleaning up installation directory...${COLOR_RESET}"
if [ -d "$BATTLENET_DIR" ]; then
    echo -e "Removing Battle.net directory: $BATTLENET_DIR"
    rm -rf "$BATTLENET_DIR"
    echo -e "${COLOR_GREEN}Directory removed.${COLOR_RESET}"
else
    echo -e "${COLOR_YELLOW}Battle.net directory not found, skipping removal: $BATTLENET_DIR${COLOR_RESET}"
fi

exit 0
