# Filename: BASE/interface/gui_ui_builder.py
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from BASE.interface.gui_theme_manager import ThemeManager
from BASE.interface.gui_controls_view import ControlsView
from BASE.interface.gui_chat_view import ChatView
from BASE.interface.gui_tools_view import ToolsView
from BASE.interface.gui_info_view import InfoView
from BASE.interface.gui_config_view import ConfigView
from BASE.interface.gui_files_view import FilesView
from BASE.interface.gui_themes import THEMES
import personality.controls as controls


class UIBuilder:
    """Handles main UI creation — tabbed left notebook | persistent right chat pane"""

    __slots__ = ('parent', 'theme_manager', 'controls_view', 'chat_view_instance',
                 'tools_view', 'info_view', 'config_view', 'files_view', 'view_frames',
                 'menubar_frame', 'current_view', 'theme_selector', 'notebook', 'tabs')

    def __init__(self, parent):
        self.parent = parent
        self.parent.root.geometry("1400x900")
        self.theme_manager = ThemeManager(self.parent)
        self.controls_view = ControlsView(self.parent)
        self.chat_view_instance = ChatView(self.parent)

        hot_reload_manager = getattr(self.parent, 'hot_reload_manager', None)

        if hot_reload_manager:
            self.parent.logger.system("[UI Builder] Hot-reload manager available")
        else:
            self.parent.logger.warning("[UI Builder] No hot-reload manager - tool reload disabled")

        self.tools_view = ToolsView(
            self.parent,
            project_root,
            hot_reload_manager=hot_reload_manager
        )
        self.info_view = InfoView(self.parent, project_root)
        self.config_view = ConfigView(self.parent, project_root)
        self.files_view = FilesView(self.parent)

        self.parent.chat_view_instance = self.chat_view_instance

        self.notebook = None
        self.tabs = {}
        self.view_frames = {}
        self.menubar_frame = None
        self.current_view = None
        self.theme_selector = None

    def setup_gui(self):
        self.create_theme_bar()
        self.create_main_layout()
        self.create_left_notebook()
        self.create_all_views()
        self.theme_manager.apply_theme()
        self.theme_manager.enable_widget_updates()

    # ------------------------------------------------------------------
    # Top bar — theme selector only
    # ------------------------------------------------------------------
    def create_theme_bar(self):
        theme = self.theme_manager.get_theme()
        font_name = "Courier New" if self.theme_manager.theme_name == "Cyber" else "Segoe UI"

        bar = tk.Frame(self.parent.root, bg=theme.BG_DARKER, height=30)
        bar.pack(side=tk.TOP, fill=tk.X)
        bar.pack_propagate(False)
        self.menubar_frame = bar

        tk.Label(
            bar, text="Theme:",
            bg=theme.BG_DARKER, fg=theme.FG_PRIMARY,
            font=(font_name, 9)
        ).pack(side=tk.RIGHT, padx=(0, 5), pady=4)

        self.theme_selector = ttk.Combobox(
            bar, values=list(THEMES.keys()),
            state='readonly', width=10, font=(font_name, 9)
        )
        self.theme_selector.set(self.theme_manager.theme_name)
        self.theme_selector.bind('<<ComboboxSelected>>', self.on_theme_change)
        self.theme_selector.pack(side=tk.RIGHT, padx=(0, 10), pady=4)

    # ------------------------------------------------------------------
    # Main layout — horizontal split: left notebook | right chat
    # ------------------------------------------------------------------
    def create_main_layout(self):
        self.parent.main_paned = ttk.PanedWindow(self.parent.root, orient=tk.HORIZONTAL)
        self.parent.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.parent.left_frame = ttk.Frame(self.parent.main_paned, width=560)
        self.parent.left_frame.pack_propagate(False)
        self.parent.main_paned.add(self.parent.left_frame, weight=1)

        self.parent.right_frame = ttk.Frame(self.parent.main_paned)
        self.parent.main_paned.add(self.parent.right_frame, weight=2)

        self.parent.chat_view = self.parent.right_frame

    # ------------------------------------------------------------------
    # Left notebook — one tab per view
    # ------------------------------------------------------------------
    def create_left_notebook(self):
        self.notebook = ttk.Notebook(self.parent.left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        tab_order = [
            ("Config",   "config_view"),
            ("Controls", "controls_view"),
            ("Files",    "files_view"),
            ("Tools",    "tools_view"),
            ("Info",     "info_view"),
        ]

        self.tabs = {}
        for name, attr in tab_order:
            frame = ttk.Frame(self.notebook)
            setattr(self.parent, attr, frame)
            self.notebook.add(frame, text=f"  {name}  ")
            self.tabs[name] = frame

    # ------------------------------------------------------------------
    # Populate every view
    # ------------------------------------------------------------------
    def create_all_views(self):
        self.config_view.create_config_view()
        self.controls_view.create_controls_view()
        self.files_view.create_files_view()
        self.tools_view.create_tools_view()
        self.info_view.create_info_view()
        self.chat_view_instance.create_chat_view()

    # ------------------------------------------------------------------
    # Theme change
    # ------------------------------------------------------------------
    def on_theme_change(self, event=None):
        new_theme = self.theme_selector.get()
        self.theme_manager.set_theme(new_theme)

        if self.menubar_frame and self.menubar_frame.winfo_exists():
            self.menubar_frame.destroy()

        self.create_theme_bar()

        if hasattr(self.parent, 'logger'):
            self.parent.logger.system(f"Theme changed to: {new_theme}")

    # ------------------------------------------------------------------
    # Legacy stubs — kept so external callers don't break
    # ------------------------------------------------------------------
    def switch_view(self, view_name: str):
        """Select the matching notebook tab if it exists."""
        if not self.notebook:
            return
        for idx, tab_id in enumerate(self.notebook.tabs()):
            if self.notebook.tab(tab_id, "text").strip() == view_name:
                self.notebook.select(idx)
                break

    def update_tab_styles(self):
        """No-op — ttk.Notebook handles its own tab highlighting."""
        pass

    # ------------------------------------------------------------------
    # Utility dialogs
    # ------------------------------------------------------------------
    def show_status_dialog(self):
        from tkinter import scrolledtext
        theme = self.theme_manager.get_theme()
        font_name = "Courier New" if self.theme_manager.theme_name == "Cyber" else "Segoe UI"

        dialog = tk.Toplevel(self.parent.root)
        dialog.title("Current Status")
        dialog.configure(bg=theme.BG_DARK)
        dialog.geometry("500x400")

        text_widget = scrolledtext.ScrolledText(
            dialog, wrap=tk.WORD, font=(font_name, 10),
            bg=theme.BG_DARKER, fg=theme.FG_PRIMARY,
            insertbackground=theme.FG_PRIMARY
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.config(state=tk.DISABLED)

    def validate_config(self):
        from tkinter import messagebox
        is_valid = self.parent.control_manager.validate_all_configs()
        if is_valid:
            messagebox.showinfo("Validation", "Configuration is valid!")
        else:
            messagebox.showwarning("Validation", "Configuration has issues. Check system log for details.")

    def export_settings(self):
        from tkinter import messagebox
        import json
        from datetime import datetime
        try:
            settings = self.parent.control_manager.get_all_features()
            filename = f"ai_settings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(settings, f, indent=2)
            messagebox.showinfo("Export", f"Settings exported to {filename}")
            self.parent.logger.success(f"Settings exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export settings: {e}")
            self.parent.logger.error(f"Failed to export settings: {e}")