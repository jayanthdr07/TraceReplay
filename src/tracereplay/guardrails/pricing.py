"""Pricing catalog and cost estimation engine for major LLM providers."""

from __future__ import annotations

import re

# Standard model pricing catalog: (input_usd_per_1m_tokens, output_usd_per_1m_tokens)
# Updated to current industry standard rates as of 2025/2026.
STANDARD_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-preview": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),
    # Anthropic
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    # Google Gemini
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-exp": (0.10, 0.40),
    # Groq (hosted open weights)
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.1-70b-versatile": (0.59, 0.79),
    "mixtral-8x7b-32768": (0.24, 0.24),
    "gemma2-9b-it": (0.20, 0.20),
    # Mistral AI
    "mistral-large": (2.00, 6.00),
    "mistral-medium": (2.70, 8.10),
    "mistral-small": (0.20, 0.60),
    "codestral": (0.30, 0.90),
    "open-mistral-7b": (0.25, 0.25),
    "open-mixtral-8x7b": (0.70, 0.70),
    # DeepSeek
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
}

# Conservative default pricing fallback for unknown models (per 1M tokens)
DEFAULT_FALLBACK_PRICING: tuple[float, float] = (1.50, 3.00)


def normalize_model_identifier(model_name: str) -> str:
    """Normalize model identifier for robust catalog matching.

    Examples:
        'gpt-4o-2024-08-06' -> 'gpt-4o'
        'claude-3-5-sonnet-20241022' -> 'claude-3-5-sonnet'
        'gemini-1.5-flash-latest' -> 'gemini-1.5-flash'
        'models/gemini-1.5-pro' -> 'gemini-1.5-pro'
    """
    clean = model_name.lower().strip()
    if clean.startswith("models/"):
        clean = clean[len("models/") :]

    # Strip snapshot date suffixes like -2024-08-06 or -20241022
    clean = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", clean)
    clean = re.sub(r"-\d{8}$", "", clean)
    clean = re.sub(r"-latest$", "", clean)
    clean = re.sub(r":latest$", "", clean)

    return clean


def resolve_model_rates(
    model: str,
    custom_pricing: dict[str, tuple[float, float]] | None = None,
) -> tuple[float, float]:
    """Resolve (prompt_cost_per_1m, completion_cost_per_1m) for a given model."""
    raw_key = model.lower().strip()
    norm_key = normalize_model_identifier(model)

    # 1. Custom user overrides take precedence
    if custom_pricing:
        if raw_key in custom_pricing:
            return custom_pricing[raw_key]
        if norm_key in custom_pricing:
            return custom_pricing[norm_key]
        for pattern, rate in custom_pricing.items():
            if pattern.lower() in raw_key or pattern.lower() in norm_key:
                return rate

    # 2. Standard catalog exact match
    if raw_key in STANDARD_MODEL_PRICING:
        return STANDARD_MODEL_PRICING[raw_key]
    if norm_key in STANDARD_MODEL_PRICING:
        return STANDARD_MODEL_PRICING[norm_key]

    # 3. Fuzzy prefix matching in standard catalog
    for catalog_model, rate in STANDARD_MODEL_PRICING.items():
        if norm_key.startswith(catalog_model) or catalog_model.startswith(norm_key):
            return rate

    # 4. Fallback default rate
    return DEFAULT_FALLBACK_PRICING


def calculate_token_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    custom_pricing: dict[str, tuple[float, float]] | None = None,
) -> float:
    """Calculate the estimated USD cost for an interaction based on prompt and completion tokens.

    Rates are defined per 1,000,000 tokens.
    """
    prompt_rate, completion_rate = resolve_model_rates(model, custom_pricing)
    prompt_cost = (prompt_tokens / 1_000_000.0) * prompt_rate
    completion_cost = (completion_tokens / 1_000_000.0) * completion_rate
    return round(prompt_cost + completion_cost, 6)
