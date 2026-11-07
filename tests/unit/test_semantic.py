"""Unit tests for Semantic Diff & Smart Drift Detection (Feature 4)."""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tracereplay.config import TraceReplayConfig
from tracereplay.core.replayer import Replayer
from tracereplay.core.session import TraceReplaySession
from tracereplay.exceptions import RequestMismatchError, SemanticDriftError
from tracereplay.models import (
    Interaction,
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    SessionRecord,
)
from tracereplay.semantic import (
    DriftAction,
    DriftReport,
    DriftStatus,
    SemanticConfig,
    SemanticDriftRecord,
    SemanticMatcher,
    calculate_semantic_similarity,
    colorize_diff,
    cosine_similarity_vectors,
    generate_inline_token_diff,
    generate_semantic_diff,
    levenshtein_similarity,
    token_cosine_similarity,
    token_jaccard_similarity,
    tokenize_text,
)
from tracereplay.storage.json_storage import JsonStorageEngine


def test_tokenize_text_and_boundaries() -> None:
    """Verify tokenizer breaks text into lowercase words, numbers, and punctuation."""
    assert tokenize_text("") == []
    assert tokenize_text("   \n\t  ") == []

    text = "Hello, world! Answer in 3 steps: 1. Read, 2. Process, 3. Output."
    tokens = tokenize_text(text)
    assert "hello" in tokens
    assert "," in tokens
    assert "3" in tokens
    assert "process" in tokens


