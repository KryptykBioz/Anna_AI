# Filename: personality/bot_info.py
"""
Bot Identity and Model Configuration
"""

# ========================================================================
# BOT AND USER IDENTITY
# ========================================================================

# Bot's name (how it refers to itself)
agentname = "Anna"

# User's name (how bot refers to the user)
username = "User"

# User's in-game username (for game-specific interactions)
game_username = "Player"

# ========================================================================
# MODEL CONFIGURATION
# ========================================================================

# PRIMARY MODELS (Fast - 2-6s each)
# Used for most cognitive operations
thoughtmodel = "gemma3:12b-it-q4_K_M"
responsemodel = "gemma3:12b-it-q4_K_M"
toolmodel = "gemma3:12b-it-q4_K_M"
actionmodel = "gemma3:12b-it-q4_K_M"

# SPECIALIZED MODELS
visionmodel = "gemma3:12b-it-q4_K_M"
embedmodel = "nomic-embed-text:latest"

# ALTERNATIVE MODELS (for experimentation)
# qwen3-vl:8b-instruct-q4_K_M
# qwen3-vl:8b-thinking-q4_K_M

# OPTIONAL: Complex reasoning (use sparingly, slower)
# reasoning_model = "gemma3:12b-it-q4_K_M"

# ========================================================================
# VOICE CONFIGURATION
# ========================================================================

# Voice index (for pyttsx3 system voices)
# Use test_voices.py to find available voices and their indices
voiceIndex = 0

# VB-Cable audio output device name
# Used for routing TTS audio to virtual audio cable
# Must match exact device name in Windows Sound Settings
vb_cable_name = "CABLE Input"

# NOTE: TTS engine selection (XTTS, GPT-SoVITS, pyttsx3) is now controlled
# dynamically via personality/controls.py and tool priority system.
# See BASE/tools/internal/ for available TTS engines.

# ========================================================================
# MULTI-AGENT CONFIGURATION
# ========================================================================

# Group Chat Server Port
# Each agent instance needs a unique port for Voice Hub communication
# Examples: 54321 (first agent), 54322 (second agent), etc.
# Only used when GROUP_CHAT = True in controls.py
group_chat_port = 54321

# ========================================================================
# NOTES
# ========================================================================
#
# Model Selection:
#   - All models should be available in your Ollama installation
#   - Verify with: ollama list
#   - Pull models with: ollama pull <model_name>
#
# Voice Configuration:
#   - voiceIndex: Run tools/voice_test.py to find available system voices
#   - vb_cable_name: Check Windows Sound Settings > Playback Devices
#
# TTS Engine Selection:
#   - Controlled via personality/controls.py (dynamic tool system)
#   - Available engines: GPT-SoVITS, XTTS, pyttsx3
#   - Priority determines default: highest priority = enabled at startup
#
# Multi-Agent Setup:
#   - Each agent needs unique group_chat_port (54321, 54322, 54323, ...)
#   - Enable GROUP_CHAT in controls.py to activate Voice Hub
#   - First agent to start will spawn the Voice Hub server
#
# ========================================================================