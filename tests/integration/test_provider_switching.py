"""Cross-provider integration tests demonstrating universal model switching."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from tracereplay.config import TraceReplayConfig
from tracereplay.core.session import session
from tracereplay.models import ReplayMode
from tracereplay.providers.patcher import patch, unpatch


def run_llm_pipeline(client: Any, prompt: str, provider: str, model: str) -> str:
    """A realistic application task that routes to whichever provider client is passed."""
    if provider == "mistral":
        resp = client.chat.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return str(resp.choices[0].message.content)

    if provider == "anthropic":
        resp = client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        if isinstance(resp, dict):
            return str(resp["content"][0]["text"])
        return str(resp.content[0].text)

    # OpenAI / Groq / Ollama / Generic
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    return str(resp.choices[0].message.content)


def test_cross_provider_seamless_switching(tmp_path: Path) -> None:
    """Verify seamless switching across OpenAI, Groq, Mistral, Ollama, and Anthropic."""
    cfg = TraceReplayConfig(fixtures_dir=tmp_path)
    test_prompt = "Explain deterministic replay in one sentence."

    # 1. Setup Mock Clients with Provider-Specific Responses
    # A. OpenAI Client
    openai_client = MagicMock()
    openai_mock_resp = MagicMock()
    openai_mock_choice = MagicMock()
    openai_mock_choice.message.content = "OpenAI: Deterministic replay guarantees results."
    openai_mock_choice.finish_reason = "stop"
    openai_mock_resp.choices = [openai_mock_choice]
    openai_client.chat.completions.create.return_value = openai_mock_resp
    orig_openai_call = openai_client.chat.completions.create
    patch(openai_client, provider="openai")

    # B. Groq Client
    groq_client = MagicMock()
    groq_mock_resp = MagicMock()
    groq_mock_choice = MagicMock()
    groq_mock_choice.message.content = "Groq LPU: Deterministic replay eliminates latency."
    groq_mock_choice.finish_reason = "stop"
    groq_mock_resp.choices = [groq_mock_choice]
    groq_client.chat.completions.create.return_value = groq_mock_resp
    orig_groq_call = groq_client.chat.completions.create
    patch(groq_client, provider="groq")

    # C. Mistral Client
    mistral_client = MagicMock()
    mistral_mock_resp = MagicMock()
    mistral_mock_choice = MagicMock()
    mistral_mock_choice.message.content = "Mistral: Deterministic replay enables tests."
    mistral_mock_choice.finish_reason = "stop"
    mistral_mock_resp.choices = [mistral_mock_choice]
    mistral_client.chat.complete.return_value = mistral_mock_resp
    orig_mistral_call = mistral_client.chat.complete
    patch(mistral_client, provider="mistral")

    # D. Ollama (Generic) Client
    ollama_client = MagicMock()
    ollama_mock_resp = MagicMock()
    ollama_mock_choice = MagicMock()
    ollama_mock_choice.message.content = "Ollama Local: Deterministic replay runs offline."
    ollama_mock_choice.finish_reason = "stop"
    ollama_mock_resp.choices = [ollama_mock_choice]
    ollama_client.chat.completions.create.return_value = ollama_mock_resp
    orig_ollama_call = ollama_client.chat.completions.create
    patch(ollama_client, provider="ollama")

    # E. Anthropic Client
    anthropic_client = MagicMock()
    anthropic_mock_resp = {
        "id": "msg_switch_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Claude: Deterministic replay freezes outputs."}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 12, "output_tokens": 10},
    }
    anthropic_client.messages.create.return_value = anthropic_mock_resp
    orig_anthropic_call = anthropic_client.messages.create
    patch(anthropic_client, provider="anthropic")

    providers_to_test = [
        ("openai", "gpt-4o", openai_client, "OpenAI: Deterministic replay"),
        ("groq", "llama-3.1-8b-instant", groq_client, "Groq LPU: Deterministic replay"),
        ("mistral", "mistral-large-latest", mistral_client, "Mistral: Deterministic replay"),
        ("ollama", "llama3.2", ollama_client, "Ollama Local: Deterministic replay"),
        ("anthropic", "claude-3-5-sonnet", anthropic_client, "Claude: Deterministic replay"),
    ]

    # PHASE 1: RECORD MODE (Generate fixtures for each provider)
    for prov_name, model_name, client_obj, expected_substr in providers_to_test:
        session_id = f"switch_{prov_name}"
        with session(name=session_id, mode=ReplayMode.RECORD, config=cfg):
            result = run_llm_pipeline(client_obj, test_prompt, prov_name, model_name)
            assert expected_substr in result

    # Reset all mock call counts
    orig_openai_call.reset_mock()
    orig_groq_call.reset_mock()
    orig_mistral_call.reset_mock()
    orig_ollama_call.reset_mock()
    orig_anthropic_call.reset_mock()

    # PHASE 2: REPLAY MODE (Zero network calls across all 5 providers)
    for prov_name, model_name, client_obj, expected_substr in providers_to_test:
        session_id = f"switch_{prov_name}"
        with session(name=session_id, mode=ReplayMode.REPLAY, config=cfg):
            replayed_result = run_llm_pipeline(client_obj, test_prompt, prov_name, model_name)
            assert expected_substr in replayed_result

    # Verify zero network calls were made in REPLAY mode
    assert orig_openai_call.call_count == 0
    assert orig_groq_call.call_count == 0
    assert orig_mistral_call.call_count == 0
    assert orig_ollama_call.call_count == 0
    assert orig_anthropic_call.call_count == 0

    # Cleanup
    unpatch(openai_client)
    unpatch(groq_client)
    unpatch(mistral_client)
    unpatch(ollama_client)
    unpatch(anthropic_client)
