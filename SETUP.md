# AI VTUBER AGENT SETUP GUIDE

Complete installation and configuration guide for the VTuber AI Agent system with RTX 50-series GPU support.

---

## TABLE OF CONTENTS

1. [System Requirements](#system-requirements)
2. [Quick Start Guide](#quick-start-guide)
3. [Python Installation](#python-installation)
4. [Ollama Installation](#ollama-installation)
5. [Agent Installation](#agent-installation)
6. [Optional Tools and Extensions](#optional-tools-and-extensions)
7. [GPU Package Setup (RTX 50-Series)](#gpu-package-setup-rtx-50-series)
8. [Virtual Audio Cable Installation](#virtual-audio-cable-installation)
9. [Warudo Installation](#warudo-installation)
10. [VRoid Studio Installation](#vroid-studio-installation)
11. [Verification & Testing](#verification--testing)
12. [Troubleshooting](#troubleshooting)
13. [Common Issues](#common-issues)

---

## SYSTEM REQUIREMENTS

### Minimum Hardware
- **CPU**: Intel i5-8400 / AMD Ryzen 5 2600 or better
- **RAM**: 16GB DDR4 (32GB recommended for multiple agents)
- **Storage**: 50GB free SSD space
- **GPU**: NVIDIA RTX 50-series (5060 Ti, 5070, 5080, 5090)
  - RTX 40/30-series compatible with standard PyTorch installation
  - Minimum 8GB VRAM (12GB+ recommended)

### Software Requirements
- **OS**: Windows 10/11 (64-bit)
- **GPU Drivers**: NVIDIA Game Ready Driver 566.03 or newer
- **Visual Studio**: Build Tools 2019/2022 (for PyAudio compilation)
- **Virtual Audio**: VB-Audio Cable (required for TTS and lip sync)
- **Internet**: Required for initial model downloads

### Disk Space Breakdown
- Python environment: ~5GB
- PyTorch + CUDA libraries: ~10GB
- Whisper models: ~3GB per model
- XTTS models: ~2GB
- Ollama models: 5-20GB depending on selection
- Warudo: ~5GB
- VRoid Studio: ~2GB
- Virtual audio cables: ~10MB (negligible)

---

## QUICK START GUIDE

### For Experienced Users

```batch
# 1. Install Python 3.11.9

# 2. Install Ollama

# 3. Clone Anna_AI from GitHub
git clone https://github.com/KryptykBioz/Anna_AI.git
cd Anna_AI

# 4. Create virtual environment
py -3.11 -m venv venv

# 5. Activate the virtual environment
.\venv\Scripts\activate

# 6. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install transformers==4.38.2

# 6.5 (RTX 50-series only). Copy GPU packages from working Anna_AI instance
# If this is your first Anna_AI install, follow full GPU setup instructions
python copy_gpu_packages.py

# 7. Configure agent
# Edit personality/bot_info.py with your settings and preferences:
#   - agentname = "Anna"
#   - username = "User"
#   - thoughtmodel = "gemma4:latest"
#   - responsemodel = "gemma4:latest"
#   - toolmodel = "gemma4:latest"
#   - actionmodel = "gemma4:latest"
#   - visionmodel = "gemma4:latest"
#   - embedmodel = "nomic-embed-text:latest"
# Edit config.json for advanced settings

# 8. Launch
.\START.bat

# 8.5. If Ollama is not running in the background already, open a terminal and run:
ollama start

# Agent should now start with basic text chat functionality ONLY.

# 9. Optional: Install additional tools
# Repository: https://github.com/KryptykBioz/AI_Agent_Tools
git clone https://github.com/KryptykBioz/AI_Agent_Tools.git
# Copy all individual tool directories into BASE/tools/installed/
# Follow tool-specific installation instructions

# NEXT STEPS:

# Install Virtual Audio Cables
# Download and install VB-Audio Cable from https://vb-audio.com/Cable/
# Run installer as Administrator, restart computer
# Optional: Install Tala cables for multiple agents from
# https://github.com/Essence-Platform/TalaVirtualAudioCables-Public

# Allow Virtual Cable to play through audio output
# Open System Settings -> Sound -> More Sound Settings (window opens) -> 
# Recording tab -> double-click virtual cable (window opens) -> 
# Check the 'Listen to this device' checkbox, Playback device should be set to default
# Note: For your agent to speak through a separate output device than the system default, 
# this can be changed here. The agent's voice can be played through a separate speaker 
# from all other audio sources

# Agent can now speak using system voice

# Install Warudo (through Steam)

# Configure Warudo for lip sync
# Warudo → Settings → Audio → Lip Sync Input: CABLE Output (VB-Audio)
# Warudo → Settings → Network → WebSocket Server: Enable (Port 19190)

# Optional: Load Anna.vrm into Warudo
# File location: Anna_AI\personality\avatar\Anna.vrm

# Agent's on-screen avatar now speaks when the agent speaks

```

Continue reading for detailed step-by-step instructions.

---

## ENVIRONMENT CONFIGURATION

### .env File Setup

The agent uses a `.env` file for Ollama performance optimization and system configuration.

**Create .env file**:

```batch
cd Anna_AI
copy .env.example .env
```

**Edit .env with optimized settings**:

```bash
# Ollama Performance Optimization for Autonomous Agent
OLLAMA_NUM_PARALLEL=1
OLLAMA_CONTEXT_LENGTH=8192
OLLAMA_FLASH_ATTENTION=true
CUDA_VISIBLE_DEVICES=0
OLLAMA_GPU_OVERHEAD=1024
OLLAMA_KEEP_ALIVE=24h                # Keep models loaded for 24 hours
OLLAMA_LOAD_TIMEOUT=5m               # Increased for initial load
OLLAMA_MAX_QUEUE=128
OLLAMA_NUM_THREADS=6

OLLAMA_MAX_LOADED_MODELS=2           # Allow both models
OLLAMA_CONCURRENT_REQUESTS=1         # But only one request at a time

# Additional optimizations
OLLAMA_ORIGINS=*                     # Allow API access
OLLAMA_DEBUG=false                   # Disable unless debugging

# Temperature settings for different cognitive modes
OLLAMA_TEMPERATURE_ACTION=0.2        # More deterministic for actions
OLLAMA_TEMPERATURE_COGNITIVE=0.6     # Balanced for thinking
OLLAMA_TEMPERATURE_RESPONSE=0.9      # More creative for responses 
```

**Key Settings Explained**:

| Setting | Value | Purpose |
|---------|-------|---------|
| `OLLAMA_KEEP_ALIVE` | 24h | Keeps models loaded in memory for fast responses |
| `OLLAMA_NUM_PARALLEL` | 1 | Single request processing for autonomous agent |
| `OLLAMA_CONTEXT_LENGTH` | 8192 | Maximum context window size |
| `OLLAMA_FLASH_ATTENTION` | true | Enables faster attention computation |
| `CUDA_VISIBLE_DEVICES` | 0 | Use first GPU (change if multi-GPU setup) |
| `OLLAMA_MAX_LOADED_MODELS` | 2 | Load multiple models simultaneously |

**Performance Tuning**:

For lower VRAM GPUs (8GB):
```bash
OLLAMA_CONTEXT_LENGTH=4096           # Reduce context window
OLLAMA_GPU_OVERHEAD=512              # Reduce GPU overhead
OLLAMA_MAX_LOADED_MODELS=1           # Load one model at a time
```

For high-end GPUs (16GB+):
```bash
OLLAMA_CONTEXT_LENGTH=16384          # Increase context window
OLLAMA_GPU_OVERHEAD=2048             # Increase GPU overhead
OLLAMA_MAX_LOADED_MODELS=3           # Load multiple models
```

**Apply .env Changes**:

```batch
# Restart Ollama service to apply changes
net stop ollama
net start ollama
```

---

## PYTHON INSTALLATION

### Step 1: Download Python 3.11.9

[Warning] Critical Version Requirement: This system requires Python **3.11.9** specifically. Newer versions may have compatibility issues with TTS and transformers.

1. Visit: https://www.python.org/downloads/release/python-3119/
2. Scroll to "Files" section
3. Download: **Windows installer (64-bit)**
   - File: `python-3.11.9-amd64.exe`

### Step 2: Install Python

1. Run the installer as Administrator
2. [Critical] Check "Add Python 3.11 to PATH"
3. Click "Customize installation"
4. Ensure these options are selected:
   - pip
   - tcl/tk and IDLE
   - Python test suite
   - py launcher
5. Click "Next"
6. Advanced Options:
   - [x] Install for all users
   - [x] Add Python to environment variables
   - [x] Precompile standard library
   - Install location: `C:\Python311` (recommended)
7. Click "Install"

### Step 3: Verify Installation

Open Command Prompt and run:

```batch
python --version
pip --version
```

Expected output:
```
Python 3.11.9
pip 24.x.x from C:\Python311\Lib\site-packages\pip (python 3.11)
```

### Step 4: Install Visual Studio Build Tools

Required for compiling PyAudio and other C extensions.

1. Download: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Run installer
3. Select "Desktop development with C++"
4. Install (requires ~7GB disk space)
5. Restart computer after installation

---

## OLLAMA INSTALLATION

### Step 1: Download Ollama

1. Visit: https://ollama.ai/download
2. Download Windows installer
3. Run installer as Administrator
4. Default installation: `C:\Users\YourUsername\AppData\Local\Programs\Ollama`

### Step 2: Start Ollama Service

Ollama starts automatically after installation. To manually control:

```batch
# Start service
net start ollama

# Stop service
net stop ollama

# Check status
sc query ollama
```

### Step 3: Download Models

Download models specified in bot_info.py:

```batch
# Core models for Anna_AI
ollama pull gemma4:latest
ollama pull nomic-embed-text:latest

# Alternative models (optional)
ollama pull qwen3-vl:8b-instruct-q4_K_M
ollama pull qwen3-vl:8b-thinking-q4_K_M
```

Model download sizes:
- gemma4:latest: ~7GB
- nomic-embed-text: ~275MB
- qwen3-vl models: ~5GB each

### Step 4: Verify Ollama Configuration

```batch
# Test connection
curl http://localhost:11434/api/version

# List installed models
ollama list

# Test model
ollama run gemma4:latest "Hello, how are you?"
```

### Step 5: Configure Agent for Ollama

Agent is pre-configured in config.json and .env:

**config.json** (Application-level settings):

```json
{
  "ollama": {
    "endpoint": "http://localhost:11434",
    "temperature": 0.85,
    "max_tokens": 1000,
    "num_ctx": 3000
  }
}
```

**.env** (Ollama server optimization):

```bash
OLLAMA_CONTEXT_LENGTH=8192
OLLAMA_KEEP_ALIVE=24h
OLLAMA_FLASH_ATTENTION=true
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=2
```

**Adjust config.json for performance**:

```json
{
  "ollama": {
    "num_ctx": 2000,  // Lower for faster responses
    "num_predict": 500,  // Shorter responses
    "temperature": 0.7  // More focused responses
  }
}
```

**Adjust .env for different GPU capabilities**:

For 8GB VRAM:
```bash
OLLAMA_CONTEXT_LENGTH=4096
OLLAMA_GPU_OVERHEAD=512
OLLAMA_MAX_LOADED_MODELS=1
```

For 16GB+ VRAM:
```bash
OLLAMA_CONTEXT_LENGTH=16384
OLLAMA_GPU_OVERHEAD=2048
OLLAMA_MAX_LOADED_MODELS=3
```

**Apply changes**:
```batch
# Restart Ollama after .env changes
net stop ollama
net start ollama

# Restart agent after config.json changes
# (Stop and restart gui_start.bat)
```

---

## AGENT INSTALLATION

### Step 1: Clone Repository

```batch
cd C:\
git clone https://github.com/KryptykBioz/Anna_AI.git
cd Anna_AI
```

### Step 2: Create Virtual Environment

```batch
python -m venv venv
.\venv\Scripts\activate
```

Expected output:
```
(venv) C:\Anna_AI>
```

### Step 3: Install Dependencies

```batch
# Upgrade pip
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Install specific transformers version
pip install transformers==4.38.2
```

Installation time: 10-20 minutes depending on internet speed.

### Step 4: Configure Agent

**Primary Configuration (personality/bot_info.py)**:

```python
# Bot and User Information
agentname = "Anna"  # Change to your agent's name
username = "User"  # How the agent addresses you
game_username = "Player"  # In-game username reference

# Model Configuration (using Ollama)
thoughtmodel = "gemma4:latest"
responsemodel = "gemma4:latest"
toolmodel = "gemma4:latest"
actionmodel = "gemma4:latest"
visionmodel = "gemma4:latest"
embedmodel = "nomic-embed-text:latest"

# Voice settings
voiceIndex = 1  # TTS voice selection

# VB-Cable configuration
vb_cable_name = "CABLE Input"  # Must match Windows device name exactly

# Group chat port (unique for each agent)
group_chat_port = 54321  # Change to 54322, 54323, etc. for additional agents
```

**Advanced Configuration (config.json)**:

Key sections to configure:

```json
{
  "ollama": {
    "endpoint": "http://localhost:11434",
    "temperature": 0.85,
    "max_tokens": 1000,
    "num_ctx": 3000
  },
  "bot": {
    "name": "Anna",
    "username": "Master"
  },
  "warudo": {
    "websocket_url": "ws://127.0.0.1:19190",
    "enabled": true,
    "auto_connect": true
  },
  "features": {
    "use_warudo": true,
    "use_sound_effects": true
  }
}
```

**Control Variables (personality/controls.py)**:

Basic settings:

```python
# Core functionality
ENABLE_CONTINUOUS_THINKING = True
AUTO_RESPOND = False
USE_STREAMING = True

# Memory systems
USE_BASE_MEMORY = True
USE_LONG_MEMORY = True
USE_SHORT_MEMORY = True
SAVE_MEMORY = True
MEMORY_LENGTH = 50

# Avatar features
AVATAR_SPEECH = True
USE_CUSTOM_VOICE = True

# Volume controls
VOICE_VOLUME = 1.0
SOUND_EFFECT_VOLUME = 1.0
```

### Step 5: Multiple Agent Setup

For running multiple agents simultaneously:

**Agent 1 (Anna_AI)**:
```python
# bot_info.py
agentname = "Anna"
vb_cable_name = "CABLE Input"
group_chat_port = 54321
```

**Agent 2 (SecondAgent_AI)**:
```python
# bot_info.py
agentname = "SecondAgent"
vb_cable_name = "CABLE-A Input"
group_chat_port = 54322
```

**Agent 3 (ThirdAgent_AI)**:
```python
# bot_info.py
agentname = "ThirdAgent"
vb_cable_name = "CABLE-B Input"
group_chat_port = 54323
```

Each agent must have:
- Unique `agentname`
- Unique `vb_cable_name`
- Unique `group_chat_port`

---

## OPTIONAL TOOLS AND EXTENSIONS

### AI Agent Tools Repository

Extended functionality for specialized tasks.

**Installation**:

```batch
cd C:\
git clone https://github.com/KryptykBioz/AI_Agent_Tools.git
cd AI_Agent_Tools
```

**Available Tools**:
- Game integration modules
- Advanced chat platform connectors
- Custom voice models
- Extended memory systems
- Specialized vision models

**Integration**:

Follow tool-specific README files in each subdirectory. Most tools integrate by copying files to:
```
Anna_AI/tools/installed/[tool_name]/
```

---

## GPU PACKAGE SETUP (RTX 50-SERIES)

[Critical] RTX 50-series GPUs require special PyTorch and transformers packages not available on PyPI.

### Option A: Copy from Working Installation (Recommended)

If you have another Anna_AI instance with working GPU packages:

```batch
# From working installation
cd C:\WorkingAnna_AI
python copy_gpu_packages.py

# This creates: gpu_packages.zip

# Copy to new installation
copy gpu_packages.zip C:\NewAnna_AI\
cd C:\NewAnna_AI
.\venv\Scripts\activate
python -c "import zipfile; zipfile.ZipFile('gpu_packages.zip').extractall('venv/Lib/site-packages')"
```

### Option B: Manual Installation (First-Time Setup)

**Step 1: Install PyTorch Nightly with CUDA 12.6**

```batch
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu126
```

**Step 2: Verify CUDA Support**

```batch
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'CUDA Version: {torch.version.cuda}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
```

Expected output:
```
CUDA Available: True
CUDA Version: 12.6
GPU: NVIDIA GeForce RTX 5070
```

**Step 3: Install Transformers with Custom Build**

[Note] If transformers 4.38.2 fails on RTX 50-series, use development version:

```batch
pip install git+https://github.com/huggingface/transformers.git
```

**Step 4: Test GPU Acceleration**

```python
import torch
from transformers import AutoTokenizer, AutoModel

# Verify GPU
print(f"GPU Available: {torch.cuda.is_available()}")
print(f"GPU Name: {torch.cuda.get_device_name(0)}")

# Test model loading
model = AutoModel.from_pretrained("bert-base-uncased").to("cuda")
print("Model loaded on GPU successfully")
```

### Troubleshooting GPU Issues

**Problem**: CUDA not detected

**Solution 1**: Update GPU drivers
```batch
# Download from: https://www.nvidia.com/Download/index.aspx
# Minimum version: 566.03
```

**Solution 2**: Reinstall PyTorch with correct CUDA version
```batch
pip uninstall torch torchvision torchaudio
pip cache purge
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu126
```

**Problem**: Out of memory errors

**Solution**: Reduce batch size and context window
```python
# config.json
"ollama": {
  "num_ctx": 2000  # Reduce from 3000
}
```

---

## VIRTUAL AUDIO CABLE INSTALLATION

### Why Virtual Audio Cables Are Required

Anna_AI's TTS system and Warudo lip sync animation require virtual audio cables to route audio internally without playing through physical speakers. This enables:

**Core Functionality**:
- **TTS Audio Routing**: Send generated speech to Warudo without external playback
- **Lip Sync Animation**: Warudo captures TTS audio for real-time lip movement
- **Silent Operation**: Agent speaks through avatar without disturbing you
- **Audio Isolation**: Separate agent audio from system sounds

**Multiple Agent Support**:
- Each agent requires a dedicated virtual cable
- Prevents audio conflicts between simultaneous agents
- Enables running multiple VTuber personalities at once

### Virtual Cable Overview

**VB-Audio Virtual Cable** (Primary):
- Source: https://vb-audio.com/Cable/
- Provides: 1 virtual cable (CABLE Input/Output)
- Use: First agent (Anna_AI)
- License: Donationware (free to use, donation appreciated)

**Tala Virtual Audio Cables** (Additional):
- Source: https://github.com/Essence-Platform/TalaVirtualAudioCables-Public
- Provides: 2 additional cables (CABLE-A, CABLE-B)
- Use: Second and third agents
- License: Free

**Cable Assignment**:
```
Agent 1 (Anna_AI)    → CABLE Input/Output
Agent 2 (Second AI)  → CABLE-A Input/Output
Agent 3 (Third AI)   → CABLE-B Input/Output
```

### Step 1: Install VB-Audio Virtual Cable

**Download VB-Audio Cable**:

1. Visit: https://vb-audio.com/Cable/
2. Click "Download" → "VBCABLE_Driver_Pack43.zip"
3. Extract ZIP file to temporary location
4. File size: ~2MB

**Install Primary Cable**:

```batch
# Navigate to extracted folder
cd C:\Downloads\VBCABLE_Driver_Pack43

# Run installer as Administrator
# Right-click VBCABLE_Setup_x64.exe → Run as administrator
```

**Installation Steps**:
1. Click "Install Driver"
2. Windows will show driver installation dialog
3. Click "Install" when prompted
4. Wait for "Installation successful" message
5. Click "OK"
6. **Restart computer** (required for driver activation)

**Verify Installation**:

After restart:
```
1. Right-click speaker icon in taskbar
2. Select "Open Sound settings"
3. Scroll to "Advanced sound options"
4. Click "App volume and device preferences"
5. Check available devices:
   - Should see "CABLE Input (VB-Audio Virtual Cable)"
   - Should see "CABLE Output (VB-Audio Virtual Cable)"
```

### Step 2: Install Tala Virtual Audio Cables (Optional)

[Note]: Only install if running multiple agents simultaneously. Single agent users can skip this step.

**Download Tala Cables**:

1. Visit: https://github.com/Essence-Platform/TalaVirtualAudioCables-Public
2. Click "Releases" (right side)
3. Download latest release: `TalaVirtualAudioCables.zip`
4. Extract to temporary location
5. File size: ~5MB

**Install Additional Cables**:

```batch
# Navigate to extracted folder
cd C:\Downloads\TalaVirtualAudioCables

# Run installer as Administrator
# Right-click Install_Cables.exe → Run as administrator
```

**Installation Steps**:
1. Installer will add CABLE-A and CABLE-B
2. Click "Install" for each cable prompt
3. Wait for completion message
4. **Restart computer** (required)

**Verify Additional Cables**:

After restart:
```
Windows Settings → Sound → Advanced sound options
Should now see:
- CABLE Input/Output (VB-Audio)
- CABLE-A Input/Output (Tala)
- CABLE-B Input/Output (Tala)
```

### Step 3: Configure Windows Audio Settings

**Set Default Devices**:

[Warning] Do NOT set virtual cables as default system devices.

```
1. Right-click speaker icon → "Open Sound settings"
2. Output device: Keep as physical speakers/headphones
3. Input device: Keep as physical microphone
4. Virtual cables will be assigned per-application
```

**Application-Specific Audio**:

Anna_AI will programmatically route audio to virtual cables. Manual configuration:

```
1. Open "App volume and device preferences"
2. Find "Anna_AI" or "python.exe" (when agent is running)
3. Set Output: CABLE Input (VB-Audio Virtual Cable)
4. Agent will automatically handle routing
```

### Step 4: Configure Agent Audio Settings

**Edit bot_info.py**:

```python
# VB-Cable for audio output (use exact device name)
vb_cable_name = "CABLE Input"
```

**For multiple agents**:
```python
# Agent 1 (Anna_AI)
vb_cable_name = "CABLE Input"

# Agent 2
vb_cable_name = "CABLE-A Input"

# Agent 3
vb_cable_name = "CABLE-B Input"
```

**Verify cable names match Windows settings**:
```batch
# List all audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"
```

---

## WARUDO INSTALLATION

### Step 1: Download Warudo

1. Visit: https://warudo.app
2. Create account or sign in
3. Download Warudo installer
4. File size: ~500MB

### Step 2: Install Warudo

1. Run installer as Administrator
2. Accept license agreement
3. Choose installation directory (default: `C:\Program Files\Warudo`)
4. Install (requires ~5GB disk space)
5. Launch Warudo after installation

### Step 3: Initial Setup

**Skip this initial setup by importing the Anna_Animations_Blueprint.json included in the personality/avatar directory directly into Warudo**

**Graphics Settings**:
```
Settings → Graphics:
- Quality: High (adjust based on GPU)
- Resolution: 1920x1080
- Anti-aliasing: MSAA 2x
- V-Sync: On
```

**Audio Settings**:
```
Settings → Audio:
- Lip Sync Input: CABLE Output (VB-Audio Virtual Cable)
- Sample Rate: 48000 Hz
- Buffer Size: 512
```

**Network Settings**:
```
Settings → Network:
- Enable WebSocket Server: [x]
- WebSocket Port: 19190
- Enable External Connections: [x]
```

### Step 4: Load VRM Character

**Import Anna.vrm**:

```
1. File → Import Model → VRM
2. Navigate to: Anna_AI\personality\avatar\Anna.vrm
3. Select Anna.vrm
4. Click "Import"
5. Character loads in scene
```

**Alternative**: Create custom character in VRoid Studio (see next section)

### Step 5: Configure Lip Sync

**Audio Routing**:

```
Warudo must capture audio from CABLE Output (VB-Audio)
Anna_AI outputs to CABLE Input
Windows routes CABLE Input → CABLE Output
Warudo listens to CABLE Output for lip sync
```

**Test Lip Sync**:

```
1. Start Anna_AI agent
2. Agent speaks through TTS
3. Warudo character lips should move in sync
4. Adjust Audio → Lip Sync Sensitivity if needed
```

---

## VROID STUDIO INSTALLATION (optional to edit avatar)

### Step 1: Download VRoid Studio

1. Visit: https://vroid.com/en/studio
2. Click "Download"
3. Choose Windows version
4. File size: ~300MB

### Step 2: Install VRoid Studio

1. Run installer
2. Accept license agreement
3. Choose installation directory
4. Install (requires ~2GB disk space)
5. Launch VRoid Studio

### Step 3: Create or Import Character

**Create New Character**:

```
1. Launch VRoid Studio
2. File → New Project
3. Choose base model (Female/Male)
4. Customize:
   - Face: Eyes, nose, mouth
   - Hair: Style, color, length
   - Body: Height, proportions
   - Clothes: Outfit selection
   - Accessories: Optional items
```

**Import Existing Character**:

```
1. File → Import
2. Select .vroid file
3. Edit as needed
```

### Step 4: Export for Warudo

**Export Settings**:

```
File → Export:
- Format: VRM 0.0 (not VRM 1.0)
- Texture Size: 2048x2048 (recommended)
- Polygon Reduction: Target 30,000 polygons
- Include Blend Shapes: [x]
- Export Expression Morphs: [x]
- Optimize for Runtime: [x]
```

**Save Location**:

```
Export to: Anna_AI\personality\avatar\YourCharacter.vrm
```

### Step 5: Update Agent Configuration

**Edit bot_info.py**:

```python
agentname = "YourCharacterName"
```

**Load in Warudo**:

```
Warudo → File → Import Model → VRM
Select: YourCharacter.vrm
```

---

## VERIFICATION & TESTING

### Test 1: Python Environment

```batch
cd Anna_AI
.\venv\Scripts\activate
python -c "import torch, transformers; print(f'PyTorch: {torch.__version__}'); print(f'Transformers: {transformers.__version__}'); print(f'CUDA: {torch.cuda.is_available()}')"
```

Expected output:
```
PyTorch: 2.10.0a0+git...
Transformers: 4.38.2
CUDA: True
```

### Test 2: Ollama Service

```batch
curl http://localhost:11434/api/version
ollama list
```

Expected output:
```
{"version":"0.x.x"}

NAME                            ID              SIZE      MODIFIED
gemma4:latest           abc123          7.2 GB    X days ago
nomic-embed-text:latest         def456          275 MB    X days ago
```

**Verify .env configuration**:

```batch
# Check if .env exists
dir .env

# View .env settings (Windows)
type .env

# Verify Ollama is using settings
ollama show gemma4:latest --verbose
```

### Test 3: Agent Launch

```batch
cd Anna_AI
.\gui_start.bat
```

Expected behavior:
1. GUI window opens
2. No error messages in console
3. Status shows "Ready"
4. Can send test message

### Test 4: Warudo Connection

```batch
curl http://127.0.0.1:19190
```

Expected output:
```
WebSocket server response or connection accepted
```



### Test 5: Full Integration Test

**Procedure**:

```
1. Start Ollama service
2. Launch Warudo, load character
3. Configure Warudo audio input: CABLE Output
4. Launch Anna_AI agent
5. Send message to agent
6. Verify:
   - Agent responds in chat
   - Voice plays through CABLE
   - Warudo lips sync to voice
   - No console errors
```

**Success Criteria**:
- [x] Agent processes message within 5 seconds
- [x] TTS voice is clear and audible
- [x] Warudo character's lips move in sync
- [x] No dropped audio packets
- [x] GPU utilization visible in nvidia-smi

---

## FINAL FILETREE
**(All features installed)**

├── BASE/
│   ├── api/
│   │   └── main.py
│   ├── config/
│   │   ├── bot_info.py
│   │   └── controls.py
│   ├── core/
│   │   ├── action/
│   │   │   ├── action_constructor.py
│   │   │   └── action_parts.py
│   │   ├── proactive/
│   │   │   ├── proactive_constructor.py
│   │   │   └── proactive_parts.py
│   │   ├── reactive/
│   │   │   ├── reactive_constructor.py
│   │   │   └── reactive_parts.py
│   │   ├── reflective/
│   │   │   ├── reflective_constructor.py
│   │   │   └── reflective_parts.py
│   │   ├── responsive/
│   │   │   ├── responsive_constructor.py
│   │   │   └── responsive_parts.py
│   │   ├── __init__.py
│   │   ├── action_state_manager.py
│   │   ├── ai_core.py
│   │   ├── clean_response.py
│   │   ├── cognitive_filter.py
│   │   ├── cognitive_loop_manager.py
│   │   ├── cognitive_loop_recovery.py
│   │   ├── config.py
│   │   ├── context_detector.py
│   │   ├── control_manager.py
│   │   ├── core_hot_reload_manager.py
│   │   ├── core_initializer.py
│   │   ├── dynamic_control_initializer.py
│   │   ├── logger.py
│   │   ├── processing_delegator.py
│   │   ├── response_decider.py
│   │   ├── speak_judge.py
│   │   ├── streaming_response_handler.py
│   │   ├── thinking_modes.py
│   │   ├── thought_buffer.py
│   │   ├── thought_processor.py
│   │   └── tool_hot_reload_manager.py
│   ├── handlers/
│   │   ├── base_tool.py
│   │   ├── chat_engagement.py
│   │   ├── chat_event_converter.py
│   │   ├── content_filter.py
│   │   ├── internal_tool_interface.py
│   │   ├── internal_tool_manager.py
│   │   ├── tool_instruction_builder.py
│   │   ├── tool_lifecycle.py
│   │   ├── tool_manager.py
│   │   └── tts_interface.py
│   ├── interface/
│   │   ├── dynamic_tool_panel_loader.py
│   │   ├── gui_chat_view.py
│   │   ├── gui_components.py
│   │   ├── gui_config_view.py
│   │   ├── gui_controls_view.py
│   │   ├── gui_files_view.py
│   │   ├── gui_info_view.py
│   │   ├── gui_interface.py
│   │   ├── gui_message_handler.py
│   │   ├── gui_message_processor.py
│   │   ├── gui_session_files_panel.py
│   │   ├── gui_theme_manager.py
│   │   ├── gui_themes.py
│   │   ├── gui_tools_view.py
│   │   ├── gui_ui_builder.py
│   │   └── voice_manager.py
│   ├── recall/
│   │   ├── __init__.py
│   │   ├── embed_document.py
│   │   ├── embed_personality.py
│   │   ├── memory_encryption.py
│   │   ├── memory_integration.py
│   │   ├── memory_manager.py
│   │   ├── memory_search.py
│   │   ├── session_file_manager.py
│   │   └── summarizer.py
│   ├── services/
│   │   ├── voice_hub_client.py
│   │   ├── voice_hub_protocol.py
│   │   └── voice_hub_server.py
│   ├── tools/
│   │   ├── installed/
│   │   │   ├── bing_search/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── README.md
│   │   │   │   └── tool.py
│   │   │   ├── calculator/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── calendar/
│   │   │   │   ├── calendar_manager.py
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── README.md
│   │   │   │   └── tool.py
│   │   │   ├── canvas/
│   │   │   │   ├── canvas_memory.json
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── README.md
│   │   │   │   └── tool.py
│   │   │   ├── coding_VS_Code/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── dice_roller/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── README.md
│   │   │   │   └── tool.py
│   │   │   ├── discord_bot/
│   │   │   │   ├── component.py
│   │   │   │   ├── config.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── discord_chat/
│   │   │   │   ├── component.py
│   │   │   │   ├── config.py
│   │   │   │   ├── discord_voice_sink.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── duckduckgo_search/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── README.md
│   │   │   │   └── tool.py
│   │   │   ├── game_guide/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── game_vision/
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── group_chat/
│   │   │   │   ├── config.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── image_generator/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── service.py
│   │   │   │   └── tool.py
│   │   │   ├── league_of_legends/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── mcp_bridge/
│   │   │   │   ├── information.json
│   │   │   │   ├── integration_guide.md
│   │   │   │   └── tool.py
│   │   │   ├── memory_search/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── minecraft/
│   │   │   │   ├── minecraft_bot/
│   │   │   │   │   ├── actions/
│   │   │   │   │   │   ├── building.js
│   │   │   │   │   │   ├── combat.js
│   │   │   │   │   │   ├── gathering.js
│   │   │   │   │   │   ├── interaction.js
│   │   │   │   │   │   ├── movement.js
│   │   │   │   │   │   ├── player-interaction.js
│   │   │   │   │   │   └── utility.js
│   │   │   │   │   ├── .env
│   │   │   │   │   ├── bot-actions.js
│   │   │   │   │   ├── bot.js
│   │   │   │   │   ├── command-parser.js
│   │   │   │   │   ├── minecraft_bot_POV.html
│   │   │   │   │   ├── package-lock.json
│   │   │   │   │   ├── package.json
│   │   │   │   │   ├── server.js
│   │   │   │   │   └── world-info.js
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── mc_start.bat
│   │   │   │   └── tool.py
│   │   │   ├── notes/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── notes.py
│   │   │   │   └── tool.py
│   │   │   ├── opencv_vision/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── README.md
│   │   │   │   └── tool.py
│   │   │   ├── reminders/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── reminders.py
│   │   │   │   └── tool.py
│   │   │   ├── screenshot_vision/
│   │   │   │   ├── gui.py
│   │   │   │   ├── information.json
│   │   │   │   ├── new_component.py
│   │   │   │   └── tool.py
│   │   │   ├── sound_effects/
│   │   │   │   ├── effects/
│   │   │   │   │   ├── hello.mp3
│   │   │   │   │   ├── impostor.mp3
│   │   │   │   │   ├── jumpscare.mp3
│   │   │   │   │   └── squee.mp3
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── system_info/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── twitch_chat/
│   │   │   │   ├── component.py
│   │   │   │   ├── config.py
│   │   │   │   ├── gui.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── unity_animation/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── unity_controller/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── user_details/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   ├── README.md
│   │   │   │   └── tool.py
│   │   │   ├── warudo/
│   │   │   │   ├── animate_avatar.py
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── web_fetch/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   ├── wiki_search/
│   │   │   │   ├── component.py
│   │   │   │   ├── information.json
│   │   │   │   └── tool.py
│   │   │   └── youtube_chat/
│   │   │       ├── component.py
│   │   │       ├── config.py
│   │   │       ├── information.json
│   │   │       └── tool.py
│   │   ├── internal/
│   │   │   ├── pyttsx3/
│   │   │   │   ├── information.json
│   │   │   │   ├── pyttsx3_engine.py
│   │   │   │   └── tool.py
│   │   │   ├── speaker_verification/
│   │   │   │   ├── information.json
│   │   │   │   ├── README.md
│   │   │   │   ├── speaker_verification_engine.py
│   │   │   │   └── tool.py
│   │   │   ├── vosk/
│   │   │   │   ├── information.json
│   │   │   │   ├── tool.py
│   │   │   │   └── vosk_engine.py
│   │   │   ├── whisper/
│   │   │   │   ├── information.json
│   │   │   │   ├── tool.py
│   │   │   │   └── whisper_engine.py
│   │   │   └── xtts/
│   │   │       ├── information.json
│   │   │       ├── tool.py
│   │   │       ├── xtts_config.json
│   │   │       └── xtts_engine.py
│   │   └── __init__.py
│   └── __init__.py
├── Documentation/
│   ├── CognitiveProcessingLoop.html
│   └── OVERVIEW.md
├── models/
│   ├── tts_models--multilingual--multi-dataset--xtts_v2/
│   │   ├── config.json
│   │   ├── hash.md5
│   │   ├── model.pth
│   │   ├── speakers_xtts.pth
│   │   ├── tos_agreed.txt
│   │   └── vocab.json
│   └── vosk-model-en-us-0.42-gigaspeech/
│       ├── am/
│       │   ├── cmvn_opts
│       │   ├── final.mdl
│       │   ├── frame_subsampling_factor
│       │   ├── phones.txt
│       │   └── tree
│       ├── conf/
│       │   ├── ivector.conf
│       │   ├── mfcc.conf
│       │   └── model.conf
│       ├── graph/
│       │   ├── phones/
│       │   │   ├── align_lexicon.int
│       │   │   ├── align_lexicon.txt
│       │   │   ├── disambig.int
│       │   │   ├── disambig.txt
│       │   │   ├── optional_silence.csl
│       │   │   ├── optional_silence.int
│       │   │   ├── optional_silence.txt
│       │   │   ├── silence.csl
│       │   │   ├── word_boundary.int
│       │   │   └── word_boundary.txt
│       │   ├── disambig_tid.int
│       │   ├── HCLG.fst
│       │   ├── num_pdfs
│       │   ├── phones.txt
│       │   └── words.txt
│       ├── ivector/
│       │   ├── final.dubm
│       │   ├── final.ie
│       │   ├── final.mat
│       │   ├── global_cmvn.stats
│       │   ├── online_cmvn.conf
│       │   ├── splice.conf
│       │   └── splice_opts
│       ├── rescore/
│       │   ├── G.carpa
│       │   └── G.fst
│       ├── rnnlm/
│       │   ├── feat_embedding.final.mat
│       │   ├── final.raw
│       │   ├── special_symbol_opts.conf
│       │   ├── special_symbol_opts.txt
│       │   └── word_feats.txt
│       └── README
├── personality/
│   ├── avatar/
│   │   ├── Anna.vrm
│   │   ├── Anna_Animation_Profile.json
│   │   ├── Anna_Animations_Blueprint.json
│   │   ├── Anna_Character_Asset.json
│   │   ├── Anna_Expression_Profile.json
│   │   └── anna_model.vroid
│   ├── base_memory/
│   │   ├── base_files/
│   │   │   ├── embeddings/
│   │   │   │   └── mecha_break_embeddings.json
│   │   │   └── mecha_break.md
│   │   ├── base_personality/
│   │   │   ├── embeddings/
│   │   │   ├── anna_response_training.py
│   │   │   └── anna_thought_training.py
│   │   └── game_guides/
│   │       ├── embeddings/
│   │       └── mecha_break.md
│   ├── memory/
│   │   ├── .keycheck
│   │   ├── .machine_salt
│   │   ├── .machine_secret
│   │   ├── .salt
│   │   ├── calendar.json
│   │   ├── long_memory.json
│   │   ├── long_memory.json.bak
│   │   ├── medium_memory.json
│   │   ├── medium_memory.json.bak
│   │   ├── notes.json
│   │   ├── reminders.json
│   │   ├── short_memory.json
│   │   ├── short_memory.json.bak
│   │   └── user_details.json
│   ├── prompts/
│   │   └── personality_prompt_parts.py
│   ├── voice/
│   │   ├── anna_voice_sample.mp3
│   │   └── raven_voice_sample.mp3
│   └── config.json
├── user_tools/
│   ├── voice_recording/
│   │   ├── guided_record.py
│   │   ├── INSTALLATION.md
│   │   ├── interactive_record.py
│   │   ├── quick_record.py
│   │   ├── record_voice_sample.py
│   │   └── RECORDING_GUIDE.md
│   ├── change_memory_password.py
│   └── decrypt_memory.py
├── .env
├── .env.template
├── .gitignore
├── MINECRAFT_BOT_START.bat
├── README.md
├── requirements.txt
├── SETUP.md
└── START.bat


---

## TROUBLESHOOTING

### Python Issues

**Problem**: `python` command not recognized

**Solution**: Add Python to PATH
```batch
# Add to System Environment Variables
setx PATH "%PATH%;C:\Python311;C:\Python311\Scripts"
# Restart Command Prompt
```

**Problem**: Virtual environment not activating

**Solution 1**: Use full path
```batch
C:\Anna_AI\venv\Scripts\activate.bat
```

**Solution 2**: Check execution policy (PowerShell)
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

**Problem**: `pip install` fails with compiler errors

**Solution**: Install Visual Studio Build Tools
```
Follow Step 4 of Python Installation section
```

### GPU Issues

**Problem**: CUDA not available

**Solution 1**: Update GPU drivers
```batch
# Download from NVIDIA website
# Minimum version: 566.03 for RTX 50-series
```

**Solution 2**: Reinstall PyTorch
```batch
pip uninstall torch torchvision torchaudio
pip cache purge
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu126
```

**Solution 3**: Check GPU visibility
```batch
nvidia-smi
```

**Problem**: Out of memory errors

**Solution**: Reduce model context in config.json
```json
{
  "ollama": {
    "num_ctx": 2000
  }
}
```

### Audio Issues

**Problem**: No audio output from agent

**Solution 1**: Verify VB-Cable installation
```
Windows Settings → Sound → Check for CABLE Input/Output
```

**Solution 2**: Check bot_info.py configuration
```python
vb_cable_name = "CABLE Input"  # Must match exactly
```

**Solution 3**: Test audio device
```batch
python -c "import sounddevice as sd; print(sd.query_devices())"
# Verify CABLE Input is listed
```

**Problem**: Audio glitches or stuttering

**Solution 1**: Increase buffer size in Warudo
```
Warudo → Settings → Audio → Buffer Size: 1024
```

**Solution 2**: Match sample rates
```
Windows Sound Settings:
Right-click CABLE Input → Properties → Advanced
Default Format: 2 channel, 16 bit, 22050 Hz

config.json: (if applicable to TTS settings)
Sample rate: 22050
```

**Solution 3**: Reduce system load
```
Close unnecessary applications
Lower Warudo graphics quality
Use smaller Whisper model
Reduce Ollama context window
```

### Ollama Issues

**Problem**: Ollama service won't start

**Solution 1**: Check if already running
```batch
tasklist | findstr ollama
```

**Solution 2**: Restart service
```batch
net stop ollama
net start ollama
```

**Solution 3**: Check logs
```batch
type "%USERPROFILE%\.ollama\logs\server.log"
```

**Problem**: Model download fails

**Solution**: Check disk space and retry
```batch
ollama pull gemma4:latest
```

**Problem**: Connection refused errors

**Solution**: Check endpoint in config.json
```json
{
  "ollama": {
    "endpoint": "http://localhost:11434"
  }
}
```

### Warudo Issues

**Problem**: Character doesn't load

**Solution 1**: Verify VRM file integrity
```
- Re-export from VRoid Studio
- Check file size (should be >5MB)
- Ensure VRM 0.0 format (not VRM 1.0)
```

**Solution 2**: Check Warudo logs
```
%LOCALAPPDATA%\Warudo\logs\
```

**Problem**: Lip sync not working

**Solution 1**: Verify audio routing
```
Warudo → Settings → Audio → Lip Sync Input: CABLE Output
Agent → bot_info.py → vb_cable_name = "CABLE Input"
```

**Solution 2**: Test audio flow
```
1. Launch agent
2. Agent speaks
3. Check Windows Volume Mixer: CABLE Output should show activity
4. Warudo should detect audio
```

**Solution 3**: Adjust sensitivity
```
Warudo → Character → Lip Sync Sensitivity: 70-90%
```

**Problem**: WebSocket connection fails

**Solution**: Verify Warudo WebSocket settings
```
Warudo → Settings → Network:
- Enable WebSocket Server: [x]
- Port: 19190 (must match config.json)
- Enable External Connections: [x]

config.json:
"warudo": {
  "websocket_url": "ws://127.0.0.1:19190"
}
```

### Environment Configuration Issues

**Problem**: Ollama not applying .env settings

**Solution 1**: Verify .env file location
```batch
# .env must be in Anna_AI root directory
dir .env
```

**Solution 2**: Check for syntax errors
```bash
# Common mistakes:
OLLAMA_KEEP_ALIVE=24h     # Correct
OLLAMA_KEEP_ALIVE="24h"   # Incorrect (no quotes)
OLLAMA_KEEP_ALIVE = 24h   # Incorrect (no spaces around =)
```

**Solution 3**: Restart Ollama service
```batch
net stop ollama
net start ollama
```

**Problem**: Temperature settings not working

**Solution**: Verify temperature hierarchy
```
.env settings (OLLAMA_TEMPERATURE_*) override config.json
config.json settings override bot_info.py defaults
Both files must be configured correctly
```

**Problem**: Models unloading too quickly

**Solution**: Increase keep-alive time
```bash
# .env
OLLAMA_KEEP_ALIVE=24h     # Keep models loaded for 24 hours
```

**Problem**: Context window errors

**Solution**: Align context settings
```bash
# .env
OLLAMA_CONTEXT_LENGTH=8192

# config.json
"ollama": {
  "num_ctx": 3000  # Must be <= OLLAMA_CONTEXT_LENGTH
}
```

---

## COMMON ISSUES

### "ModuleNotFoundError" Errors

Always activate virtual environment before running:
```batch
cd Anna_AI
.\venv\Scripts\activate
python your_script.py
```

### Virtual Environment Not Working

Recreate virtual environment:
```batch
rmdir /s /q venv
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Slow Performance

**Check GPU usage**:
```batch
nvidia-smi
```

**Optimize settings**:
- Reduce Whisper model size (large → medium → base)
- Use int8 compute type instead of float16
- Reduce Ollama context window
- Lower Warudo graphics quality

### Memory Leaks

**Restart agent periodically**:
```python
# Add to main loop
import psutil
import os

process = psutil.Process(os.getpid())
if process.memory_info().rss > 8 * 1024**3:  # 8GB
    print("Memory limit reached, restarting...")
    # Implement graceful restart
```

### Models Not Loading

**Clear cache**:
```batch
# Clear HuggingFace cache
rmdir /s /q "%USERPROFILE%\.cache\huggingface"

# Clear Ollama cache
ollama rm --all
ollama pull gemma4:latest
```

### Agent Freezes or Crashes

**Enable debug logging in controls.py**:
```python
LOG_TOOL_EXECUTION = True
LOG_PROMPT_CONSTRUCTION = True
LOG_RESPONSE_PROCESSING = True
LOG_SYSTEM_INFORMATION = True
```

**Check logs**:
- Console output
- Ollama logs: `%USERPROFILE%\.ollama\logs\server.log`
- Warudo logs: `%LOCALAPPDATA%\Warudo\logs\`

---

## ADDITIONAL RESOURCES

### Documentation Links

- **Anna_AI Repository**: https://github.com/KryptykBioz/Anna_AI
- **AI Agent Tools**: https://github.com/KryptykBioz/AI_Agent_Tools
- **VB-Audio Virtual Cable**: https://vb-audio.com/Cable/
- **Tala Virtual Cables**: https://github.com/Essence-Platform/TalaVirtualAudioCables-Public
- **Python**: https://docs.python.org/3.11/
- **PyTorch**: https://pytorch.org/docs/stable/index.html
- **Transformers**: https://huggingface.co/docs/transformers/
- **Faster Whisper**: https://github.com/SYSTRAN/faster-whisper
- **Coqui TTS**: https://docs.coqui.ai/en/latest/
- **Ollama**: https://github.com/ollama/ollama/tree/main/docs
- **Warudo**: https://docs.warudo.app/
- **VRoid Studio**: https://vroid.com/en/studio

### Community Support

- **YouTube**: https://www.youtube.com/@KryptykBioz
- **GitHub**: https://github.com/KryptykBioz
- **Twitch**: https://www.twitch.tv/kryptykbioz

### Update Policy

- **Agent Framework**: Check for updates periodically
- **Python Packages**: Update cautiously, test thoroughly, use venv to ensure package versions remain stable
- **GPU Drivers**: Update whenever available
- **Ollama**: Update when new features are needed
- **Warudo**: Update when stable releases available
- **VRoid Studio**: Update for new features

---

## CHANGELOG

### Version 1.1.0 (2025-01-02)
- Updated configuration instructions to match actual file structure
- Changed from .env to bot_info.py and config.json configuration
- Added comprehensive .env file documentation for Ollama optimization
- Added OLLAMA_KEEP_ALIVE, OLLAMA_CONTEXT_LENGTH, and performance settings
- Added temperature configuration (ACTION, COGNITIVE, RESPONSE modes)
- Corrected Warudo WebSocket port from 7890 to 19190
- Added group_chat_port configuration for multiple agents
- Clarified VB-Cable configuration syntax
- Updated Ollama model configuration examples
- Enhanced multiple agent setup instructions
- Added .env troubleshooting section
- Added YouTube integration configuration (optional)

### Version 1.0.0 (2025-01-02)
- Initial release
- RTX 50-series GPU support documented
- Comprehensive installation instructions
- Ollama, Warudo, VRoid Studio integration guides
- Troubleshooting section added

---

## SUPPORT

For technical support:
1. Check this SETUP.md file
2. Review troubleshooting section
3. Check project README.md
4. Search existing GitHub issues
5. Create new issue with:
   - Error message (full text)
   - Python version: `python --version`
   - PyTorch version: `python -c "import torch; print(torch.__version__)"`
   - GPU info: `nvidia-smi`
   - Configuration files: bot_info.py, config.json, .env
   - Steps to reproduce

---

[Note]: This setup guide is maintained for RTX 50-series GPU compatibility. For other GPU architectures, standard PyPI packages may be used without the special GPU package copy procedure.

**Last Updated**: 2026 May 05
**Compatible With**: Python 3.11.9, PyTorch 2.10.0a0, Transformers 4.38.2