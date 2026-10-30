# Security Policy

## Project status

TraceReplay is under active early-stage development. Security-sensitive behavior and supported versions will be documented as releases become available.

## Reporting a vulnerability

Please do not report security vulnerabilities through public GitHub Issues or Discussions.

Use GitHub's **Report a vulnerability** feature on the repository's Security tab, if available. If private vulnerability reporting is not enabled, contact the repository owner through the private contact method listed on their GitHub profile and request a secure reporting channel.

Include, where possible:

- A description of the vulnerability.
- Affected versions, commits, or components.
- Steps to reproduce the issue.
- Potential impact.
- A suggested mitigation, if known.

Do not include real credentials, customer data, or private production recordings in the report.

## What deserves a security report?

Examples include:

- Exposure of API keys, access tokens, or authorization headers.
- Unauthorized access to another user's, team's, or project's recordings.
- Broken team or project access controls.
- Unsafe fixture loading that leads to code execution or unintended file access.
- Authentication or session-management vulnerabilities.
- Sensitive data exposure through logs, analytics, or dashboard APIs.
- Replay behavior that unexpectedly sends requests to a live provider.

## Security expectations

The project intends to:

- Redact secrets and authorization data by default.
- Make recording scope explicit and configurable.
- Treat fixtures as potentially sensitive data.
- Validate fixture data before use.
- Avoid silent live-provider fallback in replay mode.
- Keep cloud recordings private by default.
- Enforce platform access through server-side authorization and PostgreSQL Row Level Security (RLS).
- Avoid placing service-role credentials or other privileged secrets in browser code.

## Supported versions

A formal supported-version policy will be published when the project begins making tagged releases. Until then, please report vulnerabilities affecting the current default branch as well as any published release you can reproduce.
