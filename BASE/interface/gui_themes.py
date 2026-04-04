# Filename: BASE/interface/gui_themes.py
"""
Theme and color definitions for the GUI application.
Supports Light, Dark, and Cyberpunk themes.
"""

class LightTheme:
    """Light theme - Clean and professional"""
    NAME = "Light"
    LABEL = "#000000"
    BG_DARK = "#f8f9fa"
    BG_DARKER = "#e9ecef"
    BG_LIGHTER = "#ffffff"
    FG_PRIMARY = "#212529"
    FG_SECONDARY = "#6c757d"
    FG_MUTED = "#adb5bd"
    ACCENT_PURPLE = "#6f42c1"
    ACCENT_PURPLE_LIGHT = "#9775fa"
    ACCENT_PURPLE_DARK = "#5a32a3"
    ACCENT_GREEN = "#198754"
    ACCENT_BLUE = "#0d6efd"
    ACCENT_ORANGE = "#fd7e14"
    ACCENT_RED = "#dc3545"
    ACCENT_YELLOW = "#ffc107"
    BORDER = "#dee2e6"
    BORDER_ACCENT = "#6f42c1"
    BUTTON_BG = "#e9ecef"
    BUTTON_HOVER = "#dee2e6"
    # Status colors
    ERROR_COLOR = "#dc3545"
    WARNING_COLOR = "#ffc107"
    SUCCESS_COLOR = "#198754"

class DarkTheme:
    """Dark theme - Modern purple/black aesthetic"""
    NAME = "Dark"
    LABEL = "#ffffff"
    BG_DARK = "#1e1e1e"
    BG_DARKER = "#141414"
    BG_LIGHTER = "#2a2a2a"
    FG_PRIMARY = "#d4d4d4"
    FG_SECONDARY = "#9a9a9a"
    FG_MUTED = "#6a6a6a"
    ACCENT_PURPLE = "#8b5cf6"
    ACCENT_PURPLE_LIGHT = "#a78bfa"
    ACCENT_PURPLE_DARK = "#6d28d9"
    ACCENT_GREEN = "#10b981"
    ACCENT_BLUE = "#3b82f6"
    ACCENT_ORANGE = "#f59e0b"
    ACCENT_RED = "#ef4444"
    ACCENT_YELLOW = "#fbbf24"
    BORDER = "#2a2a2a"
    BORDER_ACCENT = "#8b5cf6"
    BUTTON_BG = "#2a2a2a"
    BUTTON_HOVER = "#3a3a3a"
    # Status colors
    ERROR_COLOR = "#ef4444"
    WARNING_COLOR = "#fbbf24"
    SUCCESS_COLOR = "#10b981"

class CyberTheme:
    """Cyberpunk theme - Neon green/purple with deep backgrounds"""
    NAME = "Cyber"
    LABEL = "#00ff88"
    BG_DARK = "#0a0015"
    BG_DARKER = "#050008"
    BG_LIGHTER = "#1a0a2e"
    FG_PRIMARY = "#00ff88"
    FG_SECONDARY = "#8a2be2"
    FG_MUTED = "#6a4c93"
    ACCENT_PURPLE = "#8a2be2"
    ACCENT_PURPLE_LIGHT = "#a855f7"
    ACCENT_PURPLE_DARK = "#6d28d9"
    ACCENT_GREEN = "#00ff88"
    ACCENT_BLUE = "#00d4ff"
    ACCENT_ORANGE = "#ff6b35"
    ACCENT_RED = "#ff006e"
    ACCENT_YELLOW = "#ffbe0b"
    BORDER = "#8a2be2"
    BORDER_ACCENT = "#00ff88"
    BUTTON_BG = "#1a0a2e"
    BUTTON_HOVER = "#2d1b4e"
    GLOW_GREEN = "rgba(0, 255, 136, 0.3)"
    GLOW_PURPLE = "rgba(138, 43, 226, 0.3)"
    # Status colors
    ERROR_COLOR = "#ff006e"
    WARNING_COLOR = "#ffbe0b"
    SUCCESS_COLOR = "#00ff88"

# Theme registry for easy access
THEMES = {
    "Light": LightTheme,
    "Dark": DarkTheme,
    "Cyber": CyberTheme
}

# Default theme
DEFAULT_THEME = "Cyber"