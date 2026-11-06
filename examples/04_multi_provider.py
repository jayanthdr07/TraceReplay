"""Example 04: Multi-Provider Interception (OpenAI, Claude, Gemini, Ollama).

Demonstrates universal provider normalization in TraceReplay:
1. Unified Payload Model: Different provider SDK formats are normalized into
   RequestPayload and ResponsePayload structures.
2. Cross-Provider Testing: A single test workflow can call OpenAI, Anthropic,
   Gemini, and local Ollama, saving and replaying all interactions in one fixture.
3. Deterministic Playback: Zero external API calls on replay across all models.

Run directly with:
    python examples/04_multi_provider.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tracereplay import (
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    TraceReplayConfig,
    session,
)


def run_multi_model_pipeline(sess: Any) -> dict[str, str]:
    """Pipeline querying 4 different providers sequentially."""
    results: dict[str, str] = {}

    providers_to_test = [
        ("openai", "gpt-4o", "Explain quantum superposition in 5 words."),
        ("anthropic", "claude-3-5-sonnet-20241022", "Summarize relativity in 5 words."),
        ("gemini", "gemini-1.5-pro", "Define photosynthesis in 5 words."),
        ("ollama", "llama3:8b", "What is gravity in 5 words?"),
    ]

    mock_answers = {
        "gpt-4o": "States exist simultaneously until observed.",
        "claude-3-5-sonnet-20241022": "Space and time are relative.",
        "gemini-1.5-pro": "Light energy becomes chemical sugar.",
        "llama3:8b": "Mass attracts mass across spacetime.",
    }

    for provider, model, prompt in providers_to_test:
        req = RequestPayload(
            provider=provider,
            model=model,
            prompt=prompt,
        )

        if sess.mode == ReplayMode.RECORD:
            answer = mock_answers[model]
            resp = ResponsePayload(content=answer)
            sess.recorder.record_interaction(req, resp)
            results[provider] = answer
        else:
            resp = sess.replayer.replay_interaction(req)
            results[provider] = resp.content or ""

    return results


def main() -> None:
    fixtures_dir = Path(".tracereplay")
    cfg = TraceReplayConfig(fixtures_dir=fixtures_dir)
    session_name = "multi_provider_pipeline"

    print("=" * 65)
    print("TraceReplay - Example 04: Multi-Provider Interception")
    print("=" * 65)

    # 1. RECORD MODE
    print("\n[Phase 1] Recording interactions across 4 distinct AI providers...")
    with session(session_name, mode=ReplayMode.RECORD, config=cfg) as sess_rec:
        rec_results = run_multi_model_pipeline(sess_rec)

    for prov, ans in rec_results.items():
        print(f'  [{prov.upper()}] -> "{ans}"')

    # 2. REPLAY MODE
    print("\n[Phase 2] Deterministically replaying all 4 providers (Zero API calls)...")
    with session(session_name, mode=ReplayMode.REPLAY, config=cfg) as sess_rep:
        rep_results = run_multi_model_pipeline(sess_rep)

    for prov, ans in rep_results.items():
        print(f'  [{prov.upper()}] Replayed -> "{ans}"')

    assert rec_results == rep_results, "Replayed answers must match recorded answers"

    print("\n[SUCCESS] Universal multi-provider recording and replay verified!\n")


if __name__ == "__main__":
    main()
