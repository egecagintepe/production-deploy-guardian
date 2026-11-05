# Deployment Mode Classification Matrix

This reference documents the deterministic rules for classifying deployment changesets into **FAST_ELIGIBLE**, **FULL_REQUIRED**, **NO_OP**, and **UNKNOWN_BLOCKED**.

---

## 1. Explicit Positive Whitelisting

Modern web applications often combine backend runtimes (e.g., Python, Node, Ruby, Go) with database migrations, container images, compiled frontend Single Page Applications (SPAs), and static assets. Running a heavy container build and full restart for a single template typo wastes time and risks unnecessary downtime. Conversely, performing a lightweight in-place reload when dependencies or database schemas have changed causes immediate runtime failures.

To eliminate the danger of silently misclassifying unknown files as "safe for fast reload", the Deploy Guardian enforces **explicit positive eligibility**:

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

---

## 2. The Four Decision States

| Decision | Risk Level | Description | Recommended Action |
|---|---|---|---|
| **`NO_OP`** | Low | Only documentation, markdown, or explicitly ignored assets were modified. | No runtime deployment necessary. |
| **`FAST_ELIGIBLE`** | Low | All modified files match positive whitelist patterns (e.g. stateless views, controllers, templates) with zero schema or container changes. | Safe for in-place worker reload (`kill -HUP` or container restart). |
| **`FULL_REQUIRED`** | High / Medium | At least one modified file matches full triggers (database migrations, dependencies, Dockerfiles, compose specs, compiled frontends). | Execute full container rebuild, package installation, and database migration pipeline. |
| **`UNKNOWN_BLOCKED`** | Critical / High | Changeset includes files outside any known pattern, or Git commit diff could not be computed. | **Halt deployment**. Require operator review or explicit rule update. |

---

## 3. Pattern Matrix Reference

| Category | Typical File Patterns | Classification | Rationale |
|---|---|---|---|
| **Database Migrations** | `^migrations/`, `^db/migrate/`, `schema\.prisma`, `alembic/` | `FULL_REQUIRED` | Requires running ORM migrations (`migrate`), verifying schema locks, and synchronizing worker models. |
| **Backend Dependencies** | `requirements.*\.txt$`, `pyproject\.toml$`, `package\.json$`, `Gemfile$`, `go\.mod$`, `Cargo\.lock$` | `FULL_REQUIRED` | Requires container image rebuilding (`docker compose build`) or package manager installation (`pip install`, `npm ci`). |
| **Container & Orchestration** | `Dockerfile*`, `docker-compose.*\.ya?ml$`, `k8s/`, `helm/` | `FULL_REQUIRED` | Docker layer changes, environment definitions, port bindings, or volume mounts require recreating container services. |
| **Frontend SPAs** | `^frontend/src/`, `^client/`, `vite\.config`, `astro\.config`, `webpack\.config` | `FULL_REQUIRED` | Bundlers generate hashed assets (e.g. `index-[hash].js`). Serving new HTML with unbuilt asset hashes leads to immediate client-side 404 white screens. |
| **Deployment & Settings** | `^scripts/deploy.*`, `config/settings/` | `FULL_REQUIRED` | System-level environment handling, secret mappings, or static asset root changes must be applied cleanly across all daemons. |
| **Stateless Code (Whitelisted)** | `views?\.py$`, `controllers?/`, `serializers?\.py$`, `templates/.*\.html$`, `services?/` | `FAST_ELIGIBLE` | Code is interpreted; reloading application workers safely activates the new logic without image rebuilds. |
| **Documentation & CI (Ignored)** | `^docs/`, `\.md$`, `^\.github/`, `^\.git` | `NO_OP` | Non-runtime files do not alter production execution. |
| **Unclassified / Arbitrary Files** | Any file outside the above categories | `UNKNOWN_BLOCKED` | Fails closed. Cannot assume safety without explicit pattern definition. |

---

## 4. Conservative Fallback Rule

If git diff cannot be computed (e.g., shallow clone, missing commit hash on host, or disconnected remote), the classifier **fails closed** with `UNKNOWN_BLOCKED`. Never guess or assume a change is Fast if the diff boundary is unknown.
