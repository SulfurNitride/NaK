#!/usr/bin/env python3
"""
NaK - Linux Modding Helper
Main entry point for the Python application
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox
import logging

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gui.main_window import MainWindow
from core.core import Core
from utils.logger import setup_logging

def main():
    """Main application entry point"""
    try:
        # Setup logging
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("Starting NaK - Linux Modding Helper (Python)")
        
        # Create core application
        core = Core()
        
        # Check dependencies
        try:
            core.check_dependencies()
            logger.info("All dependencies are available")
        except Exception as e:
            logger.warning(f"Dependency check failed: {e}")
            # Continue anyway - user can still use some features
        
        # Create and run GUI
        root = tk.Tk()
        app = MainWindow(root, core)
        
        # Start the application
        logger.info("GUI started successfully")
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        # Show error dialog if GUI is available
        try:
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            messagebox.showerror("NaK Error", f"Application failed to start:\n{str(e)}")
        except:
            # Fallback to console output
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
