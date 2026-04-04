# gui_message_handler.py - Simplified filtering (already done in gui_chat_view)
"""
GUI Message Handler - Manages message flow between GUI and AI Core
Filtering now happens in gui_chat_view before display
"""

from datetime import datetime
from typing import Optional
import threading


class GUIMessageHandler:
    """
    Handles the complete message flow:
    1. User submits message (filtered in gui_chat_view)
    2. Save to memory immediately
    3. Display in GUI (already filtered)
    4. Process through AI Core
    5. Display bot response
    """

    __slots__ = ('ai_core', 'message_processor', 'message_queue', 'logger', 
                 'username', 'agentname', 'content_filter', 'controls')
    
    def __init__(self, ai_core, message_processor, message_queue, logger):
        """
        Initialize GUI message handler
        
        Args:
            ai_core: AI Core instance (contains centralized content filter)
            message_processor: MessageProcessor instance
            message_queue: Queue for GUI updates
            logger: Logger instance
        """
        self.ai_core = ai_core
        self.message_processor = message_processor
        self.message_queue = message_queue
        self.logger = logger
        self.username = ai_core.config.username
        self.agentname = ai_core.config.agentname
        
        self.content_filter = ai_core.content_filter
        self.controls = ai_core.controls
    
    def handle_user_message(self, message: str, is_auto_prompt: bool = False):
        """
        Handle complete user message flow
        Message is already filtered when it arrives here
        
        Args:
            message: User's message text (already filtered, can be empty for auto-prompts)
            is_auto_prompt: Whether this is from auto-prompt system
        """
        if is_auto_prompt:
            self.logger.system("Processing auto-prompt (background check)")
            self._process_message_async("")
            return
        
        if not message or not message.strip():
            self.logger.warning("Skipping empty user message")
            return
        
        # NOTE: Filtering already done in gui_chat_view.send_message()
        # Message arrives here pre-filtered
        
        # Save user message to memory
        user_entry = self.ai_core.memory_manager.save_user_message(message)
        
        if user_entry:
            self.logger.system(f"User message saved: {message}...")
        else:
            self.logger.warning("Memory saving disabled")
        
        # Process message asynchronously
        self._process_message_async(message)
    
    def _process_message_async(self, message: str):
        """Process message in background thread"""
        t = threading.Thread(
            target=self.message_processor.process_message,
            args=(message,),
            daemon=True,
            name="GUI_Message_Processing"
        )
        t.start()
    
    def _extract_time(self, full_timestamp: str) -> str:
        """Extract time portion from full timestamp"""
        try:
            if " at " in full_timestamp:
                time_part = full_timestamp.split(" at ")[1]
                dt = datetime.strptime(time_part, "%I:%M:%S %p")
                return dt.strftime("%H:%M:%S")
            return full_timestamp
        except Exception as e:
            self.logger.warning(f"Failed to parse timestamp: {e}")
            return full_timestamp
    
    def load_conversation_history(self, messages_to_load: int = 400):
        """Load conversation history from memory and display in GUI"""
        try:
            self.logger.memory("Checking for date rollover and previous day summarization...")
            self.ai_core.memory_manager.check_and_summarize_previous_day()
            
            all_messages = []
            all_messages.extend(self.ai_core.memory_manager.short_memory)
            all_messages.extend(self.ai_core.memory_manager.medium_memory)
            
            from datetime import datetime, timedelta
            current_date = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            recent_messages = [
                msg for msg in all_messages
                if msg.get('date') in [current_date, yesterday]
            ]
            
            recent_messages.sort(key=lambda x: self._parse_sortable_datetime(x))
            recent_messages = recent_messages[-messages_to_load:]
            
            for msg in recent_messages:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                full_timestamp = msg.get('timestamp', '')
                
                display_time = self._extract_time(full_timestamp)
                
                if role == 'user':
                    sender = self.username
                    msg_type = "user"
                elif role == 'assistant':
                    sender = self.agentname
                    msg_type = "agent"
                else:
                    continue
                
                self.message_queue.put((msg_type, sender, content))
            
            self.logger.system(f"Loaded {len(recent_messages)} messages from conversation history")
            
        except Exception as e:
            self.logger.error(f"Failed to load conversation history: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_sortable_datetime(self, msg: dict) -> datetime:
        """Parse message timestamp into sortable datetime"""
        try:
            date_str = msg.get('date', '')
            timestamp_str = msg.get('timestamp', '')
            
            if " at " in timestamp_str:
                dt = datetime.strptime(timestamp_str, "%A, %B %d, %Y at %I:%M:%S %p")
                return dt
            
            if date_str:
                return datetime.strptime(date_str, "%Y-%m-%d")
            
            return datetime.fromtimestamp(0)
            
        except Exception as e:
            self.logger.warning(f"Failed to parse datetime for sorting: {e}")
            return datetime.fromtimestamp(0)