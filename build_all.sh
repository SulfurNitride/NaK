#!/bin/bash

# Complete build script for NaK with CPU compatibility
set -e

echo "============================================"
echo "Building NaK Linux Modding Helper"
echo "============================================"

cd /home/luke/Documents/NaK-Python

# Set CPU compatibility flag for broader support (v1 = baseline x86-64)
export GOAMD64=v1
export PATH=$PATH:/home/luke/go/bin

# Build Python backend
echo ""
echo "Building Python backend..."
pyinstaller nak_backend.spec --clean

# Build Wails GUI
echo ""
echo "Building Wails GUI..."
cd nak-gui
wails build
cd ..

# Create AppImage
echo ""
echo "Creating AppImage..."
rm -f NaK-Linux-Modding-Helper-Wails.AppImage
./create_wails_appimage.sh

echo ""
echo "============================================"
echo "✓ Build complete!"
echo "============================================"
ls -lh NaK-Linux-Modding-Helper-Wails.AppImage

