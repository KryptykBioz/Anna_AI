# Filename: BASE/core/context_detector.py
"""
Shared Context Detection Logic - Cleaned
Eliminates duplication between prompt constructors
All game references removed - games are now tools
"""
from typing import List, Set, Optional


class ContextDetector:
    """Unified context detection for prompt builders"""
    
    __slots__ = ()  # Static utility class, no instance variables
    
    @staticmethod
    def detect_active_contexts(context_parts: List[str], thoughts: List[str] = None) -> Set[str]:
        """Detect active context types from conversation data"""
        active_contexts = set()
        
        all_text = context_parts + (thoughts or [])
        full_context = "\n".join(all_text).lower()
        
        if "search results" in full_context or "## search" in full_context:
            active_contexts.add('search_results')
        
        if "reminder:" in full_context or "due reminder" in full_context:
            active_contexts.add('reminder_due')
        
        if "## memory" in full_context or "past conversations" in full_context:
            active_contexts.add('memory_retrieved')
        
        # Generic tool detection (no hardcoded game names)
        if "## tool" in full_context or "tool result" in full_context:
            active_contexts.add('tool_data')
        
        if any(marker in full_context for marker in [
            "## vision", "[vision", "vision_result", 
            "vision observation", "screen analysis"
        ]):
            active_contexts.add('vision_data')
        
        if "youtube chat" in full_context or "twitch chat" in full_context:
            active_contexts.add('chat_messages')
        
        if "pending actions" in full_context or "async task" in full_context:
            active_contexts.add('pending_action')
        
        return active_contexts
    
    @staticmethod
    def has_vision_data(context_parts: List[str], thoughts: List[str] = None) -> bool:
        """Quick check for vision data presence"""
        all_text = context_parts + (thoughts or [])
        full_context = "\n".join(all_text).lower()
        
        return any(marker in full_context for marker in [
            "vision", "screen", "[vision observation"
        ])