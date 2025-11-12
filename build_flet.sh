#!/bin/bash
set -e

echo "============================================"
echo "Building NaK Flet GUI with Debian 12"
echo "Compatible with glibc 2.36+ (most modern Linux)"
echo "============================================"

# Build Docker image with host networking (fixes DNS issues)
echo "Building Docker image..."
docker build --network=host -f Dockerfile.flet -t nak-flet-builder .

# Create 7z wrapper script before Docker build
cat > /tmp/7z_wrapper.sh << 'EOF'
#!/bin/sh
# Universal 7z wrapper that works across different distros
# Tries multiple common 7z installation paths

# Try different paths for 7z binary
if [ -x /usr/lib/7zip/7z ]; then
    exec /usr/lib/7zip/7z "$@"
elif [ -x /usr/lib/p7zip/7z ]; then
    exec /usr/lib/p7zip/7z "$@"
elif [ -x /usr/bin/7zz ]; then
    exec /usr/bin/7zz "$@"
elif [ -x /usr/bin/7za ]; then
    exec /usr/bin/7za "$@"
elif [ -x /usr/bin/7zr ]; then
    exec /usr/bin/7zr "$@"
else
    echo "Error: Could not find 7z binary. Please install p7zip-full or 7zip package." >&2
    exit 127
fi
EOF
chmod +x /tmp/7z_wrapper.sh

