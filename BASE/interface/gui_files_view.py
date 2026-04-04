# Filename: BASE/interface/gui_files_view.py
"""
Files View - Wrapper for SessionFilesPanel
Manages the Files tab view
"""

import tkinter as tk
from tkinter import ttk


class FilesView:
    """Manages the Files view tab"""

    __slots__ = ('parent', 'logger', 'ai_core')
    
    def __init__(self, parent):
        self.parent = parent
        self.logger = parent.logger
        self.ai_core = parent.ai_core
        
    def create_files_view(self):
        """Create the files view with session files panel"""
        # Main container
        container = ttk.Frame(self.parent.files_view)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create session files panel using the existing SessionFilesPanel
        if hasattr(self.parent, 'session_files_panel'):
            self.parent.session_files_panel.create_panel(container)
            self.logger.system("[Files View] Session files panel integrated")
        else:
            self.logger.error("[Files View] session_files_panel not found in parent")
            
            # Show error message in the view
            error_label = tk.Label(
                container,
                text="⚠️ Session Files Panel Not Available\n\n"
                     "The session files manager could not be initialized.\n"
                     "Please check the system log for details.",
                font=("Segoe UI", 12),
                fg="#ff6b6b",
                bg="#1e1e1e",
                pady=50
            )
            error_label.pack(fill=tk.BOTH, expand=True)