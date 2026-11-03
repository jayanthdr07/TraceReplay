"""Matching engine for comparing application requests against recorded fixtures."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.exceptions import RequestMismatchError
from tracereplay.matcher.diff import generate_diff
from tracereplay.matcher.normalizer import RequestNormalizer
from tracereplay.models import Interaction, RequestPayload, SessionRecord


class MatchResult(BaseModel):
    """Result of comparing an incoming request against an expected request."""

    model_config = ConfigDict(frozen=True)

    is_match: bool
    differences: list[str] = Field(default_factory=list)
    diff: str | None = Field(default=None)
    matched_index: int | None = Field(default=None)
    expected: dict[str, Any] | None = Field(default=None)
    actual: dict[str, Any] | None = Field(default=None)


class RequestMatcher:
    """Compares incoming requests against recorded fixtures with configurable rules."""

    def __init__(
        self,
        config: TraceReplayConfig | None = None,
        normalizer: RequestNormalizer | None = None,
    ) -> None:
        self.config = config or get_config()
        self.normalizer = normalizer or RequestNormalizer(config=self.config)

    def compare(self, expected: RequestPayload, actual: RequestPayload) -> MatchResult:
        """Compare an expected RequestPayload with an actual incoming RequestPayload."""
        norm_expected = self.normalizer.normalize_request(expected)
        norm_actual = self.normalizer.normalize_request(actual)

        differences: list[str] = []

        # 1. Compare Provider
        if norm_expected["provider"] != norm_actual["provider"]:
            differences.append(
                f"Provider mismatch: expected '{norm_expected['provider']}', "
                f"got '{norm_actual['provider']}'"
            )

        # 2. Compare Model
        if norm_expected["model"] != norm_actual["model"]:
            differences.append(
                f"Model mismatch: expected '{norm_expected['model']}', got '{norm_actual['model']}'"
            )

        # 3. Compare Operation
        if norm_expected["operation"] != norm_actual["operation"]:
            differences.append(
                f"Operation mismatch: expected '{norm_expected['operation']}', "
                f"got '{norm_actual['operation']}'"
            )

        # 4. Compare Prompt (if set)
        if norm_expected["prompt"] != norm_actual["prompt"]:
            differences.append("Prompt text does not match")

        # 5. Compare Messages
        if norm_expected["messages"] != norm_actual["messages"]:
            if len(norm_expected["messages"]) != len(norm_actual["messages"]):
                differences.append(
                    f"Messages count mismatch: expected {len(norm_expected['messages'])} messages, "
                    f"got {len(norm_actual['messages'])} messages"
                )
            else:
                differences.append("Messages content mismatch: message roles or contents differ")

        # 6. Compare Parameters (if enabled)
        if (
            self.config.match_parameters
            and norm_expected["parameters"] != norm_actual["parameters"]
        ):
            differences.append("Parameters mismatch")

        # 7. Compare Tools
        if norm_expected["tools"] != norm_actual["tools"]:
            differences.append("Tools declarations mismatch")

        if not differences:
            return MatchResult(
                is_match=True,
                expected=norm_expected,
                actual=norm_actual,
            )

        diff_text = generate_diff(norm_expected, norm_actual)
        return MatchResult(
            is_match=False,
            differences=differences,
            diff=diff_text,
            expected=norm_expected,
            actual=norm_actual,
        )

    def match_interaction(self, actual: RequestPayload, interaction: Interaction) -> MatchResult:
        """Compare an incoming request against a specific recorded Interaction."""
        res = self.compare(interaction.request, actual)
        return MatchResult(
            is_match=res.is_match,
            differences=res.differences,
            diff=res.diff,
            matched_index=interaction.index if res.is_match else None,
            expected=res.expected,
            actual=res.actual,
        )

    def find_match(
        self, actual: RequestPayload, session: SessionRecord, start_index: int = 0
    ) -> tuple[Interaction | None, MatchResult]:
        """Find the matching interaction within a session starting from start_index.

        In sequential mode, checks session.interactions[start_index].
        If not strictly sequential, searches remaining interactions.
        """
        interactions = session.interactions
        if not interactions:
            return None, MatchResult(
                is_match=False,
                differences=["Session contains zero recorded interactions"],
            )

        if self.config.strict_ordering:
            if start_index >= len(interactions):
                return None, MatchResult(
                    is_match=False,
                    differences=[
                        f"Interaction sequence exhausted: request index {start_index} "
                        f"exceeds recorded session length ({len(interactions)})"
                    ],
                )
            expected_interaction = interactions[start_index]
            res = self.match_interaction(actual, expected_interaction)
            return (expected_interaction if res.is_match else None), res

        # Unordered search across all remaining interactions
        best_result: MatchResult | None = None
        for item in interactions[start_index:]:
            res = self.match_interaction(actual, item)
            if res.is_match:
                return item, res
            if best_result is None:
                best_result = res

        return None, (best_result or MatchResult(is_match=False))

    def validate_or_raise(
        self,
        expected: RequestPayload,
        actual: RequestPayload,
        interaction_index: int | None = None,
    ) -> None:
        """Compare requests and raise RequestMismatchError if they differ."""
        res = self.compare(expected, actual)
        if not res.is_match:
            diff_msg = res.diff or "\n".join(res.differences)
            summary = "; ".join(res.differences)
            index_str = (
                f" at interaction index {interaction_index}"
                if interaction_index is not None
                else ""
            )
            raise RequestMismatchError(
                f"Request mismatch{index_str}: {summary}\n{diff_msg}",
                expected=res.expected,
                actual=res.actual,
                diff=res.diff,
                interaction_index=interaction_index,
            )
