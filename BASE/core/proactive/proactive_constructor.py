# Filename: BASE/core/proactive/proactive_constructor.py
"""
Proactive Thinking Prompt Constructor - OPTIMIZED
==================================================
Minimal tool instructions in cognitive modes - detailed docs only in ACTION mode

Prompt Components:
1. Personality (core identity + proactive style)
2. Thought chain (recent thoughts for continuity)
3. Available tool list (minimal overview only)
4. Current situation (what's happening now)
5. Response guidance (how to plan ahead)

Focus: Looking forward, anticipating needs, setting goals
Tool execution: Handled by separate ACTION mode
"""

from typing import List, Optional
from BASE.core.proactive.proactive_parts import ProactivePromptParts
from personality.prompts.personality_prompt_parts import PersonalityPromptParts
from personality.bot_info import username


class ProactiveConstructor:
    """Constructs prompts for proactive thinking"""

    __slots__ = ('tool_manager', 'logger', 'parts', 'personality')
    
    def __init__(self, tool_manager=None, logger=None):
        self.tool_manager = tool_manager
        self.logger = logger
        self.parts = ProactivePromptParts()
        self.personality = PersonalityPromptParts()
    
    def build_proactive_prompt(
        self,
        thought_chain: List[str],
        ongoing_context: str,
        time_context: Optional[str] = None
    ) -> str:
        """Build complete proactive thinking prompt"""
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
        
        sections.append(self._format_current_situation(ongoing_context, time_context))
        sections.append(self.parts.get_speak_decision_instructions())
        sections.append(self.parts.get_spoken_response_rules())
        sections.append(self.parts.get_output_format())
        
        reminders = self.personality.format_important_reminders()
        if reminders:
            sections.append(reminders)
        
        prompt = "\n".join(sections)
        
        if self.logger:
            self.logger.proactive(f"{prompt}")
        
        return prompt
    
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
    
    def _build_minimal_tool_list(self) -> str:
        """Build minimal tool list (names + 1-line descriptions only)"""
        from BASE.handlers.tool_instruction_builder import ToolInstructionBuilder
        
        builder = ToolInstructionBuilder(
            tool_manager=self.tool_manager,
            logger=self.logger
        )
        
        tool_section = builder.build_tool_list_section()
        
        if tool_section:
            return f"\n<available_tools>\n{tool_section}\n</available_tools>"
        
        return ""
    
    def _format_current_situation(
        self,
        ongoing_context: str,
        time_context: Optional[str]
    ) -> str:
        """Format current situation and time context"""
        sections = []
        
        sections.append("<current_situation>\n## CURRENT SITUATION\n")
        sections.append(ongoing_context if ongoing_context else "Open time for proactive")
        
        if time_context:
            sections.append("\n## TIME CONTEXT\n")
            sections.append(time_context)
        elif ongoing_context == "Open time for proactive":
            sections.append("\n## TIME CONTEXT\n")
            sections.append(f"{username} is not currently active. Good time to plan ahead.")
        
        sections.append("</current_situation>")
        
        return "\n".join(sections)