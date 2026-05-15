#!/usr/bin/env python3
"""
Quick Voice Sample Recorder
Simple script for users who want minimal interaction
"""
import sounddevice as sd
import soundfile as sf
import numpy as np
import time
from pathlib import Path

SAMPLE_RATE = 22050
DURATION = 8

def quick_record():
    """Quick recording with minimal interaction"""
    try:
        from BASE.config.bot_info import username
        print(f"[INFO] Username: {username}")
    except ImportError:
        username = input("Enter username: ").strip()
        if not username:
            print("[ERROR] Username required")
            return
    
    output_dir = Path('./personality/voice')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{username}_voice_sample.mp3"
    
    if output_path.exists():
        response = input(f"[WARNING] {output_path} exists. Overwrite? (y/N): ").strip().lower()
        if response not in ('y', 'yes'):
            print("[CANCELLED]")
            return
    
    print(f"\n[READY] Recording {DURATION} seconds of audio")
    print("[INFO] Speak naturally - vary your tone and pace")
    print("[TIP] Read a paragraph from a book or describe your day")
    print()
    
    for i in range(3, 0, -1):
        print(f"Starting in {i}...", end='\r')
        time.sleep(1)
    
    print("[RECORDING NOW!]")
    print()
    
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16'
    )
    
    for i in range(DURATION):
        progress = '█' * (i + 1) + '░' * (DURATION - i - 1)
        print(f"[{progress}] {i+1}/{DURATION}s", end='\r')
        time.sleep(1)
    
    sd.wait()
    print(f"[{'█' * DURATION}] {DURATION}/{DURATION}s - DONE!")
    print()
    
    audio_float = audio.astype(np.float32) / 32768.0
    max_amp = np.max(np.abs(audio_float))
    
    if max_amp < 0.05:
        print(f"[WARNING] Very quiet recording (level: {max_amp:.3f})")
        print("[WARNING] Speak louder or increase microphone volume")
    elif max_amp > 0.95:
        print(f"[WARNING] Clipping detected (level: {max_amp:.3f})")
        print("[WARNING] Reduce microphone gain")
    else:
        print(f"[SUCCESS] Good audio level (peak: {max_amp:.3f})")
    
    sf.write(str(output_path), audio, SAMPLE_RATE)
    
    print()
    print(f"[SAVED] {output_path}")
    print(f"[SIZE] {output_path.stat().st_size / 1024:.1f} KB")
    print()
    print("[NEXT] Set USE_SPEAKER_VERIFICATION = True in controls.py")

if __name__ == "__main__":
    try:
        quick_record()
    except KeyboardInterrupt:
        print("\n[CANCELLED]")
    except Exception as e:
        print(f"[ERROR] {e}")