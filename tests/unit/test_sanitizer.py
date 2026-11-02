"""Unit tests for the sensitive data sanitizer engine."""

from __future__ import annotations

from tracereplay.config import TraceReplayConfig
from tracereplay.models import (
    Interaction,
    OperationType,
    RequestPayload,
    ResponsePayload,
    SessionRecord,
    TokenUsage,
)
from tracereplay.sanitizer import Sanitizer, sanitize_data


def test_sanitize_string_with_api_keys() -> None:
    """Verify that OpenAI and Bearer style keys in strings are masked."""
    sanitizer = Sanitizer()
    raw = "My secret key is sk-1234567890abcdef1234567890 and Bearer eyJhbGciOiJIUzI1NiJ9.test"
    result = sanitizer.sanitize_string(raw)
    assert "sk-1234567890abcdef1234567890" not in result
    assert "Bearer eyJhbGciOiJIUzI1NiJ9.test" not in result
    assert "[REDACTED]" in result


def test_sanitize_dictionary_keys() -> None:
    """Verify that dictionary keys matching redact_keys have values masked."""
    data = {
        "model": "gpt-4o",
        "authorization": "Bearer secret_token_123",
        "api-key": "secret_key_456",
        "nested": {
            "x-api-key": "hidden_key_789",
            "normal_field": "visible_value",
        },
    }
    result = sanitize_data(data)
    assert result["authorization"] == "[REDACTED]"
    assert result["api-key"] == "[REDACTED]"
    assert result["nested"]["x-api-key"] == "[REDACTED]"
    assert result["nested"]["normal_field"] == "visible_value"


def test_sanitize_custom_regex_pattern() -> None:
    """Verify custom regex patterns mask sensitive domain data (e.g. emails)."""
    cfg = TraceReplayConfig(redact_patterns=[r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"])
    sanitizer = Sanitizer(config=cfg)
    text = "Contact user at john.doe@example.com for info"
    result = sanitizer.sanitize_string(text)
    assert "john.doe@example.com" not in result
    assert result == "Contact user at [REDACTED] for info"


def test_sanitize_full_session_model() -> None:
    """Verify that an entire SessionRecord has its credentials scrubbed."""
    req = RequestPayload(
        provider="openai",
        model="gpt-4o",
        operation=OperationType.CHAT_COMPLETION,
        messages=[{"role": "user", "content": "Here is my key: sk-abcdef1234567890abcdef"}],
        parameters={"authorization": "Bearer secret_token"},
    )
    res = ResponsePayload(
        content="Received key",
        usage=TokenUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
    )
    interaction = Interaction(
        session_id="sess_sec",
        index=0,
        request=req,
        response=res,
        metadata={"api-key": "secret_in_metadata"},
    )
    session = SessionRecord(name="test_secret_session", interactions=[interaction])

    sanitizer = Sanitizer()
    clean_session = sanitizer.sanitize_session(session)

    # Assert secrets were scrubbed
    clean_req = clean_session.interactions[0].request
    assert "sk-abcdef1234567890abcdef" not in clean_req.messages[0]["content"]
    assert "[REDACTED]" in clean_req.messages[0]["content"]
    assert clean_req.parameters["authorization"] == "[REDACTED]"
    assert clean_session.interactions[0].metadata["api-key"] == "[REDACTED]"
