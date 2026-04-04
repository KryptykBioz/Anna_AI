# BASE/tools/internal/vosk/vosk_engine.py
"""
Vosk Engine - Self-contained CPU speech recognition
Extracted for modular architecture
"""
import json
import numpy as np
import threading
import sounddevice as sd
import queue
from pathlib import Path

SAMPLERATE = 16000
AUDIO_BLOCKSIZE = 16384
QUEUE_MAX_SIZE = 50


def load_vosk_model(model_path: str):
    """
    Load Vosk model from path
    
    Args:
        model_path: Path to Vosk model directory
    
    Returns:
        Vosk Model instance or None if failed
    """
    print(f"[Vosk] Loading model from: {model_path}")
    
    try:
        from vosk import Model
        
        if not Path(model_path).exists():
            print(f"[Vosk] Model path does not exist: {model_path}")
            return None
        
        model = Model(model_path)
        
        print("[Vosk] Model loaded successfully")
        return model
    
    except ImportError:
        print("[Vosk] ERROR: vosk package not installed")
        print("       Install with: pip install vosk")
        return None
    except Exception as e:
        print(f"[Vosk] Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return None


def recognition_worker_vosk(vosk_tool):
    """
    Worker thread for Vosk recognition
    
    Args:
        vosk_tool: VoskTool instance with _vosk_model, _raw_queue, _text_queue
    """
    from vosk import KaldiRecognizer
    
    model = vosk_tool._vosk_model
    
    if not model:
        print("[Vosk Worker] No model available")
        return
    
    print("[Vosk Worker] CPU recognition worker started")
    
    try:
        recognizer = KaldiRecognizer(model, SAMPLERATE)
        recognizer.SetWords(True)
    except Exception as e:
        print(f"[Vosk Worker] Failed to create recognizer: {e}")
        return
    
    while vosk_tool._voice_enabled:
        try:
            data = vosk_tool._raw_queue.get(timeout=0.5)
            
            if data == b"__EXIT__":
                print("[Vosk Worker] Exit signal received")
                break
            
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                
                if text and len(text) >= 3:
                    try:
                        vosk_tool._text_queue.put_nowait(text)
                        print(f"[Vosk Worker] Recognized: '{text}'")
                    except queue.Full:
                        try:
                            vosk_tool._text_queue.get_nowait()
                            vosk_tool._text_queue.put_nowait(text)
                        except:
                            pass
            else:
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get("partial", "")
                if partial_text:
                    pass
        
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[Vosk Worker] Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("[Vosk Worker] Recognition worker stopped")


def audio_callback_vosk(indata, frames, time_info, status, raw_queue):
    """
    Audio input callback for sounddevice stream
    
    Args:
        indata: Audio input data
        frames: Number of frames
        time_info: Time information
        status: Stream status
        raw_queue: Queue to push audio data to
    """
    if status:
        print(f"[Vosk Audio] Status: {status}")
    
    audio_bytes = bytes(indata)
    
    try:
        raw_queue.put_nowait(audio_bytes)
    except queue.Full:
        pass


def start_audio_stream(vosk_tool):
    """
    Start audio input stream for Vosk
    
    Args:
        vosk_tool: VoskTool instance with _raw_queue
    
    Returns:
        sounddevice RawInputStream
    """
    PREFERRED_DEVICES = [1, 12, 29, 35]
    audio_device = None
    
    print("[Vosk Audio] Testing audio devices...")
    
    for device_idx in PREFERRED_DEVICES:
        try:
            device_info = sd.query_devices(device_idx)
            device_name = device_info['name']
            
            if 'cable' in device_name.lower() or 'vb-audio' in device_name.lower():
                continue
            
            print(f"[Vosk Audio] Testing device {device_idx}: {device_name}...")
            
            test_stream = sd.RawInputStream(
                samplerate=SAMPLERATE,
                blocksize=2048,
                dtype="int16",
                channels=1,
                device=device_idx
            )
            test_stream.close()
            
            audio_device = device_idx
            print(f"[Vosk Audio] Device {audio_device} works: {device_name}")
            break
            
        except Exception as e:
            print(f"[Vosk Audio] Device {device_idx} failed: {e}")
            continue
    
    if audio_device is None:
        print("[Vosk Audio] No working microphone found!")
        devices = sd.query_devices()
        print("\n[Vosk Audio] Available devices:")
        for idx, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"  [{idx}] {device['name']} (IN: {device['max_input_channels']} channels)")
        raise RuntimeError("No functional audio input device available")
    
    stream = sd.RawInputStream(
        samplerate=SAMPLERATE,
        blocksize=AUDIO_BLOCKSIZE,
        dtype="int16",
        channels=1,
        device=audio_device,
        callback=lambda indata, frames, time_info, status: audio_callback_vosk(
            indata, frames, time_info, status, vosk_tool._raw_queue
        ),
        latency='high'
    )
    
    stream.start()
    
    print(f"[Vosk Audio] Stream active (device={audio_device}, blocksize={AUDIO_BLOCKSIZE})")
    print("[Vosk Audio] Listening for speech...")
    
    return stream


def list_audio_devices():
    """List all available audio input devices"""
    print("\n[Vosk] Available Audio Devices:")
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"  [{idx}] {device['name']} (IN: {device['max_input_channels']} channels)")