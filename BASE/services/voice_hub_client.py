# ============================================================================
# FILE: BASE/services/voice_hub_client.py
# Voice Hub Client - Agent-side interface
# ============================================================================
"""
Voice Hub Client - Agent-side interface to Voice Hub

Provides agents with:
- Auto-discovery and connection to Voice Hub
- Agent registration with voice configuration
- TTS request submission (non-blocking)
- User speech polling
- Other agents' speech polling
- Automatic heartbeat maintenance
- Reconnection on failure
"""
import zmq
import time
import threading
import uuid
from typing import Optional, Dict, Any
from pathlib import Path

from BASE.services.voice_hub_protocol import (
    HubProtocol,
    HubMessageType,
    HubPorts,
    DiscoveryPing,
    AgentRegistration,
    Heartbeat,
    TTSRequest
)


class VoiceHubClient:
    """Client interface for agents to connect to Voice Hub"""
    
    __slots__ = (
        'logger', 'agent_id', 'agent_name', 'cable_name', 'voice_config',
        'context', 'discovery_socket', 'registry_socket', 'user_speech_socket',
        'agent_speech_socket', 'tts_socket', 'connected', 'registered',
        'heartbeat_thread', 'heartbeat_stop', '_last_heartbeat'
    )
    
    def __init__(self, logger=None):
        """Initialize Voice Hub Client"""
        self.logger = logger
        
        self.agent_id = None
        self.agent_name = None
        self.cable_name = None
        self.voice_config = None
        
        self.context = zmq.Context()
        self.discovery_socket = None
        self.registry_socket = None
        self.user_speech_socket = None
        self.agent_speech_socket = None
        self.tts_socket = None
        
        self.connected = False
        self.registered = False
        
        self.heartbeat_thread = None
        self.heartbeat_stop = threading.Event()
        self._last_heartbeat = 0.0
        
        if self.logger:
            self.logger.system("[Hub Client] Initialized")
    
    def connect(self, timeout: float = 5.0) -> bool:
        """
        Discover and connect to Voice Hub
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            True if connected successfully
        """
        if self.connected:
            if self.logger:
                self.logger.warning("[Hub Client] Already connected")
            return True
        
        if self.logger:
            self.logger.system("[Hub Client] Discovering Voice Hub...")
        
        discovered = self._discover_hub(timeout)
        
        if not discovered:
            if self.logger:
                self.logger.system("[Hub Client] Voice Hub not found")
            return False
        
        if self.logger:
            self.logger.success("[Hub Client] Voice Hub discovered")
        
        try:
            self._connect_sockets()
            self.connected = True
            
            if self.logger:
                self.logger.success("[Hub Client] Connected to Voice Hub")
            
            return True
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Hub Client] Connection failed: {e}")
            self.connected = False
            return False
    
    def _discover_hub(self, timeout: float) -> bool:
        """Try to discover Voice Hub via ping"""
        try:
            self.discovery_socket = self.context.socket(zmq.REQ)
            self.discovery_socket.setsockopt(zmq.LINGER, 0)
            self.discovery_socket.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
            self.discovery_socket.connect(f"tcp://localhost:{HubPorts.DISCOVERY}")
            
            ping = DiscoveryPing(timestamp=time.time())
            self.discovery_socket.send_string(ping.to_json())
            
            response = self.discovery_socket.recv_string()
            pong = HubProtocol.parse_message(response)
            
            if pong and hasattr(pong, 'type') and pong.type == HubMessageType.DISCOVERY_PONG.value:
                if self.logger:
                    self.logger.system(
                        f"[Hub Client] Hub found: v{pong.hub_version}, "
                        f"{pong.active_agents} agent(s) connected"
                    )
                return True
            
            return False
        
        except zmq.Again:
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Hub Client] Discovery error: {e}")
            return False
        finally:
            if self.discovery_socket:
                self.discovery_socket.close()
                self.discovery_socket = None
    
    def _connect_sockets(self):
        """Connect to all Voice Hub services"""
        self.registry_socket = self.context.socket(zmq.REQ)
        self.registry_socket.setsockopt(zmq.LINGER, 0)
        self.registry_socket.setsockopt(zmq.RCVTIMEO, 5000)
        self.registry_socket.connect(f"tcp://localhost:{HubPorts.REGISTRY}")
        
        self.user_speech_socket = self.context.socket(zmq.SUB)
        self.user_speech_socket.setsockopt(zmq.LINGER, 0)
        self.user_speech_socket.setsockopt(zmq.RCVTIMEO, 100)
        self.user_speech_socket.connect(f"tcp://localhost:{HubPorts.USER_SPEECH}")
        self.user_speech_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        self.agent_speech_socket = self.context.socket(zmq.SUB)
        self.agent_speech_socket.setsockopt(zmq.LINGER, 0)
        self.agent_speech_socket.setsockopt(zmq.RCVTIMEO, 100)
        self.agent_speech_socket.connect(f"tcp://localhost:{HubPorts.AGENT_SPEECH}")
        self.agent_speech_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        self.tts_socket = self.context.socket(zmq.REQ)
        self.tts_socket.setsockopt(zmq.LINGER, 0)
        self.tts_socket.setsockopt(zmq.RCVTIMEO, 5000)
        self.tts_socket.connect(f"tcp://localhost:{HubPorts.TTS_REQUEST}")
    
    def register_agent(
        self,
        agent_name: str,
        cable_name: str,
        voice_config: Dict[str, Any]
    ) -> bool:
        """
        Register agent with Voice Hub
        
        Args:
            agent_name: Agent's name
            cable_name: Virtual Cable name for audio output
            voice_config: Voice configuration dict
            
        Returns:
            True if registration successful
        """
        if not self.connected:
            if self.logger:
                self.logger.error("[Hub Client] Not connected to hub")
            return False
        
        if self.registered:
            if self.logger:
                self.logger.warning("[Hub Client] Already registered")
            return True
        
        if not HubProtocol.validate_voice_config(voice_config):
            if self.logger:
                self.logger.error("[Hub Client] Invalid voice configuration")
            return False
        
        try:
            registration = AgentRegistration(
                agent_name=agent_name,
                cable_name=cable_name,
                voice_config=voice_config,
                timestamp=time.time()
            )
            
            self.registry_socket.send_string(registration.to_json())
            response = self.registry_socket.recv_string()
            
            ack = HubProtocol.parse_message(response)
            
            if ack and hasattr(ack, 'success') and ack.success:
                self.agent_id = ack.agent_id
                self.agent_name = agent_name
                self.cable_name = cable_name
                self.voice_config = voice_config
                self.registered = True
                
                self._start_heartbeat()
                
                if self.logger:
                    self.logger.success(
                        f"[Hub Client] Registered as {agent_name} "
                        f"(ID: {self.agent_id[:8]}...)"
                    )
                
                return True
            else:
                if self.logger:
                    error_msg = getattr(ack, 'message', 'Unknown error')
                    self.logger.error(f"[Hub Client] Registration failed: {error_msg}")
                return False
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Hub Client] Registration error: {e}")
            return False
    
    def _start_heartbeat(self):
        """Start heartbeat thread"""
        self.heartbeat_stop.clear()
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="VoiceHubHeartbeat"
        )
        self.heartbeat_thread.start()
        
        if self.logger:
            self.logger.system("[Hub Client] Heartbeat started")
    
    def _heartbeat_loop(self):
        """Heartbeat maintenance loop"""
        while not self.heartbeat_stop.is_set():
            try:
                current_time = time.time()
                
                if current_time - self._last_heartbeat >= 20.0:
                    self.send_heartbeat()
                    self._last_heartbeat = current_time
                
                time.sleep(5.0)
            
            except Exception as e:
                if self.logger:
                    self.logger.error(f"[Hub Client] Heartbeat error: {e}")
                time.sleep(5.0)
    
    def send_heartbeat(self):
        """Send heartbeat to hub"""
        if not self.connected or not self.registered:
            return
        
        try:
            heartbeat = Heartbeat(
                agent_id=self.agent_id,
                timestamp=time.time()
            )
            
            temp_socket = self.context.socket(zmq.REQ)
            temp_socket.setsockopt(zmq.LINGER, 0)
            temp_socket.setsockopt(zmq.RCVTIMEO, 2000)
            temp_socket.connect(f"tcp://localhost:{HubPorts.REGISTRY}")
            
            temp_socket.send_string(heartbeat.to_json())
            temp_socket.recv_string()
            
            temp_socket.close()
        
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[Hub Client] Heartbeat failed: {e}")
    
    def request_speech(
        self,
        text: str,
        voice_config: Optional[Dict[str, Any]] = None,
        volume: float = 1.0,
        blocking: bool = False
    ) -> Dict[str, Any]:
        """
        Request TTS generation from hub
        
        Args:
            text: Text to speak
            voice_config: Optional voice config (uses registered if None)
            volume: Volume level (0.0-1.0)
            blocking: If True, wait for completion (not implemented)
            
        Returns:
            dict with 'status' and 'request_id' or 'error'
        """
        if not self.connected or not self.registered:
            return {
                'status': 'error',
                'error': 'Not connected to hub'
            }
        
        if voice_config is None:
            voice_config = self.voice_config
        
        try:
            request = TTSRequest(
                agent_id=self.agent_id,
                text=text,
                voice_config=voice_config,
                volume=volume,
                timestamp=time.time()
            )
            
            self.tts_socket.send_string(request.to_json())
            response = self.tts_socket.recv_string()
            
            result = HubProtocol.parse_message(response)
            
            if result and hasattr(result, 'type'):
                if result.type == HubMessageType.TTS_ACCEPTED.value:
                    return {
                        'status': 'accepted',
                        'request_id': result.request_id
                    }
                elif result.type == HubMessageType.TTS_ERROR.value:
                    return {
                        'status': 'error',
                        'error': result.error_message
                    }
            
            return {
                'status': 'error',
                'error': 'Invalid response from hub'
            }
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Hub Client] TTS request error: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def poll_user_speech(self, timeout: float = 0.1) -> Optional[str]:
        """
        Poll for user speech from hub
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Recognized text or None
        """
        if not self.connected:
            return None
        
        try:
            self.user_speech_socket.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
            message = self.user_speech_socket.recv_string()
            
            speech = HubProtocol.parse_message(message)
            
            if speech and hasattr(speech, 'text'):
                return speech.text
            
            return None
        
        except zmq.Again:
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Hub Client] User speech poll error: {e}")
            return None
    
    def poll_agent_speech(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        """
        Poll for other agents' speech
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            dict with 'speaker' and 'text' or None
        """
        if not self.connected:
            return None
        
        try:
            self.agent_speech_socket.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
            message = self.agent_speech_socket.recv_string()
            
            speech = HubProtocol.parse_message(message)
            
            if speech and hasattr(speech, 'speaker') and hasattr(speech, 'text'):
                return {
                    'speaker': speech.speaker,
                    'text': speech.text,
                    'timestamp': speech.timestamp
                }
            
            return None
        
        except zmq.Again:
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"[Hub Client] Agent speech poll error: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from Voice Hub"""
        if not self.connected:
            return
        
        if self.logger:
            self.logger.system("[Hub Client] Disconnecting from hub...")
        
        self.heartbeat_stop.set()
        
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=2.0)
        
        if self.registry_socket:
            try:
                unregister = {
                    'type': 'agent_unregister',
                    'agent_id': self.agent_id,
                    'timestamp': time.time()
                }
                self.registry_socket.send_json(unregister)
            except:
                pass
            self.registry_socket.close()
        
        if self.user_speech_socket:
            self.user_speech_socket.close()
        
        if self.agent_speech_socket:
            self.agent_speech_socket.close()
        
        if self.tts_socket:
            self.tts_socket.close()
        
        self.connected = False
        self.registered = False
        
        if self.logger:
            self.logger.system("[Hub Client] Disconnected")
    
    def is_connected(self) -> bool:
        """Check if connected to hub"""
        return self.connected and self.registered
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.disconnect()
            self.context.term()
        except:
            pass