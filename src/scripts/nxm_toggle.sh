#!/bin/bash
# NaK NXM Toggle Script
# For Steam-native {{MANAGER_NAME}} installation (AppID: {{APP_ID}})
#
# This script toggles NXM link handling for this mod manager instance.
# When enabled, clicking nxm:// links will open this instance.

# Terminal auto-launch if double-clicked
if [ ! -t 0 ]; then
    for term in konsole gnome-terminal xfce4-terminal kitty alacritty xterm; do
        if command -v "$term" &> /dev/null; then
            case "$term" in
                konsole) exec "$term" --hold -e "$0" "$@" ;;
                gnome-terminal) exec "$term" -- "$0" "$@" ;;
                xfce4-terminal) exec "$term" --hold -e "$0" "$@" ;;
                kitty) exec "$term" --hold "$0" "$@" ;;
                alacritty) exec "$term" --hold -e "$0" "$@" ;;
                xterm) exec "$term" -hold -e "$0" "$@" ;;
            esac
        fi
    done
    echo "ERROR: No terminal found. Run from terminal."
    exit 1
fi

APP_ID={{APP_ID}}
MANAGER_NAME="{{MANAGER_NAME}}"
NXM_EXE="{{NXM_EXE}}"
PREFIX_PATH="{{PREFIX_PATH}}"
DEFAULT_PROTON_PATH="{{PROTON_PATH}}"
NAK_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nak"
ACTIVE_APPID_FILE="$NAK_CONFIG_DIR/active_nxm_appid"
ACTIVE_EXE_FILE="$NAK_CONFIG_DIR/active_nxm_exe"
ACTIVE_PREFIX_FILE="$NAK_CONFIG_DIR/active_nxm_prefix"
ACTIVE_PROTON_FILE="$NAK_CONFIG_DIR/active_nxm_proton"

# Find Steam path
if [ -d "$HOME/.steam/steam" ]; then
    STEAM_PATH="$HOME/.steam/steam"
elif [ -d "$HOME/.local/share/Steam" ]; then
    STEAM_PATH="$HOME/.local/share/Steam"
else
    STEAM_PATH=""
fi

echo "=================================================="
echo "NaK NXM Handler Toggle"
echo "Manager: $MANAGER_NAME"
echo "Steam AppID: $APP_ID"
echo "=================================================="
echo ""

# Function to find all available Protons
find_all_protons() {
    declare -g -a PROTON_PATHS=()
    declare -g -a PROTON_NAMES=()

    # Search locations
    local search_dirs=()
    [ -n "$STEAM_PATH" ] && search_dirs+=("$STEAM_PATH/steamapps/common")
    [ -n "$STEAM_PATH" ] && search_dirs+=("$STEAM_PATH/compatibilitytools.d")
    search_dirs+=("/usr/share/steam/compatibilitytools.d")

    for search_dir in "${search_dirs[@]}"; do
        [ ! -d "$search_dir" ] && continue

        for dir in "$search_dir"/*/; do
            [ ! -d "$dir" ] && continue
            if [ -f "$dir/proton" ]; then
                local name
                name=$(basename "$dir")
                # Filter to Proton 10+ (skip older versions)
                if [[ "$name" == *"GE-Proton"* ]]; then
                    # GE-Proton: check version number
                    local ver
                    ver=$(echo "$name" | sed -n 's/GE-Proton\([0-9]*\).*/\1/p')
                    [ -n "$ver" ] && [ "$ver" -lt 10 ] && continue
                elif [[ "$name" == "Proton "* ]]; then
                    # Steam Proton: check version
                    local ver
                    ver=$(echo "$name" | sed -n 's/Proton \([0-9]*\).*/\1/p')
                    [ -n "$ver" ] && [ "$ver" -lt 10 ] && continue
                fi
                PROTON_PATHS+=("${dir%/}")
                PROTON_NAMES+=("$name")
            fi
        done
    done
}

