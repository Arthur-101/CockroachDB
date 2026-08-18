"""FastAPI chat server for AgenticAI."""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.controller.chat_router import ChatRouter
from src.memory.cockroach_store import SQLiteMemoryStore
from src.tools.terminal_manager import terminal_manager


app = FastAPI(title="AgenticAI Chat API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global chat router instance
chat_router: Optional[ChatRouter] = None


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None
    model_override: Optional[str] = None
    use_tags: bool = True
    use_summaries: bool = True


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    model: str
    session_id: str
    tokens_used: int
    tags: List[str]


class HistoryRequest(BaseModel):
    """History request model."""
    session_id: Optional[str] = None
    limit: int = 20


class HistoryResponse(BaseModel):
    """History response model."""
    messages: List[Dict[str, Any]]
    session_id: str


# Initialize chat router
print("Starting AgenticAI Chat API initialization...")
try:
    chat_router = ChatRouter()
    print("ChatRouter instance created")
    # Note: initialize_client() is async, we'll initialize lazily on first request
    print("AgenticAI Chat API initialized successfully (client will initialize on first request)")
except Exception as e:
    print(f"FATAL: Failed to initialize chat router: {e}")
    import traceback
    traceback.print_exc()
    raise


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Handle chat requests."""
    global chat_router
    if not chat_router:
        raise HTTPException(status_code=500, detail="Chat router not initialized")
    
    try:
        result = await chat_router.chat(
            user_message=request.message,
            session_id=request.session_id,
            model_override=request.model_override,
            use_tags=request.use_tags,
            use_summaries=request.use_summaries,
        )
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/history", response_model=HistoryResponse)
async def history_endpoint(request: HistoryRequest) -> HistoryResponse:
    """Get chat history."""
    global chat_router
    if not chat_router:
        raise HTTPException(status_code=500, detail="Chat router not initialized")
    
    try:
        messages = chat_router.get_session_history(
            session_id=request.session_id,
            limit=request.limit,
        )
        session_id = request.session_id or chat_router.current_session_id
        return HistoryResponse(messages=messages, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/new-session")
async def new_session() -> Dict[str, str]:
    """Start a new chat session."""
    global chat_router
    if not chat_router:
        raise HTTPException(status_code=500, detail="Chat router not initialized")
    
    try:
        session_id = chat_router.new_session()
        return {"session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# We need the main event loop to send websocket messages from the read thread
main_loop = None

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()
    
    def on_terminal_output(data: str):
        if main_loop and not main_loop.is_closed():
            asyncio.run_coroutine_threadsafe(manager.broadcast(data), main_loop)
            
    terminal_manager.register_callback(on_terminal_output)
    import sys
    print(f"DEBUG: chat_server registered callback to terminal instance {id(terminal_manager)}", file=sys.stderr, flush=True)

@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    import sys
    print(f"DEBUG: websocket connected, terminal manager instance is {id(terminal_manager)}", file=sys.stderr, flush=True)
    await manager.connect(websocket)
    try:
        if not terminal_manager.is_running:
            terminal_manager.start()
        else:
            # Send current history to the newly connected client
            # Delay slightly to allow frontend terminal to finish resizing
            await asyncio.sleep(0.2)
            history = terminal_manager.get_history(lines=1000)
            if history:
                # Need to replace newlines with \r\n for xterm.js
                formatted_history = history.replace('\n', '\r\n')
                await websocket.send_text(formatted_history + '\r\n')
            
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "input":
                    terminal_manager.write(msg.get("data", ""))
                elif msg.get("type") == "resize":
                    terminal_manager.resize(msg.get("rows", 24), msg.get("cols", 80))
            except json.JSONDecodeError:
                # Fallback to plain text if not JSON
                terminal_manager.write(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    global chat_router
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "agenticai-chat-api",
        "router_initialized": chat_router is not None
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AgenticAI Chat API", "status": "running"}

@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get session statistics."""
    global chat_router
    if not chat_router:
        raise HTTPException(status_code=500, detail="Chat router not initialized")
    
    try:
        stats = chat_router.get_session_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Cleanup on shutdown
import atexit

@atexit.register
def cleanup():
    """Cleanup resources when server shuts down."""
    global chat_router
    if chat_router:
        try:
            chat_router.close()
            print("Chat router cleanup complete")
        except Exception as e:
            print(f"Error during cleanup: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("AGENTICAI_API_PORT", "8000"))
    print(f"Starting uvicorn server on http://127.0.0.1:{port}")
    # Use module string to avoid import issues and keep server alive
    uvicorn.run("src.api.chat_server:app", host="127.0.0.1", port=port, log_level="info", access_log=True)