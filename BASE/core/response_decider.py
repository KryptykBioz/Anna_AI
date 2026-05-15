# Filename: BASE/core/response_decider.py
"""
Response Decider - Fallback Routing Only
=========================================
Primary routing is now agent-driven via <next_mode> tags in cognitive mode output.
This module serves as the FALLBACK when:
- The agent produces no <next_mode> tag (parse failure)
- The system is starting cold (no prior agent output)
- A hard override is needed (e.g. forced action injection)

Decision Flow (fallback only):
1. Incoming input → Reactive
2. Recent input (<6 min) → Proactive
3. No input (6+ min) → Reflective

Agent-driven routing:
- Agent outputs <next_mode>reactive|proactive|reflective|action</next_mode>
- System reads this tag and routes accordingly
- Action mode always resumes at the agent's last requested next_mode after completion
"""

from typing import Optional, List
from dataclasses import dataclass
from enum import Enum


class PromptType(Enum):
    REACTIVE = "reactive"
    PROACTIVE = "proactive"
    REFLECTIVE = "reflective"
    ACTION = "action"
    RESPONSIVE = "responsive"


@dataclass
class PromptDecision:
    """
    Container for prompt decision results.

    next_mode is populated from the agent's <next_mode> tag when available.
    When None, the fallback timer-based logic applies.
    """
    __slots__ = ('prompt_type', 'reasoning', 'context_flags', 'next_mode')

    def __init__(
        self,
        prompt_type: PromptType,
        reasoning: str,
        context_flags: dict = None,
        next_mode: Optional[str] = None
    ):
        self.prompt_type = prompt_type
        self.reasoning = reasoning
        self.context_flags = context_flags if context_flags is not None else {}
        self.next_mode = next_mode

    def __repr__(self):
        return (
            f"PromptDecision(prompt_type={self.prompt_type}, "
            f"reasoning={self.reasoning!r}, "
            f"context_flags={self.context_flags}, "
            f"next_mode={self.next_mode!r})"
        )

    def __eq__(self, other):
        if not isinstance(other, PromptDecision):
            return NotImplemented
        return (
            self.prompt_type == other.prompt_type
            and self.reasoning == other.reasoning
            and self.context_flags == other.context_flags
            and self.next_mode == other.next_mode
        )


# Valid agent-specified next modes mapped to PromptType
_AGENT_MODE_MAP = {
    'reactive':   PromptType.REACTIVE,
    'proactive':  PromptType.PROACTIVE,
    'reflective': PromptType.REFLECTIVE,
    'action':     PromptType.ACTION,
}


def parse_agent_next_mode(raw_output: str) -> Optional[PromptType]:
    """
    Extract <next_mode> tag from agent output and return the corresponding PromptType.
    Returns None if tag is absent or value is unrecognised (triggers fallback).

    Args:
        raw_output: Raw string output from a cognitive mode LLM call

    Returns:
        PromptType or None
    """
    import re
    match = re.search(r'<next_mode>\s*(\w+)\s*</next_mode>', raw_output, re.IGNORECASE)
    if not match:
        return None
    return _AGENT_MODE_MAP.get(match.group(1).lower())


