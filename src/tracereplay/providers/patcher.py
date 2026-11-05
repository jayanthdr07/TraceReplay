# Client patcher and method interceptor for TraceReplay.

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from tracereplay.core.session import get_current_session
from tracereplay.exceptions import TraceReplayError
from tracereplay.models import ReplayMode
from tracereplay.providers.openai import OpenAIAdapter


class PatchHandle:
    # Manages the lifecycle of patched methods on an AI client.

    def __init__(
        self,
        target: Any,
        original_create: Callable[..., Any],
        patched_create: Callable[..., Any],
    ) -> None:
        self.target = target
        self.original_create = original_create
        self.patched_create = patched_create

    def unpatch(self) -> None:
        # Restore original create method on the client
        if hasattr(self.target, "chat") and hasattr(self.target.chat, "completions"):
            self.target.chat.completions.create = self.original_create

    def __enter__(self) -> Any:
        return self.target

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.unpatch()


def patch(client: Any) -> Any:
    # Wrap an OpenAI or AsyncOpenAI client with TraceReplay interceptors
    if not hasattr(client, "chat") or not hasattr(client.chat, "completions"):
        raise TraceReplayError(
            "Target client does not have client.chat.completions.create."
            "Ensure you pass an instantiated OpenAI or AsyncOpenAI client."
        )

    original_create = client.chat.completions.create
    adapter = OpenAIAdapter()
    is_async = asyncio.iscoroutinefunction(original_create)

    if is_async:

        async def async_intercepted_create(*args: Any, **kwargs: Any) -> Any:
            sess = get_current_session()
            if sess is None or sess.mode == ReplayMode.PASSTHROUGH:
                return await original_create(*args, **kwargs)

            request = adapter.before_request(*args, **kwargs)

            if sess.mode == ReplayMode.RECORD:
                start = time.perf_counter()
                raw_response = await original_create(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000.0
                response_payload = adapter.after_response(raw_response)
                if sess.recorder:
                    sess.recorder.record_interaction(
                        request, response_payload, duration_ms=duration_ms
                    )
                return raw_response

            if sess.mode == ReplayMode.REPLAY:
                if sess.replayer is None:
                    raise TraceReplayError("No replayer active in session")
                replayed_payload = await sess.replayer.areplay_interaction(request)
                return adapter.build_replayed_response(replayed_payload, request)

            return await original_create(*args, **kwargs)

        client.chat.completions.create = async_intercepted_create
        handle = PatchHandle(client, original_create, async_intercepted_create)
    else:

        def sync_intercepted_create(*args: Any, **kwargs: Any) -> Any:
            sess = get_current_session()
            if sess is None or sess.mode == ReplayMode.PASSTHROUGH:
                return original_create(*args, **kwargs)

            request = adapter.before_request(*args, **kwargs)

            if sess.mode == ReplayMode.RECORD:
                start = time.perf_counter()
                raw_response = original_create(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000.0
                response_payload = adapter.after_response(raw_response)
                if sess.recorder:
                    sess.recorder.record_interaction(
                        request, response_payload, duration_ms=duration_ms
                    )
                return raw_response

            if sess.mode == ReplayMode.REPLAY:
                if sess.replayer is None:
                    raise TraceReplayError("No replayer active in session")
                replayed_payload = sess.replayer.replay_interaction(request)
                return adapter.build_replayed_response(replayed_payload, request)

            return original_create(*args, **kwargs)

        client.chat.completions.create = sync_intercepted_create
        handle = PatchHandle(client, original_create, sync_intercepted_create)

    client.__enter__ = handle.__enter__
    client.__exit__ = handle.__exit__
    client.unpatch = handle.unpatch
    return client


def unpatch(client: Any) -> Any:
    # Convenience helper to unpatch an AI client.
    if hasattr(client, "unpatch"):
        client.unpatch()
    return client
