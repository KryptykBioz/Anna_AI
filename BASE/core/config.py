# Filename: BASE/core/config.py
"""
Unified Config Singleton
========================
Single source of truth: personality/config.json
Overrides via .env at project root (AGENT_SECTION_KEY or legacy OLLAMA_* keys).

No imports from bot_info.py or controls.py — those are now shims that read
from this singleton.
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

# Load .env from project root before anything else
try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(_project_root / ".env", override=True)
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(key: str, default: Any = None, cast=None) -> Any:
    """Read env var, cast if provided, return default if missing."""
    val = os.environ.get(key)
    if val is None:
        return default
    if cast is bool:
        return val.strip().lower() in ("1", "true", "yes", "on")
    if cast is not None:
        try:
            return cast(val)
        except (ValueError, TypeError):
            return default
    return val


def _env_section(section: str, key: str, default: Any, cast=None) -> Any:
    """
    Look up env override for a config section key.
    Tries AGENT_<SECTION>_<KEY> first, then falls back to default.
    """
    env_key = f"AGENT_{section.upper()}_{key.upper()}"
    return _env(env_key, default, cast)


def _cast_for(value: Any):
    """Infer cast type from default value type."""
    if isinstance(value, bool):
        return bool
    if isinstance(value, int):
        return int
    if isinstance(value, float):
        return float
    return None


# ---------------------------------------------------------------------------
# Config singleton
# ---------------------------------------------------------------------------

class Config:
    _instance: Optional["Config"] = None
    _initialized: bool = False

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if Config._initialized:
            return
        Config._initialized = True
        self._tool_registry: Dict[str, Dict] = {}
        self._raw: Dict[str, Any] = self._load_json()
        self._apply_all()
        self._discover_and_register_tools()

    # -----------------------------------------------------------------------
    # JSON loading
    # -----------------------------------------------------------------------

    def _load_json(self) -> Dict[str, Any]:
        project_root = Path(__file__).resolve().parent.parent.parent
        config_path = project_root / "personality" / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _section(self, name: str) -> Dict[str, Any]:
        return self._raw.get(name, {})

    # -----------------------------------------------------------------------
    # Apply all sections
    # -----------------------------------------------------------------------

    def _apply_all(self):
        self._apply_history_limit()  # Must run first — downstream sections consume self.history_limit
        self._apply_bot()
        self._apply_models()
        self._apply_voice()
        self._apply_ollama()
        self._apply_memory()
        self._apply_logging()
        self._apply_controls()
        self._apply_integrations()
        self._apply_features()
        self._apply_personality()

    # -----------------------------------------------------------------------
    # Apply history limit
    # -----------------------------------------------------------------------

    def _apply_history_limit(self):
        """Single source of truth for all conversation/thought history lengths."""
        self.history_limit: int = _env("AGENT_HISTORY_LIMIT", 50, int)
        self._history_limit_set: bool = os.environ.get("AGENT_HISTORY_LIMIT") is not None

    def _resolve_history_field(self, section: str, key: str, json_val: int) -> int:
        """Priority: AGENT_<SECTION>_<KEY> > AGENT_HISTORY_LIMIT > json_val > 50"""
        specific = _env(f"AGENT_{section.upper()}_{key.upper()}", None, int)
        if specific is not None:
            return specific
        if self._history_limit_set:
            return self.history_limit
        return json_val if json_val is not None else 50

    # -----------------------------------------------------------------------
    # Bot identity
    # -----------------------------------------------------------------------

    def _apply_bot(self):
        s = self._section("bot")
        self.agentname:           str = _env_section("bot", "name",           s.get("name",           "Anna"))
        self.username:            str = _env_section("bot", "username",        s.get("username",        "User"))
        self.game_username:       str = _env_section("bot", "game_username",   s.get("game_username",   "Player"))
        self.group_chat_port:     int = _env_section("bot", "group_chat_port", s.get("group_chat_port", 54321), int)
        self.max_context_entries: int = self._resolve_history_field("bot", "max_context_entries", s.get("max_context_entries", 50))
        self.recent_convo_limit:  int = self._resolve_history_field("bot", "recent_convo_limit",  s.get("recent_convo_limit",  50))


    # -----------------------------------------------------------------------
    # Models
    # -----------------------------------------------------------------------

    def _apply_models(self):
        s = self._section("models")
        default = "gemma4:latest"
        self.thought_model: str = _env_section("models", "thought_model",  s.get("thought_model",  default))
        self.text_model:    str = _env_section("models", "response_model", s.get("response_model", default))
        self.vision_model:  str = _env_section("models", "vision_model",   s.get("vision_model",   default))
        self.embed_model:   str = _env_section("models", "embed_model",    s.get("embed_model",    "nomic-embed-text:latest"))
        self.tool_model:    str = _env_section("models", "tool_model",     s.get("tool_model",     default))
        self.action_model:  str = _env_section("models", "action_model",   s.get("action_model",   default))

    # -----------------------------------------------------------------------
    # Voice
    # -----------------------------------------------------------------------

    def _apply_voice(self):
        s = self._section("voice")
        self.voice_index:               int   = _env_section("voice", "voice_index",           s.get("voice_index",           1),    int)
        self.vb_cable_name:             str   = _env_section("voice", "vb_cable_name",         s.get("vb_cable_name",         "CABLE Input"))
        self.voice_sample_filename:     str   = _env_section("voice", "voice_sample_filename", s.get("voice_sample_filename", ""))
        self.user_voice_sample_filename:str   = _env_section("voice", "user_voice_sample_filename", s.get("user_voice_sample_filename", ""))
        self.xtts_language:             str   = _env_section("voice", "xtts_language",         s.get("xtts_language",         "en"))
        self.xtts_speed:                float = _env_section("voice", "xtts_speed",            s.get("xtts_speed",            1.0),  float)
        self.xtts_temperature:          float = _env_section("voice", "xtts_temperature",      s.get("xtts_temperature",      0.7),  float)
        self.xtts_length_penalty:       float = _env_section("voice", "xtts_length_penalty",   s.get("xtts_length_penalty",   1.0),  float)
        self.xtts_repetition_penalty:   float = _env_section("voice", "xtts_repetition_penalty", s.get("xtts_repetition_penalty", 5.0), float)
        self.xtts_top_k:                int   = _env_section("voice", "xtts_top_k",            s.get("xtts_top_k",            50),   int)
        self.xtts_top_p:                float = _env_section("voice", "xtts_top_p",            s.get("xtts_top_p",            0.85), float)
        self.xtts_gpt_cond_len:         int   = _env_section("voice", "xtts_gpt_cond_len",     s.get("xtts_gpt_cond_len",     30),   int)
        self.xtts_gpt_cond_chunk_len:   int   = _env_section("voice", "xtts_gpt_cond_chunk_len", s.get("xtts_gpt_cond_chunk_len", 4), int)
        self.xtts_max_ref_length:       int   = _env_section("voice", "xtts_max_ref_length",   s.get("xtts_max_ref_length",   60),   int)
        
    # -----------------------------------------------------------------------
    # Ollama
    # -----------------------------------------------------------------------

    def _apply_ollama(self):
        s = self._section("ollama")

        # Legacy OLLAMA_* env keys take priority over AGENT_OLLAMA_* for backward compat
        def _o(key: str, default: Any, cast=None) -> Any:
            legacy = _env(f"OLLAMA_{key.upper()}", None, cast)
            if legacy is not None:
                return legacy
            return _env_section("ollama", key, s.get(key, default), cast)

        self.ollama_endpoint:          str           = _o("endpoint",             "http://localhost:11434")
        self.ollama_temperature:       float         = _o("temperature",          0.85,  float)
        self.ollama_temperature_action: float        = _o("temperature_action",   0.2,   float)
        self.ollama_temperature_cognitive: float     = _o("temperature_cognitive",0.7,   float)
        self.ollama_temperature_response: float      = _o("temperature_response", 0.9,   float)
        self.ollama_max_tokens:        int           = _o("max_tokens",           1000,  int)
        self.ollama_num_predict:       int           = _o("num_predict",          1000,  int)
        self.ollama_num_ctx:           int           = _o("num_ctx",              3000,  int)
        self.ollama_context_length:    int           = self.ollama_num_ctx
        self.ollama_top_p:             float         = _o("top_p",                0.92,  float)
        self.ollama_top_k:             int           = _o("top_k",                60,    int)
        self.ollama_repeat_penalty:    float         = _o("repeat_penalty",       1.4,   float)
        self.ollama_timeout:           int           = _o("timeout",              600,   int)
        self.ollama_keep_alive:        str           = _o("keep_alive",           "24h")
        self.ollama_num_parallel:      int           = _o("num_parallel",         1,     int)
        self.ollama_max_loaded_models: int           = _o("max_loaded_models",    2,     int)
        self.ollama_concurrent_requests: int         = _o("concurrent_requests",  1,     int)

        raw_seed = s.get("seed", None)
        seed_env = _env("OLLAMA_SEED", None, int)
        if seed_env is not None:
            self.ollama_seed: Optional[int] = seed_env if seed_env != -1 else None
        else:
            self.ollama_seed = raw_seed

    # -----------------------------------------------------------------------
    # Memory
    # -----------------------------------------------------------------------

    def _apply_memory(self):
        s = self._section("memory")
        self.max_context_entries:        int  = self._resolve_history_field("memory", "max_context_entries", s.get("max_context_entries", 50))
        self.embedding_search_results:   int  = _env_section("memory", "embedding_search_results",   s.get("embedding_search_results",   1),   int)
        self.base_memory_search_results: int  = _env_section("memory", "base_memory_search_results", s.get("base_memory_search_results", 1),   int)
        self.auto_summarize_threshold:   int  = _env_section("memory", "auto_summarize_threshold",   s.get("auto_summarize_threshold",   100), int)
        self.include_base_memory:        bool = _env_section("memory", "include_base_memory",        s.get("include_base_memory",        False), bool)
        self.memory_length:              int  = self._resolve_history_field("memory", "memory_length", s.get("memory_length", 50))
        self.max_long_term_memories:     int  = _env_section("memory", "max_long_term_memories",     s.get("max_long_term_memories",     1),   int)
        self.max_base_memories:          int  = _env_section("memory", "max_base_memories",          s.get("max_base_memories",          1),   int)


    # -----------------------------------------------------------------------
    # Logging
    # -----------------------------------------------------------------------

    def _apply_logging(self):
        s = self._section("logging")

        def _l(key: str, default: bool) -> bool:
            return _env_section("logging", key, s.get(key, default), bool)

        self.LOG_TOOL_EXECUTION:      bool = _l("log_tool_execution",      True)
        self.LOG_PROMPT_CONSTRUCTION: bool = _l("log_prompt_construction", False)
        self.LOG_REACTIVE_PROMPT:     bool = _l("log_reactive_prompt",     True)
        self.LOG_REFLECTIVE_PROMPT:   bool = _l("log_reflective_prompt",   True)
        self.LOG_PROACTIVE_PROMPT:    bool = _l("log_proactive_prompt",    True)
        self.LOG_RESPONSIVE_PROMPT:   bool = _l("log_responsive_prompt",   True)
        self.LOG_ACTION_PROMPT:       bool = _l("log_action_prompt",       True)
        self.LOG_RESPONSE_PROCESSING: bool = _l("log_response_processing", True)
        self.LOG_SYSTEM_INFORMATION:  bool = _l("log_system_information",  True)
        self.SHOW_CHAT:               bool = _l("show_chat",               False)
        self.LOG_CODING_EXECUTION:    bool = _l("log_coding_execution",    False)
        self.LOG_DISCORD_EXECUTION:   bool = _l("log_discord_execution",   False)
        self.LOG_MINECRAFT_EXECUTION: bool = _l("log_minecraft_execution", False)

    # -----------------------------------------------------------------------
    # Controls (runtime flags — mirrored into controls.py shim)
    # -----------------------------------------------------------------------

    def _apply_controls(self):
        s = self._section("controls")

        def _c(key: str, default: Any) -> Any:
            cast = _cast_for(default)
            return _env_section("controls", key, s.get(key, default), cast)

        self.KILL_COMMAND:                    str   = _c("kill_command",                    "shut down sleep now")
        self.ENABLE_CONTINUOUS_THINKING:      bool  = _c("enable_continuous_thinking",      False)
        self.MIN_PROACTIVE_INTERVAL:          float = _c("min_proactive_interval",          5.0)
        self.MAX_PROACTIVE_INTERVAL:          float = _c("max_proactive_interval",          15.0)
        self.MAX_CONSECUTIVE_PROACTIVE:       int   = _c("max_consecutive_proactive",       200)
        self.CHAT_ENGAGEMENT:                 bool  = _c("chat_engagement",                 False)
        self.AUTO_RESTART:                    bool  = _c("auto_restart",                    False)
        self.LIMIT_PROCESSING:                bool  = _c("limit_processing",                False)
        self.PROCESSING_DELAY:                int   = _c("processing_delay",                10)
        self.LIMIT_SPEAKING:                  bool  = _c("limit_speaking",                  False)
        self.SPEAKING_DELAY:                  int   = _c("speaking_delay",                  30)
        self.AUTO_RESPOND:                    bool  = _c("auto_respond",                    False)
        self.AUTO_RESPOND_INTERVAL:           int   = _c("auto_respond_interval",           60)
        self.AUTO_PROMPT:                     bool  = _c("auto_prompt",                     False)
        self.AUTO_PROMPT_INTERVAL:            int   = _c("auto_prompt_interval",            300)
        self.USE_STREAMING:                   bool  = _c("use_streaming",                   False)
        self.STREAM_RESPONSES:                bool  = _c("stream_responses",                False)
        self.USE_BASE_MEMORY:                 bool  = _c("use_base_memory",                 True)
        self.USE_LONG_MEMORY:                 bool  = _c("use_long_memory",                 True)
        self.USE_SHORT_MEMORY:                bool  = _c("use_short_memory",                True)
        self.SAVE_MEMORY:                     bool  = _c("save_memory",                     True)
        self.USE_MEMORY:                      bool  = _c("use_memory",                      True)
        self.USE_MEMORY_ENCRYPTION:           bool  = _c("use_memory_encryption",           False)
        self.MEMORY_LENGTH:                   int   = self._resolve_history_field("controls", "memory_length", s.get("memory_length", 50))
        self.MAX_LONG_TERM_MEMORIES:          int   = _c("max_long_term_memories",          1)
        self.MAX_BASE_MEMORIES:               int   = _c("max_base_memories",               1)
        self.INTELLIGENT_TOOL_SELECTION:      bool  = _c("intelligent_tool_selection",      False)
        self.USE_AI_TOOL_VERIFICATION:        bool  = _c("use_ai_tool_verification",        False)
        self.TOOL_SELECTION_THRESHOLD:        float = _c("tool_selection_threshold",        0.3)
        self.ENABLE_CONTENT_FILTER:           bool  = _c("enable_content_filter",           False)
        self.USE_AI_CONTENT_FILTER:           bool  = _c("use_ai_content_filter",           False)
        self.CONTENT_FILTER_INCOMING:         bool  = _c("content_filter_incoming",         False)
        self.CONTENT_FILTER_OUTGOING:         bool  = _c("content_filter_outgoing",         False)
        self.CONTENT_FILTER_CONTEXT:          bool  = _c("content_filter_context",          False)
        self.VOICE_VOLUME:                    float = _c("voice_volume",                    1.0)
        self.SOUND_EFFECT_VOLUME:             float = _c("sound_effect_volume",             1.0)
        self.AVATAR_SPEECH:                   bool  = _c("avatar_speech",                   True)
        self.USE_OPENCV_VISION:               bool  = _c("use_opencv_vision",               False)
        self.opencv_vision_fps:               int   = _c("opencv_vision_fps",               15)
        self.opencv_vision_interval:          float = _c("opencv_vision_interval",          5.0)
        self.opencv_vision_width:             int   = _c("opencv_vision_width",             1024)
        self.opencv_vision_height:            int   = _c("opencv_vision_height",            768)
        self.opencv_vision_change_threshold:  int   = _c("opencv_vision_change_threshold",  50000)
        self.GROUP_CHAT:                      bool  = _c("group_chat",                      False)
        self.PLAYING_GAME:                    bool  = _c("playing_game",                    False)
        self.ENABLE_TOOL_HOT_RELOAD:          bool  = _c("enable_tool_hot_reload",          True)
        self.ENABLE_CORE_HOT_RELOAD:          bool  = _c("enable_core_hot_reload",          True)
        self.ENABLE_HOT_RELOAD:               bool  = _c("enable_hot_reload",               True)
        self.ENABLE_FILE_WATCHING:            bool  = _c("enable_file_watching",            True)
        self.HOT_RELOAD_DEBOUNCE:             float = _c("hot_reload_debounce",             2.0)
        self.USE_THOUGHT_BUFFER:              bool  = _c("use_thought_buffer",              True)
        self.MAX_TOKENS:                      int   = _c("max_tokens",                      2000)
        self.MAX_TOOL_RESULT_CHARS:           int   = _c("max_tool_result_chars",           1000)
        self.MAX_TOOL_RESULTS:                int   = _c("max_tool_results",                3)
        self.TEMPERATURE:                     float = _c("temperature",                     0.7)
        
        # ── Prompt Judge ───────────────────────────────────────────────────────
        self.USE_PROMPT_JUDGE:        bool  = _c("use_prompt_judge",        False)
        self.PROMPT_JUDGE_INTERVAL:   int   = _c("prompt_judge_interval",   300)

        # Legacy aliases
        self.SLOW_MODE:                       bool  = False
        self.DELAY_TIMER:                     int   = 10
        
    # -----------------------------------------------------------------------
    # Integrations (YouTube, Twitch, Discord, Warudo, chat_engagement)
    # -----------------------------------------------------------------------

    def _apply_integrations(self):
        # --- Warudo ---
        w = self._section("warudo")
        self.warudo_websocket_url:   str   = _env_section("warudo", "websocket_url",      w.get("websocket_url",      "ws://127.0.0.1:19190"))
        self.warudo_enabled:         bool  = _env_section("warudo", "enabled",            w.get("enabled",            True),  bool)
        self.warudo_auto_connect:    bool  = _env_section("warudo", "auto_connect",       w.get("auto_connect",       True),  bool)
        self.warudo_timeout:         float = _env_section("warudo", "connection_timeout", w.get("connection_timeout", 2.0),   float)

        # --- Unity ---
        u = self._section("unity")
        self.unity_websocket_url:    str   = _env_section("unity", "websocket_url",      u.get("websocket_url",      "ws://127.0.0.1:19192"))
        self.unity_connection_timeout: float = _env_section("unity", "connection_timeout", u.get("connection_timeout", 5.0), float)

        # --- Chat engagement ---
        ce = self._section("chat_engagement")
        self.chat_engagement_enabled:        bool = _env_section("chat_engagement", "enabled",               ce.get("enabled",               False), bool)
        self.chat_engagement_autonomous:     bool = _env_section("chat_engagement", "autonomous",            ce.get("autonomous",            True),  bool)
        self.chat_engagement_check_interval: int  = _env_section("chat_engagement", "check_interval",       ce.get("check_interval",       30),    int)
        self.chat_engagement_max_unengaged:  int  = _env_section("chat_engagement", "max_unengaged_messages",ce.get("max_unengaged_messages",5),    int)
        self.chat_engagement_cooldown:       int  = _env_section("chat_engagement", "engagement_cooldown",   ce.get("engagement_cooldown",   60),    int)

        # --- YouTube ---
        yt = self._section("youtube")
        self.youtube_enabled:     bool = _env_section("youtube", "enabled",      yt.get("enabled",     True),  bool)
        self.youtube_video_id:    str  = _env("AGENT_YOUTUBE_VIDEO_ID",          yt.get("video_id",    "")) or ""
        self.youtube_auto_start:  bool = _env_section("youtube", "auto_start",  yt.get("auto_start",  False), bool)
        self.youtube_max_messages:int  = _env_section("youtube", "max_messages", yt.get("max_messages",10),    int)

        # --- Twitch ---
        tw = self._section("twitch")
        self.twitch_enabled:      bool = _env_section("twitch", "enabled",      tw.get("enabled",     True),  bool)
        self.twitch_channel:      str  = _env("AGENT_TWITCH_CHANNEL",            tw.get("channel",     "")) or ""
        self.twitch_auto_start:   bool = _env_section("twitch", "auto_start",   tw.get("auto_start",  False), bool)
        self.twitch_max_messages: int  = _env_section("twitch", "max_messages", tw.get("max_messages",10),    int)
        self.twitch_oauth_token:  str  = _env("AGENT_TWITCH_OAUTH_TOKEN",        tw.get("oauth_token", "")) or ""
        self.twitch_nickname:     str  = _env("AGENT_TWITCH_NICKNAME",           tw.get("nickname",    "")) or ""

        # --- Discord ---
        dc = self._section("discord")
        self.discord_enabled:             bool          = _env_section("discord", "enabled",               dc.get("enabled",              True),  bool)
        self.discord_token:               str           = _env("AGENT_DISCORD_BOT_TOKEN",                   dc.get("bot_token",            "")) or ""
        self.discord_command_prefix:      str           = _env_section("discord", "command_prefix",        dc.get("command_prefix",       "!"))
        self.discord_auto_start:          bool          = _env_section("discord", "auto_start",            dc.get("auto_start",           False), bool)
        raw_channels = dc.get("allowed_channels") or []
        raw_guilds   = dc.get("allowed_guilds")   or []
        self.discord_allowed_channels:    Optional[List[int]] = [int(x) for x in raw_channels] or None
        self.discord_allowed_guilds:      Optional[List[int]] = [int(x) for x in raw_guilds]   or None
        self.discord_respond_to_mentions: bool          = _env_section("discord", "respond_to_mentions",  dc.get("respond_to_mentions",  True),  bool)
        self.discord_respond_to_replies:  bool          = _env_section("discord", "respond_to_replies",   dc.get("respond_to_replies",   True),  bool)
        self.discord_respond_to_dms:      bool          = _env_section("discord", "respond_to_dms",       dc.get("respond_to_dms",       True),  bool)
        self.discord_respond_in_threads:  bool          = _env_section("discord", "respond_in_threads",   dc.get("respond_in_threads",   True),  bool)
        self.discord_typing_indicator:    bool          = _env_section("discord", "typing_indicator",     dc.get("typing_indicator",     True),  bool)
        self.discord_message_history_limit: int         = _env_section("discord", "message_history_limit",dc.get("message_history_limit",10),    int)
        self.discord_max_message_length:  int           = _env_section("discord", "max_message_length",   dc.get("max_message_length",   2000),  int)
        self.discord_split_long_messages: bool          = _env_section("discord", "split_long_messages",  dc.get("split_long_messages",  True),  bool)
        self.discord_command_cooldown:    int           = _env_section("discord", "command_cooldown",     dc.get("command_cooldown",     3),     int)

        self.IN_DISCORD_CHAT: bool = bool(
            self.discord_enabled and self.discord_token and
            self.discord_token not in ("", "YOUR_DISCORD_BOT_TOKEN_HERE")
        )

        if self.discord_enabled and not self.discord_token:
            print("[WARNING] Discord enabled but no bot_token configured")
        if self.IN_DISCORD_CHAT:
            print(f"[INFO] Discord bot configured: prefix='{self.discord_command_prefix}', auto_start={self.discord_auto_start}")

    # -----------------------------------------------------------------------
    # Features
    # -----------------------------------------------------------------------

    def _apply_features(self):
        f = self._section("features")
        self.use_search:             bool = _env_section("features", "use_search",             f.get("use_search",             False), bool)
        self.use_vision:             bool = _env_section("features", "use_vision",             f.get("use_vision",             False), bool)
        self.use_warudo:             bool = _env_section("features", "use_warudo",             f.get("use_warudo",             True),  bool)
        self.use_sound_effects:      bool = _env_section("features", "use_sound_effects",      f.get("use_sound_effects",      True),  bool)
        self.sound_effects_directory:str  = _env_section("features", "sound_effects_directory",f.get("sound_effects_directory","./BASE/tools/installed/sound_effects/effects"))

    # -----------------------------------------------------------------------
    # Personality prompt (optional addendum loaded separately)
    # -----------------------------------------------------------------------

    def _apply_personality(self):
        try:
            from personality.prompts.personality_prompt_parts import PersonalityPromptParts
            self.current_context:      Optional[str] = PersonalityPromptParts.current_context
            self.important_reminders:  Optional[str] = PersonalityPromptParts.important_reminders
        except Exception:
            self.current_context      = None
            self.important_reminders  = None

    # -----------------------------------------------------------------------
    # Tool registry (unchanged from original)
    # -----------------------------------------------------------------------

    def _discover_and_register_tools(self):
        import BASE.config.controls as controls
        project_root = Path(__file__).resolve().parent.parent.parent
        tools_dir = project_root / "BASE" / "tools" / "installed"
        if not tools_dir.exists():
            print(f"[Config] [WARNING] Tools directory not found: {tools_dir}")
            return
        try:
            created_vars, tool_count = [], 0
            for tool_dir in tools_dir.iterdir():
                if not tool_dir.is_dir():
                    continue
                info_file = tool_dir / "information.json"
                tool_file = tool_dir / "tool.py"
                if not info_file.exists() or not tool_file.exists():
                    continue
                try:
                    with open(info_file, "r", encoding="utf-8") as f:
                        info = json.load(f)
                    tool_name   = info.get("tool_name")
                    control_var = info.get("control_variable_name")
                    default_val = info.get("control_variable_value", False)
                    if not tool_name or not control_var:
                        print(f"[Config] [WARNING] Invalid metadata in {tool_dir.name}")
                        continue
                    if not hasattr(controls, control_var):
                        setattr(controls, control_var, default_val)
                        created_vars.append(f"{control_var}={default_val}")
                    self._register_tool_config_from_info(tool_name, info, tool_dir, tool_file)
                    tool_count += 1
                except Exception as e:
                    print(f"[Config] [FAILED] {tool_dir.name}: {e}")
            if created_vars:
                print(f"[Config] Created {len(created_vars)} dynamic controls: {created_vars}")
            print(f"[Config] Registered {tool_count} tools")
        except Exception as e:
            import traceback
            print(f"[Config] Tool discovery failed: {e}")
            traceback.print_exc()

    def _register_tool_config_from_info(self, tool_name: str, tool_info: dict,
                                        tool_dir: Path, tool_file: Path):
        control_var = tool_info.get("control_variable_name")
        default_val = tool_info.get("control_variable_value", False)
        self._tool_registry[tool_name] = {
            "control_variable_name": control_var,
            "default_value":         default_val,
            "display_name":          tool_info.get("metadata", {}).get("display_name", tool_name.replace("_"," ").title()),
            "category":              tool_info.get("metadata", {}).get("category", "Other Tools"),
            "description":           tool_info.get("tool_description", ""),
            "timeout":               tool_info.get("timeout_seconds", 30),
            "cooldown":              tool_info.get("cooldown_seconds", 0),
            "commands":              tool_info.get("available_commands", []),
            "usage_examples":        tool_info.get("tool_usage_examples", []),
            "tool_directory":        str(tool_dir),
            "module_path":           str(tool_file),
        }
        config_attr = f"tool_{tool_name}_enabled"
        if not hasattr(self, config_attr):
            setattr(self, config_attr, default_val)

    def _register_tool_config(self, tool_info):
        """Legacy ToolInfo object path (kept for compatibility)."""
        control_var = tool_info.control_variable_name
        default_val = tool_info.control_variable_value
        tool_name   = tool_info.tool_name
        self._tool_registry[tool_name] = {
            "control_variable_name": control_var,
            "default_value":         default_val,
            "display_name":          tool_info.metadata.get("display_name", tool_name.replace("_"," ").title()),
            "category":              tool_info.metadata.get("category", "Other Tools"),
            "description":           tool_info.tool_description,
            "timeout":               tool_info.metadata.get("timeout_seconds", 30),
            "cooldown":              tool_info.metadata.get("cooldown_seconds", 0),
            "commands":              tool_info.metadata.get("available_commands", []),
            "usage_examples":        tool_info.metadata.get("tool_usage_examples", []),
            "tool_directory":        tool_info.tool_directory,
            "module_path":           tool_info.module_path,
        }
        config_attr = f"tool_{tool_name}_enabled"
        if not hasattr(self, config_attr):
            setattr(self, config_attr, default_val)

    # -----------------------------------------------------------------------
    # Sync / accessors (unchanged API)
    # -----------------------------------------------------------------------

    def sync_control_variables_with_defaults(self, controls_module):
        for tool_name, meta in self._tool_registry.items():
            control_var = meta["control_variable_name"]
            default_val = meta["default_value"]
            if hasattr(controls_module, control_var):
                current = getattr(controls_module, control_var)
                if current != default_val:
                    setattr(controls_module, control_var, default_val)
                    print(f"[Config] Reset {control_var}: {current} -> {default_val}")

    def get_tool_registry(self) -> Dict[str, Dict]:
        return self._tool_registry.copy()

    def get_tool_config(self, tool_name: str) -> Optional[Dict]:
        return self._tool_registry.get(tool_name)

    def sync_with_controls(self, controls_module):
        for name in (
            "LOG_TOOL_EXECUTION", "LOG_PROMPT_CONSTRUCTION", "LOG_RESPONSE_PROCESSING",
            "LOG_SYSTEM_INFORMATION", "SHOW_CHAT", "LOG_REACTIVE_PROMPT",
            "LOG_REFLECTIVE_PROMPT", "LOG_PROACTIVE_PROMPT", "LOG_RESPONSIVE_PROMPT",
            "LOG_ACTION_PROMPT", "LOG_CODING_EXECUTION", "LOG_DISCORD_EXECUTION",
            "LOG_MINECRAFT_EXECUTION",
        ):
            if hasattr(controls_module, name):
                setattr(self, name, getattr(controls_module, name))

    def get_active_tools(self, controls_module) -> dict:
        return {
            "coding":             getattr(controls_module, "USE_CODING",                False),
            "game":               getattr(controls_module, "PLAYING_GAME",              False),
            "twitch":             getattr(controls_module, "IN_TWITCH_CHAT",            False),
            "youtube":            getattr(controls_module, "IN_YOUTUBE_CHAT",           False),
            "discord":            getattr(controls_module, "IN_DISCORD_CHAT",           False),
            "memory_short":       getattr(controls_module, "USE_SHORT_MEMORY",          True),
            "memory_long":        getattr(controls_module, "USE_LONG_MEMORY",           True),
            "memory_base":        getattr(controls_module, "USE_BASE_MEMORY",           True),
            "content_filter":     getattr(controls_module, "ENABLE_CONTENT_FILTER",     False),
            "ai_filter":          getattr(controls_module, "USE_AI_CONTENT_FILTER",     False),
            "speech":             getattr(controls_module, "AVATAR_SPEECH",             True),
            "intelligent_tools":  getattr(controls_module, "INTELLIGENT_TOOL_SELECTION",False),
            "continuous_thinking":getattr(controls_module, "ENABLE_CONTINUOUS_THINKING",False),
            "SLOW_MODE":          getattr(controls_module, "SLOW_MODE",                 False),
        }

    def is_playing_minecraft(self, controls_module) -> bool:
        return getattr(controls_module, "PLAYING_MINECRAFT", False)

    def is_playing_league(self, controls_module) -> bool:
        return getattr(controls_module, "PLAYING_LEAGUE", False)

    def get(self, key: str, default=None):
        if hasattr(self, key):
            return getattr(self, key)
        lower = key.lower()
        for attr in dir(self):
            if attr.lower() == lower:
                return getattr(self, attr)
        return default