# BASE/tools/internal/whisper/whisper_engine.py
"""
Whisper Engine - Self-contained Faster-Whisper implementation
Extracted from voice_to_text.py for modular architecture
"""
import os
import sys
import numpy as np
import threading
import sounddevice as sd
import queue
import time
from pathlib import Path


def setup_cuda_path():
    """Add nvidia CUDA libraries to system PATH"""
    try:
        site_packages = None
        for path in sys.path:
            if 'site-packages' in path and os.path.exists(path):
                site_packages = Path(path)
                break

        if site_packages:
            nvidia_dirs = [
                site_packages / "nvidia" / "cublas" / "bin",
                site_packages / "nvidia" / "cudnn" / "bin",
                site_packages / "nvidia" / "cuda_runtime" / "bin",
            ]

            for cuda_dir in nvidia_dirs:
                if cuda_dir.exists():
                    cuda_dir_str = str(cuda_dir)
                    if cuda_dir_str not in os.environ.get('PATH', ''):
                        os.environ['PATH'] = cuda_dir_str + os.pathsep + os.environ.get('PATH', '')
    except:
        pass

setup_cuda_path()

from faster_whisper import WhisperModel

SAMPLERATE = 16000
AUDIO_BLOCKSIZE = 16384
QUEUE_MAX_SIZE = 50
AUDIO_CHUNK_DURATION = 4.0

GPU_CONFIG = {
    'model_size': 'small',
    'compute_type': 'int8',
    'device': 'cuda',
    'beam_size': 5,
}


_WHISPER_MODEL_INSTANCE: WhisperModel | None = None
_WHISPER_MODEL_LOCK = threading.Lock()

_SINGLETON_KEY = "BASE.tools.internal.whisper._model_singleton"


def load_whisper_model() -> WhisperModel | None:
    """
    Load Faster-Whisper model — process-wide singleton.
    Safe against repeated importlib loads under different module names.

    Returns:
        WhisperModel instance or None if failed
    """
    import sys

    existing = sys.modules.get(_SINGLETON_KEY)
    if existing is not None:
        print("[Whisper] Reusing existing model instance")
        return existing

    global _WHISPER_MODEL_LOCK

    with _WHISPER_MODEL_LOCK:
        existing = sys.modules.get(_SINGLETON_KEY)
        if existing is not None:
            return existing

        print("[Whisper] Loading Faster-Whisper (SMALL, int8)...")

        try:
            model = WhisperModel(
                GPU_CONFIG['model_size'],
                device=GPU_CONFIG['device'],
                compute_type=GPU_CONFIG['compute_type']
            )

            print("[Whisper] Warming up model...")

            warmup_audio = np.zeros(SAMPLERATE, dtype=np.float32)
            segments, _ = model.transcribe(
                warmup_audio,
                language='en',
                beam_size=GPU_CONFIG['beam_size'],
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200
                )
            )
            list(segments)

            print("[Whisper] Model ready")

            sys.modules[_SINGLETON_KEY] = model
            return model

        except Exception as e:
            print(f"[Whisper] Failed to load model: {e}")
            import traceback
            traceback.print_exc()
            return None


def recognition_worker_whisper(whisper_tool):
    """Worker thread for processing audio chunks"""
    model = whisper_tool._whisper_model

    if not model:
        print("[Whisper Worker] [ERROR] No model available - exiting")
        return

    import time
    time.sleep(2.0)
    initial_queue_size = whisper_tool._raw_queue.qsize()
    print(f"[Whisper Worker] Initial queue size after 2s: {initial_queue_size}")

    if initial_queue_size == 0:
        print("[Whisper Worker] [WARNING] No audio data in queue - microphone may not be working")

    print(f"[Whisper Worker] Starting with model: {type(model)}")
    print(f"[Whisper Worker] Voice enabled: {whisper_tool._voice_enabled}")
    print(f"[Whisper Worker] Queue size: {whisper_tool._raw_queue.qsize()}")

    accumulated_audio = []
    accumulated_duration = 0.0

    chunks_received = 0
    last_log_time = time.time()

    print("[Whisper Worker] GPU recognition thread started")

    while whisper_tool._voice_enabled:
        try:
            audio_chunk = whisper_tool._raw_queue.get(timeout=0.5)

            if isinstance(audio_chunk, bytes) and audio_chunk == b"__EXIT__":
                print("[Whisper Worker] Exit signal received")
                break

            if not hasattr(audio_chunk, 'shape'):
                print(f"[Whisper Worker] [WARNING] Invalid audio chunk type: {type(audio_chunk)}")
                continue

            chunks_received += 1
            current_time = time.time()

            max_amplitude = np.max(np.abs(audio_chunk))

            if chunks_received % 30 == 0 or (current_time - last_log_time) > 5.0:
                # print(f"[Whisper Worker] Chunks: {chunks_received}, "
                #       f"Queue: {whisper_tool._raw_queue.qsize()}, "
                #       f"Audio level: {max_amplitude:.4f}, "
                #       f"Accumulated: {accumulated_duration:.1f}s")
                last_log_time = current_time

            if max_amplitude < 0.001:
                if chunks_received % 100 == 0:
                    print(f"[Whisper Worker] [WARNING] Very quiet audio: {max_amplitude}")

            accumulated_audio.append(audio_chunk)
            accumulated_duration += len(audio_chunk) / SAMPLERATE

            if accumulated_duration >= AUDIO_CHUNK_DURATION:
                audio_data = np.concatenate(accumulated_audio)

                # print(f"[Whisper Worker] Transcribing {len(audio_data)} samples "
                #       f"({accumulated_duration:.1f}s, level: {np.max(np.abs(audio_data)):.4f})")

                start_time = time.time()

                segments, info = model.transcribe(
                    audio_data,
                    language='en',
                    beam_size=GPU_CONFIG['beam_size'],
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=500,
                        speech_pad_ms=200
                    )
                )

                elapsed = time.time() - start_time

                segment_count = 0
                for segment in segments:
                    segment_count += 1
                    text = segment.text.strip()

                    if text:
                        print(f"[Whisper Worker] Recognized: '{text}' "
                              f"(confidence: {segment.avg_logprob:.2f}, {elapsed:.2f}s)")
                        try:
                            whisper_tool._text_queue.put_nowait(text)

                            if whisper_tool._use_speaker_verification and whisper_tool._audio_segment_queue:
                                whisper_tool._audio_segment_queue.put_nowait({
                                    'audio': audio_data,
                                    'sample_rate': SAMPLERATE
                                })
                        except queue.Full:
                            print("[Whisper Worker] [WARNING] Text/audio queue full")

                # if segment_count == 0:
                #     print(f"[Whisper Worker] No speech detected in {accumulated_duration:.1f}s of audio")

                accumulated_audio = []
                accumulated_duration = 0.0

        except queue.Empty:
            current_time = time.time()
            if (current_time - last_log_time) > 10.0:
                print(f"[Whisper Worker] Still running... (chunks: {chunks_received}, "
                      f"voice_enabled: {whisper_tool._voice_enabled})")
                last_log_time = current_time
            continue
        except Exception as e:
            print(f"[Whisper Worker] [ERROR] {e}")
            import traceback
            traceback.print_exc()

    print(f"[Whisper Worker] Thread stopped (processed {chunks_received} chunks, "
          f"voice_enabled={whisper_tool._voice_enabled})")


