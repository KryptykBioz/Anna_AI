# ============================================================================
# FILE: BASE/core/processing_delegator.py (STREAMING VERSION)
# Processing Delegator with Streaming Response Support
# ============================================================================
"""
Processing Delegator with Streaming
====================================
ADDED: Streaming response generation with complete memory storage

Key Changes:
1. Added StreamingResponseHandler integration
2. Added OllamaStreamingInterface for async streaming
3. _generate_responsive_response now supports streaming mode
4. All responses (complete and interrupted) stored to memory
5. Maintains backward compatibility with non-streaming mode
"""
import asyncio
import time
from typing import Optional, List
from pathlib import Path

from BASE.core.thought_processor import ThoughtProcessor
from BASE.core.logger import Logger
from BASE.recall.memory_search import MemorySearch

# NEW: Import streaming components
from BASE.core.streaming_response_handler import (
    StreamingResponseHandler,
    OllamaStreamingInterface
)

# Existing imports
from BASE.core.response_decider import ResponseDecider
from BASE.core.responsive.responsive_constructor import ResponsiveConstructor

from BASE.config.controls import KILL_COMMAND
from BASE.config.bot_info import username, agentname


class ProcessingDelegator:
    """
    Unified orchestrator with streaming support
    ADDED: Streaming response generation while maintaining backward compatibility
    """
    
    __slots__ = (
            'config', 'controls', 'project_root', 'memory_manager', 'logger',
            'memory_search', 'session_file_manager', 'tool_manager',
            'thought_processor', 'responsive_constructor', 'response_decider',
            'streaming_enabled', 'streaming_handler', 'ollama_streaming',
            'hot_reload_manager', 'cognitive_filter',
            '_prompt_judge_ref'             
        )
    
    def __init__(
        self,
        config,
        controls_module,
        project_root: Path,
        memory_manager=None,
        gui_logger=None,
        session_file_manager=None
    ):
        """Initialize processing delegator with streaming support"""
        self.config = config
        self.controls = controls_module
        self.project_root = project_root
        self.memory_manager = memory_manager
        
        # Initialize logger
        self.logger = Logger(
            name="ProcessingDelegator", 
            gui_callback=gui_logger,
            config=config
        )
        
        # Initialize memory search
        self.memory_search = None
        if memory_manager:
            self.memory_search = MemorySearch(memory_manager)
            self.logger.system("Memory search initialized")
        
        # Store dependencies
        self.session_file_manager = session_file_manager
        self.tool_manager = None
        
        # Initialize STAGE 1: Thought Processor
        self.thought_processor = ThoughtProcessor(
            config=config,
            controls_module=controls_module,
            project_root=project_root,
            memory_search=self.memory_search,
            session_file_manager=session_file_manager,
            gui_logger=gui_logger
        )
        
        # Initialize STAGE 2: Responsive Constructor
        self.responsive_constructor = ResponsiveConstructor(
            memory_search=self.memory_search,
            logger=self.logger
        )
        
        # Initialize response decider
        self.response_decider = ResponseDecider(
            agentname=agentname,
            username=username,
            logger=self.logger
        )

        # Cognitive response filter
        from BASE.core.cognitive_filter import CognitiveFilter
        self.cognitive_filter = CognitiveFilter(config=config, controls=controls_module, logger=self.logger)
        self.logger.system("Cognitive response filter initialized")
        
        # Initialize streaming components
        self.streaming_enabled = getattr(controls_module, 'USE_STREAMING', False)
        
        if self.streaming_enabled:
            # Will be initialized when TTS tool is available
            self.streaming_handler = None
            self.ollama_streaming = OllamaStreamingInterface(
                ollama_base_url=config.ollama_endpoint
            )
            self.logger.system("Ollama streaming interface initialized")
        else:
            self.streaming_handler = None
            self.ollama_streaming = None
            self.logger.system("Non-streaming mode")
        
        self.logger.system(
            f"ProcessingDelegator initialized "
            f"(streaming: {'ENABLED' if self.streaming_enabled else 'DISABLED'})"
        )

        self._prompt_judge_ref = None
    
    def initialize_streaming(self, tts_tool):
        """
        Initialize streaming handler once TTS tool is available
        
        Called by ai_core after TTS tool is set up
        
        Args:
            tts_tool: TTSTool instance
        """
        if not self.streaming_enabled:
            self.logger.system("Streaming disabled - skipping handler initialization")
            return
        
        if not tts_tool:
            self.logger.warning("Cannot initialize streaming - no TTS tool")
            return
        
        self.streaming_handler = StreamingResponseHandler(
            memory_manager=self.memory_manager,
            memory_search=self.memory_search,
            tts_tool=tts_tool,
            logger=self.logger
        )
        
        self.logger.system("StreamingResponseHandler initialized")

    def set_tool_manager(self, tool_manager):
        """Inject tool manager into thought processor"""
        self.tool_manager = tool_manager
        self.thought_processor.set_tool_manager(tool_manager)
        
        enabled = tool_manager.get_enabled_tool_names()
        self.logger.system(
            f"[ProcessingDelegator] Tool manager injected "
            f"({len(enabled)} tools enabled)"
        )

    # ========================================================================
    # HOT RELOAD MANAGEMENT
    # ========================================================================

    def _register_constructors_for_hot_reload(self):
            """
            Register prompt constructors with hot-reload manager
            
            HYBRID APPROACH: Uses directory watching with auto-dependency detection
            """
            if not hasattr(self, 'hot_reload_manager'):
                return
            
            if not self.hot_reload_manager or not self.hot_reload_manager.enabled:
                return
            
            base_path = self.project_root / 'BASE' / 'core'
            
            # HYBRID APPROACH: Watch responsive directory
            # Auto-registers responsive_constructor AND helper files
            self.hot_reload_manager.watch_directory_recursively(base_path / 'responsive')
            
            # Register self for reference updates
            self.hot_reload_manager.register_processing_delegator(self)
            
            if self.logger:
                self.logger.system(
                    "[Hot Reload] Registered responsive constructor + helpers "
                    "(auto-detected dependencies)"
                )

    def set_hot_reload_manager(self, hot_reload_manager):
        """
        Inject hot-reload manager
        
        NEW METHOD: Called by core_initializer to enable hot-reloading
        
        Args:
            hot_reload_manager: CoreHotReloadManager instance
        """
        self.hot_reload_manager = hot_reload_manager
        self._register_constructors_for_hot_reload()
    
    # ========================================================================
    # MAIN ENTRY POINT
    # ========================================================================
    
    async def process_user_input(
        self,
        user_input: str,
        source: str = "GUI",
        user_id: str = "local_user",
        is_image_message: bool = False,
        image_path: Optional[Path] = None,
        timestamp: Optional[float] = None,
        username_override: Optional[str] = None,
        context_parts: list = None
    ) -> Optional[str]:
        """
        Process user input - UNCHANGED
        Streaming happens transparently in _generate_responsive_response
        """
        # Kill command check
        if user_input and isinstance(user_input, str):
            if KILL_COMMAND in user_input.lower():
                self.logger.system("[Kill Command] Stopping")
                self.thought_processor.thought_buffer.force_shutdown()
                return None
        
        if self.thought_processor.thought_buffer.is_shutdown_requested():
            return None
        
        # Input filtering
        if user_input and user_input.strip():
            from BASE.handlers.content_filter import ContentFilter
            filter_instance = ContentFilter(use_ai_filter=False)
            
            cleaned_input, was_filtered, reason = filter_instance.filter_incoming(
                user_input,
                log_callback=self.logger.system
            )
            
            if was_filtered:
                self.logger.system(f"[Filter] Cleaned input: {reason}")
            
            user_input = cleaned_input
        
        context_parts = context_parts or []
        
        # Chat engagement check
        chat_engagement_enabled = getattr(self.controls, 'CHAT_ENGAGEMENT', False)
        is_autonomous_trigger = (source == "AUTONOMOUS_CHAT")
        
        clean_chat = self._get_clean_unengaged_chat()
        
        should_promote = False
        if chat_engagement_enabled and (clean_chat or is_autonomous_trigger):
            should_promote = self.thought_processor.thought_buffer.should_engage_with_chat()
            
            if should_promote:
                self.logger.system("[Chat Engagement] Promoting chat to primary response")
        
        if is_autonomous_trigger and not should_promote:
            return None
        
        original_input = ""
        
        # Input processing
        if should_promote and clean_chat:
            promoted_input = clean_chat
            original_input = promoted_input
            
            if user_input and user_input.strip():
                context_parts.insert(0, f"## USER NOTE\n{username_override or username} said: \"{user_input}\"")
            else:
                context_parts.insert(0, "## AUTONOMOUS ENGAGEMENT\nResponding to chat activity")
            
            context_parts = [c for c in context_parts if not c.startswith('## LIVE CHAT')]
            self.thought_processor.ingest_user_directive(promoted_input)
            
        elif user_input and user_input.strip():
            original_input = user_input
            self.thought_processor.ingest_user_directive(user_input)
        
        # Session files context
        if self.session_file_manager and self.session_file_manager.session_files:
            search_query = original_input if original_input else ""
            session_context = self.session_file_manager.get_context_for_query(search_query)
            if session_context:
                context_parts.insert(0, session_context)
        
        # Build memory context
        recent_thoughts = self.thought_processor.thought_buffer.get_thoughts_for_response()
        memory_context = self._build_memory_context(
            original_input, 
            context_parts,
            recent_thoughts=recent_thoughts
        )
        
        if memory_context:
            context_parts.insert(0, memory_context)
            self.logger.memory("[Memory] Retrieved context")
        
        # STAGE 1: THOUGHT PROCESSING (Continuous Thinking only)
        # When disabled, skip all cognitive mode processing and go straight to
        # the responsive prompt, which forces a spoken reply every time.
        continuous_thinking_active = (
            self.thought_processor.cognitive_loop is not None
            and self.thought_processor.cognitive_loop.is_running
        )

        if continuous_thinking_active:
            await self.thought_processor.process_thoughts(context_parts=context_parts)
            await self.thought_processor.process_thoughts(context_parts=context_parts)

            # STAGE 2: RESPECT AGENT'S <speak> DECISION
            if not self.thought_processor.thought_buffer.response_trigger.should_respond():
                return None
        else:
            # Prompt-response mode: clear any stale trigger, skip directly to response
            self.thought_processor.thought_buffer.response_trigger.clear()

        # STAGE 3: GENERATE RESPONSE (now supports streaming)
        response = await self._generate_responsive_response(
            user_text=original_input,
            context_parts=context_parts,
            chat_context=clean_chat,
            is_chat_engagement=should_promote
        )
        
        # Add response echo (already done in streaming, but safe to do again)
        if response:
            self.thought_processor.thought_buffer.add_response_echo(
                response_text=response,
                timestamp=time.time()
            )
            self.logger.system("[Response Echo] Added to thought buffer")
        
        # Mark chat as engaged
        if response and should_promote:
            unengaged = self.thought_processor.thought_buffer.get_unengaged_messages()
            message_indices = [msg.get('_index') for msg in unengaged if '_index' in msg]
            self.thought_processor.thought_buffer.mark_chat_engaged(message_indices)
            self.logger.system(f"[Chat Engagement] Marked {len(message_indices)} messages as engaged")
        
        # Return response to caller
        if response:
            self.logger.system(f"[RETURN] Returning response to caller: {response[:60]}...")
        
        return response
    
    # ========================================================================
    # RESPONSE GENERATION (MODIFIED FOR STREAMING)
    # ========================================================================
    
    async def _generate_responsive_response(
        self,
        user_text: str,
        context_parts: List[str],
        chat_context: Optional[str] = None,
        is_chat_engagement: bool = False
    ) -> Optional[str]:
        thought_buffer = self.thought_processor.thought_buffer
        recent_thoughts = thought_buffer.get_thoughts_for_response()

        response_context = self._build_response_context(
            context_parts, chat_context, is_chat_engagement
        )

        prompt = self.responsive_constructor.build_responsive_prompt(
            thought_chain=recent_thoughts,
            user_text=user_text,
            context_parts=response_context,
            chat_context=chat_context if is_chat_engagement else None,
            is_chat_engagement=is_chat_engagement
        )

        use_streaming = (
            self.streaming_enabled and
            self.streaming_handler is not None and
            self.ollama_streaming is not None
        )

        if use_streaming:
            response = await self._generate_streaming(
                prompt=prompt,
                user_text=user_text,
                context_parts=context_parts,
                thought_buffer=thought_buffer
            )
        else:
            response = await self._generate_non_streaming(
                prompt=prompt,
                thought_buffer=thought_buffer
            )

        if response:
            approved, reason = self.cognitive_filter.check_response(
                response=response,
                thought_chain=recent_thoughts,
                context_parts=response_context
            )
            if not approved:
                self.logger.filter(f"[CognitiveFilter] Response discarded ({reason}) — skipping cycle")
                return None
            self.cognitive_filter.update_last_response(response)

        return response
    
    async def _generate_streaming(
        self,
        prompt: str,
        user_text: str,
        context_parts: List[str],
        thought_buffer
    ) -> Optional[str]:
        self.logger.system("[Streaming] Starting streaming response generation")

        try:
            response_stream = self.ollama_streaming.stream_chat_response(
                prompt=prompt,
                model=self.config.text_model,
                system_prompt=None
            )

            complete_response = await self.streaming_handler.stream_and_store(
                response_stream=response_stream,
                thought_buffer=thought_buffer,
                context_parts=context_parts,
                user_input=user_text
            )

            if complete_response:
                import re
                THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)
                complete_response = THINK_PATTERN.sub('', complete_response).strip()

                from BASE.core.clean_response import remove_emoji
                complete_response = remove_emoji(complete_response)

            if not complete_response or not complete_response.strip():
                self.logger.warning("[Streaming] Response empty after cleaning")
                thought_buffer.response_trigger.clear()
                return None

            thought_buffer.response_trigger.clear()

            self.logger.system(f"[Streaming] Complete: {len(complete_response)} chars")
            self._submit_responsive_to_judge(prompt, complete_response)   # NEW

            return complete_response

        except Exception as e:
            self.logger.error(f"[Streaming] Error: {e}")
            import traceback
            traceback.print_exc()
            self.logger.system("[Streaming] Falling back to non-streaming mode")
            return await self._generate_non_streaming(prompt, thought_buffer)
    
    async def _generate_non_streaming(
        self,
        prompt: str,
        thought_buffer
    ) -> Optional[str]:
        response = self._call_ollama(
            prompt=prompt,
            model=self.config.text_model,
            system_prompt=None
        )

        import re
        THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)
        response = THINK_PATTERN.sub('', response).strip()

        if not response or not response.strip():
            self.logger.warning("[Response] Generated empty response")
            thought_buffer.response_trigger.clear()
            return None

        from BASE.core.clean_response import remove_emoji
        response = remove_emoji(response)

        if not response or not response.strip():
            self.logger.warning("[Response] Response became empty after cleaning")
            thought_buffer.response_trigger.clear()
            return None

        thought_buffer.response_trigger.clear()

        self.logger.system(f"[Response] Generated {len(response)} chars: {response}")
        self._submit_responsive_to_judge(prompt, response)   # NEW

        return response
    
    def _build_response_context(
        self,
        context_parts: List[str],
        chat_context: Optional[str],
        is_chat_engagement: bool
    ) -> List[str]:
        """
        Build response context from available parts
        
        Helper method to organize context consistently
        """
        response_context = []
        
        # Add memory context
        memory_parts = [
            c for c in context_parts 
            if c.startswith('## MEMORY') or c.startswith('## YESTERDAY')
        ]
        response_context.extend(memory_parts)
        
        # Add chat context
        if is_chat_engagement and chat_context:
            response_context.append(f"## CHAT TO ADDRESS\n{chat_context}")
        elif chat_context:
            response_context.append(f"## LIVE CHAT ACTIVITY\n{chat_context}")
        
        # Add other context (limit to 3)
        other_context = [
            c for c in context_parts 
            if not c.startswith('## LIVE CHAT') 
            and not c.startswith('## USER NOTE')
            and not c.startswith('## AUTONOMOUS ENGAGEMENT')
            and not c.startswith('## MEMORY')
            and not c.startswith('## YESTERDAY')
        ]
        response_context.extend(other_context[:3])
        
        return response_context
    
    def _call_ollama(self, prompt: str, model: str, system_prompt: Optional[str] = None) -> str:
        """Call Ollama API (non-streaming)"""
        import requests
        
        try:
            url = f"{self.config.ollama_endpoint}/api/generate"
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            
            # [FIX] Use config values instead of hardcoded parameters
            payload = {
                "model": model,
                "prompt": full_prompt,
                "stream": False,
                "temperature": self.config.ollama_temperature_response,  # Changed from 0.7
                "top_p": self.config.ollama_top_p,  # Changed from 0.9
                "top_k": self.config.ollama_top_k,  # Changed from 40
                "repeat_penalty": self.config.ollama_repeat_penalty,  # Changed from 1.1
                "num_predict": self.config.ollama_max_tokens,  # Added (was missing)
                "keep_alive": "24h"
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            content = result.get("response", "") or result.get("message", {}).get("content", "")
            return content.strip()
        
        except Exception as e:
            self.logger.error(f"Ollama error: {e}")
            return ""
        
    
    def _submit_responsive_to_judge(self, prompt: str, response: str):
        """Forward responsive prompt+response to the prompt judge if enabled."""
        if not getattr(self.controls, 'USE_PROMPT_JUDGE', False):
            return
        if self._prompt_judge_ref is None:
            self._prompt_judge_ref = getattr(
                self.thought_processor, '_prompt_judge', None
            )
        if self._prompt_judge_ref:
            self._prompt_judge_ref.submit("responsive", prompt, response)
    
    # ========================================================================
    # HELPER METHODS (UNCHANGED - keeping rest of class)
    # ========================================================================
    
    def _build_memory_context(
        self,
        user_input: str,
        context_parts: List[str],
        recent_thoughts: List[str]
    ) -> str:
        """Build memory context for prompts"""
        if not self.memory_search:
            return ""
        
        # Determine if memory retrieval needed
        combined_text = f"{user_input} {' '.join([str(t) for t in recent_thoughts])}"
        combined_lower = combined_text.lower()
        
        memory_triggers = [
            'remember', 'recall', 'before', 'earlier', 'last time',
            'yesterday', 'you said', 'we talked', 'mentioned'
        ]
        
        needs_memory = any(trigger in combined_lower for trigger in memory_triggers)
        
        if not needs_memory:
            return ""
        
        # Search memory
        try:
            memory_results = self.memory_search.search_medium_memory(
                query=user_input or combined_text[:200],
                k=1
            )
            
            if memory_results:
                memory_lines = ["## RELEVANT MEMORIES"]
                for r in memory_results:
                    role = username if r['role'] == 'user' else agentname
                    memory_lines.append(f"[{r['timestamp']}] {role}: {r['content']}")
                
                return "\n".join(memory_lines)
        
        except Exception as e:
            self.logger.warning(f"Memory search error: {e}")
        
        return ""
    
    def _get_clean_unengaged_chat(self) -> str:
        """Get unengaged chat messages"""
        unengaged = self.thought_processor.thought_buffer.get_unengaged_messages()
        if not unengaged:
            return ""
        
        lines = []
        for msg in unengaged[-5:]:
            platform = msg.get('platform', 'chat')
            user = msg.get('username', 'unknown')
            content = msg.get('message', '')
            lines.append(f"[{platform}] {user}: {content}")
        
        return "\n".join(lines)
    
    def get_performance_stats(self):
        """Get performance statistics"""
        return {
            'thought_processor': {
                'total_thoughts': len(self.thought_processor.thought_buffer.get_thoughts_for_response())
            },
            'streaming_enabled': self.streaming_enabled,
            'streaming_available': self.streaming_handler is not None
        }