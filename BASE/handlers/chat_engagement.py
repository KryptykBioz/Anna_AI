# Filename: BASE/handlers/chat_engagement.py
"""
Chat Engagement - SIMPLIFIED
Pure storage and engagement tracking - NO thought creation
Works with ChatEventConverter for event-driven processing

Architecture:
    ChatHandler → ChatEngagement (storage)
                        ↓
            ChatEventConverter (reads messages, creates events)
                        ↓
            ThoughtBuffer.ingest_raw_data()
                        ↓
            ThoughtProcessor interprets chat
"""
import time
from typing import List, Dict, Optional, Deque, Any, Tuple
from collections import deque


class ChatEngagement:
    """
    SIMPLIFIED: Pure storage and engagement tracking
    Does NOT create thoughts - that's ChatEventConverter's job
    """
    __slots__ = ('_chat_messages', '_last_chat_time', '_last_engagement_time')
    
    def __init__(self, thought_buffer_ref=None):
        """
        Initialize chat engagement tracking
        
        Args:
            thought_buffer_ref: UNUSED - kept for backward compatibility
        """
        self._chat_messages: Deque[Dict] = deque(maxlen=20)
        self._last_chat_time = 0.0
        self._last_engagement_time = 0.0
    
    # ========================================================================
    # STORAGE ONLY (No Thought Creation)
    # ========================================================================
    
    def ingest_chat_message(self, platform: str, username: str, message: str, 
                           has_bot_mention: bool = False):
        """
        Store incoming chat message - does NOT create thoughts
        ChatEventConverter will handle event creation
        
        Args:
            platform: Chat platform (e.g., 'Twitch', 'Discord')
            username: Username of message sender
            message: Message content
            has_bot_mention: Whether bot was mentioned
        """
        chat_data = {
            'platform': platform,
            'username': username,
            'message': message,
            'timestamp': time.time(),
            'has_mention': has_bot_mention,
            'engaged': False,
            '_index': len(self._chat_messages)  # Track for marking
        }
        
        self._chat_messages.append(chat_data)
        self._last_chat_time = time.time()
    
    # ========================================================================
    # RETRIEVAL (Used by ChatEventConverter)
    # ========================================================================
    
    def get_unengaged_messages(self, max_messages: int = 10) -> List[Dict]:
        """
        Get list of unengaged chat messages
        Used by ChatEventConverter to create events
        
        Args:
            max_messages: Maximum messages to return
            
        Returns:
            List of unengaged message dicts
        """
        unengaged = [
            msg for msg in self._chat_messages 
            if not msg.get('engaged', False)
        ]
        
        return unengaged[-max_messages:] if unengaged else []
    
    def get_unengaged_chat_count(self) -> int:
        """Get number of unengaged chat messages"""
        return sum(1 for msg in self._chat_messages if not msg.get('engaged', False))
    
    def get_time_since_last_chat(self) -> float:
        """Get seconds since last chat message"""
        if self._last_chat_time == 0.0:
            return 999999.0
        return time.time() - self._last_chat_time
    
    def has_recent_chat_activity(self, max_age: float = 60.0) -> bool:
        """Check if there's recent chat activity"""
        return self.get_time_since_last_chat() < max_age
    
    # ========================================================================
    # ENGAGEMENT TRACKING
    # ========================================================================
    
    def mark_chat_engaged(self, message_ids: Optional[List[int]] = None, 
                         batch_mode: bool = False):
        """
        Mark chat messages as engaged after agent responds
        
        Args:
            message_ids: Indices of messages to mark. If None, marks all.
            batch_mode: If True, uses efficient batch update
        """
        if message_ids is None:
            # Mark all messages as engaged
            for msg in self._chat_messages:
                msg['engaged'] = True
        elif batch_mode:
            # Efficient batch marking
            engaged_set = set(message_ids)
            for msg in self._chat_messages:
                if msg.get('_index') in engaged_set:
                    msg['engaged'] = True
        else:
            # Mark specific messages by their stored index
            for msg_id in message_ids:
                for msg in self._chat_messages:
                    if msg.get('_index') == msg_id:
                        msg['engaged'] = True
                        break
        
        self._last_engagement_time = time.time()
    
    # ========================================================================
    # ENGAGEMENT DECISIONS (Used by ThoughtBuffer.should_speak)
    # ========================================================================
    
    def should_engage_with_chat(self) -> bool:
        """
        Determine if agent should engage with chat
        
        Decision criteria:
        - Direct mentions → immediate engagement
        - Questions → engage within 30s
        - Accumulation → 3+ messages = engage
        
        Returns:
            True if should engage with chat
        """
        unengaged = self.get_unengaged_messages()
        
        if not unengaged:
            return False
        
        # Check for direct mentions (immediate)
        has_mention = any(msg.get('has_mention', False) for msg in unengaged)
        if has_mention:
            return True
        
        # Check for recent questions (within 30s)
        current_time = time.time()
        for msg in unengaged:
            if '?' in msg.get('message', ''):
                age = current_time - msg['timestamp']
                if age < 30.0:
                    return True
        
        # Check for accumulation (3+ messages)
        time_since_engagement = current_time - self._last_engagement_time
        unengaged_count = len(unengaged)
        
        if unengaged_count >= 3 and time_since_engagement > 60.0:
            return True
        
        if unengaged_count >= 5:
            return True
        
        return False
    
    def get_chat_urgency_for_decision(self) -> Tuple[int, str]:
        """
        Get urgency level for response decision
        Used by ThoughtBuffer.should_speak()
        
        Returns:
            (urgency_level, reason) tuple
        """
        unengaged = self.get_unengaged_messages()
        
        if not unengaged:
            return 0, "no_chat"
        
        # Check for mentions
        has_mention = any(msg.get('has_mention', False) for msg in unengaged)
        if has_mention:
            return 9, "chat_mention"
        
        # Check for questions
        has_question = any('?' in msg.get('message', '') for msg in unengaged)
        if has_question:
            return 7, "chat_question"
        
        # Check for accumulation
        if len(unengaged) >= 3:
            return 6, "chat_accumulation"
        
        return 0, "no_urgent_chat"
    
    def get_chat_engagement_stats(self) -> Dict[str, Any]:
        """Get chat engagement statistics for diagnostics"""
        unengaged = self.get_unengaged_messages()
        
        return {
            'total_messages': len(self._chat_messages),
            'unengaged_count': len(unengaged),
            'time_since_last_chat': self.get_time_since_last_chat(),
            'time_since_last_engagement': time.time() - self._last_engagement_time,
            'has_mentions': any(msg.get('has_mention', False) for msg in unengaged),
            'has_questions': any('?' in msg.get('message', '') for msg in unengaged)
        }
    
    def get_recent_chat_summary(self, max_messages: int = 5) -> str:
        """
        Get formatted summary of recent unengaged chat
        Used for logging/debugging
        
        Args:
            max_messages: Maximum messages to include
            
        Returns:
            Formatted chat summary string
        """
        unengaged = self.get_unengaged_messages(max_messages)
        
        if not unengaged:
            return ""
        
        lines = []
        for msg in unengaged:
            platform = msg['platform']
            username = msg['username']
            message = msg['message']
            mention = " [MENTIONED YOU]" if msg.get('has_mention', False) else ""
            lines.append(f"[{platform}] {username}: {message}{mention}")
        
        return "\n".join(lines)