# Production Safety Invariants

This document outlines the inviolable safety rules that all automated workflows, agent skills, and deployment scripts must respect.

---

## 1. Zero Data Loss Policy

Production databases and persistent volumes are authoritative. The skill enforces a strict prohibition against destructive storage actions:

- **Forbidden: Docker Volume Prune**:
  Never execute `docker volume prune` or `docker system prune -a --volumes`. Running this destroys named volumes, uploaded media, and embedded database stores.
- **Forbidden: Unscoped File Deletions**:
  Never execute `rm -rf` against system roots, user directories, persistent database volumes, or media paths. File cleanup must be target-specific (e.g. `docker image prune -f` for dangling build layers only).
- **Forbidden: Destructive Schema Alterations**:
  Never execute raw `DROP TABLE`, `DROP DATABASE`, or `TRUNCATE` operations against production data stores. Schema changes must occur exclusively through versioned, backwards-compatible ORM migration files.

---

## 2. Remote Host Integrity

- **Forbidden: In-Place Remote Editing**:
  Never use SSH or container exec to hotpatch production source code files directly on the server. All code changes must originate from the local Git workspace, pass local verification, be committed with meaningful messages, pushed to the remote repository, and pulled through the standard deployment pipeline.
- **Forbidden: Destructive Git Commands**:
  Never run `git reset --hard` or `git clean -fdx` on production checkouts. If remote checkouts carry local state, investigate why unexpected files exist before touching them.
- **Forbidden: Force Push**:
  Never execute `git push --force` or `--force-with-lease` against release branches (`main`, `master`, `production`).

---

## 3. Secret and Credential Confidentiality

- **Forbidden: Secret Printing**:
  Never print, echo, cat, or dump `.env` files, database connection strings, API tokens, or private SSH keys into terminal outputs, transcripts, or incident reports.
- **Safe Auditing**:
  When diagnosing environment mismatches, verify only variable *names* and boolean existence (e.g. "DATABASE_URL is set"), never their plaintext contents.

---

## 4. Verification Before Declaration

A deployment is not successful merely because the deployment script exited with code 0. Success requires:
1. Container status check confirms all intended services are running (not restarting).
2. HTTP health checks against live endpoints return expected status codes.
3. The deployed commit recorded by the server matches the commit requested for release.

