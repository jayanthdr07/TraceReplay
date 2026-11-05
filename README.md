# TraceReplay

<p align="center">
  <strong>Record once. Replay reliably. Test AI agents without burning API tokens or tolerating flaky CI runs.</strong>
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

**TraceReplay** is an open-source testing platform and determinism engine for applications powered by Large Language Models (LLMs) and autonomous AI agents.

Think of it as **VCR for AI applications and agents**:
1. **Record Once:** During your first test run, TraceReplay intercepts calls to providers like OpenAI, Groq, Anthropic, or Gemini, captures the complete interaction (prompts, tool calls, token usage, latency), and saves it to a readable, human-inspectable JSON fixture.
2. **Replay Reliably:** On subsequent test runs, TraceReplay replays the exact recorded responses from disk in **sub-millisecond time**—with **zero live network calls**, **zero API costs**, and **100% deterministic test passes**.

---

## Why TraceReplay?

| Testing LLM Apps Without TraceReplay | Testing With TraceReplay |
| :--- | :--- |
| 💸 **Costly:** Burning API credits on every git push and test run | 🆓 **Zero Cost:** Pay for tokens once during record, replay free forever |
| 🐢 **Slow:** 1–5 seconds per LLM request over the network | ⚡ **Blazing Fast:** Sub-5ms replay latency directly from local disk |
| 🎲 **Flaky:** Stochastic model outputs break test assertions randomly | 🎯 **100% Deterministic:** Same input always yields identical recorded output |
| 🔒 **Leaky:** Accidental commits of raw API keys and private user data | 🛡️ **Sanitized:** Automated PII and credential redaction built-in |
| ❌ **Tool Side-Effects:** Local tool functions run repeatedly in tests | 🛑 **Frozen Tools:** `@record_tool` freezes tool execution during replay |

---

## The Zero-Live-Fallback Guarantee

