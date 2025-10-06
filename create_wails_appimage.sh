#!/bin/bash

# Create AppImage for NaK Wails GUI
set -e

# Set CPU compatibility flag for broader support (v1 = baseline x86-64)
export GOAMD64=v1

echo "============================================"
echo "Creating NaK Wails AppImage"
echo "============================================"

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

# Download linuxdeploy and the gtk plugin
echo "Downloading linuxdeploy..."
wget https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
wget https://github.com/linuxdeploy/linuxdeploy-plugin-gtk/releases/download/1.0.0/linuxdeploy-plugin-gtk-x86_64.AppImage
chmod +x linuxdeploy-x86_64.AppImage
chmod +x linuxdeploy-plugin-gtk-x86_64.AppImage

# Run linuxdeploy
echo "Running linuxdeploy..."
./linuxdeploy-x86_64.AppImage --appdir "$APPDIR" --plugin gtk --output appimage

# Rename the AppImage
mv NaK_Linux_Modding_Helper-x86_64.AppImage NaK-Linux-Modding-Helper-Wails.AppImage

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