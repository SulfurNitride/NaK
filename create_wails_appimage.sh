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

# Copy the Python backend executable
echo "Copying Python backend..."
ls -la dist
cp dist/nak_backend "$APPDIR/usr/bin/"

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
wget -q https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks -O "$APPDIR/usr/bin/winetricks"
chmod +x "$APPDIR/usr/bin/winetricks"

# Download appimagetool if not present
if [ ! -f "appimagetool-x86_64.AppImage" ]; then
    echo "Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool-x86_64.AppImage
fi

# Create AppImage
echo "Creating AppImage..."
ARCH=x86_64 ./appimagetool-x86_64.AppImage "$APPDIR" NaK-Linux-Modding-Helper-Wails.AppImage

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