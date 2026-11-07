# TraceReplay

<p align="center">
  <strong>Record once. Replay reliably. Deterministic testing, AI chaos engineering, and cost guardrails for LLM applications and autonomous AI agents.</strong>
</p>

<p align="center">
  <a href="https://github.com/rakshithkumar608/TraceReplay/actions/workflows/ci.yml"><img src="https://github.com/rakshithkumar608/TraceReplay/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a>
  <a href="https://pypi.org/project/tracereplay/"><img src="https://img.shields.io/pypi/v/tracereplay.svg" alt="PyPI version"></a>
  <img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python Versions">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://mypy-lang.org/"><img src="https://img.shields.io/badge/type_checker-mypy_strict-blue.svg" alt="Mypy Strict"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
</p>

---

## What is TraceReplay?

**TraceReplay** is an open-source deterministic testing, fault injection, and cost guardrail platform purpose-built for applications powered by Large Language Models (LLMs) and autonomous AI agents.

In traditional software, network mocking tools like VCR record HTTP traffic. But **modern AI agents are non-deterministic, multi-turn state machines**:
- They generate varying prompts, execute dynamic Python tools, suffer from stealth token bloat, drift subtly across prompt engineering tweaks, and crash on third-party API rate limits.
- Repeated live API calls burn hundreds of dollars in CI, introduce 5-second network latencies per request, and cause flaky test failures.

TraceReplay solves this by capturing multi-turn LLM reasoning, tool executions, and latency metrics into inspectable local fixtures—enabling **sub-millisecond deterministic replays**, **zero live API costs in CI**, **chaos resilience validation**, and **intelligent prompt drift tolerance**.

---

## The 5 Breakthrough WOW Features

TraceReplay introduces 5 breakthrough capabilities not found in any other mocking or replay framework:

| # | Breakthrough Feature | What It Does | Why Developers Love It |
|---|---|---|---|
| **1** | **Time-Travel Forking** | Fast-forward through steps 1..N deterministically, then fork into live recording at any step or tool call. | Test edge cases at step 10 of an agent workflow without paying for or repeating steps 1..9. |
| **2** | **AI Chaos Engineering** | Inject realistic AI failures: 429 rate limits, timeouts, server outages, malformed JSON, hallucinated tools, safety refusals, and latency jitters. | Prove your agent recovers gracefully before deploying to production. |
| **3** | **Token, Cost & Latency Guardrails** | Enforce USD budget caps, max token limits, and latency thresholds with hard stops. Run offline regression detection at $0 cost. | Block runaway agent loops and catch stealth prompt inflation in CI before spending a dime. |
| **4** | **Semantic Diff & Drift Detection** | Fuzzy request matching using pure-Python hybrid cosine similarity or vector embeddings. Inline word diffs and drift reporting. | Prompts evolve naturally; minor wording tweaks replay smoothly instead of crashing tests. |
| **5** | **Deterministic Clock & Freeze Time** | Freeze `datetime.now()` to match recorded fixture timestamps. Fast-forward `time.sleep()` instantly (0 real delay). | Dynamic prompt dates ("Today is 2026-11-07") stay 100% deterministic; 60s backoff sleeps run in 0.04 ms. |

---

## Why TraceReplay?

| Testing LLMs Without TraceReplay | Testing With TraceReplay |
| :--- | :--- |
| 💸 **Costly:** Burning API credits on every git push and test run | 🆓 **Zero Cost:** Pay for tokens once during record, replay free forever |
| 🐢 **Slow:** 1–5 seconds per LLM request over the network | ⚡ **Blazing Fast:** Sub-5ms replay latency directly from local disk |
| 🎲 **Flaky:** Stochastic model outputs break test assertions randomly | 🎯 **100% Deterministic:** Same input always yields identical recorded output |
| 💥 **Brittle:** Minor prompt edits or date changes invalidate tests | 🧠 **Smart Drift:** Semantic matching allows natural prompt evolution |
| 💣 **Vulnerable:** Uncaught rate limits crash agents in production | 🧪 **Chaos Tested:** 9 native fault injectors simulate real-world API chaos |
| 🛑 **Runaway Bills:** Rogue agents can loop infinitely and drain accounts | 🛡️ **Guardrails:** Hard budget stops cut off execution if caps are exceeded |

