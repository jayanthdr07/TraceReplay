"""TraceReplay: Record once. Replay reliably. Test without repeated API calls.

TraceReplay is an open-source testing platform for applications powered by
Large Language Models (LLMs) and autonomous AI agents.
"""

from __future__ import annotations

from tracereplay import chaos, guardrails, semantic
from tracereplay.agent import AgentStep, AgentStepType, AgentTracker, record_tool
from tracereplay.chaos import ChaosConfig, ChaosEngine, Fault, FaultType
from tracereplay.config import TraceReplayConfig, configure, get_config, reset_config
from tracereplay.core import (
    Recorder,
    Replayer,
    TraceReplaySession,
    get_current_session,
    session,
)
from tracereplay.exceptions import (
    BudgetExceededError,
    ChaosContextLengthError,
    ChaosError,
    ChaosMalformedOutputError,
    ChaosRateLimitError,
    ChaosServerError,
    ChaosTimeoutError,
    ConfigurationError,
    CostBudgetExceededError,
    FixtureNotFoundError,
    InvalidFixtureError,
    LatencyBudgetExceededError,
    LiveFallbackProhibitedError,
    RecordingError,
    RequestMismatchError,
    SemanticDriftError,
    SequenceMismatchError,
    TokenBudgetExceededError,
    ToolExecutionError,
    TraceReplayError,
    UnsupportedOperationError,
)
from tracereplay.guardrails import (
    GuardrailAction,
    GuardrailConfig,
    GuardrailEngine,
    GuardrailReport,
    GuardrailType,
    GuardrailViolation,
    calculate_token_cost,
    cost_budget,
    latency_budget,
    token_budget,
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
from tracereplay.providers import (
    AnthropicAdapter,
    AnthropicMessageResponse,
    BaseProviderAdapter,
    ChatCompletionResponse,
    DeepSeekAdapter,
    GeminiAdapter,
    GeminiGenerateContentResponse,
    GenericOpenAIAdapter,
    GroqAdapter,
    MistralAdapter,
    MistralChatCompletionResponse,
    OllamaAdapter,
    OpenAIAdapter,
    patch,
    unpatch,
)
from tracereplay.sanitizer import Sanitizer, sanitize_data
from tracereplay.semantic import (
    DriftAction,
    DriftReport,
    DriftStatus,
    SemanticConfig,
    SemanticDriftRecord,
    SemanticMatcher,
    calculate_semantic_similarity,
    colorize_diff,
    cosine_similarity_vectors,
    generate_inline_token_diff,
    generate_semantic_diff,
    levenshtein_similarity,
    token_cosine_similarity,
    token_jaccard_similarity,
    tokenize_text,
)
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
    # Core Engines & Sessions
    "session",
    "get_current_session",
    "TraceReplaySession",
    "Recorder",
    "Replayer",
    # Providers & Patching
    "patch",
    "unpatch",
    "BaseProviderAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GeminiAdapter",
    "GroqAdapter",
    "DeepSeekAdapter",
    "OllamaAdapter",
    "MistralAdapter",
    "GenericOpenAIAdapter",
    "ChatCompletionResponse",
    "MistralChatCompletionResponse",
    "AnthropicMessageResponse",
    "GeminiGenerateContentResponse",
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
    "ChaosError",
    "ChaosRateLimitError",
    "ChaosTimeoutError",
    "ChaosServerError",
    "ChaosContextLengthError",
    "ChaosMalformedOutputError",
    "BudgetExceededError",
    "TokenBudgetExceededError",
    "CostBudgetExceededError",
    "LatencyBudgetExceededError",
    "SemanticDriftError",
    # Chaos Engineering
    "chaos",
    "ChaosConfig",
    "ChaosEngine",
    "Fault",
    "FaultType",
    # Guardrails
    "guardrails",
    "GuardrailConfig",
    "GuardrailAction",
    "GuardrailType",
    "GuardrailViolation",
    "GuardrailReport",
    "GuardrailEngine",
    "calculate_token_cost",
    "token_budget",
    "cost_budget",
    "latency_budget",
    # Semantic Matching & Drift Detection
    "semantic",
    "DriftAction",
    "DriftReport",
    "DriftStatus",
    "SemanticConfig",
    "SemanticDriftRecord",
    "SemanticMatcher",
    "calculate_semantic_similarity",
    "colorize_diff",
    "cosine_similarity_vectors",
    "generate_inline_token_diff",
    "generate_semantic_diff",
    "levenshtein_similarity",
    "token_cosine_similarity",
    "token_jaccard_similarity",
    "tokenize_text",
    # Storage & Sanitizer
    "Sanitizer",
    "sanitize_data",
    "JsonStorageEngine",
    "FixtureResolver",
    "sanitize_filename",
    # Matcher
    "RequestMatcher",
    "RequestNormalizer",
    "MatchResult",
    "compute_request_hash",
    "generate_diff",
    # Agent & Tool Recording
    "AgentTracker",
    "AgentStep",
    "AgentStepType",
    "record_tool",
]