class ResponseDecider:
    """
    Fallback mode router. Primary routing is agent-driven via parse_agent_next_mode().

    Use decide_prompt_type() only when no agent next_mode is available.
    """

    __slots__ = ('agentname', 'username', 'logger', 'REFLECTION_THRESHOLD')

    def __init__(self, agentname: str, username: str, logger=None):
        self.agentname = agentname
        self.username = username
        self.logger = logger
        self.REFLECTION_THRESHOLD = 360.0  # 6 minutes

    # ========================================================================
    # AGENT-DRIVEN ROUTING (primary path)
    # ========================================================================

    def decide_from_agent_output(
        self,
        raw_output: str,
        has_incoming_input: bool,
        time_since_last_input: float,
        context_parts: List[str] = None
    ) -> PromptDecision:
        """
        Route using agent's <next_mode> tag if present, else fall back to timer logic.

        Args:
            raw_output: Raw LLM output from last cognitive mode
            has_incoming_input: Whether new input is buffered
            time_since_last_input: Seconds since last user input
            context_parts: Additional context strings

        Returns:
            PromptDecision
        """
        agent_mode = parse_agent_next_mode(raw_output)

        if agent_mode is not None:
            # if self.logger:
            #     self.logger.system(f"[Router] Agent-driven: {agent_mode.value}")
            return PromptDecision(
                prompt_type=agent_mode,
                reasoning=f"Agent requested: {agent_mode.value}",
                context_flags=self._build_context_flags(agent_mode, context_parts or []),
                next_mode=agent_mode.value
            )

        # if self.logger:
        #     self.logger.system("[Router] No <next_mode> tag — using fallback timer routing")

        return self.decide_prompt_type(
            has_incoming_input=has_incoming_input,
            time_since_last_input=time_since_last_input,
            context_parts=context_parts
        )

    # ========================================================================
    # FALLBACK ROUTING (timer-based)
    # ========================================================================

    def decide_prompt_type(
        self,
        has_incoming_input: bool,
        time_since_last_input: float,
        thought_buffer=None,
        context_parts: List[str] = None
    ) -> PromptDecision:
        """
        Fallback: timer-based mode selection. Called when no agent next_mode is available.
        """
        context_parts = context_parts or []

        if has_incoming_input:
            return self._create_reactive_decision(context_parts)

        if time_since_last_input < self.REFLECTION_THRESHOLD:
            return self._create_proactive_decision(time_since_last_input)

        return self._create_reflective_decision(time_since_last_input)

    def _create_reactive_decision(self, context_parts: List[str]) -> PromptDecision:
        has_vision = self._detect_vision_data(context_parts)
        has_chat = self._detect_chat_data(context_parts)
        reasoning = "New input detected → Reactive (fallback)"
        if has_vision:
            reasoning += " (vision)"
        if has_chat:
            reasoning += " (chat)"
        return PromptDecision(
            prompt_type=PromptType.REACTIVE,
            reasoning=reasoning,
            context_flags={
                'has_vision': has_vision,
                'has_chat': has_chat,
                'needs_tool_list': True,
                'needs_grounding_rules': has_vision
            }
        )

    def _create_proactive_decision(self, time_since_last: float) -> PromptDecision:
        minutes = int(time_since_last / 60)
        return PromptDecision(
            prompt_type=PromptType.PROACTIVE,
            reasoning=f"Recent input ({minutes}m ago) → Proactive (fallback)",
            context_flags={
                'needs_tool_list': True,
                'time_since_input': time_since_last,
                'is_proactive': True
            }
        )

    def _create_reflective_decision(self, time_since_last: float) -> PromptDecision:
        minutes = int(time_since_last / 60)
        return PromptDecision(
            prompt_type=PromptType.REFLECTIVE,
            reasoning=f"No input for {minutes}m → Reflective (fallback)",
            context_flags={
                'needs_memory_retrieval': True,
                'needs_tool_list': True,
                'time_since_input': time_since_last,
                'is_reflection': True
            }
        )

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _build_context_flags(self, mode: PromptType, context_parts: List[str]) -> dict:
        base = {'needs_tool_list': mode in (PromptType.REACTIVE, PromptType.PROACTIVE, PromptType.REFLECTIVE)}
        if mode == PromptType.REACTIVE:
            base['has_vision'] = self._detect_vision_data(context_parts)
            base['has_chat'] = self._detect_chat_data(context_parts)
            base['needs_grounding_rules'] = base['has_vision']
        elif mode == PromptType.REFLECTIVE:
            base['needs_memory_retrieval'] = True
        return base

    def _detect_vision_data(self, context_parts: List[str]) -> bool:
        return any(
            ind in part.lower()
            for part in context_parts
            for ind in ('vision', 'image', 'screenshot', 'visual', 'screen')
        )

    def _detect_chat_data(self, context_parts: List[str]) -> bool:
        return any(
            ind in part.lower()
            for part in context_parts
            for ind in ('chat', 'live chat', 'twitch', 'viewer')
        )

    def get_prompt_constructor_path(self, prompt_type: PromptType) -> str:
        return {
            PromptType.REACTIVE:   "BASE.core.reactive.reactive_constructor",
            PromptType.REFLECTIVE: "BASE.core.reflective.reflective_constructor",
            PromptType.PROACTIVE:  "BASE.core.proactive.proactive_constructor",
            PromptType.ACTION:     "BASE.core.action.action_constructor",
        }.get(prompt_type, "")

    def format_decision_summary(self, decision: PromptDecision) -> str:
        parts = [f"Type: {decision.prompt_type.value}"]
        if decision.next_mode:
            parts.append(f"NextMode: {decision.next_mode}")
        flags = [k for k, v in decision.context_flags.items() if v]
        if flags:
            parts.append(f"Flags: {', '.join(flags)}")
        return " | ".join(parts)