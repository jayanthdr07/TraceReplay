"""Native provider exception synthesizers for OpenAI and Anthropic SDKs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from tracereplay.chaos.models import Fault, FaultType

if TYPE_CHECKING:
    from tracereplay.providers.base import BaseProviderAdapter


def build_native_provider_exception(
    fault: Fault,
    adapter: BaseProviderAdapter,
) -> Exception | None:
    """Attempt to construct a genuine native SDK exception for the target provider."""
    provider_name = getattr(adapter, "provider_name", "").lower()

    if "openai" in provider_name or provider_name in {"generic", "groq", "ollama", "deepseek"}:
        return _build_openai_exception(fault)

    if "anthropic" in provider_name:
        return _build_anthropic_exception(fault)

    return None


def _build_openai_exception(fault: Fault) -> Exception | None:
    """Build a native OpenAI SDK exception if openai and httpx are installed."""
    try:
        import httpx
        import openai

        url = "https://api.openai.com/v1/chat/completions"
        req = httpx.Request("POST", url)

        if fault.fault_type == FaultType.RATE_LIMIT:
            msg = fault.message or "Rate limit exceeded (429 Too Many Requests)"
            headers = {}
            if fault.retry_after is not None:
                headers["retry-after"] = str(fault.retry_after)
            resp = httpx.Response(429, request=req, headers=headers)
            body = {
                "error": {
                    "message": msg,
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                }
            }
            return cast(
                Exception,
                openai.RateLimitError(msg, response=cast(Any, resp), body=body),
            )

        if fault.fault_type == FaultType.TIMEOUT:
            return cast(Exception, openai.APITimeoutError(request=cast(Any, req)))

        if fault.fault_type == FaultType.SERVER_ERROR:
            status = fault.status_code or 500
            msg = fault.message or f"Internal server error ({status})"
            resp = httpx.Response(status, request=req)
            body = {"error": {"message": msg, "type": "server_error"}}
            return cast(
                Exception,
                openai.InternalServerError(msg, response=cast(Any, resp), body=body),
            )

        if fault.fault_type == FaultType.CONTEXT_LENGTH:
            msg = fault.message or "This model's maximum context length exceeded."
            resp = httpx.Response(400, request=req)
            body = {
                "error": {
                    "message": msg,
                    "type": "invalid_request_error",
                    "code": "context_length_exceeded",
                }
            }
            return cast(
                Exception,
                openai.BadRequestError(msg, response=cast(Any, resp), body=body),
            )

    except Exception:
        return None

    return None


def _build_anthropic_exception(fault: Fault) -> Exception | None:
    """Build a native Anthropic SDK exception if anthropic and httpx are installed."""
    try:
        import anthropic  # type: ignore[import-not-found]
        import httpx

        url = "https://api.anthropic.com/v1/messages"
        req = httpx.Request("POST", url)

        if fault.fault_type == FaultType.RATE_LIMIT:
            msg = fault.message or "Rate limit exceeded (429 Too Many Requests)"
            headers = {}
            if fault.retry_after is not None:
                headers["retry-after"] = str(fault.retry_after)
            resp = httpx.Response(429, request=req, headers=headers)
            body = {"error": {"message": msg, "type": "rate_limit_error"}}
            return cast(
                Exception,
                anthropic.RateLimitError(msg, response=cast(Any, resp), body=body),
            )

        if fault.fault_type == FaultType.TIMEOUT:
            return cast(Exception, anthropic.APITimeoutError(request=cast(Any, req)))

        if fault.fault_type == FaultType.SERVER_ERROR:
            status = fault.status_code or 500
            msg = fault.message or f"Internal server error ({status})"
            resp = httpx.Response(status, request=req)
            body = {"error": {"message": msg, "type": "server_error"}}
            return cast(
                Exception,
                anthropic.InternalServerError(msg, response=cast(Any, resp), body=body),
            )

        if fault.fault_type == FaultType.CONTEXT_LENGTH:
            msg = fault.message or "Prompt exceeds maximum context length."
            resp = httpx.Response(400, request=req)
            body = {"error": {"message": msg, "type": "invalid_request_error"}}
            return cast(
                Exception,
                anthropic.BadRequestError(msg, response=cast(Any, resp), body=body),
            )

    except Exception:
        return None

    return None
