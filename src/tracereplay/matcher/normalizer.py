"""Request normalization and hashing engine for TraceReplay.

Strips dynamic parameters and normalizes payloads for deterministic comparison.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.models import RequestPayload


class RequestNormalizer:
    """Normalizes requestpayloads to enable deterministic comparison."""

    def __init__(self, config: TraceReplayConfig | None = None) -> None:
        self.config = config or get_config()
        self.ignored_params = {p.lower() for p in self.config.ignored_parameters}

    def normalize_text(self, text: str | None) -> str | None:
        if text is None:
            return None
        return text.replace("\r\n", "\n").strip()

    def filter_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Remove ignored parameters from the request payload."""
        return {k: v for k, v in parameters.items() if k.lower() not in self.ignored_params}

    def normalize_message(self, message: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Normalize message list, handling role, content, and nested text blocks.
        normalized: list[dict[str, Any]] = []
        for msg in message:
            clean_msg: dict[str, Any] = {}
            for k, v in msg.items():
                if k == "content" and isinstance(v, str):
                    clean_msg[k] = self.normalize_text(v)
                elif k == "content" and isinstance(v, list):
                    clean_blocks: list[Any] = []
                    for block in v:
                        if isinstance(block, dict) and "text" in block:
                            clean_b = dict(block)
                            clean_b["text"] = self.normalize_text(block["text"])
                            clean_blocks.append(clean_b)
                        else:
                            clean_blocks.append(block)
                    clean_msg[k] = clean_blocks
                else:
                    clean_msg[k] = v
            normalized.append(clean_msg)
        return normalized

    normalize_messages = normalize_message

    def normalize_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        # Sort and normalize tool declarations for order-independent comparison.
        if not tools:
            return None

        normalized: list[dict[str, Any]] = []
        for tool in tools:
            clean_tool = json.loads(json.dumps(tool, sort_keys=True))
            normalized.append(clean_tool)

        def tool_key(t: dict[str, Any]) -> tuple[str, str]:
            if "function" in t and isinstance(t["function"], dict):
                name = str(t["function"].get("name", ""))
            else:
                name = str(t.get("name", ""))
            return (name, json.dumps(t, sort_keys=True))

        return sorted(normalized, key=tool_key)

    def normalize_request(self, request: RequestPayload) -> dict[str, Any]:
        # Returns a clean, normalized dictionary representation of a RequestPayload
        clean_params = (
            self.filter_parameters(request.parameters) if self.config.match_parameters else {}
        )
        op_val = (
            request.operation.value
            if hasattr(request.operation, "value")
            else str(request.operation)
        )

        return {
            "messages": self.normalize_message(request.messages),
            "model": request.model.lower().strip(),
            "operation": op_val,
            "parameters": clean_params,
            "prompt": self.normalize_text(request.prompt),
            "provider": request.provider.lower().strip(),
            "tools": self.normalize_tools(request.tools),
        }

    def compute_hash(self, request: RequestPayload) -> str:
        #  Compute a deterministic SHA-256 fingerprint for a RequestPayload.
        normalized = self.normalize_request(request)
        serialized = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_request_hash(request: RequestPayload, config: TraceReplayConfig | None = None) -> str:
    #  Convenience helper to compute a deterministic SHA-256 hash for a request.
    return RequestNormalizer(config=config).compute_hash(request)
