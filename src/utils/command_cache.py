"""
Cached command utilities for performance optimization
"""
import shutil
from functools import lru_cache

@lru_cache(maxsize=32)
def find_command(cmd: str) -> str:
    """Find command with caching"""
    return shutil.which(cmd)

@lru_cache(maxsize=16)
def get_protontricks_command() -> str:
    """Get protontricks command with caching"""
    if find_command("protontricks"):
        return "protontricks"
    elif find_command("flatpak"):
        import subprocess
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application"],
            capture_output=True, text=True, timeout=5
        )
        if "com.github.Matoking.protontricks" in result.stdout:
            return "flatpak run com.github.Matoking.protontricks"
    return ""
