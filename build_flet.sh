#!/bin/bash
set -e

echo "============================================"
echo "Building NaK Flet GUI with Ubuntu 22.04"
echo "Compatible with glibc 2.35+ (most modern Linux)"
echo "============================================"

# Build Docker image
echo "Building Docker image..."
docker build -f Dockerfile.flet -t nak-flet-builder .

echo ""
echo "Running build in Docker container..."
docker run --rm \
    -v "$(pwd):/build" \
    -w /build \
    nak-flet-builder \
    bash -c "
        echo '=== Building Flet AppImage ==='

        # Clean up old build artifacts
        echo 'Cleaning up old build artifacts...'
        rm -rf NaK-Flet.AppDir dist_flet build

        # Create PyInstaller spec if it doesn't exist
        if [ ! -f nak_flet.spec ]; then
            echo 'Creating PyInstaller spec...'
            cat > nak_flet.spec << 'SPEC'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['nak-flet/main.py'],
    pathex=[],
    binaries=[
        ('winetricks', '.'),
    ],
    datas=[
        ('src', 'src'),
    ],
    hiddenimports=[
        'flet',
        'flet_desktop',
        'flet.auth',
        'flet.auth.providers',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'vdf',
        'psutil',
        'py7zr',
        'pillow',
        'PIL',
        'PIL.Image',
        'logging',
        'logging.handlers',
        'logging.config',
        'src.core.core',
        'src.core.mo2_installer',
        'src.core.dependency_installer',
        'src.utils.steam_utils',
        'src.utils.game_utils',
        'src.utils.game_finder',
        'src.utils.steam_shortcut_manager',
        'src.utils.comprehensive_game_manager',
        'src.utils.smart_prefix_manager',
        'src.utils.prefix_locator',
        'src.utils.heroic_utils',
        'src.utils.settings_manager',
        'src.utils.logger',
        'src.utils.proton_tool_manager',
        'src.utils.dependency_cache_manager',
        'src.utils.utils',
        'src.utils.command_cache',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'libstdc++.so.6',
        'libgcc_s.so.1',
        'libssl.so.3',
        'libcrypto.so.3',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Exclude problematic system libraries that conflict with newer systems
a.binaries = [x for x in a.binaries if not any(lib in x[0] for lib in [
    'libstdc++.so.6',
    'libgcc_s.so.1',
    'libssl.so.3',
    'libcrypto.so.3',
])]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='nak-modding-helper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
SPEC
        fi

        # Build with PyInstaller
        echo 'Building with PyInstaller...'
        pyinstaller nak_flet.spec --clean --distpath dist_flet

        if [ -f dist_flet/nak-modding-helper ]; then
            echo '✓ Flet app built successfully'
            ls -lh dist_flet/nak-modding-helper
        else
            echo '✗ Build failed'
            exit 1
        fi

        # Create AppDir
        echo 'Creating AppDir...'
        mkdir -p NaK-Flet.AppDir/usr/bin
        mkdir -p NaK-Flet.AppDir/usr/lib
        mkdir -p NaK-Flet.AppDir/usr/share/applications
        mkdir -p NaK-Flet.AppDir/usr/share/icons/hicolor/256x256/apps

        # Copy binary
        cp dist_flet/nak-modding-helper NaK-Flet.AppDir/usr/bin/

        # Bundle zenity for file dialogs
        echo 'Bundling zenity for file dialogs...'
        if [ -f /usr/bin/zenity ]; then
            cp /usr/bin/zenity NaK-Flet.AppDir/usr/bin/
            echo '✓ Zenity bundled'
        else
            echo '⚠ Warning: zenity not found, file dialogs may not work'
        fi

        # Bundle winetricks
        echo 'Bundling winetricks...'
        if [ -f winetricks ]; then
            cp winetricks NaK-Flet.AppDir/usr/bin/
            chmod +x NaK-Flet.AppDir/usr/bin/winetricks
            echo '✓ Winetricks bundled'
        else
            echo '⚠ Warning: winetricks not found'
        fi

        # Bundle cabextract for extracting .cab files (needed for MO2 dependencies)
        echo 'Bundling cabextract and its dependencies...'
        if [ -f /usr/bin/cabextract ]; then
            cp /usr/bin/cabextract NaK-Flet.AppDir/usr/bin/
            echo '✓ Cabextract bundled'

            # Bundle libmspack (required by cabextract)
            if [ -f /lib/x86_64-linux-gnu/libmspack.so.0 ]; then
                cp -L /lib/x86_64-linux-gnu/libmspack.so.0 NaK-Flet.AppDir/usr/lib/
                echo '✓ libmspack.so.0 bundled'
            elif [ -f /usr/lib/x86_64-linux-gnu/libmspack.so.0 ]; then
                cp -L /usr/lib/x86_64-linux-gnu/libmspack.so.0 NaK-Flet.AppDir/usr/lib/
                echo '✓ libmspack.so.0 bundled'
            else
                echo '⚠ Warning: libmspack.so.0 not found'
            fi
        else
            echo '⚠ Warning: cabextract not found'
        fi

        # Bundle zstd/unzstd for extracting .tar.zst files (needed for vkd3d-proton)
        echo 'Bundling zstd/unzstd and its dependencies...'
        if [ -f /usr/bin/unzstd ]; then
            cp /usr/bin/unzstd NaK-Flet.AppDir/usr/bin/
            echo '✓ unzstd bundled'

            # Bundle liblzma (required by unzstd)
            for libpath in /lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu; do
                if [ -f "$libpath/liblzma.so.5" ]; then
                    cp -L "$libpath/liblzma.so.5" NaK-Flet.AppDir/usr/lib/
                    echo '✓ liblzma.so.5 bundled'
                    break
                fi
            done

            # Bundle liblz4 (required by unzstd)
            for libpath in /lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu; do
                if [ -f "$libpath/liblz4.so.1" ]; then
                    cp -L "$libpath/liblz4.so.1" NaK-Flet.AppDir/usr/lib/
                    echo '✓ liblz4.so.1 bundled'
                    break
                fi
            done
        else
            echo '⚠ Warning: unzstd not found'
        fi

        # Bundle GTK pixbuf loaders and librsvg for proper icon support
        echo 'Bundling GTK pixbuf loaders and librsvg...'

        # Create directory for pixbuf loaders
        mkdir -p NaK-Flet.AppDir/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders

        # Copy all pixbuf loaders
        if [ -d /usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders ]; then
            cp -r /usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/* \
                NaK-Flet.AppDir/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/ 2>/dev/null || true
            echo '✓ Pixbuf loaders bundled'
        fi

        # Bundle librsvg for SVG support
        for lib in librsvg-2.so.2 librsvg-2.so; do
            if [ -f /usr/lib/x86_64-linux-gnu/\$lib ]; then
                cp -L /usr/lib/x86_64-linux-gnu/\$lib NaK-Flet.AppDir/usr/lib/
                echo \"✓ \$lib bundled\"
            fi
        done

        # Bundle libxml2 (required by librsvg)
        if [ -f /usr/lib/x86_64-linux-gnu/libxml2.so.2 ]; then
            cp -L /usr/lib/x86_64-linux-gnu/libxml2.so.2 NaK-Flet.AppDir/usr/lib/
            echo '✓ libxml2.so.2 bundled'
        fi

        # Bundle libcroco (required by librsvg)
        if [ -f /usr/lib/x86_64-linux-gnu/libcroco-0.6.so.3 ]; then
            cp -L /usr/lib/x86_64-linux-gnu/libcroco-0.6.so.3 NaK-Flet.AppDir/usr/lib/
            echo '✓ libcroco-0.6.so.3 bundled'
        fi

        # Generate pixbuf loader cache file
        echo 'Generating pixbuf loader cache...'
        export GDK_PIXBUF_MODULE_FILE=NaK-Flet.AppDir/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache
        export GDK_PIXBUF_MODULEDIR=NaK-Flet.AppDir/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders
        gdk-pixbuf-query-loaders > \$GDK_PIXBUF_MODULE_FILE 2>/dev/null || true

        # Update loader paths in cache file to use relative paths
        sed -i \"s|/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/|\\$APPDIR/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/|g\" \$GDK_PIXBUF_MODULE_FILE 2>/dev/null || true

        # Bundle GStreamer libraries for Flet viewer (audioplayers plugin)
        echo 'Bundling GStreamer libraries...'

        # Core GStreamer libraries needed by audioplayers_linux_plugin
        for gst_lib in \
            libgstreamer-1.0.so.0 \
            libgstapp-1.0.so.0 \
            libgstaudio-1.0.so.0 \
            libgstbase-1.0.so.0 \
            libgstpbutils-1.0.so.0 \
            libgsttag-1.0.so.0 \
            libgstvideo-1.0.so.0 \
            libgstcodecparsers-1.0.so.0
        do
            if [ -f /usr/lib/x86_64-linux-gnu/\$gst_lib ]; then
                cp -L /usr/lib/x86_64-linux-gnu/\$gst_lib NaK-Flet.AppDir/usr/lib/
                echo \"✓ \$gst_lib bundled\"
            fi
        done

        # Bundle libmpv and its dependencies for Flet viewer
        echo 'Bundling libmpv and dependencies...'

        # Core library to bundle
        cp -L /usr/lib/x86_64-linux-gnu/libmpv.so.1 NaK-Flet.AppDir/usr/lib/ || true

        # Get all dependencies of libmpv, excluding core system libraries
        ldd /usr/lib/x86_64-linux-gnu/libmpv.so.1 | grep '=>' | awk '{print \$3}' | while read lib; do
            if [ -f \"\$lib\" ]; then
                # Exclude core system libraries that should use system versions
                case \"\$lib\" in
                    */libc.so.6|*/libm.so.6|*/libdl.so.2|*/libpthread.so.0|*/librt.so.1)
                        # Skip core C libraries
                        ;;
                    */libstdc++.so.6|*/libgcc_s.so.1)
                        # Skip C++ runtime (use system version)
                        ;;
                    */libssl.so.3|*/libcrypto.so.3)
                        # Skip SSL/crypto (use system version)
                        ;;
                    */libz.so.1|*/libbz2.so.1)
                        # Skip common compression libs (usually present)
                        ;;
                    */libGL.so.1|*/libEGL.so.1|*/libGLX.so.0|*/libGLdispatch.so.0)
                        # Skip OpenGL libraries (use system version)
                        ;;
                    */libX11.so.6|*/libXext.so.6|*/libXrandr.so.2|*/libXv.so.1|*/libXinerama.so.1|*/libXss.so.1|*/libxcb.so.1|*/libXau.so.6|*/libXdmcp.so.6|*/libX11-xcb.so.1)
                        # Skip X11 libraries (use system version)
                        ;;
                    */libwayland*.so*)
                        # Skip Wayland libraries (use system version)
                        ;;
                    */libdrm.so.2|*/libgbm.so.1)
                        # Skip DRM libraries (use system version)
                        ;;
                    */libpulse*.so*|*/libasound.so.2|*/libjack.so.0)
                        # Skip audio system libraries (use system version)
                        ;;
                    */libglib*.so*|*/libgobject*.so*|*/libgio*.so*|*/libgmodule*.so*)
                        # Skip glib libraries (use system version)
                        ;;
                    */libmount.so.1|*/libblkid.so.1|*/libuuid.so.1)
                        # Skip mount/block device libs (use system version)
                        ;;
                    *)
                        # Bundle everything else
                        cp -L \"\$lib\" NaK-Flet.AppDir/usr/lib/ 2>/dev/null || true
                        ;;
                esac
            fi
        done

        # Create desktop file
        cat > NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=NaK Linux Modding Helper