> [!IMPORTANT]
> TraceReplay enforces a strict **Zero-Live-Fallback Guarantee**:
> In `REPLAY` mode, if a request does not match a recorded fixture, TraceReplay raises a detailed [`RequestMismatchError`](#mismatch-diagnostics) showing a unified diff.
> **It will NEVER silently hit the live provider or charge your credit card.**

---

## Supported Providers

TraceReplay features universal provider adapters that normalize requests and responses across all major platforms:

| Provider | SDK / Client | Status |
| :--- | :--- | :---: |
| **OpenAI** | `openai.OpenAI` (Sync & Async) | ✅ Supported |
| **Groq** | `groq.Groq` (High-Speed LPU Inference) | ✅ Supported |
| **Anthropic Claude** | `anthropic.Anthropic` (`messages.create`) | ✅ Supported |
| **Google Gemini** | `google.genai` / `google.generativeai` | ✅ Supported |
| **DeepSeek** | OpenAI-compatible endpoint | ✅ Supported |
| **Ollama / Local LLMs** | Local inference (`http://localhost:11434`) | ✅ Supported |

---

## Installation

```bash
# Core package
pip install tracereplay

# With specific provider SDKs
pip install "tracereplay[openai]"
pip install "tracereplay[groq]"

# Full developer installation
pip install "tracereplay[all]"
```

---

## 30-Second Quickstart

### 1. Using the Native Pytest Plugin

TraceReplay integrates seamlessly into Pytest via its built-in plugin:

```python
import pytest
from openai import OpenAI

# 1. Add the @pytest.mark.trace_replay marker
@pytest.mark.trace_replay
def test_customer_support_greeting(tracereplay_patch):
    client = OpenAI()
    
    # 2. Automatically intercept the client
    tracereplay_patch(client)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "How do I track my order?"}],
    )
    
    answer = response.choices[0].message.content
    assert "order" in answer.lower()
```

Run your test suite with:
```bash
# Run in AUTO mode (Records if fixture missing; replays if fixture exists)
pytest -v

# Force re-recording new fixtures
pytest --tracereplay-mode=record

# Force strict replay (fails if any network call is attempted)
pytest --tracereplay-mode=replay
```

---

### 2. Programmatic Python SDK (Without Pytest)

```python
import tracereplay
from groq import Groq

client = Groq()
# Intercept client
tracereplay.patch(client, provider="groq")

# Use a session context manager
with tracereplay.session("groq_fast_inference", mode="auto"):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "What is quantum entanglement?"}],
    )
    print(response.choices[0].message.content)
```

---

## Autonomous AI Agents & Tool Interception

Autonomous AI agents often perform **multi-turn reasoning loops** and execute **local Python tools** (database lookups, calculators, external APIs).

TraceReplay provides two dedicated agent primitives:

### 1. The `@record_tool` Decorator
Decorate your agent's local tool functions to record their inputs and outputs. During `REPLAY` mode, **the real tool function is completely bypassed**:

```python
from tracereplay import record_tool

@record_tool(name="fetch_user_balance")
def fetch_user_balance(user_id: str) -> float:
    # During RECORD: Executes real database query and records result
    # During REPLAY: Completely skipped! Returns recorded float instantly
    return db.query_balance(user_id)
```

### 2. The `AgentTracker` Graph
Track and visualize the complete agent reasoning flow:

```python
from tracereplay import AgentTracker

tracker = AgentTracker(agent_name="support_agent")
tracker.add_user_input("Can you check my balance?")
tracker.add_llm_decision("Call fetch_user_balance tool")
tracker.add_tool_result("fetch_user_balance", result=150.25)
tracker.add_final_answer("Your current balance is $150.25.")

# Print formatted execution graph
print(tracker.visualize_flow())
```

**Output:**
```text
Agent Flow [support_agent]:
  [0] USER_INPUT: prompt="Can you check my balance?"
       |
       v
  [1] LLM_DECISION: generates response
       |
       v
  [2] TOOL_RESULT: fetch_user_balance -> 150.25 (0.5ms)
       |
       v
  [3] FINAL_ANSWER: answer="Your current balance is $150.25."
```

---

## Human-Readable Fixture Format

All fixtures are stored as atomic, versioned JSON files in `.tracereplay/`:

```json
{
  "schema_version": "1.0",
  "session_id": "sess_8f21bc90a14e",
  "name": "weather_seattle_query",
  "created_at": "2026-11-05T20:30:00Z",
  "interactions": [
    {
      "index": 0,
      "request": {
        "provider": "openai",
        "model": "gpt-4o",
        "prompt": "What is the weather in Seattle?"
      },
      "response": {
        "content": "The weather in Seattle is 16C with light rain.",
        "usage": {
          "prompt_tokens": 14,
          "completion_tokens": 12,
          "total_tokens": 26
        }
      },
      "duration_ms": 245.5
    }
  ],
  "tool_executions": []
}
```

---

## Configuration & CLI Options

Configure TraceReplay via `pyproject.toml`, environment variables, or CLI flags:

### Pytest CLI Flags
| Flag | Values | Description |
| :--- | :--- | :--- |
| `--tracereplay-mode` | `auto`, `record`, `replay`, `passthrough` | Set global execution mode |
| `--tracereplay-dir` | Path (e.g. `tests/fixtures`) | Directory to store JSON fixtures |
| `--tracereplay-disable`| Flag | Completely bypass TraceReplay |

### Environment Variables
```bash
export TRACEREPLAY_MODE="replay"
export TRACEREPLAY_DIR=".tracereplay"
export TRACEREPLAY_SIMULATE_LATENCY="false"
```

---

## Examples Directory

Explore runnable examples in the [`examples/`](examples/) directory:

- [`01_quickstart_openai.py`](examples/01_quickstart_openai.py): Hybrid OpenAI SDK recording and sub-5ms replay.
- [`02_pytest_workflow/`](examples/02_pytest_workflow/): Full Pytest test suite with `@pytest.mark.trace_replay`.
- [`03_autonomous_agent_tools.py`](examples/03_autonomous_agent_tools.py): Multi-turn agent loop with `@record_tool` and `AgentTracker`.
- [`04_multi_provider.py`](examples/04_multi_provider.py): Universal multi-provider pipeline across OpenAI, Claude, Gemini, and Ollama.
- [`05_quickstart_groq.py`](examples/05_quickstart_groq.py): High-speed Groq LPU inference recording and replay.

---

## Security & Privacy

TraceReplay automatically sanitizes sensitive data before writing to disk:
- **Redaction:** API keys (`sk-...`, `gsk_...`), authorization headers (`Bearer ...`), and organization tokens are masked as `[REDACTED]`.
- **Path Traversal Protection:** Fixture names are strictly resolved and validated within target storage roots.
- **Local First:** All recordings remain entirely on your local machine; zero data is sent to external servers.

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on setting up your local development environment, running tests, and submitting pull requests.

```bash
# Clone the repository
git clone https://github.com/rakshithkumar608/TraceReplay.git
cd TraceReplay

# Install in editable mode with development dependencies
pip install -e ".[dev,all]"

# Run tests
pytest -v

# Run linting and type checking
ruff check .
mypy src tests examples
```

---

## License

This project is licensed under the [MIT License](LICENSE).
