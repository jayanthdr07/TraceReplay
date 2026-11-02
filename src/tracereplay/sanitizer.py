"""Sensitive data sanitization and secret scrubbing engine for TraceReplay.

Prevents credentials, API keys, authorization headers, and sensitive PII
from being written to local fixture files or shared across teams.
"""

from __future__ import annotations

import re
from typing import Any

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.models import Interaction, RequestPayload, ResponsePayload, SessionRecord

# Standard patterns for the common LLM API keys
DEFAULT_API_KEY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
]


class Sanitizer:
    def __init__(self, config: TraceReplayConfig | None = None) -> None:
        self.config = config or get_config()
        self.redact_keys = {k.lower() for k in self.config.redact_keys}
        self.compiled_patterns: list[re.Pattern[str]] = list(DEFAULT_API_KEY_PATTERNS)
        for pattern_str in self.config.redact_patterns:
            self.compiled_patterns.append(re.compile(pattern_str, re.IGNORECASE))

    def sanitize_string(self, value: str) -> str:
        sanitized = value
        for pattern in self.compiled_patterns:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized

    def sanitize_value(self, value: Any, key_name: str | None = None) -> Any:
        if key_name and key_name.lower() in self.redact_keys:
            return "[REDACTED]"

        if isinstance(value, str):
            return self.sanitize_string(value)

        if isinstance(value, dict):
            return {k: self.sanitize_value(v, key_name=str(k)) for k, v in value.items()}

        if isinstance(value, list):
            return [self.sanitize_value(item, key_name=key_name) for item in value]

        return value

    def sanitize_request(self, request: RequestPayload) -> RequestPayload:
        data = request.model_dump()
        sanitized_data = self.sanitize_value(data)
        return RequestPayload.model_validate(sanitized_data)

    def sanitize_response(self, response: ResponsePayload) -> ResponsePayload:
        data = response.model_dump()
        sanitized_data = self.sanitize_value(data)
        return ResponsePayload.model_validate(sanitized_data)

    def sanitize_interaction(self, interaction: Interaction) -> Interaction:
        return interaction.model_copy(
            update={
                "request": self.sanitize_request(interaction.request),
                "response": self.sanitize_response(interaction.response),
                "metadata": self.sanitize_value(interaction.metadata),
            }
        )

    def sanitize_session(self, session: SessionRecord) -> SessionRecord:
        sanitized_interactions = [self.sanitize_interaction(item) for item in session.interactions]
        return session.model_copy(
            update={
                "interactions": sanitized_interactions,
                "metadata": self.sanitize_value(session.metadata),
            }
        )


def sanitize_data(data: Any, config: TraceReplayConfig | None = None) -> Any:
    sanitizer = Sanitizer(config=config)
    return sanitizer.sanitize_value(data)
