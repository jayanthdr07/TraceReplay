"""Semantic Diff & Smart Drift Detection for TraceReplay.

Enables fuzzy and semantic request matching, visual drift diagnostics,
and prompt evolution tracking across recorded replay sessions.
"""

from __future__ import annotations

from tracereplay.semantic.diff import (
    colorize_diff,
    generate_inline_token_diff,
    generate_semantic_diff,
)
from tracereplay.semantic.engine import SemanticMatcher
from tracereplay.semantic.models import (
    DriftAction,
    DriftReport,
    DriftStatus,
    SemanticConfig,
    SemanticDriftRecord,
)
from tracereplay.semantic.similarity import (
    calculate_semantic_similarity,
    cosine_similarity_vectors,
    levenshtein_similarity,
    token_cosine_similarity,
    token_jaccard_similarity,
    tokenize_text,
)

__all__ = [
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
]
