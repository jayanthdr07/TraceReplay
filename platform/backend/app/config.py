"""Application configuration and environment settings for TraceReplay Platform."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """FastAPI application configuration settings."""

    # Project metadata
    project_name: str = "TraceReplay Platform API"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # CORS settings for frontend Next.js communication
    cors_origins: list[str] | str = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Supabase cloud credentials
    supabase_url: str | None = None
    supabase_key: str | None = None  # Anon public key
    supabase_service_role_key: str | None = None  # Admin service role key
    database_url: str | None = None  # Direct PostgreSQL connection string
    storage_bucket: str = "tracereplay-fixtures"

    # Local storage fallback directory
    local_fixtures_dir: str = ".tracereplay/fixtures"

    model_config = SettingsConfigDict(
        env_file=(
            str(Path(__file__).resolve().parent.parent / ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from a list, comma-separated string, or JSON string."""
        if isinstance(v, list):
            return [str(item).strip() for item in v]
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    parsed = json.loads(v_trimmed)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except Exception:
                    pass
            return [origin.strip() for origin in v_trimmed.split(",") if origin.strip()]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def is_local_mode(self) -> bool:
        """Return True if running in zero-cloud local mode (no Supabase credentials)."""
        if not self.supabase_url or not self.supabase_key:
            return True
        # Check for placeholder values
        url_lower = self.supabase_url.lower()
        return bool("your-project" in url_lower or "placeholder" in url_lower)

    def get_resolved_fixtures_dir(self) -> Path:
        """Resolve the local fixtures directory path safely."""
        p = Path(self.local_fixtures_dir)
        if not p.is_absolute():
            # If relative, check root of the workspace or current directory
            root_candidate = Path(__file__).resolve().parent.parent.parent.parent / p
            if root_candidate.exists():
                return root_candidate
        return p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton instance of application settings."""
    return Settings()
