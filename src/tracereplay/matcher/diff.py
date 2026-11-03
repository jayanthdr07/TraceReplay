#  Visual diff generator for explaining request mismatches in TraceReplay.

from __future__ import annotations

import difflib
import json
from typing import Any


def format_json_for_diff(data: Any) -> list[str]:
    #  Serialize data into sorted, indented lines suitable for unified diffing.
    formatted = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return formatted.splitlines(keepends=True)


def generate_diff(
    expected: Any,
    actual: Any,
    expected_title: str = "Expected (Fixture)",
    actual_title: str = "Actual (Request)",
) -> str:
    # generate a clean unified diff between two payloads.
    expected_lines = format_json_for_diff(expected)
    actual_lines = format_json_for_diff(actual)

    diff = difflib.unified_diff(
        expected_lines, actual_lines, fromfile=expected_title, tofile=actual_title, n=3
    )
    return "".join(diff)
