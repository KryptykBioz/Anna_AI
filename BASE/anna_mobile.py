#!/usr/bin/env python3
# Filename: BASE/bot_mobile.py
"""
Mobile Entry Point - Termux/Android
=====================================
Thin wrapper around the full agentic system (AICore) stripped of:
  - GUI / hot-reload managers
  - GPU-dependent internal TTS (XTTS / Whisper)
  - Discord / YouTube / Twitch integrations
  - Streaming response handler

Voice input:  Vosk offline VAD listener — always-on, no push-to-talk.
              Passively monitors the microphone, detects speech onset via RMS
              threshold, captures until trailing silence, submits to AICore.
              Mutes itself while TTS is playing to prevent feedback.
Voice output: termux-tts-speak (Termux:API) — blocking call so the mute flag
              is accurate.
Text input:   stdin fallback mode (--mode text)
Interaction:  Full reactive/proactive/reflective cognitive loop + memory system.

Requirements (Termux):
    pkg install python termux-api
    pip install vosk pyaudio requests beautifulsoup4 ollama

    Vosk model (small ~40 MB, works well on mobile):
        wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
        unzip vosk-model-small-en-us-0.15.zip -d $HOME

Usage:
    python bot_mobile.py                              # prompted mode select
    python bot_mobile.py --mode voice                 # passive listener
    python bot_mobile.py --mode voice --model /path/to/vosk-model
    python bot_mobile.py --mode text                  # typed input only

Background (Termux):
    nohup python bot_mobile.py --mode voice > agent.log 2>&1 &
    # or with tmux/screen for an attached session you can check on:
    tmux new -s agent "python bot_mobile.py --mode voice"
"""

import sys
import os
import asyncio
import threading
import time
import json
import argparse
import audioop
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Project root resolution
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Personality imports — no BASE/ dependencies, always safe to import first
# ---------------------------------------------------------------------------
from personality.bot_info import (
    botname, username, agentname,
    botTColor, userTColor, systemTColor, errorTColor, resetTColor
)
from personality import controls as controls_module

# ---------------------------------------------------------------------------
# Vosk / PyAudio — optional, only required in voice mode
# ---------------------------------------------------------------------------
try:
    import pyaudio
    from vosk import Model as VoskModel, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

# ---------------------------------------------------------------------------
# Passive listener tuning constants
# All RMS / timing values can be adjusted here without touching logic.
# ---------------------------------------------------------------------------
VOSK_SAMPLE_RATE   = 16000   # Hz — Vosk small models expect 16 kHz
VOSK_CHUNK         = 2048    # Frames per PyAudio read — smaller = lower latency
VAD_SPEECH_RMS     = 500     # RMS threshold to consider a chunk as speech
VAD_SPEECH_ONSET   = 3       # Consecutive speech chunks needed to start capture
VAD_SILENCE_SECS   = 1.8     # Seconds of trailing silence to end an utterance
VAD_MAX_SECS       = 45.0    # Hard cap on utterance length
VAD_IDLE_SLEEP     = 0.05    # Seconds to sleep between idle monitor iterations


# ============================================================================
# TTS — termux-tts-speak
# ============================================================================

# Global flag: True while TTS is actively playing.
# The passive listener checks this and skips processing while it is set,
# preventing the mic from picking up the agent's own voice.
_tts_active = threading.Event()


def speak(text: str) -> None:
    """
    Speak text via termux-tts-speak.

    Blocking: sets _tts_active for the full duration so the passive mic
    listener suppresses itself, then clears it when playback finishes.
    termux-tts-speak itself blocks until speech completes.
    """
    if not text or not text.strip():
        return
    safe = text.replace('"', "'").replace('`', "'").replace('\n', ' ')
    _tts_active.set()
    try:
        os.system(f'termux-tts-speak "{safe}"')
    finally:
        _tts_active.clear()


# ============================================================================
# Passive Vosk VAD listener
# ============================================================================

