"""Pure-Python deterministic semantic similarity and distance algorithms.

Provides token-level cosine similarity, sequence ratio, token Jaccard overlap,
and pluggable high-dimensional vector cosine similarity.
"""

from __future__ import annotations

import collections
import difflib
import math
import re
from collections.abc import Callable

_TOKEN_PATTERN = re.compile(r"[\w]+|[^\w\s]")


def tokenize_text(text: str) -> list[str]:
    """Tokenize a text string into normalized lowercase word and symbol tokens."""
    if not text:
        return []
    return [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text)]


def cosine_similarity_vectors(vec1: list[float], vec2: list[float]) -> float:
    """Compute vector cosine similarity between two numeric lists.

    Returns a float in the range [0.0, 1.0].
    """
    if not vec1 or not vec2:
        return 0.0
    if len(vec1) != len(vec2):
        raise ValueError(
            f"Vector dimension mismatch: len(vec1)={len(vec1)} != len(vec2)={len(vec2)}"
        )

    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))

    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0 if norm_a == norm_b else 0.0

    similarity = dot_product / (norm_a * norm_b)
    return max(0.0, min(1.0, float(similarity)))


def token_cosine_similarity(text1: str, text2: str) -> float:
    """Compute term frequency cosine similarity between two text strings."""
    if text1 == text2:
        return 1.0
    if not text1.strip() or not text2.strip():
        return 1.0 if not text1.strip() and not text2.strip() else 0.0

    tokens1 = [t for t in tokenize_text(text1) if t.isalnum()]
    tokens2 = [t for t in tokenize_text(text2) if t.isalnum()]

    # Fallback to all tokens if text consists purely of punctuation
    if not tokens1 or not tokens2:
        tokens1 = tokenize_text(text1)
        tokens2 = tokenize_text(text2)

    if not tokens1 or not tokens2:
        return 0.0

    c1: collections.Counter[str] = collections.Counter(tokens1)
    c2: collections.Counter[str] = collections.Counter(tokens2)

    all_keys = set(c1.keys()) | set(c2.keys())
    dot_product = sum(c1.get(key, 0) * c2.get(key, 0) for key in all_keys)
    norm1_sq = sum(v * v for v in c1.values())
    norm2_sq = sum(v * v for v in c2.values())

    if norm1_sq == 0.0 or norm2_sq == 0.0:
        return 0.0

    similarity = dot_product / (math.sqrt(norm1_sq) * math.sqrt(norm2_sq))
    return max(0.0, min(1.0, float(similarity)))


def levenshtein_similarity(text1: str, text2: str) -> float:
    """Compute normalized sequence similarity ratio using stdlib difflib."""
    if text1 == text2:
        return 1.0
    matcher = difflib.SequenceMatcher(None, text1, text2)
    return max(0.0, min(1.0, float(matcher.ratio())))


def token_jaccard_similarity(tokens1: list[str], tokens2: list[str]) -> float:
    """Compute Jaccard token set overlap similarity |A ∩ B| / |A ∪ B|."""
    set1 = set(tokens1)
    set2 = set(tokens2)
    if not set1 and not set2:
        return 1.0
    intersection = set1 & set2
    union = set1 | set2
    if not union:
        return 0.0
    return len(intersection) / len(union)


def calculate_semantic_similarity(
    text1: str,
    text2: str,
    embedding_fn: Callable[[str], list[float]] | None = None,
) -> float:
    """Calculate overall semantic similarity score in the range [0.0, 1.0].

    When embedding_fn is provided, computes high-dimensional vector cosine similarity.
    Otherwise, computes a balanced hybrid of word token cosine and lowercase sequence ratio.
    """
    if text1 == text2:
        return 1.0

    t1_clean = text1.strip()
    t2_clean = text2.strip()
    if not t1_clean or not t2_clean:
        return 1.0 if not t1_clean and not t2_clean else 0.0

    if embedding_fn is not None:
        vec1 = embedding_fn(text1)
        vec2 = embedding_fn(text2)
        return cosine_similarity_vectors(vec1, vec2)

    # Pure-Python hybrid: 50% word token cosine + 50% lowercase sequence ratio
    t1_lower = t1_clean.lower()
    t2_lower = t2_clean.lower()
    token_score = token_cosine_similarity(t1_lower, t2_lower)
    seq_score = levenshtein_similarity(t1_lower, t2_lower)

    hybrid = (0.50 * token_score) + (0.50 * seq_score)
    return max(0.0, min(1.0, float(hybrid)))
