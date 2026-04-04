# Filename: BASE/core/control_manager.py
"""
Control Manager - Dynamic Control Variable Management
ENHANCED: Individual internal tool toggles with automatic mutual exclusivity
"""
from typing import Optional, Dict, Any
import asyncio

class ControlManager:
    """
    Manages runtime control of agent features
    
    Features:
    - Tool controls (USE_WIKI_SEARCH, etc.) → notify tool manager
    - Feature flags (USE_SYSTEM_PROMPT, etc.) → internal only
    - Internal tool controls (USE_XTTS, USE_PYTTSX3, etc.) → notify internal tool manager
    - Automatic mutual exclusivity for same-category tools
    """
    __slots__ = (
        'controls_module', 'logger', 'config',
        '_ai_core_ref', '_tool_manager_ref', '_defaults',
        '_tool_control_vars', '_internal_tool_categories'
    )
    
    # Define internal tool categories and their controls
    TTS_TOOLS = {'USE_XTTS', 'USE_PYTTSX3'}
    VOICE_INPUT_TOOLS = {'USE_WHISPER'}
    
    def __init__(self, controls_module, logger, config=None):
        """Initialize control manager"""
        self.controls_module = controls_module
        self.logger = logger
        self.config = config
        
        self._ai_core_ref = None
        self._tool_manager_ref = None
        
        # Cache of actual tool control variables
        self._tool_control_vars = set()
        
        # Build internal tool category map
        self._internal_tool_categories = {
            'tts': self.TTS_TOOLS,
            'voice_input': self.VOICE_INPUT_TOOLS
        }
        
        # Verify config instance
        if config is not None and hasattr(logger, 'config') and logger.config is not None:
            if id(config) != id(logger.config):
                error_msg = (
                    f"CRITICAL: Config instance mismatch!\n"
                    f"  ControlManager config: {id(config)}\n"
                    f"  Logger config: {id(logger.config)}\n"
                    f"These MUST be the same instance!"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            else:
                logger.system(
                    f"[ControlManager] [SUCCESS] Config instance verified: {id(config)}"
                )
        
        # Store defaults
        self._defaults = self._capture_defaults()
    
    def _capture_defaults(self) -> Dict[str, Any]:
        """Capture current control values as defaults"""
        defaults = {}
        for attr in dir(self.controls_module):
            if attr.isupper() and not attr.startswith('_'):
                defaults[attr] = getattr(self.controls_module, attr)
        return defaults
    
    # ========================================================================
    # DEPENDENCY INJECTION
    # ========================================================================
    
    def set_ai_core(self, ai_core):
        """Inject AI core reference"""
        self._ai_core_ref = ai_core
        self.logger.system("[ControlManager] AI Core reference set")
    
    def set_tool_manager(self, tool_manager):
        """Inject tool manager and discover tool controls"""
        self._tool_manager_ref = tool_manager
        
        if not tool_manager:
            self.logger.system("[ControlManager] Tool manager reference set")
            return
        
        # Discover tool controls
        try:
            all_metadata = tool_manager.get_all_tool_metadata()
            
            for tool_name, metadata in all_metadata.items():
                control_var = metadata.get('control_variable_name')
                
                if control_var:
                    self._tool_control_vars.add(control_var)
                    if self.logger:
                        self.logger.system(
                            f"[Control Manager] Registered tool control: {control_var} → {tool_name}"
                        )
            
            if self._tool_control_vars:
                self.logger.system(
                    f"[Control Manager] Tracking {len(self._tool_control_vars)} tool controls"
                )
        
        except Exception as e:
            self.logger.error(f"[Control Manager] Failed to discover tool controls: {e}")
        
        self.logger.system("[ControlManager] Tool manager reference set")
    
    def _is_tool_control(self, control_name: str) -> bool:
        """Check if control is for an external tool"""
        return control_name in self._tool_control_vars
    
    def _is_internal_tool_control(self, control_name: str) -> bool:
        """Check if control is for an internal tool"""
        all_internal = set()
        for tools in self._internal_tool_categories.values():
            all_internal.update(tools)
        return control_name in all_internal
    
    def _get_tool_category(self, control_name: str) -> Optional[str]:
        """Get category of internal tool control"""
        for category, tools in self._internal_tool_categories.items():
            if control_name in tools:
                return category
        return None
    
    # ========================================================================
    # MUTUAL EXCLUSIVITY ENFORCEMENT
    # ========================================================================
    
    def _enforce_mutual_exclusivity(self, control_name: str, new_value: bool):
        """
        Enforce mutual exclusivity for internal tools
        
        When enabling a tool, disable all other tools in the same category
        """
        if not new_value:
            # Disabling a tool doesn't require exclusivity enforcement
            return
        
        category = self._get_tool_category(control_name)
        if not category:
            return
        
        # Get all tools in this category
        category_tools = self._internal_tool_categories.get(category, set())
        
        # Disable all other tools in this category
        for other_tool in category_tools:
            if other_tool != control_name:
                old_value = getattr(self.controls_module, other_tool, False)
                if old_value:
                    self.logger.system(
                        f"[Mutual Exclusivity] Disabling {other_tool} to enable {control_name}"
                    )
                    setattr(self.controls_module, other_tool, False)
                    
                    # Notify internal tool manager of the disable
                    if self._ai_core_ref and hasattr(self._ai_core_ref, 'internal_tool_manager'):
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                loop.run_until_complete(
                                    self._ai_core_ref.handle_control_change(other_tool, False)
                                )
                            finally:
                                loop.close()
                        except Exception as e:
                            self.logger.warning(f"Failed to disable {other_tool}: {e}")
    
    # ========================================================================
    # SPECIAL HANDLERS
    # ========================================================================
    
    def handle_continuous_thinking_toggle(self, new_value: bool) -> bool:
        """Handle toggling of continuous thinking"""
        if not self._ai_core_ref:
            self.logger.error("[Continuous Thinking] No AI Core reference")
            return False
        
        ai_core = self._ai_core_ref
        
        if not hasattr(ai_core, 'processing_delegator') or not ai_core.processing_delegator:
            self.logger.error("[Continuous Thinking] No processing delegator")
            return False
        
        thought_processor = ai_core.processing_delegator.thought_processor
        
        if new_value:
            # START continuous thinking
            if thought_processor.cognitive_loop and thought_processor.cognitive_loop.is_running:
                self.logger.system("[Continuous Thinking] Already running")
                return True
            
            try:
                thought_processor.event_loop = ai_core.main_loop
                thought_processor.set_ai_core_reference(ai_core)
                thought_processor.start_continuous_thinking()
                
                self.logger.system("[SUCCESS] [Continuous Thinking] STARTED")
                return True
                
            except Exception as e:
                self.logger.error(f"[Continuous Thinking] Failed to start: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        else:
            # STOP continuous thinking
            if not thought_processor.cognitive_loop or not thought_processor.cognitive_loop.is_running:
                self.logger.system("[Continuous Thinking] Already stopped")
                return True
            
            try:
                asyncio.run_coroutine_threadsafe(
                    thought_processor.cognitive_loop.stop_continuous_loop(),
                    ai_core.main_loop
                )
                
                self.logger.system("[Continuous Thinking] STOPPED")
                return True
                
            except Exception as e:
                self.logger.error(f"[Continuous Thinking] Failed to stop: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    def handle_internal_tool_toggle(self, control_name: str, new_value: bool) -> bool:
        """
        Handle internal tool toggle with mutual exclusivity
        
        Args:
            control_name: Control variable name (e.g., 'USE_XTTS')
            new_value: New state
            
        Returns:
            True if successful
        """
        if not self._ai_core_ref:
            self.logger.error(f"[{control_name}] No AI Core reference")
            return False
        
        # Check if internal tool manager is available
        if not hasattr(self._ai_core_ref, 'internal_tool_manager') or not self._ai_core_ref.internal_tool_manager:
            self.logger.warning(f"[{control_name}] Internal tool manager not available")
            return False
        
        category = self._get_tool_category(control_name)
        
        if new_value:
            self.logger.system(f"[{control_name}] Enabling {category} tool")
            
            # Enforce mutual exclusivity BEFORE setting the new value
            self._enforce_mutual_exclusivity(control_name, new_value)
        else:
            self.logger.system(f"[{control_name}] Disabling {category} tool")
        
        # Update control variable
        setattr(self.controls_module, control_name, new_value)
        
        # Sync legacy variables for backwards compatibility
        self._sync_legacy_variables()
        
        # Notify internal tool manager
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self._ai_core_ref.handle_control_change(control_name, new_value)
                )
                
                # Verify the result
                if category == 'tts':
                    tts_tool = self._ai_core_ref.internal_tool_manager.get_active_tts_tool()
                    if tts_tool and new_value:
                        info = tts_tool.get_voice_info()
                        self.logger.success(
                            f"[{control_name}] Active TTS: {info.get('name')} ({info.get('type')})"
                        )
                        return True
                    elif not new_value:
                        return True  # Successfully disabled
                    else:
                        self.logger.warning(f"[{control_name}] No TTS tool active after enable")
                        return False
                
                elif category == 'voice_input':
                    voice_tool = self._ai_core_ref.internal_tool_manager.get_active_voice_input_tool()
                    if voice_tool and new_value:
                        self.logger.success(f"[{control_name}] Active voice input: {voice_tool.tool_name}")
                        return True
                    elif not new_value:
                        return True  # Successfully disabled
                    else:
                        self.logger.warning(f"[{control_name}] No voice input tool active after enable")
                        return False
                
                return True
                    
            finally:
                loop.close()
        
        except Exception as e:
            self.logger.error(f"[{control_name}] Toggle failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _sync_legacy_variables(self):
        """
        Sync legacy control variables for backwards compatibility
        
        Updates:
        - USE_CUSTOM_VOICE based on USE_XTTS
        - USE_GPU_VOICE based on USE_WHISPER
        - AVATAR_SPEECH based on any TTS tool enabled
        """
        # Sync USE_CUSTOM_VOICE with USE_XTTS
        use_xtts = getattr(self.controls_module, 'USE_XTTS', False)
        setattr(self.controls_module, 'USE_CUSTOM_VOICE', use_xtts)
        
        # Sync USE_GPU_VOICE with USE_WHISPER
        use_whisper = getattr(self.controls_module, 'USE_WHISPER', False)
        setattr(self.controls_module, 'USE_GPU_VOICE', use_whisper)
        
        # Sync AVATAR_SPEECH with any TTS tool enabled
        any_tts_enabled = any(
            getattr(self.controls_module, tool, False)
            for tool in self.TTS_TOOLS
        )
        setattr(self.controls_module, 'AVATAR_SPEECH', any_tts_enabled)
    
    # ========================================================================
    # MAIN UPDATE METHOD
    # ========================================================================
    
    def update_control(self, control_variable_name: str, new_value: bool) -> bool:
        """
        Update a control variable and handle side effects
        
        Args:
            control_variable_name: Name of control variable
            new_value: New boolean value
            
        Returns:
            True if update succeeded
        """
        if not hasattr(self.controls_module, control_variable_name):
            self.logger.error(f"[Control] Unknown feature: {control_variable_name}")
            return False
        
        old_value = getattr(self.controls_module, control_variable_name)
        
        # Special handling for specific controls
        if control_variable_name == 'ENABLE_CONTINUOUS_THINKING':
            success = self.handle_continuous_thinking_toggle(new_value)
            if success:
                setattr(self.controls_module, control_variable_name, new_value)
            return success
        
        # Handle internal tool controls
        elif self._is_internal_tool_control(control_variable_name):
            return self.handle_internal_tool_toggle(control_variable_name, new_value)
        
        # Logging controls (sync BOTH config and controls)
        elif control_variable_name in ['LOG_TOOL_EXECUTION', 'LOG_PROMPT_CONSTRUCTION', 
                            'LOG_RESPONSE_PROCESSING', 'LOG_SYSTEM_INFORMATION', 'SHOW_CHAT',
                            'LOG_REACTIVE_PROMPT', 'LOG_REFLECTIVE_PROMPT', 'LOG_PROACTIVE_PROMPT',
                            'LOG_RESPONSIVE_PROMPT', 'LOG_ACTION_PROMPT', 'LOG_CODING_EXECUTION',
                            'LOG_DISCORD_EXECUTION', 'LOG_MINECRAFT_EXECUTION']:
            # Update controls module
            setattr(self.controls_module, control_variable_name, new_value)
            
            # Update config (for logger to see)
            if self.config:
                setattr(self.config, control_variable_name, new_value)
                self.logger.system(f"[Control] {control_variable_name} = {new_value}")
                return True
            else:
                self.logger.warning(f"[Control] No config - cannot update {control_variable_name}")
                return False
        
        # Regular control update
        setattr(self.controls_module, control_variable_name, new_value)
        self.logger.system(f"[Control] {control_variable_name}: {old_value} → {new_value}")
        
        # Notify tool manager if this is a tool control
        if self._is_tool_control(control_variable_name):
            self.logger.system(
                f"[Control] {control_variable_name} is a tool control - notifying tool manager"
            )
            
            if self._tool_manager_ref:
                try:
                    self._tool_manager_ref.handle_control_update(control_variable_name, new_value)
                except Exception as e:
                    self.logger.warning(f"Tool manager notification failed: {e}")
            else:
                self.logger.warning(
                    f"[Control] Tool manager not available for {control_variable_name}"
                )
        else:
            self.logger.system(
                f"[Control] Internal feature flag - no tool lifecycle needed"
            )
        
        return True
    
    # ========================================================================
    # STATUS
    # ========================================================================
    
    def get_all_controls(self) -> Dict[str, bool]:
        """Get all control variables and their current values"""
        controls = {}
        
        # Regular controls
        for attr in dir(self.controls_module):
            if attr.isupper() and not attr.startswith('_'):
                value = getattr(self.controls_module, attr)
                if isinstance(value, bool):
                    controls[attr] = value
        
        # Logging controls from config
        if self.config:
            logging_controls = {
                'LOG_TOOL_EXECUTION', 'LOG_PROMPT_CONSTRUCTION',
                'LOG_RESPONSE_PROCESSING', 'LOG_SYSTEM_INFORMATION', 'SHOW_CHAT'
            }
            for ctrl in logging_controls:
                if hasattr(self.config, ctrl):
                    controls[ctrl] = getattr(self.config, ctrl)
        
        return controls
    
    def get_internal_tool_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all internal tools"""
        status = {}
        
        for category, tools in self._internal_tool_categories.items():
            category_status = {
                'category': category,
                'tools': {}
            }
            
            active_tool = None
            for tool_control in tools:
                enabled = getattr(self.controls_module, tool_control, False)
                category_status['tools'][tool_control] = enabled
                
                if enabled:
                    active_tool = tool_control
            
            category_status['active'] = active_tool
            status[category] = category_status
        
        return status
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get control manager statistics"""
        all_features = self.get_all_controls()
        enabled_count = sum(1 for v in all_features.values() if v is True)
        
        return {
            'total_controls': len(all_features),
            'enabled_count': enabled_count,
            'disabled_count': len(all_features) - enabled_count,
            'tool_controls_tracked': len(self._tool_control_vars),
            'internal_tools': self.get_internal_tool_status()
        }