def test_cosine_similarity_vectors_math() -> None:
    """Verify numeric vector cosine similarity behaves mathematically."""
    # Identical vectors
    assert cosine_similarity_vectors([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)
    # Parallel vectors with different magnitudes
    assert cosine_similarity_vectors([1.0, 2.0], [2.0, 4.0]) == pytest.approx(1.0)
    # Orthogonal vectors
    assert cosine_similarity_vectors([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    # Zero vectors
    assert cosine_similarity_vectors([0.0, 0.0], [0.0, 0.0]) == 1.0
    assert cosine_similarity_vectors([0.0, 0.0], [1.0, 1.0]) == 0.0

    # Dimension mismatch
    with pytest.raises(ValueError, match="Vector dimension mismatch"):
        cosine_similarity_vectors([1.0, 2.0], [1.0, 2.0, 3.0])


def test_token_cosine_similarity_ngram_metric() -> None:
    """Verify n-gram term frequency cosine similarity between texts."""
    t1 = "You are a helpful customer support assistant."
    t2 = "You are a polite customer support assistant."
    t3 = "Write a python script to calculate fibonacci numbers."

    # Identical
    assert token_cosine_similarity(t1, t1) == 1.0
    assert token_cosine_similarity("", "") == 1.0
    assert token_cosine_similarity(t1, "") == 0.0

    # High similarity between t1 and t2 (shared unigrams and bigrams)
    sim_close = token_cosine_similarity(t1, t2)
    assert 0.70 < sim_close < 1.0

    # Very low similarity between customer support and python script
    sim_far = token_cosine_similarity(t1, t3)
    assert sim_far < 0.20


def test_levenshtein_and_jaccard_similarity() -> None:
    """Verify string ratio and token Jaccard similarity."""
    s1 = "calculate taxes"
    s2 = "calculate tax"
    assert levenshtein_similarity(s1, s1) == 1.0
    assert levenshtein_similarity(s1, s2) > 0.85

    tokens1 = ["user", "login", "auth"]
    tokens2 = ["user", "login", "password"]
    assert token_jaccard_similarity(tokens1, tokens2) == 2.0 / 4.0
    assert token_jaccard_similarity([], []) == 1.0


def test_calculate_semantic_similarity_hybrid_score() -> None:
    """Verify hybrid similarity gives realistic, deterministic confidence scores."""
    p1 = "Analyze quarterly financial statements for Apple Inc."
    p2 = "Please analyze quarterly financial reports for Apple Inc."
    p3 = "Generate a recipe for chocolate chip cookies."

    score_close = calculate_semantic_similarity(p1, p2)
    assert 0.80 <= score_close <= 0.98

    score_divergent = calculate_semantic_similarity(p1, p3)
    assert score_divergent < 0.30


def test_calculate_semantic_similarity_with_custom_embedding_fn() -> None:
    """Verify pluggable embedding function computes vector cosine similarity."""

    # Dummy embedding provider returning fixed 3D vectors
    def dummy_embed(text: str) -> list[float]:
        if "apple" in text.lower():
            return [1.0, 0.9, 0.0]
        return [0.0, 0.1, 1.0]

    sim = calculate_semantic_similarity(
        "Analyze Apple stock",
        "Investigate Apple revenue",
        embedding_fn=dummy_embed,
    )
    assert sim == pytest.approx(1.0)

    sim_diff = calculate_semantic_similarity(
        "Analyze Apple stock",
        "Cook dinner recipe",
        embedding_fn=dummy_embed,
    )
    assert sim_diff < 0.20


def test_generate_inline_token_diff_and_tokens() -> None:
    """Verify inline token-level diff markup and added/removed token extraction."""
    exp = "Please analyze quarterly financial statements"
    act = "Please analyze annual financial records"

    inline_diff, added, removed = generate_inline_token_diff(exp, act)
    assert "[-quarterly-]" in inline_diff
    assert "{+annual+}" in inline_diff
    assert "[-statements-]" in inline_diff
    assert "{+records+}" in inline_diff
    assert "annual" in added
    assert "records" in added
    assert "quarterly" in removed
    assert "statements" in removed


def test_generate_semantic_diff_and_ansi_colorize() -> None:
    """Verify unified diff formatting and ANSI colorization."""
    exp = "Line 1: baseline\nLine 2: data\n"
    act = "Line 1: baseline\nLine 2: modified data\n"

    diff = generate_semantic_diff(exp, act)
    assert "--- Expected (Baseline Prompt)" in diff
    assert "+++ Actual (Incoming Prompt)" in diff
    assert "@@ Similarity:" in diff

    colored = colorize_diff(diff)
    assert "\033[31m" in colored  # red for - or ---
    assert "\033[32m" in colored  # green for + or +++


def test_semantic_matcher_exact_match() -> None:
    """Verify SemanticMatcher recognizes byte-for-byte exact prompts as EXACT_MATCH."""
    matcher = SemanticMatcher(config=SemanticConfig(enabled=True, threshold=0.85))
    req = RequestPayload(
        provider="openai",
        model="gpt-4o",
        prompt="Explain quantum entanglement in 2 sentences.",
    )

    record = matcher.compare_semantic(req, req, step_index=0)
    assert record.status == DriftStatus.EXACT_MATCH
    assert record.similarity_score == 1.0
    assert record.is_match is True


def test_semantic_matcher_drift_within_threshold() -> None:
    """Verify minor prompt phrasing shifts are recognized as SEMANTIC_MATCH."""
    matcher = SemanticMatcher(config=SemanticConfig(enabled=True, threshold=0.75))
    exp = RequestPayload(
        provider="openai",
        model="gpt-4o",
        prompt="Explain quantum entanglement in 2 sentences.",
    )
    act = RequestPayload(
        provider="openai",
        model="gpt-4o",
        prompt="Please explain quantum entanglement in two brief sentences.",
    )

    record = matcher.compare_semantic(exp, act, step_index=0)
    assert record.status == DriftStatus.SEMANTIC_MATCH
    assert record.similarity_score >= 0.75
    assert record.is_match is True
    assert record.diff is not None
    assert len(record.added_tokens) > 0


def test_semantic_matcher_drift_exceeded() -> None:
    """Verify major prompt drift triggers DRIFT_EXCEEDED with is_match=False."""
    matcher = SemanticMatcher(config=SemanticConfig(enabled=True, threshold=0.85))
    exp = RequestPayload(
        provider="openai",
        model="gpt-4o",
        prompt="Explain quantum entanglement in 2 sentences.",
    )
    act = RequestPayload(
        provider="openai",
        model="gpt-4o",
        prompt="Summarize the history of the Roman empire from Augustus to Nero.",
    )

    record = matcher.compare_semantic(exp, act, step_index=0)
    assert record.status == DriftStatus.DRIFT_EXCEEDED
    assert record.similarity_score < 0.50
    assert record.is_match is False


def test_semantic_matcher_structural_mismatch() -> None:
    """Verify model or provider differences trigger STRUCTURAL_MISMATCH."""
    matcher = SemanticMatcher(config=SemanticConfig(enabled=True, match_model=True))
    exp = RequestPayload(
        provider="openai",
        model="gpt-4o",
        prompt="Hello world",
    )
    act = RequestPayload(
        provider="openai",
        model="claude-3-5-sonnet",
        prompt="Hello world",
    )

    record = matcher.compare_semantic(exp, act, step_index=0)
    assert record.status == DriftStatus.STRUCTURAL_MISMATCH
    assert record.similarity_score == 0.0
    assert record.is_match is False
    assert any("Model mismatch" in d for d in record.differences)


def test_semantic_matcher_multimodal_message_flattening() -> None:
    """Verify matcher extracts and flattens multimodal and multi-turn message history."""
    matcher = SemanticMatcher(config=SemanticConfig(enabled=True))
    req = RequestPayload(
        provider="openai",
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a code tutor."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Fix this bug:"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/err.png"}},
                ],
            },
        ],
    )

    extracted = matcher.extract_prompt_text(req)
    assert "[system] You are a code tutor." in extracted
    assert "[user] Fix this bug:" in extracted


