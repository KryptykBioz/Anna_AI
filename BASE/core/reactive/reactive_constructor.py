# Filename: BASE/core/reactive/reactive_constructor.py
"""
Reactive Thinking Prompt Constructor
======================================
Processes new incoming events. The agent's output includes a <next_mode> tag
that drives the next cognitive cycle.
"""

from typing import List, Optional, Any
from BASE.core.reactive.reactive_parts import ReactivePromptParts
from personality.prompts.personality_prompt_parts import PersonalityPromptParts


class ReactiveConstructor:
    __slots__ = ('tool_manager', 'logger', 'parts', 'personality', '_tool_list_cache_key', '_tool_list_cache_value')

    def __init__(self, tool_manager=None, logger=None):
        self.tool_manager = tool_manager
        self.logger = logger
        self.parts = ReactivePromptParts()
        self.personality = PersonalityPromptParts()
        self._tool_list_cache_key = None
        self._tool_list_cache_value = ''

    def build_reactive_prompt(
        self,
        thought_chain: List[str],
        raw_events: List[Any],
        context_parts: List[str] = None,
        last_user_msg: Optional[str] = None,
        pending_actions: Optional[str] = None,
        has_vision: bool = False
    ) -> str:
        context_parts = context_parts or []
        sections = []

        sections.append(self.personality.get_unified_personality())

        current_ctx = self.personality.format_current_context()
        if current_ctx:
            sections.append(current_ctx)

        sections.append(self._format_recent_experiences(thought_chain))
        sections.append(self.parts.get_mode_instructions())

        if self.tool_manager:
            tool_list = self._build_minimal_tool_list()
            if tool_list:
                sections.append(tool_list)


        sections.append(self._format_incoming_data(raw_events))

        all_system = raw_events and all(
            getattr(e, 'source', '') == 'system_notification' for e in raw_events
        )
        if all_system and last_user_msg and thought_chain:
            user_tag = '[USER]'
            self_tag = '[SELF]'
            last_user_idx = -1
            last_self_idx = -1
            for i, t in enumerate(thought_chain):
                if user_tag in t:
                    last_user_idx = i
                if self_tag in t:
                    last_self_idx = i
            if last_user_idx > last_self_idx:
                sections.append(
                    "\n<idle_escalation>\n"
                    "[WARNING] All current events are system notifications. "
                    f"The user's last message has not been addressed: \"{last_user_msg}\"\n"
                    "You MUST escalate: set next_mode to proactive or reflective. "
                    "Do NOT output reactive as next_mode this cycle.\n"
                    "</idle_escalation>"
                )

        sections.append(self.parts.get_speak_decision_instructions())

        if pending_actions and pending_actions.strip():
            sections.append(f"\n<pending_actions>\n## PENDING ACTIONS\n\n{pending_actions}\n</pending_actions>")

        if context_parts:
            sections.append(self._format_additional_context(context_parts))

        if has_vision:
            sections.append(self.parts.get_vision_grounding())

        sections.append(self.parts.get_grounding_rules())
        sections.append(self.parts.get_output_format())

        reminders = self.personality.format_important_reminders()
        if reminders:
            sections.append(reminders)

        prompt = "\n".join(sections)

        if self.logger:
            self.logger.reactive(f"{prompt}")

        return prompt

    def _build_minimal_tool_list(self) -> str:
        from BASE.handlers.tool_instruction_builder import ToolInstructionBuilder

        enabled_tools = self.tool_manager.get_enabled_tool_names()
        cache_key = frozenset(enabled_tools)

        if cache_key == self._tool_list_cache_key:
            return self._tool_list_cache_value

        builder = ToolInstructionBuilder(tool_manager=self.tool_manager, logger=self.logger)
        tool_section = builder.build_tool_list_section()
        result = f"\n<available_tools>\n{tool_section}\n</available_tools>" if tool_section else ''
        self._tool_list_cache_key = cache_key
        self._tool_list_cache_value = result
        return result

    def _format_recent_experiences(self, thoughts: List[str]) -> str:
        if not thoughts:
            return "\n<recent_experience>\n## RECENT EXPERIENCES\n\nNo recent input.\n</recent_experience>"
        formatted = "\n".join(f"- {t}" for t in thoughts)
        return f"\n<recent_experience>\n## RECENT EXPERIENCES\n\n{formatted}\n</recent_experience>"

    def _format_incoming_data(self, raw_events: List[Any]) -> str:
        if not raw_events:
            return "\n<incoming_data>\n## NEW INCOMING DATA\n\nNo new data.\n</incoming_data>"
        lines = ["\n<incoming_data>\n## NEW INCOMING DATA\n"]
        for i, event in enumerate(raw_events, 1):
            source = getattr(event, 'source', 'unknown')
            data = getattr(event, 'content', getattr(event, 'data', str(event)))
            lines.append(f"**[Event {i}]** `{source}`: {data}")
        lines.append("</incoming_data>")
        return "\n".join(lines)

    def _format_additional_context(self, context_parts: List[str]) -> str:
        formatted = "\n\n".join(context_parts)
        return f"\n<additional_context>\n## ADDITIONAL CONTEXT\n\n{formatted}\n</additional_context>"