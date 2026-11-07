"""TraceReplay Feature 5: Deterministic Clock & Freeze Time.

Demonstrates mock time injection, automatic fixture time synchronization,
and simulated time.sleep acceleration for AI agents and test suites.
"""

from __future__ import annotations

import datetime
import tempfile
import time
from pathlib import Path

from tracereplay.clock import freeze_time
from tracereplay.config import TraceReplayConfig
from tracereplay.core.session import TraceReplaySession
from tracereplay.models import ReplayMode, RequestPayload, ResponsePayload


def main() -> None:
    print("=" * 65)
    print(" TraceReplay Demo: Deterministic Clock & Freeze Time")
    print("=" * 65)

    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = TraceReplayConfig(fixtures_dir=Path(tmp_dir))
        session_name = "calendar_booking_agent"

        # -------------------------------------------------------------
        # Scenario 1: Record interaction with dynamic system prompt date
        # -------------------------------------------------------------
        recorded_date = "2026-11-07 10:00:00 UTC"
        print(f"\n[Scenario 1] Freezing time to '{recorded_date}' and recording baseline...")

        with freeze_time(recorded_date):
            now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            system_prompt = f"Today is {now_str}. Book appointments only on business days."
            user_prompt = "Schedule a meeting for the next available Tuesday."

            with TraceReplaySession(name=session_name, mode=ReplayMode.RECORD, config=cfg) as sess:
                assert sess.recorder is not None
                sess.recorder.record_interaction(
                    RequestPayload(
                        provider="openai",
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    ),
                    ResponsePayload(
                        content="Meeting booked for Tuesday, November 10, 2026 at 10:00 AM."
                    ),
                )
        print("  Recorded baseline session with embedded dynamic timestamp.")

        # -------------------------------------------------------------
        # Scenario 2: Auto-Freeze to Fixture in Replay Mode
        # -------------------------------------------------------------
        print("\n[Scenario 2] Replaying with freeze_time=True (Auto-Sync to Fixture)...")
        # In real life, this test might run months later on a different date.
        # With freeze_time=True, TraceReplay automatically freezes the clock to
        # the exact timestamp recorded in the fixture!
        with TraceReplaySession(
            name=session_name,
            mode=ReplayMode.REPLAY,
            config=cfg,
            freeze_time=True,
        ) as sess:
            assert sess.replayer is not None
            # Application dynamically constructs its prompt using datetime.now()
            current_now = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
            replayed_system = f"Today is {current_now}. Book appointments only on business days."

            resp = sess.replayer.replay_interaction(
                RequestPayload(
                    provider="openai",
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": replayed_system},
                        {"role": "user", "content": user_prompt},
                    ],
                )
            )
            print("  [REPLAY SUCCEEDED DETERMINISTICALLY!]")
            print(f"  Clock auto-frozen to: '{current_now}'")
            print(f"  Agent Response:       '{resp.content}'")

        # -------------------------------------------------------------
        # Scenario 3: Instant Sleep Acceleration (Eliminating Real Delays)
        # -------------------------------------------------------------
        print("\n[Scenario 3] Fast-forwarding agent retry loops with simulated sleep...")
        with freeze_time("2026-11-07 10:00:00 UTC") as clock:
            print(f"  Initial clock: {datetime.datetime.utcnow().isoformat()}")
            start_wall = time.perf_counter()

            # Emulate an agent backing off for 60 seconds
            print("  Agent executing time.sleep(60.0)...")
            time.sleep(60.0)

            elapsed_wall = time.perf_counter() - start_wall
            print(f"  Clock advanced to:     {datetime.datetime.utcnow().isoformat()}")
            print(f"  Real wall-clock time:  {elapsed_wall * 1000:.2f} ms (no 60s freeze!)")
            print(f"  Total simulated delay: {clock.state.total_advanced_seconds:.1f}s")

        # -------------------------------------------------------------
        # Scenario 4: Programmatic Time Travel
        # -------------------------------------------------------------
        print("\n[Scenario 4] Programmatic time-travel with clock.tick() and clock.set_time()...")
        with freeze_time("2026-11-07 10:00:00 UTC") as clock:
            print(f"  Start:             {datetime.datetime.utcnow().isoformat()}")
            clock.advance(seconds=7200)
            print(f"  After 2h advance:  {datetime.datetime.utcnow().isoformat()}")
            clock.set_time("2026-12-31 23:59:59 UTC")
            print(f"  Jump to New Year:  {datetime.datetime.utcnow().isoformat()}")

    print("\n" + "=" * 65)
    print(" Deterministic Clock & Freeze Time demo completed successfully!")
    print("=" * 65)


if __name__ == "__main__":
    main()
