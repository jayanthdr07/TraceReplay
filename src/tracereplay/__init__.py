"""TraceReplay: Record once. Replay reliably. Test without repeated API calls.

TraceReplay is an open-source testing platform for applications powered by
Large Language Models (LLMs) and autonomous AI agents.
"""

from __future__ import annotations

from tracereplay.config import TraceReplayConfig, configure, get_config, reset_config
from tracereplay.exceptions import (
    ConfigurationError,
    FixtureNotFoundError,
    InvalidFixtureError,
    LiveFallbackProhibitedError,
    RecordingError,
    RequestMismatchError,
    SequenceMismatchError,
    ToolExecutionError,
    TraceReplayError,
    UnsupportedOperationError,
)
from tracereplay.matcher import (
    MatchResult,
    RequestMatcher,
    RequestNormalizer,
    compute_request_hash,
    generate_diff,
)
from tracereplay.models import (
    Interaction,
    OperationType,
    ReplayMode,
    RequestPayload,
    ResponsePayload,
    SessionRecord,
    TokenUsage,
    ToolCallRecord,
)
from tracereplay.sanitizer import Sanitizer, sanitize_data
from tracereplay.storage import FixtureResolver, JsonStorageEngine, sanitize_filename

__version__ = "0.1.0"
__author__ = "TraceReplay Contributors"
__license__ = "MIT"

__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__license__",
    # Configuration
    "TraceReplayConfig",
    "get_config",
    "configure",
    "reset_config",
    # Models & Enums
    "ReplayMode",
    "OperationType",
    "TokenUsage",
    "ToolCallRecord",
    "RequestPayload",
    "ResponsePayload",
    "Interaction",
    "SessionRecord",
    # Exceptions
    "TraceReplayError",
    "ConfigurationError",
    "FixtureNotFoundError",
    "RequestMismatchError",
    "InvalidFixtureError",
    "LiveFallbackProhibitedError",
    "UnsupportedOperationError",
    "SequenceMismatchError",
    "RecordingError",
    "ToolExecutionError",
    # Storage & Sanitization
    "Sanitizer",
    "sanitize_data",
    "FixtureResolver",
    "JsonStorageEngine",
    "sanitize_filename",
    # Matcher
    "RequestNormalizer",
    "RequestMatcher",
    "MatchResult",
    "compute_request_hash",
    "generate_diff",
]
