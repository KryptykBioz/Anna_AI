# BASE/handlers/internal_tool_interface.py
"""
Internal Tool Interface - Base class for internal tools

Internal tools are different from regular tools:
- Always active when enabled (not called by agent)
- Provide services (TTS, voice input, etc.)
- One tool per service category can be active
"""
from abc import ABC, abstractmethod
from typing import Dict


class InternalToolInterface(ABC):
    """
    Abstract base class for internal tools
    
    Internal tools provide background services like:
    - Text-to-speech (TTS)
    - Voice input (speech recognition)
    - Audio effects
    
    Key differences from regular tools:
    - Not called via {"tool": "name"} syntax
    - Always active when enabled
    - Mutual exclusivity within service categories
    """
    
    @property
    @abstractmethod
    def tool_name(self) -> str:
        """
        Return tool name (matches information.json)
        
        Returns:
            Tool identifier (e.g., 'xtts', 'pyttsx3', 'whisper')
        """
        pass
    
    @property
    @abstractmethod
    def service_type(self) -> str:
        """
        Return service category
        
        Service types enforce mutual exclusivity:
        - 'tts': Only one TTS tool active
        - 'voice_input': Only one voice input tool active
        - 'audio_effects': Can coexist with others
        
        Returns:
            Service category string
        """
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the tool
        
        Called when tool is loaded/enabled.
        Use this to:
        - Load models
        - Connect to services
        - Setup resources
        - Verify availability
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def cleanup(self):
        """
        Cleanup tool resources
        
        Called when tool is unloaded/disabled.
        Use this to:
        - Release models
        - Close connections
        - Free resources
        - Save state
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if tool is ready for use
        
        Returns:
            True if tool can be used, False otherwise
        """
        pass