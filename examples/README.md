# TraceReplay Examples

This directory contains standalone, copy-pasteable examples showing how to use TraceReplay in your applications, test suites, and autonomous agent workflows.

All examples are self-contained and run immediately without requiring paid accounts or live API keys.

---

## Example Overview

| Script | Purpose | Key Concepts | Command |
| :--- | :--- | :--- | :--- |
| **`01_quickstart_openai.py`** | Basic Record & Replay | `session()`, `ReplayMode.RECORD`, `ReplayMode.REPLAY` | `python examples/01_quickstart_openai.py` |
| **`02_pytest_workflow/`** | Native Pytest Testing | `@pytest.mark.trace_replay`, `tracereplay_session` | `pytest examples/02_pytest_workflow -v` |
| **`03_autonomous_agent_tools.py`** | Multi-Turn Agent Loop | `@record_tool`, `AgentTracker.visualize_flow()` | `python examples/03_autonomous_agent_tools.py` |
| **`04_multi_provider.py`** | Universal Model Testing | OpenAI, Anthropic, Gemini, Ollama normalization | `python examples/04_multi_provider.py` |
| **`05_quickstart_groq.py`** | Groq LPU Inference | `patch(client, provider="groq")`, `llama-3.3-70b` | `python examples/05_quickstart_groq.py` |

---

## 1. Quickstart (`01_quickstart_openai.py`)

Demonstrates how TraceReplay intercepts model requests and records them into `.tracereplay/` fixtures.

```bash
python examples/01_quickstart_openai.py
```

**Expected Output:**
- **Phase 1 (Record):** Sends request, records payload and response, saves `.tracereplay/quickstart_demo.json`.
- **Phase 2 (Replay):** Returns identical response in milliseconds with zero live network calls.

---

## 2. Pytest Workflow (`02_pytest_workflow/test_weather_bot.py`)

Demonstrates native Pytest test suites.

```bash
pytest examples/02_pytest_workflow -v
```

**Key Features:**
- Uses the `@pytest.mark.trace_replay(fixture="custom_name")` marker.
- Automatically switches from `RECORD` on the first test run to `REPLAY` on subsequent test runs (`AUTO` mode).
- Fully supports parameterized tests with `@pytest.mark.parametrize`.

---

## 3. Autonomous AI Agent with Tools (`03_autonomous_agent_tools.py`)

Demonstrates multi-turn agent decision graphs and local Python tool function capture.

```bash
python examples/03_autonomous_agent_tools.py
```

**Key Features:**
- Decorate local Python functions with `@record_tool`.
- During `RECORD`, real tools execute and results are captured.
- During `REPLAY`, **real tools are completely bypassed**—recorded results are returned deterministically.
- `AgentTracker` records the complete decision tree and prints an ASCII diagram:
  ```text
  Agent Flow [order_assistant]:
    [0] USER_INPUT: prompt="Can I check my order and express shipping..."
         |
         v
    [1] LLM_DECISION: generates response
         |
         v
    [2] TOOL_RESULT: lookup_order -> {'order_id': 'ORD-8821', ...}
         |
         v
    [3] LLM_DECISION: generates response
         |
         v
    [4] TOOL_RESULT: calculate_shipping_fee -> {'shipping_fee_usd': 14.25}
         |
         v
    [5] FINAL_ANSWER: answer="Hello Alice! Order #ORD-8821 is currently..."
  ```

---

## 4. Multi-Provider Normalization (`04_multi_provider.py`)

Demonstrates how TraceReplay normalizes OpenAI, Anthropic Claude, Google Gemini, Groq, and local Ollama into a unified payload format.

```bash
python examples/04_multi_provider.py
```

---

## 5. Groq LPU Inference (`05_quickstart_groq.py`)

Demonstrates intercepting Groq's ultra-fast LPU inference (`groq.Groq()` SDK).

```bash
# To test with your live Groq API key:
$env:GROQ_API_KEY="gsk_your_key_here"
python examples/05_quickstart_groq.py
```

---

## Fixtures Storage

Fixtures are saved as human-readable JSON files in `.tracereplay/`:
```text
.tracereplay/
├── quickstart_demo.json
├── weather_seattle_query.json
├── agent_order_flow.json
└── groq_quickstart.json
```
These fixture files can be checked into git to provide repeatable, zero-cost CI test runs for your entire development team.
