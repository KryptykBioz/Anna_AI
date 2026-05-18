# Filename: BASE/core/reflective/reflective_constructor.py
"""
Reflective Thinking Prompt Constructor
========================================
Memory-grounded reflection. Used when the agent requests reflective mode via
<next_mode>reflective</next_mode>, or during startup (first N thoughts).

Startup vs standard reflection differ primarily in context loading:
- Startup: loads identity, personality examples, long-term summaries, recent history
- Standard: loads memory context matched to current thoughts/query
"""

from datetime import datetime, timedelta
from typing import List, Optional
from BASE.core.reflective.reflective_parts import ReflectivePromptParts
from personality.prompts.personality_prompt_parts import PersonalityPromptParts


class ReflectiveConstructor:
    __slots__ = (
        'tool_manager', 'logger', 'parts', 'personality',
        '_tool_list_cache_key', '_tool_list_cache_value', 'memory_search'
    )

    def __init__(self, tool_manager=None, logger=None, memory_search=None):
        self.tool_manager = tool_manager
        self.logger = logger
        self.memory_search = memory_search
        self.parts = ReflectivePromptParts()
        self.personality = PersonalityPromptParts()
        self._tool_list_cache_key = None
        self._tool_list_cache_value = ''

    def build_reflective_prompt(
        self,
        thought_chain: List[str],
        ongoing_context: str,
        query: Optional[str] = None,
        is_startup: bool = False
    ) -> str:
        sections = []

        sections.append(self.personality.get_unified_personality())

        current_ctx = self.personality.format_current_context()
        if current_ctx:
            sections.append(current_ctx)

        if self.memory_search:
            examples = self._get_thought_examples(
                thought_chain=thought_chain,
                ongoing_context=ongoing_context,
                query=query,
                is_startup=is_startup
            )
            if examples:
                sections.append(examples)

        if thought_chain:
            sections.append(self._format_recent_experiences(thought_chain))

        if is_startup:
            sections.append(self.parts.get_startup_instructions())
        else:
            sections.append(self.parts.get_mode_instructions())

        if self.tool_manager:
            tool_list = self._build_minimal_tool_list()
            if tool_list:
                sections.append(tool_list)

        sections.append(self.parts.get_speak_decision_instructions())

        if is_startup:
            sections.append(self._build_startup_context())
        else:
            if self.memory_search:
                memory_context = self._get_memory_context(
                    thought_chain=thought_chain,
                    ongoing_context=ongoing_context,
                    query=query
                )
                if memory_context:
                    sections.append(f"\n<memory_context>\n## RELEVANT MEMORIES\n\n{memory_context}\n</memory_context>")
            sections.append(self._build_standard_context(ongoing_context))

        sections.append(self.parts.get_grounding_rules())
        sections.append(self.parts.get_output_format())

        reminders = self.personality.format_important_reminders()
        if reminders:
            sections.append(reminders)

        prompt = "\n".join(sections)

        if self.logger:
            mode = "Startup" if is_startup else "Standard"
            self.logger.reflective(f"[{mode}]\n{prompt}")

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

    def _get_thought_examples(
        self,
        thought_chain: List[str],
        ongoing_context: str,
        query: Optional[str],
        is_startup: bool
    ) -> str:
        if not self.memory_search:
            return ""

        query_parts = []
        if query:
            query_parts.append(query)
        if ongoing_context:
            query_parts.append(ongoing_context)
        if thought_chain:
            query_parts.extend(thought_chain)

        if not query_parts:
            if is_startup:
                query_parts.append("startup thoughts personality examples")
            else:
                return ""

        try:
            examples = self.memory_search.get_thought_interpretation_examples(
                context=" ".join(query_parts),
                k=1,
                min_similarity=0.3,
                mode_filter='reflective'
            )
            if not examples:
                return ""
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Reflective Constructor] Error retrieving thought examples: {e}")
            return ""

        if self.logger:
            self.logger.memory(
                f"[Personality Retrieval] Found {len(examples.split('SITUATION:')) - 1} thought examples"
            )

        return f"\n<personality_examples>\n## PERSONALITY EXAMPLES\n\n{examples}\n</personality_examples>"

    def _get_memory_context(
        self,
        thought_chain: List[str],
        ongoing_context: str,
        query: Optional[str]
    ) -> str:
        if not self.memory_search:
            return ""

        from BASE.config.bot_info import username, agentname

        query_parts = []
        if query:
            query_parts.append(query)
        if ongoing_context:
            query_parts.append(ongoing_context)
        if thought_chain:
            query_parts.extend(thought_chain[-5:])

        if not query_parts:
            return ""

        combined_query = " ".join(query_parts)
        text_lower = combined_query.lower()
        context_sections = []

        if any(kw in text_lower for kw in ('yesterday', 'last night', 'this morning')):
            try:
                yesterday_ctx = self.memory_search.get_yesterday_context(max_entries=1)
                if yesterday_ctx:
                    yesterday_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    context_sections.append(f"## YESTERDAY ({yesterday_date})\n{yesterday_ctx}")
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[Reflective] Yesterday context error: {e}")

        if any(kw in text_lower for kw in ('earlier', 'before', 'this morning', 'today')):
            try:
                medium_results = self.memory_search.search_medium_memory_combined(
                    user_input=combined_query,
                    recent_thoughts=thought_chain[-5:] if thought_chain else [],
                    k=1,
                    use_embedding_combination=True
                )
                if medium_results:
                    entries = "\n".join(
                        f"[{r['timestamp']}] {username if r['role'] == 'user' else agentname}: "
                        f"{r['content']} (relevance: {r['similarity']:.2f})"
                        for r in medium_results
                    )
                    context_sections.append(f"## EARLIER TODAY\n{entries}")
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[Reflective] Medium memory error: {e}")

        if any(kw in text_lower for kw in ('remember', 'recall', 'before', 'past', 'history', 'ago')):
            try:
                long_results = self.memory_search.search_long_memory_combined(
                    user_input=combined_query,
                    recent_thoughts=thought_chain[-5:] if thought_chain else [],
                    k=1,
                    use_embedding_combination=True
                )
                if long_results:
                    entries = "\n".join(
                        f"[{r['date']}] {r['summary']} (relevance: {r['similarity']:.2f})"
                        for r in long_results
                    )
                    context_sections.append(f"## PAST CONVERSATIONS\n{entries}")
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[Reflective] Long memory error: {e}")

        if any(kw in text_lower for kw in ('how to', 'explain', 'what is', 'guide', 'tell me about')):
            try:
                base_results = self.memory_search.search_base_knowledge_combined(
                    user_input=combined_query,
                    recent_thoughts=thought_chain[-5:] if thought_chain else [],
                    k=1,
                    min_similarity=0.4,
                    use_embedding_combination=True
                )
                if base_results:
                    entries = "\n".join(
                        f"[{r.get('metadata', {}).get('source_file', 'unknown')}] "
                        f"{r['text']} (relevance: {r['similarity']:.2f})"
                        for r in base_results
                    )
                    context_sections.append(f"## KNOWLEDGE BASE\n{entries}")
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[Reflective] Base knowledge error: {e}")

        result = "\n\n".join(context_sections) if context_sections else ""

        if result and self.logger:
            self.logger.memory(f"[Reflective Memory] Retrieved {len(context_sections)} memory sections")

        return result

    def _build_startup_context(self) -> str:
        sections = []

        identity = self._load_identity_knowledge()
        if identity:
            sections.append(f"## WHO YOU ARE\n{identity}")

        personality = self._load_startup_personality()
        if personality:
            sections.append(f"## YOUR PERSONALITY\n{personality}")

        summaries = self._load_startup_long_memories()
        if summaries:
            sections.append(f"## LONG-TERM MEMORIES\n{summaries}")

        yesterday = self._load_yesterday_context()
        if yesterday:
            sections.append(f"## YESTERDAY'S CONTEXT\n{yesterday}")

        recent = self._load_recent_history()
        if recent:
            sections.append(f"## RECENT HISTORY\n{recent}")

        if not sections:
            return "\n<startup_context>\n## STARTUP\n\nNo startup context available.\n</startup_context>"

        body = "\n\n".join(sections)
        return f"\n<startup_context>\n## STARTUP CONTEXT\n\n{body}\n</startup_context>"

    def _build_standard_context(self, ongoing_context: str) -> str:
        body = ongoing_context if ongoing_context else "Open time for reflection."
        return f"\n<current_situation>\n## CURRENT SITUATION\n\n{body}\n</current_situation>"

    def _load_identity_knowledge(self) -> str:
        if not self.memory_search:
            return ""
        try:
            results = self.memory_search.search_long_memory(
                "core identity personality traits preferences", k=1
            )
            if not results:
                return ""
            facts = [r['summary'] for r in results if r['similarity'] > 0.7]
            return "\n".join(f"- {f}" for f in facts) if facts else ""
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Startup] Error loading identity: {e}")
            return ""

    def _load_startup_personality(self) -> str:
        if not self.memory_search:
            return ""
        try:
            examples = self.memory_search.get_personality_examples(
                query="personality traits behavior patterns preferences", k=1
            )
            return examples or ""
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Startup] Error loading personality: {e}")
            return ""

    def _load_startup_long_memories(self) -> str:
        if not self.memory_search:
            return ""
        try:
            results = self.memory_search.search_long_memory(
                "important events relationships goals", k=1
            )
            if not results:
                return ""
            summaries = [f"- {r['summary']}" for r in results if r['similarity'] > 0.6]
            return "\n".join(summaries) if summaries else ""
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Startup] Error loading long memories: {e}")
            return ""

    def _load_yesterday_context(self) -> str:
        if not self.memory_search:
            return ""
        try:
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            results = self.memory_search.search_long_memory(
                f"yesterday {yesterday_str} events interactions", k=1
            )
            if not results:
                return ""
            events = [f"- {r['summary']}" for r in results if r['similarity'] > 0.5]
            return "\n".join(events) if events else "No significant events from yesterday."
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Startup] Error loading yesterday: {e}")
            return ""

    def _load_recent_history(self) -> str:
        if not self.memory_search:
            return ""
        try:
            results = self.memory_search.search_long_memory(
                "recent conversation interactions", k=1
            )
            if not results:
                return ""
            history = [f"- {r['summary']}" for r in results if r['similarity'] > 0.5]
            return "\n".join(history) if history else "No recent history available."
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Startup] Error loading recent history: {e}")
            return ""