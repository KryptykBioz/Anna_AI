# Speaker Verification System - Installation Guide

## Project Structure

```
Anna_AI/                                    # Your project root
│
├── BASE/
│   ├── handlers/
│   │   ├── internal_tool_interface.py     # (existing)
│   │   └── tts_interface.py               # (existing)
│   │
│   └── tools/
│       └── internal/
│           ├── xtts/                       # (existing)
│           │   ├── tool.py
│           │   ├── xtts_engine.py
│           │   ├── xtts_config.json
│           │   └── information.json
│           │
│           ├── whisper/                    # (existing - MODIFY)
│           │   ├── tool.py                 # [REPLACE] with modified version
│           │   ├── whisper_engine.py       # [MODIFY] recognition_worker_whisper()
│           │   └── information.json
│           │
│           └── speaker_verification/       # [NEW DIRECTORY]
│               ├── speaker_verification_engine.py  # [NEW]
│               ├── information.json                # [NEW]
│               ├── xtts_config.json                # [SYMLINK or COPY from xtts/]
│               └── README.md                       # [NEW]
│
├── personality/
│   ├── controls.py                         # [MODIFY] Add speaker verification settings
│   ├── bot_info.py                         # (existing)
│   │
│   └── voice/                              # [NEW DIRECTORY]
│       └── {username}_voice_sample.wav     # [CREATED by recording scripts]
│
└── tools/                                  # [NEW DIRECTORY at project root]
    └── voice_recording/                    # [NEW]
        ├── guided_record.py                # [NEW]
        ├── record_voice_sample.py          # [NEW]
        ├── quick_record.py                 # [NEW]
        └── RECORDING_GUIDE.md              # [NEW]
```

---

## Installation Steps

### Step 1: Create New Directories

```bash
# From project root (Anna_AI/)
cd Anna_AI

# Create speaker_verification tool directory
mkdir -p BASE/tools/internal/speaker_verification

# Create voice samples directory
mkdir -p personality/voice

# Create recording tools directory
mkdir -p tools/voice_recording
```

### Step 2: Install Speaker Verification Files

```bash
# Copy speaker verification engine
cp speaker_verification_engine.py BASE/tools/internal/speaker_verification/

# Copy information.json
cp information.json BASE/tools/internal/speaker_verification/

# Copy README
cp README.md BASE/tools/internal/speaker_verification/

# Create symlink to xtts_config.json (or copy it)
# Option A: Symlink (recommended)
ln -s ../../xtts/xtts_config.json BASE/tools/internal/speaker_verification/xtts_config.json

# Option B: Copy (if symlinks not supported)
cp BASE/tools/internal/xtts/xtts_config.json BASE/tools/internal/speaker_verification/
```

### Step 3: Update Whisper Tool

```bash
# Backup original whisper tool
cp BASE/tools/internal/whisper/tool.py BASE/tools/internal/whisper/tool.py.backup

# Replace with modified version
cp tool.py BASE/tools/internal/whisper/tool.py
```

### Step 4: Update Whisper Engine

Open `BASE/tools/internal/whisper/whisper_engine.py` and replace the `recognition_worker_whisper()` function with the version from `whisper_engine_recognition_worker_modified.py`.

**Location in file**: Around line 45-140 (the entire function)

**Key changes:**
- Add audio segment queueing for speaker verification
- Check `whisper_tool._use_speaker_verification` flag
- Put audio data into `whisper_tool._audio_segment_queue`

### Step 5: Install Recording Scripts

```bash
# Copy all recording scripts
cp guided_record.py tools/voice_recording/
cp record_voice_sample.py tools/voice_recording/
cp quick_record.py tools/voice_recording/
cp RECORDING_GUIDE.md tools/voice_recording/

# Make scripts executable
chmod +x tools/voice_recording/*.py
```

### Step 6: Update Controls Configuration

Edit `personality/controls.py` and add:

```python
# ============================================================================
# Speaker Verification Settings
# ============================================================================

# Enable speaker verification (filters non-user voices)
USE_SPEAKER_VERIFICATION = True

# Similarity threshold for voice matching (0.0 to 1.0)
# 0.85+ = Very strict (high security, may reject user occasionally)
# 0.75-0.80 = Strict (recommended for most users)
# 0.65-0.70 = Moderate (more permissive)
# 0.55-0.60 = Loose (testing only)
SPEAKER_VERIFICATION_THRESHOLD = 0.75
```

### Step 7: Record Voice Sample

```bash
# Run from project root
cd Anna_AI

# Option A: Guided recording (recommended)
python tools/voice_recording/guided_record.py

# Option B: Full featured recording
python tools/voice_recording/record_voice_sample.py

# Option C: Quick recording
python tools/voice_recording/quick_record.py
```

This will create: `personality/voice/{username}_voice_sample.wav`

---

## Complete File Checklist

### New Files to Create

