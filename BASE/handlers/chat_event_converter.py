# Filename: BASE/handlers/chat_event_converter.py
"""
Chat Event Converter - Bridges ChatEngagement → ThoughtProcessor
Converts unengaged chat messages into RawDataEvent objects for cognitive processing

Architecture:
    ChatHandler → ChatEngagement (storage)
                        ↓
            ChatEventConverter (conversion)
                        ↓
            ThoughtBuffer.ingest_raw_data() (processing)
"""
import time
from typing import List, Dict, Optional
from BASE.core.logger import Logger


class ChatEventConverter:
    """Converts chat messages from ChatEngagement into processable events"""
    
    __slots__ = (
        'thought_buffer', 'logger', '_last_conversion_time',
        '_conversion_interval', '_converted_message_ids'
    )
    
    def __init__(self, thought_buffer, logger: Optional[Logger] = None):
        self.thought_buffer = thought_buffer
        self.logger = logger
        
        # Track last conversion to avoid duplicates
        self._last_conversion_time = 0.0
        self._conversion_interval = 2.0
        
        # Track which messages have been converted
        self._converted_message_ids = set()
    
    def should_convert_now(self) -> bool:
        """
        Check if it's time to convert chat messages
        
        Returns:
            True if conversion interval has elapsed
        """
        current_time = time.time()
        time_since_last = current_time - self._last_conversion_time
        
        return time_since_last >= self._conversion_interval
    
    def convert_unengaged_chat_to_events(self) -> int:
        """
        Convert unengaged chat messages into raw data events
        
        This is the CRITICAL bridge that makes chat visible to the agent's
        cognitive processing system.
        
        Returns:
            Number of messages converted
        """
        if not self.should_convert_now():
            return 0
        
        # Get unengaged chat messages
        chat_engagement = self.thought_buffer.chat_engagement
        unengaged_messages = chat_engagement.get_unengaged_messages(max_messages=10)
        
        if not unengaged_messages:
            self._last_conversion_time = time.time()
            return 0
        
        converted_count = 0
        
        for msg in unengaged_messages:
            msg_id = msg.get('_index')
            
            # Skip if already converted
            if msg_id in self._converted_message_ids:
                continue
            
            # Extract message data
            platform = msg.get('platform', 'Chat')
            username = msg.get('username', 'Unknown')
            message = msg.get('message', '')
            has_mention = msg.get('has_mention', False)
            
            # Skip empty messages
            if not message or not username:
                continue
            
            # Determine event source and urgency
            if has_mention:
                source = 'chat_direct_mention'
            elif '?' in message:
                source = 'chat_question'
            else:
                source = 'chat_message'
            
            # Format event data
            event_data = f"[{platform}] {username}: {message}"
            
            # Ingest as raw event for thought processing
            self.thought_buffer.ingest_raw_data(source, event_data)
            
            # Track conversion
            self._converted_message_ids.add(msg_id)
            converted_count += 1
            
            if self.logger:
                self.logger.system(
                    f"[Chat→Event] Converted: {username}: {message}..."
                )
        
        # Update last conversion time
        self._last_conversion_time = time.time()
        
        # Cleanup old converted IDs (keep last 100)
        if len(self._converted_message_ids) > 100:
            sorted_ids = sorted(self._converted_message_ids)
            self._converted_message_ids = set(sorted_ids[-100:])
        
        return converted_count
    
    def get_stats(self) -> Dict:
        """Get converter statistics"""
        return {
            'last_conversion_time': self._last_conversion_time,
            'conversion_interval': self._conversion_interval,
            'converted_count': len(self._converted_message_ids),
            'time_since_last': time.time() - self._last_conversion_time
        }


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def integrate_chat_converter_into_cognitive_loop(cognitive_loop_manager, thought_buffer, logger):
    """
    Helper function to integrate chat converter into cognitive loop
    
    Usage in cognitive_loop_manager.py:
        from BASE.handlers.chat_event_converter import integrate_chat_converter_into_cognitive_loop
        
        # In __init__:
        self.chat_converter = integrate_chat_converter_into_cognitive_loop(
            self, thought_buffer, logger
        )
        
        # In _cognitive_loop (before process_thoughts):
        self.chat_converter.convert_unengaged_chat_to_events()
    
    Args:
        cognitive_loop_manager: CognitiveLoopManager instance
        thought_buffer: ThoughtBuffer instance
        logger: Logger instance
        
    Returns:
        ChatEventConverter instance
    """
    converter = ChatEventConverter(thought_buffer, logger)
    
    if logger:
        logger.system("[Chat Converter] Integrated into cognitive loop")
    
    return converter