"""Command-line interface (CLI) for TraceReplay.

Provides terminal inspection, provider environment checks, fixture statistics,
and interactive welcome banners.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from tracereplay import __version__
from tracereplay.guardrails.pricing import calculate_token_cost

_ASCII_BANNER = "\n".join(
    [
        r"  _____                     ____            _",
        r" |_   _| __ __ _  ___ ___  |  _ \ ___ _ __ | | __ _ _   _",
        r"   | || '__/ _` |/ __/ _ \ | |_) / _ \ '_ \| |/ _` | | | |",
        r"   | || | | (_| | (_|  __/ |  _ <  __/ |_) | | (_| | |_| |",
        r"   |_||_|  \__,_|\___\___| |_| \_\___| .__/|_|\__,_|\__, |",
        r"                                     |_|            |___/",
    ]
)


def _supports_color() -> bool:
    """Return True if the current terminal output stream supports ANSI color codes."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _is_sdk_installed(module_name: str) -> bool:
    """Safely check if a Python module or submodule is installed."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError, AttributeError):
        return False


def print_banner() -> None:
    """Display the TraceReplay ASCII art banner and project summary."""
    cyan = "\033[96m" if _supports_color() else ""
    bold = "\033[1m" if _supports_color() else ""
    reset = "\033[0m" if _supports_color() else ""
    green = "\033[92m" if _supports_color() else ""

    print(f"{cyan}{_ASCII_BANNER}{reset}")
    print(f" {bold}TraceReplay{reset} - Deterministic Testing & Replay for AI Agents & LLMs")
    print(f" Version: {green}v{__version__}{reset} | License: {bold}MIT{reset}")
    print(" https://github.com/rakshithkumar608/TraceReplay\n")


def check_providers() -> None:
    """Inspect and report the status of major AI provider SDKs and environment keys."""
    print_banner()
    bold = "\033[1m" if _supports_color() else ""
    green = "\033[92m" if _supports_color() else ""
    yellow = "\033[93m" if _supports_color() else ""
    red = "\033[91m" if _supports_color() else ""
    reset = "\033[0m" if _supports_color() else ""

    providers = [
        ("OpenAI", "openai", "OPENAI_API_KEY"),
        ("Anthropic Claude", "anthropic", "ANTHROPIC_API_KEY"),
        ("Google Gemini", "google.genai", "GEMINI_API_KEY"),
        ("Groq", "groq", "GROQ_API_KEY"),
        ("Mistral AI", "mistralai", "MISTRAL_API_KEY"),
        ("DeepSeek", "openai", "DEEPSEEK_API_KEY"),
        ("Ollama (Local)", None, "OLLAMA_HOST"),
    ]

    print(f"{bold}Provider SDK & Environment Health Check:{reset}")
    print("-" * 65)
    print(f" {'Provider':<18} | {'SDK Status':<16} | {'API Key Status'}")
    print("-" * 65)

    for name, module_name, env_key in providers:
        if module_name:
            is_installed = _is_sdk_installed(module_name)
            sdk_str = f"{green}Installed{reset}" if is_installed else f"{red}Not Installed{reset}"
        else:
            sdk_str = f"{yellow}Local HTTP{reset}"

        key_set = bool(os.getenv(env_key))
        key_str = f"{green}Detected ({env_key}){reset}" if key_set else f"{yellow}Not Set{reset}"

        print(f" {name:<18} | {sdk_str:<25} | {key_str}")

    print("-" * 65)
    print(f"\n{bold}Tip:{reset} Install missing providers using:")
    print('  pip install "tracereplay[openai]"')
    print('  pip install "tracereplay[all]"\n')


def print_stats(fixtures_dir: str = ".tracereplay/fixtures") -> None:
    """Scan local fixtures directory and print recorded interaction statistics."""
    print_banner()
    bold = "\033[1m" if _supports_color() else ""
    green = "\033[92m" if _supports_color() else ""
    reset = "\033[0m" if _supports_color() else ""

    p = Path(fixtures_dir)
    if not p.exists() or not p.is_dir():
        print(f"No fixtures directory found at '{fixtures_dir}'.")
        print("Record your first test using: pytest --tracereplay-mode=record\n")
        return

    files = list(p.glob("*.json"))
    if not files:
        print(f"Zero fixtures found in '{fixtures_dir}'.")
        return

    total_sessions = len(files)
    total_interactions = 0
    total_tokens = 0
    estimated_usd = 0.0

    for file_path in files:
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
                interactions = data.get("interactions", [])
                total_interactions += len(interactions)
                for item in interactions:
                    req = item.get("request", {})
                    resp = item.get("response", {})
                    model = req.get("model", "gpt-4o")
                    usage = resp.get("usage", {})
                    p_tok = usage.get("prompt_tokens", 0)
                    c_tok = usage.get("completion_tokens", 0)
                    total_tokens += p_tok + c_tok
                    estimated_usd += calculate_token_cost(model, p_tok, c_tok)
        except Exception:
            pass

    print(f"{bold}Recorded Fixture Metrics ({fixtures_dir}):{reset}")
    print("-" * 55)
    print(f"  Total Fixture Files:      {total_sessions:,}")
    print(f"  Total Interactions:       {total_interactions:,}")
    print(f"  Total Tokens Recorded:    {total_tokens:,}")
    print(f"  Estimated Cost Saved:     {green}${estimated_usd:.4f} USD{reset}")
    print("-" * 55)
    print(f"Every replay execution saves {green}${estimated_usd:.4f} USD{reset} in API costs!\n")


def main() -> None:
    """CLI entry point for tracereplay."""
    parser = argparse.ArgumentParser(
        prog="tracereplay",
        description="TraceReplay: Deterministic replay & testing for LLMs & AI agents.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="TraceReplay commands")

    # banner
    subparsers.add_parser("banner", help="Print the TraceReplay ASCII banner")

    # doctor / check
    subparsers.add_parser("check", help="Check installed AI provider SDKs and environment keys")

    # stats
    stats_parser = subparsers.add_parser("stats", help="Display recorded fixture savings & metrics")
    stats_parser.add_argument(
        "--dir",
        default=".tracereplay/fixtures",
        help="Path to fixtures directory (default: .tracereplay/fixtures)",
    )

    args = parser.parse_args()

    if args.command == "banner":
        print_banner()
    elif args.command == "check":
        check_providers()
    elif args.command == "stats":
        print_stats(fixtures_dir=args.dir)
    else:
        # Default behavior when invoked without arguments: display banner & quickstart
        print_banner()
        print("Usage:")
        print("  tracereplay check        Check provider SDKs and environment API keys")
        print("  tracereplay stats        View recorded tokens, interactions, and $ savings")
        print("  tracereplay --help       Show full CLI options")
        print("  pytest -v                Run test suite with deterministic replay\n")


if __name__ == "__main__":
    main()
