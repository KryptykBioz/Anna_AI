# ============================================================================
# FILE: BASE/services/voice_hub_protocol.py
# Voice Hub Protocol Definitions
# ============================================================================
"""
Voice Hub Protocol - Shared protocol definitions for Voice Hub communication

Defines ports, message types, and data structures used for communication
between Voice Hub Server and Voice Hub Clients (agents).

This protocol is agent-agnostic and focuses purely on voice infrastructure.
"""
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import json


class HubPorts:
    """Port assignments for Voice Hub services"""
    DISCOVERY = 5561
    REGISTRY = 5557
    USER_SPEECH = 5558
    AGENT_SPEECH = 5559
    TTS_REQUEST = 5560


class HubMessageType(Enum):
    """Message types in Voice Hub protocol"""
    DISCOVERY_PING = "discovery_ping"
    DISCOVERY_PONG = "discovery_pong"
    AGENT_REGISTER = "agent_register"
    AGENT_REGISTER_ACK = "agent_register_ack"
    AGENT_UNREGISTER = "agent_unregister"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    USER_SPEECH = "user_speech"
    AGENT_SPEECH = "agent_speech"
    TTS_REQUEST = "tts_request"
    TTS_ACCEPTED = "tts_accepted"
    TTS_ERROR = "tts_error"
    SHUTDOWN = "shutdown"


@dataclass
class DiscoveryPing:
    """Discovery ping message to check if hub is running"""
    type: str = HubMessageType.DISCOVERY_PING.value
    timestamp: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'DiscoveryPing':
        d = json.loads(data)
        return DiscoveryPing(**d)


@dataclass
class DiscoveryPong:
    """Discovery pong response from hub"""
    type: str = HubMessageType.DISCOVERY_PONG.value
    timestamp: float = 0.0
    hub_version: str = "1.0.0"
    active_agents: int = 0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'DiscoveryPong':
        d = json.loads(data)
        return DiscoveryPong(**d)


@dataclass
class AgentRegistration:
    """Agent registration message"""
    type: str = HubMessageType.AGENT_REGISTER.value
    agent_name: str = ""
    cable_name: str = ""
    voice_config: Dict[str, Any] = None
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.voice_config is None:
            self.voice_config = {}
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'AgentRegistration':
        d = json.loads(data)
        return AgentRegistration(**d)


@dataclass
class AgentRegistrationAck:
    """Agent registration acknowledgment"""
    type: str = HubMessageType.AGENT_REGISTER_ACK.value
    success: bool = False
    agent_id: str = ""
    message: str = ""
    timestamp: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'AgentRegistrationAck':
        d = json.loads(data)
        return AgentRegistrationAck(**d)


@dataclass
class Heartbeat:
    """Heartbeat message to maintain connection"""
    type: str = HubMessageType.HEARTBEAT.value
    agent_id: str = ""
    timestamp: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'Heartbeat':
        d = json.loads(data)
        return Heartbeat(**d)


@dataclass
class HeartbeatAck:
    """Heartbeat acknowledgment"""
    type: str = HubMessageType.HEARTBEAT_ACK.value
    timestamp: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'HeartbeatAck':
        d = json.loads(data)
        return HeartbeatAck(**d)


@dataclass
class UserSpeech:
    """User speech recognition result broadcast"""
    type: str = HubMessageType.USER_SPEECH.value
    text: str = ""
    timestamp: float = 0.0
    confidence: float = 1.0
    backend: str = "whisper"
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'UserSpeech':
        d = json.loads(data)
        return UserSpeech(**d)


@dataclass
class AgentSpeech:
    """Agent speech notification to other agents"""
    type: str = HubMessageType.AGENT_SPEECH.value
    speaker: str = ""
    text: str = ""
    timestamp: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'AgentSpeech':
        d = json.loads(data)
        return AgentSpeech(**d)


