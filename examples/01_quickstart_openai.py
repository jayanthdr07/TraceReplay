"""Example 01: Hybrid Quickstart OpenAI Record & Deterministic Replay.

HYBRID DEMO:
1. Live Mode: If `OPENAI_API_KEY` is set in your environment, this script uses the
   real OpenAI SDK (`openai.OpenAI()`) and patches it with `tracereplay.patch(client)`.
   - In RECORD mode: Calls OpenAI, burns API tokens once, and records the fixture.
   - In REPLAY mode: Intercepts `client.chat.completions.create()`, making ZERO
     network requests and replaying the recorded response in milliseconds.
2. Simulated Mode: If `OPENAI_API_KEY` is NOT detected, it gracefully falls back to
   a lightweight simulated client so any developer can run it with zero setup.

Run directly with:
    python examples/01_quickstart_openai.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tracereplay import (
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    TraceReplayConfig,
    patch,
    session,
    unpatch,
)

# Detect if live OpenAI key is configured
_raw_key = os.environ.get("OPENAI_API_KEY", "")
HAS_LIVE_KEY = bool(_raw_key and not _raw_key.startswith("placeholder"))


def run_with_real_openai(session_name: str, config: TraceReplayConfig, prompt: str) -> None:
    """Demonstrates TraceReplay with the genuine OpenAI Python SDK."""
    import openai

    client = openai.OpenAI()
    # Enable TraceReplay's automatic client interception on the client instance
    patch(client)

    print("\n[Phase 1] Executing with real OpenAI client in RECORD mode...")
    start_rec = time.perf_counter()
    with session(session_name, mode=ReplayMode.RECORD, config=config):
        response_rec = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        content_rec = response_rec.choices[0].message.content or ""
    rec_time = (time.perf_counter() - start_rec) * 1000.0

    print("  Live Model:     gpt-4o-mini")
    print(f"  Live Response:  {content_rec}")
    print(f"  Time Elapsed:   {rec_time:.2f} ms")
    print(f"  Saved Fixture:  {(config.fixtures_dir / f'{session_name}.json').resolve()}")

    print("\n[Phase 2] Executing with real OpenAI client in REPLAY mode (Zero network calls)...")
    start_rep = time.perf_counter()
    with session(session_name, mode=ReplayMode.REPLAY, config=config):
        response_rep = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        content_rep = response_rep.choices[0].message.content or ""
    rep_time = (time.perf_counter() - start_rep) * 1000.0

    print(f"  Replayed Text:  {content_rep}")
    print(f"  Time Elapsed:   {rep_time:.2f} ms (Instant local replay from fixture)")

    unpatch(client)
    assert content_rep == content_rec, "Replayed text must match recorded text"


def run_with_simulated_client(session_name: str, config: TraceReplayConfig, prompt: str) -> None:
    """Demonstrates TraceReplay in simulated mode (no API key required)."""
    live_calls = 0

    def chat_call(p: str, sess: Any) -> str:
        nonlocal live_calls
        req = RequestPayload(provider="openai", model="gpt-4o", prompt=p)

        if sess.mode == ReplayMode.RECORD:
            live_calls += 1
            time.sleep(0.1)  # Simulate network latency
            resp = ResponsePayload(
                content="Hello! As an AI model (gpt-4o), I am here to help.",
            )
            sess.recorder.record_interaction(req, resp)
            return resp.content or ""
        elif sess.mode == ReplayMode.REPLAY:
            resp = sess.replayer.replay_interaction(req)
            return resp.content or ""
        return ""

    print("\n[Phase 1] Executing in RECORD mode...")
    start_rec = time.perf_counter()
    with session(session_name, mode=ReplayMode.RECORD, config=config) as sess_rec:
        text_rec = chat_call(prompt, sess_rec)
    rec_time = (time.perf_counter() - start_rec) * 1000.0

    print(f"  Prompt:        {prompt}")
    print(f"  Response:      {text_rec}")
    print(f"  Live Calls:    {live_calls}")
    print(f"  Time Elapsed:  {rec_time:.2f} ms")
    print(f"  Saved Fixture: {(config.fixtures_dir / f'{session_name}.json').resolve()}")

    print("\n[Phase 2] Executing in REPLAY mode (Zero network traffic)...")
    start_rep = time.perf_counter()
    with session(session_name, mode=ReplayMode.REPLAY, config=config) as sess_rep:
        text_rep = chat_call(prompt, sess_rep)
    rep_time = (time.perf_counter() - start_rep) * 1000.0

    print(f"  Replayed Text: {text_rep}")
    print(f"  Live Calls:    {live_calls} (Unchanged - zero live calls!)")
    print(f"  Time Elapsed:  {rep_time:.2f} ms (Instant local replay)")

    assert text_rep == text_rec
    assert live_calls == 1


def main() -> None:
    fixtures_dir = Path(".tracereplay")
    config = TraceReplayConfig(fixtures_dir=fixtures_dir)
    session_name = "quickstart_demo"
    user_prompt = "What is TraceReplay?"

    print("=" * 65)
    print("TraceReplay - Example 01: Hybrid Quickstart (Real & Simulated)")
    print("=" * 65)

    if HAS_LIVE_KEY:
        key_preview = os.environ["OPENAI_API_KEY"][:7] + "..."
        print(f"[MODE] Live OpenAI Mode (OPENAI_API_KEY detected: {key_preview})")
        run_with_real_openai(session_name, config, user_prompt)
    else:
        print("[MODE] Simulated Zero-Setup Mode (OPENAI_API_KEY not set).")
        print("       (Tip: To test against live OpenAI, set OPENAI_API_KEY=your_key)")
        run_with_simulated_client(session_name, config, user_prompt)

    print("\n[SUCCESS] Quickstart demonstration completed deterministically!\n")


if __name__ == "__main__":
    main()
