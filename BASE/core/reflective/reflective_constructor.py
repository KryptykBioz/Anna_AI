    # Filename: BASE/core/reflective/reflective_constructor.py
"""
Reflective Thinking Prompt Constructor - OPTIMIZED
===================================================
Minimal tool instructions in cognitive modes - detailed docs only in ACTION mode

Prompt Components:
1. Personality (core identity + reflective style)
2. Thought chain (recent thoughts for continuity)
3. Available tool list (minimal overview only)
4. Memory context (past experiences to reflect on)
5. Response guidance (how to reflect)

Focus: Looking backward, learning from experience, making connections
Tool execution: Handled by separate ACTION mode
"""

from typing import List, Optional
from BASE.core.reflective.reflective_parts import ReflectivePromptParts
from personality.prompts.personality_prompt_parts import PersonalityPromptParts


class ReflectiveConstructor:
    """Constructs prompts for reflective thinking"""

    __slots__ = ('memory_search', 'tool_manager', 'logger', 'parts', 'personality')
    STARTUP_THOUGHT_THRESHOLD = 3
    def __init__(self, memory_search=None, tool_manager=None, logger=None):
        self.memory_search = memory_search
        self.tool_manager = tool_manager
        self.logger = logger
        self.parts = ReflectivePromptParts()
        self.personality = PersonalityPromptParts()
    
    # def build_reflective_prompt(
    #     self,
    #     thought_chain: List[str],
    #     memory_context: str,
    #     is_startup: bool = False
    # ) -> str:
    #     """Build complete reflective thinking prompt"""
    #     sections = []
        
    #     sections.append(self.personality.get_unified_personality())
        
    #     current_ctx = self.personality.format_current_context()
    #     if current_ctx:
    #         sections.append(current_ctx)
        
    #     sections.append(self._format_recent_experiences(thought_chain))
        
    #     if is_startup:
    #         sections.append(self.parts.get_startup_instructions())
    #     else:
    #         sections.append(self.parts.get_mode_instructions())
        
    #     if self.tool_manager:
    #         tool_list = self._build_minimal_tool_list()
    #         if tool_list:
    #             sections.append(tool_list)
        
    #     sections.append(self._format_memory_context(memory_context))
    #     sections.append(self.parts.get_speak_decision_instructions())
    #     sections.append(self.parts.get_grounding_rules())
    #     sections.append(self.parts.get_spoken_response_rules())
    #     sections.append(self.parts.get_output_format())
        
    #     reminders = self.personality.format_important_reminders()
    #     if reminders:
    #         sections.append(reminders)
        
    #     prompt = "\n".join(sections)
        
    #     if self.logger:
    #         self.logger.reflective(f"{prompt}")
        
    #     return prompt

    def build_reflective_prompt(
        self,
        thought_chain: List[str],
        ongoing_context: str,
        query: Optional[str] = None,
        is_startup: bool = False
    ) -> str:
        """Build complete reflective thinking prompt"""
        thought_count = len(thought_chain)
        is_actually_startup = is_startup or thought_count < self.STARTUP_THOUGHT_THRESHOLD
        
        if is_actually_startup and self.logger:
            self.logger.system(
                f"[Reflective Prompt] STARTUP MODE "
                f"(thought {thought_count + 1}/{self.STARTUP_THOUGHT_THRESHOLD})"
            )
        
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
                is_startup=is_actually_startup
            )
            if examples:
                sections.append(examples)
        
        if thought_chain:
            sections.append(self._format_recent_experiences(thought_chain))
        
        if is_actually_startup:
            sections.append(self.parts.get_startup_instructions())
        else:
            sections.append(self.parts.get_mode_instructions())
        
        # CRITICAL FIX: Actually build and inject tool list
        if self.tool_manager:
            tool_list = self._build_minimal_tool_list()
            if tool_list:
                sections.append(tool_list)
                if self.logger:
                    enabled = self.tool_manager.get_enabled_tool_names()
                    self.logger.system(
                        f"[Reflective Constructor] Injected {len(enabled)} tool(s): "
                        f"{', '.join(enabled)}"
                    )
            else:
                if self.logger:
                    self.logger.warning("[Reflective Constructor] No tools enabled")
        else:
            if self.logger:
                self.logger.error("[Reflective Constructor] No tool_manager - tools unavailable!")

        sections.append(self.parts.get_speak_decision_instructions())
        
        if not is_actually_startup and self.memory_search:
            memory_context = self._get_memory_context(
                thought_chain=thought_chain,
                ongoing_context=ongoing_context,
                query=query
            )
            if memory_context:
                sections.append(f"\n## RELEVANT MEMORIES\n{memory_context}")
        
        if is_actually_startup:
            sections.append(self._build_startup_context())
        else:
            sections.append(self._build_standard_context(ongoing_context, query))

        sections.append(self.parts.get_spoken_response_rules())
        sections.append(self.parts.get_output_format())
        
        reminders = self.personality.format_important_reminders()
        if reminders:
            sections.append(reminders)
        
        prompt = "\n".join(sections)
        
        if self.logger:
            mode = "Startup" if is_actually_startup else "Standard"
            self.logger.reflective(f"[{mode}]\n{prompt}")
        
        return prompt

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
    
    def _get_thought_examples(
        self,
        thought_chain: List[str],
        ongoing_context: str,
        query: Optional[str],
        is_startup: bool
    ) -> str:
        """Get personality-matched thought examples using combined context"""
        if not self.memory_search:
            return ""
        
        # Build combined query from available context
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
        
        combined_query = " ".join(query_parts)
        
        try:
            # Use get_thought_interpretation_examples (for BEHAVIORS)
            examples = self.memory_search.get_thought_interpretation_examples(
                context=combined_query,
                k=1,
                min_similarity=0.3
            )
            
            if not examples:
                return ""
        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"[Reflective Constructor] Error retrieving thought examples: {e}"
                )
            return ""
        
        if self.logger:
            thought_preview = thought_chain[-1] if thought_chain else "none"
            context_preview = ongoing_context if ongoing_context else "none"
            self.logger.memory(
                f"[Reflective Thought Examples] Found examples "
                f"(thoughts: '{thought_preview}...', context: '{context_preview}...')"
            )
        
        return f"\n## THOUGHT EXAMPLES\n\n{examples}"
    
    def _get_memory_context(
        self,
        thought_chain: List[str],
        ongoing_context: str,
        query: Optional[str]
    ) -> str:
        """
        Retrieve ACTUAL MEMORIES to reflect on
        This is separate from thought examples (which are behavioral patterns)
        """
        if not self.memory_search:
            return ""
        
        from datetime import datetime, timedelta
        from personality.bot_info import username, agentname
        
        # Build query from available context
        query_parts = []
        if query:
            query_parts.append(query)
        if ongoing_context:
            query_parts.append(ongoing_context)
        if thought_chain:
            query_parts.extend(thought_chain[-5:])  # Last 5 thoughts
        
        if not query_parts:
            return ""
        
        combined_query = " ".join(query_parts)
        text_lower = combined_query.lower()
        
        context_sections = []
        
        # Detect memory needs from keywords
        # Yesterday's context
        if any(kw in text_lower for kw in ['yesterday', 'last night', 'this morning']):
            try:
                yesterday_ctx = self.memory_search.get_yesterday_context(max_entries=1)
                if yesterday_ctx:
                    yesterday_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    context_sections.append(f"## YESTERDAY ({yesterday_date})")
                    context_sections.append(yesterday_ctx)
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[Reflective] Yesterday context error: {e}")
        
        # Medium memory (earlier today)
        if any(kw in text_lower for kw in ['earlier', 'before', 'this morning', 'today']):
            try:
                medium_results = self.memory_search.search_medium_memory_combined(
                    user_input=combined_query,
                    recent_thoughts=thought_chain[-5:] if thought_chain else [],
                    k=1,
                    use_embedding_combination=True
                )
                if medium_results:
                    context_sections.append("\n## EARLIER TODAY")
                    for r in medium_results:
                        role = username if r['role'] == 'user' else agentname
                        context_sections.append(
                            f"[{r['timestamp']}] {role}: {r['content']} "
                            f"(relevance: {r['similarity']:.2f})"
                        )
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[Reflective] Medium memory error: {e}")
        
        # Long memory (past days)
        if any(kw in text_lower for kw in ['remember', 'recall', 'before', 'past', 'history', 'ago']):
            try:
                long_results = self.memory_search.search_long_memory_combined(
                    user_input=combined_query,
                    recent_thoughts=thought_chain[-5:] if thought_chain else [],
                    k=1,
                    use_embedding_combination=True
                )
                if long_results:
                    context_sections.append("\n## PAST CONVERSATIONS")
                    for r in long_results:
                        context_sections.append(
                            f"[{r['date']}] {r['summary']} "
                            f"(relevance: {r['similarity']:.2f})"
                        )
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[Reflective] Long memory error: {e}")
        
        # Base knowledge (if asking for info/guidance)
        if any(kw in text_lower for kw in ['how to', 'explain', 'what is', 'guide', 'tell me about']):
            try:
                base_results = self.memory_search.search_base_knowledge_combined(
                    user_input=combined_query,
                    recent_thoughts=thought_chain[-5:] if thought_chain else [],
                    k=1,
                    min_similarity=0.4,
                    use_embedding_combination=True
                )
                if base_results:
                    context_sections.append("\n## KNOWLEDGE BASE")
                    for r in base_results:
                        source = r.get('metadata', {}).get('source_file', 'unknown')
                        context_sections.append(
                            f"[{source}] {r['text']} "
                            f"(relevance: {r['similarity']:.2f})"
                        )
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[Reflective] Base knowledge error: {e}")
        
        result = "\n".join(context_sections) if context_sections else ""
        
        if result and self.logger:
            self.logger.memory(
                f"[Reflective Memory] Retrieved {len(context_sections)} memory sections"
            )
        
        return result
    
    def _format_memory_context(self, memory_context: str) -> str:
        """Format memory context for reflection"""
        return f"""
<memory_context>
## MEMORY CONTEXT

{memory_context if memory_context else "No memories loaded for reflection."}
</memory_context>
"""
    
    def _build_startup_context(self) -> str:
        """Build startup context from various sources"""
        sections = []
        
        # 1. Identity knowledge
        identity = self._load_identity_knowledge()
        if identity:
            sections.append("\n## WHO YOU ARE")
            sections.append(identity)
        
        # 2. Personality examples
        personality = self._load_startup_personality()
        if personality:
            sections.append("\n## YOUR PERSONALITY")
            sections.append(personality)
        
        # 3. Long-term summaries
        summaries = self._load_startup_long_memories()
        if summaries:
            sections.append("\n## LONG-TERM MEMORIES")
            sections.append(summaries)
        
        # 4. Yesterday's context
        yesterday = self._load_yesterday_context()
        if yesterday:
            sections.append("\n## YESTERDAY'S CONTEXT")
            sections.append(yesterday)
        
        # 5. Recent history
        recent = self._load_recent_history()
        if recent:
            sections.append("\n## RECENT HISTORY")
            sections.append(recent)
        
        if not sections:
            return "\n## STARTUP\n\nNo startup context available."
        
        return "\n\n".join(["\n## STARTUP CONTEXT"] + sections)
    
    def _load_identity_knowledge(self) -> str:
        """Load core identity knowledge"""
        if not self.memory_search:
            return ""
        
        try:
            results = self.memory_search.search_long_memory(
                "core identity personality traits preferences",
                k=1
            )
            
            if not results:
                return ""
            
            facts = [r['summary'] for r in results if r['similarity'] > 0.7]
            return "\n".join([f"- {fact}" for fact in facts]) if facts else ""
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Startup] Error loading identity: {e}")
            return ""
    
    def _load_startup_personality(self) -> str:
        """Load personality-defining examples"""
        if not self.memory_search:
            return ""
        
        try:
            examples = self.memory_search.get_personality_examples(
                query="personality traits behavior patterns preferences",
                k=1
            )
            return examples if examples else ""
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Startup] Error loading personality: {e}")
            return ""
    
    def _load_startup_long_memories(self) -> str:
        """Load important long-term memory summaries"""
        if not self.memory_search:
            return ""
        
        try:
            results = self.memory_search.search_long_memory(
                "important events relationships goals",
                k=1
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
        """Load yesterday's important events"""
        if not self.memory_search:
            return ""
        
        try:
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_str = yesterday.strftime("%Y-%m-%d")
            
            results = self.memory_search.search_long_memory(
                f"yesterday {yesterday_str} events interactions",
                k=1
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
        """Load recent conversation history"""
        if not self.memory_search:
            return ""
        
        try:
            results = self.memory_search.search_long_memory(
                "recent conversation interactions",
                k=1
            )
            
            if not results:
                return ""
            
            history = [f"- {r['summary']}" for r in results if r['similarity'] > 0.5]
            return "\n".join(history) if history else "No recent history available."
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Startup] Error loading recent history: {e}")
            return ""
    
    def _build_standard_context(
        self,
        ongoing_context: str,
        query: Optional[str]
    ) -> str:
        """
        Build standard reflective context
        NOTE: Memory retrieval is now handled separately in build_reflective_prompt
        """
        sections = []
        
        # 1. Current situation
        sections.append("## CURRENT SITUATION")
        sections.append(ongoing_context if ongoing_context else "Open time for reflection")
        
        # Memory retrieval has been moved to _get_memory_context()
        # called separately in build_reflective_prompt
        
        return "\n\n".join(sections)
    