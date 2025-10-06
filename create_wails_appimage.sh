#!/bin/bash

# Create AppImage for NaK Wails GUI
set -e

# Set CPU compatibility flag for broader support (v1 = baseline x86-64)
export GOAMD64=v1

echo "============================================"
echo "Creating NaK Wails AppImage"
echo "============================================"

# Build Wails GUI with webkit support
echo "Building Wails GUI with webkit2gtk support..."
cd nak-gui
wails build -tags webkit2_41
cd ..

# Create AppDir structure
APPDIR="NaK-Wails.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copy the Wails GUI binary
echo "Copying Wails GUI..."
cp nak-gui/build/bin/nak-gui "$APPDIR/usr/bin/"

# Create a simple Python backend wrapper
echo "Creating Python backend wrapper..."
cat > "$APPDIR/usr/bin/nak-backend" << 'EOF'
#!/usr/bin/env python3
import sys
import os

# Add the src directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
appdir = os.path.dirname(os.path.dirname(script_dir))
src_path = os.path.join(appdir, "src")

if os.path.exists(src_path):
    sys.path.insert(0, src_path)

# Import and run the main application
try:
    from main import main
    sys.exit(main())
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
EOF

chmod +x "$APPDIR/usr/bin/nak-backend"

# Copy the Python source code to the AppDir
echo "Copying Python source code..."
mkdir -p "$APPDIR/src"
cp -r src/ "$APPDIR/"

# Create desktop file
cat > "$APPDIR/usr/share/applications/nak-gui.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=NaK Linux Modding Helper
Exec=nak-gui
Icon=nak-gui
Categories=Game;Utility;
Terminal=false
EOF

# Create AppRun script
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
export APPDIR="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$APPDIR/usr/lib:$LD_LIBRARY_PATH"
export PATH="$APPDIR/usr/bin:$PATH"

# Set webkit helper process path (we force webkit2gtk-4.1 with build tags)
export WEBKIT_EXEC_PATH="$APPDIR/usr/lib/webkit2gtk-4.1"

exec "$APPDIR/usr/bin/nak-gui" "$@"
EOF

chmod +x "$APPDIR/AppRun"

# Create a simple icon (using a placeholder)
cat > "$APPDIR/nak-gui.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=NaK Linux Modding Helper
Exec=nak-gui
Icon=nak-gui
Categories=Game;Utility;
Terminal=false
EOF

# Create a simple SVG icon
cat > "$APPDIR/nak-gui.svg" << 'EOF'
<svg width="256" height="256" xmlns="http://www.w3.org/2000/svg">
  <rect width="256" height="256" fill="#2c5282"/>
  <text x="128" y="140" font-size="80" fill="#7dd3fc" text-anchor="middle" font-family="Arial, sans-serif" font-weight="bold">NaK</text>
</svg>
EOF

cp "$APPDIR/nak-gui.svg" "$APPDIR/usr/share/icons/hicolor/256x256/apps/"

# Download winetricks
echo "Downloading winetricks..."
wget https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks -O "$APPDIR/usr/bin/winetricks"
chmod +x "$APPDIR/usr/bin/winetricks"

# Download linuxdeploy
echo "Downloading linuxdeploy..."
if [ ! -f "linuxdeploy-x86_64.AppImage" ]; then
    wget https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
fi
chmod +x linuxdeploy-x86_64.AppImage

# Deploy webkit2gtk libraries and helper processes explicitly
echo "Deploying webkit2gtk libraries and helper processes..."

# Find webkit2gtk library
WEBKIT_LIB=$(ldconfig -p | grep 'libwebkit2gtk-4\.' | awk '{print $NF}' | head -n 1)
if [ -z "$WEBKIT_LIB" ]; then
    # Try webkit2gtk-4.1 as fallback
    WEBKIT_LIB=$(ldconfig -p | grep 'libwebkit2gtk-4\.1' | awk '{print $NF}' | head -n 1)
fi

if [ -n "$WEBKIT_LIB" ]; then
    echo "Found webkit library: $WEBKIT_LIB"
    mkdir -p "$APPDIR/usr/lib"
    # Copy webkit and its dependencies
    cp -L "$WEBKIT_LIB" "$APPDIR/usr/lib/" || echo "Warning: Could not copy webkit library"
fi

# Find and copy webkit helper processes (critical for webkit to function)
WEBKIT_HELPERS_DIR=""
for dir in /usr/lib/x86_64-linux-gnu/webkit2gtk-4.1 /usr/lib/x86_64-linux-gnu/webkit2gtk-4.0 /usr/libexec/webkit2gtk-4.1 /usr/libexec/webkit2gtk-4.0; do
    if [ -d "$dir" ]; then
        WEBKIT_HELPERS_DIR="$dir"
        echo "Found webkit helpers in: $WEBKIT_HELPERS_DIR"
        break
    fi
done

if [ -n "$WEBKIT_HELPERS_DIR" ]; then
    # Determine the target directory structure
    WEBKIT_TARGET="$APPDIR/usr/lib/$(basename $WEBKIT_HELPERS_DIR)"
    mkdir -p "$WEBKIT_TARGET"
    
    # Copy all webkit helper processes
    echo "Copying webkit helper processes..."
    cp -r "$WEBKIT_HELPERS_DIR"/* "$WEBKIT_TARGET/" || echo "Warning: Could not copy webkit helpers"
    
    # Make sure they're executable
    chmod +x "$WEBKIT_TARGET"/* 2>/dev/null || true
else
    echo "Warning: Could not find webkit helper processes directory"
fi

# Run linuxdeploy to bundle all dependencies
echo "Running linuxdeploy..."
DISABLE_COPYRIGHT_FILES_DEPLOYMENT=1 ./linuxdeploy-x86_64.AppImage --appdir "$APPDIR" \
    --executable "$APPDIR/usr/bin/nak-gui" \
    --deploy-deps-only="$APPDIR/usr/lib" \
    --output appimage \
    || true  # Continue even if strip fails

# If AppImage wasn't created, try with appimagetool directly
if [ ! -f "NaK Linux Modding Helper-x86_64.AppImage" ]; then
    echo "Using appimagetool as fallback..."
    ARCH=x86_64 ./appimagetool-x86_64.AppImage "$APPDIR" NaK-Linux-Modding-Helper-Wails.AppImage
fi

# Rename the AppImage if it exists with the default name
if [ -f "NaK Linux Modding Helper-x86_64.AppImage" ]; then
    mv "NaK Linux Modding Helper-x86_64.AppImage" NaK-Linux-Modding-Helper-Wails.AppImage
fi

if [ -f "NaK-Linux-Modding-Helper-Wails.AppImage" ]; then
    chmod +x NaK-Linux-Modding-Helper-Wails.AppImage
    echo ""
    echo "============================================"
    echo "✓ AppImage created successfully!"
    echo "============================================"
    ls -lh NaK-Linux-Modding-Helper-Wails.AppImage
    echo ""
    echo "Run with: ./NaK-Linux-Modding-Helper-Wails.AppImage"
else
    echo "❌ Failed to create AppImage"
    exit 1
fi