def test_replayer_semantic_matching_accepts_drift() -> None:
    """Verify Replayer successfully serves recorded response when prompt drifts within threshold."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = TraceReplayConfig(fixtures_dir=Path(tmp_dir), mode=ReplayMode.REPLAY)
        storage = JsonStorageEngine(config=cfg)

        exp_req = RequestPayload(
            provider="openai",
            model="gpt-4o",
            prompt="Analyze quarterly financial statements for Acme Corp.",
        )
        resp = ResponsePayload(content="Acme Corp reported $10M revenue, 12% YoY growth.")

        session_rec = SessionRecord(
            name="acme_replay",
            interactions=[
                Interaction(
                    session_id="s1",
                    index=0,
                    request=exp_req,
                    response=resp,
                )
            ],
        )
        storage.save(session_rec)

        # Incoming prompt has slight variation
        drifted_req = RequestPayload(
            provider="openai",
            model="gpt-4o",
            prompt="Please analyze quarterly financial reports for Acme Corp.",
        )

        semantic_matcher = SemanticMatcher(
            config=SemanticConfig(enabled=True, threshold=0.80),
            global_config=cfg,
        )

        replayer = Replayer(
            session_name="acme_replay",
            storage=storage,
            config=cfg,
            semantic_matcher=semantic_matcher,
        )

        result_resp = replayer.replay_interaction(drifted_req)
        assert result_resp.content == resp.content
        assert replayer.drift_report.has_drift is True
        assert len(replayer.drift_report.records) == 1
        assert replayer.drift_report.records[0].status == DriftStatus.SEMANTIC_MATCH


def test_replayer_semantic_matching_rejects_exceeded_drift() -> None:
    """Verify Replayer raises SemanticDriftError when prompt drift exceeds threshold."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = TraceReplayConfig(fixtures_dir=Path(tmp_dir), mode=ReplayMode.REPLAY)
        storage = JsonStorageEngine(config=cfg)

        exp_req = RequestPayload(
            provider="openai",
            model="gpt-4o",
            prompt="Analyze quarterly financial statements for Acme Corp.",
        )
        session_rec = SessionRecord(
            name="acme_replay",
            interactions=[
                Interaction(
                    session_id="s1",
                    index=0,
                    request=exp_req,
                    response=ResponsePayload(content="OK"),
                )
            ],
        )
        storage.save(session_rec)

        unrelated_req = RequestPayload(
            provider="openai",
            model="gpt-4o",
            prompt="What is the capital of Australia?",
        )

        semantic_matcher = SemanticMatcher(
            config=SemanticConfig(enabled=True, threshold=0.85),
            global_config=cfg,
        )

        replayer = Replayer(
            session_name="acme_replay",
            storage=storage,
            config=cfg,
            semantic_matcher=semantic_matcher,
        )

        with pytest.raises(SemanticDriftError) as exc_info:
            replayer.replay_interaction(unrelated_req)

        assert exc_info.value.similarity_score < 0.50
        assert exc_info.value.threshold == 0.85
        assert exc_info.value.semantic_diff is not None


