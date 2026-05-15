#!/usr/bin/env python3
"""
Optimized Voice Sample Recorder for Speaker Verification
Records high-quality voice sample with varied speech patterns for maximum accuracy
"""
import sounddevice as sd
import soundfile as sf
import numpy as np
import time
from pathlib import Path

SAMPLE_RATE = 22050
RECORDING_DURATION = 10
COUNTDOWN_SECONDS = 3

OPTIMAL_SCRIPT = """
Hello, my name is {username} and this is my voice authentication sample.
I'm recording this to train the speaker verification system.
The quick brown fox jumps over the lazy dog.
She sells seashells by the seashore.
How much wood would a woodchuck chuck if a woodchuck could chuck wood?
Peter Piper picked a peck of pickled peppers.
I need to speak clearly and naturally for accurate voice recognition.
This sample includes various sounds and speech patterns.
My unique voice characteristics will be used for identification.
Thank you for listening to my voice sample recording.
"""

def print_banner():
    """Print welcome banner"""
    print("=" * 70)
    print(" " * 15 + "VOICE SAMPLE RECORDER")
    print(" " * 10 + "Speaker Verification System")
    print("=" * 70)
    print()

def check_audio_devices():
    """Display available audio input devices"""
    print("[INFO] Checking audio devices...")
    devices = sd.query_devices()
    
    input_devices = []
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            input_devices.append((idx, device))
    
    if not input_devices:
        print("[ERROR] No input devices found!")
        return None
    
    print("\n[AVAILABLE INPUT DEVICES]")
    for idx, device in input_devices:
        default_marker = " (DEFAULT)" if idx == sd.default.device[0] else ""
        print(f"  [{idx}] {device['name']}{default_marker}")
        print(f"      Channels: {device['max_input_channels']}, "
              f"Sample Rate: {device['default_samplerate']} Hz")
    
    print()
    return input_devices

def select_device(input_devices):
    """Let user select input device"""
    if len(input_devices) == 1:
        device_idx = input_devices[0][0]
        device_name = input_devices[0][1]['name']
        print(f"[AUTO] Using only available device: {device_name}")
        return device_idx
    
    default_device = sd.default.device[0]
    
    while True:
        response = input(f"Select device index (press Enter for default [{default_device}]): ").strip()
        
        if response == "":
            return default_device
        
        try:
            device_idx = int(response)
            if any(idx == device_idx for idx, _ in input_devices):
                return device_idx
            else:
                print(f"[ERROR] Invalid device index. Choose from available devices.")
        except ValueError:
            print("[ERROR] Please enter a number.")

def test_audio_level(device_idx, duration=3):
    """Test microphone audio levels"""
    print(f"\n[AUDIO TEST] Recording {duration} seconds to check levels...")
    print("[AUDIO TEST] Speak normally into the microphone...")
    print()
    
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='float32',
        device=device_idx
    )
    
    for i in range(duration):
        print(f"  Recording test... {i+1}/{duration} seconds", end='\r')
        time.sleep(1)
    
    sd.wait()
    print()
    
    max_amplitude = np.max(np.abs(audio))
    rms_level = np.sqrt(np.mean(audio**2))
    
    print(f"[AUDIO TEST] Peak level: {max_amplitude:.3f}")
    print(f"[AUDIO TEST] RMS level: {rms_level:.3f}")
    
    if max_amplitude < 0.01:
        print("[WARNING] Audio level very low - check microphone connection/volume")
        return False
    elif max_amplitude > 0.95:
        print("[WARNING] Audio level too high - reduce microphone gain to avoid clipping")
        return False
    elif max_amplitude < 0.1:
        print("[WARNING] Audio level low - consider speaking louder or increasing mic gain")
        return True
    else:
        print("[SUCCESS] Audio levels good!")
        return True

def get_username():
    """Get username from bot_info or user input"""
    try:
        from BASE.config.bot_info import username
        print(f"[INFO] Detected username from bot_info: {username}")
        confirm = input(f"Use '{username}' as username? (Y/n): ").strip().lower()
        
        if confirm in ('', 'y', 'yes'):
            return username
    except ImportError:
        print("[INFO] Could not import username from BASE.config.bot_info")
    
    while True:
        username = input("Enter username for voice sample: ").strip()
        if username:
            return username
        print("[ERROR] Username cannot be empty")