---

## The Zero-Live-Fallback Guarantee

> [!IMPORTANT]
> TraceReplay enforces a strict **Zero-Live-Fallback Guarantee**:
> In `REPLAY` mode, if a request does not match a recorded fixture, TraceReplay raises a detailed [`RequestMismatchError`](#mismatch-diagnostics) with a unified diff and semantic similarity hint.
> **It will NEVER silently hit the live provider or charge your credit card.**

---

## Supported Providers

TraceReplay provides universal adapters that normalize requests and responses across all major AI providers:

| Provider | SDK / Client | Streaming | Function / Tool Calling |
| :--- | :--- | :---: | :---: |
| **OpenAI** | `openai.OpenAI` (Sync & Async) | ✅ Supported | ✅ Supported |
| **Anthropic Claude** | `anthropic.Anthropic` (`messages.create`) | ✅ Supported | ✅ Supported |
| **Google Gemini** | `google.genai` / `google.generativeai` | ✅ Supported | ✅ Supported |
| **Groq** | `groq.Groq` (Ultra-low latency LPU) | ✅ Supported | ✅ Supported |
| **Mistral AI** | `mistralai.Mistral` | ✅ Supported | ✅ Supported |
| **DeepSeek** | OpenAI-compatible endpoint | ✅ Supported | ✅ Supported |
| **Ollama / Local LLMs** | Local inference (`http://localhost:11434`) | ✅ Supported | ✅ Supported |

---

## Installation

```bash
# Core package
pip install tracereplay

# With specific provider SDKs
pip install "tracereplay[openai]"
pip install "tracereplay[anthropic]"
pip install "tracereplay[gemini]"
pip install "tracereplay[groq]"

# Full developer installation
pip install "tracereplay[all]"
```

---

## Quickstart

### 1. Pytest Plugin Integration

Add the `@pytest.mark.trace_replay` marker. The fixture is recorded on the first run, and replayed in sub-millisecond time on subsequent runs:

```python
import pytest
from openai import OpenAI


@pytest.mark.trace_replay
def test_order_status_agent(tracereplay_patch):
    client = OpenAI()
    tracereplay_patch(client)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "How do I track my order?"}],
    )

    content = response.choices[0].message.content
    assert "order" in content.lower()
```

Run tests from the terminal:
```bash
# AUTO mode: records if fixture missing, replays if fixture exists
pytest -v

# Strict replay mode (guaranteed zero live network calls)
pytest --tracereplay-mode=replay
```

---

### 2. Programmatic Python SDK (Context Manager)

```python
import tracereplay
from groq import Groq

client = Groq()
tracereplay.patch(client, provider="groq")

with tracereplay.session("groq_fast_inference", mode="auto"):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "Explain quantum entanglement in 1 sentence."}],
    )
    print(response.choices[0].message.content)
```

---

## Deep Dive: The 5 WOW Features in Action

### 1. Time-Travel Forking

Fast-forward through multi-step reasoning deterministically, then fork into live recording at any specific step or tool call:

```python
import tracereplay
from tracereplay import record_tool


@record_tool(name="search_database")
def search_database(query: str) -> str:
    return "Found record #402"


# Replay steps 0..3 from "base_workflow", then branch into live recording at step 4:
with tracereplay.session(
    name="base_workflow",
    fork_at_step=4,
    fork_session_name="base_workflow_branch_step4",
) as sess:
    # Steps 0-3 execute deterministically from disk
    # Step 4 transitions into live execution and records to the new branch fixture!
    ...
```

You can also fork right when a specific tool is called:
```python
with tracereplay.session(name="base_workflow", fork_at_tool="search_database"):
    ...
```

---

### 2. AI Chaos Engineering & Fault Injection

Verify that your agent handles real-world production outages without crashing:

```python
from tracereplay import chaos

# Simulate a 429 Rate Limit on turn 1, with native OpenAI RateLimitError:
rate_limit_fault = chaos.rate_limit(
    step=1,
    retry_after=5,
    native=True,  # Raises actual openai.RateLimitError
)

with tracereplay.session(name="agent_resilience_test", chaos=rate_limit_fault):
    # Your agent's retry and backoff logic is tested under authentic conditions!
    ...
```

TraceReplay supports 9 native fault types:
- `chaos.rate_limit(step=..., retry_after=5)`
- `chaos.timeout(step=..., simulated_delay=2.0)`
- `chaos.server_error(step=..., status_code=503)`
- `chaos.context_length_exceeded(step=..., max_context=128000)`
- `chaos.malformed_json(step=..., corruption_type="truncated")`
- `chaos.hallucinated_tool(step=..., tool_name="unauthorized_delete_db")`
- `chaos.safety_refusal(step=..., refusal_message="Content policy refusal")`
- `chaos.latency_jitter(step=..., min_delay_ms=500, max_delay_ms=2000)`
- `chaos.custom_exception(step=..., exception=MyCustomError("API failed"))`

---

### 3. Token, Cost & Latency Guardrails

Protect your infrastructure against runaway agent loops and catch prompt bloat:

```python
with tracereplay.session(
    name="financial_analyst",
    max_cost_usd=0.05,  # Hard stop at $0.05 USD
    max_tokens=4000,  # Hard stop at 4,000 total tokens
    max_latency_ms=3000.0,  # Max 3 seconds cumulative latency
) as sess:
    # If a rogue multi-turn loop exceeds $0.05, TraceReplay instantly cuts it off
    # by raising CostBudgetExceededError!
    ...

# Generate comprehensive budget reports:
print(sess.guardrail_report.summary_text())
```

> [!TIP]
> **Zero-Network Offline Regression Testing:**
> When replaying fixtures in CI, TraceReplay computes replayed tokens and costs against your limits. If a prompt grew too large, CI catches it offline at **$0 cost**!

---

### 4. Semantic Diff & Smart Drift Detection

Avoid breaking test suites when prompts undergo minor wording or prompt engineering changes:

```python
with tracereplay.session(
    name="customer_service",
    mode="replay",
    semantic_matching=True,  # Enable fuzzy matching
    semantic_threshold=0.85,  # 85% similarity threshold
) as sess:
    # "You are a customer service assistant. Explain refund policy."
    # vs
    # "You are a polite customer support assistant. Explain refund policy concisely."
    # Replays successfully without crashing!
    ...

# Inspect prompt evolution across your test suite:
print(sess.drift_report.summary_text())
```

TraceReplay prints an inline word-level diff and unified diff:
```text
Inline Word Diff:
  you are a {+polite+} customer [-service-] {+support+} assistant . explain refund policy {+concisely+} .
  Added words:   ['polite', 'support', 'concisely']
  Removed words: ['service']

[Hint] Prompts are 83.9% similar. Enable semantic matching (`semantic_matching=True, semantic_threshold=0.80`) to allow this prompt drift.
```

---

### 5. Deterministic Clock & Freeze Time

Eliminate dynamic timestamp flakiness and speed up test suites by eliminating real sleep delays:

```python
# 1. Automatic Fixture Time Sync:
# In REPLAY mode, TraceReplay automatically freezes datetime.now() to the exact
# timestamp recorded in the fixture!
with tracereplay.session(name="booking_agent", mode="replay", freeze_time=True):
    # Dynamic prompt dates ("Today is 2026-11-07") match the fixture 100% deterministically!
    ...

# 2. Instant Sleep Fast-Forwarding:
from tracereplay import freeze_time

with freeze_time("2026-11-07 10:00:00 UTC"):
    # Agent retry loops calling time.sleep(60.0) run in 0.04 milliseconds!
    time.sleep(60.0)
    assert datetime.datetime.utcnow().minute == 1
```

---

## Autonomous Agent Tools & Tracker

Decorate your agent's local Python tools to record their inputs and outputs. During `REPLAY`, **real tools are completely bypassed**:

```python
from tracereplay import AgentTracker, record_tool


@record_tool(name="fetch_user_balance")
def fetch_user_balance(user_id: str) -> float:
    # In RECORD: Executes real DB query
    # In REPLAY: Completely skipped, returns recorded output in 0.1ms
    return db.query_balance(user_id)


# Visualize the multi-turn agent execution graph:
tracker = AgentTracker(agent_name="support_agent")
tracker.add_user_input("Can you check my balance?")
tracker.add_llm_decision("Call fetch_user_balance tool")
tracker.add_tool_result("fetch_user_balance", result=150.25)
tracker.add_final_answer("Your current balance is $150.25.")

print(tracker.visualize_flow())
```

---

## Runnable Examples Directory

Explore the complete collection of self-contained, executable scripts in [`examples/`](examples/):

| Example Script | Demonstrates | Run Command |
| :--- | :--- | :--- |
| [`01_quickstart_openai.py`](examples/01_quickstart_openai.py) | OpenAI SDK record & sub-5ms replay | `python examples/01_quickstart_openai.py` |
| [`02_pytest_workflow/`](examples/02_pytest_workflow/) | Native Pytest plugin test suite | `pytest examples/02_pytest_workflow/` |
| [`03_autonomous_agent_tools.py`](examples/03_autonomous_agent_tools.py) | `@record_tool` & `AgentTracker` visualization | `python examples/03_autonomous_agent_tools.py` |
| [`04_multi_provider.py`](examples/04_multi_provider.py) | Cross-provider switching (OpenAI, Claude, Gemini, Groq) | `python examples/04_multi_provider.py` |
| [`05_quickstart_groq.py`](examples/05_quickstart_groq.py) | High-speed Groq LPU inference recording | `python examples/05_quickstart_groq.py` |
| [`06_token_cost_guardrails.py`](examples/06_token_cost_guardrails.py) | Budget caps, hard stops & offline regression testing | `python examples/06_token_cost_guardrails.py` |
| [`07_semantic_drift_detection.py`](examples/07_semantic_drift_detection.py) | Fuzzy replay matching, word diffs & drift reports | `python examples/07_semantic_drift_detection.py` |
| [`08_deterministic_clock_freeze_time.py`](examples/08_deterministic_clock_freeze_time.py) | Fixture time auto-sync & instant 60s sleep fast-forward | `python examples/08_deterministic_clock_freeze_time.py` |

---

## Configuration & Environment Variables

Configure TraceReplay via `pyproject.toml`, CLI flags, or environment variables:

| Setting | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| **Mode** | `TRACEREPLAY_MODE` | `auto` | `auto`, `record`, `replay`, `passthrough` |
| **Fixtures Dir** | `TRACEREPLAY_DIR` | `.tracereplay/fixtures` | Directory where JSON fixtures are saved |
| **Simulate Latency** | `TRACEREPLAY_SIMULATE_LATENCY` | `false` | Replay with real recorded latency delays |
| **Match Parameters** | `TRACEREPLAY_MATCH_PARAMETERS` | `true` | Compare request parameters (temperature, etc.) |
| **Strict Ordering** | `TRACEREPLAY_STRICT_ORDERING` | `true` | Enforce sequential interaction ordering |
| **Semantic Matching** | `TRACEREPLAY_SEMANTIC_MATCHING` | `false` | Enable fuzzy/semantic request matching |
| **Semantic Threshold**| `TRACEREPLAY_SEMANTIC_THRESHOLD`| `0.85` | Minimum similarity score (0.0 - 1.0) |
| **Freeze Time** | `TRACEREPLAY_FREEZE_TIME` | `None` | `true` (auto-sync), or ISO datetime string |

---

## Security & Automatic PII Redaction

TraceReplay automatically sanitizes sensitive data before writing to disk:
- **Credential Masking:** API keys (`sk-...`, `gsk_...`), authorization headers (`Bearer ...`), and organization tokens are masked as `[REDACTED]`.
- **Custom PII Redaction:** Pass regex patterns or dictionary keys to sanitize credit cards, emails, or personal identifiers.
- **Path Traversal Protection:** Fixture names are strictly resolved and validated within target storage roots.
- **Local-First Architecture:** Recordings remain 100% on your machine or repository. Zero data is sent to external servers.

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on setting up your local development environment, running tests, and submitting pull requests.

```bash
# Clone the repository
git clone https://github.com/rakshithkumar608/TraceReplay.git
cd TraceReplay

# Install in editable mode with development dependencies
pip install -e ".[dev,all]"

# Run full test suite (157 unit & integration tests)
pytest -v

# Run linting and type checking
ruff check .
mypy src tests examples
```

---

## License

This project is licensed under the [MIT License](LICENSE).
