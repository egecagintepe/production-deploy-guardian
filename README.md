# Production Deploy Guardian

[![CI Status](https://github.com/egecagintepe/production-deploy-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/egecagintepe/production-deploy-guardian/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Autonomous deployment safety guard, change classifier, and release engineer for AI coding agents (Claude Code, Cursor, Antigravity, OpenAI Operator) and DevOps teams.

It prevents broken releases by classifying diffs (Fast reload vs. Full rebuild), validating Git and remote preflight state, enforcing zero-data-loss safety rules, orchestrating a bounded auto-recovery triage loop, and verifying post-deploy health.

---

## Key Features

- **Automated Mode Classification**: Analyzes file diffs against the deployed commit. Distinguishes stateless code/template updates (`Fast`) from database migrations, dependency bumps, container updates, and frontend builds (`Full`).
- **Fail-Closed Preflight Checks**: Verifies clean working trees, release branch alignment, remote synchronization, and disk space thresholds before touching production.
- **Strict Safety Invariants**: Automatically detects and blocks destructive actions such as `docker volume prune`, recursive deletions on data roots, force pushes, and raw table drops.
- **Bounded Error Triage Loop**: Restricts autonomous remediation to a maximum of 3 attempts for safe, locally verifiable bugs (typos, missing manifest entries, build issues) while immediately escalating on database deadlocks or disk exhaustion.
- **Post-Deploy Smoke Verification**: Probes critical HTTP endpoints with configurable retries, validates running container states, and verifies the deployed commit hash.
- **Zero External Dependencies**: Standard library Python 3.8+ CLI with JSON output mode, suitable for direct integration into agent workflows or CI/CD pipelines.

---

## Installation & Setup

### 1. As an AI Agent Skill (Claude Code, Cursor, Antigravity)

Copy the repository or clone it into your agent's skill directory:

```bash
git clone https://github.com/egecagintepe/production-deploy-guardian.git .agents/skills/production-deploy-guardian
```

Compatible agent environments will automatically index `SKILL.md` and load the guardian when evaluating deployment tasks.

### 2. Standalone CLI Usage

Clone the repository and inspect your deployment:

```bash
# Clone the repository
git clone https://github.com/egecagintepe/production-deploy-guardian.git
cd production-deploy-guardian

# Initialize configuration
cp guardian_config.example.json guardian_config.json
```

---

## CLI Usage

### Preflight Release Gate
```bash
python scripts/deploy_guardian.py preflight --config guardian_config.json
```

### Classify Changeset (Fast vs Full Deploy)
```bash
# Evaluate git diff between deployed commit and current HEAD
python scripts/deploy_guardian.py classify --config guardian_config.json --base-commit <PREV_COMMIT>

# Or evaluate specific modified files
python scripts/deploy_guardian.py classify --config guardian_config.json --files app/views.py templates/index.html
```

### Audit Command for Dangerous Operations
```bash
python scripts/deploy_guardian.py audit-safety --command "docker volume prune -f"
```

### Post-Deploy Health Check
```bash
python scripts/deploy_guardian.py verify-health --config guardian_config.json
```

---

## Configuration (`guardian_config.json`)

```json
{
  "project_name": "my-service",
  "release_branch": "main",
  "classification_rules": {
    "full_triggers": [
      { "pattern": "^migrations/|^db/migrate/", "reason": "Database migration detected" },
      { "pattern": "requirements.*\\.txt$|package\\.json$", "reason": "Dependency manifest modified" },
      { "pattern": "Dockerfile|docker-compose.*\\.ya?ml$", "reason": "Container configuration changed" },
      { "pattern": "^frontend/src/", "reason": "Frontend SPA source changed" }
    ],
    "ignore_patterns": ["^docs/", "\\.md$", "^\\.github/"]
  },
  "health_check": {
    "endpoints": [
      { "url": "https://api.example.com/healthz", "expected_status": 200, "timeout_seconds": 10 }
    ]
  },
  "deployment_commands": {
    "fast": "ssh prod-host 'app-fast-deploy'",
    "full": "ssh prod-host 'app-full-deploy'"
  }
}
```

---

## Documentation

- [Deployment Mode Classification Matrix](references/mode_classification_matrix.md)
- [Autonomous Failure Triage Playbook](references/failure_triage_playbook.md)
- [Production Safety Invariants](references/safety_invariants.md)
- [Sample Scenarios](examples/sample_scenarios.md)

---

## Testing

Run the automated test suite:
```bash
python -m unittest discover -s tests
```

---

## License

This project is licensed under the [MIT License](LICENSE).
