"""
Constants for NaK Flet application
Centralized configuration values and magic numbers
"""

# Application Version
APP_VERSION = "4.0.1"
APP_DATE = "11/18/25"

# Feature Flags
class FeatureFlags:
    """Feature toggles for major functionality"""
    # Steam/Heroic Integration (DISABLED during Proton-GE refactor)
    ENABLE_STEAM_INTEGRATION = False  # VDF editing, Steam shortcuts
    ENABLE_HEROIC_INTEGRATION = False  # Heroic launcher detection
    ENABLE_AUTO_GAME_DETECTION = False  # Automatic game scanning
    ENABLE_SIMPLE_MODDING = False  # Simple game modding view

    # Proton-GE Features (NEW)
    ENABLE_PROTON_GE = True  # Use Proton-GE instead of Steam Proton
    ENABLE_STANDALONE_PREFIXES = True  # Use ~/NaK/Prefixes/ instead of compatdata


# Window Configuration
class WindowDefaults:
    """Default window dimensions and constraints"""
    WIDTH = 1200
    HEIGHT = 800
    MIN_WIDTH = 800
    MIN_HEIGHT = 600


# Dialog Timing
class DialogDelays:
    """Delays between dialogs to prevent overlap (in seconds)"""
    CACHE_DIALOG = 0.5
    STEAM_PICKER = 0.3
    PROTON_CHECK = 0.7


# Background Scanning
class ScanningConfig:
    """Configuration for background game scanning"""
    SCAN_INTERVAL_SECONDS = 30  # How often to scan for games
    INITIAL_SCAN_DELAY = 0.5  # Delay before first scan


# UI Limits
class UILimits:
    """Limits for UI display"""
    MAX_GAMES_DISPLAYED = 50  # Maximum games to show in games view
    STEAM_PICKER_HEIGHT_BASE = 200  # Base height for Steam picker dialog
    STEAM_PICKER_HEIGHT_PER_INSTALL = 60  # Additional height per installation
    STEAM_PICKER_MAX_HEIGHT = 500  # Maximum height for Steam picker


# Cache Configuration
class CacheDefaults:
    """Default cache sizes for display"""
    DEPENDENCIES_SIZE_GB = 1.7
    MO2_SIZE_MB = 200
    VORTEX_SIZE_MB = 200
