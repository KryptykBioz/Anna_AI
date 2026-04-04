# Filename: BASE/core/action/action_constructor.py
"""
Action Mode Prompt Constructor - UPDATED
=========================================
Focus: Execute tools with correct parameters based on thought chain

Changes:
- Clearer output format instructions
- Emphasis on parameter extraction from thoughts
- Detailed tool instructions dynamically retrieved
"""

from typing import List, Dict, Optional, Any
from BASE.core.action.action_parts import ActionPromptParts
from personality.prompts.personality_prompt_parts import PersonalityPromptParts


class ActionConstructor:
    """Constructs prompts for action mode (tool execution)"""

    __slots__ = ('tool_manager', 'logger', 'parts', 'personality')
    
    def __init__(self, tool_manager=None, logger=None):
        """
        Initialize action constructor
        
        Args:
            tool_manager: ToolManager instance for tool instructions
            logger: Optional logger instance
        """
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
        """
        Build complete action execution prompt - UPDATED
        
        Args:
            thought_chain: Recent thoughts (for parameter extraction)
            planned_actions: Tool actions to execute
            context_parts: Additional context
            action_context: Why these actions were chosen
        
        Returns:
            Complete action mode prompt
        """
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
    
    # def _format_recent_experiences(self, thoughts: List[str]) -> str:
    #     """Format recent thoughts for action context"""
    #     if not thoughts:
    #         return "\n<thought_chain>\n## YOUR RECENT THOUGHTS\n\nNo recent thoughts.\n</thought_chain>"
        
    #     recent = thoughts[-10:] if len(thoughts) > 10 else thoughts
    #     formatted = "\n".join([f"- {t}" for t in recent])
        
    #     thought_count = len(recent)
    #     return f"\n<thought_chain>\n## YOUR RECENT THOUGHTS ({thought_count} thoughts)\n\n{formatted}\n</thought_chain>"
    
    def _format_recent_experiences(self, thoughts: List[str]) -> str:
        """Format thoughts for context"""
        if not thoughts:
            return "\n<recent_experience>\n## RECENT INPUT\n\nNo recent input.\n</recent_experience>"
        
        formatted = "\n".join([f"- {t}" for t in thoughts])
        return f"""
<recent_experience>
## RECENT EXPERIENCES
### SOURCE LABELS
- [THOUGHT] These are your recent internal thoughts not yet shared with the user
- [SELF] These are your spoken responses (read aloud through TTS)
- [USER] This is the user's input (spoken or text)
- [FAMILY] These are the spoken responses from your AI family members
- [TOOL] These are the results and outputs from tools you've used recently
- [SYSTEM] These are internal processing messages from your code execution
- additional labels can be added as needed to clarify sources of incoming information

### YOUR RECENT EXPERIENCES:
{formatted}
</recent_experience>
"""
    
    def _format_planned_actions(self, actions: List[Dict[str, Any]]) -> str:
        """
        Format planned actions for execution - UPDATED
        
        Args:
            actions: List of action dictionaries with 'tool' and 'args' keys
        
        Returns:
            Formatted actions section
        """
        if not actions:
            return "\n<planned_actions>\n## PLANNED ACTIONS\n\nNo actions planned.\n</planned_actions>"
        
        lines = ["\n<planned_actions>\n## PLANNED ACTIONS\n"]
        lines.append("These are the tools you decided to use. Now execute them with proper parameters.\n")
        
        for i, action in enumerate(actions, 1):
            tool_name = action.get('tool', 'unknown')
            args = action.get('args', [])
            
            lines.append(f"**[Action {i}]** `{tool_name}`")
            
            if args:
                if isinstance(args, list) and args:
                    args_str = ", ".join([f'"{a}"' for a in args])
                    lines.append(f"  - Current args: [{args_str}]")
                elif isinstance(args, dict):
                    lines.append(f"  - Current args: {args}")
                else:
                    lines.append(f"  - Args: {args}")
            else:
                lines.append("  - No args provided yet")
        
        lines.append("\n**Your Task:** Format these tool calls with correct parameters based on your thoughts.")
        lines.append("</planned_actions>")
        
        return "\n".join(lines)
    
    def _get_tool_instructions_for_actions(self, actions: List[Dict[str, Any]]) -> str:
        """
        Get detailed tool instructions for specific tools being executed - UPDATED
        
        Args:
            actions: List of action dictionaries
        
        Returns:
            Formatted tool instructions section
        """
        if not self.tool_manager or not actions:
            return ""
        
        tool_names = set()
        for action in actions:
            tool_name = action.get('tool', '')
            if tool_name:
                base_name = tool_name.split('.')[0] if '.' in tool_name else tool_name
                tool_names.add(base_name)
        
        if not tool_names:
            return ""
        
        from BASE.handlers.tool_instruction_builder import ToolInstructionBuilder
        
        builder = ToolInstructionBuilder(
            tool_manager=self.tool_manager,
            logger=self.logger
        )
        
        instructions = builder.build_retrieved_tool_instructions(list(tool_names))
        
        if instructions:
            if self.logger:
                self.logger.system(
                    f"[Action Constructor] Retrieved instructions for "
                    f"{len(tool_names)} tools: {', '.join(tool_names)}"
                )
            return f"\n<tool_instructions>\n{instructions}\n</tool_instructions>"
        
        return ""
    
    def _format_additional_context(self, context_parts: List[str]) -> str:
        """Format additional context"""
        formatted = "\n\n".join(context_parts)
        return f"\n<additional_context>\n## ADDITIONAL CONTEXT\n\n{formatted}\n</additional_context>"