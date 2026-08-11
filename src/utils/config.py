import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""


    # ── Memory configuration ─────────────────────────────────
    sqlite_db_path: str = "data/agenticai.db"
    chroma_db_path: str = "data/chroma"
    documents_path: str = "data/documents"
    redis_url: str = "redis://localhost:6379/0"

    # ── Cost / budget guard ───────────────────────────────────
    # These are kept as lightweight session-level guard rails.
    # Per-model pricing is resolved dynamically via ProviderRouter,
    # NOT stored here as hardcoded constants.
    cost_warning_threshold: float = 10.0
    cost_limit: float = 50.0

    # ── Security settings ────────────────────────────────────
    allowed_file_types: List[str] = [
        ".py", ".pdf", ".txt", ".md", ".json", ".yaml", ".yml",
    ]
    max_file_size_mb: int = 10
    require_permission_prompt: bool = True

    # ── Performance settings ─────────────────────────────────
    max_tokens_per_request: int = 4000
    temperature: float = 0.7
    request_timeout: int = 30

    # ── Chat / persona ────────────────────────────────────────
    # default_chat_model is the last-resort fallback used only when
    # no role assignment is found in Redis or SQLite.
    # Set via env var DEFAULT_CHAT_MODEL or leave blank to use the
    # orchestrator role assignment.
    default_chat_model: str = ""
    system_prompt: str = (
        "You are Antigravity, an intelligent Orchestrator AI. "
        "You have access to specialized expert sub-agents via the `ask_expert_model` tool "
        "(roles: 'coding', 'reasoning', 'multimodal', 'synthesizer'). "
        "You also have long-term memory."
    )
    summary_max_tokens: int = 400
    tag_extraction_model: Optional[str] = None

    # ── Pydantic v2 configuration ─────────────────────────────
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    # ── Validators ────────────────────────────────────────────
    @field_validator("sqlite_db_path", "chroma_db_path", "documents_path", mode="before")
    @classmethod
    def _ensure_parent_dirs(cls, v: str) -> str:
        """Create parent directories for any path-like setting."""
        path = Path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def _parse_file_types(cls, v: Any) -> List[str]:
        """Accept a comma-separated string from .env or a JSON array."""
        import json
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return [ft.strip() for ft in v.split(",") if ft.strip()]
        return v


class ConfigManager:
    """Manages configuration and settings."""

    def __init__(self):
        self.settings = Settings()
        self._cost_tracker: Dict[str, Any] = {"total_cost": 0.0, "model_usage": {}}
        self._initialize_directories()

    def _initialize_directories(self):
        """Initialize all required directories."""
        directories = [
            Path(self.settings.sqlite_db_path).parent,
            Path(self.settings.chroma_db_path),
            Path(self.settings.documents_path),
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    # ── Cost tracking ─────────────────────────────────────────
    def get_model_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for a model usage.
        Pricing is resolved dynamically from the ProviderRouter catalog
        rather than hardcoded constants.
        """
        try:
            from src.models.provider_router import ProviderRouter
            pricing = ProviderRouter.get_model_pricing_sync(model_id)
            input_cost  = (input_tokens  / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            return input_cost + output_cost
        except Exception:
            return 0.0

    def track_cost(self, model_id: str, input_tokens: int, output_tokens: int):
        """Track cost usage and check limits."""
        cost = self.get_model_cost(model_id, input_tokens, output_tokens)

        self._cost_tracker["total_cost"] += cost
        if model_id not in self._cost_tracker["model_usage"]:
            self._cost_tracker["model_usage"][model_id] = {
                "cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        self._cost_tracker["model_usage"][model_id]["cost"]          += cost
        self._cost_tracker["model_usage"][model_id]["input_tokens"]  += input_tokens
        self._cost_tracker["model_usage"][model_id]["output_tokens"] += output_tokens

        self._check_cost_limits()

    def _check_cost_limits(self):
        """Issue warnings if session cost exceeds configured thresholds."""
        total = self._cost_tracker["total_cost"]
        if total >= self.settings.cost_limit:
            print(f"⚠️  COST LIMIT EXCEEDED: ${total:.2f} (limit: ${self.settings.cost_limit})")
        elif total >= self.settings.cost_warning_threshold:
            print(f"⚠️  Cost warning: ${total:.2f} (threshold: ${self.settings.cost_warning_threshold})")

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get current session cost summary."""
        return {
            "total_cost": self._cost_tracker["total_cost"],
            "model_usage": self._cost_tracker["model_usage"],
            "cost_limit": self.settings.cost_limit,
            "cost_warning_threshold": self.settings.cost_warning_threshold,
        }

    # ── File guards ───────────────────────────────────────────
    def is_file_type_allowed(self, file_path: str) -> bool:
        """Check if file type is allowed."""
        path = Path(file_path)
        return any(path.name.lower().endswith(ft) for ft in self.settings.allowed_file_types)

    def is_file_size_allowed(self, file_path: str) -> bool:
        """Check if file size is within limits."""
        try:
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            return size_mb <= self.settings.max_file_size_mb
        except OSError:
            return False


# Global config instance
config = ConfigManager()