def display_script(username):
    """Display optimized recording script"""
    script = OPTIMAL_SCRIPT.format(username=username)
    
    print("\n" + "=" * 70)
    print(" " * 20 + "RECORDING SCRIPT")
    print("=" * 70)
    print("\n[INSTRUCTIONS]")
    print("  - Read the following text naturally and clearly")
    print("  - Speak at your normal pace and volume")
    print("  - Try to include natural intonation and emotion")
    print("  - Don't rush - clarity is more important than speed")
    print("  - The script is designed to capture diverse speech patterns")
    print()
    print("[SCRIPT]")
    print("-" * 70)
    print(script)
    print("-" * 70)
    print()

def countdown(seconds):
    """Countdown before recording"""
    for i in range(seconds, 0, -1):
        print(f"  Starting in {i}...", end='\r')
        time.sleep(1)
    print("  [RECORDING NOW!]     ")

def record_voice_sample(device_idx, duration):
    """Record the voice sample"""
    print(f"\n[RECORDING] Duration: {duration} seconds")
    print("[RECORDING] Speak now!")
    print()
    
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16',
        device=device_idx
    )
    
    for i in range(duration):
        progress = int((i / duration) * 50)
        bar = '█' * progress + '░' * (50 - progress)
        elapsed = i + 1
        print(f"  [{bar}] {elapsed}/{duration}s", end='\r')
        time.sleep(1)
    
    sd.wait()
    print(f"  [{'█' * 50}] {duration}/{duration}s - COMPLETE!")
    print()
    
    return audio

def analyze_recording(audio, sample_rate):
    """Analyze recording quality"""
    print("[ANALYSIS] Checking recording quality...")
    
    audio_float = audio.astype(np.float32) / 32768.0
    
    max_amplitude = np.max(np.abs(audio_float))
    rms_level = np.sqrt(np.mean(audio_float**2))
    
    silence_threshold = 0.01
    non_silent_samples = np.sum(np.abs(audio_float) > silence_threshold)
    speech_percentage = (non_silent_samples / len(audio_float)) * 100
    
    clipped_samples = np.sum(np.abs(audio) >= 32767)
    clipping_percentage = (clipped_samples / len(audio)) * 100
    
    print(f"  Peak amplitude: {max_amplitude:.3f}")
    print(f"  RMS level: {rms_level:.3f}")
    print(f"  Speech content: {speech_percentage:.1f}%")
    print(f"  Clipping: {clipping_percentage:.2f}%")
    
    quality_ok = True
    warnings = []
    
    if max_amplitude < 0.1:
        warnings.append("Recording very quiet - may affect accuracy")
        quality_ok = False
    
    if clipping_percentage > 1.0:
        warnings.append("Significant clipping detected - reduce microphone gain")
        quality_ok = False
    
    if speech_percentage < 40:
        warnings.append("Low speech content - ensure you spoke during recording")
        quality_ok = False
    
    if warnings:
        print("\n[WARNINGS]")
        for warning in warnings:
            print(f"  [Warning] {warning}")
    else:
        print("\n[SUCCESS] Recording quality is good!")
    
    print()
    return quality_ok

def play_recording(audio, sample_rate):
    """Play back the recording"""
    response = input("Play back recording? (Y/n): ").strip().lower()
    
    if response in ('', 'y', 'yes'):
        print("\n[PLAYBACK] Playing recording...")
        sd.play(audio, sample_rate)
        sd.wait()
        print("[PLAYBACK] Complete")
        print()

