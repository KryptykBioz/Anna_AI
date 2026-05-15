# Filename: BASE/core/responsive/responsive_constructor.py
"""
Responsive Response Prompt Constructor
=========================================
Generates verbal/TTS responses. Always follows a cognitive mode in the same cycle,
so personality context is already established. Uses compact identity reference
instead of full personality block to reduce token cost on repeated calls.
"""

from typing import List, Optional
from BASE.core.responsive.responsive_parts import ResponsivePromptParts
from personality.prompts.personality_prompt_parts import PersonalityPromptParts
from BASE.config.bot_info import username, agentname


class ResponsiveConstructor:
    __slots__ = ('memory_search', 'logger', 'parts', 'personality', '_call_count')

    def __init__(self, memory_search=None, logger=None):
        self.memory_search = memory_search
        self.logger = logger
        self.parts = ResponsivePromptParts()
        self.personality = PersonalityPromptParts()
        self._call_count = 0

    def build_responsive_prompt(
        self,
        thought_chain: List[str],
        user_text: str,
        context_parts: List[str] = None,
        chat_context: Optional[str] = None,
        is_chat_engagement: bool = False
    ) -> str:
        context_parts = context_parts or []
        sections = []

        # Full personality on first call per session; compact reference thereafter
        if self._call_count == 0:
            sections.append(self.personality.get_unified_personality())
        else:
            sections.append(
                f"<identity>You are {agentname}, speaking to {username}. "
                f"Maintain your established personality and voice.</identity>"
            )
        self._call_count += 1

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

    def reset_session(self):
        """Call at session start to re-enable full personality on next build"""
        self._call_count = 0

    def _format_recent_experiences(self, thoughts: List[str]) -> str:
        if not thoughts:
            return "\n<recent_experience>\n## RECENT EXPERIENCES\n\nNo recent input.\n</recent_experience>"
        formatted = "\n".join(f"- {t}" for t in thoughts)
        return f"\n<recent_experience>\n## RECENT EXPERIENCES\n\n{formatted}\n</recent_experience>"

    def _get_response_examples(
        self,
        thought_chain: List[str],
        user_text: str,
        chat_context: Optional[str]
    ) -> str:
        if not self.memory_search:
            return ""

        query_parts = []
        if thought_chain:
            query_parts.append(" ".join(thought_chain))
        if user_text:
            query_parts.append(user_text)
        if chat_context:
            query_parts.extend(chat_context.split('\n'))

        if not query_parts:
            return ""

        combined_query = " ".join(query_parts)

        examples = self.memory_search.get_response_generation_examples(
            context=combined_query,
            k=1
        )

        if not examples:
            return ""

        if self.logger:
            self.logger.memory(
                f"[Personality Retrieval] Found {len(examples.split('SITUATION:')) - 1} examples"
            )

        return f"\n<personality_examples>\n## PERSONALITY EXAMPLES\n\n{examples}\n</personality_examples>"

    def _format_context(self, context_parts: List[str]) -> str:
        formatted = "\n\n".join(context_parts)
        return f"\n<context>\n## CONTEXT\n\n{formatted}\n</context>"

    def _get_response_guidance(self, is_chat_engagement: bool) -> str:
        if is_chat_engagement:
            return self.parts.get_chat_engagement_guidance()
        return self.parts.get_standard_guidance()