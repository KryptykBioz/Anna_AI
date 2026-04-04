# Filename: BASE/core/logger.py
"""
Unified logging system for Anna AI
Converted to singleton pattern with proper config reference handling
"""

from enum import Enum
from typing import Optional, Callable, Dict
import sys
from datetime import datetime

class LogLevel(Enum):
    """Log message severity levels"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

class MessageType(Enum):
    """Message categorization for coloring/formatting"""
    SYSTEM = "system"
    PROMPT = "prompt"
    REACTIVE = "reactive"
    REFLECTIVE = "reflective"
    PROACTIVE = "proactive"
    RESPONSIVE = "responsive"
    ACTION = "action"
    TOOL = "tool"
    TOOL_STATUS = "tool_status"
    USER = "user"
    AGENT = "agent"
    FAMILY = "family"
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    MEMORY = "memory"
    THINKING = "thinking"
    GOAL = "goal"
    VISION = "vision"
    LIVECHAT = "livechat"
    DISCORD = "discord"
    YOUTUBE = "youtube"
    TWITCH = "twitch"
    MINECRAFT = "minecraft"
    LEAGUE = "league"
    WARUDO = "warudo"
    SPEECH = "speech"
    AUDIO = "audio"

class Logger:
    """
    Unified logger with centralized filtering
    Single source of truth for all logging decisions
    Singleton pattern - always returns the same instance
    """
    
    _instance = None
    _initialized = False
    
    __slots__ = (
        'name', 'min_level', 'enable_console', 'enable_timestamps',
        'gui_callback', 'gui_colors', 'config'
    )
    
    DEFAULT_GUI_COLORS = {
        MessageType.SYSTEM: "#6c757d",      
        MessageType.USER: "#27da03",        
        MessageType.PROMPT: "#7300ff",
        MessageType.REACTIVE: "#7300ff",
        MessageType.REFLECTIVE: "#943dff",
        MessageType.PROACTIVE: "#bf8dff",
        MessageType.RESPONSIVE: "#dcc2fd",
        MessageType.THINKING: "#f403e8",
        MessageType.ACTION: "#f4a803",
        MessageType.GOAL: "#f403e8",       
        MessageType.MEMORY: "#e6ff07",      
        MessageType.AGENT: "#bb86fc",
        MessageType.FAMILY: "#bb86fc",         
        MessageType.SPEECH: "#6f00ff",
        MessageType.LIVECHAT: "#00c3ff",        
        MessageType.DISCORD: "#00c3ff",  
        MessageType.YOUTUBE: "#00c3ff",    
        MessageType.TWITCH: "#00c3ff",     
        MessageType.MINECRAFT: "#001bb4",  
        MessageType.LEAGUE: "#001bb4",    
        MessageType.TOOL: "#b5ff07",  
        MessageType.VISION: "#ffc107",        
        MessageType.WARUDO: "#ffc107",     
        MessageType.AUDIO: "#ffc107",       
        MessageType.SUCCESS: "#00ffaa",     
        MessageType.ERROR: "#aa001f",      
        MessageType.WARNING: "#ff4800",    
    }
    
    def __new__(cls, name: str = "AnnaAI", *args, **kwargs):
        """Singleton pattern: always return the same instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        name: str = "AnnaAI",
        min_level: LogLevel = LogLevel.INFO,
        enable_console: bool = True,
        enable_timestamps: bool = True,
        gui_callback: Optional[Callable[[str, str, str], None]] = None,
        config: Optional['Config'] = None
    ):
        """
        Initialize logger (only once due to singleton)
        
        Args:
            name: Logger instance name (ignored after first init)
            min_level: Minimum log level to display
            enable_console: Enable console output (plain text)
            enable_timestamps: Include timestamps in messages
            gui_callback: Callback for GUI logging (message, msg_type, color)
            config: Config singleton instance with logging control variables
        """
        # Skip initialization if already done
        if Logger._initialized:
            # Update config reference if provided (allows dynamic config updates)
            if config is not None:
                self.config = config
            # Update GUI callback if provided
            if gui_callback is not None:
                self.gui_callback = gui_callback
            return
        
        Logger._initialized = True
        
        self.name = name
        self.min_level = min_level
        self.enable_console = enable_console
        self.enable_timestamps = enable_timestamps
        self.gui_callback = gui_callback
        self.gui_colors = self.DEFAULT_GUI_COLORS.copy()
        self.config = config  # Store reference to Config singleton
        
        # Log singleton initialization
        print(f"[Logger] Singleton instance created: {id(self)}")
        if config:
            print(f"[Logger] Config reference set: {id(config)}")
    
    def set_config(self, config: 'Config'):
        """
        Set or update config reference
        Safe to call anytime to update the config reference
        """
        self.config = config
        print(f"[Logger:{self.name}] Config reference {id(config)}")
    
    def set_gui_callback(self, callback: Callable[[str, str, str], None]):
        """Set or update GUI logging callback"""
        self.gui_callback = callback
    
    def set_gui_color(self, msg_type: MessageType, color: str):
        """Override GUI color for a specific message type"""
        self.gui_colors[msg_type] = color
    
    def set_min_level(self, level: LogLevel):
        """Change minimum log level"""
        self.min_level = level
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on level"""
        return level.value >= self.min_level.value
    
    def _check_category_enabled(self, msg_type: MessageType) -> bool:
        """
        Check if message category is enabled in config
        Direct attribute check on singleton Config instance
        """
        if not self.config:
            # No config = log everything (safe default during initialization)
            return True
        
        # Direct attribute access on singleton Config to get current value
        try:
            if msg_type in (MessageType.TOOL, MessageType.TOOL_STATUS, 
                            MessageType.VISION, MessageType.MEMORY, 
                            MessageType.GOAL, MessageType.SPEECH, 
                            MessageType.AUDIO, MessageType.WARUDO, 
                            MessageType.MINECRAFT, MessageType.LEAGUE
                        ):
                return self.config.LOG_TOOL_EXECUTION
            
            # elif msg_type == MessageType.PROMPT:
            #     return self.config.LOG_PROMPT_CONSTRUCTION
            
# MessageType.REACTIVE, 
# MessageType.REFLECTIVE, MessageType.PROACTIVE,
# MessageType.RESPONSIVE

            elif msg_type == MessageType.REACTIVE:
                return self.config.LOG_REACTIVE_PROMPT
            
            elif msg_type == MessageType.REFLECTIVE:    
                return self.config.LOG_REFLECTIVE_PROMPT
            
            elif msg_type == MessageType.PROACTIVE:
                return self.config.LOG_PROACTIVE_PROMPT
            
            elif msg_type == MessageType.RESPONSIVE:
                return self.config.LOG_RESPONSIVE_PROMPT
            
            elif msg_type == MessageType.ACTION:
                return self.config.LOG_ACTION_PROMPT
            
            elif msg_type in (MessageType.AGENT, MessageType.THINKING):
                return self.config.LOG_RESPONSE_PROCESSING
            
            elif msg_type in (MessageType.LIVECHAT, MessageType.DISCORD, 
                            MessageType.YOUTUBE, MessageType.TWITCH):
                return self.config.SHOW_CHAT
            
            elif msg_type in (MessageType.SYSTEM, MessageType.SUCCESS):
                return self.config.LOG_SYSTEM_INFORMATION
            
            elif msg_type in (MessageType.ERROR, MessageType.WARNING, MessageType.USER, MessageType.FAMILY):
                # Always log errors, warnings, and user input
                return True
            
            # Default: respect LOG_SYSTEM_INFORMATION
            return self.config.LOG_SYSTEM_INFORMATION
            
        except AttributeError:
            # Config missing attribute - default to True
            return True
    
    def _get_gui_color(self, msg_type: MessageType) -> str:
        """Get GUI color for message type"""
        return self.gui_colors.get(msg_type, self.gui_colors[MessageType.SYSTEM])
    
    def log(
        self,
        message: str,
        msg_type: MessageType = MessageType.SYSTEM,
        level: LogLevel = LogLevel.INFO,
        prefix: Optional[str] = None
    ):
        """Main logging method with centralized filtering"""
        
        if not self._should_log(level):
            return
        
        # CRITICAL: Check if category is enabled BEFORE doing any work
        if not self._check_category_enabled(msg_type):
            return  # Skip entirely - no console, no GUI, no callbacks
        
        # Auto-generate prefix if not provided
        if prefix is None:
            prefix = f"[{msg_type.value.upper()}]"
        
        # Console output (plain text, no colors)
        if self.enable_console:
            timestamp = datetime.now().strftime("%H:%M:%S") if self.enable_timestamps else ""
            parts = [f"[{timestamp}]"] if timestamp else []
            parts.extend([prefix, message])
            formatted = " ".join(parts)
            
            # Route to stderr for errors/warnings
            if level in (LogLevel.ERROR, LogLevel.CRITICAL):
                print(formatted, file=sys.stderr, flush=True)
            else:
                print(formatted, flush=True)
        
        # GUI output with color information and formatting
        if self.gui_callback:
            color = self._get_gui_color(msg_type)
            message = f"\n{'-'*20}\n{message}\n{'-'*20}\n"
            # Pass raw message, type string, and color to GUI
            self.gui_callback(message, msg_type.value, color)

    def system(self, message: str):
        """Log system message"""
        self.log(message, MessageType.SYSTEM, LogLevel.INFO, prefix="[System]")
    
    def prompt(self, message: str):
        """Log AI prompt/query"""
        self.log(message, MessageType.PROMPT, LogLevel.INFO, prefix="[Prompt]")

    def reactive(self, message: str):
        """Log AI prompt/query"""
        self.log(message, MessageType.REACTIVE, LogLevel.INFO, prefix="[Reactive]")

    def reflective(self, message: str):
        """Log AI prompt/query"""
        self.log(message, MessageType.REFLECTIVE, LogLevel.INFO, prefix="[Reflective]")

    def proactive(self, message: str):
        """Log AI prompt/query"""
        self.log(message, MessageType.PROACTIVE, LogLevel.INFO, prefix="[Proactive]")

    def responsive(self, message: str):
        """Log AI prompt/query"""
        self.log(message, MessageType.RESPONSIVE, LogLevel.INFO, prefix="[Responsive]")
    
    def thinking(self, message: str):
        """Log thinking model message"""
        self.log(message, MessageType.THINKING, LogLevel.INFO, prefix="[Thinking]")

    def action(self, message: str):
        """Log action model message"""
        self.log(message, MessageType.ACTION, LogLevel.INFO, prefix="[Action]")
    
    def tool(self, message: str):
        """Log tool execution"""
        self.log(message, MessageType.TOOL, LogLevel.INFO, prefix="[Tool]")
    
    def error(self, message: str):
        """Log error message"""
        self.log(message, MessageType.ERROR, LogLevel.ERROR)
    
    def warning(self, message: str):
        """Log warning message"""
        self.log(message, MessageType.WARNING, LogLevel.WARNING, prefix="[Warning]")
    
    def success(self, message: str):
        """Log success message"""
        self.log(message, MessageType.SUCCESS, LogLevel.INFO)
    
    def debug(self, message: str, msg_type: MessageType = MessageType.SYSTEM):
        """Log debug message"""
        self.log(message, msg_type, LogLevel.DEBUG, prefix = "[Debug]")
    
    def user_input(self, username: str, message: str):
        """Log user input"""
        self.log(f"{username}: {message}", MessageType.USER, LogLevel.INFO, prefix="[User]")
    
    def agent_response(self, agentname: str, message: str):
        """Log agent response"""
        self.log(f"{agentname}: {message}", MessageType.AGENT, LogLevel.INFO, prefix="")
    
    def memory(self, message: str):
        """Log memory system message"""
        self.log(message, MessageType.MEMORY, LogLevel.INFO, prefix="[Memory]")
    
    def goal(self, message: str):
        """Log goal-related message"""
        self.log(message, MessageType.GOAL, LogLevel.INFO, prefix="[GOAL]")
    
    def speech(self, message: str):
        """Log speech/TTS message"""
        self.log(message, MessageType.SPEECH, LogLevel.INFO, prefix="[SPEECH]")
    
    def audio(self, message: str):
        """Log audio system message"""
        self.log(message, MessageType.AUDIO, LogLevel.INFO, prefix="[Audio]")

    def livechat(self, message: str):
        """Log livechat-related message"""
        self.log(message, MessageType.LIVECHAT, LogLevel.INFO, prefix="[LiveChat]")

    def discord(self, message: str):
        """Log Discord-related message"""
        self.log(message, MessageType.DISCORD, LogLevel.INFO, prefix="[Discord]")
    
    def youtube(self, message: str):
        """Log YouTube-related message"""
        self.log(message, MessageType.YOUTUBE, LogLevel.INFO, prefix="[YouTube]")
    
    def twitch(self, message: str):
        """Log Twitch-related message"""
        self.log(message, MessageType.TWITCH, LogLevel.INFO, prefix="[Twitch]")
    
    def minecraft(self, message: str):
        """Log Minecraft-related message"""
        self.log(message, MessageType.MINECRAFT, LogLevel.INFO, prefix="[Minecraft]")
    
    def league(self, message: str):
        """Log League-related message"""
        self.log(message, MessageType.LEAGUE, LogLevel.INFO, prefix="[League]")
    
    def warudo(self, message: str):
        """Log Warudo-related message"""
        self.log(message, MessageType.WARUDO, LogLevel.INFO, prefix="[Warudo]")


# Global logger helper functions
def get_logger() -> Logger:
    """
    Get the singleton logger instance
    Always returns the same instance
    """
    return Logger()


def set_global_logger_config(config):
    """
    Update the singleton logger's config reference
    Useful for ensuring logger has access to the Config singleton
    """
    logger = Logger()
    logger.set_config(config)