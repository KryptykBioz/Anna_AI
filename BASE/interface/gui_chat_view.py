# gui_chat_view.py - Theme-aware chat view with performance optimizations
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from personality.bot_info import agentname, username
from BASE.core.logger import MessageType, Logger

class ChatView:
    """Manages the Chat view with dynamic theme support and performance optimizations"""
    
    __slots__ = ('parent',)
    
    MESSAGE_TYPE_TO_TAG = {
        MessageType.USER: "user",
        MessageType.AGENT: "agent",
        MessageType.FAMILY: "family",
        MessageType.SYSTEM: "system",
        MessageType.ERROR: "error",
        MessageType.WARNING: "warning",
        MessageType.SUCCESS: "success",
        MessageType.DISCORD: "discord",
        MessageType.YOUTUBE: "youtube",
        MessageType.TWITCH: "twitch",
        MessageType.MINECRAFT: "minecraft",
        MessageType.LEAGUE: "league",
        MessageType.WARUDO: "warudo",
        MessageType.MEMORY: "memory",
        MessageType.THINKING: "thinking",
        MessageType.GOAL: "goal",
        MessageType.SPEECH: "speech",
        MessageType.AUDIO: "audio",
        MessageType.PROMPT: "prompt",
        MessageType.TOOL: "tool",
    }
    
    # PERFORMANCE: Maximum messages to keep in chat display (actual Text widget lines)
    MAX_CHAT_LINES = 600  # ~100 messages with formatting
    
    def __init__(self, parent):
        self.parent = parent
    
    def get_theme(self):
        return self.parent.ui_builder.theme_manager.get_theme()
    
    def get_font(self):
        theme_name = self.parent.ui_builder.theme_manager.theme_name
        return "Courier New" if theme_name == "Cyber" else "Segoe UI"
    
    def create_chat_view(self):
        """Create the Chat view with system panel and chat panel"""
        chat_paned = ttk.PanedWindow(self.parent.chat_view, orient=tk.HORIZONTAL)
        chat_paned.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(chat_paned)
        chat_paned.add(left_frame, weight=1)
        
        right_frame = ttk.Frame(chat_paned)
        chat_paned.add(right_frame, weight=1)
        
        self.create_system_panel(left_frame)
        self.create_chat_panel(right_frame)

    def create_system_panel(self, parent_frame):
        """Create system information panel"""
        theme = self.get_theme()
        font_name = self.get_font()
        
        title = "SYSTEM LOG" if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else "System Information"
        
        system_frame = ttk.LabelFrame(
            parent_frame, 
            text=title,
            style="Dark.TLabelframe"
        )
        system_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        text_frame = ttk.Frame(system_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', style='Vertical.TScrollbar')
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.parent.system_log = tk.Text(
            text_frame,
            height=15,
            width=100,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=(font_name, 9),
            bg=theme.BG_DARK,
            fg=theme.FG_PRIMARY,
            insertbackground=theme.ACCENT_GREEN if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else theme.FG_PRIMARY,
            selectbackground=theme.ACCENT_PURPLE,
            selectforeground=theme.ACCENT_GREEN if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else theme.FG_PRIMARY,
            borderwidth=2 if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else 0,
            relief='solid' if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else 'flat',
            highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        self.parent.system_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.parent.system_log.yview)
        self.parent.flush_pending_log_messages()

    def create_chat_panel(self, parent_frame):
        """Create chat display and input panel"""
        theme = self.get_theme()
        font_name = self.get_font()
        
        if self.parent.ui_builder.theme_manager.theme_name == "Cyber":
            title = f"CHAT // {agentname.upper()}"
        else:
            title = f"Chat with {agentname}"
        
        chat_frame = ttk.LabelFrame(
            parent_frame, 
            text=title,
            style="Accent.TLabelframe" if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else "Dark.TLabelframe"
        )
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        text_frame = ttk.Frame(chat_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', style='Vertical.TScrollbar')
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.parent.chat_display = tk.Text(
            text_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=(font_name, 10),
            bg=theme.BG_DARK,
            fg=theme.FG_PRIMARY,
            insertbackground=theme.ACCENT_GREEN if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else theme.FG_PRIMARY,
            selectbackground=theme.ACCENT_PURPLE,
            selectforeground=theme.ACCENT_GREEN if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else theme.FG_PRIMARY,
            borderwidth=2 if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else 0,
            relief='solid' if self.parent.ui_builder.theme_manager.theme_name == "Cyber" else 'flat',
            highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        self.parent.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.parent.chat_display.yview)
        
        self._configure_chat_display_tags()
        self.create_input_panel(parent_frame)

    def _configure_chat_display_tags(self):
        """Configure color tags with current theme colors"""
        logger = self.parent.logger
        font_name = self.get_font()
        
        font_configs = {
            "user": (font_name, 10, "bold"),
            "agent": (font_name, 10, "bold"),
            "family": (font_name, 10, "bold"),
            "system": (font_name, 9, "italic"),
            "error": (font_name, 10, "bold"),
            "warning": (font_name, 10, "bold"),
            "success": (font_name, 10, "bold"),
            "voice": (font_name, 10, "italic"),
            "discord": (font_name, 10, "bold"),
            "youtube": (font_name, 10, "bold"),
            "twitch": (font_name, 10, "bold"),
            "minecraft": (font_name, 10, "bold"),
            "league": (font_name, 10, "bold"),
            "warudo": (font_name, 10, "bold"),
            "memory": (font_name, 9, "italic"),
            "thinking": (font_name, 9, "italic"),
            "goal": (font_name, 10, "bold"),
            "speech": (font_name, 9, "italic"),
            "audio": (font_name, 9, "italic"),
            "prompt": (font_name, 9, "italic"),
            "tool": (font_name, 9, "italic"),
        }
        
        for tag, font in font_configs.items():
            msg_type = self._convert_legacy_type(tag)
            color = logger._get_gui_color(msg_type)
            self.parent.chat_display.tag_configure(tag, foreground=color, font=font)

    def create_input_panel(self, parent_frame):
        """Create input panel with text box and buttons"""
        theme = self.get_theme()
        font_name = self.get_font()
        is_cyber = self.parent.ui_builder.theme_manager.theme_name == "Cyber"
        
        input_frame = ttk.Frame(parent_frame)
        input_frame.pack(fill=tk.X, pady=(5, 0))
        
        button_frame = ttk.Frame(input_frame)
        button_frame.pack(side=tk.RIGHT, padx=(5, 0))
        
        button_config = {
            'width': 10,
            'font': (font_name, 10, "bold" if is_cyber else "normal"),
            'cursor': 'hand2',
            'relief': 'solid' if is_cyber else 'flat',
            'borderwidth': 2 if is_cyber else 0,
            'highlightthickness': 2 if is_cyber else 0,
        }
        
        self.parent.send_button = tk.Button(
            button_frame,
            text="[SEND]" if is_cyber else "Send",
            bg=theme.ACCENT_GREEN,
            fg=theme.BG_DARKER if is_cyber else 'white',
            activebackground=theme.ACCENT_PURPLE if is_cyber else theme.ACCENT_GREEN,
            activeforeground=theme.ACCENT_GREEN if is_cyber else 'white',
            highlightbackground=theme.BORDER,
            highlightcolor=theme.ACCENT_GREEN,
            command=lambda: self.parent.ui_builder.chat_view_instance.send_message(),
            **button_config
        )
        self.parent.send_button.pack(fill=tk.X, pady=(0, 5))
        
        stop_button = tk.Button(
            button_frame,
            text="[STOP]" if is_cyber else "Stop",
            bg=theme.ERROR_COLOR,
            fg='white',
            activebackground=theme.ACCENT_PURPLE if is_cyber else theme.ERROR_COLOR,
            activeforeground=theme.ERROR_COLOR if is_cyber else 'white',
            highlightbackground=theme.BORDER,
            highlightcolor=theme.ERROR_COLOR,
            command=self.parent.message_processor.stop_speaking,
            **button_config
        )
        stop_button.pack(fill=tk.X)
        
        self.parent.processing_label = tk.Label(
            button_frame,
            text="",
            font=(font_name, 7),
            foreground=theme.ACCENT_PURPLE,
            background=theme.BG_DARKER,
            wraplength=85 if is_cyber else 75
        )
        self.parent.processing_label.pack(fill=tk.X, pady=(3, 0))
        
        text_container = ttk.Frame(input_frame)
        text_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.parent.input_text = tk.Text(
            text_container,
            height=4,
            wrap=tk.WORD,
            font=(font_name, 10),
            bg=theme.BG_LIGHTER,
            fg=theme.FG_PRIMARY,
            insertbackground=theme.ACCENT_GREEN if is_cyber else theme.FG_PRIMARY,
            selectbackground=theme.ACCENT_PURPLE,
            selectforeground=theme.ACCENT_GREEN if is_cyber else theme.FG_PRIMARY,
            borderwidth=2 if is_cyber else 0,
            highlightthickness=2 if is_cyber else 0,
            highlightbackground=theme.BORDER,
            highlightcolor=theme.ACCENT_GREEN if is_cyber else theme.ACCENT_PURPLE,
            relief='solid' if is_cyber else 'flat'
        )
        self.parent.input_text.pack(fill=tk.BOTH, expand=True)
        
        self.parent.input_text.bind("<Control-Return>", lambda e: self.send_message())
        self.parent.input_text.bind("<Return>", self.handle_return)

    def handle_return(self, event):
        return None if event.state & 0x1 else (self.send_message(), "break")[1]

    def send_message(self):
        """Filter user input BEFORE display and queueing"""
        import time
        msg = self.parent.input_text.get("1.0", tk.END).strip()
        if not msg:
            return
        
        self.parent.input_text.delete("1.0", tk.END)
        
        filtered_msg = msg
        if getattr(self.parent.controls, 'ENABLE_CONTENT_FILTER', True):
            cleaned, filtered, reason = self.parent.ai_core.content_filter.filter_incoming(
                msg,
                log_callback=self.parent.logger.system
            )
            if filtered:
                self.parent.logger.system(f"[Filter Input] {reason}")
            filtered_msg = cleaned
        
        self.add_message(username, filtered_msg, MessageType.USER)
        
        self.parent.input_queue.put(filtered_msg)
        self.parent.last_interaction = time.time()

    def _get_actual_line_count(self):
        try:
            last_line = self.parent.chat_display.index("end-1c").split('.')[0]
            return int(last_line)
        except Exception as e:
            if hasattr(self.parent, 'logger'):
                self.parent.logger.warning(f"Error getting chat line count: {e}")
            return 0

    def _trim_chat_display(self):
        try:
            actual_lines = self._get_actual_line_count()
            if actual_lines <= self.MAX_CHAT_LINES:
                return
            lines_to_remove = actual_lines - self.MAX_CHAT_LINES
            self.parent.chat_display.config(state=tk.NORMAL)
            self.parent.chat_display.delete("1.0", f"{lines_to_remove + 1}.0")
            self.parent.chat_display.config(state=tk.DISABLED)
        except Exception as e:
            if hasattr(self.parent, 'logger'):
                self.parent.logger.warning(f"Error trimming chat display: {e}")

    def add_message(self, sender, message, msg_type=MessageType.USER):
        """Add a message to the chat display with performance optimizations"""
        if isinstance(msg_type, str):
            msg_type = self._convert_legacy_type(msg_type)
        
        if msg_type == MessageType.AGENT:
            self.parent.logger.system(f"[ChatView] Displaying agent message: {message[:60]}...")
        
        self._trim_chat_display()
        
        self.parent.chat_display.config(state=tk.NORMAL)
        
        ts = datetime.now().strftime("%H:%M:%S")
        self.parent.chat_display.insert(tk.END, f"[{ts}] ", "system")
        
        tag = self.MESSAGE_TYPE_TO_TAG.get(msg_type, "system")
        is_cyber = self.parent.ui_builder.theme_manager.theme_name == "Cyber"
        
        if msg_type == MessageType.SYSTEM:
            self.parent.chat_display.insert(tk.END, f"{message}\n", tag)
        elif msg_type in (MessageType.ERROR, MessageType.WARNING):
            self.parent.chat_display.insert(tk.END, f"{sender}: ", tag)
            self.parent.chat_display.insert(tk.END, f"{message}\n", tag)
        elif msg_type == MessageType.USER:
            prefix = ">> " if is_cyber else ""
            self.parent.chat_display.insert(tk.END, f"{prefix}{sender}: ", tag)
            self.parent.chat_display.insert(tk.END, f"{message}\n\n")
        elif msg_type == MessageType.AGENT or MessageType.FAMILY:
            prefix = "<< " if is_cyber else ""
            self.parent.chat_display.insert(tk.END, f"{prefix}{sender}: ", tag)
            self.parent.chat_display.insert(tk.END, f"{message}\n\n")
        else:
            self.parent.chat_display.insert(tk.END, f"{sender}: ", tag)
            self.parent.chat_display.insert(tk.END, f"{message}\n\n")
        
        self.parent.chat_display.see(tk.END)
        self.parent.chat_display.config(state=tk.DISABLED)

    @staticmethod
    def _get_tag_for_type(msg_type):
        from BASE.core.logger import MessageType
        type_map = {
            MessageType.USER: "user",
            MessageType.AGENT: "agent",
            MessageType.FAMILY: "family",
            MessageType.SYSTEM: "system",
            MessageType.ERROR: "error",
            MessageType.SPEECH: "user",
            MessageType.TOOL: "tool",
            MessageType.MEMORY: "memory",
            MessageType.DISCORD: "discord",
            MessageType.YOUTUBE: "youtube",
            MessageType.TWITCH: "twitch",
            MessageType.WARUDO: "warudo"
        }
        return type_map.get(msg_type, "system")

    @staticmethod
    def add_chat_message(gui_instance, sender, message, msg_type, original_timestamp=None):
        """Add message to chat display with timestamp"""
        gui_instance.chat_display.config(state="normal")
        
        if original_timestamp:
            display_timestamp = original_timestamp
        else:
            from datetime import datetime
            display_timestamp = datetime.now().strftime("%I:%M:%S %p")
        
        gui_instance.chat_display.insert("end", f"[{display_timestamp}] ", "system")
        
        from BASE.core.logger import MessageType
        
        if msg_type == MessageType.SYSTEM:
            gui_instance.chat_display.insert("end", f"{message}\n", "system")
        elif msg_type == MessageType.ERROR:
            gui_instance.chat_display.insert("end", f"{sender}: {message}\n", "error")
        else:
            tag = ChatView._get_tag_for_type(msg_type)
            gui_instance.chat_display.insert("end", f"{sender}: ", tag)
            gui_instance.chat_display.insert("end", f"{message}\n\n")
        
        gui_instance.chat_display.see("end")
        gui_instance.chat_display.config(state="disabled")
        
    @staticmethod
    def _convert_legacy_type(legacy_type):
        legacy_map = {
            "user": MessageType.USER,
            "agent": MessageType.AGENT,
            "family": MessageType.FAMILY,
            "system": MessageType.SYSTEM,
            "error": MessageType.ERROR,
            "warning": MessageType.WARNING,
            "success": MessageType.SUCCESS,
            "voice_input": MessageType.USER,
            "voice": MessageType.USER,
            "discord": MessageType.DISCORD,
            "youtube": MessageType.YOUTUBE,
            "twitch": MessageType.TWITCH,
            "minecraft": MessageType.MINECRAFT,
            "league": MessageType.LEAGUE,
            "warudo": MessageType.WARUDO,
            "memory": MessageType.MEMORY,
            "thinking": MessageType.THINKING,
            "goal": MessageType.GOAL,
            "speech": MessageType.SPEECH,
            "audio": MessageType.AUDIO,
            "prompt": MessageType.PROMPT,
            "tool": MessageType.TOOL,
        }
        return legacy_map.get(legacy_type, MessageType.SYSTEM)
        
    def clear_chat(self):
        self.parent.chat_display.config(state=tk.NORMAL)
        self.parent.chat_display.delete("1.0", tk.END)
        self.parent.chat_display.config(state=tk.DISABLED)
        
        is_cyber = self.parent.ui_builder.theme_manager.theme_name == "Cyber"
        message = "Chat cleared" if is_cyber else "Chat cleared"
        self.parent.logger.system(message)