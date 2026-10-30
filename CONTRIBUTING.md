# Contributing to TraceReplay

Thank you for considering a contribution to TraceReplay.

TraceReplay is an early-stage open-source project. The goal is to make testing LLM-powered applications more repeatable through recording, fixture storage, and replay.

## Before you start

1. Read the project [README](README.md).
2. Check existing Issues and Pull Requests to avoid duplicate work.
3. For a significant feature or architectural change, open an Issue first and discuss the proposed approach.
4. Keep contributions focused. A small, well-tested change is easier to review.

## Contribution areas

Potential contribution areas include:

- Core interaction models and configuration.
- Fixture serialization, loading, and validation.
- Recording and replay behavior.
- Request matching.
- Provider adapters.
- Tool-call capture and replay.
- pytest integration.
- Documentation and examples.
- Dashboard and platform work, when those components are opened for contribution.

Do not claim support for a provider or API operation unless it has been implemented and tested.

## Development principles

- Local SDK use must not require a hosted TraceReplay account.
- Replay mode must not silently call a live provider when a fixture is missing.
- Errors should explain what failed and provide useful debugging context.
- Avoid storing API keys, authorization headers, or other secrets.
- Preserve provider-specific data when normalization would otherwise discard meaningful information.
- Add tests for behavior changes and regression fixes.
- Keep public APIs and documentation aligned.

## Pull request process

1. Create a branch for your change.
2. Make the smallest coherent change that solves the issue.
3. Add or update tests.
4. Run the relevant test, lint, formatting, and type-check commands documented by the project.
5. Update documentation when behavior or public APIs change.
6. Open a Pull Request describing the problem, solution, and tests performed.
7. Link the related Issue when applicable.

Do not mark checks as passing unless you have run them successfully.

## Commit messages

Use clear, descriptive commit messages. A conventional format is recommended:

- `feat: add fixture validation`
- `fix: prevent live fallback during replay`
- `docs: clarify provider setup`
- `test: cover request matching`
- `refactor: simplify interaction model`

## Issues

When opening a bug report, include:

- TraceReplay version or commit.
- Python version and operating system.
- Minimal reproduction steps.
- Expected behavior.
- Actual behavior.
- Relevant error output, with secrets and private data removed.

For feature requests, explain the use case and the behavior you expect.

## Security

Never include API keys, tokens, customer data, private prompts, or unredacted production recordings in Issues, Pull Requests, or test fixtures. For vulnerabilities, follow [SECURITY.md](SECURITY.md).

## Code of conduct

By participating, you agree to follow the expectations in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
