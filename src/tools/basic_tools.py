"""Basic tools for the AI agent."""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
import json
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from src.processors.file_processor import FileProcessor


class BasicTools:
    """Basic system tools for the AI agent."""
    
    def __init__(self, require_permission: bool = True):
        self.require_permission = require_permission
        self.permission_cache = {}
        from src.memory.cockroach_store import SQLiteMemoryStore
        from src.memory.vector_store import VectorMemoryStore
        self.db = SQLiteMemoryStore()
        self.vector_store = VectorMemoryStore()
    
    def get_current_directory(self) -> Dict[str, Any]:
        """Get current working directory."""
        return {
            "success": True,
            "result": os.getcwd(),
            "message": "Current working directory retrieved",
        }
    
    def list_files(self, directory: Optional[str] = None) -> Dict[str, Any]:
        """List files in a directory."""
        try:
            target_dir = Path(directory) if directory else Path.cwd()
            
            if not target_dir.exists():
                return {
                    "success": False,
                    "result": None,
                    "message": f"Directory does not exist: {target_dir}",
                }
            
            if not target_dir.is_dir():
                return {
                    "success": False,
                    "result": None,
                    "message": f"Path is not a directory: {target_dir}",
                }
            
            files = []
            for item in target_dir.iterdir():
                file_info = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                }
                files.append(file_info)
            
            return {
                "success": True,
                "result": files,
                "message": f"Found {len(files)} items in {target_dir}",
            }
            
        except PermissionError:
            return {
                "success": False,
                "result": None,
                "message": f"Permission denied for directory: {directory}",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error listing files: {e}",
            }
    
    def read_file(self, file_path: str, require_permission: Optional[bool] = None) -> Dict[str, Any]:
        """Read content of a file."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {
                    "success": False,
                    "result": None,
                    "message": f"File does not exist: {file_path}",
                }
            
            if not path.is_file():
                return {
                    "success": False,
                    "result": None,
                    "message": f"Path is not a file: {file_path}",
                }
            
            # Check permission if required
            if (require_permission or self.require_permission) and not self._has_permission("read", file_path):
                return {
                    "success": False,
                    "result": None,
                    "message": f"Permission denied for reading: {file_path}",
                }
            
            # Read file using FileProcessor
            content = FileProcessor.process_file(str(path))
            
            return {
                "success": True,
                "result": content,
                "message": f"File read successfully: {file_path}",
                "metadata": {
                    "size": len(content),
                    "lines": content.count('\n') + 1,
                }
            }
            
        except PermissionError:
            return {
                "success": False,
                "result": None,
                "message": f"Permission denied for file: {file_path}",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error reading file: {e}",
            }
    
    def write_file(self, file_path: str, content: str, require_permission: Optional[bool] = None) -> Dict[str, Any]:
        """Write content to a file."""
        try:
            path = Path(file_path)
            
            # Check permission if required
            if (require_permission or self.require_permission) and not self._has_permission("write", file_path):
                return {
                    "success": False,
                    "result": None,
                    "message": f"Permission denied for writing: {file_path}",
                }
            
            # Create directory if it doesn't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "result": file_path,
                "message": f"File written successfully: {file_path}",
                "metadata": {
                    "size": len(content),
                    "lines": content.count('\n') + 1,
                }
            }
            
        except PermissionError:
            return {
                "success": False,
                "result": None,
                "message": f"Permission denied for file: {file_path}",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error writing file: {e}",
            }
    
    def execute_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a shell command in the shared stateful terminal."""
        try:
            # Security check: disallow dangerous commands
            dangerous_patterns = ["rm -rf", "format", "dd if=", "mkfs", ":(){:|:&};:"]
            for pattern in dangerous_patterns:
                if pattern in command.lower():
                    return {
                        "success": False,
                        "result": None,
                        "message": f"Command contains potentially dangerous pattern: {pattern}",
                    }
            
            # Use the stateful terminal manager
            from src.tools.terminal_manager import terminal_manager
            
            result = terminal_manager.execute_agent_command(
                command=command,
                timeout=timeout
            )
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error executing command: {e}",
            }
    
    def calculate(self, expression: str) -> Dict[str, Any]:
        """Calculate a mathematical expression."""
        try:
            # Security: only allow safe operations
            allowed_chars = set("0123456789+-*/.() ")
            if not all(c in allowed_chars for c in expression):
                return {
                    "success": False,
                    "result": None,
                    "message": "Expression contains invalid characters",
                }
            
            # Evaluate safely
            result = eval(expression, {"__builtins__": {}}, {})
            
            return {
                "success": True,
                "result": result,
                "message": f"Calculation successful: {expression} = {result}",
            }
            
        except ZeroDivisionError:
            return {
                "success": False,
                "result": None,
                "message": "Division by zero",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error calculating expression: {e}",
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        import platform
        
        return {
            "success": True,
            "result": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "current_directory": os.getcwd(),
            },
            "message": "System information retrieved",
        }
    
    def get_current_datetime(self) -> Dict[str, Any]:
        """Get the current date and time."""
        from datetime import datetime
        import platform
        import subprocess
        
        is_wsl = 'linux' in platform.system().lower() and 'microsoft' in platform.release().lower()
        if is_wsl:
            try:
                # Use powershell to get the exact host Windows time since WSL clocks often drift or are stuck in UTC
                result = subprocess.run(["powershell.exe", "-Command", "Get-Date -Format 'yyyy-MM-dd HH:mm:ss dddd'"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and result.stdout.strip():
                    date_str = result.stdout.strip()
                    return {
                        "success": True,
                        "result": {
                            "datetime": date_str,
                            "note": "Time retrieved from Windows Host"
                        },
                        "message": "Current datetime retrieved",
                    }
            except Exception:
                pass
                
        now = datetime.now()
        return {
            "success": True,
            "result": {
                "datetime": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "weekday": now.strftime("%A"),
            },
            "message": "Current datetime retrieved",
        }

    def web_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search the web for a query."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return {
                    "success": True,
                    "result": results,
                    "message": f"Found {len(results)} results for '{query}'",
                }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error performing web search: {e}",
            }
            
    def fetch_webpage(self, url: str) -> Dict[str, Any]:
        """Fetch and extract text from a webpage."""
        try:
            response = httpx.get(url, timeout=15.0, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            text = soup.get_text(separator="\n", strip=True)
            # Truncate if too long (e.g., 20000 chars roughly 5000 tokens)
            if len(text) > 20000:
                text = text[:20000] + "\n...[truncated]"
                
            return {
                "success": True,
                "result": text,
                "message": f"Webpage fetched and parsed: {url}",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error fetching webpage: {e}",
            }
    
    def ask_expert_model(self, role: str = "", prompt: str = "", file_paths: Optional[list] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Delegate a task to a specialized role sub-agent."""
        try:
            from src.utils.config import config
            import httpx
            import base64
            from pathlib import Path
            from src.processors.file_processor import FileProcessor
            from src.models.provider_router import ProviderRouter
            from src.memory.redis_store import redis_store
            from src.utils.prompt_loader import PromptLoader

            target_role = (role or model_name or "reasoning").strip().lower()
            
            # Map friendly aliases to standardized role keys
            role_key = "reasoning"
            if "code" in target_role or "coding" in target_role:
                role_key = "coding"
            elif "multi" in target_role or "vision" in target_role or "gemini" in target_role or "media" in target_role:
                role_key = "multimodal"
            elif "synth" in target_role:
                role_key = "synthesizer"
            elif "sum" in target_role or "mem" in target_role:
                role_key = "summary"
            elif "stt" in target_role or "audio" in target_role:
                role_key = "stt"
            elif "tts" in target_role or "voice" in target_role:
                role_key = "tts"
            elif "logic" in target_role or "reason" in target_role or "arch" in target_role:
                role_key = "reasoning"

            pr = ProviderRouter()
            assigned_model = ""
            if redis_store.is_connected():
                assigned_model = redis_store.get_role_model(role_key)
            if not assigned_model:
                try:
                    db_roles = pr.memory_store.get_role_assignments()
                    if role_key in db_roles:
                        item = db_roles[role_key]
                        if isinstance(item, dict):
                            assigned_model = f"{item.get('provider', 'openrouter')}:{item.get('model_id', '')}"
                        elif isinstance(item, str):
                            assigned_model = item
                except Exception:
                    pass

            target_model = assigned_model.strip() if assigned_model and assigned_model.strip() else "openrouter:qwen/qwen3.5-flash-02-23"

            # Prepare context from files if provided
            content_list: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
            
            if file_paths:
                import mimetypes
                for path_str in file_paths:
                    try:
                        p = Path(path_str)
                        if p.exists() and p.is_file():
                            mime_type, _ = mimetypes.guess_type(str(p))
                            if mime_type and (mime_type.startswith('image/') or mime_type.startswith('video/') or mime_type.startswith('audio/')):
                                if p.stat().st_size < 50 * 1024 * 1024:
                                    with open(p, "rb") as media_file:
                                        encoded_string = base64.b64encode(media_file.read()).decode('utf-8')
                                        content_list.append({
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:{mime_type};base64,{encoded_string}"
                                            }
                                        })
                            elif p.stat().st_size < 1024 * 1024:
                                try:
                                    content = FileProcessor.process_file(str(p))
                                    content_list[0]["text"] += f"\n\n--- Contents of {p.name} ---\n{content}\n"
                                except ValueError as e:
                                    content_list[0]["text"] += f"\n\n[SYSTEM NOTE: Could not process {path_str}: {str(e)}]\n"
                    except Exception as e:
                        content_list[0]["text"] += f"\n\n(Error reading {path_str}: {str(e)})\n"

            # Load role system prompt from cached prompt files
            prompt_name = f"{role_key}_prompt"
            system_instruction = PromptLoader.get_prompt(prompt_name, f"You are the {role_key.upper()} sub-agent. Provide clear, direct, and concise output.")
            
            # Inject tools system directive:
            system_instruction += (
                "\n\n[SYSTEM DIRECTIVE: You have direct access to system tools to find/search/read/write files, open directories, "
                "run terminal commands, or search the web. Use these tools proactively as tool calls to gather workspace "
                "context, inspect code, or verify facts. Use tools whenever necessary to perform your tasks.]"
            )

            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": content_list if len(content_list) > 1 else content_list[0]["text"]}
            ]

            print(f"[SUPERVISOR] Delegating task to role [{role_key.upper()}] using model ({target_model})...")

            import concurrent.futures
            import asyncio

            from src.tools.basic_tools import ToolManager
            sub_tool_manager = ToolManager()
            sub_tools_schema = sub_tool_manager.get_openai_tools_schema()

            def _run_async_generate_loop():
                loop_messages = list(messages)
                loop_tokens = 0
                max_turns = 5
                turn_num = 0
                final_content = ""
                resolved_model = target_model

                while turn_num < max_turns:
                    try:
                        res_item = asyncio.run(pr.generate(
                            messages=loop_messages,
                            model_id=resolved_model,
                            temperature=0.2,
                            max_tokens=4000,
                            tools=sub_tools_schema if sub_tools_schema else None
                        ))
                    except Exception as e:
                        # Fallback
                        resolved_model = "openrouter:qwen/qwen3.5-flash-02-23"
                        res_item = asyncio.run(pr.generate(
                            messages=loop_messages,
                            model_id=resolved_model,
                            temperature=0.2,
                            max_tokens=4000,
                            tools=sub_tools_schema if sub_tools_schema else None
                        ))

                    loop_tokens += res_item.get("tokens_used", 0)
                    t_calls = res_item.get("tool_calls")
                    
                    if not t_calls:
                        final_content = res_item.get("content", "").strip()
                        break

                    loop_messages.append({
                        "role": "assistant",
                        "content": res_item.get("content") or "",
                        "tool_calls": t_calls
                    })

                    for tc in t_calls:
                        tc_id = tc.get("id")
                        tc_name = tc.get("function", {}).get("name")
                        
                        # Prevent infinite sub-agent recursion loops
                        if tc_name == "ask_expert_model":
                            res_payload = {"success": False, "message": "Recursive expert model calls are disabled."}
                        else:
                            try:
                                tc_args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                            except Exception:
                                tc_args = {}
                            res_payload = sub_tool_manager.execute_tool(tc_name, tc_args)

                        loop_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": tc_name,
                            "content": json.dumps(res_payload)
                        })

                    turn_num += 1

                return {"content": final_content, "tokens_used": loop_tokens, "model": resolved_model}

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(_run_async_generate_loop)
                    res_outcome = future.result()
            else:
                res_outcome = _run_async_generate_loop()

            target_model = res_outcome["model"]
            if res_outcome.get("content"):
                return {
                    "success": True,
                    "result": res_outcome["content"],
                    "role": role_key,
                    "model": target_model,
                    "message": f"Role [{role_key.upper()}] ({target_model}) responded successfully"
                }

            return {
                "success": False,
                "result": "",
                "role": role_key,
                "model": target_model,
                "message": f"No response generated by role {role_key}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "role": locals().get("role_key", "sub_agent"),
                "model": locals().get("target_model", "Unknown"),
                "message": f"Error asking expert model: {str(e)}"
            }

    def ingest_incident(
        self,
        title: str,
        description: Optional[str] = None,
        severity: str = "P3",
        service_name: Optional[str] = None,
        status: str = "NEW",
        root_cause: Optional[str] = None,
        metadata: Optional[str] = None
    ) -> Dict[str, Any]:
        """Save a new SRE incident and index details in vector database for RAG search."""
        try:
            parsed_metadata = None
            if metadata:
                try:
                    parsed_metadata = json.loads(metadata) if isinstance(metadata, str) else metadata
                except Exception:
                    parsed_metadata = {"raw_metadata": metadata}

            # Save to CockroachDB SQL
            inc_id = self.db.save_incident(
                title=title,
                description=description or "",
                severity=severity,
                service_name=service_name or "",
                metadata=parsed_metadata
            )
            
            # Embed and index details in vector store for RAG retrieval
            doc_content = f"Incident [{inc_id}] (Severity: {severity}, Service: {service_name or 'unknown'}, Status: {status})\nTitle: {title}\nDescription: {description or ''}\nMetadata: {metadata or ''}"
            self.vector_store.add_document(
                file_path=f"incident:{inc_id}",
                content=doc_content
            )
            
            return {
                "success": True,
                "result": {"incident_id": inc_id},
                "message": f"Successfully ingested incident {inc_id} and indexed in pgvector."
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Failed to ingest incident: {e}"}

    def save_runbook(
        self,
        title: str,
        content: str,
        service_name: Optional[str] = None,
        author: Optional[str] = "SRE Assistant"
    ) -> Dict[str, Any]:
        """Save a step-by-step diagnostic runbook / playbook and index details in vector database for RAG."""
        try:
            # Save to CockroachDB SQL
            rb_id = self.db.save_runbook(
                title=title,
                content=content,
                service_name=service_name or "",
                author=author or ""
            )
            
            # Embed and index content in vector store for RAG
            doc_content = f"Runbook Playbook [{rb_id}] for service '{service_name or 'unknown'}':\nTitle: {title}\nInstructions:\n{content}"
            self.vector_store.add_document(
                file_path=f"runbook:{rb_id}",
                content=doc_content
            )
            
            return {
                "success": True,
                "result": {"runbook_id": rb_id},
                "message": f"Successfully stored runbook {rb_id} and indexed in pgvector."
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Failed to save runbook: {e}"}

    def record_fix_action(
        self,
        incident_id: str,
        action_taken: str,
        success: int = 1,
        engineer_notes: Optional[str] = None,
        runbook_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a resolution or fix action taken for an incident, update status, and index fix history for RAG."""
        try:
            # Save to CockroachDB SQL
            fix_id = self.db.save_fix_history(
                incident_id=incident_id,
                action_taken=action_taken,
                engineer_notes=engineer_notes or "",
                runbook_id=runbook_id,
                success=(success == 1)
            )
            
            # Auto-resolve incident if successful
            if success == 1:
                self.db.resolve_incident(
                    incident_id=incident_id,
                    root_cause=engineer_notes or "Automatic resolution."
                )
                
            # Embed and index fix inside vector database so future RAG lookups can locate past resolutions
            doc_content = f"Resolution Action for Incident [{incident_id}] (Success: {success == 1}):\nAction Taken: {action_taken}\nEngineer Notes: {engineer_notes or ''}"
            self.vector_store.add_document(
                file_path=f"fix:{fix_id}",
                content=doc_content
            )
            
            return {
                "success": True,
                "result": {"fix_id": fix_id},
                "message": f"Recorded fix action {fix_id}. Incident {incident_id} resolved: {success == 1}"
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Failed to record fix action: {e}"}

    def get_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        service_name: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Retrieve recent SRE incidents from CockroachDB."""
        try:
            incidents = self.db.get_incidents(status=status, severity=severity, service_name=service_name, limit=limit)
            return {
                "success": True,
                "result": incidents,
                "message": f"Retrieved {len(incidents)} incidents."
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Failed to query incidents: {e}"}

    def get_runbooks(
        self,
        service_name: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Retrieve diagnostic runbooks from CockroachDB."""
        try:
            runbooks = self.db.get_runbooks(service_name=service_name, limit=limit)
            return {
                "success": True,
                "result": runbooks,
                "message": f"Retrieved {len(runbooks)} runbooks."
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Failed to query runbooks: {e}"}

    def get_fix_history(
        self,
        incident_id: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Retrieve fix actions history from CockroachDB."""
        try:
            history = self.db.get_fix_history(incident_id=incident_id, limit=limit)
            return {
                "success": True,
                "result": history,
                "message": f"Retrieved {len(history)} fix records."
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Failed to query fix history: {e}"}

    def _has_permission(self, action: str, resource: str) -> bool:
        """Check if permission is granted for an action on a resource."""
        permission_key = f"{action}:{resource}"
        
        if permission_key in self.permission_cache:
            return self.permission_cache[permission_key]
        
        # In a real implementation, this would show a user prompt
        # For now, we'll simulate based on file type
        from src.utils.config import config
        
        path = Path(resource)
        if path.suffix.lower() in [".py", ".txt", ".md", ".json"]:
            # Allow read/write for text files
            self.permission_cache[permission_key] = True
            return True
        elif path.suffix.lower() in [".exe", ".dll", ".sys"]:
            # Deny for system files
            self.permission_cache[permission_key] = False
            return False
        else:
            # Ask user (simulated)
            print(f"[SECURITY] Permission requested: {action} on {resource}")
            print("   Type 'allow' to grant or 'deny' to reject")
            # Simulate user allowing
            self.permission_cache[permission_key] = True
            return True
    
    def get_available_tools(self) -> Dict[str, Any]:
        """Get list of available tools with descriptions."""
        from src.controller.model_router import CapabilityMatcher, _resolve_role

        # Build expert model descriptions dynamically from assigned roles
        expert_desc = (
            "Delegate a specialized task to an expert AI model. "
            "Use this when you cannot fulfill a request with your current capabilities.\n\n"
        )
        roles = [
            ("coding",      "coding"),
            ("reasoning",   "reasoning"),
            ("multimodal",  "multimodal"),
            ("synthesizer", "synthesizer"),
        ]
        for role, label in roles:
            model_id = _resolve_role(role) or ""
            caps = CapabilityMatcher.get(model_id) if model_id else {}
            expert_desc += f"- '{label}':\n"
            if caps.get("strong_coding"):
                expert_desc += "  Strengths: coding, debugging, refactoring, algorithms\n"
                expert_desc += "  Best for: code generation, backend systems, large codebases\n\n"
            elif caps.get("strong_reasoning"):
                expert_desc += "  Strengths: deep reasoning, analysis, planning, maths\n"
                expert_desc += "  Best for: architecture design, research, multi-step reasoning\n\n"
            elif caps.get("vision"):
                expert_desc += "  Strengths: OCR, image understanding, video analysis, multimodal extraction\n"
                expert_desc += "  Best for: image/document analysis, screenshots, charts\n\n"
            else:
                expert_desc += f"  Strengths: general-purpose, tool use\n"
                expert_desc += f"  Best for: aggregation, synthesis, general tasks\n\n"

        expert_desc += (
            "IMPORTANT: deepseek models are capable of logic/reasoning too. "
            "Do NOT force them to write code unless code is actually needed."
        )

        tools = {
            "get_current_directory": {
                "description": "Get current working directory",
                "parameters": {},
                "returns": "Current directory path",
            },
            "list_files": {
                "description": "List files in a directory",
                "parameters": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path (optional, defaults to current)",
                        "required": False,
                    }
                },
                "returns": "List of files and directories",
            },
            "read_file": {
                "description": "Read content of a file",
                "parameters": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to file to read",
                        "required": True,
                    }
                },
                "returns": "File content",
            },
            "write_file": {
                "description": "Write content to a file",
                "parameters": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to file to write",
                        "required": True,
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                        "required": True,
                    }
                },
                "returns": "Path to written file",
            },
            "execute_command": {
                "description": "Execute a shell command",
                "parameters": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute",
                        "required": True,
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 30)",
                        "required": False,
                    }
                },
                "returns": "Command output",
            },
            "calculate": {
                "description": "Calculate a mathematical expression",
                "parameters": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression",
                        "required": True,
                    }
                },
                "returns": "Calculation result",
            },
            "get_system_info": {
                "description": "Get system information",
                "parameters": {},
                "returns": "System information dictionary",
            },
            "web_search": {
                "description": "Search the web for a query to find recent or relevant information",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                        "required": True,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return (default: 5)",
                        "required": False,
                    }
                },
                "returns": "List of search result dictionaries with title, href, and body",
            },
            "fetch_webpage": {
                "description": "Fetch and extract text content from a webpage URL",
                "parameters": {
                    "url": {
                        "type": "string",
                        "description": "URL of the webpage to fetch",
                        "required": True,
                    }
                },
                "returns": "Extracted text content of the webpage",
            },
            "ask_expert_model": {
                "description": "Delegate a sub-task or analysis to a specialized role sub-agent.",
                "parameters": {
                    "role": {
                        "type": "string",
                        "description": "Specialized sub-agent role ('coding', 'reasoning', 'multimodal', 'synthesizer', 'summary', 'stt', 'tts')",
                        "required": True,
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Detailed instructions for the expert sub-agent",
                        "required": True,
                    },
                    "file_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths the sub-agent should analyze",
                        "required": False,
                    }
                },
                "returns": "Response from the expert sub-agent",
            },
            "open_in_explorer": {
                "description": "Open a directory or highlight a specific file in Windows File Explorer.",
                "parameters": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute file/directory path to open",
                        "required": True
                    }
                },
                "returns": "Confirmation message"
            },
            "get_file_tree": {
                "description": "Generate a recursive directory tree of the workspace to inspect files structure.",
                "parameters": {
                    "directory": {
                        "type": "string",
                        "description": "Folder path to generate the tree for (optional, defaults to current)",
                        "required": False
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum directory nesting depth (optional, default: 3)",
                        "required": False
                    }
                },
                "returns": "Text representation of file structure"
            },
            "find_files": {
                "description": "Find files recursively matching a wildcard/glob pattern.",
                "parameters": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match e.g. '*.py' or 'index.*'",
                        "required": True
                    },
                    "directory": {
                        "type": "string",
                        "description": "Folder path to search within (optional, defaults to current)",
                        "required": False
                    }
                },
                "returns": "List of matching file paths"
            },
            "grep_search": {
                "description": "Search recursively for a query text keyword inside all workspace files.",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "Text query keyword to find in files",
                        "required": True
                    },
                    "directory": {
                        "type": "string",
                        "description": "Folder path to search within (optional, defaults to current)",
                        "required": False
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter target files e.g. '*.ts'",
                        "required": False
                    }
                },
                "returns": "List of line match dicts containing filename, line number, and content"
            },
            "ingest_incident": {
                "description": "Ingest and register a new SRE production incident in CockroachDB and index it in the pgvector database for semantic RAG search.",
                "parameters": {
                    "title": {
                        "type": "string",
                        "description": "Short summary of the incident/alert e.g., 'auth-service: HTTP 504 gateway timeout'",
                        "required": True
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the incident symptoms or logs",
                        "required": False
                    },
                    "severity": {
                        "type": "string",
                        "description": "Severity level: P1 (Critical), P2 (Major), P3 (Medium), P4 (Minor)",
                        "required": False
                    },
                    "service_name": {
                        "type": "string",
                        "description": "Affected microservice or component name",
                        "required": False
                    },
                    "status": {
                        "type": "string",
                        "description": "Current status: NEW, INVESTIGATING, MITIGATED, RESOLVED",
                        "required": False
                    },
                    "root_cause": {
                        "type": "string",
                        "description": "Identified root cause (optional)",
                        "required": False
                    },
                    "metadata": {
                        "type": "string",
                        "description": "JSON string containing diagnostic alert data or log snippets",
                        "required": False
                    }
                },
                "returns": "Ingested incident ID"
            },
            "save_runbook": {
                "description": "Store a step-by-step diagnostic or resolution runbook playbook and index it in the pgvector database for semantic RAG search.",
                "parameters": {
                    "title": {
                        "type": "string",
                        "description": "Title of the runbook playbook e.g., 'DB Connection Leaks mitigation'",
                        "required": True
                    },
                    "content": {
                        "type": "string",
                        "description": "Detailed step-by-step instructions or remediation scripts",
                        "required": True
                    },
                    "service_name": {
                        "type": "string",
                        "description": "Associated microservice or component name",
                        "required": False
                    },
                    "author": {
                        "type": "string",
                        "description": "Runbook author name",
                        "required": False
                    }
                },
                "returns": "Stored runbook ID"
            },
            "record_fix_action": {
                "description": "Record a fix or resolution action taken for an incident, update status, and index it in the pgvector database for future retrieval.",
                "parameters": {
                    "incident_id": {
                        "type": "string",
                        "description": "The ID of the incident being resolved",
                        "required": True
                    },
                    "action_taken": {
                        "type": "string",
                        "description": "Detailed summary of the fix action taken (e.g. commands run, service restarted)",
                        "required": True
                    },
                    "success": {
                        "type": "integer",
                        "description": "1 = resolved/successful, 0 = failed/unsuccessful",
                        "required": False
                    },
                    "engineer_notes": {
                        "type": "string",
                        "description": "Diagnostic findings or post-mortem notes",
                        "required": False
                    },
                    "runbook_id": {
                        "type": "string",
                        "description": "The ID of the runbook playbook that was followed (optional)",
                        "required": False
                    }
                },
                "returns": "Recorded fix ID"
            },
            "get_incidents": {
                "description": "Retrieve recent SRE incidents from CockroachDB.",
                "parameters": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: NEW, INVESTIGATING, MITIGATED, RESOLVED",
                        "required": False
                    },
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity e.g. P1",
                        "required": False
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of incidents to return (default: 10)",
                        "required": False
                    }
                },
                "returns": "List of incidents"
            },
            "get_runbooks": {
                "description": "Retrieve SRE runbook playbooks from CockroachDB.",
                "parameters": {
                    "service_name": {
                        "type": "string",
                        "description": "Filter by associated microservice name",
                        "required": False
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of runbooks to return (default: 10)",
                        "required": False
                    }
                },
                "returns": "List of runbook playbooks"
            },
            "get_fix_history": {
                "description": "Retrieve fix actions history from CockroachDB.",
                "parameters": {
                    "incident_id": {
                        "type": "string",
                        "description": "Filter by specific incident ID",
                        "required": False
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of fix records to return (default: 10)",
                        "required": False
                    }
                },
                "returns": "List of fix records"
            }
        }

        # Fetch tools dynamically from active MCP servers
        try:
            from src.tools.mcp_manager import mcp_manager
            for server in mcp_manager.get_all_servers():
                if server["status"] == "Active":
                    srv_name = server["name"]
                    for tool in server["tools"]:
                        t_name = tool["name"]
                        namespaced_name = f"mcp_{srv_name}_{t_name}"
                        
                        # Translate MCP properties/parameters schema to match ToolManager format
                        input_schema = tool.get("inputSchema", {})
                        properties = input_schema.get("properties", {})
                        required_list = input_schema.get("required", [])
                        
                        parameters_dict = {}
                        for prop_name, prop_data in properties.items():
                            parameters_dict[prop_name] = {
                                "type": prop_data.get("type", "string"),
                                "description": prop_data.get("description", ""),
                                "required": prop_name in required_list
                            }
                            # Check for arrays to support strict Gemini validation rules (missing items schema fix)
                            if prop_data.get("type") == "array" and "items" not in prop_data:
                                parameters_dict[prop_name]["items"] = {"type": "string"}
                            elif "items" in prop_data:
                                parameters_dict[prop_name]["items"] = prop_data["items"]
                        
                        tools[namespaced_name] = {
                            "description": f"[MCP: {srv_name}] {tool.get('description', '')}",
                            "parameters": parameters_dict,
                            "returns": "MCP server response payload"
                        }
        except Exception as e:
            logger.error(f"Error reading dynamic MCP tools in BasicTools: {e}")
        
        return {
            "success": True,
            "result": tools,
            "message": f"Available tools: {len(tools)}",
        }


# Tool manager for coordinating tool execution
class ToolManager:
    """Manages tool execution and coordination."""
    
    def __init__(self):
        # Disable permission prompts for the backend daemon to prevent hanging
        self.basic_tools = BasicTools(require_permission=False)
        from src.tools.file_explorer_tool import FileExplorerTool
        self.file_explorer = FileExplorerTool()
        self.tool_registry = self._register_tools()
    
    def _register_tools(self) -> Dict[str, Any]:
        """Register all available tools."""
        return {
            "get_current_directory": self.basic_tools.get_current_directory,
            "list_files": self.basic_tools.list_files,
            "read_file": self.basic_tools.read_file,
            "write_file": self.basic_tools.write_file,
            "execute_command": self.basic_tools.execute_command,
            "calculate": self.basic_tools.calculate,
            "get_system_info": self.basic_tools.get_system_info,
            "web_search": self.basic_tools.web_search,
            "fetch_webpage": self.basic_tools.fetch_webpage,
            "ask_expert_model": self.basic_tools.ask_expert_model,
            "open_in_explorer": self.file_explorer.open_in_explorer,
            "get_file_tree": self.file_explorer.get_file_tree,
            "find_files": self.file_explorer.find_files,
            "grep_search": self.file_explorer.grep_search,
            
            # Custom SRE Tools
            "ingest_incident": self.basic_tools.ingest_incident,
            "save_runbook": self.basic_tools.save_runbook,
            "record_fix_action": self.basic_tools.record_fix_action,
            "get_incidents": self.basic_tools.get_incidents,
            "get_runbooks": self.basic_tools.get_runbooks,
            "get_fix_history": self.basic_tools.get_fix_history,
        }
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with parameters (intercepts namespaced MCP tools)."""
        if tool_name.startswith("mcp_"):
            try:
                # Expected format: mcp_[server_name]_[tool_name]
                parts = tool_name.split("_", 2)
                if len(parts) >= 3:
                    server_name = parts[1]
                    inner_tool_name = parts[2]
                    
                    from src.tools.mcp_manager import mcp_manager
                    raw_res = mcp_manager.execute_mcp_tool(server_name, inner_tool_name, parameters)
                    
                    # Normalize standard MCP response to match ToolManager's expected output format
                    if isinstance(raw_res, dict) and "content" in raw_res:
                        text_parts = []
                        for item in raw_res.get("content", []):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                        
                        message_str = "\n".join(text_parts)
                        result = {
                            "success": True,
                            "result": raw_res,
                            "message": message_str or "Tool executed successfully",
                            "tool_name": tool_name,
                            "parameters": parameters,
                        }
                    elif isinstance(raw_res, dict) and raw_res.get("success") is False:
                        result = raw_res
                        result["tool_name"] = tool_name
                        result["parameters"] = parameters
                    else:
                        result = {
                            "success": True,
                            "result": raw_res,
                            "tool_name": tool_name,
                            "parameters": parameters,
                        }
                    return result
                else:
                    return {
                        "success": False,
                        "result": None,
                        "message": f"Malformed MCP tool name format: {tool_name}",
                        "tool_name": tool_name,
                        "parameters": parameters,
                    }
            except Exception as e:
                return {
                    "success": False,
                    "result": None,
                    "message": f"Failed executing MCP tool: {str(e)}",
                    "tool_name": tool_name,
                    "parameters": parameters,
                }

        if tool_name not in self.tool_registry:
            return {
                "success": False,
                "result": None,
                "message": f"Tool not found: {tool_name}",
                "tool_name": tool_name,
            }
            
        # Convert WSL paths if needed before execution
        import platform
        import re
        if 'linux' in platform.system().lower() and 'microsoft' in platform.release().lower():
            def convert_p(p):
                m = re.match(r'^([a-zA-Z]):[\\/](.*)$', p)
                if m:
                    drive = m.group(1).lower()
                    rest = m.group(2).replace('\\', '/')
                    return f"/mnt/{drive}/{rest}"
                return p
                
            for key in ['file_path', 'directory']:
                if key in parameters and isinstance(parameters[key], str):
                    parameters[key] = convert_p(parameters[key])
            
            if 'file_paths' in parameters and isinstance(parameters['file_paths'], list):
                parameters['file_paths'] = [convert_p(p) for p in parameters['file_paths']]
        
        try:
            tool_func = self.tool_registry[tool_name]
            result = tool_func(**parameters)
            result["tool_name"] = tool_name
            result["parameters"] = parameters
            return result
            
        except TypeError as e:
            return {
                "success": False,
                "result": None,
                "message": f"Invalid parameters for {tool_name}: {e}",
                "tool_name": tool_name,
                "parameters": parameters,
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error executing {tool_name}: {e}",
                "tool_name": tool_name,
                "parameters": parameters,
            }
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific tool."""
        tools_info = self.basic_tools.get_available_tools()
        if tools_info["success"]:
            return tools_info["result"].get(tool_name)
        return None
    
    def list_tools(self) -> Dict[str, Any]:
        """List all available tools."""
        return self.basic_tools.get_available_tools()

    def get_openai_tools_schema(self) -> list:
        """Get tools in OpenAI's JSON schema format."""
        schema_list = []
        tools_info = self.basic_tools.get_available_tools()
        if not tools_info["success"]:
            return []
            
        for tool_name, tool_def in tools_info["result"].items():
            parameters = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            for param_name, param_def in tool_def.get("parameters", {}).items():
                param_prop = {
                    "type": param_def.get("type", "string"),
                    "description": param_def.get("description", "")
                }
                if param_def.get("items"):
                    param_prop["items"] = param_def["items"]
                elif param_def.get("type") == "array":
                    param_prop["items"] = {"type": "string"}

                parameters["properties"][param_name] = param_prop
                if param_def.get("required", False):
                    parameters["required"].append(param_name)
                    
            schema_list.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_def.get("description", ""),
                    "parameters": parameters
                }
            })
            
        return schema_list