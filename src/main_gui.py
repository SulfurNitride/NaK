#!/usr/bin/env python3
"""
NaK - Linux Modding Helper
Main entry point for the application
"""

import sys
import os
import argparse
import logging



try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QCoreApplication
    
    from gui.main_window import main as gui_main
    from core.core import Core
    from utils.logger import get_logger, setup_comprehensive_logging
except ImportError as e:
    print(f"Import error: {e}", file=sys.stderr)
    print("Please install required dependencies:", file=sys.stderr)
    print("pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="NaK - Linux Modding Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Launch GUI
  %(prog)s --check-deps       # Check dependencies
  %(prog)s --version          # Show version
        """
    )
    
    parser.add_argument("--check-deps", action="store_true", 
                       help="Check if all dependencies are available")
    parser.add_argument("--version", action="store_true", 
                       help="Show version information")
    
    return parser


def main():
    """Main application entry point"""
    try:
        # Setup comprehensive logging
        log_file_path = setup_comprehensive_logging()
        logger = logging.getLogger(__name__)
        logger.info("Starting NaK - Linux Modding Helper")
        
        # Parse command line arguments
        parser = create_parser()
        args = parser.parse_args()
        
        # Handle CLI commands
        if args.check_deps:
            core = Core()
            if core.check_dependencies():
                print("All dependencies are available!")
                return 0
            else:
                print("Some dependencies are missing!")
                return 1
        
        if args.version:
            core = Core()
            version, date = core.get_version_info()
            print(f"NaK Linux Modding Helper v{version} ({date})")
            return 0
        
        # Launch GUI
        gui_main()
        logger.info("GUI started successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        # Show error dialog if GUI is available
        try:
            app = QCoreApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("NaK Error")
            msg_box.setText(f"Application failed to start:\n{str(e)}")
            msg_box.exec()
        except:
            # Fallback to console output
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