def save_recording(audio, sample_rate, username):
    """Save recording to file"""
    output_dir = Path('./personality/voice')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{username}_voice_sample.mp3"
    
    if output_path.exists():
        print(f"[WARNING] File already exists: {output_path}")
        response = input("Overwrite existing file? (y/N): ").strip().lower()
        
        if response not in ('y', 'yes'):
            print("[CANCELLED] Existing file not overwritten")
            return None
    
    sf.write(str(output_path), audio, sample_rate)
    
    file_size = output_path.stat().st_size
    duration = len(audio) / sample_rate
    
    print()
    print("[SUCCESS] Voice sample saved!")
    print(f"  Location: {output_path}")
    print(f"  Size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
    print(f"  Duration: {duration:.1f} seconds")
    print(f"  Sample Rate: {sample_rate} Hz")
    print(f"  Format: 16-bit PCM WAV (mono)")
    print()
    
    return output_path

def verify_file_compatibility(output_path):
    """Verify file is compatible with speaker verification system"""
    print("[VERIFICATION] Checking file compatibility...")
    
    try:
        data, sr = sf.read(str(output_path))
        
        checks = {
            "Sample rate is 22050 Hz": sr == 22050,
            "File is mono": len(data.shape) == 1 or data.shape[1] == 1,
            "Duration >= 3 seconds": len(data) / sr >= 3,
            "Duration <= 30 seconds": len(data) / sr <= 30,
            "File readable": True
        }
        
        all_passed = all(checks.values())
        
        for check, passed in checks.items():
            status = "[PASS]" if passed else "[FAIL]"
            print(f"  {status} {check}")
        
        print()
        
        if all_passed:
            print("[SUCCESS] File is compatible with speaker verification system!")
        else:
            print("[WARNING] File may have compatibility issues")
        
        return all_passed
    
    except Exception as e:
        print(f"[ERROR] Could not verify file: {e}")
        return False

def main():
    """Main recording workflow"""
    print_banner()
    
    print("[STEP 1] Audio Device Setup")
    print("-" * 70)
    input_devices = check_audio_devices()
    
    if not input_devices:
        return
    
    device_idx = select_device(input_devices)
    device_name = sd.query_devices(device_idx)['name']
    print(f"[SELECTED] {device_name}")
    print()
    
    print("[STEP 2] Audio Level Test")
    print("-" * 70)
    level_ok = test_audio_level(device_idx)
    
    if not level_ok:
        response = input("\nContinue anyway? (y/N): ").strip().lower()
        if response not in ('y', 'yes'):
            print("[CANCELLED] Recording cancelled")
            return
    
    print()
    print("[STEP 3] Username Configuration")
    print("-" * 70)
    username = get_username()
    
    print()
    print("[STEP 4] Review Recording Script")
    print("-" * 70)
    display_script(username)
    
    input("Press Enter when ready to record...")
    
    while True:
        print()
        print("[STEP 5] Recording")
        print("-" * 70)
        countdown(COUNTDOWN_SECONDS)
        
        audio = record_voice_sample(device_idx, RECORDING_DURATION)
        
        quality_ok = analyze_recording(audio, SAMPLE_RATE)
        
        play_recording(audio, SAMPLE_RATE)
        
        if quality_ok:
            response = input("Accept this recording? (Y/n): ").strip().lower()
            if response in ('', 'y', 'yes'):
                break
        else:
            response = input("Recording quality is low. Re-record? (Y/n): ").strip().lower()
            if response not in ('', 'y', 'yes'):
                response2 = input("Save anyway? (y/N): ").strip().lower()
                if response2 in ('y', 'yes'):
                    break
                else:
                    print("[CANCELLED] Recording cancelled")
                    return
        
        print("\n[INFO] Preparing to re-record...")
        input("Press Enter when ready...")
    
    print()
    print("[STEP 6] Saving Recording")
    print("-" * 70)
    output_path = save_recording(audio, SAMPLE_RATE, username)
    
    if output_path:
        verify_file_compatibility(output_path)
        
        print("=" * 70)
        print(" " * 15 + "RECORDING COMPLETE!")
        print("=" * 70)
        print()
        print("[NEXT STEPS]")
        print("  1. Enable speaker verification in personality/controls.py:")
        print("     USE_SPEAKER_VERIFICATION = True")
        print("     SPEAKER_VERIFICATION_THRESHOLD = 0.75")
        print()
        print("  2. Restart the AI agent")
        print()
        print("  3. Test voice commands - only your voice should be recognized")
        print()
        print("  4. If experiencing false rejects, lower threshold to 0.70 or 0.65")
        print("     If experiencing false accepts, raise threshold to 0.80 or 0.85")
        print()
        print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Recording cancelled by user")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()