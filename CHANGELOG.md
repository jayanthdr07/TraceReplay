# Changelog

All notable changes to TraceReplay will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-11-05

### Added

#### Milestone 1: Core Foundation & Deterministic Replay Engine
- **Core Domain Models:** High-performance immutable models (`SessionRecord`, `Interaction`, `RequestPayload`, `ResponsePayload`, `TokenUsage`, `ToolCallRecord`).
- **Atomic JSON Storage Engine:** ACID-safe atomic JSON writes, schema validation, and path traversal protection.
- **Deterministic Request Normalizer & Matcher:** Semantic whitespace normalizer, dictionary key sorting, parameter filtering, and unified diff output.
- **Strict Zero-Live-Fallback Guarantee:** Replay mode strictly halts with `RequestMismatchError` or `LiveFallbackProhibitedError` on any discrepancy—guaranteeing zero silent cloud API bills.
- **Automated PII & Secret Sanitizer:** Automatic redaction of sensitive credentials (`sk-...`, `gsk_...`, bearer tokens, authorization headers) before persisting fixtures.
- **Universal Provider Interceptors:** Out-of-the-box adapters for OpenAI (`openai.OpenAI`), Groq (`groq.Groq`), Anthropic Claude (`anthropic.Anthropic`), Google Gemini (`google.genai`), DeepSeek, and local Ollama.
- **Native Pytest Plugin:**
  - Registered under Pytest `pytest11` entrypoint (`pytest_plugin.py`).
  - `@pytest.mark.trace_replay` marker with custom fixture naming and parameterization support.
  - Auto-injected fixtures: `tracereplay_session` and `tracereplay_patch`.
  - Autonomous `AUTO` mode: Records missing fixtures on first run; deterministically replays on all subsequent runs.

#### Milestone 2: Multi-Turn Agent & Complex Tool-Call Recording (Phase 8)
- **`AgentTracker` Execution Graph:** Models complex agent workflows as stateful decision graphs (`User Input -> LLM Decision -> Tool Execution -> Tool Result -> Next Decision -> Final Answer`).
- **Visual Graph Generator:** `AgentTracker.visualize_flow()` producing human-readable ASCII decision trees for debugging agent reasoning.
- **`@record_tool` Interception Decorator:**
  - Wraps synchronous and asynchronous local Python functions.
  - Captures argument signatures and execution durations.
  - **Replay Bypass:** In `REPLAY` mode, completely bypasses the real Python function and returns recorded fixture data deterministically.
- **Sequential Tool Call Verification:** Strict index-based tool matching preventing out-of-order execution during agent reasoning loops.

#### Open-Source SDK Polish (Option A)
- **GitHub Actions CI Matrix:** Multi-OS (Ubuntu, Windows) automated testing across Python `3.10`, `3.11`, `3.12`, and `3.13` with strict `ruff` linting, `mypy` strict type-checking, and `twine` packaging checks.
- **Interactive Runnable Examples (`examples/`):**
  - `01_quickstart_openai.py`: Hybrid real/simulated OpenAI recording and sub-5ms replay.
  - `02_pytest_workflow/test_weather_bot.py`: Complete Pytest test suite.
  - `03_autonomous_agent_tools.py`: Multi-turn autonomous agent with frozen local tool functions.
  - `04_multi_provider.py`: Normalized cross-provider pipeline.
  - `05_quickstart_groq.py`: Verified live Groq LPU inference recording and playback.
  - `examples/README.md`: Quickstart cheat-sheet for running all examples.
- **Production-Grade Documentation:** High-impact landing page in `README.md` with badges, value proposition, quickstarts, and security guidelines.
