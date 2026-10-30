# GitHub Repository Configuration

This directory contains GitHub repository automation and contribution templates.

## Contents

- `ISSUE_TEMPLATE/bug_report.yml`
  - Standardized bug reports.

- `ISSUE_TEMPLATE/feature_request.yml`
  - Standardized feature requests.

- `ISSUE_TEMPLATE/config.yml`
  - Issue configuration and community links.

- `PULL_REQUEST_TEMPLATE.md`
  - Pull request checklist.

- `dependabot.yml`
  - Automated dependency update configuration.

## Dependency updates

Dependabot checks Python dependencies and GitHub Actions weekly.

Python dependency updates will become useful once the project package
configuration is added.

## Continuous integration

GitHub Actions CI will be configured after the initial Python SDK
structure and `pyproject.toml` are created. This ensures CI runs
actual project tests and checks.