# Function to select Proton
select_proton() {
    find_all_protons

    if [ ${#PROTON_PATHS[@]} -eq 0 ]; then
        echo "ERROR: No Proton installations found!"
        echo "Please install Proton via Steam or ProtonUp-Qt."
        return 1
    fi

    echo ""
    echo "Available Proton versions:"
    echo ""
    for i in "${!PROTON_NAMES[@]}"; do
        local marker=""
        # Mark the default/currently configured one
        if [ "${PROTON_PATHS[$i]}" == "$DEFAULT_PROTON_PATH" ]; then
            marker=" (default)"
        elif [ -f "$ACTIVE_PROTON_FILE" ] && [ "${PROTON_PATHS[$i]}" == "$(cat "$ACTIVE_PROTON_FILE")" ]; then
            marker=" (current)"
        fi
        echo "  $((i+1)). ${PROTON_NAMES[$i]}$marker"
    done
    echo ""

    read -r -p "Select Proton (1-${#PROTON_PATHS[@]}): " choice

    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt ${#PROTON_PATHS[@]} ]; then
        echo "Invalid selection, using default."
        SELECTED_PROTON="$DEFAULT_PROTON_PATH"
    else
        SELECTED_PROTON="${PROTON_PATHS[$((choice-1))]}"
    fi

    echo ""
    echo "Selected: $(basename "$SELECTED_PROTON")"
}

enable_nxm() {
    select_proton || return 1

    mkdir -p "$NAK_CONFIG_DIR"
    echo "$APP_ID" > "$ACTIVE_APPID_FILE"
    echo "$NXM_EXE" > "$ACTIVE_EXE_FILE"
    echo "$PREFIX_PATH" > "$ACTIVE_PREFIX_FILE"
    echo "$SELECTED_PROTON" > "$ACTIVE_PROTON_FILE"
    echo ""
    echo "NXM handling enabled for this instance"
    echo "  Using Proton: $(basename "$SELECTED_PROTON")"
}

disable_nxm() {
    rm -f "$ACTIVE_APPID_FILE" "$ACTIVE_EXE_FILE" "$ACTIVE_PREFIX_FILE" "$ACTIVE_PROTON_FILE"
    echo ""
    echo "NXM handling disabled for this instance"
}

change_proton() {
    select_proton || return 1
    echo "$SELECTED_PROTON" > "$ACTIVE_PROTON_FILE"
    echo ""
    echo "Proton updated to: $(basename "$SELECTED_PROTON")"
}

# Check current status
if [ -f "$ACTIVE_APPID_FILE" ]; then
    CURRENT_APPID=$(cat "$ACTIVE_APPID_FILE")
    if [ "$CURRENT_APPID" == "$APP_ID" ]; then
        CURRENT_PROTON=""
        [ -f "$ACTIVE_PROTON_FILE" ] && CURRENT_PROTON=$(basename "$(cat "$ACTIVE_PROTON_FILE")")
        echo "Status: ENABLED (this instance handles NXM links)"
        [ -n "$CURRENT_PROTON" ] && echo "Proton: $CURRENT_PROTON"
        echo ""
        echo "Options:"
        echo "  1. Disable NXM handling"
        echo "  2. Change Proton version"
        echo "  3. Keep current settings"
        read -r -p "Choice (1-3): " choice

        case "$choice" in
            1) disable_nxm ;;
            2) change_proton ;;
            *) echo "Keeping current settings." ;;
        esac
    else
        echo "Status: DISABLED (another instance handles NXM: AppID $CURRENT_APPID)"
        echo ""
        echo "Options:"
        echo "  1. Enable NXM handling for THIS instance (disables other)"
        echo "  2. Keep current setting"
        read -r -p "Choice (1-2): " choice

        if [ "$choice" == "1" ]; then
            enable_nxm
        else
            echo "Keeping current setting."
        fi
    fi
else
    echo "Status: DISABLED (no instance handles NXM links)"
    echo ""
    echo "Options:"
    echo "  1. Enable NXM handling for this instance"
    echo "  2. Keep disabled"
    read -r -p "Choice (1-2): " choice

    if [ "$choice" == "1" ]; then
        enable_nxm
        echo ""
        echo "Make sure the NXM handler is installed. Run NaK and check Settings."
    else
        echo "Keeping NXM handling disabled."
    fi
fi

echo ""
echo "Done!"