echo ""
echo "Running build in Docker container..."
docker run --rm \
    -v "$(pwd):/build" \
    -v "/tmp/7z_wrapper.sh:/tmp/7z_wrapper.sh:ro" \
    -w /build \
    nak-flet-builder \
    bash -c "
        echo '=== Building Flet AppImage ==='

        # Clean up old build artifacts
        echo 'Cleaning up old build artifacts...'
        rm -rf NaK-Flet.AppDir dist_flet build

        # PyInstaller spec file (nak_flet.spec) is in the repository
        # No need to generate it - it will be mounted via the volume mount

        # Build with PyInstaller (no Flutter engine bundling for Light mode)
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

        # Note: Using YAD for file dialogs (lightweight GTK dialogs without webkit!)
        # YAD is bundled below (zenity fork without webkit2gtk dependency)

        # Winetricks is now downloaded from GitHub at runtime
        # No longer bundled to always use the latest version
        echo '✓ Winetricks will be downloaded at runtime (from GitHub)'

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

        # Bundle 7z for extracting .7z files (needed for various mod archives)
        echo 'Bundling 7z and its dependencies...'
        # Copy pre-created universal 7z wrapper
        cp /tmp/7z_wrapper.sh NaK-Flet.AppDir/usr/bin/7z
        chmod +x NaK-Flet.AppDir/usr/bin/7z
        echo '✓ Universal 7z wrapper bundled'

        # Bundle YAD for file picker dialogs (lightweight, no webkit!)
        echo 'Bundling YAD and its dependencies...'
        if [ -f /usr/bin/yad ]; then
            cp /usr/bin/yad NaK-Flet.AppDir/usr/bin/
            echo '✓ YAD bundled'
        else
            echo '⚠ Warning: yad not found'
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

        # Bundle libmpv and its dependencies (required by Flet engine)
        echo 'Bundling libmpv and dependencies...'
        if [ -f /usr/lib/x86_64-linux-gnu/libmpv.so.1 ]; then
            cp -L /usr/lib/x86_64-linux-gnu/libmpv.so.1 NaK-Flet.AppDir/usr/lib/

            # Bundle libmpv dependencies
            ldd /usr/lib/x86_64-linux-gnu/libmpv.so.1 | grep '=>' | awk '{print \$3}' | while read lib; do
                if [ -f \"\$lib\" ]; then
                    case \"\$lib\" in
                        # Skip core system libraries
                        */libc.so*|*/libm.so*|*/libdl.so*|*/libpthread.so*|*/librt.so*) ;;
                        */libstdc++.so*|*/libgcc_s.so*) ;;
                        # Skip graphics/windowing (use system)
                        */libGL.so*|*/libEGL.so*|*/libGLX.so*|*/libGLdispatch.so*) ;;
                        */libX11.so*|*/libxcb.so*|*/libXau.so*|*/libXdmcp.so*|*/libXext.so*|*/libXv.so*) ;;
                        */libdrm.so*|*/libgbm.so*) ;;
                        # Skip audio (use system)
                        */libasound.so*|*/libpulse*.so*|*/libjack.so*) ;;
                        # Skip wayland (use system)
                        */libwayland*.so*) ;;
                        # Skip SSL/crypto (use system)
                        */libssl.so*|*/libcrypto.so*) ;;
                        # Skip GLib (use system - already excluded in spec)
                        */libglib-2.0.so*|*/libgobject-2.0.so*|*/libgio-2.0.so*) ;;
                        # Bundle everything else (mujs, ffmpeg libs, etc.)
                        *)
                            cp -L \"\$lib\" NaK-Flet.AppDir/usr/lib/ 2>/dev/null || true
                            ;;
                    esac
                fi
            done

            echo \"✓ libmpv and dependencies bundled\"
        fi

        # Bundle ICU libraries (required by Flutter engine and Flet)
        echo 'Bundling ICU libraries...'
        for icu_lib in \
            libicuuc.so.72 \
            libicui18n.so.72 \
            libicudata.so.72
        do
            if [ -f /usr/lib/x86_64-linux-gnu/\$icu_lib ]; then
                cp -L /usr/lib/x86_64-linux-gnu/\$icu_lib NaK-Flet.AppDir/usr/lib/
                echo \"✓ \$icu_lib bundled\"
            fi
        done

        # Create desktop file
        echo '[Desktop Entry]' > NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop
        echo 'Type=Application' >> NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop
        echo 'Name=NaK Linux Modding Helper' >> NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop
        echo 'Exec=nak-modding-helper' >> NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop
        echo 'Icon=nak-modding-helper' >> NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop
        echo 'Categories=Game;Utility;' >> NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop
        echo 'Terminal=false' >> NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop

        # Copy doro.png icon
        if [ -f nak-flet/assets/icons/icon.png ]; then
            cp nak-flet/assets/icons/icon.png NaK-Flet.AppDir/nak-modding-helper.png
            cp nak-flet/assets/icons/icon.png NaK-Flet.AppDir/usr/share/icons/hicolor/256x256/apps/nak-modding-helper.png
            echo '✓ Doro icon bundled'
        else
            echo '⚠ Warning: icon.png not found, using fallback SVG'
            # Fallback SVG
            echo '<svg width=\"256\" height=\"256\" xmlns=\"http://www.w3.org/2000/svg\">' > NaK-Flet.AppDir/nak-modding-helper.svg
            echo '  <rect width=\"256\" height=\"256\" fill=\"#2c5282\"/>' >> NaK-Flet.AppDir/nak-modding-helper.svg
            echo '  <text x=\"128\" y=\"140\" font-size=\"80\" fill=\"#7dd3fc\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-weight=\"bold\">NaK</text>' >> NaK-Flet.AppDir/nak-modding-helper.svg
            echo '</svg>' >> NaK-Flet.AppDir/nak-modding-helper.svg
            cp NaK-Flet.AppDir/nak-modding-helper.svg NaK-Flet.AppDir/usr/share/icons/hicolor/256x256/apps/
        fi

        # Copy desktop file to root
        cp NaK-Flet.AppDir/usr/share/applications/nak-modding-helper.desktop NaK-Flet.AppDir/

        # Create AppRun
        echo '#!/bin/bash' > NaK-Flet.AppDir/AppRun
        echo 'export APPDIR=\"\$(dirname \"\$(readlink -f \"\$0\")\")\"' >> NaK-Flet.AppDir/AppRun
        echo '' >> NaK-Flet.AppDir/AppRun
        echo '# Explicitly set system lib paths FIRST, then AppImage libs' >> NaK-Flet.AppDir/AppRun
        echo '# This prevents conflicts with system binaries and libraries' >> NaK-Flet.AppDir/AppRun
        echo 'export LD_LIBRARY_PATH=\"/usr/lib:/usr/lib/x86_64-linux-gnu:\$APPDIR/usr/lib:\$APPDIR/usr/lib/x86_64-linux-gnu\"' >> NaK-Flet.AppDir/AppRun
        echo 'export PATH=\"\$APPDIR/usr/bin:\$PATH\"' >> NaK-Flet.AppDir/AppRun
        echo '' >> NaK-Flet.AppDir/AppRun
        echo '# Set up GTK pixbuf loaders' >> NaK-Flet.AppDir/AppRun
        echo 'export GDK_PIXBUF_MODULE_FILE=\"\$APPDIR/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache\"' >> NaK-Flet.AppDir/AppRun
        echo 'export GDK_PIXBUF_MODULEDIR=\"\$APPDIR/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders\"' >> NaK-Flet.AppDir/AppRun
        echo '' >> NaK-Flet.AppDir/AppRun
        echo '# Preserve display server environment for proper window decorations' >> NaK-Flet.AppDir/AppRun
        echo 'export DISPLAY=\"\${DISPLAY:-:0}\"' >> NaK-Flet.AppDir/AppRun
        echo '' >> NaK-Flet.AppDir/AppRun
        echo '# Debug mode for GTK issues (uncomment if needed)' >> NaK-Flet.AppDir/AppRun
        echo '# export GTK_DEBUG=all' >> NaK-Flet.AppDir/AppRun
        echo '# export GDK_DEBUG=all' >> NaK-Flet.AppDir/AppRun
        echo '' >> NaK-Flet.AppDir/AppRun
        echo 'exec \"\$APPDIR/usr/bin/nak-modding-helper\" \"\$@\"' >> NaK-Flet.AppDir/AppRun

        chmod +x NaK-Flet.AppDir/AppRun

        # Extract appimagetool (FUSE not available in Docker)
        if [ ! -d squashfs-root ]; then
            echo 'Extracting appimagetool...'
            /usr/local/bin/appimagetool --appimage-extract
        fi

        # Create AppImage using extracted appimagetool (skip ALL tests)
        echo 'Creating AppImage...'
        NO_APPSTREAM=1 ARCH=x86_64 ./squashfs-root/AppRun --no-appstream NaK-Flet.AppDir NaK-Linux-Modding-Helper-Flet.AppImage || true

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