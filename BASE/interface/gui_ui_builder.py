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
import BASE.config.controls as controls


class UIBuilder:
    """Handles main UI creation — 2x2 grid layout"""

    __slots__ = ('parent', 'theme_manager', 'controls_view', 'chat_view_instance',
                 'tools_view', 'info_view', 'config_view', 'files_view', 'view_frames',
                 'menubar_frame', 'current_view', 'theme_selector', 'notebook', 'tabs')

    def __init__(self, parent):
        self.parent = parent
        self.parent.root.geometry("1600x1200")
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
    # Main layout — 2x2 grid via nested PanedWindows
    #
    #  ┌─────────────────┬─────────────────┐
    #  │  Upper-Left     │  Upper-Right    │
    #  │  Config/Ctrl/   │  System Log     │
    #  │  Files/Info     │                 │
    #  ├─────────────────┼─────────────────┤
    #  │  Lower-Left     │  Lower-Right    │
    #  │  Tools          │  Chat           │
    #  └─────────────────┴─────────────────┘
    # ------------------------------------------------------------------
    def create_main_layout(self):
        # Outer vertical split (top row / bottom row)
        outer_paned = ttk.PanedWindow(self.parent.root, orient=tk.VERTICAL)
        outer_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Top row — horizontal split
        top_paned = ttk.PanedWindow(outer_paned, orient=tk.HORIZONTAL)
        outer_paned.add(top_paned, weight=3)

        # Bottom row — horizontal split
        bot_paned = ttk.PanedWindow(outer_paned, orient=tk.HORIZONTAL)
        outer_paned.add(bot_paned, weight=2)

        # ── Upper-left: tabbed notebook (Config / Controls / Files / Info) ──
        ul_frame = ttk.Frame(top_paned)
        top_paned.add(ul_frame, weight=1)

        self.notebook = ttk.Notebook(ul_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        tab_order = [
            ("Controls",  "controls_view"),
            ("Config",    "config_view"),
            ("Files",     "files_view"),
            ("Info",      "info_view"),
        ]
        self.tabs = {}
        for name, attr in tab_order:
            frame = ttk.Frame(self.notebook)
            setattr(self.parent, attr, frame)
            self.notebook.add(frame, text=f"  {name}  ")
            self.tabs[name] = frame

        self.notebook.select(0)

        # ── Upper-right: System Log ──
        ur_frame = ttk.Frame(top_paned)
        top_paned.add(ur_frame, weight=1)
        # chat_view is repurposed as the system-log host frame
        self.parent.chat_view = ur_frame

        # ── Lower-left: Tools ──
        ll_frame = ttk.Frame(bot_paned)
        bot_paned.add(ll_frame, weight=1)
        self.parent.tools_view = ll_frame

        # ── Lower-right: Chat ──
        lr_frame = ttk.Frame(bot_paned)
        bot_paned.add(lr_frame, weight=1)
        self.parent.chat_panel_frame = lr_frame

        # Populate all four quadrants
        self._create_all_views()

    # ------------------------------------------------------------------
    # Populate every view
    # ------------------------------------------------------------------
    def _create_all_views(self):
        self.config_view.create_config_view()
        self.controls_view.create_controls_view()
        self.files_view.create_files_view()
        self.info_view.create_info_view()
        self.tools_view.create_tools_view()
        # System log goes into upper-right (parent.chat_view)
        self.chat_view_instance.create_system_panel(self.parent.chat_view)
        # Chat panel goes into lower-right (parent.chat_panel_frame)
        self.chat_view_instance.create_chat_panel(self.parent.chat_panel_frame)

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
        if not self.notebook:
            return
        for idx, tab_id in enumerate(self.notebook.tabs()):
            if self.notebook.tab(tab_id, "text").strip() == view_name:
                self.notebook.select(idx)
                break

    def update_tab_styles(self):
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