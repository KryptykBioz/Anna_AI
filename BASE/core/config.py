# Filename: BASE/core/config.py
# Converted to singleton pattern

import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Import bot info
from personality.bot_info import agentname, username, responsemodel, visionmodel, embedmodel, toolmodel, thoughtmodel, actionmodel

def load_config():
    """Load configuration from JSON file"""
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / "personality" / "config.json"
    
    with open(config_path, 'r') as f:
        return json.load(f)

@dataclass
class Config:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern: always return the same instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize only once"""
        # Skip initialization if already done
        if Config._initialized:
            return
        
        Config._initialized = True
        
        json_config = load_config()
        
        # Extract config sections
        ollama_config = json_config["ollama"]
        memory_config = json_config["memory"]
        youtube_config = json_config.get("youtube", {})
        discord_config = json_config.get("discord", {})
        features_config = json_config["features"]
        
        # Bot identity
        self.agentname: str = agentname
        self.username: str = username
        
        # Current context (optional prompt addendum - editable from GUI)
        from personality.prompts.personality_prompt_parts import PersonalityPromptParts
        self.current_context: Optional[str] = PersonalityPromptParts.current_context
        
        # Important reminders (optional prompt addendum - editable from GUI)
        self.important_reminders: Optional[str] = PersonalityPromptParts.important_reminders
        
        # Model configuration
        from personality.bot_info import (
            thoughtmodel, responsemodel, visionmodel, 
            embedmodel, toolmodel, actionmodel
        )
        
        self.thought_model = thoughtmodel
        self.text_model = responsemodel
        self.vision_model = visionmodel
        self.embed_model = embedmodel
        self.tool_model = toolmodel
        self.action_model = actionmodel
        # self.reasoning_model = reasoning_model
        
        # Ollama configuration
        self.ollama_endpoint: str = os.getenv("OLLAMA_ENDPOINT", ollama_config["endpoint"])
        self.ollama_temperature: float = float(os.getenv("OLLAMA_TEMPERATURE", str(ollama_config["temperature"])))
        self.ollama_max_tokens: int = int(os.getenv("OLLAMA_MAX_TOKENS", str(ollama_config["max_tokens"])))
        self.ollama_top_p: float = float(os.getenv("OLLAMA_TOP_P", str(ollama_config["top_p"])))
        self.ollama_top_k: int = int(os.getenv("OLLAMA_TOP_K", str(ollama_config["top_k"])))
        self.ollama_repeat_penalty: float = float(os.getenv("OLLAMA_REPEAT_PENALTY", str(ollama_config["repeat_penalty"])))
        self.ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", str(ollama_config["timeout"])))
        self.ollama_seed: Optional[int] = ollama_config["seed"]

                # Mode-specific temperature overrides
        self.ollama_temperature_action: float = float(
            os.getenv("OLLAMA_TEMPERATURE_ACTION", 
                     str(ollama_config.get("temperature_action", "0.2")))
        )
        self.ollama_temperature_cognitive: float = float(
            os.getenv("OLLAMA_TEMPERATURE_COGNITIVE",
                     str(ollama_config.get("temperature_cognitive", "0.6")))
        )
        self.ollama_temperature_response: float = float(
            os.getenv("OLLAMA_TEMPERATURE_RESPONSE",
                     str(ollama_config.get("temperature_response", "0.9")))
        )
        
        # Ollama Performance Settings (from .env)
        self.ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE", "24h")
        self.ollama_num_parallel: int = int(os.getenv("OLLAMA_NUM_PARALLEL", "1"))
        self.ollama_max_loaded_models: int = int(os.getenv("OLLAMA_MAX_LOADED_MODELS", "2"))
        self.ollama_context_length: int = int(os.getenv("OLLAMA_CONTEXT_LENGTH", str(ollama_config.get("num_ctx", "8192"))))
        self.ollama_concurrent_requests: int = int(os.getenv("OLLAMA_CONCURRENT_REQUESTS", "1"))
        self.ollama_num_ctx: int = int(os.getenv("OLLAMA_NUM_CTX", str(ollama_config.get("num_ctx", "3000"))))
        
        # Override seed with environment variable if provided
        if os.getenv("OLLAMA_SEED"):
            seed_val = int(os.getenv("OLLAMA_SEED", "-1"))
            self.ollama_seed = seed_val if seed_val != -1 else None
        
        # Memory configuration
        self.max_context_entries: int = memory_config["max_context_entries"]
        self.embedding_search_results: int = memory_config["embedding_search_results"]
        self.base_memory_search_results: int = memory_config["base_memory_search_results"]
        self.auto_summarize_threshold: int = memory_config["auto_summarize_threshold"]
        self.include_base_memory: bool = memory_config["include_base_memory"]
    
        # ====================================================================
        # LOGGING CONTROL VARIABLES - CENTRALIZED
        # ====================================================================
        logging_config = json_config.get("logging", {})
        
        self.LOG_TOOL_EXECUTION: bool = logging_config.get("log_tool_execution", True)
        self.LOG_PROMPT_CONSTRUCTION: bool = logging_config.get("log_prompt_construction", True)
        self.LOG_REACTIVE_PROMPT: bool = logging_config.get("log_reactive_prompt", True)
        self.LOG_REFLECTIVE_PROMPT: bool = logging_config.get("log_reflective_prompt", True)
        self.LOG_PROACTIVE_PROMPT: bool = logging_config.get("log_proactive_prompt", True)
        self.LOG_RESPONSIVE_PROMPT: bool = logging_config.get("log_responsive_prompt", True)
        self.LOG_ACTION_PROMPT: bool = logging_config.get("log_action_prompt", True)
        self.LOG_RESPONSE_PROCESSING: bool = logging_config.get("log_response_processing", True)
        self.LOG_SYSTEM_INFORMATION: bool = logging_config.get("log_system_information", True)
        self.SHOW_CHAT: bool = logging_config.get("show_chat", True)
        
        # ====================================================================

        # Chat Engagement configuration
        chat_engagement_config = json_config.get("chat_engagement", {})
        self.chat_engagement_enabled: bool = chat_engagement_config.get("enabled", True)
        self.chat_engagement_autonomous: bool = chat_engagement_config.get("autonomous", True)
        self.chat_engagement_check_interval: int = chat_engagement_config.get("check_interval", 30)
        self.chat_engagement_max_unengaged: int = chat_engagement_config.get("max_unengaged_messages", 5)
        self.chat_engagement_cooldown: int = chat_engagement_config.get("engagement_cooldown", 60)

        # YouTube configuration
        self.youtube_enabled: bool = youtube_config.get("enabled", False)
        self.youtube_video_id: str = youtube_config.get("video_id", "")
        self.youtube_auto_start: bool = youtube_config.get("auto_start", False)
        self.youtube_max_messages: int = youtube_config.get("max_messages", 10)

        # Twitch configuration
        twitch_config = json_config.get("twitch", {})
        self.twitch_enabled: bool = twitch_config.get("enabled", False)
        self.twitch_channel: str = twitch_config.get("channel", "")
        self.twitch_auto_start: bool = twitch_config.get("auto_start", False)
        self.twitch_max_messages: int = twitch_config.get("max_messages", 10)
        self.twitch_oauth_token: str = twitch_config.get("oauth_token", "")
        self.twitch_nickname: str = twitch_config.get("nickname", "")
        
        # Discord configuration
        self.discord_enabled: bool = discord_config.get('enabled', False)
        self.discord_token: str = discord_config.get('bot_token', '')
        self.discord_command_prefix: str = discord_config.get('command_prefix', '!')
        self.discord_auto_start: bool = discord_config.get('auto_start', False)
        
        # Channel/Guild restrictions
        self.discord_allowed_channels: Optional[List[int]] = (
            discord_config.get('allowed_channels') or None
        )
        self.discord_allowed_guilds: Optional[List[int]] = (
            discord_config.get('allowed_guilds') or None
        )
        
        # Behavioral settings
        self.discord_respond_to_mentions: bool = discord_config.get('respond_to_mentions', False)
        self.discord_respond_to_replies: bool = discord_config.get('respond_to_replies', False)
        self.discord_respond_to_dms: bool = discord_config.get('respond_to_dms', False)
        self.discord_respond_in_threads: bool = discord_config.get('respond_in_threads', False)
        self.discord_typing_indicator: bool = discord_config.get('typing_indicator', True)
        
        # Message handling settings
        self.discord_message_history_limit: int = discord_config.get('message_history_limit', 10)
        self.discord_max_message_length: int = discord_config.get('max_message_length', 2000)
        self.discord_split_long_messages: bool = discord_config.get('split_long_messages', True)
        self.discord_command_cooldown: int = discord_config.get('command_cooldown', 3)
        
        # Check if Discord is actually configured with valid token
        self.IN_DISCORD_CHAT: bool = bool(
            self.discord_enabled and 
            self.discord_token and 
            len(self.discord_token) > 0
        )
        
        # Validation warnings
        if self.discord_enabled and not self.discord_token:
            print("[WARNING] Discord enabled but no bot_token provided in config.json")
        elif self.discord_enabled and self.discord_token == "YOUR_DISCORD_BOT_TOKEN_HERE":
            print("[WARNING] Discord enabled but bot_token is placeholder. Update config.json")
        
        if self.IN_DISCORD_CHAT:
            print(f"[INFO] Discord bot configured: prefix='{self.discord_command_prefix}', auto_start={self.discord_auto_start}")
            if self.discord_allowed_channels:
                print(f"[INFO] Restricted to channels: {self.discord_allowed_channels}")
            if self.discord_allowed_guilds:
                print(f"[INFO] Restricted to guilds: {self.discord_allowed_guilds}")
        
        # Log Ollama performance settings
        print(f"[INFO] Ollama keep_alive: {self.ollama_keep_alive}")
        print(f"[INFO] Ollama max_loaded_models: {self.ollama_max_loaded_models}")
        print(f"[INFO] Ollama context_length: {self.ollama_context_length}")
        
        # Log singleton initialization
        print(f"[Config] Singleton instance created: {id(self)}")

        self._tool_registry = {}
        self._discover_and_register_tools()

    def _discover_and_register_tools(self):
        """
        Auto-discover and register all tools from filesystem
        Creates config attributes AND control variables dynamically
        System works with arbitrary number of tools in installed/ directory
        
        Uses new simplified tool system discovery
        """
        from pathlib import Path
        import json
        import personality.controls as controls
        
        project_root = Path(__file__).parent.parent.parent
        tools_dir = project_root / 'BASE' / 'tools' / 'installed'
        
        if not tools_dir.exists():
            print(f"[Config] [WARNING] Tools directory not found: {tools_dir}")
            return
        
        try:
            created_vars = []
            tool_count = 0
            
            # Discover tools by scanning filesystem
            for tool_dir in tools_dir.iterdir():
                if not tool_dir.is_dir():
                    continue
                
                # Check for required files
                info_file = tool_dir / 'information.json'
                tool_file = tool_dir / 'tool.py'
                
                if not info_file.exists() or not tool_file.exists():
                    continue
                
                # Load metadata
                try:
                    with open(info_file, 'r') as f:
                        info = json.load(f)
                    
                    tool_name = info.get('tool_name')
                    control_var = info.get('control_variable_name')
                    default_value = info.get('control_variable_value', False)
                    
                    if not tool_name or not control_var:
                        print(f"[Config] [WARNING] Invalid tool metadata in {tool_dir.name}")
                        continue
                    
                    # [SUCCESS] CRITICAL: Create control variable if missing
                    if not hasattr(controls, control_var):
                        setattr(controls, control_var, default_value)
                        created_vars.append(f"{control_var}={default_value}")
                    
                    # Register in config registry
                    self._register_tool_config_from_info(
                        tool_name=tool_name,
                        tool_info=info,
                        tool_dir=tool_dir,
                        tool_file=tool_file
                    )
                    
                    tool_count += 1
                    
                except Exception as e:
                    print(f"[Config] [FAILED] Failed to load tool from {tool_dir.name}: {e}")
                    continue
            
            # Log what was created
            if created_vars:
                print(f"[Config] [SUCCESS] Created {len(created_vars)} dynamic control variables:")
                for var in created_vars:
                    print(f"  - {var}")
            
            print(f"[Config] [SUCCESS] Registered {tool_count} tools dynamically")
            
        except Exception as e:
            print(f"[Config] [FAILED] Tool discovery failed: {e}")
            import traceback
            traceback.print_exc()

    def _register_tool_config_from_info(self, tool_name: str, tool_info: dict, 
                                        tool_dir: Path, tool_file: Path):
        """
        Register a single tool in config from information.json
        
        Args:
            tool_name: Tool name
            tool_info: Loaded information.json dict
            tool_dir: Tool directory path
            tool_file: tool.py file path
        """
        control_var = tool_info.get('control_variable_name')
        default_value = tool_info.get('control_variable_value', False)
        
        # Store metadata in registry
        self._tool_registry[tool_name] = {
            'control_variable_name': control_var,
            'default_value': default_value,
            'display_name': tool_info.get('metadata', {}).get(
                'display_name', 
                tool_name.replace('_', ' ').title()
            ),
            'category': tool_info.get('metadata', {}).get('category', 'Other Tools'),
            'description': tool_info.get('tool_description', ''),
            'timeout': tool_info.get('timeout_seconds', 30),
            'cooldown': tool_info.get('cooldown_seconds', 0),
            'commands': tool_info.get('available_commands', []),
            'usage_examples': tool_info.get('tool_usage_examples', []),
            'tool_directory': str(tool_dir),
            'module_path': str(tool_file),
        }
        
        # Create config attribute
        config_attr = f'tool_{tool_name}_enabled'
        if not hasattr(self, config_attr):
            setattr(self, config_attr, default_value)

    def _register_tool_config(self, tool_info):
        """
        Register a single tool in config
        FIXED: Updated for new ToolInfo structure (no tool_class_name)
        
        Args:
            tool_info: ToolInfo object with metadata
        """
        control_var = tool_info.control_variable_name
        
        # Get default value from metadata
        default_value = tool_info.control_variable_value  # Direct from ToolInfo
        
        tool_name = tool_info.tool_name
        
        # Store metadata in registry
        self._tool_registry[tool_name] = {
            'control_variable_name': control_var,
            'default_value': default_value,
            'display_name': tool_info.metadata.get(
                'display_name', 
                tool_name.replace('_', ' ').title()
            ),
            'category': tool_info.metadata.get('category', 'Other Tools'),
            'description': tool_info.tool_description,
            'timeout': tool_info.metadata.get('timeout_seconds', 30),
            'cooldown': tool_info.metadata.get('cooldown_seconds', 0),
            'commands': tool_info.metadata.get('available_commands', []),
            'usage_examples': tool_info.metadata.get('tool_usage_examples', []),
            'tool_directory': tool_info.tool_directory,
            'module_path': tool_info.module_path,
        }
        
        config_attr = f'tool_{tool_name}_enabled'
        if not hasattr(self, config_attr):
            setattr(self, config_attr, default_value)

    def sync_control_variables_with_defaults(self, controls_module):
        """
        Sync all tool control variables with their information.json defaults
        Useful for resetting tools to default state
        
        Args:
            controls_module: The personality.controls module
        """
        for tool_name, tool_meta in self._tool_registry.items():
            control_var = tool_meta['control_variable_name']
            default_value = tool_meta['default_value']
            
            # Only sync if variable exists (should always exist after _discover_and_register_tools)
            if hasattr(controls_module, control_var):
                current_value = getattr(controls_module, control_var)
                if current_value != default_value:
                    setattr(controls_module, control_var, default_value)
                    print(f"[Config] Reset {control_var}: {current_value} -> {default_value}")

    def get_tool_registry(self) -> Dict[str, Dict]:
        """
        Get all registered tool metadata
        
        Returns:
            Dict mapping tool names to metadata dicts
        """
        return self._tool_registry.copy()
    
    def get_tool_config(self, tool_name: str) -> Optional[Dict]:
        """
        Get config for specific tool
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Tool metadata dict or None
        """
        return self._tool_registry.get(tool_name)
    
    # === GAME STATE HELPERS ===
    
    def is_playing_minecraft(self, controls_module) -> bool:
        """Check if Minecraft is currently active (dynamic check)"""
        return getattr(controls_module, 'PLAYING_MINECRAFT', False)
    
    def is_playing_league(self, controls_module) -> bool:
        """Check if League of Legends is currently active (dynamic check)"""
        return getattr(controls_module, 'PLAYING_LEAGUE', False)
    
    # === SYNCHRONIZATION ===
    
    def sync_with_controls(self, controls_module):
        """
        Synchronize config with live controls module
        
        This ensures that config values stay aligned with dynamically
        updated control variables from GUI toggles.
        
        Args:
            controls_module: The live personality.controls module
        """
        # Sync logging controls FROM controls TO config
        logging_controls = [
            'LOG_TOOL_EXECUTION', 'LOG_PROMPT_CONSTRUCTION',
            'LOG_RESPONSE_PROCESSING', 'LOG_SYSTEM_INFORMATION', 'SHOW_CHAT',
            'LOG_REACTIVE_PROMPT', 'LOG_REFLECTIVE_PROMPT', 'LOG_PROACTIVE_PROMPT',
            'LOG_RESPONSIVE_PROMPT', 'LOG_ACTION_PROMPT', 'LOG_CODING_EXECUTION',
            'LOG_DISCORD_EXECUTION', 'LOG_MINECRAFT_EXECUTION'
        ]
        
        for control_name in logging_controls:
            if hasattr(controls_module, control_name):
                control_value = getattr(controls_module, control_name)
                setattr(self, control_name, control_value)
    
    def get_active_tools(self, controls_module) -> dict:
        """
        Get currently active tools based on LIVE control values
        
        This should be called each time tool status is needed,
        not cached, to ensure GUI toggles are respected.
        
        Args:
            controls_module: The live personality.controls module
            
        Returns:
            Dict of tool names to their active status
        """
        return {
            'coding': controls_module.USE_CODING,
            'game': controls_module.PLAYING_GAME,
            'twitch': getattr(controls_module, 'IN_TWITCH_CHAT', False),
            'youtube': getattr(controls_module, 'IN_YOUTUBE_CHAT', False),
            'discord': getattr(controls_module, 'IN_DISCORD_CHAT', False),
            'memory_short': controls_module.USE_SHORT_MEMORY,
            'memory_long': controls_module.USE_LONG_MEMORY,
            'memory_base': controls_module.USE_BASE_MEMORY,
            'content_filter': controls_module.ENABLE_CONTENT_FILTER,
            'ai_filter': controls_module.USE_AI_CONTENT_FILTER,
            'speech': controls_module.AVATAR_SPEECH,
            'intelligent_tools': controls_module.INTELLIGENT_TOOL_SELECTION,
            'continuous_thinking': getattr(controls_module, 'ENABLE_CONTINUOUS_THINKING', False),
            'SLOW_MODE': getattr(controls_module, 'SLOW_MODE', True),
        }
    
    # === SAFE ACCESSOR ===
    def get(self, key: str, default=None):
        """
        Safe universal getter for backward compatibility.

        Allows attribute-style or key-style access to config values.
        Example:
            self.config.get("twitch_channel")
        is equivalent to:
            self.config.twitch_channel

        Args:
            key (str): The config key name (case-insensitive)
            default: Value to return if not found
        """
        # Try exact attribute
        if hasattr(self, key):
            return getattr(self, key)

        # Try lowercase match (for case-insensitive access)
        lower_key = key.lower()
        for attr in dir(self):
            if attr.lower() == lower_key:
                return getattr(self, attr)

        # Fallback to default
        return default