Exec=nak-modding-helper
Icon=nak-modding-helper
Categories=Game;Utility;
Terminal=false
EOF

        # Create icon
        cat > NaK-Flet.AppDir/nak-modding-helper.svg << 'EOF'
<svg width=\"256\" height=\"256\" xmlns=\"http://www.w3.org/2000/svg\">
  <rect width=\"256\" height=\"256\" fill=\"#2c5282\"/>
  <text x=\"128\" y=\"140\" font-size=\"80\" fill=\"#7dd3fc\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-weight=\"bold\">NaK</text>
</svg>
EOF

        cp NaK-Flet.AppDir/nak-modding-helper.svg NaK-Flet.AppDir/usr/share/icons/hicolor/256x256/apps/

        # Copy desktop file to root
        cp NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop NaK-Flet.AppDir/

        # Create AppRun
        cat > NaK-Flet.AppDir/AppRun << 'EOF'
#!/bin/bash
export APPDIR=\"\$(dirname \"\$(readlink -f \"\$0\")\")\"
export LD_LIBRARY_PATH=\"\$APPDIR/usr/lib:\$APPDIR/usr/lib/x86_64-linux-gnu:\$LD_LIBRARY_PATH\"
export PATH=\"\$APPDIR/usr/bin:\$PATH\"

