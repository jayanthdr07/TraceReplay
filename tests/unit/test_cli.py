"""Unit tests for the TraceReplay CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tracereplay import __version__
from tracereplay.cli import (
    _supports_color,
    check_providers,
    main,
    print_banner,
    print_stats,
)


def test_supports_color() -> None:
    """Test ANSI color support detection."""
    result = _supports_color()
    assert isinstance(result, bool)


def test_print_banner(capsys: pytest.CaptureFixture[str]) -> None:
    """Test print_banner output contains key branding elements."""
    print_banner()
    captured = capsys.readouterr().out
    assert "TraceReplay" in captured
    assert f"v{__version__}" in captured
    assert "MIT" in captured
    assert "github.com/rakshithkumar608/TraceReplay" in captured


def test_check_providers(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test check_providers displays table with provider status."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    check_providers()
    captured = capsys.readouterr().out
    assert "Provider SDK & Environment Health Check" in captured
    assert "OpenAI" in captured
    assert "Detected (OPENAI_API_KEY)" in captured
    assert "Anthropic Claude" in captured
    assert "Not Set" in captured


def test_print_stats_nonexistent_dir(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """Test print_stats with a missing directory."""
    non_existent = tmp_path / "does_not_exist"
    print_stats(fixtures_dir=str(non_existent))
    captured = capsys.readouterr().out
    assert "No fixtures directory found" in captured


def test_print_stats_empty_dir(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """Test print_stats with an empty directory."""
    empty_dir = tmp_path / "empty_fixtures"
    empty_dir.mkdir()
    print_stats(fixtures_dir=str(empty_dir))
    captured = capsys.readouterr().out
    assert "Zero fixtures found" in captured


def test_print_stats_with_fixtures(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """Test print_stats with valid fixture files."""
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    fixture_content = {
        "version": "1.0",
        "interactions": [
            {
                "request": {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
                "response": {
                    "choices": [{"message": {"content": "Hello!"}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                },
            }
        ],
    }

    fixture_file = fixtures_dir / "test_session.json"
    fixture_file.write_text(json.dumps(fixture_content), encoding="utf-8")

    print_stats(fixtures_dir=str(fixtures_dir))
    captured = capsys.readouterr().out
    assert "Recorded Fixture Metrics" in captured
    assert "Total Fixture Files:      1" in captured
    assert "Total Interactions:       1" in captured
    assert "Total Tokens Recorded:    150" in captured
    assert "Cost Saved:" in captured


def test_main_default(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main with no arguments displays banner and quickstart info."""
    with patch("sys.argv", ["tracereplay"]):
        main()
    captured = capsys.readouterr().out
    assert "TraceReplay" in captured
    assert "Usage:" in captured
    assert "tracereplay check" in captured
    assert "tracereplay stats" in captured


def test_main_banner(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main banner subcommand."""
    with patch("sys.argv", ["tracereplay", "banner"]):
        main()
    captured = capsys.readouterr().out
    assert "TraceReplay" in captured
    assert f"v{__version__}" in captured


def test_main_check(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main check subcommand."""
    with patch("sys.argv", ["tracereplay", "check"]):
        main()
    captured = capsys.readouterr().out
    assert "Provider SDK & Environment Health Check" in captured


def test_main_stats(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """Test main stats subcommand with custom directory."""
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    with patch("sys.argv", ["tracereplay", "stats", "--dir", str(fixtures_dir)]):
        main()
    captured = capsys.readouterr().out
    assert "Zero fixtures found" in captured


def test_main_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main --version exits with 0 and prints version."""
    with patch("sys.argv", ["tracereplay", "--version"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    captured = capsys.readouterr().out
    assert f"tracereplay {__version__}" in captured
