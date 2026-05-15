# BASE/tools/internal/pyttsx3/tool.py
"""
pyttsx3 Internal Tool - System Voice Synthesis
"""
from typing import Dict
import threading

from BASE.handlers.internal_tool_interface import InternalToolInterface


class Pyttsx3Tool(InternalToolInterface):
    """
    System voice TTS using pyttsx3
    
    Fast, lightweight alternative to neural TTS:
    - Uses OS speech engine (SAPI5 on Windows, NSSpeechSynthesizer on macOS)
    - No GPU required
    - No voice sample needed
    - Low latency
    """
    
    __slots__ = (
        '_config', '_controls', '_logger', '_is_available',
        '_is_speaking', '_speech_lock', '_stop_event',
        'hub_client'
    )
    
    @property
    def tool_name(self) -> str:
        return "pyttsx3"
    
    @property
    def service_type(self) -> str:
        return "tts"
    
    def __init__(self, config, controls, logger=None):
        self._config = config
        self._controls = controls
        self._logger = logger
        
        self._is_available = False
        
        self._is_speaking = False
        self._speech_lock = threading.Lock()
        self._stop_event = threading.Event()
        
        self.hub_client = None
    
    async def initialize(self) -> bool:
        """Initialize pyttsx3 engine"""
        if self._logger:
            self._logger.system("[pyttsx3] Initializing system voice...")
        
        try:
            import pyttsx3
            
            test_engine = pyttsx3.init()
            voices = test_engine.getProperty('voices')
            
            if self._logger:
                self._logger.system(f"[pyttsx3] Found {len(voices)} system voices")
                if voices:
                    self._logger.system(f"[pyttsx3] Default: {voices[0].name}")
            
            del test_engine
            
            self._is_available = True
            
            if self._logger:
                self._logger.success("[pyttsx3] System voice ready")
            
            return True
        
        except Exception as e:
            if self._logger:
                self._logger.error(f"[pyttsx3] Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def cleanup(self):
        """Cleanup pyttsx3 resources"""
        self.stop()
        
        if self._logger:
            self._logger.system("[pyttsx3] Cleaned up")
    
    def is_available(self) -> bool:
        """Check if pyttsx3 is ready"""
        return self._is_available
    
    def speak(self, text: str, stream: bool = True) -> str:
        """Speak using system voice"""
        if not self.is_available():
            return "Error: pyttsx3 not available"
        
        with self._speech_lock:
            if self._is_speaking:
                self._stop_event.set()
                import time
                time.sleep(0.1)
            
            self._is_speaking = True
            self._stop_event.clear()
        
        try:
            import BASE.config.controls as controls
            volume = controls.VOICE_VOLUME
            
            if self.hub_client and self.hub_client.is_connected():
                return self._speak_via_hub(text, volume)
            
            return self._speak_local(text, volume)
        
        finally:
            with self._speech_lock:
                self._is_speaking = False
                self._stop_event.clear()
    
    def stop(self):
        """Stop playback"""
        with self._speech_lock:
            if self._is_speaking:
                self._stop_event.set()
                try:
                    import sounddevice as sd
                    sd.stop()
                except:
                    pass
                self._is_speaking = False
    
    def get_voice_info(self) -> Dict:
        """Get voice configuration"""
        info = {
            'name': 'System Voice',
            'type': 'pyttsx3',
            'tool_name': self.tool_name,
            'service_type': self.service_type
        }
        
        if self.hub_client and self.hub_client.is_connected():
            info['mode'] = 'hub'
            info['status'] = 'connected_to_hub'
        elif self.is_available():
            info['mode'] = 'local'
            info['status'] = 'available'
            
            try:
                import pyttsx3
                temp_engine = pyttsx3.init()
                voices = temp_engine.getProperty('voices')
                current = temp_engine.getProperty('voice')
                del temp_engine
                
                import BASE.config.controls as controls
                volume = controls.VOICE_VOLUME
                
                info['current_voice'] = current
                info['available_voices'] = len(voices)
                info['volume'] = volume
                info['volume_percent'] = f"{int(volume * 100)}%"
            except:
                pass
        else:
            info['mode'] = 'local'
            info['status'] = 'unavailable'
        
        return info
    
    def _speak_via_hub(self, text: str, volume: float) -> str:
        """Speak via Voice Hub"""
        if self._logger:
            self._logger.system(f"[pyttsx3 Hub] Requesting speech via Voice Hub...")
        
        from BASE.config.bot_info import voiceIndex
        
        result = self.hub_client.request_speech(
            text=text,
            voice_config={
                'type': 'pyttsx3',
                'voice_index': voiceIndex,
                'rate': 200
            },
            volume=volume,
            blocking=False
        )
        
        if result['status'] == 'accepted':
            return "Speech completed"
        else:
            error = result.get('error', 'Unknown error')
            if self._logger:
                self._logger.warning(f"[pyttsx3 Hub] Hub request failed: {error}")
            return self._speak_local(text, volume)
    
    def _speak_local(self, text: str, volume: float) -> str:
        """Speak using local pyttsx3"""
        from BASE.tools.internal.pyttsx3.pyttsx3_engine import speak_system_voice
        import pyttsx3
        
        if self._logger:
            volume_pct = int(volume * 100)
            self._logger.system(f"[pyttsx3 Local] Speaking (volume: {volume_pct}%)")
        
        try:
            engine = pyttsx3.init()
            
            result = speak_system_voice(
                text=text,
                engine=engine,
                stop_event=self._stop_event,
                volume=volume
            )
            
            del engine
            
            return result
        
        except Exception as e:
            if self._logger:
                self._logger.error(f"[pyttsx3] Error: {e}")
            return f"Error: {e}"
    
    def set_hub_client(self, hub_client):
        """Inject Voice Hub client"""
        self.hub_client = hub_client