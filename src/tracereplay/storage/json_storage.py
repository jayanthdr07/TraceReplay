"""Atomic JSON storage engine for saving and loading TraceReplay fixtures.

Ensures fixtures are human-readable, Git-friendly, and never corrupted on crash.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from pydantic import ValidationError

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.exceptions import FixtureNotFoundError, InvalidFixtureError
from tracereplay.models import SessionRecord
from tracereplay.sanitizer import Sanitizer
from tracereplay.storage.resolver import FixtureResolver


class JsonStorageEngine:
    """Storage engine for saving and loading TraceReplay fixtures in JSON format."""

    def __init__(
        self,
        resolver: FixtureResolver | None = None,
        sanitizer: Sanitizer | None = None,
        config: TraceReplayConfig | None = None,
    ) -> None:
        self.config = config or get_config()
        self.resolver = resolver or FixtureResolver(config=self.config)
        self.sanitizer = sanitizer or Sanitizer(config=self.config)

    def save(
        self,
        session: SessionRecord,
        path: Path | None = None,
        sanitize: bool = True,
    ) -> Path:
        """Save a SessionRecord to a JSON fixture file.

        Args:
            session (SessionRecord): The session record to save.
            path (Path | None): Optional path to save the fixture. If None, uses the resolver.
            sanitize (bool): Whether to sanitize sensitive data before saving.

        Returns:
            Path: The path to the saved fixture file.
        """
        target_path = path.resolve() if path else self.resolver.resolve(session.name)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Sanitize secret if requested
        to_save = self.sanitizer.sanitize_session(session) if sanitize else session

        # 2. Serialize to formatted JSON with sorted keys for clean git diffs
        json_data = to_save.model_dump_json(indent=2)

        # 3. Atomic write: Write to a hidden temporary file in the same directory
        temp_name = f".tmp_{uuid.uuid4().hex[:8]}_{target_path.name}"
        temp_path = target_path.parent / temp_name

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(json_data)
                f.flush()
                os.fsync(f.fileno())

            # 4. Rename the temporary file to the target path atomically
            os.replace(temp_path, target_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise

        return target_path

    def load(self, session_name_or_path: str | Path) -> SessionRecord:
        """Load and validate a SessionRecord from disk.

        Raises FixtureNotFoundError if file is missing.
        Raises InvalidFixtureError if JSON is malformed or schema fails.
        """
        if isinstance(session_name_or_path, Path):
            target_path = session_name_or_path.resolve()
        else:
            target_path = self.resolver.resolve(session_name_or_path)

        if not target_path.is_file():
            raise FixtureNotFoundError(
                f"Fixture file not found: {target_path}",
                fixture_path=str(target_path),
                session_name=target_path.stem,
            )

        try:
            with open(target_path, encoding="utf-8") as f:
                raw_text = f.read()
        except OSError as err:
            raise InvalidFixtureError(
                f"Failed to read fixture file: {target_path}",
                fixture_path=str(target_path),
                validation_error=str(err),
            ) from err

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as err:
            err_pos = f"line {err.lineno}, col {err.colno}"
            raise InvalidFixtureError(
                f"Malformed JSON in fixture file: {target_path} ({err_pos})",
                fixture_path=str(target_path),
                validation_error=f"JSONDecodeError: {err.msg}",
            ) from err

        try:
            return SessionRecord.model_validate(data)
        except ValidationError as err:
            raise InvalidFixtureError(
                f"Schema validation failed for fixture file: {target_path}",
                fixture_path=str(target_path),
                validation_error=str(err),
            ) from err
