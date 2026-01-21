#!/bin/bash
# NaK Winetricks GUI Script
#
# Opens the Winetricks GUI for this mod manager's Wine prefix.
# Use this to install additional Windows components or DLLs.

PREFIX="{{PREFIX_PATH}}"
NAK_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nak"
NAK_WINETRICKS="$NAK_CONFIG_DIR/bin/winetricks"

# Find winetricks - prefer NaK's bundled version (auto-updated)
if [ -x "$NAK_WINETRICKS" ]; then
    WINETRICKS_BIN="$NAK_WINETRICKS"
    echo "Using NaK bundled winetricks"
elif command -v winetricks &> /dev/null; then
    WINETRICKS_BIN="winetricks"
    echo "Using system winetricks"
else
    echo "ERROR: winetricks is not available."
    echo ""
    echo "NaK should have downloaded winetricks automatically."
    echo "If this persists, try restarting NaK or install manually:"
    echo "  - Arch/CachyOS: sudo pacman -S winetricks"
    echo "  - Ubuntu/Debian: sudo apt install winetricks"
    echo "  - Fedora: sudo dnf install winetricks"
    echo ""
    read -r -p "Press Enter to exit..."
    exit 1
fi

if [ ! -d "$PREFIX" ]; then
    echo "ERROR: Wine prefix not found at: $PREFIX"
    echo "The prefix may not have been created yet."
    echo "Try launching the mod manager through Steam first."
    read -r -p "Press Enter to exit..."
    exit 1
fi

echo "Opening Winetricks GUI for prefix:"
echo "$PREFIX"
echo ""

WINEPREFIX="$PREFIX" "$WINETRICKS_BIN" --gui
