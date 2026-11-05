# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-05

### Added
- Initial public release of `production-deploy-guardian`.
- Deterministic changeset classification engine (`Fast` in-place reload vs `Full` rebuild vs `No-Op`).
- Pre-release Git quality gates verifying clean trees, branch match, and remote synchronization.
- Dangerous operation safety scanner blocking volume prunes, destructive `rm -rf`, force pushes, and raw table drops.
- Autonomous bounded failure triage protocol (maximum 3 attempts) with immediate escalation triggers.
- Post-deployment smoke health verification CLI with configurable endpoint probing and retries.
- Comprehensive reference manuals: mode classification matrix, failure triage playbook, and safety invariants.
- Full automated test suite with 100% passing coverage on classification, safety auditing, and health checks.
- GitHub Actions CI workflow covering Python 3.8 through 3.12 across Ubuntu and Windows.
