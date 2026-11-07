"""Semantic matching engine for evaluating prompt drift against recorded fixtures."""

from __future__ import annotations

import json

from tracereplay.config import TraceReplayConfig, get_config
from tracereplay.models import Interaction, RequestPayload, SessionRecord
from tracereplay.semantic.diff import (
    generate_inline_token_diff,
    generate_semantic_diff,
)
from tracereplay.semantic.models import (
    DriftReport,
    DriftStatus,
    SemanticConfig,
    SemanticDriftRecord,
)
from tracereplay.semantic.similarity import (
    calculate_semantic_similarity,
    levenshtein_similarity,
    token_cosine_similarity,
)


class SemanticMatcher:
    """Evaluates semantic similarity and tracks prompt drift against recorded fixtures."""

    def __init__(
        self,
        config: SemanticConfig | None = None,
        global_config: TraceReplayConfig | None = None,
    ) -> None:
        self.config = config or SemanticConfig()
        self.global_config = global_config or get_config()
        self.report = DriftReport()

    def extract_prompt_text(self, request: RequestPayload) -> str:
        """Extract a single normalized text representation from prompt or messages."""
        if request.prompt:
            return request.prompt.strip()

        if not request.messages:
            return ""

        parts: list[str] = []
        for msg in request.messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(f"[{role}] {content.strip()}")
            elif isinstance(content, list):
                # Multimodal or structured content blocks
                block_texts: list[str] = []
                for b in content:
                    if isinstance(b, dict) and "text" in b:
                        block_texts.append(str(b["text"]).strip())
                    elif isinstance(b, str):
                        block_texts.append(b.strip())
                parts.append(f"[{role}] {' '.join(block_texts)}")
            elif content is not None:
                parts.append(f"[{role}] {json.dumps(content, sort_keys=True)}")

        return "\n".join(parts)

    def compare_semantic(
        self,
        expected: RequestPayload,
        actual: RequestPayload,
        step_index: int = 0,
        matched_index: int | None = None,
    ) -> SemanticDriftRecord:
        """Compare expected and actual requests using semantic similarity analysis."""
        differences: list[str] = []

        # 1. Structural checks
        if (
            self.config.match_provider
            and expected.provider.lower().strip() != actual.provider.lower().strip()
        ):
            differences.append(
                f"Provider mismatch: expected '{expected.provider}', got '{actual.provider}'"
            )

        if (
            self.config.match_model
            and expected.model.lower().strip() != actual.model.lower().strip()
        ):
            differences.append(f"Model mismatch: expected '{expected.model}', got '{actual.model}'")

        if expected.operation != actual.operation:
            differences.append(
                f"Operation mismatch: expected '{expected.operation}', got '{actual.operation}'"
            )

        if self.config.match_tools and expected.tools != actual.tools:
            differences.append("Tools declarations mismatch")

        if differences:
            return SemanticDriftRecord(
                step_index=step_index,
                similarity_score=0.0,
                threshold=self.config.threshold,
                status=DriftStatus.STRUCTURAL_MISMATCH,
                expected_text="",
                actual_text="",
                token_similarity=0.0,
                char_similarity=0.0,
                differences=differences,
                matched_index=matched_index,
            )

        # 2. Extract normalized text representations
        exp_text = self.extract_prompt_text(expected)
        act_text = self.extract_prompt_text(actual)

        if self.config.ignore_case:
            cmp_exp = exp_text.lower()
            cmp_act = act_text.lower()
        else:
            cmp_exp = exp_text
            cmp_act = act_text

        # 3. Exact match fast path
        if cmp_exp == cmp_act:
            return SemanticDriftRecord(
                step_index=step_index,
                similarity_score=1.0,
                threshold=self.config.threshold,
                status=DriftStatus.EXACT_MATCH,
                expected_text=exp_text,
                actual_text=act_text,
                token_similarity=1.0,
                char_similarity=1.0,
                matched_index=matched_index,
            )

        # 4. Semantic similarity evaluation
        sim = calculate_semantic_similarity(cmp_exp, cmp_act, embedding_fn=self.config.embedding_fn)
        t_sim = token_cosine_similarity(cmp_exp, cmp_act)
        c_sim = levenshtein_similarity(cmp_exp, cmp_act)
        inline_diff, added, removed = generate_inline_token_diff(exp_text, act_text)
        diff_text = generate_semantic_diff(exp_text, act_text)

        status = (
            DriftStatus.SEMANTIC_MATCH
            if sim >= self.config.threshold
            else DriftStatus.DRIFT_EXCEEDED
        )

        diff_summary: list[str] = []
        if added:
            diff_summary.append(f"Added tokens: {', '.join(repr(t) for t in added[:8])}")
        if removed:
            diff_summary.append(f"Removed tokens: {', '.join(repr(t) for t in removed[:8])}")

        return SemanticDriftRecord(
            step_index=step_index,
            similarity_score=sim,
            threshold=self.config.threshold,
            status=status,
            expected_text=exp_text,
            actual_text=act_text,
            token_similarity=t_sim,
            char_similarity=c_sim,
            diff=diff_text,
            inline_diff=inline_diff,
            added_tokens=added,
            removed_tokens=removed,
            differences=diff_summary,
            matched_index=matched_index,
        )

    def find_match(
        self,
        actual: RequestPayload,
        session: SessionRecord,
        start_index: int = 0,
    ) -> tuple[Interaction | None, SemanticDriftRecord]:
        """Find the matching interaction using semantic matching rules.

        In strict ordering mode, checks session.interactions[start_index].
        In unordered mode, evaluates all candidates and picks the highest similarity.
        """
        interactions = session.interactions
        if not interactions:
            record = SemanticDriftRecord(
                step_index=start_index,
                similarity_score=0.0,
                threshold=self.config.threshold,
                status=DriftStatus.STRUCTURAL_MISMATCH,
                differences=["Session contains zero recorded interactions"],
            )
            return None, record

        if self.global_config.strict_ordering:
            if start_index >= len(interactions):
                record = SemanticDriftRecord(
                    step_index=start_index,
                    similarity_score=0.0,
                    threshold=self.config.threshold,
                    status=DriftStatus.STRUCTURAL_MISMATCH,
                    differences=[
                        f"Interaction sequence exhausted: request index {start_index} "
                        f"exceeds recorded session length ({len(interactions)})"
                    ],
                )
                return None, record

            candidate = interactions[start_index]
            record = self.compare_semantic(
                candidate.request,
                actual,
                step_index=start_index,
                matched_index=candidate.index,
            )
            self.report.records.append(record)
            return (candidate if record.is_match else None), record

        # Unordered search across candidates starting from start_index
        best_candidate: Interaction | None = None
        best_record: SemanticDriftRecord | None = None

        for candidate in interactions[start_index:]:
            record = self.compare_semantic(
                candidate.request,
                actual,
                step_index=start_index,
                matched_index=candidate.index,
            )
            if record.status == DriftStatus.EXACT_MATCH:
                self.report.records.append(record)
                return candidate, record

            if best_record is None or record.similarity_score > best_record.similarity_score:
                best_record = record
                best_candidate = candidate

        final_record = best_record or SemanticDriftRecord(
            step_index=start_index,
            similarity_score=0.0,
            threshold=self.config.threshold,
            status=DriftStatus.STRUCTURAL_MISMATCH,
        )
        self.report.records.append(final_record)

        if final_record.is_match:
            return best_candidate, final_record
        return None, final_record
