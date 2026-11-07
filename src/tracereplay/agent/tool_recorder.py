"""Decorator and capture utilities for recording and replaying local Python tools."""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from collections.abc import Callable
from typing import Any, TypeVar, cast, overload

from tracereplay.core.session import get_current_session
from tracereplay.models import ReplayMode, ToolCallRecord

F = TypeVar("F", bound=Callable[..., Any])


@overload
def record_tool(func: F) -> F: ...


@overload
def record_tool(
    func: None = None,
    *,
    name: str | None = None,
    ignore_args: list[str] | None = None,
) -> Callable[[F], F]: ...


def record_tool(
    func: F | None = None,
    *,
    name: str | None = None,
    ignore_args: list[str] | None = None,
) -> F | Callable[[F], F]:
    """Decorator to intercept, record, and re-execute local Python tool functions.

    In RECORD mode:
        Executes the genuine Python function, captures arguments and return value,
        and persists the execution to the session fixture.

    In REPLAY mode:
        Bypasses the actual Python function completely, verifying sequential
        arguments and returning the deterministic recorded output.

    Usage:
        @record_tool
        def calculate_tax(amount: float, rate: float = 0.05) -> float:
            return amount * rate

        @record_tool(name="fetch_user_data", ignore_args=["db_session"])
        async def fetch_user(user_id: str, db_session: Any = None) -> dict:
            return await db.query(user_id)
    """

    def decorator(fn: F) -> F:
        tool_name = name or fn.__name__
        ignored = set(ignore_args or [])
        sig = inspect.signature(fn)

        def _extract_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            extracted: dict[str, Any] = {}
            for k, v in bound.arguments.items():
                if k not in ignored:
                    extracted[k] = v
            return extracted

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                sess = get_current_session()
                if sess is not None:
                    sess.check_fork_trigger(tool_name=tool_name)
                if sess is None or sess.mode == ReplayMode.PASSTHROUGH:
                    res = await fn(*args, **kwargs)
                    if sess is not None:
                        sess.notify_tool_call_completed()
                    return res

                call_args = _extract_args(args, kwargs)

                # AI Chaos Engineering check
                if sess is not None and sess.chaos_engine is not None:
                    await sess.chaos_engine.aevaluate_tool_call(
                        tool_name=tool_name,
                        arguments=call_args,
                        step_index=sess._tool_step_count,
                    )

                if sess.mode == ReplayMode.REPLAY:
                    start = time.perf_counter()
                    res = await sess.areplay_tool_call(tool_name, call_args)
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    if sess.guardrail_engine is not None:
                        sess.guardrail_engine.evaluate_tool_execution(
                            tool_name=tool_name,
                            duration_ms=duration_ms,
                            step_index=sess._total_step_count,
                        )
                    sess.notify_tool_call_completed()
                    return res

                # RECORD mode
                start = time.perf_counter()
                try:
                    res = await fn(*args, **kwargs)
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    record = ToolCallRecord(
                        function_name=tool_name,
                        arguments=call_args,
                        result=res,
                        duration_ms=duration_ms,
                    )
                    sess.record_tool_call(record)
                    if sess.guardrail_engine is not None:
                        sess.guardrail_engine.evaluate_tool_execution(
                            tool_name=tool_name,
                            duration_ms=duration_ms,
                            step_index=sess._total_step_count,
                        )
                    sess.notify_tool_call_completed()
                    return res
                except Exception as err:
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    record = ToolCallRecord(
                        function_name=tool_name,
                        arguments=call_args,
                        result=None,
                        duration_ms=duration_ms,
                        error=str(err),
                    )
                    sess.record_tool_call(record)
                    raise

            return cast(F, async_wrapper)

        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                sess = get_current_session()
                if sess is not None:
                    sess.check_fork_trigger(tool_name=tool_name)
                if sess is None or sess.mode == ReplayMode.PASSTHROUGH:
                    res = fn(*args, **kwargs)
                    if sess is not None:
                        sess.notify_tool_call_completed()
                    return res

                call_args = _extract_args(args, kwargs)

                # AI Chaos Engineering check
                if sess is not None and sess.chaos_engine is not None:
                    sess.chaos_engine.evaluate_tool_call(
                        tool_name=tool_name,
                        arguments=call_args,
                        step_index=sess._tool_step_count,
                    )

                if sess.mode == ReplayMode.REPLAY:
                    start = time.perf_counter()
                    res = sess.replay_tool_call(tool_name, call_args)
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    if sess.guardrail_engine is not None:
                        sess.guardrail_engine.evaluate_tool_execution(
                            tool_name=tool_name,
                            duration_ms=duration_ms,
                            step_index=sess._total_step_count,
                        )
                    sess.notify_tool_call_completed()
                    return res

                # RECORD mode
                start = time.perf_counter()
                try:
                    res = fn(*args, **kwargs)
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    record = ToolCallRecord(
                        function_name=tool_name,
                        arguments=call_args,
                        result=res,
                        duration_ms=duration_ms,
                    )
                    sess.record_tool_call(record)
                    if sess.guardrail_engine is not None:
                        sess.guardrail_engine.evaluate_tool_execution(
                            tool_name=tool_name,
                            duration_ms=duration_ms,
                            step_index=sess._total_step_count,
                        )
                    sess.notify_tool_call_completed()
                    return res
                except Exception as err:
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    record = ToolCallRecord(
                        function_name=tool_name,
                        arguments=call_args,
                        result=None,
                        duration_ms=duration_ms,
                        error=str(err),
                    )
                    sess.record_tool_call(record)
                    raise

            return cast(F, sync_wrapper)

    if func is not None:
        return decorator(func)
    return decorator