def test_replayer_semantic_action_warn_emits_warning() -> None:
    """Verify DriftAction.WARN emits a UserWarning without aborting replay."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = TraceReplayConfig(fixtures_dir=Path(tmp_dir), mode=ReplayMode.REPLAY)
        storage = JsonStorageEngine(config=cfg)

        exp_req = RequestPayload(
            provider="openai",
            model="gpt-4o",
            prompt="Analyze quarterly financial statements for Acme Corp.",
        )
        session_rec = SessionRecord(
            name="acme_warn",
            interactions=[
                Interaction(
                    session_id="s1",
                    index=0,
                    request=exp_req,
                    response=ResponsePayload(content="Financial Summary"),
                )
            ],
        )
        storage.save(session_rec)

        drifted_req = RequestPayload(
            provider="openai",
            model="gpt-4o",
            prompt="Please analyze quarterly financial reports for Acme Corp.",
        )

        semantic_matcher = SemanticMatcher(
            config=SemanticConfig(enabled=True, threshold=0.80, action=DriftAction.WARN),
            global_config=cfg,
        )

        replayer = Replayer(
            session_name="acme_warn",
            storage=storage,
            config=cfg,
            semantic_matcher=semantic_matcher,
        )

        with pytest.warns(UserWarning, match=r"\[TraceReplay Drift\] Prompt drift detected"):
            resp = replayer.replay_interaction(drifted_req)
            assert resp.content == "Financial Summary"


def test_replayer_exact_mismatch_includes_semantic_drift_hint() -> None:
    """Verify that when semantic matching is off, RequestMismatchError suggests threshold."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = TraceReplayConfig(fixtures_dir=Path(tmp_dir), mode=ReplayMode.REPLAY)
        storage = JsonStorageEngine(config=cfg)

        exp_req = RequestPayload(
            provider="openai",
            model="gpt-4o",
            prompt="Analyze quarterly financial statements for Acme Corp.",
        )
        session_rec = SessionRecord(
            name="acme_exact",
            interactions=[
                Interaction(
                    session_id="s1",
                    index=0,
                    request=exp_req,
                    response=ResponsePayload(content="Result"),
                )
            ],
        )
        storage.save(session_rec)

        drifted_req = RequestPayload(
            provider="openai",
            model="gpt-4o",
            prompt="Please analyze quarterly financial reports for Acme Corp.",
        )

        replayer = Replayer(
            session_name="acme_exact",
            storage=storage,
            config=cfg,
            semantic_matcher=None,  # Disabled
        )

        with pytest.raises(RequestMismatchError) as exc_info:
            replayer.replay_interaction(drifted_req)

        err_msg = str(exc_info.value)
        assert "[Hint] Prompts are" in err_msg
        assert "Enable semantic matching" in err_msg


def test_drift_report_summary_text_and_to_dict() -> None:
    """Verify DriftReport generates formatted ASCII summary table and JSON dict."""
    record1 = SemanticDriftRecord(
        step_index=0,
        similarity_score=1.0,
        threshold=0.85,
        status=DriftStatus.EXACT_MATCH,
    )
    record2 = SemanticDriftRecord(
        step_index=1,
        similarity_score=0.91,
        threshold=0.85,
        status=DriftStatus.SEMANTIC_MATCH,
        added_tokens=["annual"],
        removed_tokens=["quarterly"],
    )

    report = DriftReport(records=[record1, record2])
    assert report.total_replays == 2
    assert report.has_drift is True
    assert report.has_violations is False
    assert report.min_similarity == 0.91
    assert report.average_similarity == pytest.approx(0.955)

    summary = report.summary_text()
    assert "TraceReplay Semantic Drift Report" in summary
    assert "91.00%" in summary
    assert "+1 / -1" in summary

    d = report.to_dict()
    assert d["total_replays"] == 2
    assert d["has_drift"] is True
    assert len(d["records"]) == 2


def test_trace_replay_session_semantic_properties() -> None:
    """Verify TraceReplaySession exposes drift_report and has_semantic_drift properties."""
    sess = TraceReplaySession(
        name="test_sess_semantic",
        mode=ReplayMode.PASSTHROUGH,
        semantic_matching=True,
        semantic_threshold=0.88,
    )
    assert sess.semantic_matcher is not None
    assert sess.semantic_config is not None
    assert sess.semantic_config.threshold == 0.88
    assert sess.has_semantic_drift is False
    assert sess.drift_report.total_replays == 0


def test_pytest_marker_semantic_resolution() -> None:
    """Verify pytest plugin resolves semantic marker parameters into TraceReplaySession."""
    from tracereplay.pytest_plugin import create_tracereplay_session

    req = MagicMock(spec=pytest.FixtureRequest)
    req.config.getoption.return_value = False
    req.node.module.__name__ = "test_mod"
    req.node.name = "test_semantic_plugin"
    del req.node.callspec

    class DummyMarker:
        kwargs = {
            "fixture": "custom_sem_fixture",
            "mode": "replay",
            "semantic_matching": True,
            "semantic_threshold": 0.82,
            "semantic_action": "warn",
        }
        args = ()

    req.node.get_closest_marker.return_value = DummyMarker()

    cfg = TraceReplayConfig()
    generator = create_tracereplay_session(req, cfg)
    sess = next(generator)

    assert sess.name == "custom_sem_fixture"
    assert sess.semantic_matcher is not None
    assert sess.semantic_config is not None
    assert sess.semantic_config.threshold == 0.82
    assert sess.semantic_config.action == DriftAction.WARN

    with contextlib.suppress(StopIteration):
        next(generator)
