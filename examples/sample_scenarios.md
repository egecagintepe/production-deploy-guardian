# Sample Deployment Scenarios

This document illustrates realistic scenarios evaluated by the Production Deploy Guardian.

---

## Scenario A: Frontend Feature Release

**Changeset**:
- `frontend/src/components/UserProfile.vue`
- `frontend/src/styles/theme.css`
- `docs/RELEASE_NOTES.md`

**Guardian Classification**:
```bash
python scripts/deploy_guardian.py classify --files frontend/src/components/UserProfile.vue frontend/src/styles/theme.css docs/RELEASE_NOTES.md --config guardian_config.example.json
```

**Output**:
```
[CLASSIFICATION] Mode: Full
Reason: Full rebuild required due to 2 trigger(s).
Matched Triggers:
  - frontend/src/components/UserProfile.vue -> Frontend SPA source modified requiring compilation
  - frontend/src/styles/theme.css -> Frontend SPA source modified requiring compilation
Authoritative Command: ssh deploy-target 'app-full-deploy'
```

*Analysis*: Because compiled frontend source files were touched, the guardian mandates a Full rebuild to prevent asset hash mismatches and client white screens.

---

## Scenario B: Backend View Hotfix

**Changeset**:
- `app/views/order_summary.py`
- `app/serializers/order.py`

**Guardian Classification**:
```bash
python scripts/deploy_guardian.py classify --files app/views/order_summary.py app/serializers/order.py --config guardian_config.example.json
```

**Output**:
```
[CLASSIFICATION] Mode: Fast
Reason: Safe for fast in-place reload (2 file(s) modified).
Authoritative Command: ssh deploy-target 'app-fast-deploy'
```

*Analysis*: All changes are contained within stateless Python handlers with no database migrations or dependency updates. A fast in-place worker reload is chosen.

---

## Scenario C: Documentation Update

**Changeset**:
- `README.md`
- `docs/architecture.md`

**Guardian Classification**:
```bash
python scripts/deploy_guardian.py classify --files README.md docs/architecture.md --config guardian_config.example.json
```

**Output**:
```
[CLASSIFICATION] Mode: No-Op
Reason: All changed files match ignore patterns (e.g. docs/comments).
Authoritative Command: None (Documentation or ignored files only)
```

*Analysis*: Documentation changes require no server restart or deployment pipeline trigger.

---

## Scenario D: Safety Violation Detection

**Command to audit**:
```bash
docker compose down && docker volume prune -f && docker compose up -d
```

**Guardian Audit**:
```bash
python scripts/deploy_guardian.py audit-safety --command "docker compose down && docker volume prune -f && docker compose up -d"
```

**Output**:
```
[SAFETY AUDIT: FAIL] Detected 1 forbidden pattern(s):
  - Pattern: 'docker volume prune' => Indiscriminate Docker volume prune causes permanent data loss
```

*Analysis*: The dangerous volume prune operation is immediately caught and blocked.
