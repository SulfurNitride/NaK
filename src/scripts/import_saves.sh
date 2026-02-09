#!/bin/bash
# NaK Import Saves Script
# Imports game saves from your Steam game prefix into this mod manager prefix.
#
# This creates symlinks so your saves are shared between the game's Steam prefix
# and this mod manager prefix.

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

PREFIX_PATH="{{PREFIX_PATH}}"

echo "=================================================="
echo "NaK Import Saves from Steam"
echo "=================================================="
echo ""
echo "This will symlink your game saves/configs from your"
echo "Steam game prefix into this mod manager prefix."
echo ""
echo "Prefix: $PREFIX_PATH"
echo ""

# Game configurations (Display Name|My Games Folder|Steam App IDs comma-separated)
declare -a GAMES=(
    "Enderal|Enderal|933480"
    "Enderal Special Edition|Enderal Special Edition|976620"
    "Fallout 3|Fallout3|22300,22370"
    "Fallout 4|Fallout4|377160"
    "Fallout 4 VR|Fallout4VR|611660"
    "Fallout New Vegas|FalloutNV|22380"
    "Morrowind|Morrowind|22320"
    "Oblivion|Oblivion|22330"
    "Skyrim|Skyrim|72850"
    "Skyrim Special Edition|Skyrim Special Edition|489830"
    "Skyrim VR|Skyrim VR|611670"
    "Starfield|Starfield|1716740"
)

# Find Steam path
find_steam_path() {
    local paths=(
        "$HOME/.steam/steam"
        "$HOME/.local/share/Steam"
        "$HOME/.var/app/com.valvesoftware.Steam/.steam/steam"
    )
    for p in "${paths[@]}"; do
        if [ -d "$p" ]; then
            echo "$p"
            return 0
        fi
    done
    return 1
}

STEAM_PATH=$(find_steam_path)
if [ -z "$STEAM_PATH" ]; then
    echo "ERROR: Could not find Steam installation"
    exit 1
fi
echo "Found Steam at: $STEAM_PATH"
echo ""

echo "Which game's saves do you want to import?"
echo ""
for i in "${!GAMES[@]}"; do
    display_name="${GAMES[$i]%%|*}"
    echo "  $((i+1)). $display_name"
done
echo ""
read -r -p "Enter number (1-${#GAMES[@]}): " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#GAMES[@]}" ]; then
    echo "ERROR: Invalid selection"
    exit 1
fi

selected="${GAMES[$((choice-1))]}"
DISPLAY_NAME="${selected%%|*}"
rest="${selected#*|}"
FOLDER_NAME="${rest%%|*}"
APP_IDS="${rest##*|}"

echo ""
echo "Selected: $DISPLAY_NAME (App ID(s): $APP_IDS)"

# Find game prefix
STEAM_PREFIX=""
FOUND_APP_ID=""

IFS=',' read -ra APP_ID_CANDIDATES <<< "$APP_IDS"
for APP_ID in "${APP_ID_CANDIDATES[@]}"; do
    check_path="$STEAM_PATH/steamapps/compatdata/$APP_ID/pfx"
    if [ -d "$check_path" ]; then
        STEAM_PREFIX="$check_path"
        FOUND_APP_ID="$APP_ID"
        break
    fi
done

# Also check library folders
if [ -z "$STEAM_PREFIX" ] && [ -f "$STEAM_PATH/steamapps/libraryfolders.vdf" ]; then
    while IFS= read -r line; do
        if [[ "$line" =~ \"path\".*\"(.*)\" ]]; then
            lib_path="${BASH_REMATCH[1]}"
            for APP_ID in "${APP_ID_CANDIDATES[@]}"; do
                check_path="$lib_path/steamapps/compatdata/$APP_ID/pfx"
                if [ -d "$check_path" ]; then
                    STEAM_PREFIX="$check_path"
                    FOUND_APP_ID="$APP_ID"
                    break 2
                fi
            done
        fi
    done < "$STEAM_PATH/steamapps/libraryfolders.vdf"
fi

if [ -z "$STEAM_PREFIX" ]; then
    echo "ERROR: Could not find Steam prefix for $DISPLAY_NAME"
    echo "Make sure you've run the game at least once via Steam."
    exit 1
fi

echo "Found game prefix: $STEAM_PREFIX"
if [ -n "$FOUND_APP_ID" ]; then
    echo "Using App ID: $FOUND_APP_ID"
fi

# Get usernames
get_username() {
    local prefix="$1"
    for entry in "$prefix/drive_c/users"/*; do
        name=$(basename "$entry")
        if [ "$name" != "Public" ] && [ "$name" != "root" ]; then
            echo "$name"
            return
        fi
    done
    echo "steamuser"
}

STEAM_USER=$(get_username "$STEAM_PREFIX")
TARGET_USER=$(get_username "$PREFIX_PATH")

SOURCE_DIR="$STEAM_PREFIX/drive_c/users/$STEAM_USER/Documents/My Games/$FOLDER_NAME"
TARGET_DIR="$PREFIX_PATH/drive_c/users/$TARGET_USER/Documents/My Games/$FOLDER_NAME"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: No saves found at: $SOURCE_DIR"
    exit 1
fi

echo ""
echo "Source: $SOURCE_DIR"
echo "Target: $TARGET_DIR"
echo ""
read -r -p "Create symlink? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo "Cancelled."
    exit 0
fi

# Remove existing target if it's a directory or symlink
if [ -L "$TARGET_DIR" ]; then
    rm "$TARGET_DIR"
elif [ -d "$TARGET_DIR" ]; then
    echo "Target exists. Remove it? (y/n)"
    read -r remove
    if [ "$remove" == "y" ]; then
        rm -rf "$TARGET_DIR"
    else
        echo "Cancelled."
        exit 0
    fi
fi

mkdir -p "$(dirname "$TARGET_DIR")"
if ln -s "$SOURCE_DIR" "$TARGET_DIR"; then
    echo ""
    echo "Successfully linked $DISPLAY_NAME saves!"
else
    echo "Failed to create symlink"
    exit 1
fi

echo ""
echo "Done!"
