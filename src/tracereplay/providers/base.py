"""Abstract base class for LLM provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from tracereplay.models import RequestPayload, ResponsePayload


class BaseProviderAdapter(ABC):
    """Abstract interface defining provider-specific request and response transformations."""

    provider_name: str = "base"

    @abstractmethod
    def before_request(self, *args: Any, **kwargs: Any) -> RequestPayload:
        """Convert native provider SDK call arguments into a RequestPayload."""
        raise NotImplementedError

    @abstractmethod
    def after_response(self, raw_response: Any) -> ResponsePayload:
        """Convert native provider SDK response into a ResponsePayload."""
        raise NotImplementedError

    @abstractmethod
    def build_replayed_response(
        self, response_payload: ResponsePayload, request: RequestPayload
    ) -> Any:
        """Reconstruct a native provider SDK response object from ResponsePayload."""
        raise NotImplementedError

    def on_error(self, error: Exception) -> None:  # noqa: B027
        """Optional lifecycle hook called when a live provider request raises an error."""
