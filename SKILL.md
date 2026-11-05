---
name: production-deploy-guardian
description: Autonomous deployment guard and release engineer. Validates pre-release Git state, classifies deployment mode (Fast reload vs Full rebuild) based on commit diffs with positive whitelisting, runs preflight diagnostics, enforces zero-downtime safety invariants, guides bounded remediation loops, and verifies post-deploy health.
---

# Production Deploy Guardian

A robust, vendor-neutral skill for autonomous AI coding agents and DevOps engineers. It guarantees that code releases to remote or containerized environments fail closed on risk, automatically classify the safest deployment strategy using explicit positive whitelisting, respect strict non-destructive safety invariants, and verify live application health.

## Core Capabilities

1. **Pre-Release State Verification**: Validates branch alignment, clean working tree, remote synchronization, and unpushed commits. Supports live remote synchronization checks.
2. **Deterministic Mode Classification**: Analyzes file diffs against the currently deployed commit. Classifies into 4 explicit states (`FAST_ELIGIBLE`, `FULL_REQUIRED`, `NO_OP`, `UNKNOWN_BLOCKED`).
3. **Fail-Closed Preflight Telemetry**: Separates local Git verification from safe remote host telemetry (root disk space thresholds, container engine responsiveness, deployed revision hash).
4. **Non-Destructive Safety Enforcement**: Detects and blocks destructive operations (`volume prune`, `volume rm`, recursive storage deletions, force pushes, raw table drops, secret leaks).
5. **Bounded Autonomous Remediation**: Provides a structured 3-attempt triage loop for safe, local code fixes while enforcing immediate escalation on stateful, database, or infrastructure failures.
6. **Post-Deployment Health Smoke Verification**: Probes critical HTTP routes, inspects container states, and verifies deployed revision hashes.

---

## Activation & Triggers

Activate this skill when:
- Preparing a production release or staging rollout.
- Running deployment preflight checks or evaluating release readiness.
- Determining whether a change requires container image rebuilds or database migrations.
- Diagnosing a failed deployment or recovering from a deploy-time regression.
- Reviewing deployment scripts or workflows for destructive operations and safety vulnerabilities.

---

## Authoritative Workflow

```
       ┌────────────────────────┐
       │ 1. Git State Preflight │ (Local clean tree, branch match, live remote sync)
       └───────────┬────────────┘
                   │ Pass
                   ▼
       ┌────────────────────────┐
       │ 2. Remote Diagnostics  │ (Optional safe SSH: disk, containers, deployed hash)
       └───────────┬────────────┘
                   │ Pass
                   ▼
       ┌────────────────────────┐
       │ 3. Mode Classification │ (Fast vs Full vs Blocked via explicit whitelisting)
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │ 4. Guarded Deployment  │ (Execute authoritative deployment command)
       └───────────┬────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
      Success             Failure
         │                   │
         ▼                   ▼
┌──────────────────┐   ┌─────────────────────────────┐
│ 5. Health Check  │   │ Bounded Recovery Loop (≤ 3) │
└──────────────────┘   │ Auto-fix locally or STOP    │
                       └─────────────────────────────┘
```

### Step 1: Pre-Release Quality & Git Gate

Before executing any remote operation:
1. Verify repository root and current branch. Releases must originate from the designated release branch (e.g. `main` or `master`).
2. Verify that the working tree is clean (`git status --porcelain`). Never deploy uncommitted work.
3. Check remote synchronization against live remote `origin/<branch>`.
4. Run project-specific linting, typing, and local unit test suites.
5. If migration definitions exist, verify migration graph consistency (`makemigrations --check --dry-run` or ORM equivalent).

Run the automated guardian preflight:
```bash
# Local git preflight (default)
python scripts/deploy_guardian.py preflight --config guardian_config.json

# Local git + live remote origin sync check
python scripts/deploy_guardian.py preflight --config guardian_config.json --check-remote-sync

# Full preflight including safe remote host telemetry (via SSH)
python scripts/deploy_guardian.py preflight --config guardian_config.json --check-remote-sync --check-remote-host
```

### Step 2: Change-Set Mode Classification

Compute the diff between the currently deployed commit hash and local `HEAD`:
```bash
python scripts/deploy_guardian.py classify --config guardian_config.json --base-commit <PREV_COMMIT>
```

- **`FULL_REQUIRED`** is triggered when any of the following patterns are touched:
  - Database schema / migrations (`migrations/`, `db/migrate/`, `schema.prisma`, `alembic/`)
  - Dependency manifests (`requirements*.txt`, `pyproject.toml`, `package.json`, `Gemfile`, `go.mod`)
  - Container / Orchestration specs (`Dockerfile*`, `docker-compose*.yml`, `k8s/`, `helm/`)
  - Frontend SPA sources requiring compilation (`frontend/src/`, `vite.config.*`, `astro.config.*`)
  - System settings or deployment scripts (`config/settings/`, `scripts/deploy*.sh`)
- **`FAST_ELIGIBLE`** is permitted ONLY when all modified files match positive whitelist patterns:
  - Stateless backend views, controllers, serializers, helper functions
  - Server-rendered templates or static styling tweaks
  - No database migrations, no dependency manifest changes, no container updates
- **`UNKNOWN_BLOCKED`** is triggered if any modified file does not match known rules, or if commit diff cannot be resolved:
  - **Halt deployment immediately** and report unclassified files for manual operator review.

### Step 3: Production Safety Invariants

Under no circumstances should the agent run or generate commands for:
- `docker volume prune`, `docker volume rm`, or `docker system prune -a --volumes`
- Indiscriminate recursive deletions on persistent data directories (`rm -rf /var/lib/*` or storage volumes)
- Unauthenticated or forced resets (`git reset --hard` or `git clean -fdx` on remote hosts)
- Force pushing to release branches (`git push --force`)
- Destructive raw SQL statements (`DROP DATABASE`, `DROP TABLE`, `TRUNCATE`)
- Echoing, logging, or printing raw secret values or `.env` files to transcripts or logs

### Step 4: Autonomous Error Triage Loop

If the deployment command fails, follow the bounded triage protocol (maximum 3 attempts):

1. **Classify the Failure**:
   - **Safe Auto-Fixable (Proceed to local fix)**:
     - Syntax, typing, or compilation errors
     - Missing imported modules or missing dependencies in manifest
     - Unit test or lint failures caused by code logic
     - Frontend asset build failures
   - **Immediate Stop & Escalate (Halt and prompt operator)**:
     - Database migration deadlocks, schema corruption, or conflicting migrations
     - Host disk space exhaustion
     - Database connection refused or persistent container crash loops
     - SSL, domain, tunnel, or network partition errors
     - Third failed deployment attempt
2. **Execute Remediation**:
   - Apply fix locally in the development workspace.
   - Run local validation and unit tests.
   - Commit and push to the remote branch.
   - Retry deployment with incremented attempt counter.

### Step 5: Post-Deployment Health Verification

Verify application health immediately after deployment:
```bash
python scripts/deploy_guardian.py verify-health --config guardian_config.json
```
Ensure:
1. All critical HTTP endpoints return `200 OK` (or valid configured redirects).
2. Container daemon reports all core application services in healthy/running state.
3. The deployed commit hash registered on the host matches the expected release `HEAD`.

---

## Detailed References

- For diff pattern definitions and trigger rules, consult [references/mode_classification_matrix.md](references/mode_classification_matrix.md).
- For remediation decision trees and incident triage, consult [references/failure_triage_playbook.md](references/failure_triage_playbook.md).
- For mandatory security and non-destructive policies, consult [references/safety_invariants.md](references/safety_invariants.md).
