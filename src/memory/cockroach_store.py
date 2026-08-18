"""
CockroachDB memory store — drop-in replacement for SQLiteMemoryStore.

Key differences from SQLite:
  - Uses psycopg2 (PostgreSQL-wire-compatible) instead of sqlite3
  - Placeholder style: %s  (not ?)
  - ON CONFLICT … DO UPDATE  (UPSERT via standard SQL)
  - Date arithmetic uses INTERVAL syntax  (not datetime('now', …))
  - RealDictCursor gives dict-like rows (row["col"] works identically)
  - autocommit=True used for simplicity; no explicit commit() needed
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

# Redis store is kept for Pub/Sub event broadcasting (unchanged)
from src.memory.redis_store import redis_store


# ---------------------------------------------------------------------------
# Helper: build connection
# ---------------------------------------------------------------------------

def _get_conn() -> psycopg2.extensions.connection:
    """Open a new psycopg2 connection using COCKROACH_DATABASE_URL."""
    url = os.environ.get("COCKROACH_DATABASE_URL")
    if not url:
        try:
            from dotenv import load_dotenv
            # Check current working directory and project root
            root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
            if os.path.exists(root_env):
                load_dotenv(root_env)
            else:
                load_dotenv()
            url = os.environ.get("COCKROACH_DATABASE_URL")
        except Exception:
            pass
    if not url:
        raise RuntimeError(
            "COCKROACH_DATABASE_URL is not set. "
            "Add it to your .env file and restart."
        )
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    return conn


# ---------------------------------------------------------------------------
# Main store class
# ---------------------------------------------------------------------------

class CockroachMemoryStore:
    """CockroachDB-backed memory store with the same public API as SQLiteMemoryStore."""

    def __init__(self):
        self._conn: Optional[psycopg2.extensions.connection] = None
        self._ensure_connected()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _ensure_connected(self):
        """Lazily open (or re-open after disconnect) the DB connection."""
        try:
            if self._conn is None or self._conn.closed:
                self._conn = _get_conn()
        except Exception as e:
            print(f"[WARNING] CockroachDB connection error: {e}")
            raise

    @property
    def connection(self) -> psycopg2.extensions.connection:
        """Expose raw psycopg2 connection for compatibility."""
        self._ensure_connected()
        return self._conn

    def _cursor(self) -> psycopg2.extras.RealDictCursor:
        self._ensure_connected()
        return self._conn.cursor()

    def _execute(self, sql: str, params: tuple = ()) -> psycopg2.extras.RealDictCursor:
        """Execute a write statement, auto-reconnecting once on failure."""
        try:
            cur = self._cursor()
            cur.execute(sql, params)
            return cur
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            # Connection dropped — try once more
            self._conn = _get_conn()
            cur = self._cursor()
            cur.execute(sql, params)
            return cur

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def save_conversation(
        self,
        session_id: str,
        model_id: str,
        user_message: str,
        assistant_message: str,
        tokens_used: int = 0,
        cost: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save a conversation turn."""
        conversation_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO conversations
              (id, session_id, model_id, user_message, assistant_message,
               tokens_used, cost, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                conversation_id,
                session_id,
                model_id,
                user_message,
                assistant_message,
                tokens_used,
                cost,
                json.dumps(metadata or {}),
            ),
        )
        return conversation_id

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session (newest first)."""
        cur = self._cursor()
        cur.execute(
            """
            SELECT id, model_id, user_message, assistant_message,
                   tokens_used, cost, metadata, created_at
            FROM conversations
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (session_id, limit, offset),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "model_id": r["model_id"],
                "user_message": r["user_message"],
                "assistant_message": r["assistant_message"],
                "tokens_used": r["tokens_used"],
                "cost": r["cost"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_recent_conversations(
        self,
        days: int = 7,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent conversations across all sessions."""
        cur = self._cursor()
        cur.execute(
            """
            SELECT session_id, model_id, user_message, assistant_message,
                   tokens_used, cost, created_at
            FROM conversations
            WHERE created_at >= NOW() - INTERVAL '%s days'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (days, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "session_id": r["session_id"],
                "model_id": r["model_id"],
                "user_message": (
                    r["user_message"][:100] + "..."
                    if len(r["user_message"]) > 100
                    else r["user_message"]
                ),
                "assistant_message": (
                    r["assistant_message"][:100] + "..."
                    if len(r["assistant_message"]) > 100
                    else r["assistant_message"]
                ),
                "tokens_used": r["tokens_used"],
                "cost": r["cost"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Tool executions
    # ------------------------------------------------------------------

    def save_tool_execution(
        self,
        conversation_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        result: str,
        success: bool = True,
        execution_time: float = 0.0,
    ) -> str:
        """Save a tool execution record."""
        tool_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO tool_executions
              (id, conversation_id, tool_name, parameters, result, success, execution_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tool_id,
                conversation_id,
                tool_name,
                json.dumps(parameters),
                result,
                1 if success else 0,
                execution_time,
            ),
        )
        return tool_id

    def get_tool_executions(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get tool executions for a conversation."""
        cur = self._cursor()
        cur.execute(
            """
            SELECT id, tool_name, parameters, result, success, execution_time, created_at
            FROM tool_executions
            WHERE conversation_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (conversation_id, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "tool_name": r["tool_name"],
                "parameters": json.loads(r["parameters"]) if r["parameters"] else {},
                "result": r["result"],
                "success": bool(r["success"]),
                "execution_time": r["execution_time"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Documents (RAG)
    # ------------------------------------------------------------------

    def save_document(
        self,
        content: str,
        source: str,
        embedding_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save a document chunk for RAG."""
        document_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO documents (id, content, source, embedding_id, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (document_id, content, source, embedding_id, json.dumps(metadata or {})),
        )
        return document_id

    def search_documents(
        self,
        query: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Search documents by content (ILIKE) or source."""
        cur = self._cursor()
        if query:
            cur.execute(
                """
                SELECT id, content, source, embedding_id, metadata, created_at
                FROM documents
                WHERE content ILIKE %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (f"%{query}%", limit, offset),
            )
        elif source:
            cur.execute(
                """
                SELECT id, content, source, embedding_id, metadata, created_at
                FROM documents
                WHERE source = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (source, limit, offset),
            )
        else:
            cur.execute(
                """
                SELECT id, content, source, embedding_id, metadata, created_at
                FROM documents
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "content": r["content"],
                "source": r["source"],
                "embedding_id": r["embedding_id"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Cost tracking
    # ------------------------------------------------------------------

    def track_cost(
        self,
        model_id: str,
        operation_type: str,
        tokens_input: int,
        tokens_output: int,
        cost: float,
        latency: float,
    ) -> str:
        """Track a cost entry."""
        cost_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO cost_tracking
              (id, model_id, operation_type, tokens_input, tokens_output, cost, latency)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (cost_id, model_id, operation_type, tokens_input, tokens_output, cost, latency),
        )
        return cost_id

    def get_cost_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get cost summary optionally filtered by date range or model."""
        conditions: List[str] = []
        params: List[Any] = []

        if start_date:
            conditions.append("created_at >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= %s")
            params.append(end_date)
        if model_id:
            conditions.append("model_id = %s")
            params.append(model_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"""
            SELECT model_id,
                   SUM(tokens_input)  AS total_input,
                   SUM(tokens_output) AS total_output,
                   SUM(cost)          AS total_cost
            FROM cost_tracking
            {where}
            GROUP BY model_id
        """
        cur = self._cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        summary: Dict[str, Any] = {
            "total_cost": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "by_model": {},
        }
        for r in rows:
            m = r["model_id"]
            summary["by_model"][m] = {
                "cost": float(r["total_cost"] or 0),
                "input_tokens": int(r["total_input"] or 0),
                "output_tokens": int(r["total_output"] or 0),
            }
            summary["total_cost"] += float(r["total_cost"] or 0)
            summary["total_input_tokens"] += int(r["total_input"] or 0)
            summary["total_output_tokens"] += int(r["total_output"] or 0)
        return summary

    # ------------------------------------------------------------------
    # Messages (chat history with summaries + tags)
    # ------------------------------------------------------------------

    def save_message(
        self,
        session_id: str,
        role: str,
        content_raw: str,
        content_summary: Optional[str] = None,
        tags: Optional[List[str]] = None,
        model_id: Optional[str] = None,
        tokens_used: int = 0,
    ) -> str:
        """Save a chat message with optional summary and tags."""
        message_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO messages
              (id, session_id, role, content_raw, content_summary,
               tags_json, model_id, tokens_used)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                message_id,
                session_id,
                role,
                content_raw,
                content_summary,
                json.dumps(tags or []),
                model_id,
                tokens_used,
            ),
        )
        # Broadcast to Redis for multi-process sync
        if redis_store.is_connected():
            redis_store.publish_event(
                "memory:message_saved",
                {
                    "message_id": message_id,
                    "session_id": session_id,
                    "role": role,
                    "model_id": model_id,
                },
            )
        return message_id

    def update_message_summary(self, message_id: str, content_summary: str) -> None:
        """Update the compressed summary for a message."""
        self._execute(
            "UPDATE messages SET content_summary = %s WHERE id = %s",
            (content_summary, message_id),
        )

    def update_message_tags(self, message_id: str, tags: List[str]) -> None:
        """Update tags for a message."""
        self._execute(
            "UPDATE messages SET tags_json = %s WHERE id = %s",
            (json.dumps(tags), message_id),
        )

    def update_message_content(self, message_id: str, new_content: str) -> bool:
        """Update the raw content of a message."""
        try:
            self._execute(
                "UPDATE messages SET content_raw = %s WHERE id = %s",
                (new_content, message_id),
            )
            return True
        except Exception as e:
            print(f"Error updating message content: {e}")
            return False

    def get_messages(
        self,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get messages for a session in chronological order."""
        cur = self._cursor()
        # Fetch newest N then return in ascending order (same behaviour as SQLite version)
        cur.execute(
            """
            SELECT id, role, content_raw, content_summary, tags_json,
                   model_id, tokens_used, created_at
            FROM (
                SELECT id, role, content_raw, content_summary, tags_json,
                       model_id, tokens_used, created_at
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            ) sub
            ORDER BY created_at ASC
            """,
            (session_id, limit, offset),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content_raw": r["content_raw"],
                "content_summary": r["content_summary"],
                "tags": json.loads(r["tags_json"]) if r["tags_json"] else [],
                "model_id": r["model_id"],
                "tokens_used": r["tokens_used"],
                "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            }
            for r in rows
        ]

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all chat sessions with the first user message as title."""
        cur = self._cursor()
        cur.execute(
            """
            SELECT session_id, MIN(created_at) AS created_at,
                   (ARRAY_AGG(content_raw ORDER BY created_at ASC))[1] AS title
            FROM messages
            WHERE role = 'user'
            GROUP BY session_id
            ORDER BY MIN(created_at) DESC
            """
        )
        rows = cur.fetchall()
        sessions = []
        for r in rows:
            title = r["title"] or ""
            if len(title) > 40:
                title = title[:37] + "..."
            sessions.append(
                {
                    "session_id": r["session_id"],
                    "title": title,
                    "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
                }
            )
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages."""
        try:
            self._execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
            self._execute(
                "DELETE FROM conversations WHERE session_id = %s", (session_id,)
            )
            return True
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False

    def get_messages_by_tags(
        self,
        tags: List[str],
        session_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get messages matching any of the given tags (JSON text search)."""
        if not tags:
            return []
        tag_conditions = " OR ".join(["tags_json LIKE %s"] * len(tags))
        params: List[Any] = [f'%"{t}"%' for t in tags]

        query = f"""
            SELECT id, session_id, role, content_raw, content_summary,
                   tags_json, model_id, tokens_used, created_at
            FROM messages
            WHERE ({tag_conditions})
        """
        if session_id:
            query += " AND session_id = %s"
            params.append(session_id)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        cur = self._cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "session_id": r["session_id"],
                "role": r["role"],
                "content_raw": r["content_raw"],
                "content_summary": r["content_summary"],
                "tags": json.loads(r["tags_json"]) if r["tags_json"] else [],
                "model_id": r["model_id"],
                "tokens_used": r["tokens_used"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_recent_summaries(
        self,
        session_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get recent message summaries for context assembly."""
        cur = self._cursor()
        cur.execute(
            """
            SELECT role, content_summary
            FROM messages
            WHERE session_id = %s AND content_summary IS NOT NULL
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (session_id, limit),
        )
        rows = cur.fetchall()
        return [{"role": r["role"], "content_summary": r["content_summary"]} for r in rows]

    def get_all_memories_with_tags(self) -> List[Dict[str, Any]]:
        """Get all messages that have non-empty tags (used for memory display)."""
        cur = self._cursor()
        cur.execute(
            """
            SELECT id, session_id, role, content_raw, tags_json, created_at
            FROM messages
            WHERE tags_json IS NOT NULL AND tags_json != '[]'
            ORDER BY created_at DESC
            """
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "session_id": r["session_id"],
                "role": r["role"],
                "content": r["content_raw"],
                "tags": json.loads(r["tags_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # User memories (long-term extracted facts)
    # ------------------------------------------------------------------

    def save_user_memory(self, content: str, tags: List[str] = None) -> str:
        """Save an extracted factual memory."""
        memory_id = str(uuid.uuid4())
        self._execute(
            "INSERT INTO user_memories (id, content, tags_json) VALUES (%s, %s, %s)",
            (memory_id, content, json.dumps(tags or [])),
        )
        return memory_id

    def update_user_memory(self, memory_id: str, new_content: str) -> bool:
        """Update a user memory's content."""
        try:
            self._execute(
                "UPDATE user_memories SET content = %s WHERE id = %s",
                (new_content, memory_id),
            )
            return True
        except Exception as e:
            print(f"Error updating user memory: {e}")
            return False

    def delete_user_memory(self, memory_id: str) -> bool:
        """Delete a user memory."""
        try:
            self._execute("DELETE FROM user_memories WHERE id = %s", (memory_id,))
            return True
        except Exception as e:
            print(f"Error deleting user memory: {e}")
            return False

    def get_all_user_memories(self) -> List[Dict[str, Any]]:
        """Get all user memories."""
        cur = self._cursor()
        cur.execute(
            "SELECT id, content, tags_json, created_at FROM user_memories ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "content": r["content"],
                "tags": json.loads(r["tags_json"]) if r["tags_json"] else [],
                "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # API keys
    # ------------------------------------------------------------------

    def save_api_key(
        self, provider: str, key_value: str, label: Optional[str] = None
    ) -> str:
        """Save or update an API key for a provider (UPSERT)."""
        key_id = str(uuid.uuid4())
        label = label or f"{provider.title()} API Key"
        self._execute(
            """
            INSERT INTO api_keys (id, provider, label, key_value, is_active, added_at)
            VALUES (%s, %s, %s, %s, 1, CURRENT_TIMESTAMP)
            ON CONFLICT (provider) DO UPDATE SET
                label      = EXCLUDED.label,
                key_value  = EXCLUDED.key_value,
                is_active  = 1,
                added_at   = CURRENT_TIMESTAMP
            """,
            (key_id, provider.lower(), label, key_value),
        )
        return key_id

    def get_api_keys(self) -> List[Dict[str, Any]]:
        """Retrieve all registered API keys."""
        cur = self._cursor()
        cur.execute(
            "SELECT id, provider, label, key_value, is_active, added_at FROM api_keys ORDER BY added_at DESC"
        )
        return [
            {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()}
            for r in cur.fetchall()
        ]

    def get_api_key_by_provider(self, provider: str) -> Optional[str]:
        """Get active API key string for a specific provider (with alias resolution)."""
        p = provider.lower().strip()
        alias_groups = [
            {"mistral", "mistralai", "codestral"},
            {"google", "gemini"},
            {"anthropic", "claude"},
            {"openai"},
            {"groq"},
            {"openrouter"},
        ]
        aliases: set = {p}
        for group in alias_groups:
            if p in group:
                aliases = group
                break
        placeholders = ",".join(["%s"] * len(aliases))
        cur = self._cursor()
        cur.execute(
            f"SELECT key_value FROM api_keys WHERE provider IN ({placeholders}) AND is_active = 1 ORDER BY added_at DESC LIMIT 1",
            tuple(aliases),
        )
        row = cur.fetchone()
        return row["key_value"] if row else None

    def delete_api_key(self, provider: str) -> bool:
        """Delete an API key by provider."""
        cur = self._execute(
            "DELETE FROM api_keys WHERE provider = %s", (provider.lower(),)
        )
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Role assignments
    # ------------------------------------------------------------------

    def save_role_assignment(self, role: str, provider: str, model_id: str) -> bool:
        """Save model & provider assignment for a role (UPSERT)."""
        self._execute(
            """
            INSERT INTO role_assignments (role, provider, model_id, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (role) DO UPDATE SET
                provider   = EXCLUDED.provider,
                model_id   = EXCLUDED.model_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (role.lower(), provider.lower(), model_id),
        )
        # Sync with Redis
        if redis_store.is_connected():
            redis_store.set_role_model(role.lower(), f"{provider.lower()}:{model_id}")
        return True

    def get_role_assignments(self) -> Dict[str, Dict[str, str]]:
        """Retrieve all role → model assignments."""
        cur = self._cursor()
        cur.execute("SELECT role, provider, model_id FROM role_assignments")
        rows = cur.fetchall()
        res: Dict[str, Dict[str, str]] = {}
        for r in rows:
            prov = r["provider"] if r["provider"] else "openrouter"
            res[r["role"]] = {"provider": prov, "model_id": r["model_id"]}
        return res

    # ------------------------------------------------------------------
    # Model notes / favourites
    # ------------------------------------------------------------------

    def save_model_note(
        self, model_id: str, provider: str, is_favorite: int, notes: str
    ) -> bool:
        """Save or update user notes / favourite status for a model (UPSERT)."""
        self._execute(
            """
            INSERT INTO model_notes (model_id, provider, is_favorite, notes, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (model_id) DO UPDATE SET
                provider    = EXCLUDED.provider,
                is_favorite = EXCLUDED.is_favorite,
                notes       = EXCLUDED.notes,
                updated_at  = CURRENT_TIMESTAMP
            """,
            (model_id, provider.lower(), 1 if is_favorite else 0, notes),
        )
        return True

    def get_model_notes(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all model notes & favourite states."""
        cur = self._cursor()
        cur.execute(
            "SELECT model_id, provider, is_favorite, notes, updated_at FROM model_notes"
        )
        rows = cur.fetchall()
        return {
            r["model_id"]: {
                "model_id": r["model_id"],
                "provider": r["provider"],
                "is_favorite": bool(r["is_favorite"]),
                "notes": r["notes"] or "",
                "updated_at": r["updated_at"],
            }
            for r in rows
        }

    def get_model_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get call counts and last-used timestamp per model."""
        cur = self._cursor()
        cur.execute(
            """
            SELECT model_id, COUNT(*) AS call_count, MAX(created_at) AS last_used
            FROM messages
            WHERE model_id IS NOT NULL AND model_id != ''
            GROUP BY model_id
            """
        )
        rows = cur.fetchall()
        return {
            r["model_id"]: {
                "call_count": r["call_count"],
                "last_used": r["last_used"],
            }
            for r in rows
        }

    # ------------------------------------------------------------------
    # Database stats
    # ------------------------------------------------------------------

    def get_database_stats(self) -> Dict[str, Any]:
        """Get row counts for all core tables."""
        stats: Dict[str, Any] = {}
        cur = self._cursor()
        for table in [
            "conversations",
            "tool_executions",
            "documents",
            "cost_tracking",
            "messages",
        ]:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
            stats[f"{table}_count"] = cur.fetchone()["cnt"]

        # Most-used model
        cur.execute(
            """
            SELECT model_id, COUNT(*) AS cnt
            FROM conversations
            GROUP BY model_id
            ORDER BY cnt DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row:
            stats["most_used_model"] = row["model_id"]
            stats["most_used_model_count"] = row["cnt"]
        return stats

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Delete records older than `days_to_keep` days."""
        deleted = 0
        interval = f"{days_to_keep} days"
        for table in ("conversations", "tool_executions", "cost_tracking", "messages"):
            cur = self._execute(
                f"DELETE FROM {table} WHERE created_at < NOW() - INTERVAL %s",
                (interval,),
            )
            deleted += cur.rowcount
        return deleted

    # ------------------------------------------------------------------
    # SRE-specific methods (new for CockroachSRE)
    # ------------------------------------------------------------------

    def save_incident(
        self,
        title: str,
        description: str = "",
        severity: str = "P3",
        service_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        incident_id: Optional[str] = None,
    ) -> str:
        """Save or update an SRE incident in CockroachDB (deduplicates by id or title)."""
        inc_id = (incident_id or "").strip()
        cur = self._cursor()
        if inc_id:
            cur.execute("SELECT id FROM incidents WHERE id = %s LIMIT 1", (inc_id,))
        else:
            cur.execute("SELECT id FROM incidents WHERE LOWER(title) = LOWER(%s) LIMIT 1", (title.strip(),))
        existing = cur.fetchone()
        if existing:
            target_id = existing["id"]
            self._execute(
                """
                UPDATE incidents
                SET title = %s, description = %s, severity = %s, service_name = %s, metadata = %s
                WHERE id = %s
                """,
                (title.strip(), description, severity, service_name, json.dumps(metadata or {}), target_id)
            )
            return target_id

        new_id = inc_id or str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO incidents
              (id, title, description, severity, service_name, status, metadata)
            VALUES (%s, %s, %s, %s, %s, 'NEW', %s)
            """,
            (
                new_id,
                title.strip(),
                description,
                severity,
                service_name,
                json.dumps(metadata or {}),
            ),
        )
        return new_id

    def get_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        service_name: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Retrieve incidents, optionally filtered by status/severity/service."""
        conditions: List[str] = []
        params: List[Any] = []
        if status:
            conditions.append("status = %s")
            params.append(status.upper())
        if severity:
            conditions.append("severity = %s")
            params.append(severity.upper())
        if service_name:
            conditions.append("LOWER(service_name) = LOWER(%s)")
            params.append(service_name)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur = self._cursor()
        cur.execute(
            f"""
            SELECT id, title, description, severity, service_name, status,
                   root_cause, metadata, created_at, resolved_at
            FROM incidents
            {where}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (*params, limit),
        )
        rows = cur.fetchall()
        return [
            {
                **{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()},
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            }
            for r in rows
        ]

    def resolve_incident(
        self, incident_id: str, root_cause: str = ""
    ) -> bool:
        """Mark an incident as resolved."""
        try:
            self._execute(
                """
                UPDATE incidents
                SET status = 'RESOLVED', root_cause = %s, resolved_at = NOW()
                WHERE id = %s
                """,
                (root_cause, incident_id),
            )
            return True
        except Exception as e:
            print(f"Error resolving incident: {e}")
            return False

    def save_runbook(
        self,
        title: str,
        content: str,
        service_name: str = "",
        author: str = "",
    ) -> str:
        """Save or update an SRE runbook / playbook (deduplicates by title)."""
        cur = self._cursor()
        cur.execute("SELECT id FROM runbooks WHERE LOWER(title) = LOWER(%s) LIMIT 1", (title.strip(),))
        existing = cur.fetchone()
        if existing:
            runbook_id = existing["id"]
            self._execute(
                """
                UPDATE runbooks 
                SET content = %s, service_name = %s, author = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (content, service_name, author, runbook_id)
            )
            return runbook_id

        runbook_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO runbooks (id, title, content, service_name, author)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (runbook_id, title.strip(), content, service_name, author),
        )
        return runbook_id

    def get_runbooks(
        self, service_name: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve runbooks, optionally filtered by service."""
        cur = self._cursor()
        if service_name:
            cur.execute(
                """
                SELECT id, title, content, service_name, author, created_at, updated_at
                FROM runbooks
                WHERE LOWER(service_name) = LOWER(%s)
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (service_name, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, title, content, service_name, author, created_at, updated_at
                FROM runbooks
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        return [
            {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()}
            for r in cur.fetchall()
        ]

    def save_fix_history(
        self,
        incident_id: str,
        action_taken: str,
        engineer_notes: str = "",
        runbook_id: Optional[str] = None,
        success: bool = True,
    ) -> str:
        """Record or update a fix/resolution action taken during an incident."""
        cur = self._cursor()
        cur.execute("SELECT id FROM fix_history WHERE incident_id = %s AND LOWER(action_taken) = LOWER(%s) LIMIT 1", (incident_id, action_taken.strip()))
        existing = cur.fetchone()
        if existing:
            fix_id = existing["id"]
            self._execute(
                """
                UPDATE fix_history
                SET engineer_notes = %s, runbook_id = %s, success = %s
                WHERE id = %s
                """,
                (engineer_notes or "", runbook_id, 1 if success else 0, fix_id)
            )
            return fix_id

        fix_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO fix_history
              (id, incident_id, runbook_id, action_taken, engineer_notes, success)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                fix_id,
                incident_id,
                runbook_id,
                action_taken.strip(),
                engineer_notes or "",
                1 if success else 0,
            ),
        )
        return fix_id

    def get_fix_history(
        self, incident_id: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get fix history, optionally for a specific incident."""
        cur = self._cursor()
        if incident_id:
            cur.execute(
                """
                SELECT id, incident_id, runbook_id, action_taken,
                       engineer_notes, success, created_at
                FROM fix_history
                WHERE incident_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (incident_id, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, incident_id, runbook_id, action_taken,
                       engineer_notes, success, created_at
                FROM fix_history
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall()
        return [
            {
                **{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()},
                "success": bool(r["success"])
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def close(self):
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ---------------------------------------------------------------------------
# SessionManager — identical interface, updated to use CockroachMemoryStore
# ---------------------------------------------------------------------------

class SessionManager:
    """Manages conversation sessions backed by CockroachDB."""

    def __init__(self, memory_store: CockroachMemoryStore):
        self.memory_store = memory_store
        self.current_session_id = str(uuid.uuid4())
        self.session_start = datetime.now()

    def new_session(self) -> str:
        """Start a new session."""
        self.current_session_id = str(uuid.uuid4())
        self.session_start = datetime.now()
        return self.current_session_id

    def get_session_context(
        self,
        max_messages: int = 10,
        max_tokens: int = 2000,
    ):
        """Get conversation context for current session."""
        from src.models.openrouter_client import Message

        conversations = self.memory_store.get_conversation_history(
            self.current_session_id, limit=max_messages * 2
        )
        messages = []
        total_tokens = 0
        for conv in reversed(conversations):
            user_tokens = len(conv["user_message"].split())
            assistant_tokens = len(conv["assistant_message"].split())
            message_tokens = user_tokens + assistant_tokens + 20
            if total_tokens + message_tokens > max_tokens:
                break
            messages.append(Message(role="user", content=conv["user_message"]))
            messages.append(
                Message(role="assistant", content=conv["assistant_message"])
            )
            total_tokens += message_tokens
        return messages

    def save_conversation(
        self,
        model_id: str,
        user_message: str,
        assistant_message: str,
        tokens_used: int = 0,
        cost: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save a conversation turn to the current session."""
        return self.memory_store.save_conversation(
            session_id=self.current_session_id,
            model_id=model_id,
            user_message=user_message,
            assistant_message=assistant_message,
            tokens_used=tokens_used,
            cost=cost,
            metadata=metadata,
        )

    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics for the current session."""
        conversations = self.memory_store.get_conversation_history(
            self.current_session_id, limit=1000
        )
        total_tokens = sum(c["tokens_used"] for c in conversations)
        total_cost = sum(c["cost"] for c in conversations)
        model_counts: Dict[str, int] = {}
        for conv in conversations:
            m = conv["model_id"]
            model_counts[m] = model_counts.get(m, 0) + 1
        return {
            "session_id": self.current_session_id,
            "start_time": self.session_start.isoformat(),
            "conversation_count": len(conversations),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "model_usage": model_counts,
        }


# ---------------------------------------------------------------------------
# Backward-compat alias so any module that still imports SQLiteMemoryStore
# from this file gets CockroachMemoryStore transparently.
# ---------------------------------------------------------------------------
SQLiteMemoryStore = CockroachMemoryStore

# ---------------------------------------------------------------------------
# Module-level singleton (mirrors sqlite_store.py usage pattern)
# ---------------------------------------------------------------------------
try:
    memory_store = CockroachMemoryStore()
except Exception as _e:
    print(f"[WARNING] Could not initialise CockroachMemoryStore at import time: {_e}")
    memory_store = None  # type: ignore[assignment]
