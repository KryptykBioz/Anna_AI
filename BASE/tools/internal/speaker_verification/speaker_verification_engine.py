# BASE/tools/internal/speaker_verification/speaker_verification_engine.py
"""
Speaker Verification Engine - XTTS-based voice identification
Uses XTTS speaker embeddings to distinguish the user's voice from others
"""
import torch
import numpy as np
from pathlib import Path
from typing import Optional, Tuple


class SpeakerVerificationEngine:
    """
    Speaker verification using XTTS speaker embeddings
    Filters audio to only accept the authorized user's voice
    
    Leverages existing XTTS model infrastructure for zero additional dependencies
    """
    
    __slots__ = (
        '_device', '_tts_model', '_user_embedding', '_threshold',
        'logger', '_initialized', 'user_voice_sample', '_config'
    )
    
    def __init__(
        self,
        user_voice_sample: str,
        similarity_threshold: float = 0.70,
        logger=None
    ):
        """
        Initialize speaker verification engine
        
        Args:
            user_voice_sample: Path to user's voice sample WAV file
            similarity_threshold: Minimum cosine similarity for acceptance (0.0-1.0)
                                 0.75 = strict (recommended for security)
                                 0.65 = moderate (more permissive)
                                 0.55 = loose (accepts similar voices)
            logger: Optional logger instance
        """
        self.user_voice_sample = user_voice_sample
        self._threshold = similarity_threshold
        self.logger = logger
        
        self._device = None
        self._tts_model = None
        self._config = None
        self._user_embedding = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize speaker verification model"""
        try:
            if self.logger:
                self.logger.system("[Speaker Verification] Initializing...")
            
            if not Path(self.user_voice_sample).exists():
                if self.logger:
                    self.logger.error(
                        f"[Speaker Verification] User voice sample not found: {self.user_voice_sample}"
                    )
                return False
            
            self._device = self._get_best_device()
            
            if self.logger:
                self.logger.system(f"[Speaker Verification] Device: {self._device.upper()}")
            
            import torch.serialization
            from TTS.tts.configs.xtts_config import XttsConfig
            from TTS.tts.models.xtts import Xtts, XttsArgs, XttsAudioConfig
            from TTS.config.shared_configs import BaseDatasetConfig, BaseAudioConfig
            from TTS.tts.configs.shared_configs import BaseTrainingConfig
            
            torch.serialization.add_safe_globals([
                XttsConfig,
                XttsArgs,
                XttsAudioConfig,
                BaseDatasetConfig,
                BaseAudioConfig,
                BaseTrainingConfig
            ])
            
            config_path = Path(__file__).parent / 'xtts_config.json'
            
            if not config_path.exists():
                config_path = Path('./BASE/tools/internal/xtts/xtts_config.json')
            
            self._config = XttsConfig()
            self._config.load_json(str(config_path))
            
            if self.logger:
                self.logger.system("[Speaker Verification] Loading XTTS model...")
            
            self._tts_model = Xtts.init_from_config(self._config)
            
            checkpoint_dir = Path("./models/tts_models--multilingual--multi-dataset--xtts_v2")
            
            if not checkpoint_dir.exists():
                checkpoint_dir = Path("./models/xtts-v2")
                if not checkpoint_dir.exists():
                    if self.logger:
                        self.logger.error(
                            f"[Speaker Verification] XTTS model not found. "
                            f"Expected at: ./models/tts_models--multilingual--multi-dataset--xtts_v2 "
                            f"or ./models/xtts-v2"
                        )
                    return False
            
            self._tts_model.load_checkpoint(
                self._config,
                checkpoint_dir=str(checkpoint_dir),
                use_deepspeed=False
            )
            self._tts_model.to(self._device)
            self._tts_model.eval()
            
            if self.logger:
                self.logger.system("[Speaker Verification] Computing user voice embedding...")
            
            self._user_embedding = self._compute_embedding(self.user_voice_sample)
            
            if self._user_embedding is None:
                if self.logger:
                    self.logger.error("[Speaker Verification] Failed to compute user embedding")
                return False
            
            self._initialized = True
            
            if self.logger:
                self.logger.success(
                    f"[Speaker Verification] Ready (threshold: {self._threshold:.2f}, "
                    f"device: {self._device.upper()})"
                )
            
            return True
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Speaker Verification] Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def verify_speaker(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> Tuple[bool, float]:
        """
        Verify if audio matches the authorized user's voice
        
        Args:
            audio_data: Audio samples as numpy array (float32, range -1.0 to 1.0)
            sample_rate: Sample rate of audio (must be 16000 for XTTS)
        
        Returns:
            (is_user, similarity_score)
            - is_user: True if similarity >= threshold
            - similarity_score: Cosine similarity (0.0 to 1.0)
        """
        if not self._initialized:
            if self.logger:
                self.logger.warning("[Speaker Verification] Not initialized")
            return False, 0.0
        
        try:
            import tempfile
            import soundfile as sf
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            sf.write(tmp_path, audio_data, sample_rate)
            
            test_embedding = self._compute_embedding(tmp_path)
            
            os.remove(tmp_path)
            
            if test_embedding is None:
                if self.logger:
                    self.logger.warning("[Speaker Verification] Failed to compute test embedding")
                return False, 0.0
            
            similarity = self._compute_similarity(self._user_embedding, test_embedding)
            
            is_user = similarity >= self._threshold
            
            if self.logger:
                status = "[MATCH]" if is_user else "[REJECT]"
                self.logger.system(
                    f"[Speaker Verification] {status} Similarity: {similarity:.3f}"
                )
            
            return is_user, similarity
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Speaker Verification] Verification error: {e}")
            import traceback
            traceback.print_exc()
            return False, 0.0
    def _compute_embedding(self, audio_path: str) -> Optional[np.ndarray]:
        """Compute speaker embedding from audio file"""
        try:
            import soundfile as sf
            import torch
            import tempfile
            import os
            
            audio_data, sample_rate = sf.read(audio_path, dtype='float32')
            
            if audio_data.ndim > 1:
                audio_data = audio_data.mean(axis=1)
            
            if sample_rate != 22050:
                from scipy import signal
                num_samples = int(len(audio_data) * 22050 / sample_rate)
                audio_data = signal.resample(audio_data, num_samples).astype('float32')
                sample_rate = 22050
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            try:
                sf.write(tmp_path, audio_data, sample_rate)
                
                import torchaudio
                original_load = torchaudio.load
                
                def soundfile_load(filepath, *args, **kwargs):
                    data, sr = sf.read(filepath, dtype='float32')
                    if data.ndim == 1:
                        data = data.reshape(1, -1)
                    else:
                        data = data.T
                    return torch.from_numpy(data), sr
                
                torchaudio.load = soundfile_load
                
                try:
                    gpt_cond_latent, speaker_embedding = self._tts_model.get_conditioning_latents(
                        audio_path=[tmp_path],
                        gpt_cond_len=self._tts_model.config.gpt_cond_len,
                        max_ref_length=self._tts_model.config.max_ref_len,
                        sound_norm_refs=self._tts_model.config.sound_norm_refs
                    )
                    
                    embedding = speaker_embedding.cpu().numpy()
                    
                    return embedding
                finally:
                    torchaudio.load = original_load
            finally:
                try:
                    os.remove(tmp_path)
                except:
                    pass
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Speaker Verification] Embedding computation failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between embeddings
        
        Args:
            embedding1: First speaker embedding
            embedding2: Second speaker embedding
        
        Returns:
            Cosine similarity score (0.0 to 1.0)
            - 1.0 = identical voice
            - 0.75+ = very likely same speaker
            - 0.60-0.75 = possibly same speaker
            - <0.60 = different speaker
        """
        from numpy.linalg import norm
        
        embedding1_flat = embedding1.flatten()
        embedding2_flat = embedding2.flatten()
        
        dot_product = np.dot(embedding1_flat, embedding2_flat)
        magnitude = norm(embedding1_flat) * norm(embedding2_flat)
        
        if magnitude == 0:
            return 0.0
        
        similarity = dot_product / magnitude
        
        similarity = np.clip(similarity, 0.0, 1.0)
        
        return float(similarity)
    
    def update_threshold(self, new_threshold: float):
        """
        Update similarity threshold
        
        Args:
            new_threshold: New threshold value (0.0 to 1.0)
        """
        self._threshold = np.clip(new_threshold, 0.0, 1.0)
        
        if self.logger:
            self.logger.system(
                f"[Speaker Verification] Threshold updated to {self._threshold:.2f}"
            )
    
    def get_threshold(self) -> float:
        """Get current similarity threshold"""
        return self._threshold
    
    def is_initialized(self) -> bool:
        """Check if engine is initialized"""
        return self._initialized
    
    def _get_best_device(self) -> str:
        """Detect best available device"""
        if not torch.cuda.is_available():
            return 'cpu'
        
        try:
            test_tensor = torch.zeros(1).cuda()
            result = test_tensor + 1
            del test_tensor, result
            torch.cuda.empty_cache()
            return 'cuda'
        except:
            return 'cpu'
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._tts_model:
            del self._tts_model
            self._tts_model = None
        
        if self._user_embedding is not None:
            del self._user_embedding
            self._user_embedding = None
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        self._initialized = False
        
        if self.logger:
            self.logger.system("[Speaker Verification] Cleaned up")