class PassiveVoskListener:
    """
    Always-on VAD microphone listener using Vosk for offline STT.

    Architecture:
    - One persistent PyAudio input stream, open for the lifetime of the process.
    - A dedicated daemon thread runs _monitor_loop() continuously.
    - State machine: IDLE → CAPTURING → TRANSCRIBING → IDLE
    - While TTS is playing (_tts_active is set) the loop drains audio and
      discards it so no mic data accumulates during playback.
    - Recognised utterances are placed onto a thread-safe Queue. The caller
      drains this queue from its own thread.

    The stream is intentionally kept open rather than opened/closed per
    utterance — on Android/Termux this avoids audio routing delays that
    can cause the first syllable of an utterance to be clipped.
    """

    def __init__(self, model_path: str, result_callback):
        """
        Args:
            model_path:       Path to unpacked Vosk model directory.
            result_callback:  Callable[str] called from the listener thread
                              with each recognised utterance. Must be thread-safe.
        """
        if not VOSK_AVAILABLE:
            raise RuntimeError(
                "vosk and pyaudio are required.\n"
                "Install: pip install vosk pyaudio"
            )
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Vosk model not found: {model_path}\n"
                "Download a model from https://alphacephei.com/vosk/models\n"
                "Recommended for mobile: vosk-model-small-en-us-0.15"
            )

        print(systemTColor + f"[Voice] Loading Vosk model: {model_path}" + resetTColor)
        self._model    = VoskModel(model_path)
        self._audio    = pyaudio.PyAudio()
        self._callback = result_callback
        self._stop     = threading.Event()
        self._thread: Optional[threading.Thread] = None

        print(systemTColor + "[Voice] Passive listener ready." + resetTColor)

    # -----------------------------------------------------------------------

    def start(self) -> None:
        """Start the background listener thread."""
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="PassiveVoiceListener"
        )
        self._thread.start()
        print(systemTColor + "[Voice] Passive microphone listening started." + resetTColor)

    def stop(self) -> None:
        """Signal the listener to stop and wait for the thread."""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=4.0)

    def cleanup(self) -> None:
        self.stop()
        try:
            self._audio.terminate()
        except Exception:
            pass

    # -----------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        """
        Core VAD loop.

        States:
          idle      — listening for speech onset above VAD_SPEECH_RMS
          capturing — accumulating audio frames into current utterance
          done      — utterance ended, hand off to Vosk, reset to idle
        """
        stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=VOSK_SAMPLE_RATE,
            input=True,
            frames_per_buffer=VOSK_CHUNK
        )

        max_silent_chunks = int(VAD_SILENCE_SECS * VOSK_SAMPLE_RATE / VOSK_CHUNK)
        max_capture_chunks = int(VAD_MAX_SECS * VOSK_SAMPLE_RATE / VOSK_CHUNK)

        try:
            while not self._stop.is_set():
                # ── MUTE during TTS to avoid mic feedback ──────────────────
                if _tts_active.is_set():
                    # Drain the buffer so no stale audio queues up
                    try:
                        stream.read(VOSK_CHUNK, exception_on_overflow=False)
                    except Exception:
                        pass
                    time.sleep(VAD_IDLE_SLEEP)
                    continue

                # ── IDLE: wait for speech onset ────────────────────────────
                onset_count    = 0
                capture_frames = []
                silent_chunks  = 0

                while not self._stop.is_set() and not _tts_active.is_set():
                    try:
                        data = stream.read(VOSK_CHUNK, exception_on_overflow=False)
                    except Exception:
                        time.sleep(VAD_IDLE_SLEEP)
                        continue

                    rms = audioop.rms(data, 2)

                    if rms >= VAD_SPEECH_RMS:
                        onset_count += 1
                        capture_frames.append(data)
                        if onset_count >= VAD_SPEECH_ONSET:
                            # Speech confirmed — transition to CAPTURING
                            break
                    else:
                        # Reset onset counter on any silent frame
                        onset_count = 0
                        capture_frames = []

                if self._stop.is_set():
                    break

                # ── CAPTURING: collect until trailing silence or hard cap ──
                print(systemTColor + "[Voice] Speech detected, capturing..." + resetTColor)

                while not self._stop.is_set() and not _tts_active.is_set():
                    try:
                        data = stream.read(VOSK_CHUNK, exception_on_overflow=False)
                    except Exception:
                        break

                    capture_frames.append(data)
                    rms = audioop.rms(data, 2)

                    if rms < VAD_SPEECH_RMS:
                        silent_chunks += 1
                        if silent_chunks >= max_silent_chunks:
                            break
                    else:
                        silent_chunks = 0

                    if len(capture_frames) >= max_capture_chunks:
                        print(systemTColor + "[Voice] Max utterance length reached." + resetTColor)
                        break

                # If TTS fired mid-capture, discard — likely feedback
                if _tts_active.is_set():
                    print(systemTColor + "[Voice] TTS active mid-capture — discarded." + resetTColor)
                    continue

                # ── TRANSCRIBING ───────────────────────────────────────────
                if not capture_frames:
                    continue

                rec = KaldiRecognizer(self._model, VOSK_SAMPLE_RATE)
                for frame in capture_frames:
                    rec.AcceptWaveform(frame)

                result = json.loads(rec.FinalResult())
                text = result.get("text", "").strip()

                if text:
                    print(userTColor + f"{username} (voice): {text}" + resetTColor)
                    self._callback(text)
                else:
                    print(systemTColor + "[Voice] Utterance below recognition threshold, ignored." + resetTColor)

        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass


# ============================================================================
# Mobile Config
# ============================================================================

class MobileConfig:
    """
    Singleton Config compatible with AICore.
    Reads personality/config.json, then hard-overrides all mobile-unsafe flags.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, project_root: Path):
        if getattr(self, '_ready', False):
            return
        self._ready = True

        cfg_path = project_root / "personality" / "config.json"
        data: dict = {}
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    pass

        # Core model / endpoint — from config.json
        self.ollama_endpoint  = data.get("ollama_endpoint",  "http://localhost:11434")
        self.thought_model    = data.get("thought_model",    "llama3.2:3b")
        self.text_model       = data.get("text_model",       "llama3.2:3b")
        self.vision_model     = data.get("vision_model",     "")
        self.embed_model      = data.get("embed_model",      "")

        # Log verbosity — inherit from config.json where present
        self.LOG_TOOL_EXECUTION      = data.get("LOG_TOOL_EXECUTION",      True)
        self.LOG_REACTIVE_PROMPT     = data.get("LOG_REACTIVE_PROMPT",     False)
        self.LOG_REFLECTIVE_PROMPT   = data.get("LOG_REFLECTIVE_PROMPT",   False)
        self.LOG_PROACTIVE_PROMPT    = data.get("LOG_PROACTIVE_PROMPT",    False)
        self.LOG_RESPONSIVE_PROMPT   = data.get("LOG_RESPONSIVE_PROMPT",   False)
        self.LOG_ACTION_PROMPT       = data.get("LOG_ACTION_PROMPT",       False)
        self.LOG_RESPONSE_PROCESSING = data.get("LOG_RESPONSE_PROCESSING", True)
        self.LOG_SYSTEM_INFORMATION  = data.get("LOG_SYSTEM_INFORMATION",  True)
        self.SHOW_CHAT               = data.get("SHOW_CHAT",               False)

        # Back-reference set by AICore
        self.ai_core = None

        # Mobile hard-overrides — never enabled on device regardless of config.json
        self.ENABLE_GUI        = False
        self.ENABLE_HOT_RELOAD = False
        self.USE_GPU_VOICE     = False
        self.USE_XTTS          = False
        self.USE_WHISPER       = False
        self.USE_PYTTSX3       = False
        self.USE_DISCORD       = False
        self.USE_YOUTUBE       = False
        self.USE_TWITCH        = False
        self.STREAMING_ENABLED = False


