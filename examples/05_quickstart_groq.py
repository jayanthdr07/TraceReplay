"""Example 05: Groq LPU Hybrid Quickstart (Real & Simulated).

Demonstrates TraceReplay with Groq high-speed LPU inference:
1. Live Mode: If `GROQ_API_KEY` is set in your environment:
   - Uses the official `groq.Groq()` client.
   - Automatically intercepts with `tracereplay.patch(client)`.
   - In RECORD mode: Queries live Groq LPU (e.g. `llama-3.1-8b-instant`).
   - In REPLAY mode: Replays in ~3ms with ZERO network requests to Groq!
2. Simulated Mode: If `GROQ_API_KEY` is NOT set, gracefully falls back to a
   lightweight simulation so it never crashes.

To test with your live Groq API key:
    $env:GROQ_API_KEY="gsk_your_key_here"
    python examples/05_quickstart_groq.py
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

# Detect if live Groq API key is present
_raw_key = os.environ.get("GROQ_API_KEY", "")
HAS_GROQ_KEY = bool(_raw_key and not _raw_key.startswith("placeholder"))


def run_with_real_groq(session_name: str, config: TraceReplayConfig, prompt: str) -> None:
    """Demonstrates TraceReplay with the genuine Groq Python SDK."""
    from groq import Groq

    client = Groq()

    # Dynamically select an available active model for this Groq account
    model_name = "llama-3.1-8b-instant"
    try:
        model_list = [m.id for m in client.models.list().data if "llama" in m.id.lower()]
        if model_list:
            if "llama-3.1-8b-instant" in model_list:
                model_name = "llama-3.1-8b-instant"
            else:
                model_name = model_list[0]
    except Exception:
        model_name = "llama-3.1-8b-instant"

    # Intercept the Groq client instance
    patch(client, provider="groq")

    print("\n[Phase 1] Executing with real Groq client in RECORD mode...")
    start_rec = time.perf_counter()
    with session(session_name, mode=ReplayMode.RECORD, config=config):
        response_rec = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        content_rec = response_rec.choices[0].message.content or ""
    rec_time = (time.perf_counter() - start_rec) * 1000.0

    print(f"  Live Groq Model: {model_name}")
    print(f"  Live Response:   {content_rec.strip()}")
    print(f"  Live Time:       {rec_time:.2f} ms")
    print(f"  Saved Fixture:   {(config.fixtures_dir / f'{session_name}.json').resolve()}")

    print("\n[Phase 2] Executing with real Groq client in REPLAY mode (Zero Groq API calls)...")
    start_rep = time.perf_counter()
    with session(session_name, mode=ReplayMode.REPLAY, config=config):
        response_rep = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        content_rep = response_rep.choices[0].message.content or ""
    rep_time = (time.perf_counter() - start_rep) * 1000.0

    print(f"  Replayed Text:   {content_rep.strip()}")
    print(f"  Replay Time:     {rep_time:.2f} ms (Deterministic local fixture)")

    unpatch(client)
    assert content_rep == content_rec, "Replayed response must match recorded response"


def run_with_simulated_groq(session_name: str, config: TraceReplayConfig, prompt: str) -> None:
    """Demonstrates TraceReplay in simulated mode (no API key required)."""
    live_calls = 0

    def chat_call(p: str, sess: Any) -> str:
        nonlocal live_calls
        req = RequestPayload(provider="groq", model="llama-3.1-8b-instant", prompt=p)

        if sess.mode == ReplayMode.RECORD:
            live_calls += 1
            time.sleep(0.08)  # Simulate ultra-fast Groq LPU latency
            resp = ResponsePayload(
                content="Groq LPU response: Blazing-fast inference recorded successfully!",
            )
            sess.recorder.record_interaction(req, resp)
            return resp.content or ""
        elif sess.mode == ReplayMode.REPLAY:
            resp = sess.replayer.replay_interaction(req)
            return resp.content or ""
        return ""

    print("\n[Phase 1] Executing in RECORD mode (simulating Groq LPU call)...")
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
    session_name = "groq_quickstart"
    user_prompt = "What makes Groq LPUs unique for AI inference?"

    print("=" * 65)
    print("TraceReplay - Example 05: Groq LPU Hybrid Quickstart")
    print("=" * 65)

    if HAS_GROQ_KEY:
        key_preview = os.environ["GROQ_API_KEY"][:8] + "..."
        print(f"[MODE] Live Groq API Mode (GROQ_API_KEY detected: {key_preview})")
        run_with_real_groq(session_name, config, user_prompt)
    else:
        print("[MODE] Simulated Mode (GROQ_API_KEY not set).")
        print("       (Tip: Set GROQ_API_KEY=gsk_... in PowerShell to test live Groq)")
        run_with_simulated_groq(session_name, config, user_prompt)

    print("\n[SUCCESS] Groq demonstration completed deterministically!\n")


if __name__ == "__main__":
    main()
