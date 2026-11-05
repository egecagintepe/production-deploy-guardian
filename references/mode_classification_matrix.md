# Deployment Mode Classification Matrix

This reference documents the deterministic rules for classifying deployment changesets into **Fast Reload** versus **Full Rebuild**.

## Overview

Modern web applications often combine backend runtimes (e.g., Python, Node, Ruby, Go) with database migrations, container images, compiled frontend Single Page Applications (SPAs), and static assets. Running a heavy container build and full restart for a single template typo wastes time and risks unnecessary downtime. Conversely, performing a lightweight in-place reload when dependencies or database schemas have changed causes immediate runtime failures (`ModuleNotFoundError`, `OperationalError`, white-screen asset mismatches).

The Deploy Guardian enforces a binary classification:

1. **Full Rebuild (`Full`)**: Required whenever state, dependencies, system configurations, or build assets change.
2. **Fast In-Place Reload (`Fast`)**: Permitted only when all modifications are provably confined to stateless, interpreted code or server-side templates.
3. **No-Op (`No-Op`)**: When changes only touch documentation or ignored paths.

---

## Pattern Matrix

| Category | File Pattern | Classification | Rationale & Actions |
|---|---|---|---|
| **Database Migrations** | `^migrations/`, `^db/migrate/`, `schema\.prisma`, `alembic/` | **Full** | Requires running ORM migrations (`migrate`), checking schema locks, and synchronizing worker models. |
| **Backend Dependencies** | `requirements.*\.txt$`, `pyproject\.toml$`, `package\.json$`, `Gemfile$`, `go\.mod$` | **Full** | Requires container image rebuilding (`docker compose build`) or package manager installation (`pip install`, `npm ci`). Restarting a container without rebuilding does not install new packages. |
| **Container & Orchestration** | `Dockerfile*`, `docker-compose.*\.ya?ml$`, `k8s/`, `helm/` | **Full** | Docker layer changes, environment definitions, port bindings, or volume mounts require recreating container services. |
| **Frontend SPAs** | `^frontend/src/`, `^client/`, `vite\.config`, `astro\.config`, `webpack\.config` | **Full** | Bundlers generate hashed assets (e.g. `index-[hash].js`). Serving new HTML with unbuilt asset hashes leads to immediate client-side 404 white screens. |
| **Deployment & Settings** | `^scripts/deploy.*`, `config/settings/` | **Full** | System-level environment handling, secret mappings, or static asset root changes must be applied cleanly across all daemons. |
| **Stateless Views / Controllers** | `views\.py`, `controllers/`, `handlers/`, `serializers/` | **Fast** | Code is interpreted; reloading application workers (e.g. `kill -HUP` or container restart) safely activates the new logic without image rebuilds. |
| **Server-Rendered Templates** | `templates/.*\.html`, `views/.*\.erb` | **Fast** | Handled dynamically by the template engine. (Note: if new static asset tags are introduced, verify static collection). |
| **Documentation & CI** | `^docs/`, `\.md$`, `^\.github/`, `^\.git` | **No-Op / Ignored** | Non-runtime files do not alter production execution. |

---

## Conservative Fallback Rule

If git diff cannot be computed (e.g., shallow clone, missing commit hash on host, or disconnected remote), the classifier **fails closed** and triggers **Full Rebuild**. Never guess or assume a change is Fast if the diff boundary is unknown.
