"""
CockroachDB-backed vector memory store replacing ChromaDB.
Uses sentence-transformers locally to generate 384-dimensional embeddings,
and stores them inline directly in CockroachDB's documents, user_memories, and messages tables.
"""

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: build connection (shares same URL as cockroach_store)
# ---------------------------------------------------------------------------

def _get_conn() -> psycopg2.extensions.connection:
    url = os.environ.get("COCKROACH_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "COCKROACH_DATABASE_URL is not set in environment."
        )
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    return conn


class VectorMemoryStore:
    """CockroachDB-pgvector memory store. Drop-in replacement for ChromaDB."""

    def __init__(self, persist_directory: Optional[str] = None):
        """Initialize the local embedding model and DB connection."""
        logger.info("Initializing SentenceTransformer('all-MiniLM-L6-v2')...")
        try:
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("SentenceTransformer model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers model: {e}")
            raise

        self._conn: Optional[psycopg2.extensions.connection] = None
        self._ensure_connected()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _ensure_connected(self):
        try:
            if self._conn is None or self._conn.closed:
                self._conn = _get_conn()
        except Exception as e:
            logger.error(f"VectorStore failed to connect to CockroachDB: {e}")
            raise

    def _cursor(self) -> psycopg2.extras.RealDictCursor:
        self._ensure_connected()
        return self._conn.cursor()

    def _execute(self, sql: str, params: tuple = ()) -> psycopg2.extras.RealDictCursor:
        try:
            cur = self._cursor()
            cur.execute(sql, params)
            return cur
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            self._conn = _get_conn()
            cur = self._cursor()
            cur.execute(sql, params)
            return cur

    def _format_vector(self, embedding) -> str:
        """Format list of floats / numpy array as PostgreSQL vector format string: '[0.1,0.2,...]'"""
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        return "[" + ",".join(map(str, embedding)) + "]"

    # ------------------------------------------------------------------
    # Factual User Memories (facts / preferences)
    # ------------------------------------------------------------------

    def add_user_memory(self, memory_id: str, content: str):
        """Add embedding for a factual memory. The SQL record already exists, so we update it."""
        if not content or len(content.strip()) < 5:
            return

        try:
            embedding = self.model.encode(content)
            vec_str = self._format_vector(embedding)

            self._execute(
                "UPDATE user_memories SET embedding = %s WHERE id = %s",
                (vec_str, memory_id),
            )
        except Exception as e:
            logger.error(f"Error adding user memory vector: {e}")

    def update_user_memory(self, memory_id: str, content: str):
        """Update content and embedding for a factual memory."""
        try:
            embedding = self.model.encode(content)
            vec_str = self._format_vector(embedding)

            self._execute(
                "UPDATE user_memories SET content = %s, embedding = %s WHERE id = %s",
                (content, vec_str, memory_id),
            )
        except Exception as e:
            logger.error(f"Error updating user memory vector: {e}")

    def delete_user_memory(self, memory_id: str):
        """
        Delete user memory vector.
        Since cockroach_store.delete_user_memory deletes the database row entirely,
        this method is kept for API compatibility.
        """
        pass

    def search_user_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant factual user memories using cosine distance (<=>)."""
        if not query or len(query.strip()) < 3:
            return []

        try:
            embedding = self.model.encode(query)
            vec_str = self._format_vector(embedding)

            cur = self._cursor()
            cur.execute(
                """
                SELECT content, (embedding <=> %s) AS distance
                FROM user_memories
                WHERE embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT %s
                """,
                (vec_str, limit),
            )
            rows = cur.fetchall()
            return [
                {
                    "content": r["content"],
                    "distance": float(r["distance"]) if r["distance"] is not None else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error searching user memories vector store: {e}")
            return []

    # ------------------------------------------------------------------
    # Chat History Messages
    # ------------------------------------------------------------------

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None,
    ):
        """Add embedding to a chat message. (Mainly for compatibility)"""
        if not content or len(content.strip()) < 10:
            return

        doc_id = message_id or str(uuid.uuid4())
        try:
            embedding = self.model.encode(content)
            vec_str = self._format_vector(embedding)

            # Check if row exists; if so, update. Otherwise insert new message.
            cur = self._cursor()
            cur.execute("SELECT id FROM messages WHERE id = %s", (doc_id,))
            exists = cur.fetchone()

            if exists:
                self._execute(
                    "UPDATE messages SET embedding = %s WHERE id = %s",
                    (vec_str, doc_id),
                )
            else:
                self._execute(
                    """
                    INSERT INTO messages (id, session_id, role, content_raw, tags_json, embedding)
                    VALUES (%s, %s, %s, %s, '[]', %s)
                    """,
                    (doc_id, session_id, role, content, vec_str),
                )
        except Exception as e:
            logger.error(f"Error adding message vector: {e}")

    def search_similar_messages(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search similar past messages using cosine distance (<=>)."""
        if not query or len(query.strip()) < 3:
            return []

        try:
            embedding = self.model.encode(query)
            vec_str = self._format_vector(embedding)

            sql = """
                SELECT id, session_id, role, content_raw, tags_json, (embedding <=> %s) AS distance
                FROM messages
                WHERE embedding IS NOT NULL
            """
            params: List[Any] = [vec_str]
            if session_id:
                sql += " AND session_id = %s"
                params.append(session_id)
            sql += " ORDER BY distance ASC LIMIT %s"
            params.append(limit)

            cur = self._cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

            return [
                {
                    "content": r["content_raw"],
                    "metadata": {
                        "session_id": r["session_id"],
                        "role": r["role"],
                        "message_id": r["id"],
                    },
                    "distance": float(r["distance"]) if r["distance"] is not None else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error searching similar messages vector store: {e}")
            return []

    # ------------------------------------------------------------------
    # Documents / Runbooks (RAG chunks)
    # ------------------------------------------------------------------

    def add_document(
        self,
        file_path: str,
        content: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """Chunk a document, generate embeddings, and insert/upsert into documents table."""
        if not content:
            return

        # Basic overlap chunking
        chunks = []
        start = 0
        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]
            chunks.append(chunk)
            start += chunk_size - chunk_overlap
            if start >= len(content) or len(chunk) < chunk_overlap:
                break

        if not chunks:
            return

        logger.info(f"Chunked document '{file_path}' into {len(chunks)} parts. Generating embeddings...")

        try:
            for i, chunk in enumerate(chunks):
                doc_id = f"{file_path}_{i}"
                embedding = self.model.encode(chunk)
                vec_str = self._format_vector(embedding)
                meta_json = json.dumps({"file_path": file_path, "chunk": i})

                # Inline UPSERT using CockroachDB's ON CONFLICT syntax
                self._execute(
                    """
                    INSERT INTO documents (id, content, source, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        content   = EXCLUDED.content,
                        source    = EXCLUDED.source,
                        metadata  = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding
                    """,
                    (doc_id, chunk, file_path, meta_json, vec_str),
                )
            logger.info(f"Successfully upserted {len(chunks)} vector segments for '{file_path}'.")
        except Exception as e:
            logger.error(f"Error adding document chunks to vector store: {e}")

    def search_documents(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search across all indexed document vector chunks using cosine distance (<=>)."""
        if not query or len(query.strip()) < 3:
            return []

        try:
            embedding = self.model.encode(query)
            vec_str = self._format_vector(embedding)

            cur = self._cursor()
            cur.execute(
                """
                SELECT content, source, metadata, (embedding <=> %s) AS distance
                FROM documents
                WHERE embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT %s
                """,
                (vec_str, limit),
            )
            rows = cur.fetchall()

            results = []
            for r in rows:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
                if "file_path" not in meta:
                    meta["file_path"] = r["source"]
                results.append(
                    {
                        "content": r["content"],
                        "metadata": meta,
                        "distance": float(r["distance"]) if r["distance"] is not None else None,
                    }
                )
            return results
        except Exception as e:
            logger.error(f"Error searching document store: {e}")
            return []

    # ------------------------------------------------------------------
    # Context manager / Close support
    # ------------------------------------------------------------------

    def close(self):
        """Close connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
