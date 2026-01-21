#!/bin/bash
# NaK Steam Launch Script for {{MANAGER_NAME}}
# Launches via Steam using the 64-bit game ID format for non-Steam shortcuts
#
# Use this to manually launch the mod manager through Steam.
# This is equivalent to clicking Play in Steam.

# 64-bit Game ID (required for non-Steam shortcuts)
GAME_ID={{GAME_ID}}

echo "Launching {{MANAGER_NAME}} via Steam..."
xdg-open "steam://rungameid/$GAME_ID"
