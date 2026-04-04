# Voice Sample Recording Scripts - Usage Guide

## Overview

Three recording scripts are provided, each optimized for different user preferences and use cases.

---

## Script Comparison

| Script | Best For | Duration | Complexity | Features |
|--------|----------|----------|------------|----------|
| **interactive_record.py** | New users (easiest) | 7-10 prompts | Low | One prompt at a time, press Enter to advance |
| **guided_record.py** | Most users | 10-15s | Medium | All prompts shown, read at your pace |
| **record_voice_sample.py** | Maximum accuracy | 10s | High | Full workflow, extensive testing |
| **quick_record.py** | Quick setup | 8s | Low | Minimal interaction |

---

## 1. interactive_record.py [EASIEST - RECOMMENDED FOR FIRST-TIME USERS]

### Description
Records one prompt at a time with full control. You press Enter before each prompt, so there's no rushing. Each prompt is recorded separately, then all are combined into a single voice sample.

### Features
- Record each prompt individually
- Press Enter to advance to next prompt
- No time pressure or rushing
- Automatic silence trimming
- Quality check for each prompt
- Re-record individual prompts if needed
- All recordings combined automatically

### Usage

```bash
python interactive_record.py
```

### Workflow
1. Select prompt set
2. Select audio input device
3. Review instructions
4. **For each prompt:**
   - Prompt appears on screen
   - Press Enter when ready
   - 3-second countdown
   - Speak the prompt (5 seconds)
   - Automatically trims silence
   - Option to re-record if needed
5. All prompts combined into one sample
6. Quality analysis
7. Listen to playback (optional)
8. Save to `./personality/voice/{username}_voice_sample.mp3`

### Example Session

```
[PROMPT SET SELECTION]
  [1] 7 prompts - Balanced for general use
  [2] 10 prompts - Maximum accuracy
  [3] 8 prompts - Phonetically diverse
  [4] 7 prompts - Natural speech

Select prompt set (1-4, default 1): 1

[INFO] You will record 7 prompts, one at a time

[WORKFLOW]
  1. A prompt will be displayed on screen
  2. Press Enter when ready to record that prompt
  3. Recording starts after 3-second countdown
  4. Speak the prompt clearly and naturally
  5. Recording stops automatically after you finish
  6. Repeat for each prompt

Press Enter when ready to begin...

======================================================================
PROMPT 1 of 7
======================================================================

>>> Hello, I am recording my voice sample for authentication.

Press Enter when ready to record this prompt...
  Recording in 3...
  [RECORDING - Speak now!]
  [█████] 5/5s - Done!

======================================================================
PROMPT 2 of 7
======================================================================

>>> The quick brown fox jumps over the lazy dog.

Press Enter when ready to record this prompt...
...
```

### Why Use This?
- **No rushing**: Take breaks between prompts
- **Quality control**: Review each prompt individually
- **Easier for beginners**: Less overwhelming than reading all at once
- **Re-record single prompts**: Fix mistakes without redoing everything
- **Automatic editing**: Silence trimming and spacing handled for you

---

## 2. guided_record.py [RECOMMENDED FOR MOST USERS]

### Description
Interactive recorder that displays all prompts on screen during recording. All prompts are shown simultaneously - you read them at your own pace during the full recording duration.

### Features
- All prompts displayed on screen at once
- Read at your natural pace
- 10-15 second continuous recording
- Quality analysis with specific feedback
- Playback option before saving
- Re-record capability

### Usage

```bash
python guided_record.py
```

### Workflow
1. Select prompt set (standard, comprehensive, phonetic, conversational)
2. Select audio input device
3. Preview all prompts that will appear
4. **Recording:**
   - Countdown starts
   - All prompts appear on screen
   - Read through them at your own pace
   - Progress bar shows time remaining
5. Review quality analysis
6. Listen to playback (optional)
7. Accept or re-record
8. Save to `./personality/voice/{username}_voice_sample.mp3`

