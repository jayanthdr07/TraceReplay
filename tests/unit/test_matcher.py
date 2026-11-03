"""Unit tests for the request matcher, normalizer, and diff engine."""

from __future__ import annotations

import pytest

from tracereplay.config import TraceReplayConfig
from tracereplay.exceptions import RequestMismatchError
from tracereplay.matcher import (
    RequestMatcher,
    RequestNormalizer,
    compute_request_hash,
    generate_diff,
)
from tracereplay.models import (
    Interaction,
    RequestPayload,
    ResponsePayload,
    SessionRecord,
)


def test_normalizer_text_and_line_endings() -> None:
    """Verify that CRLF is converted to LF and boundary whitespace is trimmed."""
    normalizer = RequestNormalizer()
    text = "  Hello world\r\nLine 2\r\n  "
    assert normalizer.normalize_text(text) == "Hello world\nLine 2"
    assert normalizer.normalize_text(None) is None


def test_normalizer_multimodal_blocks() -> None:
    """Verify normalization of multimodal / structured content blocks."""
    normalizer = RequestNormalizer()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "  What is in this image? \r\n "},
                {"type": "image_url", "image_url": {"url": "https://example.com/pic.png"}},
            ],
        }
    ]
    norm_msgs = [normalizer.normalize_message(messages) for message in messages]
    assert norm_msgs[0][0]["content"][0]["text"] == "What is in this image?"


def test_normalizer_ignored_parameters() -> None:
    """Verify that parameters in config.ignored_parameters are stripped."""
    cfg = TraceReplayConfig(ignored_parameters=["seed", "user", "timestamp"])
    normalizer = RequestNormalizer(config=cfg)
    params = {
        "temperature": 0.7,
        "max_tokens": 150,
        "seed": 42,
        "user": "user_abc123",
        "timestamp": "2026-11-03T18:00:00Z",
    }
    filtered = normalizer.filter_parameters(params)
    assert "temperature" in filtered
    assert "max_tokens" in filtered
    assert "seed" not in filtered
    assert "user" not in filtered
    assert "timestamp" not in filtered


def test_compute_request_hash_determinism() -> None:
    """Verify that two identical requests produce the exact same SHA-256 hash."""
    req1 = RequestPayload(
        provider="openai",
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
        parameters={"temperature": 0.5, "seed": 100},
    )
    req2 = RequestPayload(
        provider="OPENAI",  # Case insensitive
        model="GPT-4O",  # Case insensitive
        messages=[{"role": "user", "content": "Hello"}],
        parameters={"temperature": 0.5, "seed": 999},  # Ignored parameter
    )
    hash1 = compute_request_hash(req1)
    hash2 = compute_request_hash(req2)
    assert hash1 == hash2


def test_matcher_exact_match_success() -> None:
    """Verify that matching identical requests returns is_match=True."""
    matcher = RequestMatcher()
    expected = RequestPayload(
        provider="anthropic",
        model="claude-3-5-sonnet",
        messages=[{"role": "user", "content": "Summarize this article"}],
        parameters={"max_tokens": 200},
    )
    actual = RequestPayload(
        provider="anthropic",
        model="claude-3-5-sonnet",
        messages=[{"role": "user", "content": "Summarize this article"}],
        parameters={"max_tokens": 200},
    )
    res = matcher.compare(expected, actual)
    assert res.is_match is True
    assert len(res.differences) == 0
    assert res.diff is None


def test_matcher_model_mismatch_generates_diff() -> None:
    """Verify that model differences return is_match=False and generate unified diff."""
    matcher = RequestMatcher()
    expected = RequestPayload(provider="openai", model="gpt-4o")
    actual = RequestPayload(provider="openai", model="gpt-3.5-turbo")

    res = matcher.compare(expected, actual)
    assert res.is_match is False
    assert any("Model mismatch" in d for d in res.differences)
    assert res.diff is not None
    assert '-  "model": "gpt-4o",' in res.diff
    assert '+  "model": "gpt-3.5-turbo",' in res.diff


