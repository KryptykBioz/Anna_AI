# Filename: BASE/recall/memory_integration.py
"""
Memory Integration for AI Core
Efficiently incorporates 4-tier memory system into the flow
"""
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import re
from datetime import datetime, timedelta
import requests
import json

class MemoryRelevanceScore:
    """Tracks when memory should be consulted"""
    
    __slots__ = (
        'needs_short_memory', 'needs_medium_memory', 'needs_long_memory',
        'needs_base_knowledge', 'needs_yesterday', 'query_hint'
    )
    
    def __init__(
        self,
        needs_short_memory: bool = True,
        needs_medium_memory: bool = False,
        needs_long_memory: bool = False,
        needs_base_knowledge: bool = False,
        needs_yesterday: bool = False,
        query_hint: str = ""
    ):
        self.needs_short_memory = needs_short_memory
        self.needs_medium_memory = needs_medium_memory
        self.needs_long_memory = needs_long_memory
        self.needs_base_knowledge = needs_base_knowledge
        self.needs_yesterday = needs_yesterday
        self.query_hint = query_hint
    
    def __repr__(self):
        return (f"MemoryRelevanceScore(needs_short={self.needs_short_memory}, "
                f"needs_medium={self.needs_medium_memory}, "
                f"needs_long={self.needs_long_memory}, "
                f"needs_base={self.needs_base_knowledge}, "
                f"needs_yesterday={self.needs_yesterday})")