@dataclass
class TTSRequest:
    """TTS generation request from agent"""
    type: str = HubMessageType.TTS_REQUEST.value
    agent_id: str = ""
    text: str = ""
    voice_config: Dict[str, Any] = None
    volume: float = 1.0
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.voice_config is None:
            self.voice_config = {}
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'TTSRequest':
        d = json.loads(data)
        return TTSRequest(**d)


@dataclass
class TTSAccepted:
    """TTS request accepted response"""
    type: str = HubMessageType.TTS_ACCEPTED.value
    request_id: str = ""
    timestamp: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'TTSAccepted':
        d = json.loads(data)
        return TTSAccepted(**d)


@dataclass
class TTSError:
    """TTS request error response"""
    type: str = HubMessageType.TTS_ERROR.value
    error_message: str = ""
    timestamp: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'TTSError':
        d = json.loads(data)
        return TTSError(**d)


class HubProtocol:
    """Protocol utilities and helpers"""
    
    @staticmethod
    def create_message(msg_type: HubMessageType, **kwargs) -> str:
        """Create a protocol message"""
        message_classes = {
            HubMessageType.DISCOVERY_PING: DiscoveryPing,
            HubMessageType.DISCOVERY_PONG: DiscoveryPong,
            HubMessageType.AGENT_REGISTER: AgentRegistration,
            HubMessageType.AGENT_REGISTER_ACK: AgentRegistrationAck,
            HubMessageType.HEARTBEAT: Heartbeat,
            HubMessageType.HEARTBEAT_ACK: HeartbeatAck,
            HubMessageType.USER_SPEECH: UserSpeech,
            HubMessageType.AGENT_SPEECH: AgentSpeech,
            HubMessageType.TTS_REQUEST: TTSRequest,
            HubMessageType.TTS_ACCEPTED: TTSAccepted,
            HubMessageType.TTS_ERROR: TTSError,
        }
        
        msg_class = message_classes.get(msg_type)
        if not msg_class:
            raise ValueError(f"Unknown message type: {msg_type}")
        
        msg = msg_class(**kwargs)
        return msg.to_json()
    
    @staticmethod
    def parse_message(data: str) -> Optional[Any]:
        """Parse a protocol message"""
        try:
            d = json.loads(data)
            msg_type_str = d.get('type')
            
            if not msg_type_str:
                return None
            
            message_classes = {
                HubMessageType.DISCOVERY_PING.value: DiscoveryPing,
                HubMessageType.DISCOVERY_PONG.value: DiscoveryPong,
                HubMessageType.AGENT_REGISTER.value: AgentRegistration,
                HubMessageType.AGENT_REGISTER_ACK.value: AgentRegistrationAck,
                HubMessageType.HEARTBEAT.value: Heartbeat,
                HubMessageType.HEARTBEAT_ACK.value: HeartbeatAck,
                HubMessageType.USER_SPEECH.value: UserSpeech,
                HubMessageType.AGENT_SPEECH.value: AgentSpeech,
                HubMessageType.TTS_REQUEST.value: TTSRequest,
                HubMessageType.TTS_ACCEPTED.value: TTSAccepted,
                HubMessageType.TTS_ERROR.value: TTSError,
            }
            
            msg_class = message_classes.get(msg_type_str)
            if not msg_class:
                return None
            
            return msg_class.from_json(data)
        
        except Exception as e:
            print(f"[Protocol] Error parsing message: {e}")
            return None
    
    @staticmethod
    def validate_voice_config(voice_config: Dict[str, Any]) -> bool:
        """Validate voice configuration structure"""
        if not isinstance(voice_config, dict):
            return False
        
        voice_type = voice_config.get('type')
        if voice_type not in ['xtts', 'pyttsx3']:
            return False
        
        if voice_type == 'xtts':
            required = ['voice_sample', 'language', 'speed']
            return all(k in voice_config for k in required)
        
        elif voice_type == 'pyttsx3':
            required = ['voice_index', 'rate']
            return all(k in voice_config for k in required)
        
        return False