### Prompt Sets

**Standard** (10 seconds - recommended)
- Balanced mix of phonemes
- Natural sentences
- Good for general use

**Comprehensive** (15 seconds)
- Maximum phonetic diversity
- Tongue twisters and pangrams
- Best accuracy for challenging environments

**Phonetic** (12 seconds)
- NATO alphabet
- Phonetically diverse pangrams
- Optimized for technical accuracy

**Conversational** (10 seconds)
- Natural speech patterns
- Everyday conversation
- Most natural-sounding sample

### Example Session

```
[PROMPT SET SELECTION]
  [1] Balanced prompts for general use (10 sec)
  [2] Extensive prompts for maximum accuracy (15 sec)
  [3] Phonetically diverse tongue-twisters (12 sec)
  [4] Natural conversational speech (10 sec)

Select prompt set (1-4, default 1): 1
[SELECTED] Balanced prompts for general use (10 sec)

[RECORDING PROMPTS PREVIEW]
----------------------------------------------------------------------
 1. Hello, I am recording my voice sample for authentication.
 2. The quick brown fox jumps over the lazy dog.
 3. I enjoy using voice commands to control my AI assistant.
 4. This sample captures my unique vocal characteristics.
 5. Numbers: one, two, three, four, five, six, seven, eight, nine, ten.
 6. My voice is being analyzed for speaker verification.
 7. Thank you for listening to this recording.
----------------------------------------------------------------------

Press Enter when ready to continue...

Starting in 3...
[RECORDING NOW - Speak the prompts below]
======================================================================
 1. Hello, I am recording my voice sample for authentication.
 2. The quick brown fox jumps over the lazy dog.
 3. I enjoy using voice commands to control my AI assistant.
 4. This sample captures my unique vocal characteristics.
 5. Numbers: one, two, three, four, five, six, seven, eight, nine, ten.
 6. My voice is being analyzed for speaker verification.
 7. Thank you for listening to this recording.
======================================================================

[TIP] Read naturally - you have the full duration to speak all prompts

[██████████████████████████████░░░░░░░░░░░░] 6/10s - 4s remaining
```

---

## 2. record_voice_sample.py

### Description
Comprehensive recording tool with full audio device testing, level calibration, and quality verification. Best for users who want maximum control and accuracy.

### Features
- Audio device selection with detailed information
- Pre-recording audio level test
- Optimized 10-second script with varied phonemes
- Comprehensive quality analysis
- Playback capability
- File compatibility verification
- Re-record option

### Usage

```bash
python record_voice_sample.py
```

### Workflow
1. **Audio Device Setup**
   - Lists all available input devices
   - Auto-selects or lets you choose
   
2. **Audio Level Test**
   - 3-second test recording
   - Checks if levels are too low/high
   - Provides specific feedback

3. **Username Configuration**
   - Auto-detects from `bot_info.py`
   - Manual entry if needed

4. **Review Recording Script**
   - Displays full script before recording
   - Optimized text for speaker verification

5. **Recording**
   - 10-second guided recording
   - Real-time progress bar
   - Quality analysis after recording

6. **Quality Verification**
   - Peak amplitude check
   - RMS level analysis
   - Speech content percentage
   - Clipping detection
   - File format compatibility

7. **Save & Verify**
   - Saves to correct location
   - Verifies file is compatible with system

### Audio Level Test Output

```
[AUDIO TEST] Recording 3 seconds to check levels...
[AUDIO TEST] Speak normally into the microphone...
  Recording test... 3/3 seconds
[AUDIO TEST] Peak level: 0.452
[AUDIO TEST] RMS level: 0.087
[SUCCESS] Audio levels good!
```

### Quality Analysis Output

```
[ANALYSIS] Checking recording quality...
  Peak amplitude: 0.512
  RMS level: 0.094
  Speech content: 78.3%
  Clipping: 0.00%

[SUCCESS] Recording quality is good!
```

