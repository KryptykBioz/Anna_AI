#!/usr/bin/env python3
"""
Interactive Prompt Recording - One Prompt at a Time
Records each prompt individually, then combines them into a single sample
"""
import sounddevice as sd
import soundfile as sf
import numpy as np
import time
from pathlib import Path

SAMPLE_RATE = 22050

PROMPT_SETS = {
    "standard": [
        "Hello, I am recording my voice sample for authentication.",
        "The quick brown fox jumps over the lazy dog.",
        "I enjoy using voice commands to control my AI assistant.",
        "This sample captures my unique vocal characteristics.",
        "Numbers: one, two, three, four, five, six, seven, eight, nine, ten.",
        "My voice is being analyzed for speaker verification.",
        "Thank you for listening to this recording."
    ],
    "comprehensive": [
        "Hello, my name is {username} and this is my voice authentication.",
        "The quick brown fox jumps over the lazy dog.",
        "She sells seashells by the seashore on sunny summer days.",
        "How much wood would a woodchuck chuck if a woodchuck could chuck wood?",
        "Peter Piper picked a peck of pickled peppers from the pantry.",
        "I need to speak clearly and naturally for accurate recognition.",
        "This recording includes various phonetic sounds and speech patterns.",
        "Numbers: zero, one, two, three, four, five, six, seven, eight, nine.",
        "My unique voice characteristics will identify me reliably.",
        "Thank you very much for your attention to this voice sample."
    ],
    "phonetic": [
        "Hello, this is my voice verification sample.",
        "Alpha, Bravo, Charlie, Delta, Echo, Foxtrot, Golf.",
        "The five boxing wizards jump quickly through the maze.",
        "Pack my box with five dozen liquor jugs for the party.",
        "Sphinx of black quartz, judge my vow for authenticity.",
        "How vexingly quick daft zebras jump over the moon.",
        "My voice has unique features that distinguish it from others.",
        "Thank you for recording this phonetically diverse sample."
    ],
    "conversational": [
        "Hi there, I'm setting up voice authentication today.",
        "I think it's really cool that AI can recognize individual voices.",
        "My favorite foods are pizza, sushi, and chocolate ice cream.",
        "The weather has been quite unpredictable lately, hasn't it?",
        "I enjoy listening to music while working on my computer.",
        "This voice sample will help the system recognize me accurately.",
        "Alright, I think that should be enough for the recording."
    ]
}

def print_header():
    """Print script header"""
    print("=" * 70)
    print(" " * 10 + "INTERACTIVE VOICE SAMPLE RECORDER")
    print(" " * 15 + "One Prompt at a Time")
    print("=" * 70)
    print()

def select_prompt_set():
    """Let user select which prompt set to use"""
    print("[PROMPT SET SELECTION]")
    print()
    
    sets = {
        "1": ("standard", "7 prompts - Balanced for general use"),
        "2": ("comprehensive", "10 prompts - Maximum accuracy"),
        "3": ("phonetic", "8 prompts - Phonetically diverse"),
        "4": ("conversational", "7 prompts - Natural speech")
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
        from personality.bot_info import username
        print(f"\n[INFO] Detected username: {username}")
        return username
    except ImportError:
        username = input("\nEnter username: ").strip()
        return username if username else "user"

def select_device():
    """Select audio input device"""
    devices = sd.query_devices()
    input_devices = [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0]
    
    if not input_devices:
        print("[ERROR] No input devices found")
        return None
    
    if len(input_devices) == 1:
        device_idx = input_devices[0][0]
        print(f"\n[AUTO] Using: {input_devices[0][1]['name']}")
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

def show_instructions(total_prompts):
    """Show recording instructions"""
    print("\n" + "=" * 70)
    print(" " * 20 + "HOW THIS WORKS")
    print("=" * 70)
    print()
    print(f"[INFO] You will record {total_prompts} prompts, one at a time")
    print()
    print("[WORKFLOW]")
    print("  1. A prompt will be displayed on screen")
    print("  2. Press Enter when ready to record that prompt")
    print("  3. Recording starts after 3-second countdown")
    print("  4. Speak the prompt clearly and naturally")
    print("  5. Recording stops automatically after you finish")
    print("  6. Repeat for each prompt")
    print("  7. All prompts are combined into one voice sample")
    print()
    print("[TIPS]")
    print("  - Take your time between prompts")
    print("  - Speak at your normal pace")
    print("  - Use natural intonation")
    print("  - No need to rush")
    print()
    print("=" * 70)
    print()
    input("Press Enter when ready to begin...")

def record_single_prompt(device_idx, prompt_text, prompt_num, total_prompts):
    """Record a single prompt"""
    print()
    print("=" * 70)
    print(f"PROMPT {prompt_num} of {total_prompts}")
    print("=" * 70)
    print()
    print(f">>> {prompt_text}")
    print()
    
    input("Press Enter when ready to record this prompt...")
    
    for i in range(3, 0, -1):
        print(f"  Recording in {i}...", end='\r')
        time.sleep(1)
    
    print("  [RECORDING - Speak now!]  ")
    
    duration = 5
    
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='float32',
        device=device_idx
    )
    
    start_time = time.time()
    last_print = 0
    
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time
        remaining = duration - elapsed
        
        if int(elapsed) > last_print:
            last_print = int(elapsed)
            bars = '█' * (last_print + 1) + '░' * (duration - last_print - 1)
            print(f"  [{bars}] {last_print + 1}/{duration}s", end='\r')
        
        time.sleep(0.1)
    
    sd.wait()
    print(f"  [{'█' * duration}] {duration}/{duration}s - Done!")
    
    # FIX: Flatten audio to 1D array
    audio = audio.flatten()
    
    silence_threshold = 0.01
    non_silent_samples = np.sum(np.abs(audio) > silence_threshold)
    speech_pct = (non_silent_samples / len(audio)) * 100
    
    if speech_pct < 20:
        print()
        print("  [WARNING] Very little speech detected")
        response = input("  Re-record this prompt? (Y/n): ").strip().lower()
        if response in ('', 'y', 'yes'):
            return record_single_prompt(device_idx, prompt_text, prompt_num, total_prompts)
    
    silence_start = None
    for i, sample in enumerate(audio):
        if abs(sample) > silence_threshold:
            silence_start = i
            break
    
    silence_end = None
    for i in range(len(audio) - 1, -1, -1):
        if abs(audio[i]) > silence_threshold:
            silence_end = i + 1
            break
    
    if silence_start is not None and silence_end is not None:
        audio = audio[silence_start:silence_end]
    
    padding = int(0.3 * SAMPLE_RATE)
    audio = np.concatenate([
        np.zeros(padding, dtype=np.float32),
        audio,
        np.zeros(padding, dtype=np.float32)
    ])
    
    return audio

