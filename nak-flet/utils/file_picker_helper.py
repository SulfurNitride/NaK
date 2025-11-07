"""
File picker helper using YAD

Simple, lightweight file picker using YAD (zenity fork without webkit dependencies!)
"""

import subprocess
from typing import Optional
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)


def pick_directory(title: str = "Select Directory") -> Optional[str]:
    """
    Open file chooser using YAD

    Args:
        title: Dialog title text

    Returns:
        Selected directory path (absolute), or None if cancelled
    """
    try:
        logger.debug(f"Calling yad with title: {title}")

        result = subprocess.run(
            ['yad', '--file', '--directory', f'--title={title}'],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            path = result.stdout.strip()
            if path:
                logger.info(f"User selected directory: {path}")
                return path

        logger.info("User cancelled directory selection")
        return None

    except Exception as e:
        logger.error(f"Failed to call yad: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def pick_file(title: str = "Select File", file_filter: Optional[str] = None) -> Optional[str]:
    """
    Open file chooser using YAD

    Args:
        title: Dialog title text
        file_filter: Optional file filter pattern (e.g., "*.exe")

    Returns:
        Selected file path (absolute), or None if cancelled
    """
    try:
        logger.debug(f"Calling yad with title: {title}")

        cmd = ['yad', '--file', f'--title={title}']

        if file_filter:
            cmd.append(f'--file-filter={file_filter}')

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            path = result.stdout.strip()
            if path:
                logger.info(f"User selected file: {path}")
                return path

        logger.info("User cancelled file selection")
        return None

    except Exception as e:
        logger.error(f"Failed to call yad: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
