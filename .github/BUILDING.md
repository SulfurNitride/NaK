# Building NaK Linux Modding Helper

This document explains how to build the NaK AppImage locally and via GitHub Actions.

## Building via GitHub Actions (Recommended for Distribution)

The easiest way to get a compatible AppImage is to use GitHub Actions:

1. **Push to GitHub**: The build automatically runs on every push to `main`/`master`
2. **Download Artifact**: Go to Actions tab → Select your workflow run → Download the AppImage artifact
3. **For Releases**: Create a GitHub release, and the AppImage will be automatically attached

### Advantages:
- Builds on Ubuntu 20.04 (glibc 2.31) for maximum compatibility
- Works on Ubuntu 20.04+, Debian 11+, Fedora 32+, etc.
- No local build dependencies needed
- Consistent, reproducible builds

## Building Locally

### Prerequisites

**System Dependencies:**
```bash
# Ubuntu/Debian
sudo apt-get install \
    python3 python3-pip \
    golang-go \
    nodejs npm \
    pkg-config \
    libgtk-3-dev \
    libwebkit2gtk-4.0-dev \
    build-essential \
    wget

# Arch/CachyOS
sudo pacman -S \
    python python-pip \
    go \
    nodejs npm \
    pkg-config \
    gtk3 \
    webkit2gtk \
    base-devel \
    wget
```

**Python Dependencies:**
```bash
pip install pyinstaller requests pillow psutil py7zr vdf
```

**Wails:**
```bash
go install github.com/wailsapp/wails/v2/cmd/wails@latest
export PATH=$PATH:$HOME/go/bin
```

### Build Script

Simply run:
```bash
./build_all.sh
```

Or manually:
```bash
# Build Python backend
pyinstaller nak_backend.spec --clean

# Build Wails GUI
cd nak-gui
export GOAMD64=v1  # For CPU compatibility
wails build
cd ..

# Create AppImage
./create_wails_appimage.sh
```

### Compatibility Notes

**Build System Matters!**
- Building on **newer systems** (e.g., your host with glibc 2.42) → Only works on systems with glibc ≥ 2.42
- Building on **older systems** (e.g., Ubuntu 20.04 with glibc 2.31) → Works on systems with glibc ≥ 2.31

**Recommended Build Environments:**
1. **GitHub Actions** (Ubuntu 20.04) - Best compatibility
2. **Virtual Machine** (Ubuntu 20.04 or Debian 11) - Good compatibility
3. **Your Host System** - Only for personal use if you have a recent distro

## GitHub Actions Details

The workflow (`.github/workflows/build-appimage.yml`) automatically:
- ✅ Builds on Ubuntu 20.04 for wide compatibility
- ✅ Sets `GOAMD64=v1` for baseline x86-64 CPU support
- ✅ Uploads AppImage as artifact (available for 90 days)
- ✅ Attaches AppImage to GitHub releases automatically
- ✅ Generates build info with compatibility details

### Manual Trigger

You can manually trigger a build:
1. Go to GitHub → Actions tab
2. Select "Build AppImage" workflow
3. Click "Run workflow" → Choose branch → "Run workflow"

### Download Built AppImage

**From Actions:**
1. Go to Actions tab
2. Click on the latest successful run
3. Scroll down to "Artifacts"
4. Download `NaK-AppImage-{version}`

**From Releases:**
1. Go to Releases tab
2. Download `NaK-Linux-Modding-Helper-{version}-x86_64.AppImage`

## Troubleshooting

### "CPU ISA level is lower than required" error

This means your system's CPU or VM doesn't support the instruction set used during compilation.

**Solution:** Use the AppImage built via GitHub Actions, which uses baseline x86-64 instructions.

### "GLIBC_X.XX not found" error

This means your system's glibc is older than what was used during build.

**Solution:** Use the AppImage built via GitHub Actions on Ubuntu 20.04 (glibc 2.31).

### Build fails locally

Make sure all dependencies are installed (see Prerequisites above).

For the AppImage creation, you need:
```bash
wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage
```

## For Developers

### Local Development

For testing changes locally (not for distribution):
```bash
# Quick rebuild after changes
./build_all.sh

# Or rebuild just the Python backend
pyinstaller nak_backend.spec --clean

# Or rebuild just the Wails GUI
cd nak-gui && wails build && cd ..
```

### Before Releasing

1. Test the AppImage on multiple distros (Ubuntu, Arch, Debian, etc.)
2. Create a GitHub release (tag it with version like `v1.0.0`)
3. The AppImage will be automatically built and attached to the release
4. Update release notes with changes and compatibility info

