#!/bin/bash

# Build NaK AppImage using Docker for maximum compatibility
set -e

echo "============================================"
echo "Building NaK with Docker (glibc 2.31)"
echo "============================================"

cd /home/luke/Documents/NaK-Python

# Build the Docker image if it doesn't exist
if ! docker images | grep -q nak-builder; then
    echo ""
    echo "Building Docker image (this may take a few minutes)..."
    docker build -t nak-builder .
fi

echo ""
echo "Building NaK inside Docker container..."
echo ""

# Run the build inside Docker
docker run --rm \
    -v "$(pwd):/workspace" \
    -w /workspace \
    -e GOAMD64=v1 \
    nak-builder \
    /bin/bash -c "
        set -e
        echo '→ Building Python backend...'
        pyinstaller nak_backend.spec --clean
        
        echo ''
        echo '→ Building Wails GUI...'
        cd nak-gui
        wails build
        cd ..
        
        echo ''
        echo '→ Creating AppImage...'
        rm -f NaK-Linux-Modding-Helper-Wails.AppImage
        ./create_wails_appimage.sh
    "

echo ""
echo "============================================"
echo "✓ Docker build complete!"
echo "============================================"
ls -lh NaK-Linux-Modding-Helper-Wails.AppImage

echo ""
echo "This AppImage should work on systems with glibc ≥ 2.31"
echo "(Ubuntu 20.04+, Debian 11+, Fedora 32+, etc.)"

