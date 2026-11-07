"""Visual semantic diff generator for prompt evolution and drift analysis."""

from __future__ import annotations

import difflib

from tracereplay.semantic.similarity import (
    calculate_semantic_similarity,
    tokenize_text,
)


def generate_inline_token_diff(
    expected_text: str, actual_text: str
) -> tuple[str, list[str], list[str]]:
    """Generate an inline word-level diff and extract added/removed token lists.

    Returns:
        (inline_diff_str, added_tokens, removed_tokens)
    """
    exp_tokens = tokenize_text(expected_text)
    act_tokens = tokenize_text(actual_text)

    matcher = difflib.SequenceMatcher(None, exp_tokens, act_tokens)
    inline_parts: list[str] = []
    added_tokens: list[str] = []
    removed_tokens: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            inline_parts.extend(exp_tokens[i1:i2])
        elif tag == "replace":
            rem = exp_tokens[i1:i2]
            add = act_tokens[j1:j2]
            removed_tokens.extend(rem)
            added_tokens.extend(add)
            inline_parts.append(f"[-{' '.join(rem)}-]")
            inline_parts.append(f"{{+{' '.join(add)}+}}")
        elif tag == "delete":
            rem = exp_tokens[i1:i2]
            removed_tokens.extend(rem)
            inline_parts.append(f"[-{' '.join(rem)}-]")
        elif tag == "insert":
            add = act_tokens[j1:j2]
            added_tokens.extend(add)
            inline_parts.append(f"{{+{' '.join(add)}+}}")

    return " ".join(inline_parts), added_tokens, removed_tokens


def generate_semantic_diff(
    expected_text: str,
    actual_text: str,
    expected_title: str = "Expected (Baseline Prompt)",
    actual_title: str = "Actual (Incoming Prompt)",
) -> str:
    """Generate a rich unified semantic diff between expected and actual prompt text."""
    exp_lines = expected_text.splitlines(keepends=True)
    act_lines = actual_text.splitlines(keepends=True)

    similarity = calculate_semantic_similarity(expected_text, actual_text)
    header = f"--- {expected_title}\n+++ {actual_title}\n@@ Similarity: {similarity:.2%} @@\n"

    diff = difflib.unified_diff(
        exp_lines,
        act_lines,
        fromfile=expected_title,
        tofile=actual_title,
        n=2,
    )
    raw_diff = "".join(list(diff)[2:])  # Skip default header
    return header + raw_diff


def colorize_diff(diff_text: str) -> str:
    """Apply terminal ANSI colors to unified diff text."""
    colored_lines: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++"):
            colored_lines.append(f"\033[32m{line}\033[0m")
        elif line.startswith("---"):
            colored_lines.append(f"\033[31m{line}\033[0m")
        elif line.startswith("@@"):
            colored_lines.append(f"\033[36m{line}\033[0m")
        elif line.startswith("+"):
            colored_lines.append(f"\033[32m{line}\033[0m")
        elif line.startswith("-"):
            colored_lines.append(f"\033[31m{line}\033[0m")
        else:
            colored_lines.append(line)
    return "\n".join(colored_lines)
