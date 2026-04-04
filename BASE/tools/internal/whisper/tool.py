# BASE/tools/internal/whisper/tool.py
"""
Whisper Internal Tool - GPU Speech Recognition with Speaker Verification
"""
from typing import Optional
import threading
import queue

from BASE.handlers.internal_tool_interface import InternalToolInterface


class WhisperTool(InternalToolInterface):
    """
    GPU-accelerated speech recognition using Faster-Whisper
    
    Features:
    - RTX 50-series optimized (int8 compute)
    - Real-time transcription
    - Voice activity detection
    - Speaker verification (user voice filtering)
    - Voice Hub integration
    """
    
    __slots__ = (
        '_config', '_controls', '_logger', '_is_available',
        '_whisper_model', '_recognition_thread', '_raw_queue',
        '_text_queue', '_audio_segment_queue', '_stream', '_voice_enabled',
        '_speaker_verifier', '_use_speaker_verification',
        'hub_client', 'on_speech_callback'
    )
    
    @property
    def tool_name(self) -> str:
        return "whisper"
    
    @property
    def service_type(self) -> str:
        return "voice_input"
    
    def __init__(self, config, controls, logger=None):
        self._config = config
        self._controls = controls
        self._logger = logger
        
        self._is_available = False
        self._whisper_model = None
        self._recognition_thread = None
        self._raw_queue = None
        self._text_queue = None
        self._audio_segment_queue = None
        self._stream = None
        self._voice_enabled = False
        
        self._speaker_verifier = None
        self._use_speaker_verification = getattr(controls, 'USE_SPEAKER_VERIFICATION', False)
        
        self.hub_client = None
        self.on_speech_callback = None
    
    async def initialize(self) -> bool:
        """Initialize Whisper model and optional speaker verification"""
        if self._logger:
            self._logger.system("[Whisper] Loading GPU model...")
        
        try:
            from BASE.tools.internal.whisper.whisper_engine import load_whisper_model
            
            self._whisper_model = load_whisper_model()
            
            if self._whisper_model:
                self._is_available = True
                
                if self._logger:
                    import torch
                    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
                    self._logger.success(f"[Whisper] Ready on {gpu_name}")
            else:
                if self._logger:
                    self._logger.error("[Whisper] Model loading failed")
                return False
            
            if self._use_speaker_verification:
                await self._initialize_speaker_verification()
            
            return True
        
        except Exception as e:
            if self._logger:
                self._logger.error(f"[Whisper] Initialization error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _initialize_speaker_verification(self) -> bool:
        """Initialize speaker verification engine"""
        try:
            from pathlib import Path
            from personality.bot_info import username
            
            user_voice_sample = Path(f"./personality/voice/{username}_voice_sample.wav")
            
            if not user_voice_sample.exists():
                if self._logger:
                    self._logger.warning(
                        f"[Whisper] Speaker verification disabled - "
                        f"user voice sample not found: {user_voice_sample}"
                    )
                    self._logger.warning(
                        f"[Whisper] Create {user_voice_sample} to enable speaker verification"
                    )
                self._use_speaker_verification = False
                return False
            
            from BASE.tools.internal.speaker_verification.speaker_verification_engine import (
                SpeakerVerificationEngine
            )
            
            similarity_threshold = getattr(
                self._controls,
                'SPEAKER_VERIFICATION_THRESHOLD',
                0.75
            )
            
            self._speaker_verifier = SpeakerVerificationEngine(
                user_voice_sample=str(user_voice_sample),
                similarity_threshold=similarity_threshold,
                logger=self._logger
            )
            
            success = await self._speaker_verifier.initialize()
            
            if success:
                if self._logger:
                    self._logger.success(
                        f"[Whisper] Speaker verification enabled "
                        f"(threshold: {similarity_threshold:.2f})"
                    )
                return True
            else:
                if self._logger:
                    self._logger.error("[Whisper] Speaker verification initialization failed")
                self._use_speaker_verification = False
                return False
        
        except Exception as e:
            if self._logger:
                self._logger.error(f"[Whisper] Speaker verification setup error: {e}")
            import traceback
            traceback.print_exc()
            self._use_speaker_verification = False
            return False
    
    async def cleanup(self):
        """Cleanup Whisper and speaker verification resources"""
        self.stop_listening()
        
        if self._speaker_verifier:
            await self._speaker_verifier.cleanup()
            self._speaker_verifier = None
        
        if self._logger:
            self._logger.system("[Whisper] Cleaned up")
    
    def is_available(self) -> bool:
        """Check if Whisper is ready"""
        return self._is_available
    
    def start_listening(self, callback=None) -> bool:
        """Start voice recognition"""
        if not self.is_available():
            return False
        
        if self._voice_enabled:
            if self._logger:
                self._logger.warning("[Whisper] Already listening")
            return True
        
        self.on_speech_callback = callback
        
        self._raw_queue = queue.Queue(maxsize=50)
        self._text_queue = queue.Queue(maxsize=20)
        self._audio_segment_queue = queue.Queue(maxsize=20)
        
        from BASE.tools.internal.whisper.whisper_engine import recognition_worker_whisper
        
        self._recognition_thread = threading.Thread(
            target=lambda: recognition_worker_whisper(self),
            daemon=True,
            name="WhisperGPU"
        )
        self._recognition_thread.start()
        
        from BASE.tools.internal.whisper.whisper_engine import start_audio_stream
        
        self._stream = start_audio_stream(self)
        
        self._voice_enabled = True
        
        if self._logger:
            verification_status = "with speaker verification" if self._use_speaker_verification else "without speaker verification"
            self._logger.success(f"[Whisper] Started listening {verification_status}")
        
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
            self._logger.system("[Whisper] Stopped listening")
    
    def _speech_processing_loop(self):
        """Process recognized text from queue with optional speaker verification"""
        from personality.bot_info import agentname, username
        
        if self._logger:
            self._logger.system("[Whisper] Speech processing loop started")
        
        while self._voice_enabled:
            try:
                text = self._text_queue.get(timeout=0.1)
                
                if self._logger:
                    self._logger.system(f"[Whisper] Got text from queue: '{text}'")
                
                if self._use_speaker_verification and self._speaker_verifier:
                    try:
                        audio_segment = self._audio_segment_queue.get(timeout=0.1)
                        
                        is_user, similarity = self._speaker_verifier.verify_speaker(
                            audio_segment['audio'],
                            audio_segment['sample_rate']
                        )
                        
                        if not is_user:
                            if self._logger:
                                self._logger.system(
                                    f"[Whisper] Rejected non-user voice "
                                    f"(similarity: {similarity:.3f}, text: '{text}')"
                                )
                            continue
                        
                        if self._logger:
                            self._logger.system(
                                f"[Whisper] Verified user voice (similarity: {similarity:.3f})"
                            )
                    
                    except queue.Empty:
                        if self._logger:
                            self._logger.warning(
                                "[Whisper] No audio segment for speaker verification, accepting text"
                            )
                
                if text and len(text) >= 3:
                    if agentname.lower() not in text.lower():
                        if self._logger:
                            self._logger.speech(f"[User] {text}")
                        
                        if self.on_speech_callback:
                            if self._logger:
                                self._logger.system(f"[Whisper] Calling callback with: {username}, {text}")
                            self.on_speech_callback(username, text)
                        else:
                            if self._logger:
                                self._logger.error("[Whisper] No callback registered!")
                    else:
                        if self._logger:
                            self._logger.system(f"[Whisper] Filtered (contains agent name): {text}")
            
            except queue.Empty:
                continue
            except Exception as e:
                if self._logger:
                    self._logger.error(f"[Whisper] Processing error: {e}")
                import traceback
                traceback.print_exc()
    
    def set_hub_client(self, hub_client):
        """Inject Voice Hub client"""
        self.hub_client = hub_client
    
    def enable_speaker_verification(self, enable: bool):
        """Enable or disable speaker verification at runtime"""
        self._use_speaker_verification = enable
        
        if self._logger:
            status = "enabled" if enable else "disabled"
            self._logger.system(f"[Whisper] Speaker verification {status}")
    
    def update_verification_threshold(self, threshold: float):
        """Update speaker verification threshold"""
        if self._speaker_verifier:
            self._speaker_verifier.update_threshold(threshold)
        
        if self._logger:
            self._logger.system(f"[Whisper] Verification threshold updated to {threshold:.2f}")