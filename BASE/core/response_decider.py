# Filename: BASE/core/response_decider.py
"""
Response Decider - Agent-Driven Response Only
==============================================
CRITICAL CHANGE: This module ONLY decides which thinking mode to use.
It does NOT decide when the agent should speak.

The agent decides when to speak via <speak>YES</speak> or <speak>NO</speak> tags.

Decision Flow:
1. Incoming input → Reactive thinking
2. Recent input (<6 min) → Proactive thinking  
3. No input (6+ min) → Reflective thinking

COMPLETELY REMOVED:
- Priority marker detection ([HIGH], [CRITICAL])
- Agent name mention detection
- Question mark detection  
- Urgent reminder detection
- ALL hardcoded response forcing logic

Response timing is 100% controlled by the agent's <speak> tags.
"""

from typing import Optional, List
from dataclasses import dataclass
from enum import Enum


class PromptType(Enum):
    """Types of prompts the agent can construct"""
    REACTIVE = "reactive"
    PROACTIVE = "proactive"
    REFLECTIVE = "reflective"
    ACTION = "action"
    RESPONSIVE = "responsive"


@dataclass
class PromptDecision:
    """
    Container for prompt decision results
    
    Attributes:
        prompt_type: Which prompt constructor to use
        reasoning: Human-readable reasoning for decision
        context_flags: Additional flags for prompt construction
    """
    __slots__ = ('prompt_type', 'reasoning', 'context_flags')
    
    def __init__(self, prompt_type: PromptType, reasoning: str, context_flags: dict = None):
        self.prompt_type = prompt_type
        self.reasoning = reasoning
        self.context_flags = context_flags if context_flags is not None else {}
    
    def __repr__(self):
        return (f"PromptDecision(prompt_type={self.prompt_type}, "
                f"reasoning={self.reasoning!r}, context_flags={self.context_flags})")
    
    def __eq__(self, other):
        if not isinstance(other, PromptDecision):
            return NotImplemented
        return (self.prompt_type == other.prompt_type and 
                self.reasoning == other.reasoning and
                self.context_flags == other.context_flags)


