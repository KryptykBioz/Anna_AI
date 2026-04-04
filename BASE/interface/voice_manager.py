# BASE/interface/voice_manager.py
"""
Voice input management component with volume controls
REFACTORED: Uses internal tool manager for modular voice services
COMPLETE: All original functionality preserved including Voice Hub support
"""
import tkinter as tk
from tkinter import ttk
import threading
import time
import sys
from pathlib import Path
import subprocess

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from BASE.interface.gui_themes import DarkTheme

# Import GPU-accelerated voice module for legacy support
# NOTE: This import is for backwards compatibility with legacy voice systems
# The new modular system uses internal tools and doesn't require these imports
try:
    from BASE.tools.internal.voice.voice_to_text import init_audio, start_vosk_stream
    GPU_VOICE_AVAILABLE = True
except ImportError:
    GPU_VOICE_AVAILABLE = False
    # This is EXPECTED with the new modular system
    # Internal tools handle voice input - no error needed

try:
    from personality.bot_info import agentname, username
except ImportError:
    agentname = "Anna"
    username = "User"


class VoiceManager:
    """Manages voice input using internal tool manager with Voice Hub support"""

    __slots__ = ('message_queue', 'input_queue', 'logger', 'ai_core',
                 'voice_enabled', 'audio_started',
                 'recognition_backend', 'recognition_device', 'whisper_model', 'vosk_model',
                 'stream', 'raw_queue', 'text_queue', 'voice_thread', 'voice_worker_thread',
                 'hub_client', 'using_hub', 'agent_speech_thread',
                 'voice_button', 'voice_status', 'voice_volume_slider', 'voice_volume_label',
                 'sound_volume_slider', 'sound_volume_label',
                 'overflow_count', 'last_overflow_log', 'transcription_times',
                 '_audio_debug_counter', '_last_nonzero_audio', 'voice_tool')
    
    def __init__(self, message_queue, input_queue, logger, ai_core=None):
        """Initialize voice manager"""
        self.message_queue = message_queue
        self.input_queue = input_queue
        self.logger = logger
        self.ai_core = ai_core
        
        self.voice_enabled = False
        self.audio_started = False
        
        # GPU voice recognition components (legacy)
        self.recognition_backend = None
        self.recognition_device = None
        self.whisper_model = None
        self.vosk_model = None
        self.stream = None
        self.raw_queue = None
        self.text_queue = None
        
        # Voice threads
        self.voice_thread = None
        self.voice_worker_thread = None
        
        # Voice Hub integration
        self.hub_client = None
        self.using_hub = False
        self.agent_speech_thread = None
        
        # Internal tool system
        self.voice_tool = None
        
        # GUI components
        self.voice_button = None
        self.voice_status = None
        self.voice_volume_slider = None
        self.voice_volume_label = None
        self.sound_volume_slider = None
        self.sound_volume_label = None
        
        # Debug counters (legacy)
        self.overflow_count = 0
        self.last_overflow_log = 0
        self.transcription_times = []
        self._audio_debug_counter = 0
        self._last_nonzero_audio = 0

    def create_voice_panel(self, parent_frame):
        """Create voice control panel with volume controls"""
        voice_frame = ttk.LabelFrame(
            parent_frame, text="Voice & Audio Control", style="Dark.TLabelframe"
        )
        voice_frame.pack(fill=tk.X, pady=(0, 5))
        
        voice_controls = ttk.Frame(voice_frame)
        voice_controls.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        self.voice_button = ttk.Button(
            voice_controls,
            text="Start Voice Input",
            command=self.toggle_voice_input,
            width=20,
        )
        self.voice_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.voice_status = tk.Label(
            voice_controls,
            text="Voice: Disabled",
            font=("Segoe UI", 9),
            foreground=DarkTheme.FG_MUTED,
            background=DarkTheme.BG_DARKER,
        )
        self.voice_status.pack(side=tk.LEFT)
        
        self._create_volume_controls(voice_frame)

    def _create_volume_controls(self, parent_frame):
        """Create volume slider controls"""
        import personality.controls as controls
        
        volume_container = ttk.Frame(parent_frame)
        volume_container.pack(fill=tk.X, padx=5, pady=(10, 5))
        
        # TTS Voice Volume
        voice_vol_frame = ttk.Frame(volume_container)
        voice_vol_frame.pack(fill=tk.X, pady=(0, 8))
        
        voice_label_frame = ttk.Frame(voice_vol_frame)
        voice_label_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        voice_icon = tk.Label(
            voice_label_frame,
            text="🔊",
            font=("Segoe UI", 12),
            background=DarkTheme.BG_DARKER,
            width=2
        )
        voice_icon.pack(side=tk.LEFT)
        
        voice_text = tk.Label(
            voice_label_frame,
            text="Voice",
            font=("Segoe UI", 9, "bold"),
            foreground=DarkTheme.FG_PRIMARY,
            background=DarkTheme.BG_DARKER,
            width=8,
            anchor="w"
        )
        voice_text.pack(side=tk.LEFT, padx=(5, 0))
        
        voice_slider_frame = ttk.Frame(voice_vol_frame)
        voice_slider_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.voice_volume_slider = tk.Scale(
            voice_slider_frame,
            from_=0, to=100, orient=tk.HORIZONTAL,
            command=self._on_voice_volume_change,
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY,
            troughcolor=DarkTheme.BG_LIGHTER,
            activebackground=DarkTheme.ACCENT_PURPLE,
            highlightthickness=0,
            showvalue=0,
            length=150
        )
        self.voice_volume_slider.set(int(controls.VOICE_VOLUME * 100))
        self.voice_volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.voice_volume_label = tk.Label(
            voice_slider_frame,
            text=f"{int(controls.VOICE_VOLUME * 100)}%",
            font=("Segoe UI", 9, "bold"),
            foreground=DarkTheme.ACCENT_PURPLE,
            background=DarkTheme.BG_DARKER,
            width=5
        )
        self.voice_volume_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Sound Effects Volume
        sound_vol_frame = ttk.Frame(volume_container)
        sound_vol_frame.pack(fill=tk.X)
        
        sound_label_frame = ttk.Frame(sound_vol_frame)
        sound_label_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        sound_icon = tk.Label(
            sound_label_frame,
            text="🎵",
            font=("Segoe UI", 12),
            background=DarkTheme.BG_DARKER,
            width=2
        )
        sound_icon.pack(side=tk.LEFT)
        
        sound_text = tk.Label(
            sound_label_frame,
            text="Sounds",
            font=("Segoe UI", 9, "bold"),
            foreground=DarkTheme.FG_PRIMARY,
            background=DarkTheme.BG_DARKER,
            width=8,
            anchor="w"
        )
        sound_text.pack(side=tk.LEFT, padx=(5, 0))
        
        sound_slider_frame = ttk.Frame(sound_vol_frame)
        sound_slider_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.sound_volume_slider = tk.Scale(
            sound_slider_frame,
            from_=0, to=100, orient=tk.HORIZONTAL,
            command=self._on_sound_volume_change,
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY,
            troughcolor=DarkTheme.BG_LIGHTER,
            activebackground=DarkTheme.ACCENT_BLUE,
            highlightthickness=0,
            showvalue=0,
            length=150
        )
        self.sound_volume_slider.set(int(controls.SOUND_EFFECT_VOLUME * 100))
        self.sound_volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.sound_volume_label = tk.Label(
            sound_slider_frame,
            text=f"{int(controls.SOUND_EFFECT_VOLUME * 100)}%",
            font=("Segoe UI", 9, "bold"),
            foreground=DarkTheme.ACCENT_BLUE,
            background=DarkTheme.BG_DARKER,
            width=5
        )
        self.sound_volume_label.pack(side=tk.LEFT, padx=(5, 0))
        
        hint_label = tk.Label(
            volume_container,
            text="Volumes apply immediately to all audio output",
            font=("Segoe UI", 8, "italic"),
            foreground=DarkTheme.FG_MUTED,
            background=DarkTheme.BG_DARKER
        )
        hint_label.pack(pady=(5, 0))
    
    def _on_voice_volume_change(self, value):
        """Handle TTS voice volume slider change"""
        import personality.controls as controls
        volume = int(value) / 100.0
        controls.VOICE_VOLUME = volume
        if self.voice_volume_label:
            self.voice_volume_label.config(text=f"{int(value)}%")
    
    def _on_sound_volume_change(self, value):
        """Handle sound effects volume slider change"""
        import personality.controls as controls
        volume = int(value) / 100.0
        controls.SOUND_EFFECT_VOLUME = volume
        if self.sound_volume_label:
            self.sound_volume_label.config(text=f"{int(value)}%")

    def toggle_voice_input(self):
        """Toggle voice input on/off - WITH VOICE HUB SUPPORT"""
        if not self.voice_enabled:
            # Check if GROUP_CHAT enabled
            import personality.controls as controls
            use_hub = getattr(controls, 'GROUP_CHAT', False)
            
            if use_hub:
                # Try Voice Hub integration
                from BASE.services.voice_hub_client import VoiceHubClient
                
                self.hub_client = VoiceHubClient(logger=self.logger)
                
                if self.hub_client.connect(timeout=5.0):
                    # Connected to existing hub
                    self.logger.success("[Voice Hub] Connected to Voice Hub")
                    self.using_hub = True
                else:
                    # No hub found - spawn it
                    self.logger.system("[Voice Hub] Spawning Voice Hub server...")
                    self._spawn_voice_hub()
                    
                    time.sleep(2.0)
                    
                    if self.hub_client.connect(timeout=5.0):
                        self.logger.success("[Voice Hub] Connected to new Voice Hub")
                        self.using_hub = True
                    else:
                        self.logger.error("[Voice Hub] Failed to connect - using local")
                        self.hub_client = None
                        self.using_hub = False
                
                if self.using_hub:
                    # Register with hub
                    from personality.bot_info import agentname, vb_cable_name
                    success = self.hub_client.register_agent(
                        agent_name=agentname,
                        cable_name=vb_cable_name,
                        voice_config=self._get_voice_config()
                    )
                    
                    if success:
                        self._start_hub_voice_processing()
                        return
                    else:
                        self.logger.error("[Voice Hub] Registration failed - using local")
                        self.hub_client = None
                        self.using_hub = False
            
            # LOCAL VOICE PROCESSING - use internal tools
            if not self.using_hub:
                self._start_local_voice_input()
        else:
            self.stop_voice_input()
    
    def _start_local_voice_input(self):
        """Start local voice input using internal tool manager"""
        if not self.ai_core or not self.ai_core.internal_tool_manager:
            self.logger.error("[Voice] Internal tool manager not available")
            self._update_voice_status("Error: No tool manager", "error")
            return
        
        self.voice_tool = self.ai_core.internal_tool_manager.get_active_voice_input_tool()
        
        if not self.voice_tool:
            if GPU_VOICE_AVAILABLE:
                self._start_legacy_voice_input()
                return
            
            self.logger.error("[Voice] No voice input tool active")
            self._update_voice_status("Error: No voice input tool", "error")
            return
        
        if not self.voice_tool.is_available():
            self.logger.error("[Voice] Voice input tool not enabled")
            self._update_voice_status("Error: Tool unavailable", "error")
            return
        
        # Store reference to self for callback closure
        voice_mgr = self
        
        def speech_callback(username_param, text):
            """
            Callback for recognized speech
            Matches tool signature: callback(username, text)
            """
            voice_mgr._on_speech_recognized(username_param, text)
        
        success = self.voice_tool.start_listening(callback=speech_callback)
        
        if success:
            self.voice_enabled = True
            self._update_voice_status(f"{self.voice_tool.tool_name} Listening", "active")
            self.logger.success("[Voice] Voice input started")
        else:
            self.logger.error("[Voice] Failed to start voice input")
            self._update_voice_status("Failed to start", "error")

    def _on_speech_recognized(self, username, text):
        """
        Handle recognized speech from internal tool
        FIXED: Signature now matches what the callback receives
        """
        self.message_queue.put(("voice_input", username, text))
        self.input_queue.put(text)
        self.logger.speech(f"{username}: {text}")
    
    def _start_legacy_voice_input(self):
        """Start legacy GPU voice input (fallback)"""
        try:
            init_audio(self)
            
            backend_name = f"{self.recognition_backend.upper()} on {self.recognition_device.upper()}"
            self.logger.success(f"Voice backend: {backend_name}")
            
            self.voice_enabled = True
            self._update_voice_status(backend_name, "active")
            
            start_vosk_stream(self)
            
            self.voice_thread = threading.Thread(
                target=self.voice_processing_loop, daemon=True
            )
            self.voice_thread.start()
            
            self.logger.success("Voice input started successfully")
        
        except Exception as e:
            self.logger.error(f"Voice initialization error: {str(e)}")
            import traceback
            traceback.print_exc()
            self.voice_enabled = False
            self._update_voice_status("Error", "error")
    
    # def _on_speech_recognized(self, user, text):
    #     """Handle recognized speech from internal tool"""
    #     self.message_queue.put(("voice_input", user, text))
    #     self.input_queue.put(text)
    #     self.logger.speech(f"{user}: {text}")
    
    def _update_voice_status(self, message, status_type="normal"):
        """Update voice status label"""
        if not self.voice_status:
            return
        
        color_map = {
            "active": DarkTheme.ACCENT_GREEN,
            "inactive": DarkTheme.FG_MUTED,
            "error": DarkTheme.ACCENT_RED
        }
        
        color = color_map.get(status_type, DarkTheme.FG_PRIMARY)
        
        self.voice_status.config(
            text=f"Voice: {message}",
            foreground=color
        )
        
        if self.voice_button:
            if status_type == "active":
                self.voice_button.config(text="Stop Voice Input")
            else:
                self.voice_button.config(text="Start Voice Input")

    def _spawn_voice_hub(self):
        """Spawn Voice Hub server as detached subprocess"""
        try:
            project_root = Path(__file__).parent.parent.parent
            hub_script = project_root / "BASE" / "services" / "voice_hub_server.py"
            
            if not hub_script.exists():
                self.logger.error(f"Voice Hub script not found: {hub_script}")
                return
            
            # Spawn as detached process
            if sys.platform == "win32":
                subprocess.Popen(
                    [sys.executable, str(hub_script)],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    [sys.executable, str(hub_script)],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            self.logger.system("[Voice Hub] Server process spawned")
        
        except Exception as e:
            self.logger.error(f"[Voice Hub] Failed to spawn server: {e}")

    def _start_hub_voice_processing(self):
        """Start voice processing using Voice Hub"""
        self.voice_enabled = True
        
        if self.voice_button:
            self.voice_button.config(text="Stop Voice Input")
        if self.voice_status:
            self.voice_status.config(
                text="Voice: Hub (Whisper GPU)",
                foreground=DarkTheme.ACCENT_GREEN
            )
        
        # Start user speech thread
        self.voice_thread = threading.Thread(
            target=self._hub_user_speech_loop,
            daemon=True
        )
        self.voice_thread.start()
        
        # Start agent speech monitoring thread
        self.agent_speech_thread = threading.Thread(
            target=self._hub_agent_speech_loop,
            daemon=True
        )
        self.agent_speech_thread.start()
        
        self.logger.success("[Voice Hub] Voice processing started")

    def _hub_user_speech_loop(self):
        """Process user speech from Voice Hub"""
        from personality.bot_info import agentname, username
        
        while self.voice_enabled and self.hub_client:
            text = self.hub_client.poll_user_speech(timeout=0.1)
            
            if text and len(text) >= 3:
                # Filter out own agent name
                if agentname.lower() not in text.lower():
                    self.message_queue.put(("voice_input", username, text))
                    self.input_queue.put(text)
                    self.logger.speech(f"User: {text}")

    def _hub_agent_speech_loop(self):
        """Monitor other agents' speech and inject to thought buffer"""
        from personality.bot_info import agentname
        
        while self.voice_enabled and self.hub_client:
            speech = self.hub_client.poll_agent_speech(timeout=0.1)
            
            if speech:
                speaker = speech.get('speaker')
                text = speech.get('text')
                
                # Don't process our own speech
                if speaker and speaker != agentname:
                    self.logger.system(f"[{speaker}] {text}")
                    
                    # Inject to thought buffer if ai_core available
                    if self.ai_core and hasattr(self.ai_core, 'thought_buffer'):
                        self.ai_core.thought_buffer.add_processed_thought(
                            content=f"[Agent: {speaker}] {text}",
                            source="voice_hub",
                            category="agent_speech",
                            priority=0.7
                        )

    def _get_voice_config(self) -> dict:
        """Get current agent's voice configuration for Voice Hub registration"""
        import personality.controls as controls
        
        if controls.USE_CUSTOM_VOICE:
            from personality.bot_info import agentname
            voice_sample = f"./personality/voice/{agentname}_voice_sample.mp3"
            
            return {
                'type': 'xtts',
                'voice_sample': voice_sample,
                'language': 'en',
                'speed': 1.0
            }
        else:
            from personality.bot_info import voiceIndex
            return {
                'type': 'pyttsx3',
                'voice_index': voiceIndex,
                'rate': 200
            }

    def stop_voice_input(self):
        """Stop voice input and cleanup"""
        try:
            self.voice_enabled = False
            
            # Disconnect from Voice Hub if connected
            if self.hub_client and self.hub_client.is_connected():
                self.logger.system("[Voice Hub] Disconnecting from hub...")
                self.hub_client.disconnect()
                self.hub_client = None
                self.using_hub = False
            
            # Stop agent speech monitoring thread
            if self.agent_speech_thread and self.agent_speech_thread.is_alive():
                self.agent_speech_thread.join(timeout=2.0)
            
            # Stop internal tool if active
            if self.voice_tool:
                self.voice_tool.stop_listening()
                self.voice_tool = None
            
            # Stop legacy voice if active
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as e:
                    self.logger.error(f"Error stopping stream: {str(e)}")
                self.stream = None
            
            if self.raw_queue:
                try:
                    self.raw_queue.put(b"__EXIT__")
                except:
                    pass
            
            if self.voice_thread and self.voice_thread.is_alive():
                self.voice_thread.join(timeout=2.0)
            
            self._update_voice_status("Disabled", "inactive")
            
            self.logger.system("Voice input stopped")

        except Exception as e:
            self.logger.error(f"Error in stop_voice_input: {str(e)}")

    def voice_processing_loop(self):
        """Process recognized text from text_queue (legacy)"""
        try:
            self.logger.system("Voice processing loop started")
            self.logger.system(f"Backend: {self.recognition_backend}, Device: {self.recognition_device}")
            
            while self.voice_enabled:
                try:
                    # Get recognized text from queue (non-blocking with timeout)
                    text = self.text_queue.get(timeout=0.1)
                    
                    if text and len(text) >= 3:
                        # Queue for AI processing
                        self.message_queue.put(("voice_input", username, text))
                        self.input_queue.put(text)
                        self.logger.speech(f"Voice recognized: {text}")
                        
                except:
                    # Timeout or queue empty - continue loop
                    continue
                    
        except Exception as e:
            self.logger.error(f"Voice processing loop error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def cleanup(self):
        """Cleanup voice manager"""
        if self.voice_enabled:
            self.stop_voice_input()


class VolumeControlPanel:
    """Standalone volume control panel"""

    __slots__ = ('parent', 'logger', 'controls', 'voice_volume_slider', 'voice_volume_label',
                 'sound_volume_slider', 'sound_volume_label')

    def __init__(self, parent, logger, controls_module):
        self.parent = parent
        self.logger = logger
        self.controls = controls_module
        self.voice_volume_slider = None
        self.voice_volume_label = None
        self.sound_volume_slider = None
        self.sound_volume_label = None
    
    def create_panel(self, show_title=True):
        """Create volume control panel"""
        if show_title:
            container = ttk.LabelFrame(
                self.parent,
                text="Audio Volume",
                style="Dark.TLabelframe"
            )
        else:
            container = ttk.Frame(self.parent)
        
        container.pack(fill=tk.X, pady=5)
        
        # Voice Volume
        voice_frame = ttk.Frame(container)
        voice_frame.pack(fill=tk.X, padx=5, pady=(5, 8))
        
        tk.Label(
            voice_frame,
            text="Voice",
            font=("Segoe UI", 9, "bold"),
            foreground=DarkTheme.FG_PRIMARY,
            background=DarkTheme.BG_DARKER,
            width=10,
            anchor="w"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.voice_volume_slider = tk.Scale(
            voice_frame,
            from_=0, to=100, orient=tk.HORIZONTAL,
            command=self._on_voice_volume_change,
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY,
            troughcolor=DarkTheme.BG_LIGHTER,
            activebackground=DarkTheme.ACCENT_PURPLE,
            highlightthickness=0,
            showvalue=0
        )
        self.voice_volume_slider.set(int(self.controls.VOICE_VOLUME * 100))
        self.voice_volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.voice_volume_label = tk.Label(
            voice_frame,
            text=f"{int(self.controls.VOICE_VOLUME * 100)}%",
            font=("Segoe UI", 9, "bold"),
            foreground=DarkTheme.ACCENT_PURPLE,
            background=DarkTheme.BG_DARKER,
            width=5
        )
        self.voice_volume_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Sound Effects Volume
        sound_frame = ttk.Frame(container)
        sound_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        tk.Label(
            sound_frame,
            text="Sounds",
            font=("Segoe UI", 9, "bold"),
            foreground=DarkTheme.FG_PRIMARY,
            background=DarkTheme.BG_DARKER,
            width=10,
            anchor="w"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.sound_volume_slider = tk.Scale(
            sound_frame,
            from_=0, to=100, orient=tk.HORIZONTAL,
            command=self._on_sound_volume_change,
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY,
            troughcolor=DarkTheme.BG_LIGHTER,
            activebackground=DarkTheme.ACCENT_BLUE,
            highlightthickness=0,
            showvalue=0
        )
        self.sound_volume_slider.set(int(self.controls.SOUND_EFFECT_VOLUME * 100))
        self.sound_volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.sound_volume_label = tk.Label(
            sound_frame,
            text=f"{int(self.controls.SOUND_EFFECT_VOLUME * 100)}%",
            font=("Segoe UI", 9, "bold"),
            foreground=DarkTheme.ACCENT_BLUE,
            background=DarkTheme.BG_DARKER,
            width=5
        )
        self.sound_volume_label.pack(side=tk.LEFT, padx=(5, 0))
        
        return container
    
    def _on_voice_volume_change(self, value):
        volume = int(value) / 100.0
        self.controls.VOICE_VOLUME = volume
        if self.voice_volume_label:
            self.voice_volume_label.config(text=f"{int(value)}%")
    
    def _on_sound_volume_change(self, value):
        volume = int(value) / 100.0
        self.controls.SOUND_EFFECT_VOLUME = volume
        if self.sound_volume_label:
            self.sound_volume_label.config(text=f"{int(value)}%")