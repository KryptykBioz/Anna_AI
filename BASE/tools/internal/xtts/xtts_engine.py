# BASE/tools/internal/xtts/xtts_engine.py
"""
XTTS Engine - Self-contained XTTS implementation
Extracted from text_to_custom_voice.py for modular architecture
"""
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['OMP_NUM_THREADS'] = '12'
os.environ['MKL_NUM_THREADS'] = '12'
os.environ['TORCHAUDIO_USE_BACKEND_DISPATCHER'] = '0'
os.environ['TORCHAUDIO_BACKEND'] = 'soundfile'

import sys
from pathlib import Path
from typing import Iterator, Optional, Dict
import time
import tempfile
import sounddevice as sd
import soundfile as sf
import torch
import threading
import re
import numpy as np
import pickle
import hashlib

torch.backends.cudnn.enabled = False

_original_torch_load = torch.load

def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _patched_torch_load

import torchaudio
import soundfile as sf_lib

_original_torchaudio_load = torchaudio.load

def _soundfile_load(filepath, *args, **kwargs):
    try:
        data, sr = sf_lib.read(filepath, dtype='float32')
        if len(data.shape) == 1:
            audio = torch.from_numpy(data).unsqueeze(0)
        else:
            audio = torch.from_numpy(data.T)
        return audio, sr
    except:
        return _original_torchaudio_load(filepath, *args, **kwargs)

torchaudio.load = _soundfile_load

from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts


