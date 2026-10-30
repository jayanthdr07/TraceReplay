# TraceReplay

**Record once. Replay reliably. Test, inspect, and debug with confidence.**

TraceReplay is an open-source Python library and developer platform for recording and replaying supported interactions between applications and Large Language Models (LLMs).

It is designed to help developers create repeatable tests for LLM-powered applications without repeatedly calling live AI providers during every test run.

> **Project status:** Early development. APIs, provider integrations, and platform capabilities are subject to change. Do not assume a feature is production-ready until it is documented and covered by tests.

## Why TraceReplay?

Testing an application that depends on an LLM can involve repeated network requests, API costs, variable model responses, rate limits, and provider availability.

TraceReplay is being built around two primary modes:

- **Record mode:** communicate with a supported live provider, capture the interaction, and save it as a fixture.
- **Replay mode:** match an incoming request against a saved fixture and return the recorded response without contacting the provider.

Replay must fail clearly when a matching fixture is missing or invalid. It must never silently fall back to a live provider request.

TraceReplay does not generate AI responses and does not claim that live model outputs are deterministic. It makes previously recorded interactions reusable for testing.

## Planned capabilities

The product vision includes:

- Recording supported LLM requests and responses.
- Readable, local JSON fixtures.
- Request matching and deterministic replay of recorded interactions.
- Tool-call and tool-result recording/replay where supported.
- pytest integration.
- Multiple provider adapters, implemented and validated incrementally.
- An optional web dashboard for recordings, sessions, and projects.
- Team workspaces, invitations, and role-based permissions.
- Testing and performance analytics.
- Visual interaction timelines, execution-flow inspection, and run comparison.

These are planned capabilities, not a claim that they are all currently implemented. Consult the project roadmap and release notes for implementation status.

## Architecture direction

TraceReplay has two connected but independently useful parts:

1. **Python SDK:** the recording, fixture, matching, replay, provider-adapter, and pytest functionality. Local recording and replay should work without a hosted account.
2. **Optional web platform:** a Next.js dashboard backed by FastAPI and Supabase services for accounts, teams, projects, shared metadata, and shared recordings.

The current technology direction is:

| Area | Technology |
|---|---|
| Core SDK | Python |
| Testing | pytest |
| Data validation | Pydantic |
| Local fixtures | JSON files |
| Platform API | Python FastAPI |
| Dashboard | Next.js + TypeScript |
| UI | Tailwind CSS + shadcn/ui |
| Authentication | Supabase Auth |
| Platform database | Supabase PostgreSQL |
| Shared artifact storage | Supabase Storage |
| Realtime updates | Supabase Realtime |
| Authorization | PostgreSQL Row Level Security (RLS) |
| CI | GitHub Actions |
| Python package distribution | PyPI |

The SDK must not require Supabase or FastAPI for local replay. Cloud synchronization is an optional platform capability.

## Security

Recorded prompts, responses, tool arguments, and tool results may contain private or sensitive data.

- Do not commit API keys, access tokens, or credentials.
- Authorization headers and secrets must not be stored in fixtures by default.
- Recording and redaction behavior must be explicit and configurable.
- Treat fixture files as sensitive application data.
- Cloud recordings must be private by default and protected by authorization policies.

See [SECURITY.md](SECURITY.md) for reporting instructions.

## Development status

The project is being established in stages. The initial engineering focus is the Python SDK:

1. Interaction models and configuration.
2. JSON fixture storage and validation.
3. Recording engine.
4. Replay engine and request matching.
5. Clear errors and no-live-fallback guarantees.
6. First provider integration.
7. pytest integration.
8. Documentation, examples, and automated tests.

The dashboard and team platform follow after the core SDK architecture is stable.

## Contributing

Contributions are welcome once the project contribution workflow is in place. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Please use GitHub Issues for bugs and feature discussions.

## Support

For questions and usage discussions, use GitHub Discussions when enabled. For confirmed bugs, open a GitHub Issue. Do not report security vulnerabilities in public issues; follow [SECURITY.md](SECURITY.md).

## License

TraceReplay is planned to be released under the MIT License. See [LICENSE](LICENSE) once the license file has been added to the repository.