- [ ] `BASE/tools/internal/speaker_verification/` (directory)
- [ ] `BASE/tools/internal/speaker_verification/speaker_verification_engine.py`
- [ ] `BASE/tools/internal/speaker_verification/information.json`
- [ ] `BASE/tools/internal/speaker_verification/README.md`
- [ ] `BASE/tools/internal/speaker_verification/xtts_config.json` (symlink or copy)
- [ ] `personality/voice/` (directory)
- [ ] `tools/voice_recording/` (directory)
- [ ] `tools/voice_recording/guided_record.py`
- [ ] `tools/voice_recording/record_voice_sample.py`
- [ ] `tools/voice_recording/quick_record.py`
- [ ] `tools/voice_recording/RECORDING_GUIDE.md`

### Files to Modify

- [ ] `BASE/tools/internal/whisper/tool.py` (replace entire file)
- [ ] `BASE/tools/internal/whisper/whisper_engine.py` (replace `recognition_worker_whisper()`)
- [ ] `personality/controls.py` (add speaker verification settings)

### Files Created by User

- [ ] `personality/voice/{username}_voice_sample.wav` (created by recording script)

---

## Verification Checklist

After installation, verify:

```bash
# 1. Check directory structure
ls -la BASE/tools/internal/speaker_verification/
# Should show: speaker_verification_engine.py, information.json, README.md, xtts_config.json

ls -la personality/voice/
# Should show: {username}_voice_sample.wav (after recording)

ls -la tools/voice_recording/
# Should show: guided_record.py, record_voice_sample.py, quick_record.py, RECORDING_GUIDE.md

# 2. Check file permissions
ls -l tools/voice_recording/*.py
# Should show: -rwxr-xr-x (executable)

# 3. Verify controls.py has new settings
grep "USE_SPEAKER_VERIFICATION" personality/controls.py
# Should output: USE_SPEAKER_VERIFICATION = True

# 4. Check whisper tool was updated
grep "_speaker_verifier" BASE/tools/internal/whisper/tool.py
# Should find the attribute in __slots__

# 5. Test import
python -c "from BASE.tools.internal.speaker_verification.speaker_verification_engine import SpeakerVerificationEngine; print('OK')"
# Should output: OK
```

---

## Alternative: Quick Install Script

Create this as `install_speaker_verification.sh`:

```bash
#!/bin/bash
# Quick installation script for speaker verification system

echo "Installing Speaker Verification System..."

# Create directories
echo "Creating directories..."
mkdir -p BASE/tools/internal/speaker_verification
mkdir -p personality/voice
mkdir -p tools/voice_recording

# Copy speaker verification files
echo "Installing speaker verification engine..."
cp speaker_verification_engine.py BASE/tools/internal/speaker_verification/
cp information.json BASE/tools/internal/speaker_verification/
cp README.md BASE/tools/internal/speaker_verification/

# Create symlink to xtts_config.json
echo "Linking XTTS configuration..."
ln -sf ../../xtts/xtts_config.json BASE/tools/internal/speaker_verification/xtts_config.json

# Backup and update whisper tool
echo "Updating Whisper tool..."
cp BASE/tools/internal/whisper/tool.py BASE/tools/internal/whisper/tool.py.backup
cp tool.py BASE/tools/internal/whisper/tool.py

# Copy recording scripts
echo "Installing recording scripts..."
cp guided_record.py tools/voice_recording/
cp record_voice_sample.py tools/voice_recording/
cp quick_record.py tools/voice_recording/
cp RECORDING_GUIDE.md tools/voice_recording/
chmod +x tools/voice_recording/*.py

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Update personality/controls.py (add USE_SPEAKER_VERIFICATION = True)"
echo "2. Update BASE/tools/internal/whisper/whisper_engine.py (replace recognition_worker_whisper function)"
echo "3. Record voice sample: python tools/voice_recording/guided_record.py"
echo "4. Restart your AI agent"
```

Make it executable:
```bash
chmod +x install_speaker_verification.sh
```

Run it:
```bash
./install_speaker_verification.sh
```

---

## Manual Installation (Detailed)

### For speaker_verification_engine.py

**Exact location:**
```
BASE/tools/internal/speaker_verification/speaker_verification_engine.py
```

**Command:**
```bash
mkdir -p BASE/tools/internal/speaker_verification
cp speaker_verification_engine.py BASE/tools/internal/speaker_verification/
```

### For information.json

**Exact location:**
```
BASE/tools/internal/speaker_verification/information.json
```

**Command:**
```bash
cp information.json BASE/tools/internal/speaker_verification/
```

### For README.md

**Exact location:**
```
BASE/tools/internal/speaker_verification/README.md
```

**Command:**
```bash
cp README.md BASE/tools/internal/speaker_verification/
```

### For xtts_config.json

**Exact location:**
```
BASE/tools/internal/speaker_verification/xtts_config.json
```

**Command (symlink - recommended):**
```bash
cd BASE/tools/internal/speaker_verification
ln -s ../xtts/xtts_config.json xtts_config.json
cd ../../../../
```

**Command (copy - alternative):**
```bash
cp BASE/tools/internal/xtts/xtts_config.json BASE/tools/internal/speaker_verification/
```

