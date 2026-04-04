#!/usr/bin/env python3
# Filename: BASE/api/main.py
"""
FastAPI Backend for Anna AI Agent
Provides REST API and WebSocket endpoints for web-based GUI
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
from pathlib import Path
from datetime import datetime
import traceback

from BASE.core.ai_core import AICore
from BASE.core.config import Config
from personality import bot_info, controls

app = FastAPI(
    title="Anna AI API",
    description="REST API for Anna AI Agent",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ai_core: Optional[AICore] = None
active_websockets: List[WebSocket] = []


class ChatMessage(BaseModel):
    message: str
    source: str = "Web GUI"


class ControlUpdate(BaseModel):
    control_name: str
    value: Any


class ToolToggle(BaseModel):
    tool_name: str
    enabled: bool


class FileUpload(BaseModel):
    filepath: str


@app.on_event("startup")
async def startup_event():
    """Initialize AI Core on startup"""
    global ai_core
    try:
        print("[API] Initializing AI Core...")
        
        # Initialize Config singleton
        config = Config()
        print(f"[API] Config initialized - Agent: {config.agentname}")
        
        # Initialize AI Core with required arguments
        # Note: AICore.__init__ may have async operations that conflict with FastAPI's event loop
        # The internal tools error can be ignored - they'll initialize when needed
        ai_core = AICore(config=config, controls_module=controls)
        
        print("[API] AI Core initialized successfully")
        print(f"[API] Agent: {config.agentname}")
        print(f"[API] Ollama endpoint: {config.get('ollama.endpoint', 'http://ollama:11434')}")
        
    except Exception as e:
        print(f"[API] Failed to initialize AI Core: {e}")
        import traceback
        traceback.print_exc()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global ai_core
    if ai_core:
        print("[API] Shutting down AI Core...")
        # Cleanup if needed


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "agent": bot_info.agentname,
        "version": "1.0.0"
    }


@app.get("/api/status")
async def get_status():
    """Get agent status"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    # Safely get thought count
    memory_count = 0
    if hasattr(ai_core, 'thought_buffer') and ai_core.thought_buffer:
        memory_count = len(ai_core.thought_buffer.thoughts) if hasattr(ai_core.thought_buffer, 'thoughts') else 0
    elif hasattr(ai_core, 'memory_manager') and ai_core.memory_manager:
        # Fallback to memory manager if thought_buffer doesn't exist
        memory_count = len(getattr(ai_core.memory_manager, 'short_memory', []))
    
    # Safely get TTS tool
    active_tts = None
    if hasattr(ai_core, 'internal_tool_manager') and ai_core.internal_tool_manager:
        tts_tool = ai_core.internal_tool_manager.get_active_tts_tool()
        active_tts = tts_tool.tool_name if tts_tool else None
    
    # Safely get voice input tool
    active_voice = None
    if hasattr(ai_core, 'internal_tool_manager') and ai_core.internal_tool_manager:
        voice_tool = ai_core.internal_tool_manager.get_active_voice_input_tool()
        active_voice = voice_tool.tool_name if voice_tool else None
    
    return {
        "agent_name": ai_core.config.agentname,
        "username": ai_core.config.username,
        "continuous_thinking": controls.ENABLE_CONTINUOUS_THINKING,
        "auto_respond": controls.AUTO_RESPOND,
        "avatar_speech": controls.AVATAR_SPEECH,
        "use_memory": controls.USE_MEMORY,
        "memory_count": memory_count,
        "active_tts": active_tts,
        "active_voice_input": active_voice
    }


