# Filename: BASE/core/action/action_constructor.py
"""
Action Mode Prompt Constructor
================================
Executes tools with correct parameters based on thought chain.
Does not produce a <next_mode> tag — the system resumes the agent's
last requested next_mode after action completion.
"""

from typing import List, Dict, Optional, Any
from BASE.core.action.action_parts import ActionPromptParts
from personality.prompts.personality_prompt_parts import PersonalityPromptParts


class ActionConstructor:
    __slots__ = ('tool_manager', 'logger', 'parts', 'personality')

    def __init__(self, tool_manager=None, logger=None):
        self.tool_manager = tool_manager
        self.logger = logger
        self.parts = ActionPromptParts()
        self.personality = PersonalityPromptParts()

    def build_action_prompt(
        self,
        thought_chain: List[str],
        planned_actions: List[Dict[str, Any]],
        context_parts: List[str] = None,
        action_context: Optional[str] = None
    ) -> str:
        context_parts = context_parts or []
        sections = []

        sections.append(self.parts.get_mode_instructions())
        sections.append(self._format_recent_experiences(thought_chain))
        sections.append(self._format_planned_actions(planned_actions))

        if self.tool_manager and planned_actions:
            tool_instructions = self._get_tool_instructions_for_actions(planned_actions)
            if tool_instructions:
                sections.append(tool_instructions)

        if action_context:
            sections.append(f"\n<action_context>\n## ACTION CONTEXT\n\n{action_context}\n</action_context>")

        sections.append(self.parts.get_execution_principles())

        if context_parts:
            sections.append(self._format_additional_context(context_parts))

        sections.append(self.parts.get_output_format())

        prompt = "\n".join(sections)

        if self.logger:
            self.logger.action(f"{prompt}")

        return prompt

    def _format_recent_experiences(self, thoughts: List[str]) -> str:
        """Last few thoughts only — no label legend needed for tool execution"""
        if not thoughts:
            return "\n<recent_experience>\n## RECENT THOUGHTS\n\nNo recent thoughts.\n</recent_experience>"
        recent = thoughts[-50:] if len(thoughts) > 50 else thoughts
        formatted = "\n".join(f"- {t}" for t in recent)
        return f"\n<recent_experience>\n## RECENT THOUGHTS\n\n{formatted}\n</recent_experience>"

    def _format_planned_actions(self, actions: List[Dict[str, Any]]) -> str:
        if not actions:
            return "\n<planned_actions>\n## PLANNED ACTIONS\n\nNo actions planned.\n</planned_actions>"

        lines = ["\n<planned_actions>\n## PLANNED ACTIONS\n"]
        lines.append("Execute these tools with proper commands and parameters.\n")

        for i, action in enumerate(actions, 1):
            tool_name = action.get('tool', 'unknown')
            args = action.get('args', [])
            lines.append(f"**[Action {i}]** `{tool_name}`")
            if args:
                if isinstance(args, list) and args:
                    args_str = ", ".join(f'"{a}"' for a in args)
                    lines.append(f"  - Args hint: [{args_str}]")
                elif isinstance(args, dict):
                    lines.append(f"  - Args hint: {args}")
            else:
                lines.append("  - No args provided — extract from thoughts and tool docs")

        lines.append("\n**Task:** Format each as `tool.command` with correct parameters.")
        lines.append("</planned_actions>")
        return "\n".join(lines)

    def _get_tool_instructions_for_actions(self, actions: List[Dict[str, Any]]) -> str:
        if not self.tool_manager or not actions:
            return ""

        tool_names = {
            (a.get('tool', '').split('.')[0] if '.' in a.get('tool', '') else a.get('tool', ''))
            for a in actions
            if a.get('tool', '')
        }

        if not tool_names:
            return ""

        from BASE.handlers.tool_instruction_builder import ToolInstructionBuilder

        builder = ToolInstructionBuilder(tool_manager=self.tool_manager, logger=self.logger)
        instructions = builder.build_retrieved_tool_instructions(list(tool_names))

        if instructions:
            if self.logger:
                self.logger.system(
                    f"[Action Constructor] Instructions for: {', '.join(tool_names)}"
                )
            return f"\n<tool_instructions>\n{instructions}\n</tool_instructions>"

        return ""

    def _format_additional_context(self, context_parts: List[str]) -> str:
        formatted = "\n\n".join(context_parts)
        return f"\n<additional_context>\n## ADDITIONAL CONTEXT\n\n{formatted}\n</additional_context>"