class ResponseDecider:
    """
    Determines which thinking mode to use based on input timing
    
    Decision Logic (SIMPLE):
    1. New input → Reactive (process it)
    2. Recent input (<6 min) → Proactive (think about it)
    3. Old input (6+ min) → Reflective (review memory)
    
    Does NOT analyze content for "priority" or "questions" or "agent mentions"
    The agent decides when to speak via <speak>YES/NO</speak> tags
    """
    
    __slots__ = ('agentname', 'username', 'logger', 'REFLECTION_THRESHOLD')
    
    def __init__(self, agentname: str, username: str, logger=None):
        """
        Initialize response decider
        
        Args:
            agentname: Agent's name
            username: User's name
            logger: Optional logger instance
        """
        self.agentname = agentname
        self.username = username
        self.logger = logger
        
        # Timing threshold for switching to reflective mode
        self.REFLECTION_THRESHOLD = 360.0  # 6 minutes
    
    # ========================================================================
    # MAIN DECISION ENTRY POINT
    # ========================================================================
    
    def decide_prompt_type(
        self,
        has_incoming_input: bool,
        time_since_last_input: float,
        thought_buffer = None,
        context_parts: List[str] = None
    ) -> PromptDecision:
        """
        Decide which thinking mode to use (SIMPLIFIED)
        
        No content analysis. No priority detection. Just timing-based.
        
        Args:
            has_incoming_input: Whether there's new input to process
            time_since_last_input: Seconds since last user input
            thought_buffer: ThoughtBuffer instance (not used for decision)
            context_parts: Additional context strings
        
        Returns:
            PromptDecision indicating which thinking mode
        """
        context_parts = context_parts or []
        
        # Simple 3-way decision based on timing only:
        
        # 1. New input → Process it (Reactive)
        if has_incoming_input:
            return self._create_reactive_decision(context_parts)
        
        # 2. Recent input → Think about it (Proactive)
        if time_since_last_input < self.REFLECTION_THRESHOLD:
            return self._create_proactive_decision(time_since_last_input)
        
        # 3. Old input → Reflect on memories (Reflective)
        return self._create_reflective_decision(time_since_last_input)
    
    # ========================================================================
    # DECISION BUILDERS
    # ========================================================================
    
    def _create_reactive_decision(self, context_parts: List[str]) -> PromptDecision:
        """Create decision for reactive thinking (processing new input)"""
        has_vision = self._detect_vision_data(context_parts)
        has_chat = self._detect_chat_data(context_parts)
        
        reasoning = "New input detected → Reactive thinking mode"
        if has_vision:
            reasoning += " (vision data present)"
        if has_chat:
            reasoning += " (chat activity present)"
        
        context_flags = {
            'has_vision': has_vision,
            'has_chat': has_chat,
            'needs_tool_list': True,
            'needs_grounding_rules': has_vision
        }
        
        return PromptDecision(
            prompt_type=PromptType.REACTIVE,
            reasoning=reasoning,
            context_flags=context_flags
        )
    
    def _create_proactive_decision(self, time_since_last: float) -> PromptDecision:
        """Create decision for proactive thinking (planning, goals)"""
        minutes = int(time_since_last / 60)
        reasoning = f"Recent input ({minutes}m ago) → Proactive thinking mode"
        
        context_flags = {
            'needs_tool_list': True,
            'time_since_input': time_since_last,
            'is_proactive': True
        }
        
        return PromptDecision(
            prompt_type=PromptType.PROACTIVE,
            reasoning=reasoning,
            context_flags=context_flags
        )
    
    def _create_reflective_decision(self, time_since_last: float) -> PromptDecision:
        """Create decision for reflective thinking (memory review)"""
        minutes = int(time_since_last / 60)
        reasoning = f"No input for {minutes}m → Reflective thinking mode"
        
        context_flags = {
            'needs_memory_retrieval': True,
            'needs_tool_list': True,
            'time_since_input': time_since_last,
            'is_reflection': True
        }
        
        return PromptDecision(
            prompt_type=PromptType.REFLECTIVE,
            reasoning=reasoning,
            context_flags=context_flags
        )
    
    # ========================================================================
    # CONTEXT DETECTION (for flags only, not for decision logic)
    # ========================================================================
    
    def _detect_vision_data(self, context_parts: List[str]) -> bool:
        """Detect if vision data is present (for context flags)"""
        for part in context_parts:
            if any(indicator in part.lower() for indicator in [
                'vision', 'image', 'screenshot', 'visual', 'screen'
            ]):
                return True
        return False
    
    def _detect_chat_data(self, context_parts: List[str]) -> bool:
        """Detect if chat data is present (for context flags)"""
        for part in context_parts:
            if any(indicator in part.lower() for indicator in [
                'chat', 'live chat', 'twitch', 'viewer'
            ]):
                return True
        return False
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_prompt_constructor_path(self, prompt_type: PromptType) -> str:
        """
        Get the module path for the appropriate prompt constructor
        
        Args:
            prompt_type: Type of prompt to construct
        
        Returns:
            Module path string
        """
        constructor_map = {
            PromptType.REACTIVE: "BASE.core.reactive.reactive_constructor",
            PromptType.REFLECTIVE: "BASE.core.reflective.reflective_constructor",
            PromptType.PROACTIVE: "BASE.core.proactive.proactive_constructor",
            PromptType.ACTION: "BASE.core.action.action_constructor"
        }
        return constructor_map.get(prompt_type, "")
    
    def should_log_decision(self, decision: PromptDecision) -> bool:
        """Determine if this decision should be logged"""
        # Log reflective mode switches (less common)
        return decision.prompt_type == PromptType.REFLECTIVE
    
    def format_decision_summary(self, decision: PromptDecision) -> str:
        """Format decision as summary string for logging"""
        parts = [f"Type: {decision.prompt_type.value}"]
        
        if decision.context_flags:
            flags = [k for k, v in decision.context_flags.items() if v]
            if flags:
                parts.append(f"Flags: {', '.join(flags)}")
        
        return " | ".join(parts)