### For modified Whisper tool.py

**Exact location:**
```
BASE/tools/internal/whisper/tool.py
```

**Commands:**
```bash
# Backup original
cp BASE/tools/internal/whisper/tool.py BASE/tools/internal/whisper/tool.py.backup

# Replace with modified version
cp tool.py BASE/tools/internal/whisper/tool.py
```

### For Whisper engine modification

**Exact location:**
```
BASE/tools/internal/whisper/whisper_engine.py
```

**Manual edit required:**
1. Open `BASE/tools/internal/whisper/whisper_engine.py`
2. Find the `recognition_worker_whisper()` function (starts around line 45)
3. Replace it with the version from `whisper_engine_recognition_worker_modified.py`
4. Save the file

**Key lines to add:**
```python
# Around line 150, after transcription completes:
if whisper_tool._use_speaker_verification and whisper_tool._audio_segment_queue:
    whisper_tool._audio_segment_queue.put_nowait({
        'audio': audio_data,
        'sample_rate': SAMPLERATE
    })
```

### For recording scripts

**Exact locations:**
```
tools/voice_recording/guided_record.py
tools/voice_recording/record_voice_sample.py
tools/voice_recording/quick_record.py
tools/voice_recording/RECORDING_GUIDE.md
```

**Commands:**
```bash
mkdir -p tools/voice_recording
cp guided_record.py tools/voice_recording/
cp record_voice_sample.py tools/voice_recording/
cp quick_record.py tools/voice_recording/
cp RECORDING_GUIDE.md tools/voice_recording/
chmod +x tools/voice_recording/*.py
```

---

## Troubleshooting Installation

### "Module not found" error

**Problem:** `ImportError: No module named 'BASE.tools.internal.speaker_verification'`

**Solution:**
```bash
# Verify directory exists
ls -la BASE/tools/internal/speaker_verification/

# Verify __init__.py exists in parent directories (if required)
# Usually not needed for Python 3.3+, but if issues persist:
touch BASE/__init__.py
touch BASE/tools/__init__.py
touch BASE/tools/internal/__init__.py
touch BASE/tools/internal/speaker_verification/__init__.py
```

### "xtts_config.json not found" error

**Problem:** `FileNotFoundError: xtts_config.json`

**Solution:**
```bash
# Check if symlink is broken
ls -la BASE/tools/internal/speaker_verification/xtts_config.json

# If broken, recreate as copy instead
cp BASE/tools/internal/xtts/xtts_config.json BASE/tools/internal/speaker_verification/
```

### "Voice sample not found" error

**Problem:** `[Whisper] Speaker verification disabled - user voice sample not found`

**Solution:**
```bash
# Check voice sample exists
ls -la personality/voice/{username}_voice_sample.wav

# If missing, record it
python tools/voice_recording/guided_record.py
```

### Recording script import errors

**Problem:** `ImportError: personality.bot_info`

**Solution:**
- This is normal if running outside project directory
- Script will prompt for manual username entry
- Or run from project root: `cd Anna_AI && python tools/voice_recording/guided_record.py`

---

## Post-Installation Testing

```bash
# Test 1: Import speaker verification engine
python -c "
from BASE.tools.internal.speaker_verification.speaker_verification_engine import SpeakerVerificationEngine
print('[OK] Speaker verification engine imports successfully')
"

# Test 2: Check Whisper tool has speaker verification
python -c "
import sys
sys.path.insert(0, '.')
from BASE.tools.internal.whisper.tool import WhisperTool
print('[OK] Whisper tool imports successfully')
print('[OK] Has _speaker_verifier:', '_speaker_verifier' in WhisperTool.__slots__)
"

# Test 3: Verify controls.py updated
python -c "
from personality import controls
print('[OK] USE_SPEAKER_VERIFICATION:', controls.USE_SPEAKER_VERIFICATION)
print('[OK] SPEAKER_VERIFICATION_THRESHOLD:', controls.SPEAKER_VERIFICATION_THRESHOLD)
"

# Test 4: Check voice sample exists
python -c "
from personality.bot_info import username
from pathlib import Path
sample = Path(f'./personality/voice/{username}_voice_sample.wav')
print(f'[OK] Voice sample exists: {sample.exists()}')
if sample.exists():
    print(f'[OK] File size: {sample.stat().st_size / 1024:.1f} KB')
"
```

All tests should output `[OK]` messages.

---

## Summary

**Essential files placement:**
1. Speaker verification engine → `BASE/tools/internal/speaker_verification/`
2. Modified Whisper tool → `BASE/tools/internal/whisper/tool.py` (replace)
3. Recording scripts → `tools/voice_recording/`
4. Voice sample → `personality/voice/{username}_voice_sample.wav` (created by script)
5. Controls update → `personality/controls.py` (add settings)

**Run from project root:**
```bash
cd Anna_AI
python tools/voice_recording/guided_record.py
```

The system will then be ready to use with speaker verification enabled.