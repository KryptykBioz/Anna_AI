# Filename: BASE/core/responsive/responsive_constructor.py
"""
Responsive Response Prompt Constructor
===================================
Constructs prompts for generating verbal/TTS responses to users.

Prompt Components:
1. Personality (core identity + speaking style)
2. Response examples (from memory) - FIXED: Now uses combined thought+user context
3. Thought chain (recent internal thoughts)
4. Response guidance (urgency-based instructions)

Focus: Natural responsive communication based on accumulated thoughts
"""

from typing import List, Optional
from BASE.core.responsive.responsive_parts import ResponsivePromptParts
from personality.prompts.personality_prompt_parts import PersonalityPromptParts
from personality.bot_info import username


class ResponsiveConstructor:
    """Constructs prompts for responsive (spoken) response generation"""

    __slots__ = ('memory_search', 'logger', 'parts', 'personality')
    
    def __init__(self, memory_search=None, logger=None):
        """
        Initialize responsive constructor
        
        Args:
            memory_search: MemorySearch instance for personality examples
            logger: Optional logger instance
        """
        self.memory_search = memory_search
        self.logger = logger
        
        self.parts = ResponsivePromptParts()
        self.personality = PersonalityPromptParts()
    
    def build_responsive_prompt(
        self,
        thought_chain: List[str],
        user_text: str,
        context_parts: List[str] = None,
        chat_context: Optional[str] = None,
        is_chat_engagement: bool = False
    ) -> str:
        """
        Build complete responsive (spoken) response prompt
        
        Args:
            thought_chain: Recent thoughts (for context)
            user_text: Current user input
            context_parts: Additional context (memory, game, etc.)
            chat_context: Live chat messages
            is_chat_engagement: Whether responding to chat
        
        Returns:
            Complete responsive (spoken) response prompt
        """
        context_parts = context_parts or []
        
        sections = []
        
        sections.append(self.personality.get_unified_personality())
        
        current_ctx = self.personality.format_current_context()
        if current_ctx:
            sections.append(current_ctx)
        
        if self.memory_search:
            examples = self._get_response_examples(
                thought_chain=thought_chain,
                user_text=user_text,
                chat_context=chat_context
            )
            if examples:
                sections.append(examples)
        
        sections.append(self._format_recent_experiences(thought_chain))
        
        if context_parts:
            sections.append(self._format_context(context_parts))
        
        if user_text and not is_chat_engagement:
            sections.append(f'\n<user_message>\n**{username}:** "{user_text}"\n</user_message>')
        elif is_chat_engagement and chat_context:
            sections.append(f'\n<chat_to_address>\n## CHAT TO ADDRESS\n\n{chat_context}\n</chat_to_address>')
        
        sections.append(self._get_response_guidance(is_chat_engagement))
        sections.append(self.parts.get_output_format())
        
        reminders = self.personality.format_important_reminders()
        if reminders:
            sections.append(reminders)
        
        prompt = "\n".join(sections)
        
        if self.logger:
            self.logger.responsive(f"{prompt}")
        
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
    
    def _get_response_examples(
        self,
        thought_chain: List[str],
        user_text: str,
        chat_context: Optional[str]
    ) -> str:
        """
        FIXED: Get personality-matched response examples using combined context
        
        Now retrieves examples based on BOTH:
        - Recent thought chain (what the agent has been thinking)
        - User input / chat context (what's being responded to)
        
        This ensures examples are relevant to the full situation, not just
        the user's words in isolation.
        """
        if not self.memory_search:
            return ""
        
        recent_thoughts = thought_chain if thought_chain else []
        
        query_parts = []
        
        if recent_thoughts:
            thought_text = " ".join(recent_thoughts)
            query_parts.append(thought_text)
        
        if user_text:
            query_parts.append(user_text)
        
        if chat_context:
            chat_lines = chat_context.split('\n')
            query_parts.extend(chat_lines)
        
        if not query_parts:
            return ""
        
        combined_query = " ".join(query_parts)
        if user_text:
            combined_query += f" {user_text}"
        
        examples = self.memory_search.get_response_generation_examples(
            context=combined_query,
            k=1
        )
        
        if not examples:
            return ""
        
        if self.logger:
            thought_preview = recent_thoughts if recent_thoughts else "none"
            user_preview = user_text if user_text else "none"
            self.logger.memory(
                f"[Personality Retrieval] Found {len(examples.split('SITUATION:')) - 1} examples "
                f"(thoughts: '{thought_preview}...', user: '{user_preview}...')"
            )
        
        return f"\n<personality_examples>\n## PERSONALITY EXAMPLES\n\n{examples}\n</personality_examples>"
    
    def _format_context(self, context_parts: List[str]) -> str:
        """Format additional context"""
        relevant_context = context_parts
        formatted = "\n\n".join(relevant_context)
        
        return f"\n<context>\n## CONTEXT\n\n{formatted}\n</context>"
    
    def _get_response_guidance(
        self,
        is_chat_engagement: bool
    ) -> str:
        """Get urgency-appropriate response guidance"""
        if is_chat_engagement:
            return self.parts.get_chat_engagement_guidance()
        else:
            return self.parts.get_standard_guidance()