def combine_recordings(recordings):
    """Combine all recordings with appropriate spacing"""
    combined = []
    
    inter_prompt_gap = int(0.5 * SAMPLE_RATE)
    
    for i, recording in enumerate(recordings):
        combined.append(recording)
        
        if i < len(recordings) - 1:
            combined.append(np.zeros(inter_prompt_gap, dtype=np.float32))
    
    return np.concatenate(combined)

def analyze_quality(audio, sample_rate):
    """Analyze recording quality"""
    print("\n[QUALITY ANALYSIS]")
    
    max_amp = np.max(np.abs(audio))
    rms = np.sqrt(np.mean(audio**2))
    
    silence_threshold = 0.01
    speech_pct = (np.sum(np.abs(audio) > silence_threshold) / len(audio)) * 100
    
    duration = len(audio) / sample_rate
    
    print(f"  Total duration: {duration:.1f} seconds")
    print(f"  Peak level: {max_amp:.3f} {'[TOO LOW]' if max_amp < 0.1 else '[TOO HIGH]' if max_amp > 0.95 else '[GOOD]'}")
    print(f"  RMS level: {rms:.3f}")
    print(f"  Speech content: {speech_pct:.1f}% {'[LOW]' if speech_pct < 40 else '[GOOD]'}")
    
    quality_ok = max_amp >= 0.1 and max_amp < 0.95 and speech_pct >= 40
    
    return quality_ok

def save_sample(audio, sample_rate, username):
    """Save voice sample"""
    output_dir = Path('./personality/voice')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{username}_voice_sample.mp3"
    
    if output_path.exists():
        response = input(f"\n[WARNING] {output_path} exists. Overwrite? (y/N): ").strip().lower()
        if response not in ('y', 'yes'):
            return None
    
    # FIX: Ensure audio is 1D before converting
    if audio.ndim > 1:
        audio = audio.flatten()
    
    audio_int16 = (audio * 32767).astype(np.int16)
    
    sf.write(str(output_path), audio_int16, sample_rate)
    
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
    prompts = PROMPT_SETS[prompt_set_name]
    
    username = get_username()
    
    formatted_prompts = [p.format(username=username) for p in prompts]
    
    show_instructions(len(formatted_prompts))
    
    device_idx = select_device()
    if device_idx is None:
        return
    
    print()
    print("[INFO] Starting interactive recording...")
    
    recordings = []
    
    for i, prompt_text in enumerate(formatted_prompts, 1):
        audio = record_single_prompt(device_idx, prompt_text, i, len(formatted_prompts))
        recordings.append(audio)
    
    print()
    print("=" * 70)
    print(" " * 20 + "ALL PROMPTS RECORDED")
    print("=" * 70)
    print()
    print("[INFO] Combining recordings...")
    
    combined_audio = combine_recordings(recordings)
    
    quality_ok = analyze_quality(combined_audio, SAMPLE_RATE)
    
    print()
    response = input("Listen to complete sample? (Y/n): ").strip().lower()
    if response in ('', 'y', 'yes'):
        print("\n[PLAYBACK] Playing combined sample...")
        sd.play(combined_audio, SAMPLE_RATE)
        sd.wait()
        print("[PLAYBACK] Done")
    
    print()
    if not quality_ok:
        print("[WARNING] Quality issues detected")
        response = input("Save anyway? (y/N): ").strip().lower()
        if response not in ('y', 'yes'):
            print("[CANCELLED] Recording not saved")
            return
    
    output_path = save_sample(combined_audio, SAMPLE_RATE, username)
    
    if output_path:
        print("=" * 70)
        print(" " * 20 + "RECORDING COMPLETE!")
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