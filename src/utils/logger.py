"""
Logger utility module for consistent logging across the application
Enhanced with comprehensive file logging and AppImage support
"""
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a logger with consistent configuration

    If the root logger has handlers (from setup_comprehensive_logging),
    just return a logger that propagates to the root logger.
    Otherwise, configure it independently.
    """
    logger = logging.getLogger(name)

    # Check if root logger is configured
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Root logger is configured, just set level and propagate
        if level is not None:
            logger.setLevel(level)
        else:
            logger.setLevel(logging.NOTSET)  # Inherit from root
        logger.propagate = True  # Let it propagate to root logger
        return logger

    # Only configure if root logger is not configured and logger has no handlers
    if not logger.handlers:
        # Set level - use INFO by default for cleaner output
        if level is None:
            level = logging.INFO
        logger.setLevel(level)

        # Create formatter with more detail
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d [%(levelname)8s] %(name)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(console_handler)

        # Prevent propagation to root logger
        logger.propagate = False

    return logger


def get_appimage_log_path() -> Path:
    """Get the log file path in the NaK logs directory"""
    # Always use the NaK logs directory
    nak_logs_dir = Path.home() / "NaK" / "logs"
    nak_logs_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"nak_debug_{timestamp}.log"
    return nak_logs_dir / log_filename


def setup_comprehensive_logging(level: int = logging.INFO) -> Path:
    """Setup comprehensive logging system with file output"""
    # Get log file path
    log_file_path = get_appimage_log_path()

    # Ensure log directory exists
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create custom formatter with more detail
    detailed_formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d [%(levelname)8s] %(name)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console formatter (clean, professional)
    console_formatter = logging.Formatter(
        '[%(levelname)s] %(message)s'
    )

    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create file handler with detailed logging
    file_handler = RotatingFileHandler(log_file_path, maxBytes=1024*1024, backupCount=5, mode='w', encoding='utf-8')
    file_handler.setLevel(level)  # Use the same level as parameter
    file_handler.setFormatter(detailed_formatter)

    # Create console handler with less verbose logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    root_logger.setLevel(level)  # Use the same level as parameter
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info("NaK - Linux Modding Helper - Starting")
    logger.debug(f"Log file: {log_file_path}")
    if os.environ.get('APPIMAGE'):
        logger.debug(f"Running from AppImage: {os.environ.get('APPIMAGE')}")
    logger.debug(f"Working directory: {Path.cwd()}")
    logger.debug(f"Python: {sys.executable} ({sys.version.split()[0]})")

    # Log environment info
    logger.debug("Environment variables:")
    for key, value in sorted(os.environ.items()):
        if any(sensitive in key.upper() for sensitive in ['TOKEN', 'PASSWORD', 'SECRET', 'KEY']):
            logger.debug(f"  {key}=<REDACTED>")
        else:
            logger.debug(f"  {key}={value}")

    return log_file_path
