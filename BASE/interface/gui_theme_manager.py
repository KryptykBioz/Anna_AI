# Filename: BASE/interface/gui_theme_manager.py

from tkinter import ttk
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from BASE.interface.gui_themes import THEMES, DEFAULT_THEME

class ThemeManager:
    """Manages application themes and Tkinter style configurations"""

    __slots__ = ('parent', 'current_theme', 'theme_name', 'skip_widget_update')

    def __init__(self, parent):
        self.parent = parent
        self.current_theme = THEMES[DEFAULT_THEME]
        self.theme_name = DEFAULT_THEME
        self.skip_widget_update = True  # Skip updates until widgets are created
    
    def set_theme(self, theme_name):
        """Switch to a different theme"""
        if theme_name in THEMES:
            self.theme_name = theme_name
            self.current_theme = THEMES[theme_name]
            self.apply_theme()
            return True
        return False
    
    def get_theme(self):
        """Get current theme class"""
        return self.current_theme
    
    def enable_widget_updates(self):
        """Enable widget updates after GUI initialization is complete"""
        self.skip_widget_update = False
    
    def apply_theme(self):
        """Apply current theme to the GUI"""
        theme = self.current_theme
        self.parent.root.configure(bg=theme.BG_DARKER)
        
        # Apply dark title bar (Windows 10/11) - only for dark themes
        if self.theme_name in ["Dark", "Cyber"]:
            try:
                import ctypes as ct
                
                def set_dark_title_bar(window):
                    """Set dark title bar on Windows 10/11 using DWM API"""
                    window.update()
                    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                    set_window_attribute = ct.windll.dwmapi.DwmSetWindowAttribute
                    get_parent = ct.windll.user32.GetParent
                    hwnd = get_parent(window.winfo_id())
                    
                    value = ct.c_int(2)
                    set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                                       ct.byref(value), ct.sizeof(value))
                
                set_dark_title_bar(self.parent.root)
                
            except Exception:
                pass  # Silently fail if not on Windows
        
        # Configure default Tkinter scrollbar colors
        self.parent.root.option_add("*Scrollbar.background", theme.BUTTON_BG)
        self.parent.root.option_add("*Scrollbar.troughColor", theme.BG_DARKER)
        self.parent.root.option_add("*Scrollbar.activeBackground", 
                                    theme.ACCENT_GREEN if self.theme_name == "Cyber" 
                                    else theme.ACCENT_PURPLE)
        self.parent.root.option_add("*Scrollbar.highlightBackground", theme.BG_DARKER)
        self.parent.root.option_add("*Scrollbar.borderWidth", 0)
        self.parent.root.option_add("*Scrollbar.relief", "flat")
        
        style = ttk.Style()
        style.theme_use('clam')

        # Frame styling
        style.configure('TFrame', background=theme.BG_DARKER)
        
        # Label styling
        font_name = "Courier New" if self.theme_name == "Cyber" else "Segoe UI"
        style.configure('TLabel', 
                       background=theme.BG_DARKER, 
                       foreground=theme.FG_PRIMARY, 
                       font=(font_name, 9))
        
        # Button styling
        style.configure('TButton', 
                       background=theme.BUTTON_BG, 
                       foreground=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_PRIMARY,
                       borderwidth=2 if self.theme_name == "Cyber" else 1, 
                       bordercolor=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.BORDER,
                       focuscolor='none' if self.theme_name != "Cyber" else theme.ACCENT_PURPLE,
                       font=(font_name, 9, "bold"),
                       relief='flat',
                       padding=(16, 8) if self.theme_name == "Cyber" else (12, 6))
        style.map('TButton',
                 background=[('active', theme.BUTTON_HOVER),
                           ('pressed', theme.ACCENT_PURPLE)],
                 foreground=[('active', theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_PRIMARY),
                           ('pressed', '#ffffff' if self.theme_name == "Cyber" else theme.FG_PRIMARY)],
                 bordercolor=[('active', theme.ACCENT_PURPLE)])
        
        # Checkbutton styling
        style.configure('TCheckbutton', 
                       background=theme.BG_DARKER, 
                       foreground=theme.FG_PRIMARY,
                       focuscolor='none',
                       indicatorcolor=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.ACCENT_PURPLE,
                       font=(font_name, 9))
        style.map('TCheckbutton',
                 background=[('active', theme.BG_DARKER)],
                 foreground=[('active', theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_PRIMARY)],
                 indicatorcolor=[('selected', theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.ACCENT_PURPLE),
                               ('active', theme.ACCENT_PURPLE)])

        # Scrollbar styling
        style.configure('Vertical.TScrollbar',
                       background=theme.BUTTON_BG,
                       troughcolor=theme.BG_DARKER,
                       bordercolor=theme.BORDER,
                       arrowcolor=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_MUTED,
                       relief='flat',
                       borderwidth=1 if self.theme_name == "Cyber" else 0)
        style.map('Vertical.TScrollbar',
                 background=[('active', theme.ACCENT_PURPLE),
                           ('pressed', theme.ACCENT_GREEN)])
        
        style.configure('Horizontal.TScrollbar',
                       background=theme.BUTTON_BG,
                       troughcolor=theme.BG_DARKER,
                       bordercolor=theme.BORDER,
                       arrowcolor=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_MUTED,
                       relief='flat',
                       borderwidth=1 if self.theme_name == "Cyber" else 0)
        style.map('Horizontal.TScrollbar',
                 background=[('active', theme.ACCENT_PURPLE),
                           ('pressed', theme.ACCENT_GREEN)])

        # LabelFrame styling
        style.configure("Dark.TLabelframe", 
                       background=theme.BG_DARKER,
                       foreground=theme.ACCENT_PURPLE, 
                       bordercolor=theme.BORDER,
                       borderwidth=2 if self.theme_name == "Cyber" else 1,
                       relief='solid')
        style.configure("Dark.TLabelframe.Label", 
                       background=theme.BG_DARKER,
                       foreground=theme.ACCENT_PURPLE,
                       font=(font_name, 10 if self.theme_name == "Cyber" else 9, "bold"))
        
        # Accent labelframe
        style.configure("Accent.TLabelframe", 
                       background=theme.BG_DARKER,
                       foreground=theme.ACCENT_GREEN, 
                       bordercolor=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.BORDER_ACCENT,
                       relief='solid',
                       borderwidth=2)
        style.configure("Accent.TLabelframe.Label", 
                       background=theme.BG_DARKER,
                       foreground=theme.ACCENT_GREEN,
                       font=(font_name, 11 if self.theme_name == "Cyber" else 10, "bold"))
        
        # Notebook (tabs) styling
        style.configure('TNotebook', 
                       background=theme.BG_DARKER,
                       borderwidth=0)
        style.configure('TNotebook.Tab',
                       background=theme.BUTTON_BG,
                       foreground=theme.FG_PRIMARY,
                       borderwidth=2 if self.theme_name == "Cyber" else 1,
                       bordercolor=theme.BORDER,
                       padding=(12, 6),
                       font=(font_name, 9, "bold"))
        style.map('TNotebook.Tab',
                 background=[('selected', theme.ACCENT_PURPLE),
                           ('active', theme.BUTTON_HOVER)],
                 foreground=[('selected', theme.ACCENT_GREEN if self.theme_name == "Cyber" else '#ffffff')],
                 bordercolor=[('selected', theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.BORDER_ACCENT)])
        
        # Combobox styling for theme selector
        style.configure('TCombobox',
                       fieldbackground=theme.BG_LIGHTER,
                       background=theme.BUTTON_BG,
                       foreground=theme.FG_PRIMARY,
                       selectbackground=theme.ACCENT_PURPLE,
                       selectforeground='#ffffff',
                       borderwidth=1,
                       relief='solid')
        style.map('TCombobox',
                 fieldbackground=[('readonly', theme.BG_LIGHTER)],
                 selectbackground=[('readonly', theme.BG_LIGHTER)])
        
        # Update all existing text widgets if they exist
        if not self.skip_widget_update:
            self._update_text_widgets()
        
        # Update menu/tabs if they exist
        if hasattr(self.parent, 'ui_builder') and hasattr(self.parent.ui_builder, 'tabs'):
            self.parent.ui_builder.update_tab_styles()
    
    def _update_text_widgets(self):
        """Update colors of existing text widgets"""
        theme = self.current_theme
        font_name = "Courier New" if self.theme_name == "Cyber" else "Segoe UI"
        
        # Update system log if it exists and is not None
        if hasattr(self.parent, 'system_log') and self.parent.system_log is not None:
            self.parent.system_log.config(
                bg=theme.BG_DARK,
                fg=theme.FG_PRIMARY,
                insertbackground=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_PRIMARY,
                selectbackground=theme.ACCENT_PURPLE,
                selectforeground=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_PRIMARY,
                font=(font_name, 9)
            )
        
        # Update chat display if it exists and is not None
        if hasattr(self.parent, 'chat_display') and self.parent.chat_display is not None:
            self.parent.chat_display.config(
                bg=theme.BG_DARK,
                fg=theme.FG_PRIMARY,
                insertbackground=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_PRIMARY,
                selectbackground=theme.ACCENT_PURPLE,
                selectforeground=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_PRIMARY,
                font=(font_name, 10)
            )
            
            # Reconfigure chat display tags with new colors
            if hasattr(self.parent, 'chat_view_instance') and self.parent.chat_view_instance is not None:
                self.parent.chat_view_instance._configure_chat_display_tags()
        
        # Update input text if it exists and is not None
        if hasattr(self.parent, 'input_text') and self.parent.input_text is not None:
            self.parent.input_text.config(
                bg=theme.BG_LIGHTER,
                fg=theme.FG_PRIMARY,
                insertbackground=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_PRIMARY,
                selectbackground=theme.ACCENT_PURPLE,
                selectforeground=theme.ACCENT_GREEN if self.theme_name == "Cyber" else theme.FG_PRIMARY,
                font=(font_name, 10)
            )
        
        # Update processing label if it exists and is not None
        if hasattr(self.parent, 'processing_label') and self.parent.processing_label is not None:
            self.parent.processing_label.config(
                foreground=theme.ACCENT_PURPLE,
                background=theme.BG_DARKER
            )