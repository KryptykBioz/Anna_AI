# Filename: BASE/config/controls.py
"""
Runtime control variables shim.
Default values now live in personality/config.json (controls section).
This module seeds every variable from the Config singleton at import time,
then remains a plain mutable module so the GUI and control_manager can
toggle flags at runtime exactly as before.

DO NOT hardcode defaults here — edit personality/config.json instead.
"""
from BASE.core.config import Config as _Config

_c = _Config()

# ── Cognitive loop ─────────────────────────────────────────────────────────
KILL_COMMAND                 = _c.KILL_COMMAND
ENABLE_CONTINUOUS_THINKING   = _c.ENABLE_CONTINUOUS_THINKING
MIN_PROACTIVE_INTERVAL       = _c.MIN_PROACTIVE_INTERVAL
MAX_PROACTIVE_INTERVAL       = _c.MAX_PROACTIVE_INTERVAL
MAX_CONSECUTIVE_PROACTIVE    = _c.MAX_CONSECUTIVE_PROACTIVE
CHAT_ENGAGEMENT              = _c.CHAT_ENGAGEMENT
AUTO_RESTART                 = _c.AUTO_RESTART

# ── Rate limiting ──────────────────────────────────────────────────────────
LIMIT_PROCESSING             = _c.LIMIT_PROCESSING
PROCESSING_DELAY             = _c.PROCESSING_DELAY
LIMIT_SPEAKING               = _c.LIMIT_SPEAKING
SPEAKING_DELAY               = _c.SPEAKING_DELAY

# ── Auto-response ──────────────────────────────────────────────────────────
AUTO_RESPOND                 = _c.AUTO_RESPOND
AUTO_RESPOND_INTERVAL        = _c.AUTO_RESPOND_INTERVAL
AUTO_PROMPT                  = _c.AUTO_PROMPT
AUTO_PROMPT_INTERVAL         = _c.AUTO_PROMPT_INTERVAL

# ── Streaming ──────────────────────────────────────────────────────────────
USE_STREAMING                = _c.USE_STREAMING
STREAM_RESPONSES             = _c.STREAM_RESPONSES

# ── Memory ─────────────────────────────────────────────────────────────────
USE_BASE_MEMORY              = _c.USE_BASE_MEMORY
USE_LONG_MEMORY              = _c.USE_LONG_MEMORY
USE_SHORT_MEMORY             = _c.USE_SHORT_MEMORY
SAVE_MEMORY                  = _c.SAVE_MEMORY
USE_MEMORY                   = _c.USE_MEMORY
USE_MEMORY_ENCRYPTION        = _c.USE_MEMORY_ENCRYPTION
MEMORY_LENGTH                = _c.MEMORY_LENGTH
HISTORY_LIMIT                = _c.history_limit
MAX_LONG_TERM_MEMORIES       = _c.MAX_LONG_TERM_MEMORIES
MAX_BASE_MEMORIES            = _c.MAX_BASE_MEMORIES

# ── Tool intelligence ──────────────────────────────────────────────────────
INTELLIGENT_TOOL_SELECTION   = _c.INTELLIGENT_TOOL_SELECTION
USE_AI_TOOL_VERIFICATION     = _c.USE_AI_TOOL_VERIFICATION
TOOL_SELECTION_THRESHOLD     = _c.TOOL_SELECTION_THRESHOLD

# ── Content filtering ──────────────────────────────────────────────────────
ENABLE_CONTENT_FILTER        = _c.ENABLE_CONTENT_FILTER
USE_AI_CONTENT_FILTER        = _c.USE_AI_CONTENT_FILTER
CONTENT_FILTER_INCOMING      = _c.CONTENT_FILTER_INCOMING
CONTENT_FILTER_OUTGOING      = _c.CONTENT_FILTER_OUTGOING
CONTENT_FILTER_CONTEXT       = _c.CONTENT_FILTER_CONTEXT

