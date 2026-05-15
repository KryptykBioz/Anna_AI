# BASE/tools/internal/vosk/tool.py
"""
Vosk Internal Tool - CPU Speech Recognition
Fallback voice recognition for systems without CUDA support
"""
from typing import Optional
import threading
import queue
from pathlib import Path

from BASE.handlers.internal_tool_interface import InternalToolInterface


class VoskTool(InternalToolInterface):
    """
    CPU-based speech recognition using Vosk
    
    Features:
    - No GPU required (CPU-only)
    - Lightweight offline recognition
    - Voice Hub integration
    - Fallback for systems without CUDA
    """
    
    __slots__ = (
        '_config', '_controls', '_logger', '_is_available',
        '_vosk_model', '_recognition_thread', '_raw_queue',
        '_text_queue', '_stream', '_voice_enabled', '_model_path',
        'hub_client', 'on_speech_callback'
    )
    
    @property
    def tool_name(self) -> str:
        return "vosk"
    
    @property
    def service_type(self) -> str:
        return "voice_input"
    
    def __init__(self, config, controls, logger=None):
        self._config = config
        self._controls = controls
        self._logger = logger
        
        self._is_available = False
        self._vosk_model = None
        self._recognition_thread = None
        self._raw_queue = None
        self._text_queue = None
        self._stream = None
        self._voice_enabled = False
        
        project_root = Path(__file__).parent.parent.parent.parent.parent
        self._model_path = project_root / "models" / "vosk-model-en-us-0.42-gigaspeech"
        
        self.hub_client = None
        self.on_speech_callback = None
    
    async def initialize(self) -> bool:
        """Initialize Vosk model"""
        if self._logger:
            self._logger.system("[Vosk] Loading CPU model...")
        
        if not self._model_path.exists():
            if self._logger:
                self._logger.error(f"[Vosk] Model not found: {self._model_path}")
                self._logger.error("[Vosk] Expected location: Anna_AI/models/vosk-model-en-us-0.42-gigaspeech")
            return False
        
        try:
            from BASE.tools.internal.vosk.vosk_engine import load_vosk_model
            
            self._vosk_model = load_vosk_model(str(self._model_path))
            
            if self._vosk_model:
                self._is_available = True
                
                if self._logger:
                    self._logger.success(f"[Vosk] CPU recognition ready (model: {self._model_path.name})")
                
                return True
            else:
                if self._logger:
                    self._logger.error("[Vosk] Model loading failed")
                return False
        
        except Exception as e:
            if self._logger:
                self._logger.error(f"[Vosk] Initialization error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def cleanup(self):
        """Cleanup Vosk resources"""
        self.stop_listening()
        
        if self._logger:
            self._logger.system("[Vosk] Cleaned up")
    
    def is_available(self) -> bool:
        """Check if Vosk is ready"""
        return self._is_available
    
    def start_listening(self, callback=None) -> bool:
        """Start voice recognition"""
        if not self.is_available():
            return False
        
        if self._voice_enabled:
            if self._logger:
                self._logger.warning("[Vosk] Already listening")
            return True
        
        self.on_speech_callback = callback
        
        self._raw_queue = queue.Queue(maxsize=50)
        self._text_queue = queue.Queue(maxsize=20)
        
        from BASE.tools.internal.vosk.vosk_engine import recognition_worker_vosk
        
        self._recognition_thread = threading.Thread(
            target=lambda: recognition_worker_vosk(self),
            daemon=True,
            name="VoskCPU"
        )
        self._recognition_thread.start()
        
        from BASE.tools.internal.vosk.vosk_engine import start_audio_stream
        
        self._stream = start_audio_stream(self)
        
        self._voice_enabled = True
        
        if self._logger:
            self._logger.success("[Vosk] Started listening")
        
        processing_thread = threading.Thread(
            target=self._speech_processing_loop,
            daemon=True
        )
        processing_thread.start()
        
        return True
    
    def stop_listening(self):
        """Stop voice recognition"""
        if not self._voice_enabled:
            return
        
        self._voice_enabled = False
        
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except:
                pass
            self._stream = None
        
        if self._raw_queue:
            try:
                self._raw_queue.put(b"__EXIT__")
            except:
                pass
        
        if self._recognition_thread and self._recognition_thread.is_alive():
            self._recognition_thread.join(timeout=2.0)
        
        if self._logger:
            self._logger.system("[Vosk] Stopped listening")
    
    def _speech_processing_loop(self):
        """Process recognized text from queue"""
        from BASE.config.bot_info import agentname, username
        
        while self._voice_enabled:
            try:
                text = self._text_queue.get(timeout=0.1)
                
                if text and len(text) >= 3:
                    if agentname.lower() not in text.lower():
                        if self._logger:
                            self._logger.speech(f"[User] {text}")
                        
                        if self.on_speech_callback:
                            self.on_speech_callback(username, text)
            
            except queue.Empty:
                continue
            except Exception as e:
                if self._logger:
                    self._logger.error(f"[Vosk] Processing error: {e}")
    
    def set_hub_client(self, hub_client):
        """Inject Voice Hub client"""
        self.hub_client = hub_client