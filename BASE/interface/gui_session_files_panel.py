# Filename: BASE/interface/gui_session_files_panel.py
"""
Session Files Panel for GUI
Allows users to upload/manage temporary reference files
FIXED: Proper theme import and error handling
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Try to import theme, provide fallback if not available
try:
    from BASE.interface.gui_themes import DarkTheme
except ImportError:
    # Fallback theme if not available
    class DarkTheme:
        BG_DARKER = "#1e1e1e"
        BG_DARK = "#2d2d2d"
        FG_PRIMARY = "#ffffff"
        FG_SECONDARY = "#b0b0b0"
        FG_MUTED = "#808080"
        ACCENT_RED = "#ff6b6b"
        ACCENT_GREEN = "#51cf66"
        ACCENT_PURPLE = "#7c3aed"
        BUTTON_BG = "#3d3d3d"
        BUTTON_HOVER = "#4d4d4d"
        BORDER = "#404040"


class SessionFilesPanel:
    """Manages session file upload and display"""

    __slots__ = ('parent', 'ai_core', 'logger', 'file_items', 'canvas', 'scrollbar',
                'scrollable_frame', 'canvas_window')

    def __init__(self, parent, ai_core, logger):
        self.parent = parent
        self.ai_core = ai_core
        self.logger = logger
        self.file_items = {}  # file_id -> frame mapping
    
    def create_panel(self, parent_frame):
        """Create session files management panel"""
        
        # Main container
        main_frame = ttk.LabelFrame(
            parent_frame,
            text="Session Files (Temporary Reference)",
            style="Dark.TLabelframe"
        )
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Info label
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        info_label = tk.Label(
            info_frame,
            text="Upload code or documentation files for AI to reference during this session only.\n"
                "Files are NOT saved to persistent memory and will be cleared when you close the app.",
            font=("Segoe UI", 9),
            foreground=DarkTheme.FG_SECONDARY,
            background=DarkTheme.BG_DARKER,
            justify=tk.LEFT,
            wraplength=700
        )
        info_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            button_frame,
            text="📁 Upload File",
            command=self.upload_file,
            width=15
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            button_frame,
            text="Clear All",
            command=self.clear_all_files,
            width=15
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            button_frame,
            text="Refresh",
            command=self.refresh_file_list,
            width=15
        ).pack(side=tk.LEFT, padx=2)
        
        # Files list container
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas for scrolling
        self.canvas = tk.Canvas(
            list_frame,
            bg=DarkTheme.BG_DARKER,
            highlightthickness=0,
            height=400
        )
        self.scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        def update_scroll_region(event=None):
            self.canvas.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            bbox = self.canvas.bbox("all")
            canvas_height = self.canvas.winfo_height()
            
            if bbox and bbox[3] > canvas_height:
                self.scrollbar.pack(side="right", fill="y")
            else:
                self.scrollbar.pack_forget()
        
        def configure_canvas_width(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)
            update_scroll_region()
        
        self.scrollable_frame.bind("<Configure>", update_scroll_region)
        self.canvas.bind("<Configure>", configure_canvas_width)
        
        # Bind mousewheel - only scroll if content overflows
        def _on_mousewheel(event):
            bbox = self.canvas.bbox("all")
            canvas_height = self.canvas.winfo_height()
            if bbox and bbox[3] > canvas_height:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def _bind_mousewheel(event):
            bbox = self.canvas.bbox("all")
            canvas_height = self.canvas.winfo_height()
            if bbox and bbox[3] > canvas_height:
                self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")
        
        self.canvas.bind("<Enter>", _bind_mousewheel)
        self.canvas.bind("<Leave>", _unbind_mousewheel)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Initial load
        self.refresh_file_list()
    
    def upload_file(self):
        """Open file dialog and upload selected file"""
        filetypes = [
            ("All Supported", "*.py *.js *.ts *.java *.cpp *.c *.cs *.go *.rs *.md *.txt *.json *.xml"),
            ("Python", "*.py"),
            ("JavaScript/TypeScript", "*.js *.ts"),
            ("Java", "*.java"),
            ("C/C++", "*.c *.cpp *.h *.hpp"),
            ("Markdown", "*.md"),
            ("Text", "*.txt"),
            ("All Files", "*.*")
        ]
        
        filepath_str = filedialog.askopenfilename(
            title="Select File to Upload",
            filetypes=filetypes
        )
        
        if not filepath_str:
            return
        
        try:
            file_path = Path(filepath_str)
            
            # Check file size
            size_mb = file_path.stat().st_size / (1024 * 1024)
            
            if size_mb > 1.0:
                if not messagebox.askyesno(
                    "Large File",
                    f"File is {size_mb:.2f}MB. This may use significant context.\n"
                    f"Continue?"
                ):
                    return
            
            # Load file
            self.logger.system(f"Loading session file: {file_path.name}...")
            
            result = self.ai_core.load_session_file(file_path)
            
            if result and result.get('success'):
                file_info = result.get('file_data', {})
                
                messagebox.showinfo(
                    "File Loaded",
                    f"Successfully loaded: {file_path.name}\n\n"
                    f"Type: {file_info.get('file_type', 'unknown')}\n"
                    f"Lines: {file_info.get('line_count', 0)}\n"
                    f"Sections: {len(file_info.get('sections', []))}\n"
                    f"Size: {size_mb:.1f}MB"
                )
                self.refresh_file_list()
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'Failed to load file'
                messagebox.showerror(
                    "Upload Failed",
                    f"Failed to load file:\n{error_msg}"
                )
        
        except Exception as e:
            self.logger.error(f"Error uploading file: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Error uploading file:\n{str(e)}")
    
    def clear_all_files(self):
        """Clear all session files"""
        if not self.file_items:
            messagebox.showinfo("No Files", "No session files to clear")
            return
        
        if messagebox.askyesno(
            "Clear All Files",
            f"Remove all {len(self.file_items)} session file(s)?\n"
            f"This cannot be undone."
        ):
            self.ai_core.clear_all_session_files()
            self.refresh_file_list()
    
    def refresh_file_list(self):
        """Refresh the displayed file list"""
        # Clear existing items
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.file_items.clear()
        
        files = self.ai_core.list_session_files()
        
        if not files:
            # Show empty state
            empty_label = tk.Label(
                self.scrollable_frame,
                text="No session files loaded\n\nClick 'Upload File' to add reference files",
                font=("Segoe UI", 10),
                foreground=DarkTheme.FG_MUTED,
                background=DarkTheme.BG_DARKER,
                pady=20
            )
            empty_label.pack(fill=tk.BOTH, expand=True)
            return
        
        # Display each file
        for file_info in files:
            self.create_file_item(file_info)
    
    def create_file_item(self, file_info: dict):
        """Create a visual item for a file"""
        file_id = file_info['file_id']
        
        # Container frame
        item_frame = ttk.Frame(self.scrollable_frame)
        item_frame.pack(fill=tk.X, padx=2, pady=2)
        
        # Content frame with background
        content_frame = tk.Frame(
            item_frame,
            bg=DarkTheme.BG_DARK,
            relief=tk.RAISED,
            borderwidth=1
        )
        content_frame.pack(fill=tk.X, padx=2, pady=2)
        
        # File icon and name
        header_frame = tk.Frame(content_frame, bg=DarkTheme.BG_DARK)
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Type emoji
        filename = file_info.get('filename', 'unknown')
        file_ext = Path(filename).suffix.lstrip('.').lower() if filename else 'txt'
        
        type_emoji = {
            'py': '🐍', 'js': '📜', 'ts': '📜', 'java': '☕',
            'cpp': '⚙️', 'c': '⚙️', 'h': '⚙️', 'hpp': '⚙️',
            'cs': '🎮', 'go': '🐹', 'rs': '🦀', 'md': '📝',
            'txt': '📄', 'json': '🔧', 'xml': '🔧',
            'yaml': '🔧', 'yml': '🔧'
        }.get(file_ext, '📄')
        
        tk.Label(
            header_frame,
            text=type_emoji,
            font=("Segoe UI", 12),
            bg=DarkTheme.BG_DARK,
            foreground=DarkTheme.FG_PRIMARY
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        # Filename
        tk.Label(
            header_frame,
            text=filename,
            font=("Segoe UI", 10, "bold"),
            bg=DarkTheme.BG_DARK,
            foreground=DarkTheme.FG_PRIMARY,
            anchor="w"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Remove button
        remove_btn = tk.Button(
            header_frame,
            text="✕",
            font=("Segoe UI", 10, "bold"),
            bg=DarkTheme.ACCENT_RED,
            fg="white",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda fid=file_id: self.remove_file(fid)
        )
        remove_btn.pack(side=tk.RIGHT)
        
        # File details
        details_frame = tk.Frame(content_frame, bg=DarkTheme.BG_DARK)
        details_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        file_type = file_info.get('file_type', 'unknown')
        line_count = file_info.get('line_count', 0)
        sections = file_info.get('sections', 0)
        size_kb = file_info.get('size_kb', 0)
        
        details_text = (
            f"Type: {file_type} | "
            f"Lines: {line_count} | "
            f"Sections: {sections} | "
            f"Size: {size_kb:.1f}KB"
        )
        
        tk.Label(
            details_frame,
            text=details_text,
            font=("Segoe UI", 8),
            bg=DarkTheme.BG_DARK,
            foreground=DarkTheme.FG_MUTED,
            anchor="w"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.file_items[file_id] = item_frame
    
    def remove_file(self, file_id: str):
        """Remove a specific file"""
        if messagebox.askyesno(
            "Remove File",
            "Remove this file from session?\nThe AI will no longer be able to reference it."
        ):
            self.ai_core.unload_session_file(file_id)
            self.refresh_file_list()
    
    def get_stats(self) -> dict:
        """Get current session files statistics"""
        files = self.ai_core.list_session_files()
        total_size = sum(f.get('size_kb', 0) for f in files)
        
        return {
            'file_count': len(files),
            'total_size_kb': total_size,
            'types': list(set(f.get('file_type', 'N/A') for f in files))
        }