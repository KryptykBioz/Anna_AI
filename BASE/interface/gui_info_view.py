# Filename: BASE/interface/gui_info_view.py
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path
from BASE.interface.gui_themes import DarkTheme

class InfoView:
    """Displays README.md content from project root"""

    __slots__ = ('parent', 'project_root', 'readme_path', 'readme_text')
    
    def __init__(self, parent, project_root):
        self.parent = parent
        self.project_root = project_root
        self.readme_path = Path(project_root) / "README.md"
        
    def create_info_view(self):
        """Create the info view with README content"""
        info_frame = self.parent.info_view
        
        # Create header
        header_frame = tk.Frame(info_frame, bg=DarkTheme.BG_DARKER, height=50)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(
            header_frame,
            text="📖 Project Information",
            font=("Segoe UI", 14, "bold"),
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY
        )
        title_label.pack(side=tk.LEFT, padx=15, pady=10)
        
        # Add refresh button
        refresh_button = ttk.Button(
            header_frame,
            text="Refresh",
            command=self.refresh_readme,
            width=12
        )
        refresh_button.pack(side=tk.RIGHT, padx=15, pady=10)
        
        # Create scrolled text widget for README content
        text_frame = tk.Frame(info_frame, bg=DarkTheme.BG_DARK)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.readme_text = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY,
            insertbackground=DarkTheme.FG_PRIMARY,
            padx=15,
            pady=15,
            relief=tk.FLAT,
            borderwidth=0
        )
        self.readme_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure text tags for markdown-style formatting
        self.configure_text_tags()
        
        # Load README content
        self.load_readme()
        
    def configure_text_tags(self):
        """Configure text tags for basic markdown formatting"""
        # Headers
        self.readme_text.tag_configure(
            "h1",
            font=("Segoe UI", 18, "bold"),
            foreground=DarkTheme.ACCENT_GREEN,
            spacing1=15,
            spacing3=10
        )
        self.readme_text.tag_configure(
            "h2",
            font=("Segoe UI", 16, "bold"),
            foreground=DarkTheme.ACCENT_PURPLE,
            spacing1=12,
            spacing3=8
        )
        self.readme_text.tag_configure(
            "h3",
            font=("Segoe UI", 14, "bold"),
            foreground=DarkTheme.ACCENT_BLUE,
            spacing1=10,
            spacing3=6
        )
        
        # Code blocks
        self.readme_text.tag_configure(
            "code",
            font=("Consolas", 9),
            background=DarkTheme.BG_DARK,
            foreground=DarkTheme.ACCENT_GREEN,
            relief=tk.FLAT
        )
        
        # Bold text
        self.readme_text.tag_configure(
            "bold",
            font=("Segoe UI", 10, "bold"),
            foreground=DarkTheme.FG_PRIMARY
        )
        
        # Links
        self.readme_text.tag_configure(
            "link",
            foreground=DarkTheme.ACCENT_BLUE,
            underline=True
        )
        
        # List items
        self.readme_text.tag_configure(
            "list",
            lmargin1=30,
            lmargin2=30
        )
        
    def load_readme(self):
        """Load and display README.md content"""
        self.readme_text.config(state=tk.NORMAL)
        self.readme_text.delete(1.0, tk.END)
        
        try:
            if not self.readme_path.exists():
                self.show_error(f"README.md not found at:\n{self.readme_path}")
                return
            
            with open(self.readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.parse_and_display_markdown(content)
            
            # Add file info at the bottom
            self.readme_text.insert(tk.END, "\n\n" + "─" * 80 + "\n")
            self.readme_text.insert(
                tk.END,
                f"Loaded from: {self.readme_path}\n",
                "code"
            )
            
        except Exception as e:
            self.show_error(f"Error loading README.md:\n{str(e)}")
        
        self.readme_text.config(state=tk.DISABLED)
        
    def parse_and_display_markdown(self, content):
        """Parse and display markdown content with basic formatting"""
        lines = content.split('\n')
        in_code_block = False
        
        for line in lines:
            # Code blocks
            if line.startswith('```'):
                in_code_block = not in_code_block
                continue
            
            if in_code_block:
                self.readme_text.insert(tk.END, line + '\n', 'code')
                continue
            
            # Headers
            if line.startswith('# '):
                self.readme_text.insert(tk.END, line[2:] + '\n', 'h1')
            elif line.startswith('## '):
                self.readme_text.insert(tk.END, line[3:] + '\n', 'h2')
            elif line.startswith('### '):
                self.readme_text.insert(tk.END, line[4:] + '\n', 'h3')
            
            # List items
            elif line.startswith('- ') or line.startswith('* '):
                self.readme_text.insert(tk.END, '  • ' + line[2:] + '\n', 'list')
            elif line.startswith('  - ') or line.startswith('  * '):
                self.readme_text.insert(tk.END, '    ◦ ' + line[4:] + '\n', 'list')
            
            # Bold text (simplified - just **text**)
            elif '**' in line:
                self.insert_formatted_line(line)
            
            # Inline code
            elif '`' in line:
                self.insert_code_line(line)
            
            # Links (simplified)
            elif '[' in line and '](' in line:
                self.insert_link_line(line)
            
            # Regular text
            else:
                self.readme_text.insert(tk.END, line + '\n')
    
    def insert_formatted_line(self, line):
        """Insert line with bold formatting"""
        parts = line.split('**')
        for i, part in enumerate(parts):
            if i % 2 == 1:  # Odd indices are bold
                self.readme_text.insert(tk.END, part, 'bold')
            else:
                self.readme_text.insert(tk.END, part)
        self.readme_text.insert(tk.END, '\n')
    
    def insert_code_line(self, line):
        """Insert line with inline code formatting"""
        parts = line.split('`')
        for i, part in enumerate(parts):
            if i % 2 == 1:  # Odd indices are code
                self.readme_text.insert(tk.END, part, 'code')
            else:
                self.readme_text.insert(tk.END, part)
        self.readme_text.insert(tk.END, '\n')
    
    def insert_link_line(self, line):
        """Insert line with link formatting (simplified)"""
        import re
        # Simple pattern: [text](url)
        pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        
        last_end = 0
        for match in re.finditer(pattern, line):
            # Insert text before link
            self.readme_text.insert(tk.END, line[last_end:match.start()])
            # Insert link text
            self.readme_text.insert(tk.END, match.group(1), 'link')
            last_end = match.end()
        
        # Insert remaining text
        self.readme_text.insert(tk.END, line[last_end:] + '\n')
    
    def show_error(self, message):
        """Display error message in the text widget"""
        self.readme_text.insert(tk.END, "ERROR\n\n", 'h2')
        self.readme_text.insert(tk.END, message)
    
    def refresh_readme(self):
        """Refresh README content"""
        self.load_readme()
        self.parent.logger.system("README.md refreshed")