# ============================================================================
# FILE: BASE/services/voice_hub_server.py
# Voice Hub Server - Centralized voice processing
# ============================================================================
"""
Voice Hub Server - Centralized voice infrastructure for multi-agent systems

Responsibilities:
- Load speech recognition models (Whisper/Vosk) once on GPU
- Load XTTS model once for all agents using custom voices
- Manage pyttsx3 engines per agent
- Process incoming audio and broadcast recognized speech
- Handle TTS requests concurrently without blocking
- Route audio to agent-specific Virtual Cables
- Monitor agent heartbeats and cleanup disconnected agents
- Shutdown when last agent disconnects

Lifecycle:
- Spawned by first agent with GROUP_CHAT=True
- Runs as detached subprocess
- Auto-shuts down when all agents disconnect
"""
import zmq
import time
import threading
import uuid
import queue
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
import numpy as np

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from BASE.services.voice_hub_protocol import (
    HubProtocol,
    HubMessageType,
    HubPorts,
    DiscoveryPong,
    AgentRegistrationAck,
    HeartbeatAck,
    UserSpeech,
    AgentSpeech,
    TTSAccepted,
    TTSError
)


class VoiceHubServer:
    """Centralized voice processing server for multi-agent systems"""
    
    def __init__(self):
        """Initialize Voice Hub Server"""
        self.running = False
        self.agents = {}
        self.agents_lock = threading.Lock()
        
        self.context = zmq.Context()
        self.discovery_socket = None
        self.registry_socket = None
        self.user_speech_pub = None
        self.agent_speech_pub = None
        self.tts_socket = None
        
        self.whisper_model = None
        self.vosk_model = None
        self.xtts_model = None
        self.pyttsx3_engines = {}
        
        self.recognition_backend = None
        self.recognition_device = None
        
        self.tts_executor = ThreadPoolExecutor(max_workers=4)
        self.active_tts_tasks = {}
        
        self.speech_thread = None
        self.heartbeat_thread = None
        
        self.raw_queue = None
        self.text_queue = None
        
        print("[Voice Hub] Initializing...")
    
    def start(self):
        """Start Voice Hub Server"""
        if self.running:
            print("[Voice Hub] Already running")
            return
        
        print("[Voice Hub] Starting Voice Hub Server...")
        
        try:
            self._setup_sockets()
            self._load_models()
            
            self.running = True
            
            self._start_threads()
            
            print("[Voice Hub] [SUCCESS] Voice Hub Server started")
            print(f"[Voice Hub] Backend: {self.recognition_backend}")
            print(f"[Voice Hub] Device: {self.recognition_device}")
            
            self._run_server_loop()
        
        except Exception as e:
            print(f"[Voice Hub] [ERROR] Startup failed: {e}")
            import traceback
            traceback.print_exc()
            self.shutdown()
    
    def _setup_sockets(self):
        """Setup ZMQ sockets"""
        print("[Voice Hub] Setting up network sockets...")
        
        self.discovery_socket = self.context.socket(zmq.REP)
        self.discovery_socket.bind(f"tcp://*:{HubPorts.DISCOVERY}")
        
        self.registry_socket = self.context.socket(zmq.REP)
        self.registry_socket.bind(f"tcp://*:{HubPorts.REGISTRY}")
        
        self.user_speech_pub = self.context.socket(zmq.PUB)
        self.user_speech_pub.bind(f"tcp://*:{HubPorts.USER_SPEECH}")
        
        self.agent_speech_pub = self.context.socket(zmq.PUB)
        self.agent_speech_pub.bind(f"tcp://*:{HubPorts.AGENT_SPEECH}")
        
        self.tts_socket = self.context.socket(zmq.REP)
        self.tts_socket.bind(f"tcp://*:{HubPorts.TTS_REQUEST}")
        
        print("[Voice Hub] [SUCCESS] Sockets bound")
    
    def _load_models(self):
        """Load voice recognition models"""
        print("[Voice Hub] Loading voice recognition models...")
        
        use_gpu = True
        
        if use_gpu:
            try:
                import torch
                if torch.cuda.is_available():
                    print(f"[Voice Hub] GPU: {torch.cuda.get_device_name(0)}")
                    self.whisper_model = self._load_whisper_model()
                    self.recognition_backend = "whisper"
                    self.recognition_device = "cuda"
                    print("[Voice Hub] [SUCCESS] Whisper loaded on GPU")
                else:
                    raise RuntimeError("CUDA not available")
            except Exception as e:
                print(f"[Voice Hub] GPU failed: {e}")
                print("[Voice Hub] Falling back to Vosk (CPU)...")
                self.vosk_model = self._load_vosk_model()
                self.recognition_backend = "vosk"
                self.recognition_device = "cpu"
                print("[Voice Hub] [SUCCESS] Vosk loaded on CPU")
        else:
            self.vosk_model = self._load_vosk_model()
            self.recognition_backend = "vosk"
            self.recognition_device = "cpu"
            print("[Voice Hub] [SUCCESS] Vosk loaded on CPU")
        
        print(f"[Voice Hub] XTTS will be loaded on first use (if needed)")
    
    def _load_whisper_model(self):
        """Load Whisper model for GPU acceleration"""
        from faster_whisper import WhisperModel
        
        model = WhisperModel(
            'small',
            device='cuda',
            compute_type='int8',
            cpu_threads=0,
            num_workers=1
        )
        
        dummy = np.zeros(16000, dtype=np.float32)
        _ = list(model.transcribe(dummy, language="en"))
        
        return model
    
    def _load_vosk_model(self):
        """Load Vosk model for CPU fallback"""
        from vosk import Model
        
        model_path = project_root / "models" / "vosk-model-en-us-0.42-gigaspeech"
        
        if not model_path.exists():
            raise FileNotFoundError(f"Vosk model not found: {model_path}")
        
        return Model(str(model_path))
    
    def _load_xtts_model(self):
        """Lazy load XTTS model when first needed"""
        if self.xtts_model is not None:
            return self.xtts_model
        
        print("[Voice Hub] Loading XTTS model...")
        
        try:
            from BASE.tools.internal.voice.text_to_custom_voice import init_tts
            
            self.xtts_model = init_tts()
            print("[Voice Hub] [SUCCESS] XTTS model loaded")
            
            return self.xtts_model
        
        except Exception as e:
            print(f"[Voice Hub] [ERROR] XTTS loading failed: {e}")
            return None
    
    def _get_or_create_pyttsx3_engine(self, agent_id: str, voice_config: Dict):
        """Get or create pyttsx3 engine for agent"""
        if agent_id in self.pyttsx3_engines:
            return self.pyttsx3_engines[agent_id]
        
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            
            voices = engine.getProperty('voices')
            voice_index = voice_config.get('voice_index', 0)
            
            if 0 <= voice_index < len(voices):
                engine.setProperty('voice', voices[voice_index].id)
            
            rate = voice_config.get('rate', 200)
            engine.setProperty('rate', rate)
            
            engine.setProperty('volume', 1.0)
            
            self.pyttsx3_engines[agent_id] = engine
            
            print(f"[Voice Hub] Created pyttsx3 engine for agent {agent_id[:8]}")
            
            return engine
        
        except Exception as e:
            print(f"[Voice Hub] [ERROR] Failed to create pyttsx3 engine: {e}")
            return None
    
    def _start_threads(self):
        """Start background threads"""
        print("[Voice Hub] Starting background threads...")
        
        self.speech_thread = threading.Thread(
            target=self._speech_recognition_loop,
            daemon=True,
            name="VoiceHub_SpeechRecognition"
        )
        self.speech_thread.start()
        
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_monitor_loop,
            daemon=True,
            name="VoiceHub_HeartbeatMonitor"
        )
        self.heartbeat_thread.start()
        
        print("[Voice Hub] [SUCCESS] Background threads started")
    
    def _run_server_loop(self):
        """Main server event loop"""
        print("[Voice Hub] Server loop started")
        
        poller = zmq.Poller()
        poller.register(self.discovery_socket, zmq.POLLIN)
        poller.register(self.registry_socket, zmq.POLLIN)
        poller.register(self.tts_socket, zmq.POLLIN)
        
        while self.running:
            try:
                sockets = dict(poller.poll(timeout=1000))
                
                if self.discovery_socket in sockets:
                    self._handle_discovery()
                
                if self.registry_socket in sockets:
                    self._handle_registry()
                
                if self.tts_socket in sockets:
                    self._handle_tts_request()
                
                with self.agents_lock:
                    if len(self.agents) == 0 and time.time() > 60:
                        print("[Voice Hub] No agents connected - shutting down")
                        self.shutdown()
                        break
            
            except KeyboardInterrupt:
                print("[Voice Hub] Keyboard interrupt")
                self.shutdown()
                break
            except Exception as e:
                print(f"[Voice Hub] [ERROR] Server loop error: {e}")
                import traceback
                traceback.print_exc()
    
    def _handle_discovery(self):
        """Handle discovery ping"""
        try:
            message = self.discovery_socket.recv_string()
            
            with self.agents_lock:
                agent_count = len(self.agents)
            
            pong = DiscoveryPong(
                timestamp=time.time(),
                hub_version="1.0.0",
                active_agents=agent_count
            )
            
            self.discovery_socket.send_string(pong.to_json())
        
        except Exception as e:
            print(f"[Voice Hub] [ERROR] Discovery error: {e}")
    
    def _handle_registry(self):
        """Handle agent registration and heartbeat"""
        try:
            message = self.registry_socket.recv_string()
            msg = HubProtocol.parse_message(message)
            
            if not msg:
                self.registry_socket.send_string('{"error": "Invalid message"}')
                return
            
            if hasattr(msg, 'type'):
                if msg.type == HubMessageType.AGENT_REGISTER.value:
                    self._register_agent(msg)
                elif msg.type == HubMessageType.HEARTBEAT.value:
                    self._handle_heartbeat(msg)
                else:
                    self.registry_socket.send_string('{"error": "Unknown message type"}')
        
        except Exception as e:
            print(f"[Voice Hub] [ERROR] Registry error: {e}")
            try:
                self.registry_socket.send_string('{"error": "Internal error"}')
            except:
                pass
    
    def _register_agent(self, registration):
        """Register new agent"""
        agent_id = str(uuid.uuid4())
        
        agent_info = {
            'id': agent_id,
            'name': registration.agent_name,
            'cable': registration.cable_name,
            'voice_config': registration.voice_config,
            'registered_at': time.time(),
            'last_heartbeat': time.time()
        }
        
        with self.agents_lock:
            self.agents[agent_id] = agent_info
        
        print(f"[Voice Hub] Agent registered: {registration.agent_name} (ID: {agent_id[:8]})")
        print(f"[Voice Hub] Total agents: {len(self.agents)}")
        
        ack = AgentRegistrationAck(
            success=True,
            agent_id=agent_id,
            message="Registration successful",
            timestamp=time.time()
        )
        
        self.registry_socket.send_string(ack.to_json())
    
    def _handle_heartbeat(self, heartbeat):
        """Handle agent heartbeat"""
        agent_id = heartbeat.agent_id
        
        with self.agents_lock:
            if agent_id in self.agents:
                self.agents[agent_id]['last_heartbeat'] = time.time()
        
        ack = HeartbeatAck(timestamp=time.time())
        self.registry_socket.send_string(ack.to_json())
    
    def _handle_tts_request(self):
        """Handle TTS generation request (non-blocking)"""
        try:
            message = self.tts_socket.recv_string()
            request = HubProtocol.parse_message(message)
            
            if not request or not hasattr(request, 'type'):
                error = TTSError(
                    error_message="Invalid request",
                    timestamp=time.time()
                )
                self.tts_socket.send_string(error.to_json())
                return
            
            request_id = str(uuid.uuid4())
            
            future = self.tts_executor.submit(
                self._process_tts_request,
                request_id,
                request
            )
            
            self.active_tts_tasks[request_id] = future
            
            accepted = TTSAccepted(
                request_id=request_id,
                timestamp=time.time()
            )
            
            self.tts_socket.send_string(accepted.to_json())
        
        except Exception as e:
            print(f"[Voice Hub] [ERROR] TTS request error: {e}")
            try:
                error = TTSError(
                    error_message=str(e),
                    timestamp=time.time()
                )
                self.tts_socket.send_string(error.to_json())
            except:
                pass
    
    def _process_tts_request(self, request_id: str, request):
        """Process TTS request in worker thread"""
        try:
            agent_id = request.agent_id
            text = request.text
            voice_config = request.voice_config
            volume = request.volume
            
            with self.agents_lock:
                if agent_id not in self.agents:
                    print(f"[Voice Hub] Unknown agent: {agent_id}")
                    return
                
                agent = self.agents[agent_id]
                cable_name = agent['cable']
                agent_name = agent['name']
            
            voice_type = voice_config.get('type')
            
            if voice_type == 'xtts':
                success = self._generate_xtts(text, voice_config, cable_name, volume)
            elif voice_type == 'pyttsx3':
                success = self._generate_pyttsx3(text, voice_config, cable_name, volume, agent_id)
            else:
                print(f"[Voice Hub] Unknown voice type: {voice_type}")
                success = False
            
            if success:
                self._broadcast_agent_speech(agent_name, text)
            
            if request_id in self.active_tts_tasks:
                del self.active_tts_tasks[request_id]
        
        except Exception as e:
            print(f"[Voice Hub] [ERROR] TTS processing error: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_xtts(self, text: str, voice_config: Dict, cable_name: str, volume: float) -> bool:
        """Generate speech using XTTS"""
        try:
            if self.xtts_model is None:
                self.xtts_model = self._load_xtts_model()
            
            if self.xtts_model is None:
                print("[Voice Hub] XTTS model not available")
                return False
            
            from BASE.tools.internal.voice.text_to_custom_voice import speak_custom_voice
            from BASE.tools.internal.voice.voice_utils import find_cable_by_name
            
            voice_sample = voice_config.get('voice_sample')
            language = voice_config.get('language', 'en')
            speed = voice_config.get('speed', 1.0)
            
            cable_index = find_cable_by_name(cable_name)
            
            if cable_index is None:
                print(f"[Voice Hub] Cable not found: {cable_name}")
                return False
            
            result = speak_custom_voice(
                text=text,
                ref_audio=voice_sample,
                language=language,
                speed=speed,
                use_cache=True,
                fallback=True,
                stop_flag=None,
                volume=volume,
                xtts_model=self.xtts_model
            )
            
            return "SUCCESS" in result or "completed" in result
        
        except Exception as e:
            print(f"[Voice Hub] XTTS generation error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _generate_pyttsx3(self, text: str, voice_config: Dict, cable_name: str, 
                          volume: float, agent_id: str) -> bool:
        """Generate speech using pyttsx3"""
        try:
            engine = self._get_or_create_pyttsx3_engine(agent_id, voice_config)
            
            if engine is None:
                print("[Voice Hub] pyttsx3 engine not available")
                return False
            
            from BASE.tools.internal.voice.text_to_system_voice import speak_system_voice
            
            result = speak_system_voice(
                text=text,
                engine=engine,
                stop_event=None,
                volume=volume
            )
            
            return "completed" in result.lower() or "success" in result.lower()
        
        except Exception as e:
            print(f"[Voice Hub] pyttsx3 generation error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _broadcast_agent_speech(self, speaker: str, text: str):
        """Broadcast agent speech to other agents"""
        try:
            speech = AgentSpeech(
                speaker=speaker,
                text=text,
                timestamp=time.time()
            )
            
            self.agent_speech_pub.send_string(speech.to_json())
        
        except Exception as e:
            print(f"[Voice Hub] Agent speech broadcast error: {e}")
    
    def _speech_recognition_loop(self):
        """Speech recognition thread"""
        print("[Voice Hub] Starting speech recognition...")
        
        try:
            if self.recognition_backend == "whisper":
                self._whisper_recognition_loop()
            else:
                self._vosk_recognition_loop()
        
        except Exception as e:
            print(f"[Voice Hub] Speech recognition error: {e}")
            import traceback
            traceback.print_exc()
    
    def _whisper_recognition_loop(self):
        """Whisper-based speech recognition"""
        import sounddevice as sd
        import queue
        
        samplerate = 16000
        AUDIO_BLOCKSIZE = 16384
        AUDIO_CHUNK_DURATION = 4.0
        
        self.raw_queue = queue.Queue(maxsize=50)
        
        audio_buffer = []
        samples_per_chunk = int(samplerate * AUDIO_CHUNK_DURATION)
        
        device = self._find_microphone()
        if device is None:
            print("[Voice Hub] No microphone found")
            return
        
        def audio_callback(indata, frames, time_info, status):
            try:
                self.raw_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass
        
        stream = sd.RawInputStream(
            samplerate=samplerate,
            blocksize=AUDIO_BLOCKSIZE,
            dtype="int16",
            channels=1,
            device=device,
            callback=audio_callback,
            latency='high'
        )
        
        stream.start()
        print(f"[Voice Hub] Whisper recognition active on device {device}")
        
        while self.running:
            try:
                data = self.raw_queue.get(timeout=0.1)
                
                audio_data = np.frombuffer(data, dtype=np.int16)
                audio_float = audio_data.astype(np.float32) / 32768.0
                audio_buffer.extend(audio_float)
                
                if len(audio_buffer) >= samples_per_chunk:
                    audio_chunk = np.array(audio_buffer[:samples_per_chunk])
                    audio_buffer = audio_buffer[samples_per_chunk:]
                    
                    segments, info = self.whisper_model.transcribe(
                        audio_chunk,
                        language="en",
                        beam_size=5,
                        vad_filter=True,
                        vad_parameters=dict(
                            threshold=0.5,
                            min_speech_duration_ms=250,
                            min_silence_duration_ms=500
                        ),
                        without_timestamps=True
                    )
                    
                    text = " ".join([s.text.strip() for s in segments])
                    
                    if text and len(text) >= 5:
                        self._broadcast_user_speech(text)
            
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Voice Hub] Whisper loop error: {e}")
        
        stream.stop()
        stream.close()
    
    def _vosk_recognition_loop(self):
        """Vosk-based speech recognition"""
        import sounddevice as sd
        import queue
        import json
        from vosk import KaldiRecognizer
        
        samplerate = 16000
        AUDIO_BLOCKSIZE = 16384
        
        self.raw_queue = queue.Queue(maxsize=50)
        
        device = self._find_microphone()
        if device is None:
            print("[Voice Hub] No microphone found")
            return
        
        rec = KaldiRecognizer(self.vosk_model, samplerate)
        
        def audio_callback(indata, frames, time_info, status):
            try:
                self.raw_queue.put_nowait(bytes(indata))
            except queue.Full:
                pass
        
        stream = sd.RawInputStream(
            samplerate=samplerate,
            blocksize=AUDIO_BLOCKSIZE,
            dtype="int16",
            channels=1,
            device=device,
            callback=audio_callback,
            latency='high'
        )
        
        stream.start()
        print(f"[Voice Hub] Vosk recognition active on device {device}")
        
        while self.running:
            try:
                data = self.raw_queue.get(timeout=0.1)
                
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    
                    if text and len(text) >= 5:
                        self._broadcast_user_speech(text)
            
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Voice Hub] Vosk loop error: {e}")
        
        stream.stop()
        stream.close()
    
    def _find_microphone(self) -> Optional[int]:
        """Find working microphone device"""
        import sounddevice as sd
        
        PREFERRED_DEVICES = [1, 12, 29, 35]
        
        for device_idx in PREFERRED_DEVICES:
            try:
                device_info = sd.query_devices(device_idx)
                device_name = device_info['name']
                
                if 'cable' in device_name.lower() or 'vb-audio' in device_name.lower():
                    continue
                
                test_stream = sd.RawInputStream(
                    samplerate=16000,
                    blocksize=2048,
                    dtype="int16",
                    channels=1,
                    device=device_idx
                )
                test_stream.close()
                
                print(f"[Voice Hub] Using microphone: {device_name}")
                return device_idx
            
            except Exception:
                continue
        
        return None
    
    def _broadcast_user_speech(self, text: str):
        """Broadcast user speech to all agents"""
        try:
            speech = UserSpeech(
                text=text,
                timestamp=time.time(),
                confidence=1.0,
                backend=self.recognition_backend
            )
            
            self.user_speech_pub.send_string(speech.to_json())
            print(f"[Voice Hub] User: {text}")
        
        except Exception as e:
            print(f"[Voice Hub] Broadcast error: {e}")
    
    def _heartbeat_monitor_loop(self):
        """Monitor agent heartbeats and cleanup stale agents"""
        print("[Voice Hub] Heartbeat monitor started")
        
        while self.running:
            try:
                time.sleep(30.0)
                
                current_time = time.time()
                stale_agents = []
                
                with self.agents_lock:
                    for agent_id, agent_info in self.agents.items():
                        last_heartbeat = agent_info['last_heartbeat']
                        
                        if current_time - last_heartbeat > 60.0:
                            stale_agents.append(agent_id)
                    
                    for agent_id in stale_agents:
                        agent_name = self.agents[agent_id]['name']
                        del self.agents[agent_id]
                        
                        if agent_id in self.pyttsx3_engines:
                            del self.pyttsx3_engines[agent_id]
                        
                        print(f"[Voice Hub] Removed stale agent: {agent_name}")
                    
                    if len(stale_agents) > 0:
                        print(f"[Voice Hub] Active agents: {len(self.agents)}")
            
            except Exception as e:
                print(f"[Voice Hub] Heartbeat monitor error: {e}")
    
    def shutdown(self):
        """Shutdown Voice Hub"""
        if not self.running:
            return
        
        print("[Voice Hub] Shutting down...")
        
        self.running = False
        
        if self.speech_thread and self.speech_thread.is_alive():
            self.speech_thread.join(timeout=2.0)
        
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=2.0)
        
        self.tts_executor.shutdown(wait=True, cancel_futures=False)
        
        if self.discovery_socket:
            self.discovery_socket.close()
        if self.registry_socket:
            self.registry_socket.close()
        if self.user_speech_pub:
            self.user_speech_pub.close()
        if self.agent_speech_pub:
            self.agent_speech_pub.close()
        if self.tts_socket:
            self.tts_socket.close()
        
        self.context.term()
        
        print("[Voice Hub] Shutdown complete")


def main():
    """Main entry point for Voice Hub Server"""
    print("=" * 70)
    print("VOICE HUB SERVER")
    print("=" * 70)
    
    server = VoiceHubServer()
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Voice Hub] Keyboard interrupt received")
        server.shutdown()
    except Exception as e:
        print(f"[Voice Hub] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        server.shutdown()


if __name__ == "__main__":
    main()