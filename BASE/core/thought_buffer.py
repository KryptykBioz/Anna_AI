# Filename: BASE/core/thought_buffer.py
import sys
import time
from typing import List, Dict, Optional, Deque, Any
from collections import deque
from datetime import datetime

from BASE.config.bot_info import agentname, username

import re as _re

# ============================================================================
# STRING INTERNING OPTIMIZATION
# ============================================================================

_SOURCES = {
    'user_input', 'chat_message', 'chat_direct_mention', 'chat_question',
    'direct_mention', 'tool_result', 'tool_failed', 'tool_timeout',
    'vision_result', 'search_result', 'memory_result', 'urgent_reminder',
    'response_echo', 'proactive_reflection', 'internal',
    'system_notification', 'chat_engagement', 'group_chat', 'tool_context',
    'system_log',
}
_INTERNED_SOURCES = {s: sys.intern(s) for s in _SOURCES}

_SUPPRESS_PATTERN = _re.compile(
    r'^(?:'
    r'<mode_instructions>|<recent_experience>|<planned_actions>'
    r'|<tool_instructions>|<execution_principles>|<output_format>'
    r'|<action_context>|<additional_context>|<available_tools>'
    r'|<personality>|<speak_decision>|<grounding_rules>'
    r'|\[Action Mode\] AI Response:'
    r'|\[Action Mode\] Calling AI'
    r'|Action \n<mode_instructions>'
    r')',
    _re.IGNORECASE
)

# Sources that represent genuine external input requiring reactive processing
_ACTIONABLE_SOURCES = frozenset({
    'user_input', 'chat_message', 'chat_direct_mention', 'chat_question',
    'direct_mention', 'tool_result', 'tool_failed', 'tool_timeout',
    'vision_result', 'search_result', 'memory_result', 'urgent_reminder',
    'group_chat',
})


# ============================================================================
# FORMATTING UTILITIES
# ============================================================================