def test_matcher_tools_order_independence() -> None:
    """Verify that declared tools match regardless of list declaration order."""
    matcher = RequestMatcher()
    tool_a = {"type": "function", "function": {"name": "search"}}
    tool_b = {"type": "function", "function": {"name": "calculator"}}

    req1 = RequestPayload(provider="openai", model="gpt-4o", tools=[tool_a, tool_b])
    req2 = RequestPayload(provider="openai", model="gpt-4o", tools=[tool_b, tool_a])

    res = matcher.compare(req1, req2)
    assert res.is_match is True


def test_matcher_find_match_sequential() -> None:
    """Verify sequential matching in multi-turn sessions."""
    matcher = RequestMatcher(config=TraceReplayConfig(strict_ordering=True))

    turn0_req = RequestPayload(provider="openai", model="gpt-4o", prompt="Turn 0")
    turn1_req = RequestPayload(provider="openai", model="gpt-4o", prompt="Turn 1")

    session = SessionRecord(
        name="test_seq",
        interactions=[
            Interaction(
                session_id="s1",
                index=0,
                request=turn0_req,
                response=ResponsePayload(content="Ans 0"),
            ),
            Interaction(
                session_id="s1",
                index=1,
                request=turn1_req,
                response=ResponsePayload(content="Ans 1"),
            ),
        ],
    )

    # 1. First request should match Turn 0
    matched, res = matcher.find_match(turn0_req, session, start_index=0)
    assert matched is not None
    assert matched.index == 0
    assert res.is_match is True

    # 2. Second request should match Turn 1
    matched, res = matcher.find_match(turn1_req, session, start_index=1)
    assert matched is not None
    assert matched.index == 1
    assert res.is_match is True

    # 3. If sequential step sends Turn 0 again at index 1, it must fail
    matched, res = matcher.find_match(turn0_req, session, start_index=1)
    assert matched is None
    assert res.is_match is False
    assert any("Prompt text does not match" in d for d in res.differences)


def test_matcher_find_match_unordered() -> None:
    """Verify out-of-order matching when strict_ordering is disabled."""
    matcher = RequestMatcher(config=TraceReplayConfig(strict_ordering=False))

    req_a = RequestPayload(provider="openai", model="gpt-4o", prompt="Query A")
    req_b = RequestPayload(provider="openai", model="gpt-4o", prompt="Query B")

    session = SessionRecord(
        name="test_unordered",
        interactions=[
            Interaction(
                session_id="s1",
                index=0,
                request=req_a,
                response=ResponsePayload(content="A"),
            ),
            Interaction(
                session_id="s1",
                index=1,
                request=req_b,
                response=ResponsePayload(content="B"),
            ),
        ],
    )

    matched, res = matcher.find_match(req_b, session, start_index=0)
    assert matched is not None
    assert matched.index == 1
    assert res.is_match is True


def test_matcher_validate_or_raise() -> None:
    """Verify validate_or_raise raises informative RequestMismatchError on difference."""
    matcher = RequestMatcher()
    expected = RequestPayload(provider="openai", model="gpt-4o", prompt="Hello")
    actual = RequestPayload(provider="openai", model="gpt-4o", prompt="Goodbye")

    with pytest.raises(RequestMismatchError) as exc_info:
        matcher.validate_or_raise(expected, actual, interaction_index=2)

    assert "Request mismatch at interaction index 2" in str(exc_info.value)
    assert exc_info.value.expected is not None
    assert exc_info.value.actual is not None
    assert exc_info.value.diff is not None


def test_generate_diff_utility() -> None:
    """Verify diff generator outputs standard unified diff format."""
    obj1 = {"count": 1, "key": "value1"}
    obj2 = {"count": 1, "key": "value2"}
    diff = generate_diff(obj1, obj2)
    assert "--- Expected (Fixture)" in diff
    assert "+++ Actual (Request)" in diff
    assert '-  "key": "value1"' in diff
    assert '+  "key": "value2"' in diff
