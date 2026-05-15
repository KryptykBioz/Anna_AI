#!/usr/bin/env python3
"""
Guided Voice Sample Recorder with Optimal Text Prompts
Records voice sample with prompts designed to maximize speaker verification accuracy
"""
import sounddevice as sd
import soundfile as sf
import numpy as np
import time
from pathlib import Path

SAMPLE_RATE = 22050

PROMPT_SETS = {
    "standard": {
        "duration": 10,
        "prompts": [
            "Hello, I am recording my voice sample for authentication.",
            "The quick brown fox jumps over the lazy dog.",
            "I enjoy using voice commands to control my AI assistant.",
            "This sample captures my unique vocal characteristics.",
            "Numbers: one, two, three, four, five, six, seven, eight, nine, ten.",
            "My voice is being analyzed for speaker verification.",
            "Thank you for listening to this recording."
        ]
    },
    "comprehensive": {
        "duration": 15,
        "prompts": [
            "Hello, my name is {username} and this is my voice authentication.",
            "The quick brown fox jumps over the lazy dog.",
            "She sells seashells by the seashore on sunny summer days.",
            "How much wood would a woodchuck chuck if a woodchuck could chuck wood?",
            "Peter Piper picked a peck of pickled peppers from the pantry.",
            "I need to speak clearly and naturally for accurate recognition.",
            "This recording includes various phonetic sounds and speech patterns.",
            "Numbers: zero, one, two, three, four, five, six, seven, eight, nine.",
            "My unique voice characteristics will identify me reliably.",
            "Artificial intelligence and machine learning are fascinating technologies.",
            "I enjoy reading books, watching movies, and listening to music.",
            "The weather today is beautiful with clear blue skies.",
            "Thank you very much for your attention to this voice sample."
        ]
    },
    "phonetic": {
        "duration": 12,
        "prompts": [
            "Hello, this is my voice verification sample.",
            "Alpha, Bravo, Charlie, Delta, Echo, Foxtrot, Golf.",
            "The five boxing wizards jump quickly through the maze.",
            "Pack my box with five dozen liquor jugs for the party.",
            "Sphinx of black quartz, judge my vow for authenticity.",
            "How vexingly quick daft zebras jump over the moon.",
            "Crazy Frederick bought many very exquisite opal jewels.",
            "The job requires extra pluck and zeal from every young wage earner.",
            "My voice has unique features that distinguish it from others.",
            "Thank you for recording this phonetically diverse sample."
        ]
    },
    "conversational": {
        "duration": 10,
        "prompts": [
            "Hi there, I'm setting up voice authentication today.",
            "I think it's really cool that AI can recognize individual voices.",
            "My favorite foods are pizza, sushi, and chocolate ice cream.",
            "I usually wake up around seven in the morning on weekdays.",
            "The weather has been quite unpredictable lately, hasn't it?",
            "I enjoy listening to music while working on my computer.",
            "Sometimes I wonder what technology will be like in twenty years.",
            "This voice sample will help the system recognize me accurately.",
            "Alright, I think that should be enough for the recording."
        ]
    }
}

def print_header():
    """Print script header"""
    print("=" * 70)
    print(" " * 12 + "GUIDED VOICE SAMPLE RECORDER")
    print(" " * 15 + "With Optimal Text Prompts")
    print("=" * 70)
    print()

def select_prompt_set():
    """Let user select which prompt set to use"""
    print("[PROMPT SET SELECTION]")
    print()
    
    sets = {
        "1": ("standard", "Balanced prompts for general use (10 sec)"),
        "2": ("comprehensive", "Extensive prompts for maximum accuracy (15 sec)"),
        "3": ("phonetic", "Phonetically diverse tongue-twisters (12 sec)"),
        "4": ("conversational", "Natural conversational speech (10 sec)")
    }
    
    for key, (name, desc) in sets.items():
        print(f"  [{key}] {desc}")
    
    print()
    
    while True:
        choice = input("Select prompt set (1-4, default 1): ").strip()
        
        if choice == "":
            choice = "1"
        
        if choice in sets:
            set_name = sets[choice][0]
            print(f"[SELECTED] {sets[choice][1]}")
            return set_name
        else:
            print("[ERROR] Invalid selection. Choose 1-4.")

def get_username():
    """Get username"""
    try:
        from BASE.config.bot_info import username
        print(f"\n[INFO] Detected username: {username}")
        return username
    except ImportError:
        username = input("\nEnter username: ").strip()
        return username if username else "user"

def display_prompts(prompts, username):
    """Display prompts to user"""
    print("\n" + "=" * 70)
    print(" " * 22 + "RECORDING PROMPTS")
    print("=" * 70)
    print()
    print("[INSTRUCTIONS]")
    print("  - ALL prompts will be shown on screen during recording")
    print("  - Read them in order at your own comfortable pace")
    print("  - You have the full duration to speak all prompts")
    print("  - Speak naturally with normal intonation and emotion")
    print("  - Pause briefly between prompts as needed")
    print()
    print("[PROMPTS PREVIEW]")
    print("-" * 70)
    
    for i, prompt in enumerate(prompts, 1):
        formatted = prompt.format(username=username)
        print(f"{i:2d}. {formatted}")
    
    print("-" * 70)
    print()
    print("[NOTE] These prompts will appear again during recording")
    print()

