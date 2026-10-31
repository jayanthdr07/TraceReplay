"""Base pytest configuration and shared fixtures for TraceReplay test suite."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src directory is in sys.path when running tests locally without editable install
SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