# ── Volume ─────────────────────────────────────────────────────────────────
VOICE_VOLUME                 = _c.VOICE_VOLUME
SOUND_EFFECT_VOLUME          = _c.SOUND_EFFECT_VOLUME
AVATAR_SPEECH                = _c.AVATAR_SPEECH

# ── Vision ─────────────────────────────────────────────────────────────────
USE_OPENCV_VISION            = _c.USE_OPENCV_VISION
opencv_vision_fps            = _c.opencv_vision_fps
opencv_vision_interval       = _c.opencv_vision_interval
opencv_vision_width          = _c.opencv_vision_width
opencv_vision_height         = _c.opencv_vision_height
opencv_vision_change_threshold = _c.opencv_vision_change_threshold

# ── Multi-agent ────────────────────────────────────────────────────────────
GROUP_CHAT                   = _c.GROUP_CHAT
PLAYING_GAME                 = _c.PLAYING_GAME

# ── Hot reload ─────────────────────────────────────────────────────────────
ENABLE_TOOL_HOT_RELOAD       = _c.ENABLE_TOOL_HOT_RELOAD
ENABLE_CORE_HOT_RELOAD       = _c.ENABLE_CORE_HOT_RELOAD
ENABLE_HOT_RELOAD            = _c.ENABLE_HOT_RELOAD
ENABLE_FILE_WATCHING         = _c.ENABLE_FILE_WATCHING
HOT_RELOAD_DEBOUNCE          = _c.HOT_RELOAD_DEBOUNCE

# ── Thought buffer ─────────────────────────────────────────────────────────
USE_THOUGHT_BUFFER           = _c.USE_THOUGHT_BUFFER

# ── Logging ────────────────────────────────────────────────────────────────
LOG_TOOL_EXECUTION           = _c.LOG_TOOL_EXECUTION
LOG_PROMPT_CONSTRUCTION      = _c.LOG_PROMPT_CONSTRUCTION
LOG_REACTIVE_PROMPT          = _c.LOG_REACTIVE_PROMPT
LOG_REFLECTIVE_PROMPT        = _c.LOG_REFLECTIVE_PROMPT
LOG_PROACTIVE_PROMPT         = _c.LOG_PROACTIVE_PROMPT
LOG_RESPONSIVE_PROMPT        = _c.LOG_RESPONSIVE_PROMPT
LOG_ACTION_PROMPT            = _c.LOG_ACTION_PROMPT
LOG_RESPONSE_PROCESSING      = _c.LOG_RESPONSE_PROCESSING
LOG_SYSTEM_INFORMATION       = _c.LOG_SYSTEM_INFORMATION
SHOW_CHAT                    = _c.SHOW_CHAT
LOG_CODING_EXECUTION         = _c.LOG_CODING_EXECUTION
LOG_DISCORD_EXECUTION        = _c.LOG_DISCORD_EXECUTION
LOG_MINECRAFT_EXECUTION      = _c.LOG_MINECRAFT_EXECUTION

# ── Performance ────────────────────────────────────────────────────────────
MAX_TOKENS                   = _c.MAX_TOKENS
MAX_TOOL_RESULT_CHARS        = _c.MAX_TOOL_RESULT_CHARS
MAX_TOOL_RESULTS             = _c.MAX_TOOL_RESULTS
TEMPERATURE                  = _c.TEMPERATURE
SLOW_MODE                    = _c.SLOW_MODE
DELAY_TIMER                  = _c.DELAY_TIMER

# ── Prompt Judge ───────────────────────────────────────────────────────────
USE_PROMPT_JUDGE             = _c.USE_PROMPT_JUDGE
PROMPT_JUDGE_INTERVAL        = _c.PROMPT_JUDGE_INTERVAL

# ── Dynamic tool controls (USE_*) ──────────────────────────────────────────
# These are injected at runtime by Config._discover_and_register_tools()
# and by dynamic_control_initializer. Do not define them here.