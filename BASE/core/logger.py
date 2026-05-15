# Filename: BASE/core/logger.py
from enum import Enum
from typing import Optional, Callable
import sys
from datetime import datetime


class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class MessageType(Enum):
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
    JUDGE = "judge"
    FILTER = "filter"


class Logger:
    _instance = None
    _initialized = False

    __slots__ = (
        'name', 'min_level', 'enable_console', 'enable_timestamps',
        'gui_callback', 'gui_colors', 'config', '_thought_buffer_callback'
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
        MessageType.JUDGE: "#ff9900",
        MessageType.FILTER: "#ff9900",
    }

    # Message types forwarded to the thought buffer
    _BUFFER_TYPES = frozenset((
        MessageType.SYSTEM,
        MessageType.SUCCESS,
        MessageType.WARNING,
        MessageType.ERROR,
        MessageType.TOOL,
        MessageType.TOOL_STATUS,
        MessageType.ACTION,
        MessageType.VISION,
        MessageType.MINECRAFT,
        MessageType.LEAGUE,
        MessageType.WARUDO,
        MessageType.AUDIO,
    ))

    def __new__(cls, name: str = "AnnaAI", *args, **kwargs):
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
        if Logger._initialized:
            if config is not None:
                self.config = config
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
        self.config = config
        self._thought_buffer_callback = None

        print(f"[Logger] Singleton instance created: {id(self)}")
        if config:
            print(f"[Logger] Config reference set: {id(config)}")

    def set_config(self, config: 'Config'):
        self.config = config
        print(f"[Logger:{self.name}] Config reference {id(config)}")

    def set_gui_callback(self, callback: Callable[[str, str, str], None]):
        self.gui_callback = callback

    def set_thought_buffer_callback(self, callback: Callable[[str], None]):
        """
        Register callback that forwards qualifying log messages into the thought buffer.
        callback(message: str) — typically thought_buffer.ingest_system_message.
        Forwards all _BUFFER_TYPES messages. Safe to call multiple times; last wins.
        """
        self._thought_buffer_callback = callback

    def set_gui_color(self, msg_type: MessageType, color: str):
        self.gui_colors[msg_type] = color

    def set_min_level(self, level: LogLevel):
        self.min_level = level

    def _should_log(self, level: LogLevel) -> bool:
        return level.value >= self.min_level.value

    def _check_category_enabled(self, msg_type: MessageType) -> bool:
        if not self.config:
            return True

        try:
            if msg_type in (MessageType.TOOL, MessageType.TOOL_STATUS,
                            MessageType.VISION, MessageType.MEMORY,
                            MessageType.GOAL, MessageType.SPEECH,
                            MessageType.AUDIO, MessageType.WARUDO,
                            MessageType.MINECRAFT, MessageType.LEAGUE):
                return self.config.LOG_TOOL_EXECUTION

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

            elif msg_type in (MessageType.ERROR, MessageType.WARNING,
                              MessageType.USER, MessageType.FAMILY,
                              MessageType.JUDGE, MessageType.FILTER):
                return True

            return self.config.LOG_SYSTEM_INFORMATION

        except AttributeError:
            return True

    def _get_gui_color(self, msg_type: MessageType) -> str:
        return self.gui_colors.get(msg_type, self.gui_colors[MessageType.SYSTEM])

    def log(
        self,
        message: str,
        msg_type: MessageType = MessageType.SYSTEM,
        level: LogLevel = LogLevel.INFO,
        prefix: Optional[str] = None
    ):
        if not self._should_log(level):
            return

        if not self._check_category_enabled(msg_type):
            return

        if prefix is None:
            prefix = f"[{msg_type.value.upper()}]"

        if self.enable_console:
            timestamp = datetime.now().strftime("%H:%M:%S") if self.enable_timestamps else ""
            parts = [f"[{timestamp}]"] if timestamp else []
            parts.extend([prefix, message])
            formatted = " ".join(parts)

            if level in (LogLevel.ERROR, LogLevel.CRITICAL):
                print(formatted, file=sys.stderr, flush=True)
            else:
                print(formatted, flush=True)

        if self.gui_callback:
            color = self._get_gui_color(msg_type)
            gui_message = f"\n{'-'*20}\n{message}\n{'-'*20}\n"
            self.gui_callback(gui_message, msg_type.value, color)

        if self._thought_buffer_callback and msg_type in self._BUFFER_TYPES:
            try:
                self._thought_buffer_callback(
                    f"{prefix.strip('[]')} {message}" if prefix else message
                )
            except Exception:
                pass

    def system(self, message: str):
        self.log(message, MessageType.SYSTEM, LogLevel.INFO, prefix="[System]")

    def prompt(self, message: str):
        self.log(message, MessageType.PROMPT, LogLevel.INFO, prefix="[Prompt]")

    def reactive(self, message: str):
        self.log(message, MessageType.REACTIVE, LogLevel.INFO, prefix="[Reactive]")

    def reflective(self, message: str):
        self.log(message, MessageType.REFLECTIVE, LogLevel.INFO, prefix="[Reflective]")

    def proactive(self, message: str):
        self.log(message, MessageType.PROACTIVE, LogLevel.INFO, prefix="[Proactive]")

    def responsive(self, message: str):
        self.log(message, MessageType.RESPONSIVE, LogLevel.INFO, prefix="[Responsive]")

    def thinking(self, message: str):
        self.log(message, MessageType.THINKING, LogLevel.INFO, prefix="[Thinking]")

    def action(self, message: str):
        self.log(message, MessageType.ACTION, LogLevel.INFO, prefix="[Action]")

    def tool(self, message: str):
        self.log(message, MessageType.TOOL, LogLevel.INFO, prefix="[Tool]")
    
    def vision(self, message: str):
        self.log(message, MessageType.VISION, LogLevel.INFO, prefix="[Vision]")

    def error(self, message: str):
        self.log(message, MessageType.ERROR, LogLevel.ERROR)

    def warning(self, message: str):
        self.log(message, MessageType.WARNING, LogLevel.WARNING, prefix="[Warning]")

    def judge(self, message: str):
        self.log(message, MessageType.JUDGE, LogLevel.INFO, prefix="[Judge]")

    def filter(self, message: str):
        self.log(message, MessageType.FILTER, LogLevel.INFO, prefix="[Filter]")

    def success(self, message: str):
        self.log(message, MessageType.SUCCESS, LogLevel.INFO)

    def debug(self, message: str, msg_type: MessageType = MessageType.SYSTEM):
        self.log(message, msg_type, LogLevel.DEBUG, prefix="[Debug]")

    def user_input(self, username: str, message: str):
        self.log(f"{username}: {message}", MessageType.USER, LogLevel.INFO, prefix="[User]")

    def agent_response(self, agentname: str, message: str):
        self.log(f"{agentname}: {message}", MessageType.AGENT, LogLevel.INFO, prefix="")

    def memory(self, message: str):
        self.log(message, MessageType.MEMORY, LogLevel.INFO, prefix="[Memory]")

    def goal(self, message: str):
        self.log(message, MessageType.GOAL, LogLevel.INFO, prefix="[GOAL]")

    def speech(self, message: str):
        self.log(message, MessageType.SPEECH, LogLevel.INFO, prefix="[SPEECH]")

    def audio(self, message: str):
        self.log(message, MessageType.AUDIO, LogLevel.INFO, prefix="[Audio]")

    def livechat(self, message: str):
        self.log(message, MessageType.LIVECHAT, LogLevel.INFO, prefix="[LiveChat]")

    def discord(self, message: str):
        self.log(message, MessageType.DISCORD, LogLevel.INFO, prefix="[Discord]")

    def youtube(self, message: str):
        self.log(message, MessageType.YOUTUBE, LogLevel.INFO, prefix="[YouTube]")

    def twitch(self, message: str):
        self.log(message, MessageType.TWITCH, LogLevel.INFO, prefix="[Twitch]")

    def minecraft(self, message: str):
        self.log(message, MessageType.MINECRAFT, LogLevel.INFO, prefix="[Minecraft]")

    def league(self, message: str):
        self.log(message, MessageType.LEAGUE, LogLevel.INFO, prefix="[League]")

    def warudo(self, message: str):
        self.log(message, MessageType.WARUDO, LogLevel.INFO, prefix="[Warudo]")


def get_logger() -> Logger:
    return Logger()


def set_global_logger_config(config):
    logger = Logger()
    logger.set_config(config)