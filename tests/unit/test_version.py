"""Unit tests for package metadata and versioning."""

from __future__ import annotations

import re

import tracereplay


def test_package_has_version() -> None:
    """Ensure that the package defines a version string."""
    assert hasattr(tracereplay, "__version__")
    assert isinstance(tracereplay.__version__, str)


def test_package_version_semver_format() -> None:
    """Ensure that the package version follows semantic versioning (MAJOR.MINOR.PATCH)."""
    semver_pattern = r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?$"
    assert re.match(
        semver_pattern, tracereplay.__version__
    ), f"Invalid version format: {tracereplay.__version__}"


def test_package_metadata() -> None:
    """Ensure package author and license metadata are exposed."""
    assert tracereplay.__license__ == "MIT"
    assert "TraceReplay Contributors" in tracereplay.__author__
