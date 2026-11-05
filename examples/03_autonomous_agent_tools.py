"""Example 03: Autonomous AI Agent & Tool Execution Recording (Phase 8).

Demonstrates deterministic replay of multi-turn autonomous AI agent loops:
1. Tool Interception: `@tracereplay.record_tool` freezes local Python tool functions.
2. Sequential Graph: `AgentTracker` records and visualizes the complete decision tree:
   User Input -> LLM Decision -> Tool Execution -> Tool Result -> Next Decision -> Final Answer
3. Zero-Live-Fallback: In REPLAY mode, neither the LLM nor local tool functions run again.

Run directly with:
    python examples/03_autonomous_agent_tools.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tracereplay import (
    AgentTracker,
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    TraceReplayConfig,
    record_tool,
    session,
)

# ============================================================================
# Tool Functions Decorated with @record_tool
# ============================================================================

real_order_lookup_calls = 0
real_shipping_calc_calls = 0


@record_tool(name="lookup_order")
def lookup_order(order_id: str) -> dict[str, Any]:
    """Simulated local database query to fetch order status."""
    global real_order_lookup_calls
    real_order_lookup_calls += 1
    return {
        "order_id": order_id,
        "customer": "Alice Smith",
        "items": ["Laptop Stand", "USB-C Cable"],
        "weight_kg": 1.8,
        "status": "Processing",
    }


@record_tool(name="calculate_shipping_fee")
def calculate_shipping_fee(weight_kg: float, express: bool = False) -> float:
    """Simulated shipping calculator service."""
    global real_shipping_calc_calls
    real_shipping_calc_calls += 1
    base_rate = 5.0
    return (base_rate + weight_kg * 2.5) * (1.5 if express else 1.0)


# ============================================================================
# Autonomous Agent Loop
# ============================================================================


class SupportAgent:
    """Autonomous agent coordinating LLM reasoning and local tool executions."""

    def __init__(self, name: str = "order_assistant") -> None:
        self.name = name

    def run(self, user_query: str, order_id: str, sess: Any) -> tuple[str, AgentTracker]:
        tracker = AgentTracker(agent_name=self.name)

        # 1. User Input
        tracker.add_user_input(user_query, metadata={"order_id": order_id})

        # 2. Turn 1: LLM decides to fetch order details
        prompt_1 = f"User asks: '{user_query}' for Order #{order_id}. What tool should be called?"
        req_1 = RequestPayload(provider="openai", model="gpt-4o", prompt=prompt_1)

        if sess.mode == ReplayMode.RECORD:
            resp_1 = ResponsePayload(
                content='{"action": "call_tool", "tool": "lookup_order", '
                f'"arguments": {{"order_id": "{order_id}"}}}}'
            )
            sess.recorder.record_interaction(req_1, resp_1)
        else:
            resp_1 = sess.replayer.replay_interaction(req_1)

        tracker.add_llm_decision(resp_1.content)

        # 3. Tool Execution 1: lookup_order (bypassed in replay)
        order_info = lookup_order(order_id=order_id)
        tracker.add_tool_result("lookup_order", order_info)

        # 4. Turn 2: LLM decides to calculate shipping based on package weight
        weight = order_info["weight_kg"]
        prompt_2 = f"Order details: {order_info}. Calculate express shipping for weight {weight}kg."
        req_2 = RequestPayload(provider="openai", model="gpt-4o", prompt=prompt_2)

        if sess.mode == ReplayMode.RECORD:
            resp_2 = ResponsePayload(
                content='{"action": "call_tool", "tool": "calculate_shipping_fee", '
                f'"arguments": {{"weight_kg": {weight}, "express": true}}}}'
            )
            sess.recorder.record_interaction(req_2, resp_2)
        else:
            resp_2 = sess.replayer.replay_interaction(req_2)

        tracker.add_llm_decision(resp_2.content)

        # 5. Tool Execution 2: calculate_shipping_fee (bypassed in replay)
        shipping_cost = calculate_shipping_fee(weight_kg=weight, express=True)
        tracker.add_tool_result("calculate_shipping_fee", {"shipping_fee_usd": shipping_cost})

        # 6. Turn 3: LLM compiles final response
        prompt_3 = (
            f"Order: {order_id}, status: {order_info['status']}, shipping: ${shipping_cost:.2f}. "
            "Write response to customer."
        )
        req_3 = RequestPayload(provider="openai", model="gpt-4o", prompt=prompt_3)

        if sess.mode == ReplayMode.RECORD:
            resp_3 = ResponsePayload(
                content=f"Hello Alice! Order #{order_id} is currently Processing. "
                f"Express shipping for your items is ${shipping_cost:.2f}."
            )
            sess.recorder.record_interaction(req_3, resp_3)
        else:
            resp_3 = sess.replayer.replay_interaction(req_3)

        final_msg = resp_3.content or ""
        tracker.add_final_answer(final_msg)

        return final_msg, tracker


# ============================================================================
# Main Demonstration Runner
# ============================================================================


def main() -> None:
    fixtures_dir = Path(".tracereplay")
    cfg = TraceReplayConfig(fixtures_dir=fixtures_dir)
    agent = SupportAgent(name="order_assistant")
    session_name = "agent_order_flow"

    print("=" * 65)
    print("TraceReplay - Example 03: Multi-Turn Agent & Tool Recording")
    print("=" * 65)

    # ------------------------------------------------------------------------
    # Phase 1: RECORD MODE (Real tools and LLM runs)
    # ------------------------------------------------------------------------
    print("\n[Phase 1] Running Autonomous Agent in RECORD mode...")
    with session(session_name, mode=ReplayMode.RECORD, config=cfg) as sess_rec:
        answer_rec, tracker_rec = agent.run(
            user_query="Can I check my order and express shipping cost?",
            order_id="ORD-8821",
            sess=sess_rec,
        )

    print(f"  Final Answer:   {answer_rec}")
    print(f"  lookup_order calls:          {real_order_lookup_calls}")
    print(f"  calculate_shipping calls:    {real_shipping_calc_calls}")
    assert real_order_lookup_calls == 1
    assert real_shipping_calc_calls == 1

    # ------------------------------------------------------------------------
    # Phase 2: REPLAY MODE (Zero LLM calls, Zero Tool executions)
    # ------------------------------------------------------------------------
    print("\n[Phase 2] Running Autonomous Agent in REPLAY mode...")
    with session(session_name, mode=ReplayMode.REPLAY, config=cfg) as sess_rep:
        answer_rep, tracker_rep = agent.run(
            user_query="Can I check my order and express shipping cost?",
            order_id="ORD-8821",
            sess=sess_rep,
        )

    print(f"  Final Answer:   {answer_rep}")
    print(f"  lookup_order calls:          {real_order_lookup_calls} (Skipped in replay!)")
    print(f"  calculate_shipping calls:    {real_shipping_calc_calls} (Skipped in replay!)")

    assert answer_rep == answer_rec
    assert real_order_lookup_calls == 1, "Real tool must NOT run during replay"
    assert real_shipping_calc_calls == 1, "Real tool must NOT run during replay"

    # ------------------------------------------------------------------------
    # Phase 3: Inspect the Agent Execution Graph
    # ------------------------------------------------------------------------
    print("\n[Phase 3] Generated Agent Execution Graph:")
    print("-" * 65)
    print(tracker_rep.visualize_flow())
    print("-" * 65)
    print("\n[SUCCESS] Multi-turn agent replayed deterministically with ZERO live calls!\n")


if __name__ == "__main__":
    main()