---

## 3. quick_record.py

### Description
Minimal interaction recorder for experienced users or quick setup. No prompts, just record.

### Features
- Single-step recording
- 8-second duration
- Basic quality check
- Automatic save to correct location
- Minimal output

### Usage

```bash
python quick_record.py
```

### Workflow
1. Detects username (or asks)
2. Checks if file exists (prompts to overwrite)
3. 3-second countdown
4. 8 seconds of recording
5. Basic quality check
6. Auto-save

### When to Use
- You've recorded before and know what to do
- Quick re-recording after changing microphone
- Testing different microphone setups
- You prefer to speak freely without prompts

### Example Session

```
[INFO] Username: john
[READY] Recording 8 seconds of audio
[INFO] Speak naturally - vary your tone and pace
[TIP] Read a paragraph from a book or describe your day

Starting in 3...
[RECORDING NOW!]

[████████] 8/8s - DONE!

[SUCCESS] Good audio level (peak: 0.423)

[SAVED] ./personality/voice/john_voice_sample.mp3
[SIZE] 172.3 KB

[NEXT] Set USE_SPEAKER_VERIFICATION = True in controls.py
```

---

## Recording Best Practices

### Environment
- **Quiet room**: Minimize background noise
- **No echo**: Avoid large empty rooms
- **Consistent location**: Record where you'll use the system
- **No music**: Only your voice should be recorded

### Microphone
- **Position**: 6-12 inches from mouth
- **Angle**: Slightly off-axis to reduce plosives
- **Quality**: Use decent microphone (headset is fine)
- **Test first**: Use level test to check setup

### Speaking
- **Natural pace**: Don't rush, don't go too slow
- **Clear articulation**: Pronounce words normally
- **Vary tone**: Include questions, statements, emphasis
- **Volume**: Speak at normal conversation level
- **Emotion**: Use natural intonation, not monotone

### Technical
- **Format**: 22050 Hz, 16-bit PCM, mono
- **Duration**: 6-10 seconds optimal (min 3s, max 30s)
- **Level**: Peak 0.2-0.8 (avoid clipping at 1.0)
- **Content**: Mix of phonemes, not repeated words

---

## Troubleshooting

### "No input devices found"
- Check microphone is connected
- Verify microphone permissions in OS
- Try `python -m sounddevice` to list devices

### "Audio level very low"
- Speak louder
- Move microphone closer
- Increase microphone gain in OS settings
- Check mute button on microphone

### "Audio level too high"
- Reduce microphone gain
- Move microphone farther away
- Speak more softly
- Check for automatic gain control (AGC)

### "Recording very quiet"
- Peak level < 0.1 indicates microphone issue
- Solution: Increase gain or speak louder
- Re-record after adjusting

### "Clipping detected"
- Peak level > 0.95 indicates distortion
- Solution: Reduce gain or speak softer
- Re-record to avoid accuracy issues

### "Low speech content"
- You may not have spoken during recording
- Microphone may not be capturing audio
- Solution: Test microphone, re-record

### Import Error: personality.bot_info
- Script will prompt for manual username entry
- This is normal if running outside project directory
- Solution: Enter your username when prompted

---

## Which Script Should I Use?

### Use `interactive_record.py` if:
- [Checkmark] **First time setting up voice verification**
- [Checkmark] You want to take your time with each prompt
- [Checkmark] You prefer recording one prompt at a time
- [Checkmark] You want control over when to advance
- [Checkmark] You might need to re-record individual prompts
- [Checkmark] **This is recommended for beginners**

### Use `guided_record.py` if:
- [Checkmark] You prefer continuous recording
- [Checkmark] You can read multiple prompts fluidly
- [Checkmark] You want a faster recording process
- [Checkmark] You're comfortable with all prompts shown at once
- [Checkmark] **This is recommended for experienced users**

