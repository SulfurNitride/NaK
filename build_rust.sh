#!/bin/bash

# Complete build script for NaK Linux Modding Helper
echo "============================================"
echo "NaK Linux Modding Helper - Complete Build"
echo "============================================"

cd /home/luke/Documents/NaK-Python

# Step 1: Build Python backend with PyInstaller
echo ""
echo "Step 1: Building Python backend with PyInstaller..."
pyinstaller nak_backend.spec --clean --noconfirm
if [ $? -ne 0 ]; then
    echo "❌ Python backend build failed!"
    exit 1
fi
echo "✓ Python backend built successfully"

# Step 2: Build Rust GUI
echo ""
echo "Step 2: Building Rust GUI..."

# Clean environment variables that might cause proxy issues
unset CARGO_PROXY
unset RUSTUP_PROXY
unset RUST_PROXY

# Use direct cargo path
CARGO_BIN="/home/luke/.cargo/bin/cargo"
RUSTC_BIN="/home/luke/.cargo/bin/rustc"

# Check if cargo exists
if [ ! -f "$CARGO_BIN" ]; then
    echo "❌ Error: Cargo not found at $CARGO_BIN"
    exit 1
fi

# Use RUSTC environment variable to force direct rustc
export RUSTC="$RUSTC_BIN"
export CARGO="$CARGO_BIN"

# Build the Rust GUI
$CARGO_BIN build --release
if [ $? -ne 0 ]; then
    echo "❌ Rust GUI build failed!"
    exit 1
fi
echo "✓ Rust GUI built successfully"

# Step 3: Create AppImage
echo ""
echo "Step 3: Creating AppImage..."
./create_iced_appimage.sh
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================"
    echo "✓ Build complete!"
    echo "============================================"
    ls -lh NaK-Linux-Modding-Helper-Iced.AppImage
else
    echo "❌ AppImage creation failed!"
    exit 1
fi