class XTTSEngine:
    """
    Self-contained XTTS voice cloning engine
    
    Features:
    - GPU-accelerated synthesis
    - Dual caching (embeddings + audio)
    - Sentence streaming
    - Voice Hub integration
    """
    
    __slots__ = (
        'voice_sample_path', 'language', 'speed', 'logger',
        '_device', '_tts_model', '_embeddings_cache', '_audio_cache',
        '_cache_dir', 'hub_client', '_initialized'
    )
    
    def __init__(self, voice_sample_path: str, language: str = 'en',
                 speed: float = 1.0, logger=None, hub_client=None):
        self.voice_sample_path = voice_sample_path
        self.language = language
        self.speed = speed
        self.logger = logger
        self.hub_client = hub_client
        
        self._device = None
        self._tts_model = None
        self._embeddings_cache = {}
        self._audio_cache = {}
        self._cache_dir = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize XTTS model and caches"""
        try:
            if self.logger:
                self.logger.system("[XTTS Engine] Initializing...")
            
            self._device = self._get_best_device()
            
            if self.logger:
                device_str = self._device if isinstance(self._device, str) else str(self._device)
                self.logger.system(f"[XTTS Engine] Using device: {device_str.upper()}")
            
            self._setup_cache_directory()
            self._load_embeddings_cache()
            
            if self.logger:
                self.logger.system("[XTTS Engine] Loading XTTS v2 model...")
            
            self._tts_model = self._init_tts()
            
            if not self._tts_model:
                return False
            
            if self.logger:
                self.logger.system("[XTTS Engine] Computing voice embeddings...")
            
            self._compute_voice_embeddings()
            
            self._initialized = True
            
            if self.logger:
                self.logger.success("[XTTS Engine] Ready")
            
            return True
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[XTTS Engine] Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def cleanup(self):
        """Cleanup XTTS resources"""
        self._save_embeddings_cache()
        
        if self._tts_model:
            del self._tts_model
            self._tts_model = None
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        if self.logger:
            self.logger.system("[XTTS Engine] Cleaned up")
    
    def speak(self, text: str, stop_flag=None, volume: float = 1.0) -> str:
        """Generate and play complete audio"""
        if not self._initialized:
            return "Error: Engine not initialized"
        
        text = self._clean_text(text)
        if not text:
            return "Error: No text after cleaning"
        
        try:
            cache_key = self._get_cache_key(text)
            
            if cache_key in self._audio_cache:
                if self.logger:
                    self.logger.audio("[XTTS] Using cached audio")
                audio_data, sr = self._audio_cache[cache_key]
            else:
                audio_data, sr = self._generate_audio(text)
                self._cache_audio(cache_key, audio_data, sr)
            
            if stop_flag and stop_flag.is_set():
                return "Interrupted"
            
            return self._play_audio(audio_data, sr, volume, stop_flag)
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[XTTS] Error: {e}")
            return f"Error: {e}"
    
    def speak_stream(self, text: str, stop_flag=None, volume: float = 1.0) -> str:
        """Generate and stream audio sentence-by-sentence"""
        if not self._initialized:
            return "Error: Engine not initialized"
        
        text = self._clean_text(text)
        if not text:
            return "Error: No text after cleaning"
        
        sentences = self._split_into_sentences(text)
        
        if self.logger:
            self.logger.audio(f"[XTTS Stream] {len(sentences)} sentences")
        
        for idx, sentence in enumerate(sentences):
            if stop_flag and stop_flag.is_set():
                if self.logger:
                    self.logger.audio("[XTTS Stream] Interrupted")
                return "Interrupted"
            
            cache_key = self._get_cache_key(sentence)
            
            if cache_key in self._audio_cache:
                audio_data, sr = self._audio_cache[cache_key]
            else:
                audio_data, sr = self._generate_audio(sentence)
                self._cache_audio(cache_key, audio_data, sr)
            
            result = self._play_audio(audio_data, sr, volume, stop_flag)
            
            if "Interrupted" in result:
                return "Interrupted"
            elif "Error" in result:
                if self.logger:
                    self.logger.warning(f"[XTTS Stream] Sentence {idx+1} failed: {result}")
                continue
        
        return "[SUCCESS]"
    
    def speak_streaming_chunks(self, text_chunks: Iterator[str], stop_event=None, volume: float = 1.0) -> str:
        """Speak text chunks as they arrive"""
        if not self._initialized:
            return "Error: Engine not initialized"
        
        buffer = ""
        chunk_count = 0
        
        for text_chunk in text_chunks:
            if stop_event and stop_event.is_set():
                return "Interrupted"
            
            if not text_chunk or not text_chunk.strip():
                continue
            
            buffer += text_chunk
            
            has_punctuation = any(char in buffer for char in '.!?,;:')
            word_count = len(buffer.split())
            
            if (has_punctuation and word_count >= 3) or word_count >= 10:
                sentence = buffer.strip()
                buffer = ""
                
                cache_key = self._get_cache_key(sentence)
                
                if cache_key in self._audio_cache:
                    audio_data, sr = self._audio_cache[cache_key]
                else:
                    audio_data, sr = self._generate_audio(sentence)
                    self._cache_audio(cache_key, audio_data, sr)
                
                result = self._play_audio(audio_data, sr, volume, stop_event)
                
                if "Interrupted" in result:
                    return "Interrupted"
                
                chunk_count += 1
        
        if buffer.strip():
            sentence = buffer.strip()
            cache_key = self._get_cache_key(sentence)
            
            if cache_key in self._audio_cache:
                audio_data, sr = self._audio_cache[cache_key]
            else:
                audio_data, sr = self._generate_audio(sentence)
                self._cache_audio(cache_key, audio_data, sr)
            
            result = self._play_audio(audio_data, sr, volume, stop_event)
            
            if "Interrupted" in result:
                return "Interrupted"
        
        return "[SUCCESS]"
    
    def stop(self):
        """Stop playback"""
        try:
            sd.stop()
        except:
            pass
    
    def get_device(self) -> str:
        """Get device string"""
        if self._device:
            return self._device if isinstance(self._device, str) else str(self._device)
        return "unknown"
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'embeddings_cached': len(self._embeddings_cache),
            'audio_clips_cached': len(self._audio_cache)
        }
    
    def precache_phrases(self, phrases: list):
        """Pre-cache common phrases"""
        if self.logger:
            self.logger.system(f"[XTTS] Pre-caching {len(phrases)} phrases")
        
        for phrase in phrases:
            cache_key = self._get_cache_key(phrase)
            if cache_key not in self._audio_cache:
                try:
                    audio_data, sr = self._generate_audio(phrase)
                    self._cache_audio(cache_key, audio_data, sr)
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"[XTTS] Cache failed for '{phrase}': {e}")
    
    def set_hub_client(self, hub_client):
        """Set Voice Hub client"""
        self.hub_client = hub_client
    
    def _get_best_device(self):
        """Detect best available device"""
        force_device = os.environ.get('XTTS_DEVICE', '').lower()
        
        if force_device == 'cpu':
            return 'cpu'
        
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
        
    def _init_tts(self):
        """Initialize TTS model"""
        try:
            config_path = Path(__file__).parent / 'xtts_config.json'
            
            if not config_path.exists():
                config_path = self._download_xtts_config()
            
            config = XttsConfig()
            config.load_json(str(config_path))
            
            model = Xtts.init_from_config(config)
            
            checkpoint_dir = self._find_xtts_model_directory()
            
            if not checkpoint_dir:
                if self.logger:
                    self.logger.error("[XTTS] Model not found. Attempting to download...")
                checkpoint_dir = self._download_xtts_model()
                
                if not checkpoint_dir:
                    if self.logger:
                        self.logger.error("[XTTS] Model download failed")
                    return None
            
            if self.logger:
                self.logger.system(f"[XTTS] Loading from: {checkpoint_dir}")
            
            model.load_checkpoint(
                config,
                checkpoint_dir=str(checkpoint_dir),
                use_deepspeed=False
            )
            
            if self._device == 'cuda':
                model.cuda()
            
            return model
        except Exception as e:
            if self.logger:
                self.logger.error(f"[XTTS] Model init failed: {e}")
            return None
        
    def _find_xtts_model_directory(self):
        """
        Find XTTS model directory
        
        Only searches in: Anna_AI/models/tts_models--multilingual--multi-dataset--xtts_v2
        """
        project_models_dir = Path(__file__).parent.parent.parent.parent.parent / 'models' / 'tts_models--multilingual--multi-dataset--xtts_v2'
        
        if project_models_dir.exists() and (project_models_dir / 'model.pth').exists():
            if self.logger:
                self.logger.system(f"[XTTS] Found model at: {project_models_dir}")
            return project_models_dir
        
        if self.logger:
            self.logger.warning(f"[XTTS] Model not found at: {project_models_dir}")
        
        return None

    def _download_xtts_model(self):
        """
        Download XTTS model and move to project directory
        
        Returns path to model directory in Anna_AI/models
        """
        try:
            if self.logger:
                self.logger.system("[XTTS] Downloading model from Hugging Face...")
                self.logger.system("[XTTS] This is a one-time download (~1.8GB)")
            
            from TTS.utils.manage import ModelManager
            import shutil
            
            manager = ModelManager()
            result = manager.download_model("tts_models/multilingual/multi-dataset/xtts_v2")
            
            if isinstance(result, tuple) and len(result) >= 1:
                model_path = result[0]
            else:
                model_path = result
            
            model_path = Path(model_path)
            
            if model_path.is_file() and model_path.name == 'model.pth':
                source_dir = model_path.parent
            elif model_path.is_dir():
                source_dir = model_path
            else:
                source_dir = model_path.parent
            
            if self.logger:
                self.logger.system(f"[XTTS] Source: {source_dir}")
            
            if not (source_dir / 'model.pth').exists():
                raise RuntimeError(f"model.pth not found in {source_dir}")
            
            target_dir = Path(__file__).parent.parent.parent.parent.parent / 'models' / 'tts_models--multilingual--multi-dataset--xtts_v2'
            
            if self.logger:
                self.logger.system(f"[XTTS] Moving model to: {target_dir}")
            
            if target_dir.exists():
                shutil.rmtree(target_dir)
            
            shutil.copytree(source_dir, target_dir)
            
            if (target_dir / 'model.pth').exists():
                if self.logger:
                    self.logger.success(f"[XTTS] Model installed at: {target_dir}")
                return target_dir
            else:
                raise RuntimeError(f"Copy failed - model.pth not in {target_dir}")
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[XTTS] Download/move failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _download_xtts_config(self):
        """Download XTTS config if missing"""
        import urllib.request
        
        config_url = "https://huggingface.co/coqui/XTTS-v2/raw/main/config.json"
        config_path = Path(__file__).parent / 'xtts_config.json'
        
        urllib.request.urlretrieve(config_url, str(config_path))
        
        return config_path
    
    def _setup_cache_directory(self):
        """Setup cache directory"""
        self._cache_dir = Path.home() / '.cache' / 'xtts_embeddings'
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_embeddings_cache(self):
        """Load embeddings from disk"""
        cache_file = self._cache_dir / 'embeddings.pkl'
        
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    self._embeddings_cache = pickle.load(f)
                
                if self.logger:
                    self.logger.system(f"[XTTS] Loaded {len(self._embeddings_cache)} cached embeddings")
            except:
                self._embeddings_cache = {}
    
    def _save_embeddings_cache(self):
        """Save embeddings to disk"""
        if not self._cache_dir:
            return
        
        cache_file = self._cache_dir / 'embeddings.pkl'
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(self._embeddings_cache, f)
        except:
            pass
    
    def _compute_voice_embeddings(self):
        """Compute voice embeddings from sample"""
        cache_key = f"voice_{Path(self.voice_sample_path).stem}"
        
        if cache_key in self._embeddings_cache:
            return
        
        try:
            gpt_cond_latent, speaker_embedding = self._tts_model.get_conditioning_latents(
                audio_path=[self.voice_sample_path],
                gpt_cond_len=30,
                gpt_cond_chunk_len=4,
                max_ref_length=60
            )
            
            self._embeddings_cache[cache_key] = {
                'gpt_cond_latent': gpt_cond_latent,
                'speaker_embedding': speaker_embedding
            }
        except Exception as e:
            if self.logger:
                self.logger.error(f"[XTTS] Embedding computation failed: {e}")
    
    def _generate_audio(self, text: str):
        """Generate audio from text"""
        cache_key = f"voice_{Path(self.voice_sample_path).stem}"
        embeddings = self._embeddings_cache.get(cache_key)
        
        if not embeddings:
            raise RuntimeError("Voice embeddings not available")
        
        out = self._tts_model.inference(
            text,
            self.language,
            embeddings['gpt_cond_latent'],
            embeddings['speaker_embedding'],
            temperature=0.7,
            length_penalty=1.0,
            repetition_penalty=5.0,
            top_k=50,
            top_p=0.85,
            speed=self.speed
        )
        
        audio_data = np.array(out['wav'])
        sr = 24000
        
        return audio_data, sr
    
    def _play_audio(self, audio_data, sr, volume, stop_flag):
        """Play audio with volume control"""
        try:
            if volume < 1.0:
                audio_data = audio_data * volume
                audio_data = np.clip(audio_data, -1.0, 1.0)
            
            device = self._find_vb_cable_device()
            
            sd.play(audio_data, sr, device=device)
            
            while sd.get_stream().active:
                if stop_flag and stop_flag.is_set():
                    sd.stop()
                    return "Interrupted"
                sd.sleep(100)
            
            return "[SUCCESS]"
        
        except Exception as e:
            return f"Error: {e}"
    
    def _find_vb_cable_device(self):
        """Find VB-Cable device"""
        try:
            from personality.bot_info import vb_cable_name
            
            devices = sd.query_devices()
            
            for i, device in enumerate(devices):
                device_name = device['name']
                if device['max_output_channels'] > 0:
                    if vb_cable_name in device_name:
                        return i
        except:
            pass
        
        return None
    
    def _clean_text(self, text: str) -> str:
        """Clean text for TTS"""
        text = re.sub(r'[""]', '', text)
        text = re.sub(r'\*[^*]*\*', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'_', ' ', text)
        return text.strip()
    
    def _split_into_sentences(self, text: str):
        """Split text into sentences"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            sentences = [text]
        
        return sentences
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def _cache_audio(self, key: str, audio_data, sr):
        """Cache audio data"""
        MAX_CACHE = 50
        
        if len(self._audio_cache) >= MAX_CACHE:
            oldest_key = next(iter(self._audio_cache))
            del self._audio_cache[oldest_key]
        
        self._audio_cache[key] = (audio_data, sr)