@app.post("/api/chat")
async def send_chat_message(msg: ChatMessage):
    """Process chat message"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    try:
        response = await ai_core.process_user_message(
            message=msg.message,
            source=msg.source
        )
        
        # Broadcast to websocket clients
        await broadcast_message({
            "type": "agent_response",
            "sender": ai_core.config.agentname,
            "message": response,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        
        return {
            "success": True,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/controls")
async def get_controls():
    """Get all control variables"""
    controls_dict = {}
    for key in dir(controls):
        if key.isupper() and not key.startswith('_'):
            controls_dict[key] = getattr(controls, key)
    
    return controls_dict


@app.post("/api/controls/update")
async def update_control(update: ControlUpdate):
    """Update a control variable"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    try:
        # Update via control manager
        ai_core.control_manager.update_control(
            update.control_name,
            update.value
        )
        
        return {
            "success": True,
            "control": update.control_name,
            "value": update.value
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/memory")
async def get_memory():
    """Get recent memories"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    try:
        short_mem = ai_core.memory_manager.short_memory[-50:] if ai_core.memory_manager.short_memory else []
        medium_mem = ai_core.memory_manager.medium_memory[-50:] if ai_core.memory_manager.medium_memory else []
        
        return {
            "short_term": short_mem,
            "medium_term": medium_mem,
            "total_count": len(short_mem) + len(medium_mem)
        }
    except Exception as e:
        return {
            "error": str(e)
        }


@app.get("/api/conversation_history")
async def get_conversation_history(limit: int = 100):
    """Get conversation history"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    try:
        all_messages = []
        all_messages.extend(ai_core.memory_manager.short_memory)
        all_messages.extend(ai_core.memory_manager.medium_memory)
        
        # Filter to today and yesterday
        from datetime import timedelta
        current_date = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        recent = [
            msg for msg in all_messages
            if msg.get('date') in [current_date, yesterday]
        ]
        
        recent.sort(key=lambda x: x.get('timestamp', ''))
        
        return {
            "messages": recent[-limit:],
            "count": len(recent)
        }
    except Exception as e:
        return {
            "error": str(e),
            "messages": []
        }


@app.get("/api/tools")
async def get_tools():
    """Get all available tools and their status"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    try:
        # Get internal tools
        internal_tools = []
        if ai_core.internal_tool_manager:
            tts_tools = ai_core.internal_tool_manager.get_tools_by_service('tts')
            voice_tools = ai_core.internal_tool_manager.get_tools_by_service('voice_input')
            
            for tool in tts_tools + voice_tools:
                internal_tools.append({
                    "name": tool.tool_name,
                    "display_name": tool.display_name,
                    "service_type": tool.service_type,
                    "enabled": tool.is_enabled,
                    "available": tool.is_available(),
                    "priority": tool.priority,
                    "category": "Internal"
                })
        
        # Get external tools
        external_tools = []
        if ai_core.tool_manager:
            for tool_name, tool_info in ai_core.tool_manager.available_tools.items():
                external_tools.append({
                    "name": tool_name,
                    "display_name": tool_info.get('display_name', tool_name),
                    "description": tool_info.get('description', ''),
                    "enabled": ai_core.tool_manager.is_tool_enabled(tool_name),
                    "category": tool_info.get('category', 'External')
                })
        
        return {
            "internal_tools": internal_tools,
            "external_tools": external_tools
        }
    except Exception as e:
        return {
            "error": str(e),
            "internal_tools": [],
            "external_tools": []
        }


@app.post("/api/tools/toggle")
async def toggle_tool(toggle: ToolToggle):
    """Enable or disable a tool"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    try:
        # Check if it's an internal tool
        if ai_core.internal_tool_manager:
            tool = ai_core.internal_tool_manager.get_tool_by_name(toggle.tool_name)
            if tool:
                if toggle.enabled:
                    ai_core.internal_tool_manager.enable_tool(toggle.tool_name)
                else:
                    ai_core.internal_tool_manager.disable_tool(toggle.tool_name)
                
                return {
                    "success": True,
                    "tool": toggle.tool_name,
                    "enabled": toggle.enabled
                }
        
        # Check if it's an external tool
        if ai_core.tool_manager:
            if toggle.enabled:
                ai_core.tool_manager.enable_tool(toggle.tool_name)
            else:
                ai_core.tool_manager.disable_tool(toggle.tool_name)
            
            return {
                "success": True,
                "tool": toggle.tool_name,
                "enabled": toggle.enabled
            }
        
        return {
            "success": False,
            "error": f"Tool {toggle.tool_name} not found"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/session_files")
async def get_session_files():
    """Get list of uploaded session files"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    try:
        files = ai_core.list_session_files()
        return {
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        return {
            "error": str(e),
            "files": []
        }


@app.post("/api/session_files/upload")
async def upload_session_file(file_data: FileUpload):
    """Upload a session file"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    try:
        file_path = Path(file_data.filepath)
        if not file_path.exists():
            return {
                "success": False,
                "error": "File not found"
            }
        
        result = ai_core.load_session_file(file_path)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.delete("/api/session_files/{file_id}")
async def delete_session_file(file_id: str):
    """Delete a session file"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    try:
        ai_core.unload_session_file(file_id)
        return {
            "success": True,
            "file_id": file_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    if not ai_core:
        raise HTTPException(status_code=503, detail="AI Core not initialized")
    
    return {
        "agent_name": ai_core.config.agentname,
        "username": ai_core.config.username,
        "models": {
            "thought": bot_info.thoughtmodel,
            "response": bot_info.responsemodel,
            "vision": bot_info.visionmodel,
            "tool": bot_info.toolmodel
        },
        "voice_index": bot_info.voiceIndex,
        "vb_cable": bot_info.vb_cable_name
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()
    active_websockets.append(websocket)
    
    try:
        while True:
            # Keep connection alive and receive messages
            data = await websocket.receive_text()
            
            # Echo back for now (can be used for commands)
            await websocket.send_json({
                "type": "echo",
                "data": data
            })
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)


async def broadcast_message(message: dict):
    """Broadcast message to all connected WebSocket clients"""
    for websocket in active_websockets:
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"[WebSocket] Failed to send to client: {e}")


@app.get("/api/thoughts")
async def get_recent_thoughts(limit: int = 20):
    """Get recent thoughts from thought buffer"""
    if not ai_core or not ai_core.thought_buffer:
        return {"thoughts": []}
    
    try:
        thoughts = ai_core.thought_buffer.thoughts[-limit:]
        return {
            "thoughts": [
                {
                    "content": t.content,
                    "priority": t.priority.name if hasattr(t.priority, 'name') else str(t.priority),
                    "timestamp": t.timestamp
                }
                for t in thoughts
            ]
        }
    except Exception as e:
        return {
            "error": str(e),
            "thoughts": []
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)