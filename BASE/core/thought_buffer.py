# Filename: BASE/core/thought_buffer.py
"""
THOUGHT BUFFER - Core Cognitive State Management
==================================================
OPTIMIZED: String interning for memory efficiency and faster comparisons
"""
import sys
import time
from typing import List, Dict, Optional, Deque, Any 
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from personality.bot_info import agentname, username


# ============================================================================
# STRING INTERNING OPTIMIZATION
# ============================================================================

_SOURCES = {
    'user_input', 'chat_message', 'chat_direct_mention', 'chat_question',
    'direct_mention', 'tool_result', 'tool_failed', 'tool_timeout',
    'vision_result', 'search_result', 'memory_result', 'urgent_reminder',
    'response_echo', 'proactive_reflection', 'internal',
    'system_notification', 'chat_engagement', 'group_chat', 'tool_context'
}
_INTERNED_SOURCES = {s: sys.intern(s) for s in _SOURCES}


# ============================================================================
# FORMATTING UTILITIES
# ============================================================================

def format_timestamp(timestamp: Optional[float] = None) -> str:
    """Format timestamp for display."""
    if timestamp:
        dt = datetime.fromtimestamp(timestamp)
    else:
        dt = datetime.now()
    return dt.strftime("[%H:%M:%S]")

def format_source(source: str) -> str:
    """Format source tag for display."""
    source_map = {
        'user_input': 'USER',
        'chat_message': 'CHAT',
        'chat_direct_mention': 'CHAT',
        'chat_question': 'CHAT',
        'direct_mention': 'USER',
        'tool_result': 'TOOL',
        'tool_failed': 'TOOL',
        'tool_timeout': 'TOOL',
        'vision_result': 'VISION',
        'search_result': 'SEARCH',
        'memory_result': 'MEMORY',
        'urgent_reminder': 'REMINDER',
        'response_echo': 'SELF',
        'proactive_reflection': 'THOUGHT',
        'internal': 'THOUGHT',
        'system_notification': 'SYSTEM',
        'chat_engagement': 'SYSTEM',
        'group_chat': 'FAMILY'
    }
    formatted = source_map.get(source, source.upper())
    return f"[{formatted}]"

def format_thought_with_metadata(content: str, source: str, timestamp: Optional[float] = None) -> str:
    """
    Format thought with metadata prefix.
    Format: [TIMESTAMP] [SOURCE] content
    Example: [19:24:04] [USER] Hello, Anna.
    """
    time_str = format_timestamp(timestamp)
    source_str = format_source(source)
    return f"{time_str} {source_str} {content}"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class RawDataEvent:
    """Unprocessed incoming data awaiting interpretation."""
    __slots__ = ('source', 'data', 'timestamp', 'processed')
    
    def __init__(self, source: str, data: str, timestamp: float = None, processed: bool = False):
        self.source = sys.intern(source) if source not in _INTERNED_SOURCES else _INTERNED_SOURCES[source]
        self.data = data
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.processed = processed
    
    def __repr__(self):
        return f"RawDataEvent(source={self.source!r}, data={self.data!r}, timestamp={self.timestamp}, processed={self.processed})"
    
    def __eq__(self, other):
        if not isinstance(other, RawDataEvent):
            return NotImplemented
        return (self.source == other.source and 
                self.data == other.data and 
                self.timestamp == other.timestamp and 
                self.processed == other.processed)


@dataclass
class ProcessedThought:
    """Interpreted thought with metadata."""
    __slots__ = ('content', 'source', 'timestamp', 'original_ref', 'included_in_response')
    
    def __init__(self, content: str, source: str, timestamp: float, 
                 original_ref: Optional[str] = None, included_in_response: bool = False):
        self.content = content
        self.source = sys.intern(source) if source not in _INTERNED_SOURCES else _INTERNED_SOURCES[source]
        self.timestamp = timestamp
        self.original_ref = original_ref
        self.included_in_response = included_in_response
    
    def __repr__(self):
        return (f"ProcessedThought(content={self.content!r}, source={self.source!r}, "
                f"timestamp={self.timestamp}, original_ref={self.original_ref!r}, "
                f"included_in_response={self.included_in_response})")
    
    def __eq__(self, other):
        if not isinstance(other, ProcessedThought):
            return NotImplemented
        return (self.content == other.content and 
                self.source == other.source and 
                self.timestamp == other.timestamp and 
                self.original_ref == other.original_ref and 
                self.included_in_response == other.included_in_response)


