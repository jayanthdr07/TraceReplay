"""Data models and schemas for semantic matching and prompt drift detection."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DriftStatus(str, Enum):
    """Classification of request similarity against recorded fixtures."""

    EXACT_MATCH = "exact_match"
    SEMANTIC_MATCH = "semantic_match"
    DRIFT_EXCEEDED = "drift_exceeded"
    STRUCTURAL_MISMATCH = "structural_mismatch"


class DriftAction(str, Enum):
    """Behavioral policy when semantic drift is detected within threshold."""

    ACCEPT = "accept"
    WARN = "warn"
    RAISE = "raise"


class SemanticDriftRecord(BaseModel):
    """Record of a single interaction's prompt drift evaluation."""

    model_config = ConfigDict(frozen=True)

    step_index: int
    similarity_score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    status: DriftStatus
    expected_text: str = ""
    actual_text: str = ""
    token_similarity: float = Field(default=1.0, ge=0.0, le=1.0)
    char_similarity: float = Field(default=1.0, ge=0.0, le=1.0)
    diff: str | None = None
    inline_diff: str | None = None
    added_tokens: list[str] = Field(default_factory=list)
    removed_tokens: list[str] = Field(default_factory=list)
    differences: list[str] = Field(default_factory=list)
    matched_index: int | None = None

    @property
    def is_match(self) -> bool:
        """Return True if request is accepted as match (exact or within threshold)."""
        return self.status in (DriftStatus.EXACT_MATCH, DriftStatus.SEMANTIC_MATCH)

    def to_dict(self) -> dict[str, Any]:
        """Convert record to a serializable dictionary."""
        return {
            "step_index": self.step_index,
            "similarity_score": round(self.similarity_score, 4),
            "threshold": self.threshold,
            "status": self.status.value,
            "token_similarity": round(self.token_similarity, 4),
            "char_similarity": round(self.char_similarity, 4),
            "added_tokens": self.added_tokens,
            "removed_tokens": self.removed_tokens,
            "differences": self.differences,
            "matched_index": self.matched_index,
        }


class SemanticConfig(BaseModel):
    """Configuration options for semantic matching and drift evaluation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    enabled: bool = False
    threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    action: DriftAction = DriftAction.ACCEPT
    match_model: bool = True
    match_provider: bool = True
    match_tools: bool = True
    ignore_whitespace: bool = True
    ignore_case: bool = False
    embedding_fn: Callable[[str], list[float]] | None = None


class DriftReport(BaseModel):
    """Cumulative report of semantic drift across all replayed interactions."""

    records: list[SemanticDriftRecord] = Field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        """Return True if any interaction experienced prompt drift from the baseline."""
        return any(r.status != DriftStatus.EXACT_MATCH for r in self.records)

    @property
    def has_violations(self) -> bool:
        """Return True if any interaction drifted beyond the allowed threshold."""
        return any(
            r.status in (DriftStatus.DRIFT_EXCEEDED, DriftStatus.STRUCTURAL_MISMATCH)
            for r in self.records
        )

    @property
    def total_replays(self) -> int:
        """Return total number of evaluated replay interactions."""
        return len(self.records)

    @property
    def min_similarity(self) -> float:
        """Return minimum observed similarity score across all steps."""
        if not self.records:
            return 1.0
        return min(r.similarity_score for r in self.records)

    @property
    def average_similarity(self) -> float:
        """Return arithmetic mean similarity score across all steps."""
        if not self.records:
            return 1.0
        return sum(r.similarity_score for r in self.records) / len(self.records)

    def summary_text(self) -> str:
        """Format an informative summary table of drift metrics across steps."""
        lines = [
            "==================================================================",
            "                TraceReplay Semantic Drift Report                 ",
            "==================================================================",
            f" Total Interactions: {self.total_replays}",
            f" Has Drift:         {'YES' if self.has_drift else 'NO'}",
            f" Min Similarity:    {self.min_similarity:.2%}",
            f" Avg Similarity:    {self.average_similarity:.2%}",
            "------------------------------------------------------------------",
            " Step | Status             | Similarity | Threshold | Diff Tokens",
            "------------------------------------------------------------------",
        ]

        if not self.records:
            lines.append("  (No interactions evaluated)")
        else:
            for r in self.records:
                status_str = r.status.value.ljust(18)
                diff_summary = f"+{len(r.added_tokens)} / -{len(r.removed_tokens)}"
                lines.append(
                    f" {r.step_index:>4} | {status_str} | "
                    f"{r.similarity_score:>9.2%} | {r.threshold:>8.2%} | {diff_summary}"
                )

        lines.append("==================================================================")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert full report to a serializable dictionary."""
        return {
            "total_replays": self.total_replays,
            "has_drift": self.has_drift,
            "has_violations": self.has_violations,
            "min_similarity": round(self.min_similarity, 4),
            "average_similarity": round(self.average_similarity, 4),
            "records": [r.to_dict() for r in self.records],
        }
