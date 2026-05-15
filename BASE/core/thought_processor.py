# Filename: BASE/core/thought_processor.py
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import asyncio
import re

from BASE.core.thought_buffer import ThoughtBuffer
from BASE.core.logger import Logger
from BASE.core.thinking_modes import ThinkingModes
from BASE.core.response_decider import ResponseDecider, PromptType, parse_agent_next_mode
from BASE.core.reactive.reactive_constructor import ReactiveConstructor
from BASE.core.reflective.reflective_constructor import ReflectiveConstructor
from BASE.core.proactive.proactive_constructor import ProactiveConstructor
from BASE.core.action.action_constructor import ActionConstructor

from BASE.tools.installed.discord_bot import config
from BASE.config.bot_info import username, agentname


class ThoughtProcessor:
    __slots__ = (
            'config', 'controls', 'project_root', 'memory_search',
            'session_file_manager', 'logger', 'thought_buffer',
            '_is_processing', '_last_memory_integration',
            '_last_processing_time',
            'cognitive_loop', 'event_loop', '_ai_core_ref',
            '_autonomous_response_callback',
            'thinking_modes', 'action_state_manager', 'tool_manager',
            '_last_tool_exploration',
            'response_decider', 'reactive_constructor',
            'reflective_constructor', 'proactive_constructor',
            'action_constructor', 'hot_reload_manager',
            '_requested_next_mode',
            '_prompt_judge', '_last_cognitive_response'
    )

    def __init__(
        self, config, controls_module, project_root: Path,
        memory_search=None, session_file_manager=None,
        gui_logger=None
    ):
        self.config = config
        self.controls = controls_module
        self.project_root = project_root
        self.memory_search = memory_search
        self.session_file_manager = session_file_manager

        self.logger = Logger(name="ThoughtProcessor", gui_callback=gui_logger, config=config)
        self.thought_buffer = ThoughtBuffer(max_thoughts=config.history_limit)
        # Wire logger → thought buffer for agent self-awareness.
        # Every SYSTEM/SUCCESS/WARNING/ERROR log message is forwarded as a
        # 'system_log' raw event so the agent can observe internal state.
        self.logger.set_thought_buffer_callback(
            self.thought_buffer.ingest_system_message
        )

        self.response_decider = ResponseDecider(
            agentname=agentname,
            username=username,
            logger=self.logger
        )

        self.reactive_constructor = ReactiveConstructor(
            tool_manager=None,
            logger=self.logger
        )

        self.reflective_constructor = ReflectiveConstructor(
            memory_search=memory_search,
            tool_manager=None,
            logger=self.logger
        )

        self.proactive_constructor = ProactiveConstructor(
            tool_manager=None,
            logger=self.logger
        )

        self.action_constructor = ActionConstructor(
            tool_manager=None,
            logger=self.logger
        )

        self._requested_next_mode = 'reactive'

        self._is_processing = False
        self._last_memory_integration = 0.0
        self._last_tool_exploration = 0.0
        self._last_cognitive_response = ''
        self._last_processing_time = 0.0

        self._prompt_judge = None
        self._init_prompt_judge()

        self.tool_manager = None
        self.action_state_manager = None

        self.cognitive_loop = None
        self.event_loop = None
        self._ai_core_ref = None
        self._autonomous_response_callback = None

        self.thinking_modes = ThinkingModes(
            processor=self,
            config=config,
            controls=controls_module,
            logger=self.logger
        )

        self._register_constructors_for_hot_reload()

        self.logger.system("Thought Processor initialized (simplified response triggering)")


    def _init_prompt_judge(self):
        """Initialize the prompt judge if USE_PROMPT_JUDGE is enabled at startup."""
        if not getattr(self.controls, 'USE_PROMPT_JUDGE', False):
            return
        try:
            from BASE.tools.internal.prompt_judge.prompt_judge import PromptJudge
            self._prompt_judge = PromptJudge(
                config=self.config,
                controls=self.controls,
                project_root=self.project_root,
                logger=self.logger
            )
            self._prompt_judge.start()
            self.logger.judge("[Prompt Judge] Initialized and started")
        except Exception as e:
            self.logger.judge(f"[Prompt Judge] Failed to initialize: {e}")

    def _get_prompt_judge(self):
        """
        Lazy-initialize the prompt judge if the control was enabled after startup.
        Returns the judge instance or None if disabled.
        """
        if not getattr(self.controls, 'USE_PROMPT_JUDGE', False):
            return None
        if self._prompt_judge is None:
            self._init_prompt_judge()
        return self._prompt_judge

    def _submit_to_judge(self, prompt_type: str, prompt: str, response: str):
        """Submit a prompt+response pair to the judge. No-op if judge is off."""
        judge = self._get_prompt_judge()
        if judge:
            judge.submit(prompt_type, prompt, response)


    # ========================================================================
    # HOT RELOAD SYSTEM
    # ========================================================================

    def _register_constructors_for_hot_reload(self):
        if not hasattr(self, 'hot_reload_manager'):
            return
        if not self.hot_reload_manager or not self.hot_reload_manager.enabled:
            return

        base_path = self.project_root / 'BASE' / 'core'

        self.hot_reload_manager.watch_directory_recursively(base_path / 'reactive')
        self.hot_reload_manager.watch_directory_recursively(base_path / 'reflective')
        self.hot_reload_manager.watch_directory_recursively(base_path / 'proactive')
        self.hot_reload_manager.watch_directory_recursively(base_path / 'action')

        self.hot_reload_manager.register_thought_processor(self)

        registered_count = len([m for m in self.hot_reload_manager.modules.keys()
                                 if m in ['reactive_constructor', 'reflective_constructor',
                                          'proactive_constructor', 'action_constructor']])
        if self.logger:
            self.logger.system(
                f"[Hot Reload] Registered {registered_count} constructors + helpers "
                f"(auto-detected dependencies)"
            )

    def set_hot_reload_manager(self, hot_reload_manager):
        self.hot_reload_manager = hot_reload_manager
        self._register_constructors_for_hot_reload()

    # ========================================================================
    # DATA INGESTION
    # ========================================================================

    def ingest_data(self, source: str, data: str):
        self.thought_buffer.ingest_raw_data(source, data)
        self.logger.system(f"Ingested: {source} ({len(data)} chars)")

    def ingest_user_directive(self, user_input: str):
        if not user_input or not user_input.strip():
            self.logger.system("[Input] Empty input - checking for proactive processing")
            return
        self.logger.tool(f"[USER INPUT] {user_input}")
        self.ingest_data('user_input', user_input)
        self.logger.system(f"[Input] User: {user_input}")

    # ========================================================================
    # DEPENDENCY INJECTION
    # ========================================================================

    def set_tool_manager(self, tool_manager):
        self.tool_manager = tool_manager
        self.action_state_manager = tool_manager.action_state_manager

        self.reactive_constructor.tool_manager = tool_manager
        self.reflective_constructor.tool_manager = tool_manager
        self.proactive_constructor.tool_manager = tool_manager
        self.action_constructor.tool_manager = tool_manager

        self.thinking_modes.tool_manager = tool_manager
        self.thinking_modes.action_state_manager = self.action_state_manager

        enabled_count = len(tool_manager.get_enabled_tool_names())
        self.logger.system(
            f"[Thought Processor] Tool manager injected: "
            f"{enabled_count} tools available"
        )

    # ========================================================================
    # CONTINUOUS THINKING CONTROL
    # ========================================================================

    def start_continuous_thinking(self):
        if self.cognitive_loop is not None:
            if self.cognitive_loop.is_running:
                self.logger.warning("[Continuous] Loop already started")
                return
            self.logger.system("[Continuous] Restarting stopped cognitive loop")
            if hasattr(self, 'event_loop') and self.event_loop:
                asyncio.run_coroutine_threadsafe(
                    self.cognitive_loop.start_continuous_loop(), self.event_loop
                )
                self.logger.system("Continuous autonomous thinking RE-ENABLED")
            else:
                self.logger.error("No event loop available for continuous thinking")
            return

        from BASE.core.cognitive_loop_manager import CognitiveLoopManager

        self.cognitive_loop = CognitiveLoopManager(
            thought_processor=self, controls=self.controls, logger=self.logger
        )

        if hasattr(self, '_ai_core_ref') and self._ai_core_ref:
            self.cognitive_loop.set_ai_core(self._ai_core_ref)

        if self._autonomous_response_callback:
            self.cognitive_loop.autonomous_response_callback = self._autonomous_response_callback
            self.logger.system("[Cognitive Loop] Autonomous response callback registered")
        else:
            self.logger.warning("[Cognitive Loop] No callback stored - autonomous responses will not display!")

        if hasattr(self, 'event_loop') and self.event_loop:
            asyncio.run_coroutine_threadsafe(
                self.cognitive_loop.start_continuous_loop(), self.event_loop
            )
        else:
            self.logger.error("No event loop available for continuous thinking")
            return

        self.logger.system("Continuous autonomous thinking ENABLED")

    def set_ai_core_reference(self, ai_core):
        self._ai_core_ref = ai_core
        if self.cognitive_loop:
            self.cognitive_loop.set_ai_core(ai_core)

    def set_autonomous_response_callback(self, callback):
        self._autonomous_response_callback = callback
        if self.cognitive_loop:
            self.cognitive_loop.autonomous_response_callback = callback
            self.logger.system("[Cognitive Loop] Autonomous response callback registered")
        else:
            self.logger.system("[Cognitive Loop] Callback stored, will register when loop starts")

    async def stop_continuous_thinking(self):
        if self.cognitive_loop:
            await self.cognitive_loop.stop_continuous_loop()
            self.cognitive_loop = None

    # ========================================================================
    # THOUGHT PROCESSING
    # ========================================================================

    async def process_thoughts(self, context_parts: List[str] = None) -> bool:
        if self._is_processing:
            return False

        LIMIT_PROCESSING = getattr(self.controls, 'LIMIT_PROCESSING', False)
        if LIMIT_PROCESSING:
            current_time = time.time()
            time_since_last = current_time - self._last_processing_time
            processing_delay = getattr(self.controls, 'PROCESSING_DELAY', 30)
            if time_since_last < processing_delay:
                return False
            self._last_processing_time = current_time

        self._is_processing = True
        processing_occurred = False
        context_parts = context_parts or []

        try:
            if self._check_chat_engagement_need():
                chat_thought = self._create_chat_engagement_thought()
                if chat_thought:
                    self.thought_buffer.add_processed_thought(
                        chat_thought['content'],
                        chat_thought['source'],
                        chat_thought.get('original_ref'),
                        chat_thought.get('timestamp')
                    )

            new_thoughts = self.thought_buffer.get_new_thoughts()

            if self.thought_buffer.has_actionable_new_thoughts():
                # ----------------------------------------------------------------
                # Incoming events always run reactive regardless of the agent's
                # last requested mode. The agent's <next_mode> from this cycle's
                # response is stored and takes effect on the next no-events cycle.
                # ----------------------------------------------------------------
                thoughts, actions, should_speak, next_mode = await self._reactive_processing(
                    new_thoughts, context_parts
                )

                if thoughts:
                    for thought_text in thoughts:
                        self.thought_buffer.add_processed_thought(
                            self._clean_thought_text(thought_text),
                            'internal',
                            timestamp=time.time()
                        )

                if should_speak:
                    self.thought_buffer.response_trigger.trigger()

                if actions and self.tool_manager:
                    tool_names = [a.get('tool', 'unknown') for a in actions]
                    self.thought_buffer.add_processed_thought(
                        f"Executing {len(actions)} tool(s): {', '.join(tool_names)}. "
                        f"Results will be available shortly.",
                        'system_notification',
                        timestamp=time.time()
                    )
                    self.logger.system(
                        f"[Action Mode] Spawning {len(actions)} actions "
                        f"(non-blocking, speak={should_speak})"
                    )
                    asyncio.create_task(
                        self._execute_action_mode(
                            actions=actions,
                            context_parts=context_parts,
                            mode_context="reactive"
                        )
                    )

                self._apply_next_mode(next_mode, 'reactive', context_parts)
                processing_occurred = True

            else:
                # ----------------------------------------------------------------
                # No actionable incoming events — route by the agent's last
                # requested mode. Default is reactive.
                # ----------------------------------------------------------------
                mode = self._requested_next_mode

                if mode in ('proactive', 'reflective'):
                    prompt_type = self._mode_str_to_prompt_type(mode)
                    result = await self._proactive_processing_by_type(prompt_type, context_parts)

                    if result:
                        proactive_thought = result.get('thought')
                        should_speak      = result.get('should_speak', False)
                        proactive_actions = result.get('actions', [])
                        next_mode         = result.get('next_mode')

                        if proactive_thought:
                            self.thought_buffer.add_proactive_thought(
                                self._clean_thought_text(proactive_thought)
                            )
                            processing_occurred = True

                        if should_speak:
                            self.thought_buffer.response_trigger.trigger()

                        if proactive_actions and self.tool_manager:
                            tool_names = [a.get('tool', 'unknown') for a in proactive_actions]
                            self.thought_buffer.add_processed_thought(
                                f"Executing {len(proactive_actions)} tool(s): {', '.join(tool_names)}. "
                                f"Results will be available shortly.",
                                'system_notification',
                                timestamp=time.time()
                            )
                            asyncio.create_task(
                                self._execute_action_mode(
                                    actions=proactive_actions,
                                    context_parts=context_parts,
                                    mode_context=mode
                                )
                            )

                        self._apply_next_mode(next_mode, mode, context_parts)

                else:
                    # reactive (default) or unrecognised — run with current events
                    # (may be system-only notifications or empty)
                    thoughts, actions, should_speak, next_mode = await self._reactive_processing(
                        new_thoughts, context_parts
                    )

                    if thoughts:
                        for thought_text in thoughts:
                            self.thought_buffer.add_processed_thought(
                                self._clean_thought_text(thought_text),
                                'internal',
                                timestamp=time.time()
                            )
                        processing_occurred = True

                    if should_speak:
                        self.thought_buffer.response_trigger.trigger()

                    if actions and self.tool_manager:
                        tool_names = [a.get('tool', 'unknown') for a in actions]
                        self.thought_buffer.add_processed_thought(
                            f"Executing {len(actions)} tool(s): {', '.join(tool_names)}. "
                            f"Results will be available shortly.",
                            'system_notification',
                            timestamp=time.time()
                        )
                        asyncio.create_task(
                            self._execute_action_mode(
                                actions=actions,
                                context_parts=context_parts,
                                mode_context="reactive"
                            )
                        )

                    self._apply_next_mode(next_mode, 'reactive', context_parts)

            self.thought_buffer.mark_thoughts_seen()

            await self._check_urgent_reminders()

            if time.time() - self._last_memory_integration > 120.0:
                await self.thinking_modes.periodic_memory_integration()
                self._last_memory_integration = time.time()

            return processing_occurred

        finally:
            self._is_processing = False

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _convert_raw_events_to_thoughts(self, raw_events: List) -> None:
        for event in raw_events:
            source = event.source
            data = event.data
            timestamp = event.timestamp

            if source == 'user_input':
                self.thought_buffer.add_processed_thought(
                    content=data,
                    source='user_input',
                    original_ref=data,
                    timestamp=timestamp
                )

            elif source in ('tool_result', 'tool_failed', 'tool_timeout'):
                self.thought_buffer.add_processed_thought(
                    content=data,
                    source=source,
                    original_ref=data,
                    timestamp=timestamp
                )
                self.logger.system(f"[Event->Thought] Tool: {source}")

            elif source == 'vision_result':
                self.thought_buffer.add_processed_thought(
                    content=data,
                    source=source,
                    original_ref=data,
                    timestamp=timestamp
                )
                self.logger.system("[Event->Thought] Vision result")

            elif source == 'system_log':
                # Do NOT call self.logger here — would cause infinite recursion.
                self.thought_buffer.add_processed_thought(
                    content=data,
                    source='system_log',
                    original_ref=data,
                    timestamp=timestamp
                )

    async def _reactive_processing(self, new_thoughts, context_parts):
        self.logger.tool(f"[REACTIVE] Processing {len(new_thoughts)} new thoughts")

        recent_thoughts = self.thought_buffer.get_thoughts_for_response()
        last_user_msg = self.thought_buffer.get_last_user_input()

        pending_actions = ""
        if self.action_state_manager:
            pending_actions = self.action_state_manager.get_context_summary()

        has_vision = any(t.source == 'vision_result' for t in new_thoughts)

        filtered_context = [
            p for p in context_parts
            if not (last_user_msg and last_user_msg.strip() in p)
        ] if context_parts else []

        prompt = self.reactive_constructor.build_reactive_prompt(
            thought_chain=recent_thoughts,
            raw_events=new_thoughts,
            context_parts=filtered_context,
            last_user_msg=last_user_msg,
            pending_actions=pending_actions,
            has_vision=has_vision
        )

        response = self._call_ollama(
            prompt=prompt,
            model=self.config.thought_model,
            system_prompt=None,
            mode="cognitive"
        )

        self.logger.thinking(response)

        thoughts, actions, should_speak, next_mode = self._parse_cognitive_response(response)

        if response:
            self._submit_to_judge("reactive", prompt, response)

        self.logger.tool(
            f"[REACTIVE RESULT] "
            f"Thoughts: {len(thoughts)}, "
            f"Actions: {len(actions)}, "
            f"Speak: {should_speak}, "
            f"Next: {next_mode or '(fallback)'}"
        )

        actions = self._validate_actions(actions)
        return thoughts, actions, should_speak, next_mode

    async def _proactive_processing_by_type(
        self, prompt_type: PromptType, context_parts: List[str]
    ) -> Optional[Dict]:
        recent_thoughts = self.thought_buffer.get_thoughts_for_response()
        ongoing_ctx = self.thought_buffer.get_ongoing_context()

        if prompt_type == PromptType.REFLECTIVE:
            thought_count = len(self.thought_buffer.get_thoughts_for_response())
            is_startup = thought_count < 3
            prompt = self.reflective_constructor.build_reflective_prompt(
                thought_chain=recent_thoughts,
                ongoing_context=ongoing_ctx,
                query=ongoing_ctx,
                is_startup=is_startup
            )

        elif prompt_type == PromptType.PROACTIVE:
            time_since_user = self.thought_buffer.get_time_since_last_user_input()
            time_context = f"{int(time_since_user)}s since last user input"
            prompt = self.proactive_constructor.build_proactive_prompt(
                thought_chain=recent_thoughts,
                ongoing_context=ongoing_ctx,
                time_context=time_context
            )

        elif prompt_type == PromptType.RESPONSIVE:
            if self.logger:
                self.logger.system(
                    "[Proactive] RESPONSIVE mode detected - skipping "
                    "(responses handled by processing_delegator)"
                )
            return None

        else:
            self.logger.warning(f"[Proactive] Unknown prompt type: {prompt_type}")
            return None

        response = self._call_ollama(
            prompt=prompt,
            model=self.config.thought_model,
            system_prompt=None,
            mode="cognitive"
        )

        self.logger.thinking(response)

        thought, actions, should_speak, next_mode = self._parse_cognitive_response(response)

        if response:
            type_map = {
                'PromptType.REFLECTIVE': 'reflective',
                'PromptType.PROACTIVE':  'proactive',
            }
            judge_type = type_map.get(str(prompt_type), str(prompt_type).lower().split('.')[-1])
            self._submit_to_judge(judge_type, prompt, response)

        thought_text = thought[0] if thought else None

        if not thought_text:
            return None

        actions = self._validate_actions(actions)
        return {'thought': thought_text, 'should_speak': should_speak, 'actions': actions, 'next_mode': next_mode}


    def _parse_cognitive_response(self, response: str) -> Tuple[List[str], List[Dict], bool, Optional[str]]:
        thoughts = []
        thought_match = re.search(r'<thought>(.*?)</thought>', response, re.DOTALL)
        if thought_match:
            thought_text = thought_match.group(1).strip()
            if thought_text:
                thoughts.append(thought_text)
        else:
            in_block = False
            for line in response.strip().split('\n'):
                line = line.strip()
                if line.startswith(('```xml', '```', '<speak>', '<actions>', '<next_mode>')):
                    in_block = True
                    continue
                if line.startswith(('</speak>', '</actions>', '</next_mode>')):
                    in_block = False
                    continue
                if not in_block and line and not line.startswith('<') and not line.startswith('```'):
                    thoughts.append(line)

        speak_match = re.search(r'<speak>\s*(YES|NO)\s*</speak>', response, re.IGNORECASE)
        should_speak = speak_match.group(1).upper() == 'YES' if speak_match else False

        actions = []
        actions_match = re.search(r'<actions>(.*?)</actions>', response, re.DOTALL)
        if actions_match:
            try:
                actions_text = re.sub(r'```json\s*|\s*```', '', actions_match.group(1).strip())
                actions = json.loads(actions_text)
                if not isinstance(actions, list):
                    actions = [actions]
            except json.JSONDecodeError as e:
                self.logger.warning(f"[Parse] Failed to parse actions: {e}")
                actions = []

        next_mode_type = parse_agent_next_mode(response)
        next_mode = next_mode_type.value if next_mode_type else None

        return thoughts, actions, should_speak, next_mode

    async def _execute_action_mode(
        self, actions: List[Dict], context_parts: List[str], mode_context: str
    ):
        if not actions or not self.tool_manager:
            return

        try:
            start_time = time.time()
            normalized_actions = self._normalize_action_format(actions)

            if not normalized_actions:
                self.logger.warning("[Action Mode] No valid actions after normalization")
                return

            self.logger.system(
                f"[Action Mode] Processing {len(normalized_actions)} actions from {mode_context} mode"
            )

            thought_chain = self.thought_buffer.get_thoughts_for_response()
            action_context = (
                f"Executing {len(normalized_actions)} tool(s) from {mode_context} thinking. "
                f"Focus on correct parameter formatting and usage."
            )

            # Do not forward context_parts — action mode only needs the thought
            # chain and tool docs. context_parts would re-inject last user message
            # and other content already present in the thought chain.
            prompt = self.action_constructor.build_action_prompt(
                thought_chain=thought_chain,
                planned_actions=normalized_actions,
                context_parts=None,
                action_context=action_context
            )

            self.logger.action("[Action Mode] Calling AI to construct complete tool commands...")

            action_response = self._call_ollama(
                prompt=prompt,
                model=self.config.action_model,
                system_prompt=None
            )

            self.logger.action(f"[Action Mode] AI Response: {action_response}")

            if action_response:
                self._submit_to_judge("action", prompt, action_response)

            formatted_actions = self._parse_action_response(action_response)

            if not formatted_actions:
                self.logger.warning("[Action Mode] No valid actions in AI response, using original")
                formatted_actions = self._inject_fallback_args(normalized_actions, thought_chain)

            self.logger.system(
                f"[Action Mode] Executing {len(formatted_actions)} formatted tool calls"
            )

            await self.tool_manager.execute_structured_actions(
                formatted_actions, self.thought_buffer
            )

            elapsed = time.time() - start_time
            self.logger.system(
                f"[Action Mode] Completed {len(formatted_actions)} actions in {elapsed:.1f}s"
            )

        except Exception as e:
            self.logger.error(f"[Action Mode] Execution error: {e}")
            import traceback
            traceback.print_exc()

    def _normalize_action_format(self, actions: List[Dict]) -> List[Dict]:
        normalized = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            tool_name = action.get('tool', '')
            args = action.get('args', [])
            if isinstance(args, dict):
                args_list = list(args.values())
            elif isinstance(args, list):
                args_list = args
            else:
                args_list = [args] if args else []
            normalized.append({'tool': tool_name, 'args': args_list})
        return normalized

    def _parse_action_response(self, response: str) -> List[Dict]:
        try:
            actions_match = re.search(r'<actions>(.*?)</actions>', response, re.DOTALL)
            if not actions_match:
                self.logger.warning("[Action Parse] No <actions> block found in response")
                return []

            actions_text = actions_match.group(1).strip()
            actions_text = re.sub(r'```json\s*|\s*```', '', actions_text)
            actions_text = re.sub(r',\s*([}\]])', r'\1', actions_text)
            actions = json.loads(actions_text)

            if not isinstance(actions, list):
                actions = [actions]

            valid_actions = []
            for action in actions:
                if not isinstance(action, dict):
                    continue
                tool_call = action.get('tool', '')
                args = action.get('args', [])
                if not tool_call or '.' not in tool_call:
                    self.logger.warning(
                        f"[Action Parse] Invalid tool format (missing command): {tool_call}"
                    )
                    continue
                if not isinstance(args, list):
                    args = [args] if args else []
                valid_actions.append({'tool': tool_call, 'args': args})

            if valid_actions:
                self.logger.success(
                    f"[Action Parse] Extracted {len(valid_actions)} properly formatted actions"
                )

            return valid_actions

        except json.JSONDecodeError as e:
            self.logger.error(f"[Action Parse] JSON decode error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"[Action Parse] Parse error: {e}")
            return []
        
    def _apply_next_mode(
        self, next_mode: Optional[str], current_mode: str, context_parts: List[str]
    ):
        """
        Persist the agent's requested next mode.
        If the agent omitted <next_mode>, falls back to the timer-based decider.
        Logs only when the mode actually changes.
        """
        if next_mode:
            if next_mode != self._requested_next_mode:
                self.logger.system(f"[Mode] {current_mode} -> {next_mode}")
                self._requested_next_mode = next_mode
            return

        # Fallback: model omitted <next_mode> — use timer-based routing
        time_since = self.thought_buffer.get_time_since_last_user_input()
        decision = self.response_decider.decide_prompt_type(
            has_incoming_input=False,
            time_since_last_input=time_since,
            thought_buffer=self.thought_buffer,
            context_parts=context_parts
        )
        fallback = decision.prompt_type.value
        if fallback != self._requested_next_mode:
            self.logger.system(f"[Mode] {current_mode} -> {fallback} (fallback, no <next_mode> tag)")
            self._requested_next_mode = fallback

    def _inject_fallback_args(self, actions: List[Dict], thought_chain: List) -> List[Dict]:
        if not thought_chain:
            return actions

        fallback_query = ""
        for thought in reversed(thought_chain):
            text = str(thought).strip()
            if text and len(text) > 5:
                fallback_query = text[:120]
                break

        if not fallback_query:
            return actions

        result = []
        for action in actions:
            tool = action.get('tool', '')
            args = action.get('args', [])
            if tool and '.' not in tool:
                tool = f"{tool}.search"
            if not args:
                self.logger.system(
                    f"[Action Fallback] Injecting thought-derived query into "
                    f"'{tool}': \"{fallback_query[:60]}...\""
                )
                args = [fallback_query]
            result.append({'tool': tool, 'args': args})

        return result

    def _validate_actions(self, actions: List[Dict]) -> List[Dict]:
        if not actions or not self.tool_manager:
            return []

        enabled_tools = self.tool_manager.get_enabled_tool_names()
        valid = []
        for a in actions:
            if not isinstance(a, dict):
                continue
            tool = a.get('tool')
            if not tool or not isinstance(tool, str):
                continue
            tool_name = tool.split('.')[0] if '.' in tool else tool
            if tool_name in enabled_tools:
                valid.append(a)
        return valid

    def _clean_thought_text(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'```[a-z]*\s*|\s*```', '', text)
        return text.strip()

    def _call_ollama(self, prompt: str, model: str, system_prompt: Optional[str] = None,
                     image_data: str = "", mode: str = "cognitive") -> str:
        import requests

        if mode == "action":
            temperature = self.config.ollama_temperature_action
        elif mode == "response":
            temperature = self.config.ollama_temperature_response
        else:
            temperature = self.config.ollama_temperature_cognitive

        try:
            if image_data:
                url = f"{self.config.ollama_endpoint}/api/chat"
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt, "images": [image_data]})
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": "24h",
                    "options": {
                        "temperature": temperature,
                        "top_p": self.config.ollama_top_p,
                        "top_k": self.config.ollama_top_k,
                        "repeat_penalty": self.config.ollama_repeat_penalty,
                        "num_predict": self.config.ollama_max_tokens
                    }
                }
            else:
                url = f"{self.config.ollama_endpoint}/api/generate"
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                payload = {
                    "model": model,
                    "prompt": full_prompt,
                    "stream": False,
                    "temperature": temperature,
                    "top_p": self.config.ollama_top_p,
                    "top_k": self.config.ollama_top_k,
                    "repeat_penalty": self.config.ollama_repeat_penalty,
                    "num_predict": self.config.ollama_max_tokens,
                    "keep_alive": "24h"
                }
                if self.config.ollama_seed is not None:
                    payload["seed"] = self.config.ollama_seed

            response = requests.post(url, json=payload, timeout=self.config.ollama_timeout)
            response.raise_for_status()
            result = response.json()
            content = result.get("response", "") or result.get("message", {}).get("content", "")
            return content.strip()

        except Exception as e:
            self.logger.error(f"Ollama API error: {e}")
            return ""

    def _check_chat_engagement_need(self) -> bool:
        if not getattr(self.controls, 'CHAT_ENGAGEMENT', False):
            return False
        return self.thought_buffer.should_engage_with_chat()

    def _create_chat_engagement_thought(self) -> Optional[Dict]:
        unengaged = self.thought_buffer.get_unengaged_messages(max_messages=5)
        if not unengaged:
            return None

        chat_summary_parts = [
            f"{msg.get('username', 'Someone')}: {msg.get('message', '')}"
            for msg in unengaged
        ]
        summary = "\n".join(chat_summary_parts)
        return {
            'content': f"Chat activity:\n{summary}",
            'source': 'chat_engagement',
            'original_ref': summary,
            'timestamp': time.time()
        }

    async def _check_urgent_reminders(self):
        pass

    def get_performance_stats(self) -> Dict:
        pending_count = 0
        if self.action_state_manager:
            pending_count = len(self.action_state_manager.get_pending_actions())
        return {
            'thought_buffer_size': len(self.thought_buffer._thoughts),
            'raw_events_pending': len(self.thought_buffer.get_unprocessed_events()),
            'thoughts_not_in_response': self.thought_buffer.count_not_included_in_response(),
            'pending_actions': pending_count,
            'prompt_system': 'modular_simplified_trigger'
        }

    def verify_tool_injection(self):
        if not self.tool_manager:
            self.logger.error("[Verification] No tool_manager in ThoughtProcessor!")
            return False

        enabled = self.tool_manager.get_enabled_tool_names()
        self.logger.system(f"[Verification] ThoughtProcessor has tool_manager")
        self.logger.system(f"[Verification] Enabled tools: {enabled}")

        constructors = [
            ('reactive', self.reactive_constructor),
            ('reflective', self.reflective_constructor),
            ('proactive', self.proactive_constructor),
            ('action', self.action_constructor)
        ]

        all_ok = True
        for name, constructor in constructors:
            if not hasattr(constructor, 'tool_manager'):
                self.logger.error(f"[Verification] {name} constructor missing tool_manager!")
                all_ok = False
            elif constructor.tool_manager is None:
                self.logger.error(f"[Verification] {name} constructor has None tool_manager!")
                all_ok = False
            else:
                self.logger.success(f"[Verification] {name} constructor has tool_manager")

        return all_ok
    
    @staticmethod
    def _mode_str_to_prompt_type(mode: str) -> PromptType:
        return {
            'proactive':  PromptType.PROACTIVE,
            'reflective': PromptType.REFLECTIVE,
        }.get(mode, PromptType.PROACTIVE)