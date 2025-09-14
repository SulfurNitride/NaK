#!/usr/bin/env python3
"""
AppImage build script for NaK
Builds a portable AppImage package
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return the result"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout

def build_appimage():
    """Build the AppImage package"""
    print("Building NaK AppImage...")
    
    # Check if appimagetool is available
    appimagetool_path = None
    if shutil.which("appimagetool"):
        appimagetool_path = "appimagetool"
    elif os.path.exists("./appimagetool-x86_64.AppImage"):
        appimagetool_path = "./appimagetool-x86_64.AppImage"
    else:
        print("Error: appimagetool not found. Please install it first:")
        print("  wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage")
        print("  chmod +x appimagetool-x86_64.AppImage")
        print("  sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool")
        sys.exit(1)
    
    # Create build directory
    build_dir = Path("build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    
    # Create AppDir structure
    appdir = build_dir / "AppDir"
    appdir.mkdir()
    
    # Copy AppDir files from APPIMAGEBUILDER
    apprun_src = Path("APPIMAGEBUILDER/AppDir/AppRun")
    desktop_src = Path("APPIMAGEBUILDER/AppDir/nak.desktop")
    
    if not apprun_src.exists():
        print(f"Error: {apprun_src} not found!")
        sys.exit(1)
    if not desktop_src.exists():
        print(f"Error: {desktop_src} not found!")
        sys.exit(1)
        
    shutil.copy(apprun_src, appdir)
    shutil.copy(desktop_src, appdir)
    
    # Make AppRun executable
    os.chmod(appdir / "AppRun", 0o755)
    
    # Install Python dependencies using virtual environment approach
    print("Installing Python dependencies...")
    
    # Create a temporary virtual environment
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        venv_path = Path(temp_dir) / "venv"
        run_command(["python3", "-m", "venv", str(venv_path)])
        
        # Install dependencies in the venv
        pip_path = venv_path / "bin" / "pip"
        run_command([
            str(pip_path), "install", "-r", "requirements.txt"
        ])
        
        # Copy the site-packages to AppImage
        import sys
        python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site_packages_src = venv_path / "lib" / python_version / "site-packages"
        site_packages_dst = appdir / "usr" / "lib" / "python3" / "site-packages"
        
        print(f"Copying from {site_packages_src} to {site_packages_dst}")
        shutil.copytree(site_packages_src, site_packages_dst, dirs_exist_ok=True)
    
    # Verify PySide6 installation
    pyside6_path = appdir / "usr" / "lib" / "python3" / "site-packages" / "PySide6"
    if pyside6_path.exists():
        print(f"✓ PySide6 installed successfully at {pyside6_path}")
        # Check for QtWidgets module
        qtwidgets_path = pyside6_path / "QtWidgets.abi3.so"
        if qtwidgets_path.exists():
            print(f"✓ QtWidgets module found at {qtwidgets_path}")
        else:
            print(f"✗ QtWidgets module missing")
    else:
        print(f"✗ PySide6 installation failed - {pyside6_path} not found")
        sys.exit(1)
    
    # Copy source code
    src_dir = appdir / "usr" / "lib" / "python3" / "site-packages" / "nak"
    src_path = Path("src")
    if not src_path.exists():
        print(f"Error: {src_path} not found!")
        sys.exit(1)
    shutil.copytree(src_path, src_dir)
    
    # Copy main script (AppImage version)
    usr_bin = appdir / "usr" / "bin"
    usr_bin.mkdir(parents=True)
    main_script_src = Path("main_appimage.py")
    if not main_script_src.exists():
        print(f"Error: {main_script_src} not found!")
        sys.exit(1)
    shutil.copy(main_script_src, usr_bin / "main_appimage.py")
    
    # Make main script executable
    os.chmod(usr_bin / "main_appimage.py", 0o755)
    
    # Create icon directory
    icon_dir = appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icon_dir.mkdir(parents=True)
    
    # Create a simple icon (1x1 pixel PNG)
    import base64
    icon_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    with open(icon_dir / "nak.png", "wb") as f:
        f.write(icon_data)
    
    # Copy icon to AppDir root for desktop file
    with open(appdir / "nak.png", "wb") as f:
        f.write(icon_data)
    
    # Build AppImage
    print("Building AppImage...")
    output_name = "NaK-Linux-Modding-Helper-x86_64.AppImage"
    run_command([
        appimagetool_path, str(appdir), output_name
    ])
    
    # Verify the AppImage was created
    if not Path(output_name).exists():
        print(f"Error: AppImage {output_name} was not created!")
        sys.exit(1)
    
    print("AppImage built successfully!")
    print("File: NaK-Linux-Modding-Helper-x86_64.AppImage")

if __name__ == "__main__":
    build_appimage()