class MemoryAwarePromptBuilder:
    """Extended prompt builder with memory awareness"""
    
    __slots__ = (
        'controls', 'memory_search', '_token_budget', '_memory_triggers', 'config'
    )

    def __init__(self, controls_module, memory_search, config=None):
        self.controls = controls_module
        self.memory_search = memory_search
        self.config = config
        self._token_budget = 1500

        self._memory_triggers = {
            'recall': ['remember', 'recall', 'before', 'earlier', 'last time', 'you said', 'we talked'],
            'reference': ['guide', 'how to', 'explain', 'what is', 'tell me about'],
            'yesterday': ['yesterday', 'last night', 'this morning'],
            'history': ['history', 'past', 'previous', 'ago', 'used to'],
        }
    
    # ============================================================================
    # MEMORY RELEVANCE DETECTION
    # ============================================================================
    
    def detect_memory_needs(
        self,
        thoughts: List[str],
        context_parts: List[str],
        urgency_level: int
    ) -> MemoryRelevanceScore:
        """
        Analyze if memory should be consulted
        Returns relevance score indicating which tiers to query
        """
        score = MemoryRelevanceScore()
        
        # High urgency (9-10): Skip memory for speed
        if urgency_level >= 9:
            score.needs_short_memory = True  # Only recent context
            return score
        
        # Combine recent thoughts for analysis
        recent_text = " ".join(thoughts).lower() if thoughts else ""
        
        # Check for memory trigger keywords
        has_recall = any(kw in recent_text for kw in self._memory_triggers['recall'])
        has_reference = any(kw in recent_text for kw in self._memory_triggers['reference'])
        has_yesterday = any(kw in recent_text for kw in self._memory_triggers['yesterday'])
        has_history = any(kw in recent_text for kw in self._memory_triggers['history'])
        
        # Build memory needs
        score.needs_short_memory = True  # Always include recent
        
        if has_yesterday:
            score.needs_yesterday = True
            score.query_hint = recent_text  # Last 100 chars as hint
        
        if has_recall or has_history:
            score.needs_medium_memory = True
            score.needs_long_memory = True
            score.query_hint = recent_text
        
        if has_reference:
            score.needs_base_knowledge = True
            score.query_hint = self._extract_reference_query(recent_text)
        
        # Medium urgency (7-8): Only short + medium
        if urgency_level >= 7:
            score.needs_long_memory = False
            score.needs_base_knowledge = False
        
        return score
    
    def _extract_reference_query(self, text: str) -> str:
        """Extract what the user wants to know about"""
        patterns = [
            r'how to (.+)',
            r'what is (.+)',
            r'explain (.+)',
            r'tell me about (.+)',
            r'guide (?:for|to) (.+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)  # First 50 chars
        
        return text  # Fallback to last 100 chars
    
    # ============================================================================
    # MEMORY CONTEXT BUILDING
    # ============================================================================
    
    def build_memory_context(self, relevance: MemoryRelevanceScore) -> str:
        if not self.memory_search:
            return ""

        # Pull limit from config, falling back to 1 (conservative)
        k = (
            getattr(self.config, 'max_context_entries', None)
            or getattr(self.config, 'embedding_search_results', None)
            or 1
        )

        context_parts = []

        if relevance.needs_short_memory:
            short_mem = self.memory_search.get_short_memory()
            if short_mem:
                context_parts.append("## RECENT CONVERSATION")
                context_parts.append(short_mem)

        if relevance.needs_yesterday:
            yesterday_ctx = self.memory_search.get_yesterday_context()
            if yesterday_ctx:
                yesterday_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                context_parts.append(f"\n## YESTERDAY ({yesterday_date})")
                context_parts.append(yesterday_ctx)

        if relevance.needs_medium_memory and relevance.query_hint:
            medium_results = self.memory_search.search_medium_memory(relevance.query_hint, k=k)
            if medium_results:
                context_parts.append("\n## EARLIER TODAY")
                for r in medium_results:
                    role = self.memory_search.memory_manager.username if r['role'] == 'user' else self.memory_search.memory_manager.agentname
                    context_parts.append(f"[{r['timestamp']}] {role}: {r['content']}")
                    context_parts.append(f"(relevance: {r['similarity']:.2f})")

        if relevance.needs_long_memory and relevance.query_hint:
            long_results = self.memory_search.search_long_memory(relevance.query_hint, k=k)
            if long_results:
                context_parts.append("\n## PAST DAYS")
                for r in long_results:
                    context_parts.append(f"[{r['date']}] {r['summary']}")
                    context_parts.append(f"(relevance: {r['similarity']:.2f})")

        if relevance.needs_base_knowledge and relevance.query_hint:
            base_results = self.memory_search.search_base_knowledge(
                relevance.query_hint, k=k, min_similarity=0.4
            )
            if base_results:
                personality = [r for r in base_results
                            if r.get('metadata', {}).get('type') in
                            ['conversation_example', 'category_summary', 'system_prompt']]
                documents = [r for r in base_results if r not in personality]

                if personality:
                    context_parts.append("\n## PERSONALITY KNOWLEDGE")
                    for r in personality:
                        context_parts.append(r['text'])
                        context_parts.append(f"(relevance: {r['similarity']:.2f})")

                if documents:
                    context_parts.append("\n## REFERENCE GUIDES")
                    for r in documents:
                        source = r.get('metadata', {}).get('source_file', 'unknown')
                        context_parts.append(f"From {source}:")
                        context_parts.append(r['text'])
                        context_parts.append(f"(relevance: {r['similarity']:.2f})")

        return "\n".join(context_parts) if context_parts else ""
    
    # ============================================================================
    # INTEGRATED PROMPT BUILDING
    # ============================================================================
    
    def build_response_prompt_with_memory(
        self,
        thoughts: List[str],
        context_parts: List[str],
        urgency_level: int,
        core_builder  # OptimizedPromptBuilder instance
    ) -> str:
        """
        Build response prompt with intelligent memory integration
        Combines core prompt building with memory awareness
        """
        # Detect if memory is needed
        memory_needs = self.detect_memory_needs(thoughts, context_parts, urgency_level)
        
        # Build memory context (only if needed)
        memory_context = ""
        if any([
            memory_needs.needs_medium_memory,
            memory_needs.needs_long_memory,
            memory_needs.needs_base_knowledge,
            memory_needs.needs_yesterday
        ]):
            memory_context = self.build_memory_context(memory_needs)
        
        # Get core instructions from base builder
        core_instructions = core_builder.build_response_prompt(
            thoughts=thoughts,
            context_parts=context_parts,
            urgency_level=urgency_level
        )
        
        # Combine: Core instructions + Memory context + Other context
        full_prompt_parts = [core_instructions]
        
        if memory_context:
            full_prompt_parts.append("\n## MEMORY CONTEXT")
            full_prompt_parts.append(memory_context)
        
        # Add other context (game, chat, etc.)
        if context_parts:
            full_prompt_parts.append("\n## CURRENT CONTEXT")
            full_prompt_parts.append("\n".join(context_parts))
        
        return "\n".join(full_prompt_parts)


# ============================================================================
# MEMORY-AWARE THINKING PROCESSOR
# ============================================================================

class MemoryAwareThinkingProcessor:
    """Extends IntegratedThinkingProcessor with memory integration"""
    
    __slots__ = (
        'base_processor', 'config', '_call_ollama', '_log', 'controls',
        'memory_prompt_builder', '_event_batch_size'
    )
    
    def __init__(self, config, ollama_caller, logger, controls, memory_search):
        from BASE.core.thought_processor import ThoughtProcessor
        self.base_processor = ThoughtProcessor(
            config=config,
            controls_module=controls,
            project_root=config.project_root if hasattr(config, 'project_root') else None,
            memory_search=memory_search
        )

        self.config = config
        self._call_ollama = ollama_caller
        self._log = logger
        self.controls = controls

        self.memory_prompt_builder = MemoryAwarePromptBuilder(controls, memory_search, config=config)

        self._event_batch_size = 3
    
    # Delegate batch interpretation (no memory needed)
    def batch_interpret_events(self, raw_events, thought_buffer):
        return self.base_processor.batch_interpret_events(raw_events, thought_buffer)
    
    # Delegate action decision (memory happens at response stage)
    def generate_action_decision(self, thought_buffer, context_parts, action_state_manager=None):
        return self.base_processor.generate_action_decision(
            thought_buffer, context_parts, action_state_manager
        )
    
    # MODIFIED: Response synthesis with memory
    def synthesize_response_with_memory(
        self,
        thought_buffer,
        urgency_level: int,
        context_parts: List[str]
    ) -> str:
        """
        Synthesize response WITH memory integration
        Memory is only consulted when relevant (detected from thoughts)
        """
        thoughts = thought_buffer.get_thoughts_for_response()
        if not thoughts:
            return "Hmm..."
        
        # Select thoughts based on urgency
        if urgency_level >= 8:
            relevant_thoughts = thoughts
        else:
            relevant_thoughts = thoughts
        
        thoughts_text = [str(t) for t in relevant_thoughts]  # Ensure strings
        
        # Build memory-aware prompt
        prompt = self.memory_prompt_builder.build_response_prompt_with_memory(
            thoughts=thoughts_text,
            context_parts=context_parts,
            urgency_level=urgency_level,
            core_builder=self.base_processor.prompt_builder
        )
        
        # Add thoughts and user message
        recent_thoughts_text = "\n".join([f"- {t}" for t in thoughts_text])
        
        # Extract last user message
        last_user_msg = ""
        for t in thought_buffer._thoughts:
            if t.source in ['user_input', 'direct_mention'] and t.original_ref:
                last_user_msg = t.original_ref
                break
        
        # Build final prompt
        situation = self.base_processor._get_urgency_situation(urgency_level, thought_buffer)
        
        full_prompt = f"""{prompt}

YOUR THOUGHTS:
{recent_thoughts_text}

{situation}

User said: "{last_user_msg}"

Respond in 1-2 sentences. Natural, conversational.

Response:"""
        
        # Generate response
        model = self.config.text_model
        
        response = self._call_ollama(
            prompt=full_prompt,
            model=model,
            system_prompt=None
        )
        
        # Clean
        import re
        THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)
        response = THINK_PATTERN.sub('', response).strip()
        
        return response if response else "I'm thinking..."
    
    # Delegate goal methods
    def generate_goal(self, thought_buffer, user_input=""):
        return self.base_processor.generate_goal(thought_buffer, user_input)
    
    def check_goal_achievement(self, thought_buffer):
        return self.base_processor.check_goal_achievement(thought_buffer)