def audio_callback_whisper(indata, frames, time_info, status, raw_queue):
    """
    Audio input callback for sounddevice stream

    Args:
        indata: Audio input data (2D array: shape=(frames, channels))
        frames: Number of frames
        time_info: Time information
        status: Stream status
        raw_queue: Queue to push audio data to
    """
    if status:
        print(f"[Whisper Audio] Status: {status}")

    audio_chunk = indata[:, 0].copy() if indata.ndim == 2 else indata.copy()

    try:
        raw_queue.put_nowait(audio_chunk)
    except queue.Full:
        print("[Whisper Audio] [Warning] Queue full - dropping audio chunk")


def start_audio_stream(whisper_tool):
    """
    Start audio input stream with device selection

    Args:
        whisper_tool: WhisperTool instance with _raw_queue

    Returns:
        sounddevice InputStream
    """
    import sounddevice as sd

    PREFERRED_DEVICES = [1, 12, 29, 35]
    audio_device = None

    print("[Whisper Audio] Testing audio devices...")

    for device_idx in PREFERRED_DEVICES:
        try:
            device_info = sd.query_devices(device_idx)
            device_name = device_info['name']

            if 'cable' in device_name.lower() or 'vb-audio' in device_name.lower():
                print(f"[Whisper Audio] Skipping virtual device {device_idx}: {device_name}")
                continue

            print(f"[Whisper Audio] Testing device {device_idx}: {device_name}...")

            test_stream = sd.InputStream(
                samplerate=SAMPLERATE,
                blocksize=2048,
                dtype=np.float32,
                channels=1,
                device=device_idx
            )
            test_stream.close()

            audio_device = device_idx
            print(f"[Whisper Audio] [SUCCESS] Using device {audio_device}: {device_name}")
            break

        except Exception as e:
            print(f"[Whisper Audio] Device {device_idx} failed: {e}")
            continue

    if audio_device is None:
        print("[Whisper Audio] No preferred device found, searching all devices...")
        devices = sd.query_devices()

        for idx, device in enumerate(devices):
            if device['max_input_channels'] == 0:
                continue

            device_name = device['name']
            if 'cable' in device_name.lower() or 'vb-audio' in device_name.lower():
                continue

            try:
                print(f"[Whisper Audio] Testing device {idx}: {device_name}...")
                test_stream = sd.InputStream(
                    samplerate=SAMPLERATE,
                    blocksize=2048,
                    dtype=np.float32,
                    channels=1,
                    device=idx
                )
                test_stream.close()

                audio_device = idx
                print(f"[Whisper Audio] [SUCCESS] Using device {audio_device}: {device_name}")
                break
            except Exception as e:
                print(f"[Whisper Audio] Device {idx} failed: {e}")
                continue

    if audio_device is None:
        print("[Whisper Audio] [ERROR] No working microphone found!")
        print("[Whisper Audio] Available devices:")
        list_audio_devices()
        raise RuntimeError("No functional audio input device available")

    print(f"[Whisper Audio] Creating stream (device={audio_device}, "
          f"rate={SAMPLERATE}, blocksize={AUDIO_BLOCKSIZE})...")

    stream = sd.InputStream(
        samplerate=SAMPLERATE,
        channels=1,
        dtype=np.float32,
        blocksize=AUDIO_BLOCKSIZE,
        device=audio_device,
        callback=lambda indata, frames, time_info, status: audio_callback_whisper(
            indata, frames, time_info, status, whisper_tool._raw_queue
        ),
        latency='high'
    )

    stream.start()

    print(f"[Whisper Audio] [SUCCESS] Stream started and active")

    return stream


def list_audio_devices():
    """List all available audio input devices"""
    import sounddevice as sd

    print("[Whisper Audio] Available input devices:")
    devices = sd.query_devices()
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"  [{idx}] {device['name']} "
                  f"(IN: {device['max_input_channels']} channels, "
                  f"Rate: {device['default_samplerate']} Hz)")