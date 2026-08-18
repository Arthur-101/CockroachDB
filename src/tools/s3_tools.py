"""
Amazon S3 integration for CockroachSRE.

Handles:
- Upload / download runbooks and incident logs to/from S3
- Auto-index fetched content into CockroachDB vector store (pgvector)
- List and sync S3 knowledge base objects

Bucket: cockroachsre-knowledge-base
Region: ap-south-1  (matches AWS_REGION in .env)
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default bucket / prefix constants (overridable via env)
# ---------------------------------------------------------------------------
DEFAULT_BUCKET = os.environ.get("S3_BUCKET_NAME", "cockroachsre-knowledge-base")
RUNBOOK_PREFIX = "runbooks/"
INCIDENT_PREFIX = "incident-logs/"


def _get_s3_client():
    """Build a boto3 S3 client from environment credentials."""
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "ap-south-1"),
    )


class S3KnowledgeBase:
    """
    Amazon S3 knowledge base manager.

    S3 acts as the authoritative source of truth for runbooks and incident logs.
    Content is fetched from S3 and indexed into CockroachDB's distributed vector store
    for semantic search.
    """

    def __init__(self, bucket: str = DEFAULT_BUCKET):
        self.bucket = bucket
        self._s3 = None  # lazy init

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = _get_s3_client()
        return self._s3

    # ------------------------------------------------------------------
    # Upload helpers
    # ------------------------------------------------------------------

    def upload_runbook(
        self,
        name: str,
        content: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Upload a runbook markdown/text file to S3 under runbooks/."""
        clean_name = name if name.endswith(".md") or name.endswith(".txt") else f"{name}.md"
        key = f"{RUNBOOK_PREFIX}{clean_name}"
        return self._upload(key, content, content_type="text/markdown", tags=tags)

    def upload_incident_log(
        self,
        incident_id: str,
        content: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Upload a JSON or text incident log to S3 under incident-logs/<date>/."""
        date_prefix = datetime.utcnow().strftime("%Y-%m-%d")
        clean_id = incident_id.replace(".json", "")
        key = f"{INCIDENT_PREFIX}{date_prefix}/{clean_id}.json"
        return self._upload(key, content, content_type="application/json", tags=tags)

    def upload_postmortem(
        self,
        name: str,
        content: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Upload a postmortem or resolution document under incident-logs/<date>/."""
        date_prefix = datetime.utcnow().strftime("%Y-%m-%d")
        clean_name = name if name.endswith(".json") else f"{name}.json"
        key = f"{INCIDENT_PREFIX}{date_prefix}/{clean_name}"
        return self._upload(key, content, content_type="application/json", tags=tags)

    def _upload(
        self,
        key: str,
        content: str,
        content_type: str = "text/plain",
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        try:
            put_kwargs: Dict[str, Any] = {
                "Bucket": self.bucket,
                "Key": key,
                "Body": content.encode("utf-8"),
                "ContentType": content_type,
            }
            if tags:
                put_kwargs["Tagging"] = "&".join(f"{k}={v}" for k, v in tags.items())

            self.s3.put_object(**put_kwargs)
            logger.info(f"S3 upload OK: s3://{self.bucket}/{key}")
            return {
                "success": True,
                "s3_key": key,
                "bucket": self.bucket,
                "url": f"s3://{self.bucket}/{key}",
            }
        except (ClientError, BotoCoreError) as e:
            logger.error(f"S3 upload failed for {key}: {e}")
            return {"success": False, "error": str(e), "s3_key": key}

    # ------------------------------------------------------------------
    # Download / fetch helpers
    # ------------------------------------------------------------------

    def fetch_runbook(self, name: str) -> Dict[str, Any]:
        """Fetch a runbook from S3 by filename."""
        key = f"{RUNBOOK_PREFIX}{name}"
        return self._fetch(key)

    def fetch_object(self, key: str) -> Dict[str, Any]:
        """Fetch any object from S3 by its full key."""
        return self._fetch(key)

    def _fetch(self, key: str) -> Dict[str, Any]:
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            logger.info(f"S3 fetch OK: s3://{self.bucket}/{key} ({len(content)} chars)")
            return {
                "success": True,
                "content": content,
                "s3_key": key,
                "bucket": self.bucket,
                "content_type": response.get("ContentType", "text/plain"),
                "last_modified": str(response.get("LastModified", "")),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return {"success": False, "error": f"Object not found: {key}", "content": None}
            logger.error(f"S3 fetch failed for {key}: {e}")
            return {"success": False, "error": str(e), "content": None}
        except BotoCoreError as e:
            logger.error(f"S3 fetch failed for {key}: {e}")
            return {"success": False, "error": str(e), "content": None}

    # ------------------------------------------------------------------
    # List objects
    # ------------------------------------------------------------------

    def list_runbooks(self) -> Dict[str, Any]:
        """List all runbooks in the S3 knowledge base."""
        return self._list_prefix(RUNBOOK_PREFIX)

    def list_incident_logs(self, date_prefix: Optional[str] = None) -> Dict[str, Any]:
        """List incident logs, optionally filtered by date (YYYY-MM-DD)."""
        prefix = f"{INCIDENT_PREFIX}{date_prefix}/" if date_prefix else INCIDENT_PREFIX
        return self._list_prefix(prefix)

    def list_postmortems(self) -> Dict[str, Any]:
        """List all postmortems in S3."""
        return self._list_prefix(POSTMORTEM_PREFIX)

    def list_all(self) -> Dict[str, Any]:
        """List every object in the knowledge base bucket."""
        return self._list_prefix("")

    def _list_prefix(self, prefix: str) -> Dict[str, Any]:
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)

            objects = []
            for page in pages:
                for obj in page.get("Contents", []):
                    objects.append({
                        "key": obj["Key"],
                        "size_bytes": obj["Size"],
                        "last_modified": str(obj["LastModified"]),
                        "name": obj["Key"].split("/")[-1],
                    })

            logger.info(f"S3 list '{prefix}': {len(objects)} objects")
            return {"success": True, "objects": objects, "count": len(objects), "prefix": prefix}
        except (ClientError, BotoCoreError) as e:
            logger.error(f"S3 list failed for prefix '{prefix}': {e}")
            return {"success": False, "error": str(e), "objects": []}

    # ------------------------------------------------------------------
    # S3 → CockroachDB vector index pipeline
    # ------------------------------------------------------------------

    def sync_to_vector_store(
        self,
        prefix: str = "",
        vector_store=None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Fetch objects from S3 and index them into CockroachDB vector store.

        This is the core integration:
          S3 (source of truth) → CockroachDB pgvector (semantic index)

        The agent can then run cosine-distance queries against CockroachDB
        to find relevant runbooks without re-fetching from S3 every time.
        """
        if vector_store is None:
            from src.memory.vector_store import VectorMemoryStore
            vector_store = VectorMemoryStore()

        list_result = self._list_prefix(prefix)
        if not list_result["success"]:
            return {"success": False, "error": list_result.get("error"), "indexed_count": 0}

        objects = list_result["objects"][:limit]
        indexed, skipped, errors = 0, 0, []

        for obj in objects:
            key = obj["key"]
            if key.endswith("/"):
                skipped += 1
                continue

            fetch_result = self._fetch(key)
            if not fetch_result["success"] or not fetch_result.get("content"):
                errors.append({"key": key, "error": fetch_result.get("error", "empty content")})
                continue

            content = fetch_result["content"]
            try:
                vector_store.add_document(
                    file_path=f"s3://{self.bucket}/{key}",
                    content=content,
                )
                indexed += 1
                logger.info(f"Indexed s3://{self.bucket}/{key} into CockroachDB pgvector")

                try:
                    from src.memory.cockroach_store import SQLiteMemoryStore
                    db = SQLiteMemoryStore()
                    if key.startswith("runbooks/") and key.endswith(".md"):
                        title = key.split("/")[-1].replace(".md", "").replace("-", " ").title()
                        first_line = content.split("\n")[0]
                        if first_line.startswith("#"):
                            title = first_line.lstrip("#").strip()
                        db.save_runbook(
                            title=title,
                            content=content,
                            service_name="cockroachdb",
                            author="AWS S3 Sync",
                        )
                    elif (key.startswith("incident-logs/") or key.startswith("incidents/")) and key.endswith(".json"):
                        try:
                            import json
                            inc_data = json.loads(content)
                            if isinstance(inc_data, dict):
                                inc_id = inc_data.get("incident_id") or key.split("/")[-1].replace(".json", "")
                                title = inc_data.get("title", inc_id)
                                symptoms = inc_data.get("symptoms", [])
                                desc = "\n".join(symptoms) if isinstance(symptoms, list) else str(symptoms)
                                if not desc and inc_data.get("root_cause"):
                                    desc = str(inc_data.get("root_cause"))

                                db.save_incident(
                                    title=title,
                                    description=desc,
                                    severity=inc_data.get("severity", "P2"),
                                    service_name=inc_data.get("affected_service", "cockroachdb"),
                                    metadata=inc_data,
                                    incident_id=inc_id,
                                )

                                resolution = inc_data.get("resolution")
                                if resolution:
                                    db.save_fix_history(
                                        incident_id=inc_id,
                                        action_taken=str(resolution),
                                        engineer_notes=str(inc_data.get("root_cause", "")),
                                        runbook_id=inc_data.get("runbook_used"),
                                        success=True
                                    )
                                    db.resolve_incident(
                                        incident_id=inc_id,
                                        root_cause=str(inc_data.get("root_cause", ""))
                                    )
                        except Exception as json_err:
                            logger.debug(f"Incident JSON parse note: {json_err}")
                except Exception as ex:
                    logger.debug(f"Relational sync note: {ex}")
            except Exception as e:
                errors.append({"key": key, "error": str(e)})
                logger.error(f"Failed to index {key}: {e}")

        return {
            "success": True,
            "indexed_count": indexed,
            "skipped_count": skipped,
            "error_count": len(errors),
            "errors": errors,
            "total_objects": len(objects),
        }

    def fetch_and_index(self, key: str, vector_store=None) -> Dict[str, Any]:
        """
        Fetch a single S3 object and immediately index into CockroachDB.
        Used when the agent needs to ingest a specific document on demand.
        """
        if vector_store is None:
            from src.memory.vector_store import VectorMemoryStore
            vector_store = VectorMemoryStore()

        fetch_result = self._fetch(key)
        if not fetch_result["success"]:
            return fetch_result

        content = fetch_result["content"]
        try:
            vector_store.add_document(
                file_path=f"s3://{self.bucket}/{key}",
                content=content,
            )
            return {
                "success": True,
                "s3_key": key,
                "indexed": True,
                "chars_indexed": len(content),
                "message": "Fetched from S3 and indexed into CockroachDB vector store.",
            }
        except Exception as e:
            return {"success": False, "s3_key": key, "indexed": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Connectivity test
    # ------------------------------------------------------------------

    def test_connection(self) -> Dict[str, Any]:
        """
        Verify S3 credentials and bucket accessibility.
        Called from the Settings UI Test button.
        """
        try:
            self.s3.head_bucket(Bucket=self.bucket)
            return {
                "success": True,
                "bucket": self.bucket,
                "region": os.environ.get("AWS_REGION", "ap-south-1"),
                "message": f"Connected to s3://{self.bucket}",
            }
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "404":
                return {"success": False, "error": f"Bucket '{self.bucket}' not found."}
            elif code in ("403", "401"):
                return {"success": False, "error": "Access denied — check AWS credentials."}
            return {"success": False, "error": str(e)}
        except BotoCoreError as e:
            return {"success": False, "error": f"AWS config error: {e}"}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
s3_kb = S3KnowledgeBase()