### Use `record_voice_sample.py` if:
- [Checkmark] Want maximum control over the process
- [Checkmark] Need to test audio levels first
- [Checkmark] Want comprehensive quality verification
- [Checkmark] Having issues with voice recognition accuracy
- [Checkmark] Setting up in noisy/challenging environment

### Use `quick_record.py` if:
- [Checkmark] Already know how to record voice samples
- [Checkmark] Just need to quickly re-record
- [Checkmark] Prefer minimal interaction
- [Checkmark] Testing different microphone setups
- [Checkmark] Comfortable speaking without prompts

---

## After Recording

### 1. Enable Speaker Verification

Edit `personality/controls.py`:

```python
# Speaker Verification
USE_SPEAKER_VERIFICATION = True

# Threshold (0.75 is recommended default)
# Higher = more strict (fewer false accepts)
# Lower = more lenient (fewer false rejects)
SPEAKER_VERIFICATION_THRESHOLD = 0.75
```

### 2. Verify File Location

Check that file exists:
```bash
ls -lh ./personality/voice/{username}_voice_sample.mp3
```

Should output something like:
```
-rw-r--r-- 1 user user 172K Feb 7 10:30 john_voice_sample.mp3
```

### 3. Restart AI Agent

The speaker verification system will initialize on startup.

### 4. Test Voice Commands

Speak a command and verify:
- Your voice is accepted and processed
- Other voices are rejected with similarity scores logged

### 5. Monitor Logs

Watch for speaker verification output:
```
[Speaker Verification] [MATCH] Similarity: 0.82
[Speaker Verification] [REJECT] Similarity: 0.54
```

### 6. Tune Threshold (if needed)

**If your voice is rejected:**
- Lower threshold to 0.70 or 0.65
- Re-record with clearer audio
- Check microphone quality

**If other voices are accepted:**
- Raise threshold to 0.80 or 0.85
- Re-record with more vocal variety
- Ensure sample is high quality

---

## Advanced Usage

### Recording for Multiple Users

Record separate samples for each authorized user:

```bash
# User 1
python guided_record.py
# Enter username: john

# User 2  
python guided_record.py
# Enter username: jane
```

Files created:
- `./personality/voice/john_voice_sample.mp3`
- `./personality/voice/jane_voice_sample.mp3`

### Re-recording After Voice Changes

Your voice may change due to:
- Illness (cold, sore throat)
- Time of day (morning vs evening)
- Emotional state
- Aging

If verification accuracy decreases, re-record:

```bash
python quick_record.py
# Overwrites existing sample
```

### Testing Different Microphones

```bash
# Record with microphone A
python quick_record.py

# Test accuracy

# Record with microphone B
python quick_record.py

# Compare accuracy
```

---

## File Specifications

All scripts produce WAV files with these specifications:

| Parameter | Value | Why |
|-----------|-------|-----|
| Sample Rate | 22050 Hz | XTTS standard rate |
| Bit Depth | 16-bit | Optimal quality/size ratio |
| Channels | 1 (mono) | Speaker verification needs mono |
| Format | PCM WAV | Uncompressed, lossless |
| Duration | 6-15 seconds | Sufficient for accurate embeddings |

---

## Support

If you encounter issues:

1. Run audio device diagnostic:
   ```bash
   python -m sounddevice
   ```

2. Check Python dependencies:
   ```bash
   pip list | grep -E "sounddevice|soundfile|numpy"
   ```

3. Verify microphone permissions (OS-specific)

4. Try different recording script

5. Check README.md for detailed troubleshooting

---

## Quick Reference

```bash
# Easiest - record one prompt at a time (recommended for beginners)
python interactive_record.py

# Fast - all prompts shown at once (recommended for experienced users)
python guided_record.py

# Maximum control and testing
python record_voice_sample.py

# Quick and simple
python quick_record.py

# After recording, enable in controls.py
USE_SPEAKER_VERIFICATION = True
SPEAKER_VERIFICATION_THRESHOLD = 0.75
```