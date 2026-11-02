"""Fixture path resolution and filesystem safety manager.

Prevents path traversal attacks and standardizes fixture file naming.
"""

from __future__ import annotations

import re
from pathlib import Path

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.exceptions import ConfigurationError

UNSAFE_FILENAME_CHARS = re.compile(r'[/\\:*?"<>|]')


def sanitize_filename(name: str) -> str:
    cleaned = UNSAFE_FILENAME_CHARS.sub("_", name.strip())
    cleaned = cleaned.strip(". _")
    return cleaned or "default_fixture"


class FixtureResolver:
    def __init__(
        self, base_dir: Path | None = None, config: TraceReplayConfig | None = None
    ) -> None:
        cfg = config or get_config()
        self.base_dir = (base_dir or cfg.fixtures_dir).resolve()

    def resolve(self, session_name: str, subfolder: str | None = None) -> Path:
        safe_name = sanitize_filename(session_name)
        if not safe_name.endswith(".json"):
            safe_name = f"{safe_name}.json"

        target_dir = self.base_dir
        if subfolder:
            safe_subfolder = sanitize_filename(subfolder)
            target_dir = target_dir / safe_subfolder

        resolved_path = (target_dir / safe_name).resolve()

        # Security check: Prevent path traversal attacks
        try:
            resolved_path.relative_to(self.base_dir)
        except ValueError as err:
            msg = (
                f"Path traversal detected: '{session_name}' resolves "
                f"outside fixtures directory: {self.base_dir}"
            )
            raise ConfigurationError(msg) from err

        return resolved_path

    def exists(self, session_name: str, subfolder: str | None = None) -> bool:
        return self.resolve(session_name, subfolder=subfolder).is_file()

    def list_fixtures(self) -> list[Path]:
        if not self.base_dir.exists():
            return []
        return sorted(self.base_dir.rglob("*.json"))
