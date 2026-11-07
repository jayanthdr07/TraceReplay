"""Example 06: Token, Cost & Latency Guardrails (Budget Caps & Hard Stop Enforcers).

Demonstrates:
1. Hard financial stops: Preventing runaway cost loops with max_cost_usd.
2. Token usage boundaries: Restricting prompt and completion token consumption.
3. Offline regression catching: Verifying token budgets in REPLAY mode with zero network calls.
4. Comprehensive audit reports: Printing cost breakdown by model and execution duration.

Run directly with:
    python examples/06_token_cost_guardrails.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from tracereplay import (
    CostBudgetExceededError,
    ReplayMode,
    TokenBudgetExceededError,
    TraceReplayConfig,
    guardrails,
    patch,
    session,
    unpatch,
)

# ---------------------------------------------------------------------------
# Lightweight client mock for standalone demonstration
# ---------------------------------------------------------------------------


class MockCompletions:
    def create(self, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", "gpt-4o")
        msgs = kwargs.get("messages", [])
        content = msgs[0]["content"] if msgs else "Hello"

        # Simulates 4,000 prompt tokens and 1,000 completion tokens
        p_tok = 4000
        c_tok = 1000
        return {
            "id": "chatcmpl_guardrail_demo",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"Synthesized analysis for '{content}'.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "total_tokens": p_tok + c_tok,
            },
        }


class MockClient:
    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": MockCompletions()})()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        demo_dir = Path(tmp_dir)
        cfg = TraceReplayConfig(fixtures_dir=demo_dir)

        raw_client = MockClient()
        client = patch(raw_client, provider="openai")

        print("\n" + "=" * 65)
        print(" TraceReplay Guardrails Demo (Feature 3: Budget Caps & Hard Stops)")
        print("=" * 65)

        # -------------------------------------------------------------------
        # Scenario 1: Successful Session within Budget with Real-Time Audit
        # -------------------------------------------------------------------
        print("\n[Scenario 1] Executing session within safety budget ($0.05 USD)...")

        safe_budget = guardrails.cost_budget(max_cost_usd=0.05)

        with session(
            "safe_agent_run",
            mode=ReplayMode.RECORD,
            guardrails=safe_budget,
            config=cfg,
        ) as s:
            # GPT-4o: $2.50/1M prompt, $10.00/1M completion
            # 4,000 prompt ($0.010) + 1,000 completion ($0.010) = $0.020 USD
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Analyze quarterly financial statements"}],
            )
            print(f"  Response: {resp['choices'][0]['message']['content']}")

            report = s.guardrail_report
            if report:
                print(f"  Current Tokens:   {report.total_tokens:,}")
                print(f"  Calculated Cost:  ${report.total_cost_usd:.5f} USD")
                print(f"  Budget Cap:       ${safe_budget.max_cost_usd:.5f} USD")
                print(f"  Status:           {'PASSED' if report.passed else 'FAILED'}")

        # -------------------------------------------------------------------
        # Scenario 2: Enforcing Hard Financial Stop on Runaway Cost
        # -------------------------------------------------------------------
        print("\n[Scenario 2] Preventing runaway loop with a strict $0.03 USD ceiling...")

        strict_budget = guardrails.cost_budget(max_cost_usd=0.030)

        try:
            with session(
                "runaway_agent_run",
                mode=ReplayMode.RECORD,
                guardrails=strict_budget,
                config=cfg,
            ):
                # Step 1: Incurs $0.020 USD (Cumulative $0.020 <= $0.030 -> OK)
                print("  Step 1 executing...")
                client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "Summarize batch 1"}],
                )
                print("  Step 1 completed successfully.")

                # Step 2: Would incur another $0.020 USD (Cumulative $0.040 > $0.030 -> BREACH!)
                print("  Step 2 executing (rogue agent turn)...")
                client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "Summarize batch 2"}],
                )
                print("  [ERROR] Should not reach here!")
        except CostBudgetExceededError as err:
            print(f"\n  [BLOCKED BY GUARDRAIL] {err}")
            print(f"  Metric:    {err.metric}")
            print(f"  Threshold: ${err.threshold:.4f} USD")
            print(f"  Actual:    ${err.actual:.4f} USD")

        # -------------------------------------------------------------------
        # Scenario 3: Offline Replay Token Regression Detection
        # -------------------------------------------------------------------
        print("\n[Scenario 3] Offline regression testing: catching token bloat in REPLAY mode...")

        # We replay 'safe_agent_run' (which used 5,000 tokens) with a regression cap of 3,000 tokens
        regression_cap = guardrails.token_budget(max_tokens=3000)

        try:
            with session(
                "safe_agent_run",
                mode=ReplayMode.REPLAY,
                guardrails=regression_cap,
                config=cfg,
            ):
                client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "user", "content": "Analyze quarterly financial statements"}
                    ],
                )
        except TokenBudgetExceededError as err:
            print(f"\n  [REGRESSION DETECTED OFFLINE] {err}")
            print(f"  Threshold: {err.threshold:,} tokens")
            print(f"  Actual:    {err.actual:,} tokens")
            print("  Zero network calls were made, preventing stealth prompt regressions!")

        unpatch(raw_client)
        print("\n" + "=" * 65)
        print(" Guardrails demonstration completed successfully!")
        print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
