# BASE/tools/internal/pyttsx3/pyttsx3_engine.py
"""
pyttsx3 Engine - Self-contained system voice implementation
Extracted from text_to_system_voice.py for modular architecture
"""
import os
import tempfile
import pyttsx3
import sounddevice as sd
import soundfile as sf
import threading
import numpy as np
from pathlib import Path
import re

_current_temp_file = None
_temp_file_lock = threading.Lock()


def _get_temp_wav():
    """Create and track a unique temp WAV file"""
    global _current_temp_file
    with _temp_file_lock:
        if _current_temp_file and os.path.exists(_current_temp_file):
            try:
                os.remove(_current_temp_file)
            except:
                pass
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="tts_")
        os.close(fd)
        _current_temp_file = path
        return path


def _cleanup_temp_file(path):
    """Safely delete temp file"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except:
        pass


def clean_text_for_tts(text: str) -> str:
    """Clean text for TTS"""
    text = re.sub(r'[""]', '', text)
    text = re.sub(r'\*[^*]*\*', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'_', ' ', text)
    return text.strip()


def find_vb_cable_device():
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


def speak_system_voice(text: str, engine, stop_event=None, volume: float = 1.0) -> str:
    """
    Generate and play speech using system voice
    
    Args:
        text: Text to speak
        engine: pyttsx3 engine instance
        stop_event: Optional threading.Event to interrupt
        volume: Volume level (0.0 to 1.0)
    
    Returns:
        "Speech completed", "Interrupted", or "Error: <message>"
    """
    text = clean_text_for_tts(text)
    if not text:
        return "Error: No text after cleaning"
    
    temp_wav = None
    try:
        temp_wav = _get_temp_wav()
        
        generation_done = threading.Event()
        generation_error = None
        
        def generate_wav(engine_to_use):
            """Generate WAV file"""
            nonlocal generation_error
            try:
                from personality.bot_info import voiceIndex
                
                voices = engine_to_use.getProperty('voices')
                if 0 <= voiceIndex < len(voices):
                    engine_to_use.setProperty('voice', voices[voiceIndex].id)
                engine_to_use.setProperty('rate', 200)
                engine_to_use.setProperty('volume', 1.0)
                
                engine_to_use.save_to_file(text, temp_wav)
                engine_to_use.runAndWait()
                
                generation_done.set()
            
            except Exception as e:
                generation_error = e
                generation_done.set()
        
        thread = threading.Thread(target=generate_wav, args=(engine,), daemon=True)
        thread.start()
        
        while not generation_done.is_set():
            if stop_event and stop_event.is_set():
                _cleanup_temp_file(temp_wav)
                return "Interrupted"
            generation_done.wait(0.1)
        
        if generation_error:
            raise generation_error
        
        if not os.path.exists(temp_wav):
            raise RuntimeError("WAV file was not created")
        
        if stop_event and stop_event.is_set():
            _cleanup_temp_file(temp_wav)
            return "Interrupted"
        
        data, samplerate = sf.read(temp_wav, dtype='float32')
        
        clamped_volume = max(0.0, min(1.0, volume))
        
        if clamped_volume < 1.0:
            data = data * clamped_volume
            data = np.clip(data, -1.0, 1.0)
        
        device = find_vb_cable_device()
        
        sd.play(data, samplerate, device=device)
        
        while sd.get_stream().active:
            if stop_event and stop_event.is_set():
                sd.stop()
                return "Interrupted"
            sd.sleep(100)
        
        return "Speech completed"
    
    except Exception as e:
        return f"Error: {e}"
    
    finally:
        if temp_wav:
            _cleanup_temp_file(temp_wav)