def format_timestamp(timestamp: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()
    return dt.strftime("[%H:%M:%S]")

def format_source(source: str) -> str:
    source_map = {
        'user_input':          'USER',
        'chat_message':        'CHAT',
        'chat_direct_mention': 'CHAT',
        'chat_question':       'CHAT',
        'direct_mention':      'USER',
        'tool_result':         'TOOL',
        'tool_failed':         'TOOL',
        'tool_timeout':        'TOOL',
        'vision_result':       'VISION',
        'search_result':       'SEARCH',
        'memory_result':       'MEMORY',
        'urgent_reminder':     'REMINDER',
        'response_echo':       'SELF',
        'proactive_reflection':'THOUGHT',
        'internal':            'THOUGHT',
        'system_notification': 'SYSTEM',
        'chat_engagement':     'SYSTEM',
        'group_chat':          'FAMILY',
        'system_log':          'SYSTEM',
    }
    return f"[{source_map.get(source, source.upper())}]"

def format_thought_with_metadata(content: str, source: str, timestamp: Optional[float] = None) -> str:
    return f"{format_timestamp(timestamp)} {format_source(source)} {content}"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class ProcessedThought:
    __slots__ = ('content', 'source', 'timestamp', 'original_ref', 'included_in_response')

    def __init__(self, content: str, source: str, timestamp: float,
                 original_ref: Optional[str] = None, included_in_response: bool = False):
        self.content = content
        self.source = _INTERNED_SOURCES.get(source, sys.intern(source))
        self.timestamp = timestamp
        self.original_ref = original_ref
        self.included_in_response = included_in_response

    def __repr__(self):
        return (f"ProcessedThought(content={self.content!r}, source={self.source!r}, "
                f"timestamp={self.timestamp})")

    def __eq__(self, other):
        if not isinstance(other, ProcessedThought):
            return NotImplemented
        return (self.content == other.content and
                self.source == other.source and
                self.timestamp == other.timestamp)


class ResponseTriggers:
    __slots__ = ('_should_speak', '_set_time')

    def __init__(self):
        self._should_speak = False
        self._set_time = 0.0

    def trigger(self):
        self._should_speak = True
        self._set_time = time.time()

    def should_respond(self) -> bool:
        return self._should_speak

    def clear(self):
        self._should_speak = False
        self._set_time = 0.0

    def get_stats(self) -> dict:
        return {
            'should_speak': self._should_speak,
            'time_since_trigger': time.time() - self._set_time if self._set_time > 0 else 0
        }


# ============================================================================
# THOUGHT BUFFER
# ============================================================================

class ThoughtBuffer:
    __slots__ = (
        '_thoughts', 'max_thoughts',
        'last_response_time', 'last_thought_generation',
        'current_goal', 'goal_set_time', 'goal_progress_thoughts',
        'goals_achieved', 'has_urgent_reminders', 'urgent_reminder_count',
        '_response_counter', 'last_proactive_thought_time',
        'ongoing_context', 'last_user_input', 'last_user_input_time',
        'min_proactive_interval', 'max_proactive_interval',
        'thought_momentum', 'consecutive_proactive_thoughts',
        'last_cognitive_activity', '_shutdown_requested',
        'chat_engagement', 'response_trigger',
        '_last_processed_idx',
    )

    def __init__(self, max_thoughts=200):
        self._thoughts: Deque[ProcessedThought] = deque(maxlen=max_thoughts)
        self.max_thoughts = max_thoughts

        # High-water mark: index of the last thought seen by a processing cycle.
        # Anything above this index is "new" and will be included in the next
        # cycle's incoming_data. Reset to current length after each cycle.
        self._last_processed_idx = 0

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
    # INGESTION — single entry point for all incoming information
    # ========================================================================

    def ingest_raw_data(self, source: str, data: str):
        """Primary ingestion point. All external data enters here in arrival order."""
        if source == 'user_input':
            self.set_last_user_input(data)
        self._append(data, source)

    def ingest_system_message(self, message: str):
        """Ingest internal system log messages. Suppresses prompt/response dumps."""
        if _SUPPRESS_PATTERN.match(message.lstrip()):
            return
        self._append(message, 'system_notification')

    def _append(self, content: str, source: str, original_ref: str = None,
                timestamp: float = None):
        """Write a thought to the buffer, formatting content with metadata."""
        if timestamp is None:
            timestamp = time.time()

        if source == 'user_input':
            display = f'{username} said: {content}'
        elif source == 'response_echo':
            display = f'I said: {content}'
        else:
            display = content

        formatted = format_thought_with_metadata(display, source, timestamp)
        interned = _INTERNED_SOURCES.get(source, sys.intern(source))

        self._thoughts.append(ProcessedThought(
            content=formatted,
            source=interned,
            timestamp=timestamp,
            original_ref=original_ref,
            included_in_response=False
        ))
        self.last_thought_generation = time.time()

        if source == 'urgent_reminder':
            self.has_urgent_reminders = True
            self.urgent_reminder_count += 1

    # ========================================================================
    # NEW ENTRY DETECTION
    # ========================================================================

    def get_new_thoughts(self) -> List[ProcessedThought]:
        """Return thoughts added since the last processing cycle."""
        thoughts = list(self._thoughts)
        # _last_processed_idx is relative to buffer length at last mark.
        # Since deque may have rotated, work from the tail.
        new_count = max(0, len(thoughts) - self._last_processed_idx)
        return thoughts[-new_count:] if new_count else []

    def has_actionable_new_thoughts(self) -> bool:
        """True if any new thoughts since last cycle are from actionable sources."""
        return any(t.source in _ACTIONABLE_SOURCES for t in self.get_new_thoughts())

    def mark_thoughts_seen(self):
        """Advance the high-water mark after a processing cycle completes."""
        self._last_processed_idx = len(self._thoughts)

    # ========================================================================
    # LEGACY COMPATIBILITY — keeps existing call sites working
    # ========================================================================

    def get_unprocessed_events(self) -> List[ProcessedThought]:
        """Legacy: returns new thoughts as a list. Source field replaces .source on RawDataEvent."""
        return self.get_new_thoughts()

    def mark_events_processed(self, count: int):
        """Legacy: advance high-water mark by count. Use mark_thoughts_seen() for new code."""
        self.mark_thoughts_seen()

    # ========================================================================
    # PROCESSED THOUGHTS (public write path for internal agent thoughts)
    # ========================================================================

    def add_processed_thought(self, content: str, source: str,
                               original_ref: str = None, timestamp: float = None):
        self._append(content, source, original_ref=original_ref, timestamp=timestamp)

    # ========================================================================
    # READ ACCESS
    # ========================================================================

    def get_thoughts_for_response(self) -> List[str]:
        return [t.content for t in self._thoughts]

    def get_thoughts_for_context(self) -> str:
        return "\n".join(t.content for t in self._thoughts)

    def get_recent_context(self, last_n: int = 10) -> List[str]:
        return [t.content for t in list(self._thoughts)[-last_n:]]

    def get_thinking_stats(self) -> Dict[str, Any]:
        return {
            'consecutive_proactive': self.consecutive_proactive_thoughts,
            'momentum': self.thought_momentum,
            'can_think_proactively': True,
            'time_since_last_proactive': time.time() - self.last_proactive_thought_time,
            'time_since_activity': time.time() - self.last_cognitive_activity
        }

    # ========================================================================
    # USER INPUT TRACKING
    # ========================================================================

    def set_last_user_input(self, user_input: str):
        if user_input and user_input.strip():
            self.last_user_input = user_input.strip()
            self.last_user_input_time = time.time()

    def get_last_user_input(self) -> str:
        return self.last_user_input

    def get_time_since_last_user_input(self) -> float:
        if not self.last_user_input:
            return 999999.0
        return time.time() - self.last_user_input_time

    def has_recent_user_input(self, max_age: float = 30.0) -> bool:
        if not self.last_user_input:
            return False
        return (time.time() - self.last_user_input_time) < max_age

    def get_user_context(self) -> str:
        if not self.last_user_input:
            return ""
        if time.time() - self.last_user_input_time > 60.0:
            return ""
        return f"Recent user request: {self.last_user_input}"

    def clear_stale_user_input(self, max_age: float = 20.0):
        if self.last_user_input and time.time() - self.last_user_input_time > max_age:
            self.last_user_input = ""
            self.last_user_input_time = 0.0

    # ========================================================================
    # RESPONSE ECHO
    # ========================================================================

    def add_response_echo(self, response_text: str, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        self._append(response_text, 'response_echo', timestamp=timestamp)
        if self._thoughts:
            self._thoughts[-1].included_in_response = True
        self.last_response_time = timestamp

    # ========================================================================
    # RESPONSE DECISION
    # ========================================================================

    def should_speak(self) -> bool:
        return self.response_trigger.should_respond()

    def mark_thoughts_as_responsive(self):
        for t in self._thoughts:
            t.included_in_response = True
        self.response_trigger.clear()
        self.last_response_time = time.time()

    def mark_thoughts_responsive(self, count: int = None):
        if count is None:
            for t in self._thoughts:
                if not t.included_in_response:
                    t.included_in_response = True
        else:
            not_included = [t for t in self._thoughts if not t.included_in_response]
            for t in not_included[-count:]:
                t.included_in_response = True

    def count_not_included_in_response(self) -> int:
        return sum(1 for t in self._thoughts if not t.included_in_response)

    def should_generate_thoughts(self) -> bool:
        return True  # Always — agent decides what to do with idle time

    def should_generate_proactive_thought(self) -> bool:
        return True

    # ========================================================================
    # PROACTIVE THINKING
    # ========================================================================

    def add_proactive_thought(self, content: str):
        self._append(content, 'proactive_reflection')
        self.last_proactive_thought_time = time.time()
        self.last_cognitive_activity = time.time()
        self.consecutive_proactive_thoughts += 1

        content_lower = content.lower()
        high_quality = ['wonder', 'curious', 'should check', 'could', 'might want',
                        'consider', 'need to', 'want to', 'plan', 'prepare',
                        'notice', 'observe', 'realize', 'think about', 'remember',
                        'recall', 'past', 'future', 'next', 'if', 'when']
        if any(ind in content_lower for ind in high_quality):
            self.thought_momentum = min(1.0, self.thought_momentum + 0.1)
        else:
            self.thought_momentum = max(0.3, self.thought_momentum - 0.05)

    def reset_consecutive_counter(self):
        self.consecutive_proactive_thoughts = 0
        self.thought_momentum = 0.6
        self.last_cognitive_activity = time.time()

    def decay_momentum(self):
        self.thought_momentum = max(0.3, self.thought_momentum - 0.02)
        self.last_cognitive_activity = time.time()

    # ========================================================================
    # ONGOING CONTEXT
    # ========================================================================

    def set_ongoing_context(self, context: str):
        self.ongoing_context = context

    def get_ongoing_context(self) -> str:
        if self.ongoing_context:
            return self.ongoing_context
        if self.current_goal:
            return f"Goal: {self.current_goal['description']}"
        return ""

    # ========================================================================
    # CHAT ENGAGEMENT
    # ========================================================================

    def ingest_chat_message(self, platform: str, username: str, message: str,
                             has_bot_mention: bool = False):
        self.chat_engagement.ingest_chat_message(platform, username, message, has_bot_mention)

    def should_engage_with_chat(self) -> bool:
        return self.chat_engagement.should_engage_with_chat()

    def mark_chat_engaged(self, message_ids: List[int] = None, batch_mode: bool = False):
        self.chat_engagement.mark_chat_engaged(message_ids, batch_mode)

    def get_unengaged_messages(self, max_messages: int = 5) -> List[Dict]:
        return self.chat_engagement.get_unengaged_messages(max_messages)

    def get_chat_engagement_stats(self) -> Dict[str, Any]:
        return self.chat_engagement.get_chat_engagement_stats()

    # ========================================================================
    # GOAL MANAGEMENT
    # ========================================================================

    def set_goal(self, goal_description: str, reason: str = ""):
        self.current_goal = {
            "description": goal_description,
            "reason": reason,
            "set_at": time.time(),
            "progress_count": 0,
        }
        self.goal_set_time = time.time()
        self.goal_progress_thoughts = []

    def add_goal_progress(self, progress_note: str):
        if self.current_goal:
            self.goal_progress_thoughts.append({"note": progress_note, "timestamp": time.time()})
            self.current_goal["progress_count"] += 1

    def achieve_goal(self, achievement_note: str = ""):
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
        if not self.current_goal:
            return ""
        duration = time.time() - self.current_goal["set_at"]
        summary = f"CURRENT GOAL: {self.current_goal['description']}"
        if self.current_goal["reason"]:
            summary += f"\nREASON: {self.current_goal['reason']}"
        summary += f"\nPROGRESS: {self.current_goal['progress_count']} actions ({duration:.0f}s elapsed)"
        if self.goal_progress_thoughts:
            summary += "\nRECENT PROGRESS:\n" + "\n".join(
                f"- {p['note']}" for p in self.goal_progress_thoughts
            )
        return summary

    # ========================================================================
    # URGENT REMINDERS
    # ========================================================================

    def acknowledge_urgent_reminders(self):
        self.has_urgent_reminders = False
        self.urgent_reminder_count = 0

    # ========================================================================
    # UTILITY
    # ========================================================================

    def force_shutdown(self):
        self._shutdown_requested = True

    def is_shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def get_thoughts(self, last_n: int = None) -> List[Dict]:
        thoughts_list = [
            {
                'content': t.content,
                'source': t.source,
                'timestamp': t.timestamp,
                'original_text': t.original_ref or '',
                'included_in_response': t.included_in_response
            }
            for t in self._thoughts
        ]
        return thoughts_list[-last_n:] if last_n else thoughts_list