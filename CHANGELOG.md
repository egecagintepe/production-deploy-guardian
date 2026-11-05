# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-11-05

### Security & Hardening
- **Positive Whitelisting Classification**: Eliminated dangerous silent fallbacks to `Fast` deployment for unclassified files. Added four explicit decision states: `FAST_ELIGIBLE`, `FULL_REQUIRED`, `NO_OP`, and `UNKNOWN_BLOCKED`.
- **Live Remote Synchronization Gate**: Preflight now checks live remote tracking references (`git ls-remote`) instead of relying solely on stale local cache.
- **Optional Safe Remote Telemetry**: Added read-only SSH preflight diagnostic for root partition free disk space and container daemon responsiveness.
- **Enhanced Destructive Command Auditor**: Expanded regex scanner to cover shell chaining (`&&`, `||`, `;`), flag variations (`-f`, `--force`), raw block overwrites, and secret dumping.
- **Official Agent Skills Compliance**: Validated frontmatter and directory layout against the official Agent Skills specification (`npx skills-ref validate`).
- **Comprehensive E2E Test Suite**: Expanded test coverage to 27 unit and integration tests including synthetic Git repositories and CLI subprocess testing.

## [1.0.0] - 2026-11-05

### Added
- Preliminary release of `production-deploy-guardian`.
