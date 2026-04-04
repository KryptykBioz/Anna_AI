# Filename: BASE/interface/gui_controls_view.py
"""
Controls View - REFACTORED for internal tool manager
Handles control changes that trigger tool switching
"""

import tkinter as tk
from tkinter import ttk
from BASE.interface.gui_themes import DarkTheme


class ControlsView:
    """Manages the Controls view with internal tool integration"""

    __slots__ = ('parent',)
    
    def __init__(self, parent):
        self.parent = parent
    
    def create_controls_view(self):
        """Create the Controls view with control panel and auxiliary panels"""
        controls_paned = ttk.PanedWindow(self.parent.controls_view, orient=tk.HORIZONTAL)
        controls_paned.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(controls_paned, width=460)
        left_frame.pack_propagate(False)
        controls_paned.add(left_frame, weight=0)
        
        right_frame = ttk.Frame(controls_paned)
        controls_paned.add(right_frame, weight=1)
        
        self.parent.control_panel_manager.create_control_panel(left_frame)
        
        self.create_auxiliary_panels(right_frame)

    def create_auxiliary_panels(self, parent_frame):
        """Create voice, YouTube, Twitch, Discord, and Warudo panels"""
        
        self.create_current_context_panel(parent_frame)
        
        self.create_important_reminders_panel(parent_frame)
        
        self.parent.voice_manager.create_voice_panel(parent_frame)
        
        integrations_frame = ttk.LabelFrame(
            parent_frame, 
            text="External Integrations", 
            style="Dark.TLabelframe"
        )
        integrations_frame.pack(fill=tk.X, pady=(5, 0))

    def create_important_reminders_panel(self, parent_frame):
        """Create important reminders editor panel"""
        reminders_frame = ttk.LabelFrame(
            parent_frame,
            text="Important Reminders (Prompt Addendum)",
            style="Dark.TLabelframe"
        )
        reminders_frame.pack(fill=tk.X, pady=(0, 5))
        
        inner_frame = tk.Frame(reminders_frame, bg=DarkTheme.BG_DARK)
        inner_frame.pack(fill=tk.X, padx=10, pady=10)
        
        instructions = tk.Label(
            inner_frame,
            text="Optional reminders appended to end of all cognitive prompts. Leave blank to disable.",
            font=("Segoe UI", 8, "italic"),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_MUTED,
            wraplength=300,
            justify=tk.LEFT
        )
        instructions.pack(anchor=tk.W, pady=(0, 5))
        
        text_frame = tk.Frame(inner_frame, bg=DarkTheme.BG_DARK)
        text_frame.pack(fill=tk.X, pady=(0, 5))
        
        from tkinter import scrolledtext
        self.parent.reminders_text = scrolledtext.ScrolledText(
            text_frame,
            height=3,
            width=40,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY,
            insertbackground=DarkTheme.ACCENT_GREEN,
            relief=tk.FLAT,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=DarkTheme.BORDER,
            highlightcolor=DarkTheme.ACCENT_PURPLE
        )
        self.parent.reminders_text.pack(fill=tk.X)
        
        current_value = self.parent.config.important_reminders
        if current_value:
            self.parent.reminders_text.insert(1.0, current_value)
        
        button_frame = tk.Frame(inner_frame, bg=DarkTheme.BG_DARK)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        save_btn = tk.Button(
            button_frame,
            text="[Save] Save & Apply",
            command=self.save_important_reminders,
            font=("Segoe UI", 9, "bold"),
            bg=DarkTheme.ACCENT_PURPLE,
            fg="white",
            activebackground=DarkTheme.BUTTON_HOVER,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=5
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 5))

        clear_btn = tk.Button(
            button_frame,
            text="[Clear] Clear",
            command=self.clear_important_reminders,
            font=("Segoe UI", 9),
            bg=DarkTheme.BUTTON_BG,
            fg=DarkTheme.FG_PRIMARY,
            activebackground=DarkTheme.BUTTON_HOVER,
            activeforeground=DarkTheme.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=5
        )
        clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.parent.reminders_status_label = tk.Label(
            button_frame,
            text="",
            font=("Segoe UI", 8, "italic"),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_MUTED
        )
        self.parent.reminders_status_label.pack(side=tk.LEFT, padx=(10, 0))

    def save_important_reminders(self):
        """Save important reminders to config"""
        try:
            reminders = self.parent.reminders_text.get(1.0, tk.END).strip()
            
            if reminders:
                self.parent.config.important_reminders = reminders
                self.parent.logger.system(f"[Important Reminders] Updated: {reminders[:50]}...")
                self.parent.reminders_status_label.config(
                    text="[Confirmed] Saved",
                    fg=DarkTheme.ACCENT_GREEN
                )
            else:
                self.parent.config.important_reminders = None
                self.parent.logger.system("[Important Reminders] Cleared")
                self.parent.reminders_status_label.config(
                    text="[Confirmed] Cleared",
                    fg=DarkTheme.ACCENT_GREEN
                )
            
            self.parent.root.after(2000, lambda: self.parent.reminders_status_label.config(text=""))
            
        except Exception as e:
            self.parent.logger.error(f"[Important Reminders] Save error: {e}")
            self.parent.reminders_status_label.config(
                text="[Warning] Error",
                fg=DarkTheme.ACCENT_RED
            )

    def clear_important_reminders(self):
        """Clear important reminders"""
        self.parent.reminders_text.delete(1.0, tk.END)
        self.save_important_reminders()
    
    def create_current_context_panel(self, parent_frame):
        """Create current context editor panel"""
        context_frame = ttk.LabelFrame(
            parent_frame,
            text="Current Context (Prompt Addendum)",
            style="Dark.TLabelframe"
        )
        context_frame.pack(fill=tk.X, pady=(0, 5))
        
        inner_frame = tk.Frame(context_frame, bg=DarkTheme.BG_DARK)
        inner_frame.pack(fill=tk.X, padx=10, pady=10)
        
        instructions = tk.Label(
            inner_frame,
            text="Optional context added to all cognitive prompts. Leave blank to disable.",
            font=("Segoe UI", 8, "italic"),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_MUTED,
            wraplength=300,
            justify=tk.LEFT
        )
        instructions.pack(anchor=tk.W, pady=(0, 5))
        
        text_frame = tk.Frame(inner_frame, bg=DarkTheme.BG_DARK)
        text_frame.pack(fill=tk.X, pady=(0, 5))
        
        from tkinter import scrolledtext
        self.parent.context_text = scrolledtext.ScrolledText(
            text_frame,
            height=3,
            width=40,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY,
            insertbackground=DarkTheme.ACCENT_GREEN,
            relief=tk.FLAT,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=DarkTheme.BORDER,
            highlightcolor=DarkTheme.ACCENT_PURPLE
        )
        self.parent.context_text.pack(fill=tk.X)
        
        current_value = self.parent.config.current_context
        if current_value:
            self.parent.context_text.insert(1.0, current_value)
        
        button_frame = tk.Frame(inner_frame, bg=DarkTheme.BG_DARK)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        save_btn = tk.Button(
            button_frame,
            text="Save & Apply",
            command=self.save_current_context,
            font=("Segoe UI", 9, "bold"),
            bg=DarkTheme.ACCENT_PURPLE,
            fg="white",
            activebackground=DarkTheme.BUTTON_HOVER,
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=5
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        clear_btn = tk.Button(
            button_frame,
            text="Clear",
            command=self.clear_current_context,
            font=("Segoe UI", 9),
            bg=DarkTheme.BUTTON_BG,
            fg=DarkTheme.FG_PRIMARY,
            activebackground=DarkTheme.BUTTON_HOVER,
            activeforeground=DarkTheme.FG_PRIMARY,
            relief=tk.FLAT,
            cursor="hand2",
            padx=15,
            pady=5
        )
        clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.parent.context_status_label = tk.Label(
            button_frame,
            text="",
            font=("Segoe UI", 8, "italic"),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_MUTED
        )
        self.parent.context_status_label.pack(side=tk.LEFT, padx=(10, 0))
    
    def save_current_context(self):
        """Save current context to config"""
        try:
            context = self.parent.context_text.get(1.0, tk.END).strip()
            
            if context:
                self.parent.config.current_context = context
                self.parent.logger.system(f"[Current Context] Updated: {context[:50]}...")
                self.parent.context_status_label.config(
                    text="[Confirmed] Saved",
                    fg=DarkTheme.ACCENT_GREEN
                )
            else:
                self.parent.config.current_context = None
                self.parent.logger.system("[Current Context] Cleared")
                self.parent.context_status_label.config(
                    text="[Confirmed] Cleared",
                    fg=DarkTheme.ACCENT_GREEN
                )
            
            self.parent.root.after(2000, lambda: self.parent.context_status_label.config(text=""))
            
        except Exception as e:
            self.parent.logger.error(f"[Current Context] Save error: {e}")
            self.parent.context_status_label.config(
                text="[Warning] Error",
                fg=DarkTheme.ACCENT_RED
            )
    
    def clear_current_context(self):
        """Clear current context"""
        self.parent.context_text.delete(1.0, tk.END)
        self.save_current_context()