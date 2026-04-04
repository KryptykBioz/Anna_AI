# Filename: BASE/core/thinking_modes.py
"""
Thinking Modes
===========================
REMOVED: prompt_builder dependency (now uses constructors directly from processor)
Focuses on mode determination and context building only
"""
import time
from typing import List, Optional
from personality.bot_info import username


class ThinkingModes:
    """
    Thinking mode determination and context building
    REFACTORED: No longer handles prompt construction
    """
    __slots__ = (
        'processor', 'config', 'controls', 'logger',
        'tool_manager', 'action_state_manager'
    )
    
    # Thresholds
    STARTUP_THOUGHT_THRESHOLD = 3
    SELF_REFLECTION_IDLE_THRESHOLD = 360.0  # 6 minutes
    
    def __init__(self, processor, config, controls, logger):
        """Initialize thinking modes"""
        self.processor = processor
        self.config = config
        self.controls = controls
        self.logger = logger
        
        self.tool_manager = None
        self.action_state_manager = None
    
    # ========================================================================
    # CONTEXT BUILDING (shared by all modes)
    # ========================================================================
    
    async def build_thought_context(self) -> List[str]:
        """Build context for thought processing (NO CHAT)"""
        context_parts = []
        
        # Tool state (FIRST)
        tool_state = self._get_tool_state_summary()
        if tool_state:
            context_parts.insert(0, tool_state)
        
        # Session files (SECOND)
        if hasattr(self.processor, 'session_file_manager'):
            sfm = self.processor.session_file_manager
            if sfm and sfm.session_files:
                last_user_msg = self.processor.thought_buffer.get_last_user_input()
                session_context = sfm.get_context_for_query(last_user_msg)
                if session_context:
                    context_parts.append(session_context)
        
        # User context
        user_ctx = self.processor.thought_buffer.get_user_context()
        if user_ctx:
            context_parts.append(user_ctx)
        
        # Ongoing context
        ongoing_ctx = self.processor.thought_buffer.get_ongoing_context()
        if ongoing_ctx:
            context_parts.append(f"Current Focus: {ongoing_ctx}")
        
        # Goal context
        if self.processor.thought_buffer.current_goal:
            goal_summary = self.processor.thought_buffer.get_goal_summary()
            if goal_summary:
                context_parts.append(goal_summary)
        
        return context_parts
    
    def _get_tool_state_summary(self) -> Optional[str]:
        """Get actionable tool state summary"""
        if self.tool_manager and hasattr(self.tool_manager, 'action_state_manager'):
            action_mgr = self.tool_manager.action_state_manager
            failure_summary = action_mgr.get_recent_failures_summary(max_failures=3)
            
            if failure_summary:
                return failure_summary
            
            pending = action_mgr.get_pending_actions()
            if len(pending) > 3:
                return f"## PENDING TOOLS\n{len(pending)} actions in progress (may be slow)"
        
        return None
    
    # ========================================================================
    # MODE DETERMINATION
    # ========================================================================
    
    def determine_thinking_mode(self, context_parts: List[str]) -> str:
        """
        Determine thinking mode:
        
        Priority:
        1. STARTUP: First 3 thoughts → memory_reflection_startup
        2. Reactive: new data to act on
        3. Responsive: form a spoken response to the user
        4. Proactive: plan for future actions (no new input to process)
        5. Reflective: self-reflection on past interactions (no new input and idle)
        
        Returns:
            Mode string (used by thought_processor for decision)
        """
        # Get current thought count
        thought_count = len(self.processor.thought_buffer.get_thoughts_for_response())
        
        # PRIORITY 1: STARTUP (First 3 thoughts only)
        if thought_count < self.STARTUP_THOUGHT_THRESHOLD:
            if self.logger:
                self.logger.system(
                    f"[Mode: STARTUP] Thought {thought_count + 1}/{self.STARTUP_THOUGHT_THRESHOLD}"
                )
            return 'memory_reflection_startup'
        
        # SELF-REFLECTION
        time_since_user = self.processor.thought_buffer.get_time_since_last_user_input()
        
        # Get thoughts AND user input for keyword detection
        recent_thoughts = self.processor.thought_buffer.get_thoughts_for_response()
        thoughts_text = " ".join([str(t) for t in recent_thoughts]).lower()
        
        last_user_input = self.processor.thought_buffer.get_last_user_input() or ""
        combined_text = f"{thoughts_text} {last_user_input.lower()}"
        
        # Memory trigger keywords
        memory_triggers = [
            'remember', 'recall', 'before', 'earlier', 'last time',
            'yesterday', 'last night', 'this morning', 'ago',
            'used to', 'back when', 'when we', 'that time',
            'you said', 'we talked', 'mentioned', 'told me',
            'wonder if', 'curious about', 'did i', 'did we'
        ]
        
        has_past_mention = any(trigger in combined_text for trigger in memory_triggers)
        
        if has_past_mention or time_since_user >= self.SELF_REFLECTION_IDLE_THRESHOLD:
            reason = []
            if has_past_mention:
                matched = [t for t in memory_triggers if t in combined_text]
                reason.append(f"past mentioned ({matched[0]})")
            if time_since_user >= self.SELF_REFLECTION_IDLE_THRESHOLD:
                minutes = time_since_user / 60.0
                reason.append(f"{minutes:.0f}+ min idle")
            
            if self.logger:
                self.logger.system(f"[Mode: SELF-REFLECTION] {' + '.join(reason)}")
            return 'memory_reflection'
        
        # FUTURE PROACTIVE
        proactive_triggers = [
            'should', 'will', 'plan', 'next', 'prepare',
            'could', 'might', 'consider', 'want to', 'need to'
        ]
        
        has_proactive = any(trigger in thoughts_text for trigger in proactive_triggers)
        
        if has_proactive:
            if self.logger:
                self.logger.system("[Mode: PROACTIVE] Proactive keywords detected")
            return 'future_proactive'
        
        # STANDARD (default proactive)
        if self.logger and thought_count == self.STARTUP_THOUGHT_THRESHOLD:
            self.logger.system("[Mode: STANDARD] Exited startup → Standard proactive")
        
        return 'standard'
    
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