def guided_recording(device_idx, prompts, username, duration):
    """Record with on-screen prompt guidance"""
    print(f"\n[RECORDING] Total duration: {duration} seconds")
    print("[INFO] Recording will start after countdown")
    print("[INFO] Read prompts at your own pace - there's plenty of time")
    print()
    
    input("Press Enter to start countdown...")
    print()
    
    for i in range(3, 0, -1):
        print(f"Starting in {i}...", end='\r')
        time.sleep(1)
    
    print("[RECORDING NOW - Speak the prompts below]                    ")
    print("=" * 70)
    
    for i, prompt in enumerate(prompts, 1):
        formatted = prompt.format(username=username)
        print(f"{i:2d}. {formatted}")
    
    print("=" * 70)
    print()
    print("[TIP] Read naturally - you have the full duration to speak all prompts")
    print()
    
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16',
        device=device_idx
    )
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time
        remaining = duration - elapsed
        progress_pct = (elapsed / duration) * 100
        
        bar_length = 50
        filled = int(bar_length * progress_pct / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"[{bar}] {int(elapsed)}/{duration}s - {int(remaining)}s remaining", end='\r')
        
        time.sleep(0.1)
    
    sd.wait()
    
    print(f"\n[{'█' * 50}] {duration}/{duration}s - COMPLETE!                    ")
    print()
    
    return audio

def select_device():
    """Select audio input device"""
    devices = sd.query_devices()
    input_devices = [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0]
    
    if not input_devices:
        print("[ERROR] No input devices found")
        return None
    
    if len(input_devices) == 1:
        device_idx = input_devices[0][0]
        print(f"[AUTO] Using: {input_devices[0][1]['name']}")
        return device_idx
    
    print("\n[INPUT DEVICES]")
    for idx, device in input_devices:
        default = " (DEFAULT)" if idx == sd.default.device[0] else ""
        print(f"  [{idx}] {device['name']}{default}")
    
    print()
    
    while True:
        choice = input(f"Select device (default {sd.default.device[0]}): ").strip()
        
        if choice == "":
            return sd.default.device[0]
        
        try:
            device_idx = int(choice)
            if any(idx == device_idx for idx, _ in input_devices):
                return device_idx
        except ValueError:
            pass
        
        print("[ERROR] Invalid device")

def analyze_quality(audio, sample_rate):
    """Analyze recording quality"""
    audio_float = audio.astype(np.float32) / 32768.0
    
    max_amp = np.max(np.abs(audio_float))
    rms = np.sqrt(np.mean(audio_float**2))
    
    silence_threshold = 0.01
    speech_pct = (np.sum(np.abs(audio_float) > silence_threshold) / len(audio_float)) * 100
    
    clipping_pct = (np.sum(np.abs(audio) >= 32767) / len(audio)) * 100
    
    print("[QUALITY ANALYSIS]")
    print(f"  Peak level: {max_amp:.3f} {'[TOO LOW]' if max_amp < 0.1 else '[TOO HIGH]' if max_amp > 0.95 else '[GOOD]'}")
    print(f"  RMS level: {rms:.3f}")
    print(f"  Speech content: {speech_pct:.1f}% {'[LOW]' if speech_pct < 40 else '[GOOD]'}")
    print(f"  Clipping: {clipping_pct:.2f}% {'[HIGH]' if clipping_pct > 1 else '[NONE]'}")
    
    return max_amp >= 0.1 and clipping_pct < 1.0 and speech_pct >= 40

def save_sample(audio, sample_rate, username):
    """Save voice sample"""
    output_dir = Path('./personality/voice')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{username}_voice_sample.mp3"
    
    if output_path.exists():
        response = input(f"\n[WARNING] {output_path} exists. Overwrite? (y/N): ").strip().lower()
        if response not in ('y', 'yes'):
            return None
    
    sf.write(str(output_path), audio, sample_rate)
    
    print()
    print("[SUCCESS] Voice sample saved!")
    print(f"  Path: {output_path}")
    print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")
    print(f"  Duration: {len(audio) / sample_rate:.1f} seconds")
    print()
    
    return output_path

def main():
    """Main workflow"""
    print_header()
    
    prompt_set_name = select_prompt_set()
    prompt_set = PROMPT_SETS[prompt_set_name]
    
    username = get_username()
    
    display_prompts(prompt_set["prompts"], username)
    
    input("Press Enter when ready to continue...")
    
    device_idx = select_device()
    if device_idx is None:
        return
    
    while True:
        audio = guided_recording(
            device_idx,
            prompt_set["prompts"],
            username,
            prompt_set["duration"]
        )
        
        quality_ok = analyze_quality(audio, SAMPLE_RATE)
        
        print()
        response = input("Listen to playback? (Y/n): ").strip().lower()
        if response in ('', 'y', 'yes'):
            print("[PLAYBACK] Playing...")
            sd.play(audio, SAMPLE_RATE)
            sd.wait()
            print("[PLAYBACK] Done")
        
        print()
        if quality_ok:
            response = input("Accept recording? (Y/n): ").strip().lower()
            if response in ('', 'y', 'yes'):
                break
        else:
            print("[WARNING] Quality issues detected")
            response = input("Re-record? (Y/n): ").strip().lower()
            if response not in ('', 'y', 'yes'):
                response2 = input("Save anyway? (y/N): ").strip().lower()
                if response2 in ('y', 'yes'):
                    break
                else:
                    print("[CANCELLED]")
                    return
        
        print("\n[INFO] Preparing to re-record...")
        input("Press Enter when ready...")
    
    output_path = save_sample(audio, SAMPLE_RATE, username)
    
    if output_path:
        print("=" * 70)
        print(" " * 20 + "SETUP COMPLETE!")
        print("=" * 70)
        print()
        print("[NEXT STEPS]")
        print("  1. Add to personality/controls.py:")
        print("       USE_SPEAKER_VERIFICATION = True")
        print("       SPEAKER_VERIFICATION_THRESHOLD = 0.75")
        print()
        print("  2. Restart your AI agent")
        print()
        print("  3. Test with voice commands")
        print()
        print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[CANCELLED]")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()