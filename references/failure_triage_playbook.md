# Autonomous Failure Triage Playbook

This playbook establishes the protocol for autonomous agents and operators when a deployment fails. It balances self-healing capabilities with strict escalation boundaries to prevent cascading production failures.

---

## 1. Bounded Triage Loop

The agent is permitted up to **three (3) total deployment attempts** per release request.

```
Deployment Execution
       │
       ▼
Did deployment succeed?
  ├── YES ──► Proceed to Post-Deploy Health Verification
  └── NO  ──► Evaluate Failure Signature
                 │
                 ├── Safe Auto-Fixable? (Attempts < 3)
                 │     └── 1. Reproduce & fix locally in workspace
                 │         2. Run targeted test & linters
                 │         3. Commit and push to release branch
                 │         4. Increment attempt counter & retry deploy
                 │
                 └── Stateful / High Risk / Ambiguous / Attempt == 3
                       └── STOP IMMEDIATELY.
                           1. Capture logs & failure symptoms
                           2. Leave production in safe state
                           3. Report findings to operator
```

---

## 2. Failure Signatures

### Tier 1: Safe Auto-Fixable Failures (Eligible for Autonomous Remediation)

These errors are localized to application source code or build configuration and can be verified deterministically in the local workspace prior to redeployment:

1. **Syntax, Import, or Type Errors**:
   - `SyntaxError`, `ImportError`, `NameError`, TypeScript compile errors.
   - *Action*: Fix code typo, run unit tests, commit, push, and retry.
2. **Missing Manifest Dependency**:
   - `ModuleNotFoundError: No module named 'X'` when `X` is used in code but was omitted from `requirements.txt` or `package.json`.
   - *Action*: Add package to manifest with explicit pinned version, commit, push, and trigger Full deploy.
3. **Frontend Compilation or Asset Missing**:
   - Vite, Webpack, or Astro build failure during static collection.
   - *Action*: Resolve asset path or typescript error, verify build locally (`npm run build`), commit, push, and retry.
4. **Unit Test or Linter Regressions**:
   - Pre-deployment check fails due to updated business logic.
   - *Action*: Update test expectations to match new contract or fix implementation, verify tests pass locally, commit, and retry.

---

### Tier 2: Immediate Escalation & Blocker Failures (HALT IMMEDIATELY)

These conditions represent stateful data risks, hardware constraints, or external infrastructure outages. Autonomous guessing risks compounding the disaster:

1. **Database Migration Failures**:
   - Deadlocks, constraint violations (`IntegrityError`), non-nullable columns added without defaults, or ambiguous partial migrations.
   - *Why Halt*: Modifying database schema blindly can lead to permanent data loss or table locks. Never run `--fake` migrations without human approval.
2. **Disk Space Exhaustion**:
   - Root partition free space is below the safety threshold (e.g. `< 5GB`).
   - *Why Halt*: Building images on a full disk causes Docker daemon corruption and unrecoverable container panics.
3. **Persistent Container Crash Loops / Kernel OOMs**:
   - Container terminates immediately upon startup (`exit code 137` = OOMKilled, or database server crash).
   - *Why Halt*: Indicates severe memory exhaustion or fundamental service configuration mismatch.
4. **Secret or Credential Mismatch**:
   - Authentication errors connecting to production databases or payment gateways.
   - *Why Halt*: Agents must never guess passwords or tamper with production `.env` files.
5. **Network, DNS, or Tunnel Outage**:
   - Edge reverse proxy (Cloudflare, AWS ALB, Nginx) cannot reach host.
   - *Why Halt*: External infrastructure must be diagnosed from the network provider console.