# ============================================================================
# Controls patch
# ============================================================================

def _patch_controls_for_mobile(ctrl_module) -> None:
    """Mutate the live controls module before AICore reads it."""
    overrides = {
        "ENABLE_TOOL_HOT_RELOAD": False,
        "ENABLE_CORE_HOT_RELOAD": False,
        "USE_GPU_VOICE":          False,
        "USE_XTTS":               False,
        "USE_WHISPER":            False,
        "USE_PYTTSX3":            False,
        "IN_DISCORD":             False,
        "IN_YOUTUBE":             False,
        "IN_TWITCH":              False,
        "CHAT_ENGAGEMENT":        False,
        "ENABLE_STREAMING":       False,
        "PRELOAD_MODELS":         False,
    }
    for attr, val in overrides.items():
        setattr(ctrl_module, attr, val)


# ============================================================================
# Mobile AI Core wrapper
# ============================================================================

class MobileAICore:
    """
    Boots the real AICore with mobile-safe config/controls.
    Exposes send() as a synchronous blocking call for use from any thread.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config = MobileConfig(project_root)
        _patch_controls_for_mobile(controls_module)

        print(systemTColor + "[Mobile] Initialising AI Core..." + resetTColor)

        from BASE.core.ai_core import AICore

        self._core = AICore(
            config=self.config,
            controls_module=controls_module,
            project_root=project_root,
            gui_logger=None
        )
        self._loop: asyncio.AbstractEventLoop = self._core.main_loop

        print(systemTColor + "[Mobile] AI Core ready." + resetTColor)

    def send(self, message: str) -> Optional[str]:
        """Submit a message to AICore, block until reply. Thread-safe."""
        if not message or not message.strip():
            return None
        future = asyncio.run_coroutine_threadsafe(
            self._core.process_user_message(
                message=message,
                source="mobile",
                user_id="local_user"
            ),
            self._loop
        )
        try:
            return future.result(timeout=120.0)
        except Exception as e:
            print(errorTColor + f"[Error] send() failed: {e}" + resetTColor)
            return None

    def shutdown(self) -> None:
        self._core.shutdown()


# ============================================================================
# Shared response handler — used by both voice and text paths
# ============================================================================

def _handle_reply(reply: Optional[str]) -> None:
    """Print and speak any non-empty reply."""
    if reply:
        print(botTColor + f"\n{agentname}: {reply}" + resetTColor)
        speak(reply)  # blocking — mutes mic listener for its duration


# ============================================================================
# Voice mode — passive always-on listener
# ============================================================================

def voice_loop(ai: MobileAICore, model_path: str) -> None:
    """
    Passive voice interaction loop.

    - PassiveVoskListener runs on its own daemon thread, continuously
      monitoring the microphone for speech.
    - Recognised utterances are submitted to AICore via a threading.Queue
      processed on this (main) thread to keep send() calls serialised.
    - The main thread also accepts 'exit'/'quit' from stdin so the process
      can be stopped cleanly without killing the terminal.
    - Running in the background with nohup/tmux redirects stdin, so the
      KeyboardInterrupt / EOFError handlers ensure a clean shutdown either way.
    """
    import queue

    utterance_queue: queue.Queue = queue.Queue()

    def _on_utterance(text: str) -> None:
        """Called from listener thread — enqueue for main-thread processing."""
        utterance_queue.put(text)

    listener = PassiveVoskListener(model_path=model_path, result_callback=_on_utterance)
    listener.start()

    print(systemTColor + "[Voice] Always-on passive mode active. Speak naturally." + resetTColor)
    print(systemTColor + "[Voice] Type 'exit' or Ctrl+C to stop." + resetTColor)

    # Stdin watcher thread — lets the user type 'exit' even in voice mode,
    # and also catches text input as a fallback when the user prefers to type.
    stop_event = threading.Event()

    def _stdin_watcher():
        while not stop_event.is_set():
            try:
                line = sys.stdin.readline()
                if not line:               # EOF — stdin closed (background run)
                    break
                text = line.strip()
                if text.lower() in {"exit", "quit"}:
                    stop_event.set()
                    break
                if text:
                    utterance_queue.put(text)
            except Exception:
                break

    stdin_thread = threading.Thread(target=_stdin_watcher, daemon=True, name="StdinWatcher")
    stdin_thread.start()

    try:
        while not stop_event.is_set():
            try:
                # Block with timeout so we can check stop_event periodically
                text = utterance_queue.get(timeout=0.5)
            except Exception:
                continue

            if text.lower() in {"exit", "quit", "goodbye"}:
                stop_event.set()
                break

            reply = ai.send(text)
            _handle_reply(reply)

    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        listener.cleanup()


# ============================================================================
# Text mode — typed input
# ============================================================================

def text_loop(ai: MobileAICore) -> None:
    print(systemTColor + f"[Text Mode] Type messages. 'exit' to quit." + resetTColor)
    while True:
        try:
            raw = input(userTColor + f"\n{username}: " + resetTColor).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if raw.lower() in {"exit", "quit"}:
            break
        if not raw:
            continue
        reply = ai.send(raw)
        _handle_reply(reply)


# ============================================================================
# Entry point
# ============================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Mobile Termux interface — passive voice + full cognitive loop"
    )
    p.add_argument(
        "--mode", choices=["text", "voice"], default=None,
        help="Interaction mode. Prompted interactively if omitted."
    )
    p.add_argument(
        "--model",
        default=str(Path.home() / "vosk-model-small-en-us-0.15"),
        help="Path to the Vosk model directory (voice mode only). "
             "Default: ~/vosk-model-small-en-us-0.15"
    )
    return p.parse_args()


def choose_mode() -> str:
    print(systemTColor + "\n=== Mode Selection ===" + resetTColor)
    print(systemTColor + "1. Voice  — passive always-on listener (Vosk offline)" + resetTColor)
    print(systemTColor + "2. Text   — type messages" + resetTColor)
    while True:
        choice = input(userTColor + "Choose (1/2): " + resetTColor).strip()
        if choice == "1":
            return "voice"
        if choice == "2":
            return "text"
        print(errorTColor + "Enter 1 or 2." + resetTColor)


def main() -> None:
    args = parse_args()

    speak(f"Hello, {username}. Starting up.")

    ai = MobileAICore(PROJECT_ROOT)

    mode = args.mode or choose_mode()

    if mode == "voice":
        if not VOSK_AVAILABLE:
            print(errorTColor + "[Error] vosk/pyaudio not installed — falling back to text mode." + resetTColor)
            print(errorTColor + "Install: pip install vosk pyaudio" + resetTColor)
            mode = "text"
        elif not os.path.exists(args.model):
            print(errorTColor + f"[Error] Vosk model not found: {args.model}" + resetTColor)
            print(errorTColor + "Specify path with --model or download from https://alphacephei.com/vosk/models" + resetTColor)
            mode = "text"

    speak(f"{agentname} is ready.")

    try:
        if mode == "voice":
            voice_loop(ai, args.model)
        else:
            text_loop(ai)
    except KeyboardInterrupt:
        pass
    finally:
        print(systemTColor + "\n[Mobile] Shutting down..." + resetTColor)
        speak("Goodbye.")
        ai.shutdown()
        print(systemTColor + "[Mobile] Done." + resetTColor)


if __name__ == "__main__":
    main()