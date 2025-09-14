# NaK - Linux Modding Helper

A comprehensive tool for setting up and managing mod managers on Linux gaming systems.

## Features

- **Mod Organizer 2 Setup**: Download, install, and configure MO2 with automatic Steam integration
- **Dependency Management**: Install required dependencies for games and mod managers  
- **NXM Handler**: Configure Nexus Mods download links to work with MO2
- **Steam Integration**: Add games and mod managers to Steam with proper Proton configuration
- **Cross-Library Support**: Automatic STEAM_COMPAT_MOUNTS for multi-drive setups
- **Firefox Integration**: Proper NXM handler registration for Firefox

## Installation

### AppImage (Recommended)

Download the latest AppImage from the releases page and make it executable:
```bash
chmod +x NaK-Linux-Modding-Helper-x86_64.AppImage
./NaK-Linux-Modding-Helper-x86_64.AppImage
```

### From Source

1. Clone the repository:
```bash
git clone https://github.com/sulfurnitride/nak.git
cd nak
```

2. Install dependencies:
```bash
make install-deps
```

3. Run the application:
```bash
make run
```

### Building AppImage

1. Install appimagetool:
```bash
make install-appimagetool
```

2. Build the AppImage:
```bash
make build
```

## Usage

### GUI Mode
Simply run the application and use the graphical interface:
```bash
python main.py
```

### CLI Mode
Check dependencies:
```bash
python main.py --check-deps
```

Show version:
```bash
python main.py --version
```

## Project Structure

```
nak/
├── src/                    # Source code
│   ├── core/              # Core functionality
│   ├── gui/               # GUI components
│   └── utils/             # Utility functions
├── APPIMAGEBUILDER/       # AppImage build files
├── main.py               # Main entry point
├── build_appimage.py     # AppImage build script
├── requirements.txt      # Python dependencies
├── setup.py             # Package setup
├── Makefile             # Build automation
└── README.md           # This file
```

## Requirements

- Python 3.8+
- PySide6
- requests
- Pillow
- psutil
- py7zr
- vdf

## License

MIT License - see LICENSE file for details.