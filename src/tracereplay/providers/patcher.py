"""Client patcher and method interceptor for TraceReplay."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from tracereplay.core.session import get_current_session
from tracereplay.exceptions import TraceReplayError
from tracereplay.models import ReplayMode
from tracereplay.providers.anthropic import AnthropicAdapter
from tracereplay.providers.base import BaseProviderAdapter
from tracereplay.providers.gemini import GeminiAdapter
from tracereplay.providers.generic import GenericOpenAIAdapter
from tracereplay.providers.groq import DeepSeekAdapter, GroqAdapter, OllamaAdapter
from tracereplay.providers.mistral import MistralAdapter
from tracereplay.providers.openai import OpenAIAdapter


class PatchHandle:
    """Manages the lifecycle of patched methods on an AI client."""

    def __init__(
        self,
        target: Any,
        restore_fn: Callable[[], None],
    ) -> None:
        self.target = target
        self.restore_fn = restore_fn

    def unpatch(self) -> None:
        """Restore original unintercepted method on the client."""
        self.restore_fn()

    def __enter__(self) -> Any:
        return self.target

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.unpatch()


def _resolve_adapter(client: Any, provider: str | None = None) -> BaseProviderAdapter:
    """Resolve the appropriate provider adapter based on client type or provider hint."""
    prov_hint = (provider or "").lower().strip()
    class_name = client.__class__.__name__.lower()
    module_name = getattr(client.__class__, "__module__", "").lower()
    base_url = str(getattr(client, "base_url", "")).lower()

    if prov_hint == "openai" or "openai" in class_name or "openai" in module_name:
        return OpenAIAdapter()
    if prov_hint == "mistral" or "mistral" in class_name or "mistral" in module_name:
        return MistralAdapter()
    if prov_hint == "anthropic" or "anthropic" in class_name or "anthropic" in module_name:
        return AnthropicAdapter()
    if prov_hint == "gemini" or "gemini" in class_name or "google" in module_name:
        return GeminiAdapter()
    if prov_hint == "groq" or "groq" in class_name or "groq" in module_name:
        return GroqAdapter()
    if prov_hint == "deepseek" or "deepseek" in class_name or "deepseek" in module_name:
        return DeepSeekAdapter()
    if (
        prov_hint == "ollama"
        or "ollama" in class_name
        or "ollama" in module_name
        or ":11434" in base_url
    ):
        return OllamaAdapter()
    if prov_hint == "generic" or ":8000" in base_url or ":1234" in base_url or ":8080" in base_url:
        return GenericOpenAIAdapter(provider_alias=prov_hint or "generic")

    # Structural fallback based on method signatures
    if hasattr(client, "chat") and hasattr(client.chat, "complete"):
        return MistralAdapter()
    if hasattr(client, "messages") and hasattr(client.messages, "create"):
        return AnthropicAdapter()
    if hasattr(client, "generate_content"):
        return GeminiAdapter()
    if hasattr(client, "chat") and hasattr(client.chat, "completions"):
        if prov_hint in {"generic", "vllm", "localai", "lmstudio"}:
            return GenericOpenAIAdapter(provider_alias=prov_hint)
        return OpenAIAdapter()

    raise TraceReplayError(
        f"Unable to auto-detect provider for client '{type(client).__name__}'. "
        "Pass provider='openai' | 'anthropic' | 'gemini' | 'groq' | "
        "'mistral' | 'generic' | 'ollama'."
    )


def patch(client: Any, provider: str | None = None) -> Any:
    """Wrap an AI client with TraceReplay interceptors."""
    adapter = _resolve_adapter(client, provider=provider)

    def _sync_intercept(orig_fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        sess = get_current_session()
        if sess is not None:
            sess.check_fork_trigger()
        if sess is None or sess.mode == ReplayMode.PASSTHROUGH:
            res = orig_fn(*args, **kwargs)
            if sess is not None:
                sess.notify_llm_call_completed()
            return res

        request = adapter.before_request(*args, **kwargs)

        # AI Chaos Engineering check
        if sess is not None and sess.chaos_engine is not None:
            chaos_response = sess.chaos_engine.evaluate_pre_request(
                adapter=adapter,
                request=request,
                step_index=sess._llm_step_count,
            )
            if chaos_response is not None:
                sess.notify_llm_call_completed()
                return chaos_response

        if sess.mode == ReplayMode.RECORD:
            start = time.perf_counter()
            raw_response = orig_fn(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000.0
            response_payload = adapter.after_response(raw_response)
            if sess.recorder:
                sess.recorder.record_interaction(request, response_payload, duration_ms=duration_ms)
            sess.notify_llm_call_completed()
            return raw_response

        if sess.mode == ReplayMode.REPLAY:
            if sess.replayer is None:
                raise TraceReplayError("No replayer active in session")
            replayed_payload = sess.replayer.replay_interaction(request)
            res = adapter.build_replayed_response(replayed_payload, request)
            sess.notify_llm_call_completed()
            return res

        res = orig_fn(*args, **kwargs)
        sess.notify_llm_call_completed()
        return res

    async def _async_intercept(orig_fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        sess = get_current_session()
        if sess is not None:
            sess.check_fork_trigger()
        if sess is None or sess.mode == ReplayMode.PASSTHROUGH:
            res = await orig_fn(*args, **kwargs)
            if sess is not None:
                sess.notify_llm_call_completed()
            return res

        request = adapter.before_request(*args, **kwargs)

        # AI Chaos Engineering check
        if sess is not None and sess.chaos_engine is not None:
            chaos_response = await sess.chaos_engine.aevaluate_pre_request(
                adapter=adapter,
                request=request,
                step_index=sess._llm_step_count,
            )
            if chaos_response is not None:
                sess.notify_llm_call_completed()
                return chaos_response

        if sess.mode == ReplayMode.RECORD:
            start = time.perf_counter()
            raw_response = await orig_fn(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000.0
            response_payload = adapter.after_response(raw_response)
            if sess.recorder:
                sess.recorder.record_interaction(request, response_payload, duration_ms=duration_ms)
            sess.notify_llm_call_completed()
            return raw_response

        if sess.mode == ReplayMode.REPLAY:
            if sess.replayer is None:
                raise TraceReplayError("No replayer active in session")
            replayed_payload = await sess.replayer.areplay_interaction(request)
            res = adapter.build_replayed_response(replayed_payload, request)
            sess.notify_llm_call_completed()
            return res

        res = await orig_fn(*args, **kwargs)
        sess.notify_llm_call_completed()
        return res

    # 1. Mistral AI (client.chat.complete / client.chat.complete_async)
    if isinstance(adapter, MistralAdapter):
        if not hasattr(client, "chat") or not hasattr(client.chat, "complete"):
            raise TraceReplayError("Mistral client must have client.chat.complete")

        orig_complete = client.chat.complete
        orig_async_complete = getattr(client.chat, "complete_async", None)

        def sync_mistral_create(*args: Any, **kwargs: Any) -> Any:
            return _sync_intercept(orig_complete, *args, **kwargs)

        client.chat.complete = sync_mistral_create

        if orig_async_complete is not None:

            async def async_mistral_create(*args: Any, **kwargs: Any) -> Any:
                return await _async_intercept(orig_async_complete, *args, **kwargs)

            client.chat.complete_async = async_mistral_create

        def restore_mistral() -> None:
            client.chat.complete = orig_complete
            if orig_async_complete is not None:
                client.chat.complete_async = orig_async_complete

        handle = PatchHandle(client, restore_mistral)
        client.__enter__ = handle.__enter__
        client.__exit__ = handle.__exit__
        client.unpatch = handle.unpatch
        return client

    # 2. Anthropic Claude (client.messages.create)
    if isinstance(adapter, AnthropicAdapter):
        if not hasattr(client, "messages") or not hasattr(client.messages, "create"):
            raise TraceReplayError("Anthropic client must have client.messages.create")
        orig_anthropic = client.messages.create
        is_async = asyncio.iscoroutinefunction(orig_anthropic)

        if is_async:

            async def async_anthropic_create(*args: Any, **kwargs: Any) -> Any:
                return await _async_intercept(orig_anthropic, *args, **kwargs)

            client.messages.create = async_anthropic_create
        else:

            def sync_anthropic_create(*args: Any, **kwargs: Any) -> Any:
                return _sync_intercept(orig_anthropic, *args, **kwargs)

            client.messages.create = sync_anthropic_create

        handle = PatchHandle(client, lambda: setattr(client.messages, "create", orig_anthropic))
        client.__enter__ = handle.__enter__
        client.__exit__ = handle.__exit__
        client.unpatch = handle.unpatch
        return client

    # 3. Google Gemini (model.generate_content)
    if isinstance(adapter, GeminiAdapter):
        if not hasattr(client, "generate_content"):
            raise TraceReplayError("Gemini model/client must have client.generate_content")
        orig_gemini = client.generate_content
        is_async = asyncio.iscoroutinefunction(orig_gemini)

        if is_async:

            async def async_gemini_create(*args: Any, **kwargs: Any) -> Any:
                return await _async_intercept(orig_gemini, *args, **kwargs)

            client.generate_content = async_gemini_create
        else:

            def sync_gemini_create(*args: Any, **kwargs: Any) -> Any:
                return _sync_intercept(orig_gemini, *args, **kwargs)

            client.generate_content = sync_gemini_create

        handle = PatchHandle(client, lambda: setattr(client, "generate_content", orig_gemini))
        client.__enter__ = handle.__enter__
        client.__exit__ = handle.__exit__
        client.unpatch = handle.unpatch
        return client

    # 4. OpenAI / Groq / DeepSeek / Ollama / Generic (client.chat.completions.create)
    if not hasattr(client, "chat") or not hasattr(client.chat, "completions"):
        raise TraceReplayError(
            "Target client does not have client.chat.completions.create. "
            "Ensure you pass an instantiated OpenAI, Groq, DeepSeek, Ollama, or Generic client."
        )

    orig_openai = client.chat.completions.create
    is_async = asyncio.iscoroutinefunction(orig_openai)

    if is_async:

        async def async_intercepted_create(*args: Any, **kwargs: Any) -> Any:
            return await _async_intercept(orig_openai, *args, **kwargs)

        client.chat.completions.create = async_intercepted_create
    else:

        def sync_intercepted_create(*args: Any, **kwargs: Any) -> Any:
            return _sync_intercept(orig_openai, *args, **kwargs)

        client.chat.completions.create = sync_intercepted_create

    handle = PatchHandle(client, lambda: setattr(client.chat.completions, "create", orig_openai))
    client.__enter__ = handle.__enter__
    client.__exit__ = handle.__exit__
    client.unpatch = handle.unpatch
    return client


def unpatch(client: Any) -> Any:
    """Convenience helper to unpatch an AI client."""
    if hasattr(client, "unpatch"):
        client.unpatch()
    return client