# Set up GTK pixbuf loaders
export GDK_PIXBUF_MODULE_FILE=\"\$APPDIR/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache\"
export GDK_PIXBUF_MODULEDIR=\"\$APPDIR/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders\"

# Preserve display server environment for proper window decorations
export DISPLAY=\"\${DISPLAY:-:0}\"

# Debug mode for GTK issues (uncomment if needed)
# export GTK_DEBUG=all
# export GDK_DEBUG=all

exec \"\$APPDIR/usr/bin/nak-modding-helper\" \"\$@\"
EOF

        chmod +x NaK-Flet.AppDir/AppRun

        # Download appimagetool if needed
        if [ ! -f appimagetool-x86_64.AppImage ]; then
            echo 'Downloading appimagetool...'
            wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
            chmod +x appimagetool-x86_64.AppImage
        fi

        # Extract appimagetool (FUSE not available in Docker)
        if [ ! -d squashfs-root ]; then
            echo 'Extracting appimagetool...'
            ./appimagetool-x86_64.AppImage --appimage-extract
        fi

        # Create AppImage using extracted appimagetool
        echo 'Creating AppImage...'
        ARCH=x86_64 ./squashfs-root/AppRun NaK-Flet.AppDir NaK-Linux-Modding-Helper-Flet.AppImage

        if [ -f NaK-Linux-Modding-Helper-Flet.AppImage ]; then
            chmod +x NaK-Linux-Modding-Helper-Flet.AppImage
            echo ''
            echo '============================================'
            echo '✓ Flet AppImage created successfully!'
            echo '============================================'
            ls -lh NaK-Linux-Modding-Helper-Flet.AppImage
            echo ''
            echo 'This is a self-contained AppImage with:'
            echo '  • Flutter engine bundled'
            echo '  • Modern Material Design UI'
            echo '  • Compatible with glibc 2.35+ (Ubuntu 22.04+, Debian 12+)'
            echo ''
            echo 'Run with: ./NaK-Linux-Modding-Helper-Flet.AppImage'
        else
            echo '✗ Failed to create AppImage'
            exit 1
        fi
    "

echo ""
if [ -f "NaK-Linux-Modding-Helper-Flet.AppImage" ]; then
    echo "✓ Build complete!"
    ls -lh NaK-Linux-Modding-Helper-Flet.AppImage
else
    echo "Build failed - check output above"
fi