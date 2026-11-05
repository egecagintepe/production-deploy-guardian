<div align="center">

# Production Deploy Guardian

**Your AI agent can write the deployment. This skill helps it know when *not* to deploy.**

[![CI](https://github.com/egecagintepe/production-deploy-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/egecagintepe/production-deploy-guardian/actions)
[![Release](https://img.shields.io/github/v/release/egecagintepe/production-deploy-guardian?color=blue)](https://github.com/egecagintepe/production-deploy-guardian/releases/latest)
[![skills.sh](https://img.shields.io/badge/skills.sh-production--deploy--guardian-blue)](https://skills.sh/egecagintepe/production-deploy-guardian)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Agent Skills: v1](https://img.shields.io/badge/Agent%20Skills-v1.0-emerald.svg)](https://agentskills.io/specification)

*Autonomous deployment safety guard, changeset classifier, and bounded error triage loop for AI coding agents and DevOps teams.*

<br />

```bash
npx skills add egecagintepe/production-deploy-guardian
```

<br />

```
   Git Diff ──► [ POSITIVE WHITELIST ] ──► FAST_ELIGIBLE  (Stateless view / template hotfix)
                     │
                     ├──► [ FULL TRIGGERS ]   ──► FULL_REQUIRED  (Migrations, packages, Docker)
                     │
                     └──► [ UNKNOWN / DIFF ]  ──► UNKNOWN_BLOCKED (Halt & escalate to operator)
```

</div>

---

## Problem → Solution → Result

- **The Problem**: When autonomous AI coding agents (Claude Code, Cursor, Codex, Gemini) ship code to staging or production:
  1. **Silent Under-Deployment**: The agent executes an in-place worker reload (`Fast`) when database models or dependencies changed, causing immediate `ModuleNotFoundError` or `OperationalError` outages.
  2. **Needless Over-Deployment**: The agent triggers a 15-minute container rebuild for a one-line typo in a view or template.
  3. **Destructive Operations**: In panics or triage loops, agents run `docker volume prune`, `rm -rf`, or `git reset --hard`, destroying live persistent databases or storage volumes.
  4. **Infinite Flailing Loops**: When a deployment fails, unconstrained agents repeatedly execute failing retries, compounding downtime.

- **The Solution**: `production-deploy-guardian` provides a deterministic safety gate. It requires explicit verified deployment baselines (`--base-commit`), classifies changesets using positive whitelisting, intercepts destructive commands, and enforces a strict 3-attempt retry budget.

- **The Result**: Agents deploy safely with minimal downtime, never mistake schema migrations for lightweight hotfixes, cannot execute destructive volume commands, and fail closed (`UNKNOWN_BLOCKED`) whenever changes cannot be proven safe.

---

## Quick Install (30 Seconds)

### Option 1: Using Agent Skills CLI (`skills.sh`)
```bash
npx skills add egecagintepe/production-deploy-guardian
```

### Option 2: Direct Agent Integration (Claude Code, Cursor, Codex)
Clone into your project's local agent skills directory:
```bash
git clone https://github.com/egecagintepe/production-deploy-guardian.git .agents/skills/production-deploy-guardian
```

### Option 3: Standalone CLI Tool (Zero Dependencies)
```bash
git clone https://github.com/egecagintepe/production-deploy-guardian.git
cd production-deploy-guardian
cp guardian_config.example.json guardian_config.json
python scripts/deploy_guardian.py --help
```

---

## Before & After

| Scenario | Naive AI Agent Behavior | Production Deploy Guardian |
|---|---|---|
| **Unregistered shell script modified** | Assumes non-container code; reloads worker in-place (`Fast`). | **`UNKNOWN_BLOCKED`**: File is not in positive whitelist; halts deployment for human review. |
| **New dependency in `requirements.txt`** | Runs `docker compose restart web` (fails to install package; site crashes). | **`FULL_REQUIRED`**: Mandates full container build pipeline (`docker compose build`). |
| **Deploy fails with DB lock** | Tries random commands, drops locks or restarts containers blindly. | **`STOP_IMMEDIATELY`**: Escalates to human operator. Enforces strict 3-attempt retry budget. |
| **Agent executes cleanup command** | Runs `docker volume prune -f` (destroys database volumes). | **`BLOCKED`**: Destructive storage command intercepted by safety auditor. |

---

## How It Works: The 4 Decision States

The Guardian rejects silent assumptions. It classifies changesets using **explicit positive eligibility**:

```
                       Modified File
                             │
            Does it match `ignore_patterns`?
                    ├── YES ──► Ignored (e.g. docs, markdown, unit tests)
                    └── NO
                         │
            Does it match `full_triggers`?
                    ├── YES ──► FULL_REQUIRED (Migrations, packages, Docker, settings)
                    └── NO
                         │
            Does it match `fast_eligible_patterns`?
                    ├── YES ──► FAST_ELIGIBLE (Whitelisted views, controllers, templates)
                    └── NO
                         │
                         ▼
                  UNKNOWN_BLOCKED
       (Unclassified file! Deployment halted for manual review)
```

1. **`FAST_ELIGIBLE`**: All changed files strictly match whitelisted stateless files (views, serializers, templates). Safe for in-place worker reload.
2. **`FULL_REQUIRED`**: At least one file matches a rebuild trigger (database migrations, dependency manifests, Dockerfiles, compose specs, compiled SPAs).
3. **`NO_OP`**: Only documentation, markdown, or ignored assets changed. No runtime deployment necessary.
4. **`UNKNOWN_BLOCKED`**: Changeset contains unclassified files, or Git diff could not be computed against a verified baseline. **Fails closed**.

---

## Real CLI Examples

### 1. Classify Changeset (Fast vs Full vs Blocked)
```bash
# Evaluate git diff between verified deployed commit and current HEAD:
python scripts/deploy_guardian.py classify --config guardian_config.json --base-commit a1b2c3d

# Or evaluate explicit files directly:
python scripts/deploy_guardian.py classify --config guardian_config.json --files app/views.py app/controllers/user.py
```

Output:
```text
=== Deployment Classification: FAST_ELIGIBLE (Risk: LOW) ===
Reason: All 2 modified file(s) match positive fast-eligible patterns with no schema or container changes.
Action: Safe for in-place worker reload or lightweight restart.
Command: ssh deploy-target 'app-fast-deploy'
```

### 2. Preflight Release Gate
```bash
# Verify local working tree and branch match:
python scripts/deploy_guardian.py preflight --config guardian_config.json

# Include live remote origin synchronization check:
python scripts/deploy_guardian.py preflight --config guardian_config.json --check-remote-sync

# Optional: Run read-only remote host telemetry (disk space, container status via SSH):
python scripts/deploy_guardian.py preflight --config guardian_config.json --check-remote-sync --check-remote-host
```

Output:
```text
=== Preflight Gate: PASS ===
Local Git: Clean on branch 'main' (HEAD: 3d21b75)
Remote Host: Connected. Disk Free: 14200 MB. Deployed: 3d21b75
```

### 3. Audit Command for Destructive Operations
```bash
python scripts/deploy_guardian.py audit-safety --command "docker compose down && docker volume prune -f"
```

Output:
```text
[SAFETY AUDIT: FAIL] Detected 1 dangerous pattern(s):
  - Snippet: 'docker volume prune' => Destructive Docker volume removal causes permanent data loss

Notice: Lexical command auditing is a heuristic defense-in-depth measure, not a formal sandbox boundary.
```

### 4. Post-Deploy Health Check
```bash
python scripts/deploy_guardian.py verify-health --config guardian_config.json
```

---

## Configuration (`guardian_config.json`)

```json
{
  "project_name": "ecommerce-api",
  "release_branch": "main",
  "remote": {
    "ssh_host": "deploy-server",
    "commit_file_path": "/var/run/deployed_commit",
    "min_disk_free_mb": 5120
  },
  "classification_rules": {
    "full_triggers": [
      { "pattern": "^migrations/|^db/migrate/", "reason": "Database migration detected" },
      { "pattern": "requirements.*\\.txt$|package\\.json$", "reason": "Dependency manifest modified" },
      { "pattern": "Dockerfile|docker-compose.*\\.ya?ml$", "reason": "Container configuration changed" },
      { "pattern": "^frontend/src/", "reason": "Frontend SPA source changed" }
    ],
    "fast_eligible_patterns": [
      "views?\\.py$",
      "controllers?/",
      "serializers?\\.py$",
      "templates/.*\\.html$"
    ],
    "ignore_patterns": ["^docs/", "\\.md$", "^\\.github/"]
  },
  "health_check": {
    "endpoints": [
      { "url": "https://api.example.com/healthz", "expected_status": 200, "timeout_seconds": 10 }
    ],
    "required_containers": ["app_web", "app_worker", "app_redis"]
  },
  "deployment_commands": {
    "fast": "ssh deploy-server 'app-fast-deploy'",
    "full": "ssh deploy-server 'app-full-deploy'"
  }
}
```

---

## Frequently Asked Questions (FAQ)

### Does passing preflight guarantee zero downtime?
**No.** Preflight ensures that your repository is clean, synchronized with remote origins, and verified locally. True zero downtime depends on your infrastructure: load balancer connection draining, rolling container updates, and backward-compatible non-blocking database migrations.

### Why does `classify` require an explicit `--base-commit`?
Assuming `HEAD~1` is unsafe in modern Git workflows because feature branches, squashed merges, and rebased commits often contain multiple revisions. If the deployed baseline is missing or unresolved, the classifier refuses to guess and fails closed (`UNKNOWN_BLOCKED`).

### Can regex safety auditing prove arbitrary shell scripts safe?
**No.** Lexical pattern scanning is a defense-in-depth heuristic designed to catch accidental destructive commands (like `docker volume prune` or `rm -rf /`). Obfuscated shell payloads cannot be proven safe statically. High-consequence operations must rely on explicit allowlists and human review.

### What happens when an unclassified file is changed?
If a changed file does not match `ignore_patterns`, `full_triggers`, or `fast_eligible_patterns`, the Guardian returns `UNKNOWN_BLOCKED` and exits with an error code. It halts the deployment and requests human confirmation rather than guessing.

---

## Deep Documentation

- [Deployment Mode Classification Matrix](references/mode_classification_matrix.md) — Detailed pattern catalog and edge cases
- [Autonomous Failure Triage Playbook](references/failure_triage_playbook.md) — 3-attempt bounded retry decision tree
- [Production Safety Invariants](references/safety_invariants.md) — Non-negotiable operational policies
- [Sample Deployment Scenarios](examples/sample_scenarios.md) — Realistic case studies

---

## Verified Compatibility

| Environment | Supported | Notes |
|---|---|---|
| **Python** | 3.8, 3.9, 3.10, 3.11, 3.12 | Standard library only; zero external dependencies. |
| **Platforms** | Linux, macOS, Windows | Path-agnostic and shell-agnostic. |
| **Agent Skills** | Specification v1.0 | Validated with official `skills-ref validate`. |
| **AI Agents** | Claude Code, Cursor, Codex, Antigravity | Indexed via `SKILL.md`. |

---

## Safety Boundaries & Limitations

- **No Zero-Downtime Guarantee**: Passing preflight does not guarantee zero-downtime; zero-downtime depends on your infrastructure's rolling deploy, load balancer draining, and database migration backward-compatibility.
- **Regex Limitations**: Lexical safety auditing is a defense-in-depth heuristic. Obfuscated shell payloads cannot be proven safe statically. Consequential operations must rely on allowlists and human review.

---

## Testing

Run the full automated test suite (29 tests):
```bash
python -m unittest discover -s tests
```

---

## License

This project is licensed under the [MIT License](LICENSE).