class ResponseTriggers:
    """
    SIMPLIFIED: Just a boolean flag
    Agent said <speak>YES</speak> = True
    Agent said <speak>NO</speak> = False
    """
    __slots__ = ('_should_speak', '_set_time')
    
    def __init__(self):
        self._should_speak = False
        self._set_time = 0.0
    
    def trigger(self):
        """Agent said <speak>YES</speak> - no parameters needed"""
        self._should_speak = True
        self._set_time = time.time()
    
    def should_respond(self) -> bool:
        """Check if agent wants to speak - returns simple boolean"""
        return self._should_speak
    
    def clear(self):
        """Clear flag after response generated"""
        self._should_speak = False
        self._set_time = 0.0
    
    def get_stats(self) -> dict:
        """Get statistics for debugging"""
        return {
            'should_speak': self._should_speak,
            'time_since_trigger': time.time() - self._set_time if self._set_time > 0 else 0
        }


# ============================================================================
# THOUGHT BUFFER
# ============================================================================

class ThoughtBuffer:
    """
    Central cognitive state manager.
    OPTIMIZED: String interning for reduced memory and faster comparisons.
    """
    
    __slots__ = (
        '_raw_events', '_thoughts', 'max_thoughts',
        'last_response_time', 'last_thought_generation', 
        'current_goal', 'goal_set_time', 'goal_progress_thoughts', 
        'goals_achieved', 'has_urgent_reminders', 'urgent_reminder_count',
        '_response_counter', 'last_proactive_thought_time', 
        'ongoing_context', 'last_user_input', 'last_user_input_time',
        'min_proactive_interval', 'max_proactive_interval',
        'thought_momentum', 'consecutive_proactive_thoughts',
        'last_cognitive_activity', '_shutdown_requested', 
        'chat_engagement', 'response_trigger'
    )
    
    def __init__(self, max_thoughts=25):
        self._raw_events: Deque[RawDataEvent] = deque(maxlen=50)
        self._thoughts: Deque[ProcessedThought] = deque(maxlen=max_thoughts)
        
        self.max_thoughts = max_thoughts
        
        self.last_response_time = 0.0
        self.last_thought_generation = 0.0
        self.last_proactive_thought_time = 0.0
        self.last_cognitive_activity = time.time()
        self._response_counter = 0
        
        self.last_user_input = ""
        self.last_user_input_time = 0.0
        
        self.ongoing_context = ""
        
        self.current_goal = None
        self.goal_set_time = None
        self.goal_progress_thoughts = []
        self.goals_achieved = []
        
        self.has_urgent_reminders = False
        self.urgent_reminder_count = 0
        
        self.min_proactive_interval = 5.0
        self.max_proactive_interval = 15.0
        self.thought_momentum = 0.5
        self.consecutive_proactive_thoughts = 0
        
        self._shutdown_requested = False
        
        from BASE.handlers.chat_engagement import ChatEngagement
        self.chat_engagement = ChatEngagement(thought_buffer_ref=self)

        self.response_trigger = ResponseTriggers()

    # ========================================================================
    # RAW DATA INGESTION
    # ========================================================================

    def ingest_raw_data(self, source: str, data: str):
        """Add raw event to processing queue."""
        if source == 'user_input':
            self.set_last_user_input(data)
        
        self._raw_events.append(RawDataEvent(source, data))

    def get_unprocessed_events(self) -> List[RawDataEvent]:
        """Get events awaiting interpretation."""
        return [e for e in self._raw_events if not e.processed]
    
    def mark_events_processed(self, count: int):
        """Mark N oldest events as processed."""
        for event in self._raw_events:
            if not event.processed and count > 0:
                event.processed = True
                count -= 1
    
    def clear_old_events(self, max_age: float = 30.0):
        """Remove old processed events."""
        cutoff = time.time() - max_age
        kept = [e for e in self._raw_events 
                if e.timestamp > cutoff or not e.processed]
        self._raw_events.clear()
        self._raw_events.extend(kept)
    
    # ========================================================================
    # PROCESSED THOUGHTS
    # ========================================================================
    
    def add_processed_thought(
        self, 
        content: str, 
        source: str, 
        original_ref: str = None,
        timestamp: Optional[float] = None
    ):
        """Add interpreted thought with metadata."""
        if source == 'urgent_reminder':
            self.has_urgent_reminders = True
            self.urgent_reminder_count += 1
        
        if timestamp is None:
            timestamp = time.time()
        
        if source == 'user_input':
            content = f'{username} said: {content}'
        elif source == 'response_echo':
            content = f'I said: {content}'
        
        interned_source = _INTERNED_SOURCES.get(source, sys.intern(source))
        
        formatted_content = format_thought_with_metadata(
            content=content,
            source=interned_source,
            timestamp=timestamp
        )
        
        self._thoughts.append(ProcessedThought(
            content=formatted_content,
            source=interned_source,
            timestamp=timestamp,
            original_ref=original_ref,
            included_in_response=False
        ))
        
        self.last_thought_generation = time.time()

    # ========================================================================
    # CONTEXT FORMATTING
    # ========================================================================

    def _format_thought(self, thought: ProcessedThought) -> str:
        """Format single thought for context display."""
        return thought.content

    def get_thoughts_for_context(self) -> str:
        """Get formatted thought history for prompt context."""
        formatted_thoughts = [
            self._format_thought(thought)
            for thought in self._thoughts
        ]
        return "\n".join(formatted_thoughts)
    
    def get_thoughts_for_response(self) -> List[str]:
        """Get thought contents for response generation."""
        return [t.content for t in self._thoughts]
    
    def get_recent_context(self, last_n: int = 10) -> List[str]:
        """Get recent thought contents for context."""
        recent = list(self._thoughts)[-last_n:]
        return [t.content for t in recent]
    
    # ========================================================================
    # USER INPUT TRACKING
    # ========================================================================
    
    def set_last_user_input(self, user_input: str):
        """Track most recent user input for context."""
        if user_input and user_input.strip():
            self.last_user_input = user_input.strip()
            self.last_user_input_time = time.time()
    
    def get_last_user_input(self) -> str:
        """Get most recent user input."""
        return self.last_user_input
    
    def get_time_since_last_user_input(self) -> float:
        """Get seconds since last user input."""
        if not self.last_user_input:
            return 999999.0
        return time.time() - self.last_user_input_time
    
    def has_recent_user_input(self, max_age: float = 30.0) -> bool:
        """Check if user input is recent enough to be relevant."""
        if not self.last_user_input:
            return False
        return (time.time() - self.last_user_input_time) < max_age
    
    def get_user_context(self) -> str:
        """Get formatted user context for prompts (returns empty if stale)."""
        if not self.last_user_input:
            return ""
        
        age = time.time() - self.last_user_input_time
        if age > 60.0:
            return ""
        
        return f"Recent user request: {self.last_user_input}"
    
    def clear_stale_user_input(self, max_age: float = 20.0):
        """Clear user input if too old."""
        if not self.last_user_input:
            return
        
        age = time.time() - self.last_user_input_time
        if age > max_age:
            self.last_user_input = ""
            self.last_user_input_time = 0.0
    
    # ========================================================================
    # RESPONSE ECHO
    # ========================================================================

    def add_response_echo(self, response_text: str, timestamp: Optional[float] = None):
        """Add agent's spoken response as thought echo with [SELF] prefix"""
        if timestamp is None:
            timestamp = time.time()
        
        self.add_processed_thought(
            content=response_text,
            source='response_echo',
            original_ref=None,
            timestamp=timestamp
        )
        
        if self._thoughts:
            self._thoughts[-1].included_in_response = True
        
        self.last_response_time = timestamp
    
    # ========================================================================
    # RESPONSE DECISION LOGIC - SIMPLIFIED
    # ========================================================================
    
    def should_speak(self) -> bool:
        """
        SIMPLIFIED: Just check the flag
        Returns: boolean only - no reason needed
        """
        return self.response_trigger.should_respond()
    
    def mark_thoughts_as_responsive(self):
        """Mark thoughts as included in spoken response and clear trigger."""
        for thought in self._thoughts:
            thought.included_in_response = True
        
        self.response_trigger.clear()
        self.last_response_time = time.time()
    
    def mark_thoughts_responsive(self, count: Optional[int] = None):
        """Mark thoughts as included in response (legacy compatibility)."""
        if count is None:
            for thought in self._thoughts:
                if not thought.included_in_response:
                    thought.included_in_response = True
        else:
            not_included = [t for t in self._thoughts if not t.included_in_response]
            for thought in not_included[-count:]:
                thought.included_in_response = True
    
    def count_not_included_in_response(self) -> int:
        """Count thoughts not yet included in spoken response."""
        return sum(1 for t in self._thoughts if not t.included_in_response)
    
    def should_generate_thoughts(self) -> bool:
        """Check if cognitive processing should occur."""
        if len(self.get_unprocessed_events()) > 0:
            return True
        
        if self.should_generate_proactive_thought():
            return True
        
        return False
    
    # ========================================================================
    # PROACTIVE THINKING CONTROL
    # ========================================================================
    
    def should_generate_proactive_thought(self) -> bool:
        """Determine if agent should generate proactive thought."""
        if len(self.get_unprocessed_events()) > 0:
            return False
        return True
    
    def add_proactive_thought(self, content: str):
        """Add proactive thought with quality tracking."""
        self.add_processed_thought(
            content=content,
            source='proactive_reflection',
            original_ref=None
        )
        self.last_proactive_thought_time = time.time()
        self.last_cognitive_activity = time.time()
        self.consecutive_proactive_thoughts += 1
        
        content_lower = content.lower()
        high_quality_indicators = [
            'wonder', 'curious', 'should check', 'could', 'might want',
            'consider', 'need to', 'want to', 'plan', 'prepare',
            'notice', 'observe', 'realize', 'think about', 'remember',
            'recall', 'past', 'future', 'next', 'if', 'when'
        ]
        
        is_high_quality = sum(1 for ind in high_quality_indicators if ind in content_lower)
        
        if is_high_quality > 0:
            self.thought_momentum = min(1.0, self.thought_momentum + 0.1)
        else:
            self.thought_momentum = max(0.3, self.thought_momentum - 0.05)
    
    def reset_consecutive_counter(self):
        """Reset proactive counter when external input received."""
        self.consecutive_proactive_thoughts = 0
        self.thought_momentum = 0.6
        self.last_cognitive_activity = time.time()
    
    def get_thinking_stats(self) -> Dict[str, Any]:
        """Get current thinking state for diagnostics."""
        return {
            'consecutive_proactive': self.consecutive_proactive_thoughts,
            'momentum': self.thought_momentum,
            'can_think_proactively': self.should_generate_proactive_thought(),
            'time_since_last_proactive': time.time() - self.last_proactive_thought_time,
            'time_since_activity': time.time() - self.last_cognitive_activity
        }
    
    def decay_momentum(self):
        """Decay thought momentum when no processing occurs."""
        self.thought_momentum = max(0.3, self.thought_momentum - 0.02)
        self.last_cognitive_activity = time.time()
    
    # ========================================================================
    # ONGOING CONTEXT MANAGEMENT
    # ========================================================================
    
    def set_ongoing_context(self, context: str):
        """Set current focus area for the agent."""
        self.ongoing_context = context

    def get_ongoing_context(self) -> str:
        """Get current focus area."""
        if self.ongoing_context:
            return self.ongoing_context
        
        if self.current_goal:
            return f"Goal: {self.current_goal['description']}"
        
        return ""
    
    # ========================================================================
    # CHAT ENGAGEMENT DELEGATION
    # ========================================================================
    
    def ingest_chat_message(
        self, 
        platform: str, 
        username: str, 
        message: str,
        has_bot_mention: bool = False
    ):
        """Delegate to chat engagement module."""
        self.chat_engagement.ingest_chat_message(
            platform, username, message, has_bot_mention
        )
    
    def should_engage_with_chat(self) -> bool:
        """Delegate to chat engagement module."""
        return self.chat_engagement.should_engage_with_chat()
    
    def mark_chat_engaged(
        self, 
        message_ids: Optional[List[int]] = None,
        batch_mode: bool = False
    ):
        """Delegate to chat engagement module."""
        self.chat_engagement.mark_chat_engaged(message_ids, batch_mode)
    
    def get_unengaged_messages(self, max_messages: int = 5) -> List[Dict]:
        """Delegate to chat engagement module."""
        return self.chat_engagement.get_unengaged_messages(max_messages)
    
    def get_chat_engagement_stats(self) -> Dict[str, Any]:
        """Delegate to chat engagement module."""
        return self.chat_engagement.get_chat_engagement_stats()
    
    # ========================================================================
    # GOAL MANAGEMENT
    # ========================================================================
    
    def set_goal(self, goal_description: str, reason: str = ""):
        """Set new goal for agent."""
        self.current_goal = {
            "description": goal_description,
            "reason": reason,
            "set_at": time.time(),
            "progress_count": 0,
        }
        self.goal_set_time = time.time()
        self.goal_progress_thoughts = []
    
    def add_goal_progress(self, progress_note: str):
        """Track progress toward current goal."""
        if self.current_goal:
            self.goal_progress_thoughts.append({
                "note": progress_note, 
                "timestamp": time.time()
            })
            self.current_goal["progress_count"] += 1
    
    def achieve_goal(self, achievement_note: str = ""):
        """Mark current goal as achieved."""
        if self.current_goal:
            self.goals_achieved.append({
                "goal": self.current_goal["description"],
                "reason": self.current_goal["reason"],
                "achieved_at": time.time(),
                "duration": time.time() - self.current_goal["set_at"],
                "progress_count": self.current_goal["progress_count"],
                "achievement_note": achievement_note,
            })
            self.current_goal = None
            self.goal_set_time = None
            self.goal_progress_thoughts = []
    
    def get_goal_summary(self) -> str:
        """Get formatted goal summary for prompts."""
        if not self.current_goal:
            return ""
        
        duration = time.time() - self.current_goal["set_at"]
        progress = self.current_goal["progress_count"]
        
        summary = f"CURRENT GOAL: {self.current_goal['description']}"
        if self.current_goal["reason"]:
            summary += f"\nREASON: {self.current_goal['reason']}"
        summary += f"\nPROGRESS: {progress} actions ({duration:.0f}s elapsed)"
        
        if self.goal_progress_thoughts:
            recent = self.goal_progress_thoughts
            summary += "\nRECENT PROGRESS:\n" + "\n".join(
                [f"- {p['note']}" for p in recent]
            )
        
        return summary
    
    # ========================================================================
    # URGENT REMINDERS
    # ========================================================================
    
    def acknowledge_urgent_reminders(self):
        """Clear urgent reminder flags after acknowledgment."""
        self.has_urgent_reminders = False
        self.urgent_reminder_count = 0
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def force_shutdown(self):
        """Request immediate shutdown."""
        self._shutdown_requested = True
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown was requested."""
        return self._shutdown_requested
    
    def get_thoughts(self, last_n: Optional[int] = None) -> List[Dict]:
        """Get thoughts as dictionaries with metadata."""
        thoughts_list = []
        for t in self._thoughts:
            thoughts_list.append({
                'content': t.content,
                'source': t.source,
                'timestamp': t.timestamp,
                'original_text': t.original_ref or '',
                'included_in_response': t.included_in_response
            })
        
        if last_n is not None:
            return thoughts_list[-last_n:]
        return thoughts_list