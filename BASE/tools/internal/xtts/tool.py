# BASE/tools/internal/xtts/tool.py
"""
XTTS Internal Tool - Neural Voice Cloning
Self-contained XTTS implementation as internal tool
"""
from typing import Optional, Dict, Iterator
from pathlib import Path
import threading

from BASE.handlers.internal_tool_interface import InternalToolInterface


class XTTSTool(InternalToolInterface):
    """
    XTTS neural voice cloning tool
    
    Complete self-contained implementation:
    - GPU-accelerated voice synthesis
    - Voice cloning from sample
    - Dual caching (embeddings + audio)
    - Streaming support
    - Voice Hub integration
    """
    
    __slots__ = (
        '_config', '_controls', '_logger', '_voice_sample_path',
        '_language', '_speed', '_is_available', '_init_error',
        '_xtts_engine', '_is_speaking', '_speech_lock', '_stop_event',
        'hub_client', 'streaming_handler'
    )
    
    @property
    def tool_name(self) -> str:
        return "xtts"
    
    @property
    def service_type(self) -> str:
        return "tts"
    
    def __init__(self, config, controls, logger=None):
        self._config = config
        self._controls = controls
        self._logger = logger
        
        from personality.bot_info import agentname
        self._voice_sample_path = Path(f"./personality/voice/{agentname}_voice_sample.wav")
        self._language = 'en'
        self._speed = 1.0
        
        self._is_available = False
        self._init_error = None
        self._xtts_engine = None
        
        self._is_speaking = False
        self._speech_lock = threading.Lock()
        self._stop_event = threading.Event()
        
        self.hub_client = None
        self.streaming_handler = None
    
    async def initialize(self) -> bool:
        """Initialize XTTS engine"""
        if self._logger:
            self._logger.system("[XTTS] Initializing neural voice cloning...")
        
        if not self._voice_sample_path.exists():
            self._init_error = f"Voice sample not found: {self._voice_sample_path}"
            if self._logger:
                self._logger.error(f"[XTTS] {self._init_error}")
            return False
        
        try:
            import soundfile as sf
            data, sr = sf.read(str(self._voice_sample_path))
            duration = len(data) / sr
            
            if self._logger:
                self._logger.system(f"[XTTS] Voice sample: {duration:.1f}s @ {sr}Hz")
        
        except Exception as e:
            self._init_error = f"Invalid voice sample: {e}"
            if self._logger:
                self._logger.error(f"[XTTS] {self._init_error}")
            return False
        
        try:
            from BASE.tools.internal.xtts.xtts_engine import XTTSEngine
            
            self._xtts_engine = XTTSEngine(
                voice_sample_path=str(self._voice_sample_path),
                language=self._language,
                speed=self._speed,
                logger=self._logger,
                hub_client=self.hub_client
            )
            
            success = await self._xtts_engine.initialize()
            
            if success:
                self._is_available = True
                
                if self._logger:
                    device = self._xtts_engine.get_device()
                    cache_stats = self._xtts_engine.get_cache_stats()
                    self._logger.success(
                        f"[XTTS] Ready on {device.upper()} "
                        f"({cache_stats['embeddings_cached']} embeddings cached)"
                    )
                
                return True
            else:
                self._init_error = "Engine initialization failed"
                if self._logger:
                    self._logger.error(f"[XTTS] {self._init_error}")
                return False
        
        except Exception as e:
            self._init_error = f"Initialization error: {e}"
            if self._logger:
                self._logger.error(f"[XTTS] {self._init_error}")
            import traceback
            traceback.print_exc()
            return False
    
    async def cleanup(self):
        """Cleanup XTTS resources"""
        self.stop()
        
        if self._xtts_engine:
            await self._xtts_engine.cleanup()
        
        if self._logger:
            self._logger.system("[XTTS] Cleaned up")
    
    def is_available(self) -> bool:
        """Check if XTTS is ready"""
        return self._is_available and self._xtts_engine is not None
    
    def speak(self, text: str, stream: bool = True) -> str:
        """Speak text using XTTS"""
        if not self.is_available():
            return f"Error: XTTS not available - {self._init_error}"
        
        with self._speech_lock:
            if self._is_speaking:
                self._stop_event.set()
                import time
                time.sleep(0.1)
            
            self._is_speaking = True
            self._stop_event.clear()
        
        try:
            import personality.controls as controls
            volume = controls.VOICE_VOLUME
            
            if self.hub_client and self.hub_client.is_connected():
                return self._speak_via_hub(text, volume, stream)
            
            return self._speak_local(text, volume, stream)
        
        finally:
            with self._speech_lock:
                self._is_speaking = False
                self._stop_event.clear()
    
    def speak_streaming_chunks(self, text_chunks: Iterator[str]) -> str:
        """Speak text chunks as they arrive"""
        if not self.is_available():
            return f"Error: XTTS not available"
        
        with self._speech_lock:
            if self._is_speaking:
                self._stop_event.set()
                import time
                time.sleep(0.1)
            
            self._is_speaking = True
            self._stop_event.clear()
        
        try:
            import personality.controls as controls
            volume = controls.VOICE_VOLUME
            
            return self._xtts_engine.speak_streaming_chunks(
                text_chunks=text_chunks,
                stop_event=self._stop_event,
                volume=volume
            )
        
        finally:
            with self._speech_lock:
                self._is_speaking = False
                self._stop_event.clear()
    
    def stop(self):
        """Stop current speech"""
        with self._speech_lock:
            if self._is_speaking:
                self._stop_event.set()
                if self._xtts_engine:
                    self._xtts_engine.stop()
                self._is_speaking = False
    
    def get_voice_info(self) -> Dict:
        """Get voice configuration"""
        info = {
            'name': 'Custom Voice (XTTS)',
            'type': 'xtts',
            'tool_name': self.tool_name,
            'service_type': self.service_type,
            'sample': str(self._voice_sample_path),
            'language': self._language,
            'speed': self._speed
        }
        
        if self.hub_client and self.hub_client.is_connected():
            info['mode'] = 'hub'
            info['status'] = 'connected_to_hub'
        elif self.is_available():
            info['mode'] = 'local'
            info['status'] = 'available'
            
            if self._xtts_engine:
                info['device'] = self._xtts_engine.get_device()
                cache_stats = self._xtts_engine.get_cache_stats()
                info.update(cache_stats)
            
            import personality.controls as controls
            info['volume'] = controls.VOICE_VOLUME
            info['volume_percent'] = f"{int(controls.VOICE_VOLUME * 100)}%"
        else:
            info['mode'] = 'local'
            info['status'] = 'unavailable'
            info['error'] = self._init_error
        
        return info
    
    def _speak_via_hub(self, text: str, volume: float, stream: bool) -> str:
        """Speak via Voice Hub"""
        if self._logger:
            self._logger.system(f"[XTTS Hub] Requesting speech via Voice Hub...")
        
        result = self.hub_client.request_speech(
            text=text,
            voice_config={
                'type': 'xtts',
                'voice_sample': str(self._voice_sample_path),
                'language': self._language,
                'speed': self._speed
            },
            volume=volume,
            blocking=False
        )
        
        if result['status'] == 'accepted':
            return "Speech completed"
        else:
            error = result.get('error', 'Unknown error')
            if self._logger:
                self._logger.warning(f"[XTTS Hub] Hub request failed: {error}")
                self._logger.system(f"[XTTS Hub] Falling back to local generation")
            return self._speak_local(text, volume, stream)
    
    def _speak_local(self, text: str, volume: float, stream: bool) -> str:
        """Speak using local XTTS engine"""
        if self._logger:
            volume_pct = int(volume * 100)
            self._logger.system(f"[XTTS Local] Speaking (volume: {volume_pct}%)")
        
        if stream:
            result = self._xtts_engine.speak_stream(
                text=text,
                stop_flag=self._stop_event,
                volume=volume
            )
        else:
            result = self._xtts_engine.speak(
                text=text,
                stop_flag=self._stop_event,
                volume=volume
            )
        
        if result == "[SUCCESS]":
            return "Speech completed"
        elif result == "Interrupted":
            return "Interrupted"
        elif result.startswith("Error"):
            return result
        else:
            return "Speech completed"
    
    def set_hub_client(self, hub_client):
        """Inject Voice Hub client"""
        self.hub_client = hub_client
        if self._xtts_engine:
            self._xtts_engine.set_hub_client(hub_client)
    
    def set_streaming_handler(self, handler):
        """Inject streaming handler"""
        self.streaming_handler = handler
    
    def precache_phrases(self, phrases: list):
        """Pre-cache common phrases"""
        if self._xtts_engine:
            self._xtts_engine.precache_phrases(phrases)
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        if self._xtts_engine:
            return self._xtts_engine.get_cache_stats()
        return {'status': 'unavailable'}