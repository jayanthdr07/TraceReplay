"""Pydantic data models for TraceReplay interactions, payloads, and fixtures.

All models adhere to Pydantic v2, are immutable (frozen), and provide
deterministic JSON serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id(prefix: str = "tr") -> str:
    # Generates a random unique identifier with a designated prefix.
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ReplayMode(str, Enum):
    # Operating modes for TraceReplay execution.

    RECORD = "record"  # Call live AI provider and save fixtures
    REPLAY = "replay"  # Use local fixtures strictly; zero network calls
    AUTO = "auto"  # Replay if fixture exists; record if missing
    PASSTHROUGH = "passthrough"  # Bypass TraceReplay completly (live calls, no record)


class OperationType(str, Enum):
    # Types of AI operations supported by traceReplay.

    CHAT_COMPLETION = "chat_completion"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    TOOL_CALL = "tool_call"
    AGENT_STEP = "agent_step"


class TokenUsage(BaseModel):
    # Token consumption and cost metrics for an interaction.

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)


class ToolCallRecord(BaseModel):
    """Captures a tool or function invocation requested by an LLM."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: _generate_id("call"))
    type: str = Field(default="function")
    function_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    raw_arguments: str | None = Field(default=None)
    result: Any | None = Field(default=None)
    error: str | None = Field(default=None)


class RequestPayload(BaseModel):
    """Normalized payload representing an incoming request to an AI provider."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    operation: OperationType = Field(default=OperationType.CHAT_COMPLETION)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    prompt: str | None = Field(default=None)
    parameters: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] | None = Field(default=None)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    def get_prompt_text(self) -> str | None:
        """Extract the principal prompt or last user message text across providers."""
        if self.prompt is not None:
            return self.prompt
        for msg in reversed(self.messages):
            if msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    # Extract text blocks from list of content parts
                    texts = [
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict) and item.get("type") == "text"
                    ]
                    return " ".join(texts) if texts else None
        return None

    def get_tool_names(self) -> list[str]:
        """Return the names of all declared tools in this request."""
        if not self.tools:
            return []
        names: list[str] = []
        for tool in self.tools:
            if "function" in tool and isinstance(tool["function"], dict):
                name = tool["function"].get("name")
                if name:
                    names.append(name)
            elif "name" in tool:
                names.append(tool["name"])
        return names


class ResponsePayload(BaseModel):
    """Normalized payload representing an AI provider response."""

    model_config = ConfigDict(frozen=True)

    content: str | None = Field(default=None)
    finish_reason: str | None = Field(default="stop")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    is_streaming: bool = Field(default=False)
    stream_chunks: list[dict[str, Any]] | None = Field(default=None)
    raw_response: dict[str, Any] | None = Field(default=None)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class Interaction(BaseModel):
    """Single recorded atomic interaction between an application and an AI provider."""

    model_config = ConfigDict(frozen=True)

    interaction_id: str = Field(default_factory=lambda: _generate_id("int"))
    session_id: str
    index: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=_utc_now)
    duration_ms: float = Field(default=0.0, ge=0.0)
    status: str = Field(default="success")
    request: RequestPayload
    response: ResponsePayload
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionRecord(BaseModel):
    """Root fixture document capturing an entire test run or multi-turn session."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(default="1.0")
    session_id: str = Field(default_factory=lambda: _generate_id("sess"))
    name: str
    test_name: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utc_now)
    interactions: list[Interaction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_interactions(self) -> int:
        """Return the total count of interactions in this session."""
        return len(self.interactions)

    @property
    def total_tokens(self) -> int:
        """Calculate aggregate tokens consumed across all interactions in this session."""
        return sum(item.response.usage.total_tokens for item in self.interactions)

    @property
    def total_duration_ms(self) -> float:
        """Calculate total elapsed execution latency in milliseconds."""
        return sum(item.duration_ms for item in self.interactions)

    def get_interaction(self, index: int) -> Interaction | None:
        """Retrieve interaction by index sequence number."""
        for item in self.interactions:
            if item.index == index:
                return item
        return None

    def get_tool_calls(self) -> list[ToolCallRecord]:
        """Collect all tool calls across all interactions in this session."""
        calls: list[ToolCallRecord] = []
        for item in self.interactions:
            calls.extend(item.response.tool_calls)
        return calls

    def find_interactions(
        self, provider: str | None = None, model: str | None = None
    ) -> list[Interaction]:
        results: list[Interaction] = []
        for item in self.interactions:
            if provider and item.request.provider.lower() != provider.lower():
                continue
            if model and item.request.model.lower() != model.lower():
                continue
            results.append(item)
        return results
