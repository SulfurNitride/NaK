#!/bin/bash

set -e

echo "Creating Tauri + System Python AppImage..."

# Create AppDir structure
rm -rf AppDir
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/lib
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons

# Copy the Tauri executable (we need to build it first)
if [ ! -f "src-tauri/target/release/app" ]; then
    echo "Tauri app not found. Please build it first with: cargo tauri build"
    exit 1
fi

cp src-tauri/target/release/app AppDir/usr/bin/nak-app
chmod +x AppDir/usr/bin/nak-app

# Copy the Python backend
if [ ! -f "dist/nak_backend" ]; then
    echo "Python backend not found. Please build it first with PyInstaller"
    exit 1
fi

cp dist/nak_backend AppDir/usr/bin/nak-backend
chmod +x AppDir/usr/bin/nak-backend

# Create desktop file
cat > AppDir/nak-linux-modding-helper.desktop << EOF
[Desktop Entry]
Name=NaK Linux Modding Helper
Comment=Linux Modding Helper for NaK
Exec=nak-app
Icon=nak-linux-modding-helper
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=true
EOF

# Create AppRun script
cat > AppDir/AppRun << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:$PATH"

# Run the Tauri application
exec "${HERE}/usr/bin/nak-app" "$@"
EOF

chmod +x AppDir/AppRun

# Create a simple icon (text-based)
echo "Creating simple icon..."
cat > AppDir/nak-linux-modding-helper.svg << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <rect width="64" height="64" fill="#000000"/>
  <text x="32" y="40" font-family="monospace" font-size="24" fill="#00ff00" text-anchor="middle">NaK</text>
</svg>
EOF

# Create AppImage
echo "Creating AppImage..."
if command -v appimagetool &> /dev/null; then
    ARCH=x86_64 appimagetool AppDir NaK-Linux-Modding-Helper-Tauri.AppImage
    echo "AppImage created: NaK-Linux-Modding-Helper-Tauri.AppImage"
    ls -lh NaK-Linux-Modding-Helper-Tauri.AppImage
else
    echo "appimagetool not found. Please install it first:"
    echo "wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    echo "chmod +x appimagetool-x86_64.AppImage"
    echo "sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool"
fi