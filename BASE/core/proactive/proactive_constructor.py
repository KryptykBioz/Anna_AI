# Filename: BASE/core/proactive/proactive_constructor.py
"""
Proactive Thinking Prompt Constructor
========================================
Forward-looking planning and goal-driven thinking.
The agent's output includes a <next_mode> tag that drives the next cognitive cycle.
"""

from typing import List, Optional
from BASE.core.proactive.proactive_parts import ProactivePromptParts
from personality.prompts.personality_prompt_parts import PersonalityPromptParts
from BASE.config.bot_info import username


class ProactiveConstructor:
    __slots__ = (
        'tool_manager', 'memory_search', 'logger', 'parts', 'personality',
        '_tool_list_cache_key', '_tool_list_cache_value'
    )

    def __init__(self, tool_manager=None, memory_search=None, logger=None):
        self.tool_manager = tool_manager
        self.memory_search = memory_search
        self.logger = logger
        self.parts = ProactivePromptParts()
        self.personality = PersonalityPromptParts()
        self._tool_list_cache_key = None
        self._tool_list_cache_value = ''

    def build_proactive_prompt(
        self,
        thought_chain: List[str],
        ongoing_context: str,
        time_context: Optional[str] = None
    ) -> str:
        sections = []

        sections.append(self.personality.get_unified_personality())

        current_ctx = self.personality.format_current_context()
        if current_ctx:
            sections.append(current_ctx)

        sections.append(self._format_recent_experiences(thought_chain))

        if self.memory_search:
            examples = self._get_thought_examples(thought_chain, ongoing_context)
            if examples:
                sections.append(examples)

        sections.append(self.parts.get_mode_instructions())

        if self.tool_manager:
            tool_list = self._build_minimal_tool_list()
            if tool_list:
                sections.append(tool_list)

        sections.append(self._format_current_situation(ongoing_context, time_context))
        sections.append(self.parts.get_speak_decision_instructions())
        sections.append(self.parts.get_output_format())

        reminders = self.personality.format_important_reminders()
        if reminders:
            sections.append(reminders)

        prompt = "\n".join(sections)

        if self.logger:
            self.logger.proactive(f"{prompt}")

        return prompt

    def _get_thought_examples(
        self,
        thought_chain: List[str],
        ongoing_context: str
    ) -> str:
        if not self.memory_search:
            return ""

        query_parts = []
        if thought_chain:
            query_parts.append(" ".join(thought_chain))
        if ongoing_context:
            query_parts.append(ongoing_context)

        if not query_parts:
            return ""

        examples = self.memory_search.get_thought_interpretation_examples(
            context=" ".join(query_parts),
            k=1,
            mode_filter='proactive'
        )

        if not examples:
            return ""

        if self.logger:
            self.logger.memory(
                f"[Personality Retrieval] Found {len(examples.split('SITUATION:')) - 1} thought examples"
            )

        return f"\n<personality_examples>\n## PERSONALITY EXAMPLES\n\n{examples}\n</personality_examples>"

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

    def _format_current_situation(self, ongoing_context: str, time_context: Optional[str]) -> str:
        sections = ["<current_situation>\n## CURRENT SITUATION\n"]

        if ongoing_context:
            sections.append(ongoing_context)
        else:
            sections.append(
                "Use this time to research, gather data, and plan ahead. Anticipate the user's needs "
                "and your own desires. Proactively identify opportunities to add value, solve problems, and make progress. "
                "take notes, set reminders, and prepare for future interactions. "
                "Do not wait — pick up work immediately."
            )

        if time_context:
            sections.append("\n## TIME CONTEXT\n")
            sections.append(time_context)

        sections.append("</current_situation>")
        return "\n".join(sections)