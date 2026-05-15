# Filename: BASE/core/thinking_modes.py
"""
Thinking Modes
===========================
Context building and periodic maintenance only.
Mode determination is now agent-driven via <next_mode> tags.
Fallback routing lives in response_decider.py.
"""
import time
from typing import List, Optional
from BASE.config.bot_info import username


class ThinkingModes:
    """
    Context building for cognitive mode prompts.
    Mode selection has been moved to agent output parsing (response_decider.parse_agent_next_mode).
    """
    __slots__ = (
        'processor', 'config', 'controls', 'logger',
        'tool_manager', 'action_state_manager'
    )

    STARTUP_THOUGHT_THRESHOLD = 3
    STALE_THRESHOLD = 60.0  # seconds — matches grounding_rules in reactive_parts
    
    def __init__(self, processor, config, controls, logger):
        self.processor = processor
        self.config = config
        self.controls = controls
        self.logger = logger
        self.tool_manager = None
        self.action_state_manager = None

    # ========================================================================
    # CONTEXT BUILDING
    # ========================================================================

    async def build_thought_context(self) -> List[str]:
        """Build context for thought processing"""
        context_parts = []

        tool_state = self._get_tool_state_summary()
        if tool_state:
            context_parts.insert(0, tool_state)

        if hasattr(self.processor, 'session_file_manager'):
            sfm = self.processor.session_file_manager
            if sfm and sfm.session_files:
                last_user_msg = self.processor.thought_buffer.get_last_user_input()
                session_context = sfm.get_context_for_query(last_user_msg)
                if session_context:
                    context_parts.append(session_context)

        user_ctx = self.processor.thought_buffer.get_user_context()
        if user_ctx:
            context_parts.append(user_ctx)

        ongoing_ctx = self.processor.thought_buffer.get_ongoing_context()
        if ongoing_ctx:
            context_parts.append(f"Current Focus: {ongoing_ctx}")

        if self.processor.thought_buffer.current_goal:
            goal_summary = self.processor.thought_buffer.get_goal_summary()
            if goal_summary:
                context_parts.append(goal_summary)

        return context_parts

    def _get_tool_state_summary(self) -> Optional[str]:
        """Get actionable tool state summary. Injects stale actions as raw events."""
        if not (self.tool_manager and hasattr(self.tool_manager, 'action_state_manager')):
            return None

        action_mgr = self.tool_manager.action_state_manager

        if hasattr(self.processor, 'thought_buffer'):
            pending = action_mgr.get_pending_actions()
            now = time.time()
            # for action in pending:
            #     elapsed = now - action.initiated_at
            #     if elapsed >= self.STALE_THRESHOLD:
            #         stale_msg = (
            #             f"[STALE] Tool '{action.tool_name}' (id: {action.action_id}) "
            #             f"has not responded in {elapsed:.0f}s — retry required"
            #         )
            #         self.processor.thought_buffer.ingest_raw_data('system_notification', stale_msg)

        failure_summary = action_mgr.get_recent_failures_summary(max_failures=3)
        if failure_summary:
            return failure_summary

        pending = action_mgr.get_pending_actions()
        if len(pending) > 3:
            return f"## PENDING TOOLS\n{len(pending)} actions in progress (may be slow)"

        return None
    
    # ========================================================================
    # STARTUP CHECK
    # ========================================================================

    def is_startup(self) -> bool:
        """True for the first STARTUP_THOUGHT_THRESHOLD thoughts of a session"""
        thought_count = len(self.processor.thought_buffer.get_thoughts_for_response())
        return thought_count < self.STARTUP_THOUGHT_THRESHOLD

    # ========================================================================
    # PERIODIC MAINTENANCE
    # ========================================================================

    async def periodic_memory_integration(self):
        """Periodic memory integration check"""
        if not self.processor.memory_search:
            return

        ongoing_ctx = self.processor.thought_buffer.get_ongoing_context()
        if not ongoing_ctx:
            return

        try:
            memory_results = self.processor.memory_search.search_long_memory(ongoing_ctx, k=1)

            if memory_results and memory_results[0]['similarity'] > 0.6:
                past_experience = memory_results[0]
                memory_thought = (
                    f"I remember discussing {ongoing_ctx} before: "
                    f"{past_experience['summary']}"
                )
                self.processor.thought_buffer.add_processed_thought(
                    memory_thought, 'memory_integration', past_experience['summary']
                )
                self.logger.memory("Integrated relevant memory")
        except Exception as e:
            self.logger.warning(f"Memory integration error: {e}")