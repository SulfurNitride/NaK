#!/bin/bash
# NaK Fix Game Registry Script
# For Steam-native {{MANAGER_NAME}} installation
#
# This script helps fix game installation paths in the Wine registry
# so that {{MANAGER_NAME}} can properly detect installed games.

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

PREFIX="{{PREFIX_PATH}}"
PROTON_PATH="{{PROTON_PATH}}"
WINE_BIN="$PROTON_PATH/files/bin/wine"

# Check if Proton wine exists
if [ ! -x "$WINE_BIN" ]; then
    echo "ERROR: Proton wine not found at: $WINE_BIN"
    echo "The Proton installation may have been moved or deleted."
    exit 1
fi

echo "=================================================="
echo "NaK Game Registry Fixer"
echo "Prefix: $PREFIX"
echo "=================================================="
echo ""

# Game configurations
declare -a GAMES=(
    "Enderal|Software\\SureAI\\Enderal|Install_Path"
    "Enderal Special Edition|Software\\SureAI\\Enderal SE|installed path"
    "Fallout 3|Software\\Bethesda Softworks\\Fallout3|Installed Path"
    "Fallout 4|Software\\Bethesda Softworks\\Fallout4|Installed Path"
    "Fallout 4 VR|Software\\Bethesda Softworks\\Fallout 4 VR|Installed Path"
    "Fallout New Vegas|Software\\Bethesda Softworks\\FalloutNV|Installed Path"
    "Morrowind|Software\\Bethesda Softworks\\Morrowind|Installed Path"
    "Oblivion|Software\\Bethesda Softworks\\Oblivion|Installed Path"
    "Skyrim|Software\\Bethesda Softworks\\Skyrim|Installed Path"
    "Skyrim Special Edition|Software\\Bethesda Softworks\\Skyrim Special Edition|Installed Path"
    "Skyrim VR|Software\\Bethesda Softworks\\Skyrim VR|Installed Path"
    "Starfield|Software\\Bethesda Softworks\\Starfield|Installed Path"
)

echo "Which game do you want to fix the registry for?"
echo ""
for i in "${!GAMES[@]}"; do
    game_name="${GAMES[$i]%%|*}"
    echo "  $((i+1)). $game_name"
done
echo ""
read -r -p "Enter number (1-${#GAMES[@]}): " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#GAMES[@]}" ]; then
    echo "ERROR: Invalid selection"
    exit 1
fi

selected="${GAMES[$((choice-1))]}"
GAME_NAME="${selected%%|*}"
rest="${selected#*|}"
REG_PATH="${rest%%|*}"
VALUE_NAME="${rest##*|}"

echo ""
echo "Selected: $GAME_NAME"
echo ""
echo "Enter the LINUX path to the game installation:"
echo "(e.g., /home/user/.steam/steam/steamapps/common/Skyrim Special Edition)"
read -r -p "Game path: " GAME_PATH

if [ ! -d "$GAME_PATH" ]; then
    echo "WARNING: Directory does not exist. Continue anyway? (y/n)"
    read -r confirm
    if [ "$confirm" != "y" ]; then
        exit 1
    fi
fi

# Convert to Wine path
WINE_PATH_DISPLAY="Z:${GAME_PATH//\//\\}"
# Double backslashes for .reg file format
WINE_PATH_REG="Z:${GAME_PATH//\//\\\\}"

echo ""
echo "=================================================="
echo "Registry Fix Details"
echo "=================================================="
echo "Game: $GAME_NAME"
echo "Linux Path: $GAME_PATH"
echo "Wine Path: $WINE_PATH_DISPLAY"
echo "Registry Key: HKLM\\$REG_PATH"
echo "Value: $VALUE_NAME"
echo "=================================================="
echo ""
read -r -p "Apply this fix? (y/n): " apply

if [ "$apply" != "y" ]; then
    echo "Cancelled."
    exit 0
fi

# Create .reg file
REG_FILE=$(mktemp --suffix=.reg)
cat > "$REG_FILE" << EOF
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\$REG_PATH]
"$VALUE_NAME"="$WINE_PATH_REG"

[HKEY_LOCAL_MACHINE\\SOFTWARE\\Wow6432Node\\${REG_PATH#Software\\}]
"$VALUE_NAME"="$WINE_PATH_REG"
EOF

echo "Applying registry fix..."
if WINEPREFIX="$PREFIX" "$WINE_BIN" regedit "$REG_FILE" 2>/dev/null; then
    echo ""
    echo "Registry fix applied successfully!"
else
    echo ""
    echo "Registry fix may have failed. Check manually."
fi

rm -f "$REG_FILE"
echo ""
echo "Done! You may need to restart {{MANAGER_NAME}} for changes to take effect."
