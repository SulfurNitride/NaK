"""
Cache Configuration Manager
Handles cache preferences for NaK Linux Modding Helper
"""

import json
import os
from pathlib import Path
from typing import Dict, Any


class CacheConfig:
    """Manages cache configuration preferences"""

    def __init__(self):
        # Set up config path
        self.nak_dir = Path.home() / "NaK"
        self.config_file = self.nak_dir / "cache_config.json"

        # Ensure NaK directory exists
        self.nak_dir.mkdir(parents=True, exist_ok=True)

        # Load or create config
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load cache configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception:
                # If config is corrupted, return default
                return self._get_default_config()
        else:
            # First run - create default config
            default_config = self._get_default_config()
            default_config["first_run"] = True
            self._save_config(default_config)
            return default_config

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default cache configuration"""
        return {
            "cache_enabled": True,  # Enable caching by default
            "cache_dependencies": True,  # Cache dependency files (1.7GB)
            "cache_mo2": True,  # Cache MO2 downloads
            "cache_vortex": True,  # Cache Vortex downloads
            "first_run": False,
            "cache_location": str(self.nak_dir / "cache"),
            "show_cache_prompt": True  # Show prompt on first run
        }

    def _save_config(self, config: Dict[str, Any]):
        """Save cache configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Failed to save cache config: {e}")

    def is_first_run(self) -> bool:
        """Check if this is the first run"""
        return self.config.get("first_run", False)

    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled"""
        return self.config.get("cache_enabled", True)

    def should_cache_dependencies(self) -> bool:
        """Check if dependency caching is enabled"""
        return self.config.get("cache_dependencies", True)

    def should_cache_mo2(self) -> bool:
        """Check if MO2 caching is enabled"""
        return self.config.get("cache_mo2", True)

    def should_cache_vortex(self) -> bool:
        """Check if Vortex caching is enabled"""
        return self.config.get("cache_vortex", True)

    def get_cache_location(self) -> str:
        """Get the cache directory location"""
        return self.config.get("cache_location", str(self.nak_dir / "cache"))

    def should_show_cache_prompt(self) -> bool:
        """Check if cache prompt should be shown"""
        return self.config.get("show_cache_prompt", True)

    def set_cache_preferences(self, enable_cache: bool, cache_dependencies: bool = True, cache_mo2: bool = True, cache_vortex: bool = True):
        """Set cache preferences"""
        self.config["cache_enabled"] = enable_cache
        self.config["cache_dependencies"] = cache_dependencies
        self.config["cache_mo2"] = cache_mo2
        self.config["cache_vortex"] = cache_vortex
        self.config["first_run"] = False
        self.config["show_cache_prompt"] = False
        self._save_config(self.config)

    def mark_first_run_complete(self):
        """Mark first run as complete"""
        self.config["first_run"] = False
        self.config["show_cache_prompt"] = False
        self._save_config(self.config)

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information"""
        cache_dir = Path(self.get_cache_location())

        if not cache_dir.exists():
            return {
                "exists": False,
                "size_mb": 0,
                "file_count": 0
            }

        # Calculate cache size
        total_size = 0
        file_count = 0
        for file in cache_dir.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size
                file_count += 1

        return {
            "exists": True,
            "size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "location": str(cache_dir)
        }
