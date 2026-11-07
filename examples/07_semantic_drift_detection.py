"""TraceReplay Feature 4: Semantic Diff & Smart Drift Detection.

Demonstrates fuzzy and semantic request matching, visual drift diagnostics,
and prompt evolution tracking across recorded replay sessions.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from tracereplay.config import TraceReplayConfig
from tracereplay.core.session import TraceReplaySession
from tracereplay.exceptions import RequestMismatchError, SemanticDriftError
from tracereplay.models import ReplayMode, RequestPayload, ResponsePayload
from tracereplay.semantic import (
    colorize_diff,
    generate_inline_token_diff,
    generate_semantic_diff,
)


def main() -> None:
    print("=" * 65)
    print(" TraceReplay Demo: Semantic Diff & Smart Drift Detection")
    print("=" * 65)

    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = TraceReplayConfig(fixtures_dir=Path(tmp_dir))
        session_name = "customer_service_agent"

        # -------------------------------------------------------------
        # Scenario 1: Record Baseline Session
        # -------------------------------------------------------------
        print("\n[Scenario 1] Recording baseline LLM interaction...")
        baseline_prompt = "You are a customer service assistant. Explain our 30-day refund policy."
        baseline_reply = (
            "We offer a 100% money-back guarantee within 30 days of purchase with receipt."
        )

        with TraceReplaySession(name=session_name, mode=ReplayMode.RECORD, config=cfg) as sess:
            # Emulate recording
            assert sess.recorder is not None
            sess.recorder.record_interaction(
                RequestPayload(
                    provider="openai",
                    model="gpt-4o",
                    prompt=baseline_prompt,
                ),
                ResponsePayload(content=baseline_reply),
            )
        print("  Recorded baseline prompt successfully.")

        # -------------------------------------------------------------
        # Scenario 2: Exact Matching Rejects Evolved Prompt with Hint
        # -------------------------------------------------------------
        evolved_prompt = (
            "You are a polite customer support assistant. "
            "Explain our 30-day refund policy concisely."
        )
        print("\n[Scenario 2] Attempting exact replay with drifted prompt...")
        try:
            with TraceReplaySession(
                name=session_name,
                mode=ReplayMode.REPLAY,
                config=cfg,
                semantic_matching=False,
            ) as sess:
                assert sess.replayer is not None
                sess.replayer.replay_interaction(
                    RequestPayload(
                        provider="openai",
                        model="gpt-4o",
                        prompt=evolved_prompt,
                    )
                )
        except RequestMismatchError as err:
            print("  [EXACT REPLAY REJECTED (Expected)]")
            first_line = str(err).splitlines()[0]
            print(f"  Reason: {first_line}")
            # Show the intelligent hint that TraceReplay added
            for line in str(err).splitlines():
                if "[Hint]" in line or "Enable semantic matching" in line:
                    print(f"  {line}")

        # -------------------------------------------------------------
        # Scenario 3: Semantic Matching Accepts Drift & Shows Visual Diff
        # -------------------------------------------------------------
        print("\n[Scenario 3] Replaying with semantic_matching=True (threshold=0.80)...")
        with TraceReplaySession(
            name=session_name,
            mode=ReplayMode.REPLAY,
            config=cfg,
            semantic_matching=True,
            semantic_threshold=0.80,
        ) as sess:
            assert sess.replayer is not None
            resp = sess.replayer.replay_interaction(
                RequestPayload(
                    provider="openai",
                    model="gpt-4o",
                    prompt=evolved_prompt,
                )
            )
            print("  [SEMANTIC REPLAY SUCCEEDED!]")
            print(f"  Deterministic Response: '{resp.content}'")

            report = sess.drift_report
            record = report.records[0]
            print(f"  Similarity Score:      {record.similarity_score:.2%}")
            print(f"  Token Cosine Sim:      {record.token_similarity:.2%}")
            print(f"  Sequence Edit Ratio:   {record.char_similarity:.2%}")

            inline, added, removed = generate_inline_token_diff(baseline_prompt, evolved_prompt)
            print("\n  Inline Word-Level Diff:")
            print(f"    {inline}")
            print(f"    Added words:   {added}")
            print(f"    Removed words: {removed}")

            diff = generate_semantic_diff(baseline_prompt, evolved_prompt)
            print("\n  Unified Semantic Diff:")
            print(colorize_diff(diff))

        # -------------------------------------------------------------
        # Scenario 4: Divergent Prompt Exceeding Threshold
        # -------------------------------------------------------------
        divergent_prompt = "Write a Python script to simulate quantum mechanics equations."
        print("\n[Scenario 4] Testing divergent prompt with semantic_matching=True...")
        try:
            with TraceReplaySession(
                name=session_name,
                mode=ReplayMode.REPLAY,
                config=cfg,
                semantic_matching=True,
                semantic_threshold=0.85,
            ) as sess:
                assert sess.replayer is not None
                sess.replayer.replay_interaction(
                    RequestPayload(
                        provider="openai",
                        model="gpt-4o",
                        prompt=divergent_prompt,
                    )
                )
        except SemanticDriftError as err:
            print("  [BLOCKED BY SEMANTIC GUARD]")
            print(
                f"  Similarity {err.similarity_score:.2%} was below threshold {err.threshold:.2%}."
            )

        # -------------------------------------------------------------
        # Scenario 5: Cumulative Drift Report
        # -------------------------------------------------------------
        print("\n[Scenario 5] Cumulative Drift Report:")
        print(report.summary_text())

    print("\n" + "=" * 65)
    print(" Semantic Diff & Drift Detection demonstration completed!")
    print("=" * 65)


if __name__ == "__main__":
    main()
