# Filename: BASE/core/ai_core.py
"""
AI Core - Main Orchestration
REFACTORED: Integrated internal tool manager for modular voice services
COMPLETE: All original functionality preserved
"""
from typing import Optional, Dict, Any, List
from pathlib import Path
import asyncio
import time
import threading

from BASE.core.core_initializer import CoreInitializer
from BASE.core.logger import Logger
from BASE.core.config import Config
from BASE.handlers.content_filter import ContentFilter

from BASE.config.controls import KILL_COMMAND

class AICore:
    """Main AI backend orchestrator with modular internal tools"""
    
    __slots__ = (
        'config', 'controls', 'project_root', 'gui_logger', 'logger',
        'shutdown_flag', 'speech_stop_flag', 'main_loop', '_loop_thread',
        'memory_manager', 'memory_search', 'session_file_manager',
        'processing_delegator', 'control_manager', 'tts_tool',
        'discord_integration', 'youtube_chat', 'twitch_chat', 'chat_handler',
        'last_reminder_cleanup', 'reminder_cleanup_interval', 'initializer',
        'content_filter', 'action_state_manager', 'instruction_persistence_manager',
        'tool_manager', 'streaming_enabled', 'hot_reload_manager',
        'core_hot_reload', 'tool_hot_reload', 'internal_tool_manager'
    )
    
    def __init__(self, config, controls_module, project_root=None, gui_logger=None):
        """Initialize AI system with modular internal tools"""
        # ===================================================================
        # STEP 1: Store singleton references
        # ===================================================================
        self.config = config
        self.config.ai_core = self
        self.controls = controls_module
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.gui_logger = gui_logger
        
        # ===================================================================
        # STEP 2: Create Logger WITH config reference immediately
        # ===================================================================
        self.logger = Logger(
            name="Core",
            gui_callback=gui_logger,
            config=self.config
        )
        
        if not hasattr(self.logger, 'config') or self.logger.config is None:
            raise RuntimeError("CRITICAL: Logger config not set during initialization!")
        
        if id(self.logger.config) != id(self.config):
            raise RuntimeError(
                f"CRITICAL: Logger has different config instance!\n"
                f"  AICore config: {id(self.config)}\n"
                f"  Logger config: {id(self.logger.config)}"
            )
        
        self.logger.system(f"[Init] Config instance: {id(self.config)}")
        self.logger.system(f"[Init] Logger config instance: {id(self.logger.config)}")
        self.logger.system("[Init] [SUCCESS] Single config instance verified")
        
        # ===================================================================
        # STEP 2.5: Initialize Dynamic Tool Control Variables
        # ===================================================================
        from BASE.core.dynamic_control_initializer import DynamicControlInitializer
        
        self.logger.system("[Init] Initializing dynamic tool control variables...")
        
        control_initializer = DynamicControlInitializer(
            project_root=self.project_root,
            controls_module=controls_module,
            logger=self.logger
        )
        
        initialized_count = control_initializer.initialize_all_controls()
        
        self.logger.success(
            f"[Init] Dynamic tool controls initialized: {initialized_count} variables"
        )
        
        # ===================================================================
        # STEP 3: Setup event loop and flags
        # ===================================================================
        self.shutdown_flag = threading.Event()
        self.speech_stop_flag = threading.Event()
        
        self.main_loop = None
        self._loop_thread = None
        self._start_event_loop()
        
        self.tts_tool = None
        
        self.discord_integration = None
        self.youtube_chat = None
        self.twitch_chat = None
        self.chat_handler = None
        
        self.last_reminder_cleanup = 0
        self.reminder_cleanup_interval = 60
        
        # ===================================================================
        # STEP 4: Initialize via CoreInitializer
        # ===================================================================
        self.logger.system("Initializing AI Core...")
        self.initializer = CoreInitializer(
            ai_core=self,
            config=self.config,
            controls=controls_module,
            project_root=self.project_root,
            logger=self.logger,
            main_loop=self.main_loop
        )

        self.initializer.initialize_all_systems()

        # ===================================================================
        # STEP 5: Extract ALL initialized components
        # ===================================================================
        self.memory_manager = self.initializer.memory_manager
        self.memory_search = self.initializer.memory_search
        self.session_file_manager = self.initializer.session_file_manager
        self.action_state_manager = self.initializer.action_state_manager
        self.instruction_persistence_manager = self.initializer.instruction_persistence_manager
        self.processing_delegator = self.initializer.processing_delegator
        self.control_manager = self.initializer.control_manager
        self.tool_manager = self.initializer.tool_manager
        
        # ===================================================================
        # STEP 5.5: Initialize Internal Tool Manager (NEW)
        # ===================================================================
        self.internal_tool_manager = None
        self._init_internal_tools()

        # ===================================================================
        # STEP 6: HOT-RELOAD SYSTEMS
        # ===================================================================
        if getattr(controls_module, 'ENABLE_TOOL_HOT_RELOAD', False):
            from BASE.core.tool_hot_reload_manager import HotReloadManager as ToolHotReloadManager
            
            self.tool_hot_reload = ToolHotReloadManager(
                project_root=self.project_root,
                logger=self.logger,
                config=self.config
            )
            
            self.tool_hot_reload.register_tool_manager(self.tool_manager)
            
            # self.logger.system("[Hot Reload] Tool hot-reloading ENABLED (GUI reload buttons active)")
        else:
            self.tool_hot_reload = None
            # self.logger.system("[Hot Reload] Tool hot-reloading DISABLED")

        if getattr(controls_module, 'ENABLE_CORE_HOT_RELOAD', False):
            from BASE.core.core_hot_reload_manager import CoreHotReloadManager
            
            # self.logger.system("[Hot Reload] Initializing core hot-reload manager...")
            
            self.core_hot_reload = CoreHotReloadManager(
                project_root=self.project_root,
                logger=self.logger
            )
            
            # self.logger.system(f"[Hot Reload] Manager created, enabled={self.core_hot_reload.enabled}")
            
            self.logger.system("[Hot Reload] Registering thought processor constructors...")
            self.processing_delegator.thought_processor.set_hot_reload_manager(self.core_hot_reload)
            
            self.logger.system("[Hot Reload] Registering processing delegator constructor...")
            self.processing_delegator.set_hot_reload_manager(self.core_hot_reload)
            
            self.logger.system(f"[Hot Reload] Registered modules: {len(self.core_hot_reload.modules)}")
            # for name, module in self.core_hot_reload.modules.items():
                # self.logger.system(f"[Hot Reload]   - {name}: {module.file_path.name}")
            
            # self.logger.system("[Hot Reload] Starting file watcher...")
            self.core_hot_reload.start_watching()
            
            if self.core_hot_reload.observer:
                self.logger.system("[Hot Reload] Observer started successfully")
            else:
                self.logger.warning("[Hot Reload] Observer failed to start!")
            
            # self.logger.system("[Hot Reload] Core module hot-reloading ENABLED (prompt constructors)")
        else:
            self.core_hot_reload = None
            # self.logger.system("[Hot Reload] Core hot-reloading DISABLED")

        if self.tool_hot_reload or self.core_hot_reload:
            systems = []
            if self.tool_hot_reload:
                systems.append("tools")
            if self.core_hot_reload:
                systems.append("core")
            # self.logger.system(f"[Hot Reload] Active systems: {', '.join(systems)}")
        
        self.logger.system("[Init] AI Core initialization complete")

        self.content_filter = ContentFilter(
            ollama_endpoint=config.ollama_endpoint,
            use_ai_filter=controls_module.USE_AI_CONTENT_FILTER
        )
        
        self.logger.system("[Init] AI Core initialization complete")
    
    # ========================================================================
    # INTERNAL TOOL MANAGER (NEW)
    # ========================================================================
    
    def _init_internal_tools(self):
        """Initialize internal tool manager for modular voice services"""
        try:
            from BASE.handlers.internal_tool_manager import InternalToolManager
            
            self.logger.system("[Internal Tools] Initializing modular tool system...")
            
            self.internal_tool_manager = InternalToolManager(
                project_root=self.project_root,
                config=self.config,
                controls=self.controls,
                logger=self.logger
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.internal_tool_manager.discover_and_initialize()
                )
            finally:
                loop.close()
            
            self._setup_tts_from_internal_tools()
            
            status = self.internal_tool_manager.get_status()
            self.logger.success(
                f"[Internal Tools] System ready - "
                f"{status['active_tools']} active tools"
            )
            
            for category, tool_name in status['active_by_category'].items():
                self.logger.system(f"[Internal Tools]   {category}: {tool_name}")
        
        except Exception as e:
            self.logger.error(f"[Internal Tools] Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            self.internal_tool_manager = None
    
    def _setup_tts_from_internal_tools(self):
        """Setup TTS tool reference from internal tool manager"""
        if not self.internal_tool_manager:
            return
        
        tts_tool = self.internal_tool_manager.get_active_tts_tool()
        
        if tts_tool:
            self.tts_tool = tts_tool
            info = tts_tool.get_voice_info()
            self.logger.success(
                f"[TTS] Active: {info.get('name')} ({info.get('type')})"
            )
        else:
            self.logger.warning("[TTS] No TTS tool active")
    
    async def handle_control_change(self, control_name: str, new_value):
        """Handle control variable changes for internal tools"""
        if self.internal_tool_manager:
            await self.internal_tool_manager.handle_control_change(control_name, new_value)
            
            if control_name in ['USE_CUSTOM_VOICE', 'USE_GPU_VOICE']:
                self._setup_tts_from_internal_tools()
    
    def setup_tts_tool(self, tts_tool):
        """DEPRECATED: For backwards compatibility only"""
        self.logger.warning("[TTS] setup_tts_tool() is deprecated - use internal tool manager")
        self.tts_tool = tts_tool
    
    # ========================================================================
    # CONFIG VERIFICATION
    # ========================================================================
    
    def _verify_config_propagation(self):
        """Verify all components reference the same config instance"""
        base_config_id = id(self.config)
        
        checks = {
            'logger': (self.logger.config, 'Logger'),
            'control_manager': (self.control_manager.config if hasattr(self.control_manager, 'config') else None, 'ControlManager'),
        }
        
        failures = []
        for component_name, (component_config, display_name) in checks.items():
            if component_config is None:
                self.logger.warning(f"[Config Check] {display_name} has no config reference")
                continue
            
            component_id = id(component_config)
            if component_id != base_config_id:
                failures.append(
                    f"  - {display_name}: {id(component_config)} != {base_config_id}"
                )
        
        if failures:
            error_msg = (
                "CRITICAL: Config instance mismatch detected!\n" +
                "\n".join(failures)
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        self.logger.system("[Config Check] [SUCCESS] All components share same config instance")
        self.logger.system("Summarizing past day's conversations to long-term memory. This may take a moment...")
    
    # ========================================================================
    # EVENT LOOP MANAGEMENT
    # ========================================================================
    
    def _start_event_loop(self):
        """Start dedicated event loop for async processing"""
        def run_loop():
            self.main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.main_loop)
            self.main_loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True, name="AICore_EventLoop")
        self._loop_thread.start()
        
        timeout, start_time = 5.0, time.time()
        while self.main_loop is None and (time.time() - start_time) < timeout:
            time.sleep(0.01)
        
        if self.main_loop:
            self.logger.system("Event loop initialized")
        else:
            self.logger.error("Failed to initialize event loop")
    
    def _stop_event_loop(self):
        """Stop the event loop"""
        if self.main_loop and self.main_loop.is_running():
            self.main_loop.call_soon_threadsafe(self.main_loop.stop)
            if self._loop_thread:
                self._loop_thread.join(timeout=2.0)
            self.logger.system("Event loop stopped")
    
    # ========================================================================
    # INTEGRATION LIFECYCLE
    # ========================================================================
    
    def start_integrations(self):
        """Start all external integrations"""
        self.logger.system("Integrations started")
    
    def shutdown(self):
        """Gracefully shutdown all systems"""
        self.logger.system("Starting IMMEDIATE shutdown...")
        self.shutdown_flag.set()
        self.speech_stop_flag.set()
        
        # Stop hot-reload managers
        if hasattr(self, 'core_hot_reload') and self.core_hot_reload:
            try:
                self.core_hot_reload.stop_watching()
                self.logger.system("Stopped core hot-reload manager")
            except Exception as e:
                self.logger.warning(f"Error stopping core hot-reload: {e}")
        
        # Stop cognitive loop FIRST
        try:
            thought_processor = self.processing_delegator.thought_processor
            thought_buffer = thought_processor.thought_buffer
            thought_buffer.force_shutdown()
            
            if hasattr(thought_processor, 'cognitive_loop'):
                loop_manager = thought_processor.cognitive_loop
                if loop_manager and loop_manager.is_running:
                    if self.main_loop and self.main_loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            loop_manager.stop_continuous_loop(), self.main_loop
                        )
                        time.sleep(0.5)
            
            self.logger.system("Stopped cognitive loop")
        except Exception as e:
            self.logger.warning(f"Error stopping cognitive loop: {e}")
        
        # Stop chat handler
        if hasattr(self, 'chat_handler') and self.chat_handler:
            try:
                self.chat_handler.shutdown()
            except Exception as e:
                self.logger.warning(f"Error stopping chat handler: {e}")
        
        # Stop Discord
        if self.discord_integration and self.discord_integration.running:
            try:
                self.discord_integration.stop()
                self.logger.discord("Stopped")
            except Exception as e:
                self.logger.warning(f"Error stopping Discord: {e}")
        
        # Stop internal tools
        if self.internal_tool_manager:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.internal_tool_manager.cleanup_all())
            finally:
                loop.close()
        
        # Stop TTS (legacy)
        if self.tts_tool:
            try:
                self.tts_tool.stop()
            except:
                pass
        
        # Stop event loop
        self._stop_event_loop()
        
        self.logger.system("Shutdown complete")
    
    # ========================================================================
    # MAIN API - USER INTERACTION
    # ========================================================================
    
    async def process_user_message(
        self, message: str, source: str = "GUI", user_id: str = "local_user",
        is_image_message: bool = False, image_path: Optional[Path] = None,
        timestamp: Optional[float] = None, username_override: Optional[str] = None
    ) -> Optional[str]:
        """Main entry point for processing user messages"""
        
        # Kill command check
        if message and isinstance(message, str):
            if self._check_kill_command(message):
                self.logger.system("[Kill Command] Initiating shutdown")
                self.shutdown_flag.set()
                return "Shutting down immediately..."
        
        if self.shutdown_flag.is_set():
            return None
        
        # Normalize empty messages
        if message and not message.strip():
            message = ""
        
        # Input filtering
        if message and message.strip() and getattr(self.controls, 'ENABLE_CONTENT_FILTER', True):
            cleaned_message, was_filtered, reason = self.content_filter.filter_incoming(
                message, log_callback=self.logger.system
            )
            if was_filtered:
                self.logger.system(f"[Filter Input] {reason}")
            message = cleaned_message
        
        # Periodic cleanup
        if hasattr(self, 'action_state_manager') and self.action_state_manager:
            self.action_state_manager.cleanup_old_actions()
        self._cleanup_old_reminders()
        
        # Build context
        context_parts = self._build_context(user_text=message)
        
        # Process via delegator
        try:
            reply = await self.processing_delegator.process_user_input(
                user_input=message, source=source, user_id=user_id,
                is_image_message=is_image_message, image_path=image_path,
                timestamp=timestamp, username_override=username_override,
                context_parts=context_parts
            )
            
            # Output filtering
            if reply and getattr(self.controls, 'ENABLE_CONTENT_FILTER', True):
                cleaned_reply, was_filtered, reason = self.content_filter.filter_outgoing(
                    reply, log_callback=self.logger.system
                )
                if was_filtered:
                    self.logger.system(f"[Filter Output] {reason}")
                reply = cleaned_reply
            
            # Save to memory
            if reply and self.controls.SAVE_MEMORY:
                self.memory_manager.save_bot_response(reply)
                self.logger.memory("Saved bot response to memory")
            
            # Broadcast to group chat if enabled
            if reply and getattr(self.controls, 'IN_GROUP_CHAT', False):
                if hasattr(self, 'tool_manager') and self.tool_manager:
                    import asyncio
                    
                    tool_ready = await self.tool_manager.wait_for_tool_ready(
                        'group_chat',
                        timeout=2.0
                    )
                    
                    if tool_ready:
                        group_chat_tool = self.tool_manager._active_tools.get('group_chat')
                        if group_chat_tool and hasattr(group_chat_tool, 'broadcast_spoken_response'):
                            try:
                                result = group_chat_tool.broadcast_spoken_response(reply)
                                if result:
                                    self.logger.success(f"[Group Chat] Broadcast successful")
                                else:
                                    self.logger.warning(f"[Group Chat] Broadcast returned False")
                            except Exception as e:
                                self.logger.warning(f"[Group Chat] Broadcast failed: {e}")
                                import traceback
                                traceback.print_exc()
                    else:
                        self.logger.warning("[Group Chat] Tool not ready after 2s wait")
            
            return reply
            
        except Exception as e:
            self.logger.error(f"[Process] Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _check_kill_command(self, text: str) -> bool:
        """Check if text contains kill command"""
        if not text or not isinstance(text, str):
            return False
        return KILL_COMMAND in text.lower()
    
    def _should_check_chat_engagement(self) -> bool:
        """Check if chat engagement should be considered"""
        chat_enabled = getattr(self.controls, 'CHAT_ENGAGEMENT', False)
        if not chat_enabled:
            return False
        
        has_active_chat = (
            (self.youtube_chat and self.youtube_chat.enabled) or
            (self.twitch_chat and self.twitch_chat.enabled) or
            (self.discord_integration and self.discord_integration.running)
        )
        return has_active_chat
    
    # ========================================================================
    # CONTEXT BUILDING
    # ========================================================================
    
    def _build_context(self, user_text: str = "") -> List[str]:
        """Build context for AI processing"""
        context_parts = []
        
        # Session files
        if hasattr(self, 'session_file_manager') and self.session_file_manager:
            if self.session_file_manager.session_files:
                session_context = self.session_file_manager.get_context_for_query(user_text)
                if session_context:
                    context_parts.append(session_context)
        
        # Live chat context
        chat_context = self._get_chat_context()
        if chat_context:
            chat_engagement = getattr(self.controls, 'CHAT_ENGAGEMENT', False)
            if chat_engagement:
                context_parts.append(f"## LIVE CHAT ACTIVITY\n{chat_context}")
            else:
                context_parts.append(f"## LIVE CHAT ACTIVITY (response-only)\n{chat_context}")
        
        # Pending actions
        pending_context = self._get_pending_actions_context()
        if pending_context:
            context_parts.append(pending_context)
        
        return context_parts
    
    def _get_pending_actions_context(self) -> str:
        """Get pending actions context from tool system"""
        if not hasattr(self, 'action_state_manager') or not self.action_state_manager:
            return ""
        
        try:
            pending = self.action_state_manager.get_context_summary()
            if pending:
                return f"## PENDING ACTIONS\n\n{pending}"
        except Exception as e:
            self.logger.warning(f"[Pending Actions] Failed to get context: {e}")
        
        return ""
    
    def _get_chat_context(self) -> str:
        """Get live chat messages"""
        if hasattr(self, 'chat_handler') and self.chat_handler:
            chat_messages = self._get_clean_chat_messages()
            if not chat_messages:
                return ""
            
            # Ingest into thought buffer
            for msg in chat_messages:
                self._ingest_chat_message_clean(msg)
            
            return self._format_chat_for_context(chat_messages)
        
        return self._get_chat_context_legacy()
    
    def _get_clean_chat_messages(self, max_messages: int = 10, max_age: float = 300.0):
        """Get clean chat message objects from ChatHandler"""
        if not hasattr(self, 'chat_handler') or not self.chat_handler:
            return []
        
        all_messages = []
        current_time = time.time()
        
        for platform_name, buffer in self.chat_handler._buffers.items():
            for msg in buffer:
                if (current_time - msg.timestamp) > max_age:
                    continue
                all_messages.append(msg)
        
        all_messages.sort(key=lambda m: m.timestamp)
        return all_messages[-max_messages:]
    
    def _format_chat_for_context(self, chat_messages) -> str:
        """Format chat messages for context"""
        if not chat_messages:
            return ""
        lines = [f"[{msg.platform}] {msg.author}: {msg.content}" for msg in chat_messages]
        return "\n".join(lines)
    
    def _ingest_chat_message_clean(self, chat_msg):
        """Ingest clean ChatMessage into thought buffer"""
        from BASE.config.bot_info import agentname
        has_mention = agentname.lower() in chat_msg.content.lower()
        
        self.processing_delegator.thought_processor.thought_buffer.ingest_chat_message(
            platform=chat_msg.platform,
            username=chat_msg.author,
            message=chat_msg.content,
            has_bot_mention=has_mention
        )
    
    def _get_chat_context_legacy(self) -> str:
        """Get chat from legacy integrations"""
        chat_parts = []
        
        if self.youtube_chat and self.youtube_chat.enabled:
            yt_context = self.youtube_chat.get_context_for_ai()
            if yt_context:
                chat_parts.append(f"[YouTube]\n{yt_context}")
        
        if self.twitch_chat and self.twitch_chat.enabled:
            twitch_context = self.twitch_chat.get_context_for_ai()
            if twitch_context:
                chat_parts.append(f"[Twitch]\n{twitch_context}")
        
        return "\n\n".join(chat_parts) if chat_parts else ""
    
    def get_live_chat_context(self) -> str:
        """Get recent live chat for AI context"""
        if not hasattr(self, 'chat_handler') or not self.chat_handler:
            return ""
        return self.chat_handler.get_recent_chat_context(max_messages=10, max_age_seconds=300.0)
    
    def _cleanup_old_reminders(self):
        """Periodic cleanup of announced reminders"""
        current_time = time.time()
        if current_time - self.last_reminder_cleanup < self.reminder_cleanup_interval:
            return
        
        self.last_reminder_cleanup = current_time
        
        if not getattr(self.controls, 'USE_REMINDERS', False):
            return
    
    # ========================================================================
    # ACCESSORS
    # ========================================================================
    
    def list_session_files(self):
        """List all session files"""
        return self.session_file_manager.list_files()
    
    def load_session_file(self, filepath: Path):
        """Load a session file from disk"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            result = self.session_file_manager.add_file(
                filepath=str(filepath), content=content, file_type="auto"
            )
            
            if result['success']:
                self.logger.system(f"Loaded session file: {filepath.name}")
                return result
            else:
                self.logger.error(f"Failed to load: {result.get('error', 'Unknown error')}")
                return None
        except Exception as e:
            self.logger.error(f"Error loading {filepath}: {e}")
            return None
    
    def get_control_manager(self):
        return self.control_manager
    
    def get_memory_manager(self):
        return self.memory_manager
    
    def get_session_file_manager(self):
        return self.session_file_manager
    
    # Session file convenience methods
    def add_session_file(self, filepath: str, content: str, file_type: str = "auto"):
        return self.session_file_manager.add_file(filepath, content, file_type)
    
    def unload_session_file(self, file_id: str):
        return self.session_file_manager.remove_file(file_id)
    
    def remove_session_file(self, file_id: str):
        return self.session_file_manager.remove_file(file_id)
    
    def get_session_file_content(self, file_id: str, line_start=None, line_end=None):
        return self.session_file_manager.get_file_content(file_id, line_start, line_end)
    
    def search_session_files(self, query: str, file_id=None, top_k: int = 5):
        return self.session_file_manager.search(query, file_id, top_k)
    
    def clear_all_session_files(self):
        self.session_file_manager.clear_all()
    
    def clear_session_files(self):
        self.session_file_manager.clear_all()
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        stats = {
            'memory': self.memory_manager.get_stats(),
            'delegator': self.processing_delegator.get_performance_stats()
        }
        
        if hasattr(self, 'instruction_persistence_manager'):
            stats['instruction_persistence'] = (
                self.instruction_persistence_manager.get_statistics()
            )
        
        if hasattr(self, 'processing_delegator'):
            thought_processor = self.processing_delegator.thought_processor
            if hasattr(thought_processor, 'cognitive_loop') and thought_processor.cognitive_loop:
                stats['cognitive_loop'] = thought_processor.cognitive_loop.get_statistics()
        
        return stats