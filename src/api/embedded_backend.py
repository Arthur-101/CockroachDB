#!/usr/bin/env python3
"""
Minimal Python backend for Tauri integration.
Communicates via stdin/stdout JSON-RPC instead of HTTP.
"""

import sys
import json
import traceback
from typing import Dict, Any, Optional
import os
import asyncio
import subprocess

# -----------------------------------------------------------------------
# Resolve project root from THIS file's location and load .env explicitly
# with an absolute path — works regardless of where Tauri spawns us from.
# -----------------------------------------------------------------------
_HERE = os.path.abspath(__file__)                        # …/src/api/embedded_backend.py
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))  # …/CockroachAI

# Add project root to Python path
sys.path.insert(0, _PROJECT_ROOT)

# Load .env before any project module is imported (they read os.environ at import time)
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(_PROJECT_ROOT, ".env")
    load_dotenv(dotenv_path=_env_path, override=False)
    print(f"INFO: Loaded .env from {_env_path}", file=sys.stderr)
except ImportError:
    print("WARNING: python-dotenv not installed — .env not loaded automatically.", file=sys.stderr)

from src.memory.cockroach_store import SQLiteMemoryStore, SessionManager
from src.controller.chat_router import ChatRouter
from src.utils.config import config


class EmbeddedBackend:
    """Minimal backend that handles JSON-RPC requests via stdin/stdout."""
    
    def __init__(self):
        self.memory = SQLiteMemoryStore()
        self.router = ChatRouter(
            memory_store=self.memory
        )
        print("INFO: Embedded backend initialized", file=sys.stderr)
        
        # Run uvicorn server in a background thread so it shares memory and singletons
        import threading
        import socket
        import uvicorn
        from src.api.chat_server import app

        def _find_free_port(preferred: int) -> int:
            """Return preferred port if free, otherwise let OS pick one."""
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", preferred))
                return preferred
            except OSError:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", 0))
                    return s.getsockname()[1]

        def run_uvicorn():
            preferred = int(os.getenv("AGENTICAI_API_PORT", "8000"))
            port = _find_free_port(preferred)
            if port != preferred:
                print(f"INFO: Port {preferred} in use — chat server binding to {port}", file=sys.stderr)
            os.environ["AGENTICAI_API_PORT"] = str(port)   # publish to rest of process
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="error", access_log=False)
            
        self.chat_server_thread = threading.Thread(target=run_uvicorn, daemon=True)
        self.chat_server_thread.start()
        print("INFO: Chat server started in background thread", file=sys.stderr)
        
    def __del__(self):
        pass
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a JSON-RPC request and return response."""
        try:
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "chat":
                return await self._handle_chat(params)
            elif method == "health":
                return self._handle_health()
            elif method == "history":
                return self._handle_history(params)
            elif method == "new_session":
                return self._handle_new_session()
            elif method == "get_sessions":
                return self._handle_get_sessions()
            elif method == "delete_session":
                return self._handle_delete_session(params)
            elif method == "get_all_memories":
                return self._handle_get_all_memories()
            elif method == "add_memory":
                return self._handle_add_memory(params)
            elif method == "update_memory":
                return self._handle_update_memory(params)
            elif method == "delete_memory":
                return self._handle_delete_memory(params)
            elif method == "index_document":
                return self._handle_index_document(params)
            elif method == "get_available_models":
                return await self._handle_get_available_models(params)
            elif method == "get_role_models":
                return self._handle_get_role_models()
            elif method == "update_role_model":
                return self._handle_update_role_model(params)
            elif method == "get_api_keys":
                return self._handle_get_api_keys()
            elif method == "add_api_key":
                return self._handle_add_api_key(params)
            elif method == "delete_api_key":
                return self._handle_delete_api_key(params)
            elif method == "test_api_key":
                return await self._handle_test_api_key(params)
            elif method == "get_model_tracker_data":
                return await self._handle_get_model_tracker_data()
            elif method == "save_model_note":
                return self._handle_save_model_note(params)
            elif method == "get_mcp_servers":
                return self._handle_get_mcp_servers()
            elif method == "add_mcp_server":
                return self._handle_add_mcp_server(params)
            elif method == "delete_mcp_server":
                return self._handle_delete_mcp_server(params)
            elif method == "get_mcp_logs":
                return self._handle_get_mcp_logs(params)
            elif method == "get_incidents":
                return self._handle_get_incidents(params)
            elif method == "ingest_incident":
                return self._handle_ingest_incident(params)
            elif method == "get_runbooks":
                return self._handle_get_runbooks(params)
            elif method == "save_runbook":
                return self._handle_save_runbook(params)
            elif method == "get_fix_history":
                return self._handle_get_fix_history(params)
            # --- Amazon S3 Knowledge Base ---
            elif method == "s3_test_connection":
                return await self._handle_s3_test_connection()
            elif method == "s3_list_all":
                return await self._handle_s3_list_all(params)
            elif method == "s3_upload_runbook":
                return await self._handle_s3_upload_runbook(params)
            elif method == "s3_fetch_runbook":
                return await self._handle_s3_fetch_runbook(params)
            elif method == "s3_sync_to_cockroachdb":
                return await self._handle_s3_sync_to_cockroachdb(params)
            elif method == "s3_upload_incident":
                return await self._handle_s3_upload_incident(params)
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": request.get("id")
                }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                    "data": traceback.format_exc()
                },
                "id": request.get("id")
            }
    
    async def _handle_chat(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat request."""
        message = params.get("message", "")
        session_id = params.get("session_id")
        model_override = params.get("model_override")
        use_tags = params.get("use_tags", True)
        use_summaries = params.get("use_summaries", True)
        
        if not message:
            raise ValueError("Message is required")
        
        result = await self.router.chat(
            user_message=message,
            session_id=session_id,
            model_override=model_override,
            use_tags=use_tags,
            use_summaries=use_summaries
        )
        
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": params.get("request_id")
        }
    
    def _handle_health(self) -> Dict[str, Any]:
        """Handle health check."""
        from src.memory.redis_store import redis_store
        return {
            "jsonrpc": "2.0",
            "result": {
                "status": "healthy",
                "router_initialized": True,
                "service": "agenticai-embedded",
                "redis_connected": redis_store.is_connected()
            },
            "id": None
        }
    
    def _handle_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle history request."""
        session_id = params.get("session_id")
        limit = params.get("limit", 50)
        
        messages = self.memory.get_messages(
            session_id=session_id,
            limit=limit
        )
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "messages": messages
            },
            "id": params.get("request_id")
        }
    
    def _handle_new_session(self) -> Dict[str, Any]:
        """Handle new session creation."""
        session_id = self.router.new_session()
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "session_id": session_id
            },
            "id": None
        }

    def _handle_get_sessions(self) -> Dict[str, Any]:
        """Handle request to get all sessions."""
        sessions = self.memory.get_all_sessions()
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "sessions": sessions
            },
            "id": None
        }

    def _handle_delete_session(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id")
        success = self.memory.delete_session(session_id)
        return {
            "jsonrpc": "2.0",
            "result": {"success": success},
            "id": params.get("request_id")
        }

    def _handle_get_all_memories(self) -> Dict[str, Any]:
        memories = self.memory.get_all_user_memories()
        return {
            "jsonrpc": "2.0",
            "result": {"memories": memories},
            "id": None
        }

    def _handle_add_memory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        content = params.get("content", "").strip()
        tags = params.get("tags", ["manual"])
        if not content:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "Memory content cannot be empty"},
                "id": params.get("request_id")
            }
        
        memory_id = self.memory.save_user_memory(content, tags)
        try:
            self.router.vector_store.add_user_memory(memory_id, content)
        except Exception as e:
            print(f"Warning: Failed to add user memory to vector store: {e}", file=sys.stderr)
            
        return {
            "jsonrpc": "2.0",
            "result": {"success": True, "memory_id": memory_id},
            "id": params.get("request_id")
        }

    def _handle_update_memory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        message_id = params.get("message_id")
        content = params.get("content")
        success = self.memory.update_user_memory(message_id, content)
        if success:
            self.router.vector_store.update_user_memory(message_id, content)
        return {
            "jsonrpc": "2.0",
            "result": {"success": success},
            "id": params.get("request_id")
        }

    def _handle_delete_memory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        memory_id = params.get("memory_id")
        success = self.memory.delete_user_memory(memory_id)
        if success:
            self.router.vector_store.delete_user_memory(memory_id)
        return {
            "jsonrpc": "2.0",
            "result": {"success": success},
            "id": params.get("request_id")
        }

    def _handle_index_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process a document and index its contents into ChromaDB vector store."""
        file_path = (params.get("file_path") or params.get("filePath") or "").strip()
        if not file_path or not os.path.exists(file_path):
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": f"File not found: {file_path}"},
                "id": params.get("request_id")
            }
            
        try:
            from src.processors.file_processor import FileProcessor
            content = FileProcessor.process_file(file_path)
            self.router.vector_store.add_document(
                file_path=file_path,
                content=content
            )
            file_name = os.path.basename(file_path)
            char_count = len(content)
            chunk_count = (char_count // 800) + 1
            
            data_url = None
            _, ext = os.path.splitext(file_path)
            ext_lower = ext.lower()
            if ext_lower in ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.svg']:
                try:
                    import base64
                    with open(file_path, 'rb') as img_f:
                        encoded = base64.b64encode(img_f.read()).decode('utf-8')
                        mime = 'image/png' if ext_lower == '.png' else 'image/jpeg' if ext_lower in ['.jpg', '.jpeg'] else f'image/{ext_lower[1:]}'
                        data_url = f"data:{mime};base64,{encoded}"
                except Exception as img_err:
                    print(f"Error encoding image base64: {img_err}", file=sys.stderr)

            return {
                "jsonrpc": "2.0",
                "result": {
                    "status": "success",
                    "file_path": file_path,
                    "file_name": file_name,
                    "character_count": char_count,
                    "chunk_count": chunk_count,
                    "content_snippet": content[:300],
                    "data_url": data_url
                },
                "id": params.get("request_id")
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": params.get("request_id")
            }

    async def _handle_get_available_models(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch available models with cost information for a provider."""
        provider = params.get("provider", "openrouter")
        from src.models.provider_router import ProviderRouter
        pr = ProviderRouter(memory_store=self.memory)
        models = await pr.fetch_provider_models(provider)
        return {
            "jsonrpc": "2.0",
            "result": {"models": models, "provider": provider},
            "id": params.get("request_id")
        }

    def _handle_get_role_models(self) -> Dict[str, Any]:
        """Fetch active provider & model assignment for all roles."""
        db_roles = self.memory.get_role_assignments()
        defaults = {
            "orchestrator": {"provider": "openrouter", "model_id": "qwen/qwen3.5-flash-02-23"},
            "coding": {"provider": "openrouter", "model_id": "deepseek/deepseek-v4-flash"},
            "reasoning": {"provider": "openrouter", "model_id": "deepseek/deepseek-v4-pro"},
            "multimodal": {"provider": "openrouter", "model_id": "google/gemini-2.5-flash-lite"},
            "synthesizer": {"provider": "openrouter", "model_id": "google/gemini-2.5-flash-lite"}
        }
        from src.memory.redis_store import redis_store
        for role in defaults:
            if redis_store.is_connected():
                redis_str = redis_store.get_role_model(role)
                if redis_str and redis_str.strip():
                    parts = redis_str.strip().split(":", 1)
                    if len(parts) == 2:
                        defaults[role] = {"provider": parts[0], "model_id": parts[1]}
                    else:
                        defaults[role]["model_id"] = parts[0]
                    continue
            if role in db_roles:
                defaults[role] = db_roles[role]
                
        return {
            "jsonrpc": "2.0",
            "result": {"role_models": defaults},
            "id": None
        }

    def _handle_update_role_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update model assignment for a role and update Redis + SQLite."""
        role = params.get("role", "").lower().strip()
        provider = params.get("provider", "openrouter").lower().strip()
        model_id = (params.get("model_id") or params.get("modelId") or "").strip()
        if not role or not model_id:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "Role, provider, and model_id are required"},
                "id": params.get("request_id")
            }
        success = self.memory.save_role_assignment(role, provider, model_id)
        from src.memory.redis_store import redis_store
        if redis_store.is_connected():
            redis_store.set_role_model(role, f"{provider}:{model_id}")
            
        print(f"INFO: Model assigned to role [{role}] -> [{provider}] {model_id}", file=sys.stderr, flush=True)
        return {
            "jsonrpc": "2.0",
            "result": {"success": success, "role": role, "provider": provider, "model_id": model_id},
            "id": params.get("request_id")
        }

    def _handle_get_api_keys(self) -> Dict[str, Any]:
        """Get list of registered provider API keys."""
        keys = self.memory.get_api_keys()
        # Obfuscate values for privacy
        safe_keys = []
        for k in keys:
            val = k.get("key_value", "")
            masked = f"{val[:6]}...{val[-4:]}" if len(val) > 10 else "••••••••"
            safe_keys.append({
                "id": str(k.get("id")) if k.get("id") else None,
                "provider": k.get("provider"),
                "label": k.get("label"),
                "masked_value": masked,
                "is_active": k.get("is_active"),
                "added_at": str(k.get("added_at")) if k.get("added_at") is not None else None,
            })
        return {
            "jsonrpc": "2.0",
            "result": {"api_keys": safe_keys},
            "id": None
        }

    def _handle_add_api_key(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update an API key for a provider."""
        provider = params.get("provider", "").strip().lower()
        key_value = (params.get("key_value") or params.get("keyValue") or "").strip()
        label = params.get("label")
        if not provider or not key_value:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "Provider and key_value are required"},
                "id": params.get("request_id")
            }
        key_id = self.memory.save_api_key(provider, key_value, label)
        print(f"INFO: Saved API Key for provider [{provider}]", file=sys.stderr, flush=True)
        return {
            "jsonrpc": "2.0",
            "result": {"success": True, "key_id": key_id, "provider": provider},
            "id": params.get("request_id")
        }

    def _handle_delete_api_key(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an API key for a provider."""
        provider = params.get("provider", "").strip().lower()
        success = self.memory.delete_api_key(provider)
        print(f"INFO: Deleted API Key for provider [{provider}]", file=sys.stderr, flush=True)
        return {
            "jsonrpc": "2.0",
            "result": {"success": success, "provider": provider},
            "id": params.get("request_id")
        }

    async def _handle_test_api_key(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Test API key for a provider."""
        provider = (params.get("provider") or "").strip().lower()
        key_value = (params.get("key_value") or params.get("keyValue") or "").strip()
        model_id = params.get("model_id") or params.get("modelId")
        
        # If no key_value provided, look up from DB or env
        if not key_value:
            from src.models.provider_router import ProviderRouter
            pr = ProviderRouter(memory_store=self.memory)
            key_value = (pr.get_api_key_for_provider(provider) or "").strip()
            
        if not provider or not key_value:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "error": f"No API Key found for provider [{provider}]. Please enter a key or set environment variable."},
                "id": params.get("request_id")
            }
            
        from src.models.provider_router import ProviderRouter
        router = ProviderRouter(memory_store=self.memory)
        res = await router.test_provider_key(provider, key_value, model_id)
        return {
            "jsonrpc": "2.0",
            "result": res,
            "id": params.get("request_id")
        }

    async def _handle_get_model_tracker_data(self) -> Dict[str, Any]:
        """Fetch combined catalog, usage stats, and notes for Model Tracker & Favorites."""
        from src.models.provider_router import ProviderRouter
        pr = ProviderRouter(memory_store=self.memory)
        
        providers = ["bedrock", "google", "openai", "anthropic", "groq", "mistral"]
        all_models = []
        
        for prov in providers:
            try:
                cat = await pr.fetch_provider_models(prov)
                for m in cat:
                    m["provider"] = prov
                    all_models.append(m)
            except Exception:
                pass
                
        user_notes = self.memory.get_model_notes()
        usage_stats = self.memory.get_model_usage_stats()
        
        tracker_items = []
        seen_ids = set()
        
        for m in all_models:
            mid = m["id"]
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            
            note_info = user_notes.get(mid, {})
            u_info = usage_stats.get(mid, {})
            
            tracker_items.append({
                "model_id": mid,
                "name": m.get("name", mid),
                "provider": m.get("provider", "openrouter"),
                "cost_label": m.get("cost_label", "Standard"),
                "is_active": m.get("is_active", True),
                "is_favorite": note_info.get("is_favorite", False),
                "notes": note_info.get("notes", ""),
                "call_count": u_info.get("call_count", 0),
                "last_used": u_info.get("last_used", None)
            })
            
        tracker_items.sort(key=lambda x: (not x["is_favorite"], -x["call_count"]))

        return {
            "jsonrpc": "2.0",
            "result": {"models": tracker_items},
            "id": None
        }

    def _handle_save_model_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save user note and favorite status for a model."""
        model_id = (params.get("model_id") or params.get("modelId") or "").strip()
        provider = params.get("provider", "openrouter").strip()
        fav_val = params.get("is_favorite") if "is_favorite" in params else params.get("isFavorite", 0)
        is_favorite = 1 if fav_val else 0
        notes = params.get("notes", "").strip()
        
        if not model_id:
            return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "model_id is required"}}
            
        success = self.memory.save_model_note(model_id, provider, is_favorite, notes)
        return {
            "jsonrpc": "2.0",
            "result": {"success": success, "model_id": model_id, "is_favorite": bool(is_favorite), "notes": notes},
            "id": params.get("request_id")
        }

    def _handle_get_mcp_servers(self) -> Dict[str, Any]:
        """Fetch all configured MCP servers with status and tools metadata."""
        from src.tools.mcp_manager import mcp_manager
        try:
            servers = mcp_manager.get_all_servers()
            return {
                "jsonrpc": "2.0",
                "result": {"success": True, "servers": servers},
                "id": None
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "message": str(e)},
                "id": None
            }

    def _handle_add_mcp_server(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add or update an MCP server configuration."""
        from src.tools.mcp_manager import mcp_manager
        try:
            name = params.get("name", "").strip()
            command = params.get("command", "").strip()
            args = params.get("args", [])
            env = params.get("env", {})
            enabled = params.get("enabled", True)
            
            if not name or not command:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Server name and command are required"},
                    "id": params.get("request_id")
                }
                
            success = mcp_manager.add_server(name, command, args, env, enabled)
            return {
                "jsonrpc": "2.0",
                "result": {"success": success},
                "id": params.get("request_id")
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "message": str(e)},
                "id": params.get("request_id")
            }

    def _handle_delete_mcp_server(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an MCP server config and terminate running client process."""
        from src.tools.mcp_manager import mcp_manager
        try:
            name = params.get("name", "").strip()
            if not name:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Server name is required"},
                    "id": params.get("request_id")
                }
            success = mcp_manager.delete_server(name)
            return {
                "jsonrpc": "2.0",
                "result": {"success": success},
                "id": params.get("request_id")
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "message": str(e)},
                "id": params.get("request_id")
            }

    def _handle_get_mcp_logs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve circular buffer logs for a specific MCP server."""
        from src.tools.mcp_manager import mcp_manager
        try:
            name = params.get("name", "").strip()
            if not name:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Server name is required"},
                    "id": params.get("request_id")
                }
            logs = mcp_manager.get_logs(name)
            return {
                "jsonrpc": "2.0",
                "result": {"success": True, "logs": logs},
                "id": params.get("request_id")
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "message": str(e)},
                "id": params.get("request_id")
            }


    def _handle_get_incidents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve recent incidents, optionally filtered by status/severity/service."""
        try:
            status = params.get("status")
            severity = params.get("severity")
            service_name = params.get("service_name") or params.get("serviceName")
            limit = params.get("limit", 20)
            
            incidents = self.memory.get_incidents(
                status=status,
                severity=severity,
                service_name=service_name,
                limit=limit
            )
            return {
                "jsonrpc": "2.0",
                "result": {"success": True, "incidents": incidents},
                "id": params.get("request_id")
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "message": str(e)},
                "id": params.get("request_id")
            }

    def _handle_ingest_incident(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest a new SRE incident and trigger vector embeddings generation."""
        try:
            from src.tools.basic_tools import BasicTools
            bt = BasicTools(require_permission=False)
            
            res = bt.ingest_incident(
                title=params.get("title", ""),
                description=params.get("description"),
                severity=params.get("severity", "P3"),
                service_name=params.get("service_name") or params.get("serviceName"),
                status=params.get("status", "NEW"),
                metadata=params.get("metadata")
            )
            return {
                "jsonrpc": "2.0",
                "result": res,
                "id": params.get("request_id")
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "message": str(e)},
                "id": params.get("request_id")
            }

    def _handle_get_runbooks(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve recent SRE runbooks."""
        try:
            service_name = params.get("service_name") or params.get("serviceName")
            limit = params.get("limit", 20)
            
            runbooks = self.memory.get_runbooks(
                service_name=service_name,
                limit=limit
            )
            return {
                "jsonrpc": "2.0",
                "result": {"success": True, "runbooks": runbooks},
                "id": params.get("request_id")
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "message": str(e)},
                "id": params.get("request_id")
            }

    def _handle_save_runbook(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new runbook playbook and trigger vector indexing."""
        try:
            from src.tools.basic_tools import BasicTools
            bt = BasicTools(require_permission=False)
            
            res = bt.save_runbook(
                title=params.get("title", ""),
                content=params.get("content", ""),
                service_name=params.get("service_name") or params.get("serviceName"),
                author=params.get("author", "SRE Assistant")
            )
            return {
                "jsonrpc": "2.0",
                "result": res,
                "id": params.get("request_id")
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "message": str(e)},
                "id": params.get("request_id")
            }

    def _handle_get_fix_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve resolution fix history."""
        try:
            incident_id = params.get("incident_id") or params.get("incidentId")
            limit = params.get("limit", 20)
            
            history = self.memory.get_fix_history(
                incident_id=incident_id,
                limit=limit
            )
            return {
                "jsonrpc": "2.0",
                "result": {"success": True, "fix_history": history},
                "id": params.get("request_id")
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "result": {"success": False, "message": str(e)},
                "id": params.get("request_id")
            }

    # ==================================================================
    # Amazon S3 Knowledge Base handlers
    # ==================================================================

    async def _handle_s3_test_connection(self) -> Dict[str, Any]:
        """Test S3 bucket connectivity."""
        import asyncio
        from src.tools.s3_tools import s3_kb
        result = await asyncio.get_event_loop().run_in_executor(None, s3_kb.test_connection)
        return {"jsonrpc": "2.0", "result": result, "id": None}

    async def _handle_s3_list_all(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all objects in the S3 knowledge base bucket."""
        import asyncio
        from src.tools.s3_tools import s3_kb
        prefix = params.get("prefix", "")
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: s3_kb._list_prefix(prefix)
        )
        return {"jsonrpc": "2.0", "result": result, "id": None}

    async def _handle_s3_upload_runbook(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a runbook to S3 and optionally index it into CockroachDB."""
        import asyncio
        from src.tools.s3_tools import s3_kb
        name = params.get("name", "")
        content = params.get("content", "")
        auto_index = params.get("auto_index", True)
        if not name or not content:
            return {"jsonrpc": "2.0", "result": {"success": False, "error": "name and content required"}, "id": None}

        upload_result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: s3_kb.upload_runbook(name, content)
        )

        index_result = None
        if auto_index and upload_result.get("success"):
            key = upload_result["s3_key"]
            index_result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: s3_kb.fetch_and_index(key)
            )

        return {
            "jsonrpc": "2.0",
            "result": {
                "upload": upload_result,
                "index": index_result,
                "message": f"Runbook '{name}' uploaded to S3 and indexed into CockroachDB." if index_result else f"Runbook '{name}' uploaded to S3."
            },
            "id": None
        }

    async def _handle_s3_fetch_runbook(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch a runbook from S3 by name."""
        import asyncio
        from src.tools.s3_tools import s3_kb
        name = params.get("name", "")
        if not name:
            return {"jsonrpc": "2.0", "result": {"success": False, "error": "name required"}, "id": None}
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: s3_kb.fetch_runbook(name)
        )
        return {"jsonrpc": "2.0", "result": result, "id": None}

    async def _handle_s3_sync_to_cockroachdb(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync all S3 objects into CockroachDB pgvector index.
        This is the main S3 → CockroachDB pipeline trigger.
        """
        import asyncio
        from src.tools.s3_tools import s3_kb
        prefix = params.get("prefix", "")
        limit = params.get("limit", 50)
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: s3_kb.sync_to_vector_store(prefix=prefix, limit=limit)
        )
        return {"jsonrpc": "2.0", "result": result, "id": None}

    async def _handle_s3_upload_incident(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload an incident log to S3 and index into CockroachDB."""
        import asyncio
        from src.tools.s3_tools import s3_kb
        incident_id = params.get("incident_id", "")
        content = params.get("content", "")
        auto_index = params.get("auto_index", True)
        if not incident_id or not content:
            return {"jsonrpc": "2.0", "result": {"success": False, "error": "incident_id and content required"}, "id": None}

        upload_result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: s3_kb.upload_incident_log(incident_id, content)
        )

        index_result = None
        if auto_index and upload_result.get("success"):
            key = upload_result["s3_key"]
            index_result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: s3_kb.fetch_and_index(key)
            )

        return {
            "jsonrpc": "2.0",
            "result": {
                "upload": upload_result,
                "index": index_result,
                "message": f"Incident '{incident_id}' uploaded to S3 and indexed into CockroachDB."
            },
            "id": None
        }


async def main_async():
    """Async main entry point."""
    # Redirect standard output to stderr to prevent random prints from breaking JSON-RPC
    original_stdout = sys.stdout
    sys.stdout = sys.stderr
    
    backend = EmbeddedBackend()
    
    # Ensure original stdout is line-buffered
    original_stdout.reconfigure(line_buffering=True)
    
    print("INFO: Embedded backend ready, waiting for JSON-RPC requests...", file=sys.stderr)
    
    loop = asyncio.get_event_loop()
    
    while True:
        # Read from stdin without blocking the asyncio event loop
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        if not line.strip():
            continue
            
        try:
            request = json.loads(line)
            # Await the processing so responses remain somewhat ordered
            response = await backend.process_request(request)
            print(json.dumps(response, default=str), file=original_stdout, flush=True)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error: Invalid JSON"
                },
                "id": None
            }
            print(json.dumps(error_response), file=original_stdout, flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": None
            }
            print(json.dumps(error_response), file=original_stdout, flush=True)


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()