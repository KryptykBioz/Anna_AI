# ============================================================================
# Filename: BASE/handlers/tts_interface.py
# ============================================================================
"""
Unified TTS Interface - Abstract base class for all TTS backends
Defines the contract that all TTS implementations must follow
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict
import threading


class TTSInterface(ABC):
    """Abstract interface for TTS backends"""
    
    __slots__ = ()  # Abstract base, no instance variables
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
    
    @abstractmethod
    def speak(self, text: str, stream: bool = True, stop_event: Optional[threading.Event] = None) -> str:
        """
        Generate and play speech from text
        
        Args:
            text: Text to convert to speech
            stream: If True, stream audio as it's generated (sentence by sentence)
                   If False, generate complete audio before playing
            stop_event: Optional threading.Event that backend should check to interrupt speech
            
        Returns:
            str: Status message - one of:
                "Speech completed" - successful completion
                "Interrupted" - stopped by stop_event
                "Error: <message>" - error occurred
        """
        pass
    
    @abstractmethod
    def stop(self):
        """
        Stop any currently playing speech immediately
        Should be safe to call even if nothing is playing
        """
        pass
    
    @abstractmethod
    def get_voice_info(self) -> Dict:
        """
        Get information about the current voice configuration
        
        Returns:
            Dict with keys:
                'name': Human-readable name (e.g., "Custom Voice", "System Voice")
                'type': Backend type (e.g., "XTTS", "pyttsx3")
                Additional backend-specific keys as needed
        """
        pass