#!/usr/bin/env python3
"""
Production Deploy Guardian CLI.
Autonomous deployment safety guard, changeset classifier, preflight gate, and health verifier.
Standard library only (zero external dependencies).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
import time
from typing import Dict, List, Optional, Tuple, Any

# Destructive command patterns for defense-in-depth scanning
DANGEROUS_COMMAND_PATTERNS = [
    (r"docker\s+volume\s+(prune|rm)", "Destructive Docker volume removal causes permanent data loss"),
    (r"docker\s+system\s+prune.*(-a|--all)?.*--volumes", "Docker system prune with --volumes deletes persistent state"),
    (r"podman\s+volume\s+(prune|rm)", "Destructive Podman volume removal causes permanent data loss"),
    (r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(/|/var|/etc|/opt|/home|/root|/var/lib|/data|media|backups)", "Dangerous recursive deletion on persistent root or storage path"),
    (r"git\s+push\s+.*(--force|-f|\+[a-zA-Z0-9_\-\/]+)", "Force pushing destroys remote Git history"),
    (r"git\s+reset\s+--hard", "Hard reset on production host destroys uncommitted state or detaches heads"),
    (r"git\s+clean\s+-[a-zA-Z]*f[a-zA-Z]*", "Git clean forcibly removes untracked working tree files"),
    (r"DROP\s+(DATABASE|SCHEMA|TABLE)\s+", "Destructive raw SQL drop statement"),
    (r"TRUNCATE\s+(TABLE\s+)?", "Destructive raw SQL truncate statement"),
    (r"(cat|type|echo|more|less|head|tail)\s+.*\.env(\s+|$|;|>|\|)", "Echoing or dumping raw .env contents leaks secrets into logs"),
    (r"mkfs(\.[a-zA-Z0-9]+)?\s+", "Filesystem formatting command destroys partition data"),
    (r">\s*/dev/(sd[a-z]|nvme[0-9]n[0-9]|null)", "Raw disk block overwrite")
]

LIMITATION_NOTICE = (
    "Lexical and regex command auditing is a heuristic defense-in-depth measure, "
    "not a formal sandbox or security boundary. Obfuscated commands, shell aliases, "
    "eval blocks, and variable expansions cannot be proven safe statically. "
    "Consequential production operations must rely on strict allowlists and human review."
)

def load_config(config_path: str) -> Dict[str, Any]:
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_cmd(cmd: List[str], cwd: Optional[str] = None, timeout: int = 30) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return 1, "", str(e)

def get_git_diff_files(base_commit: Optional[str], target_commit: str = "HEAD", cwd: Optional[str] = None) -> Tuple[bool, List[str], str]:
    if not base_commit or not base_commit.strip():
        return False, [], "Missing verified deployment baseline commit (--base-commit). Cannot assume HEAD~1 represents deployed state."
    code, out, err = run_cmd(["git", "diff", "--name-only", base_commit.strip(), target_commit], cwd=cwd)
    if code != 0:
        return False, [], f"git diff between {base_commit} and {target_commit} failed: {err}"
    return True, [line.strip() for line in out.splitlines() if line.strip()], ""

def classify_changes(diff_files: List[str], config: Dict[str, Any], diff_resolved: bool = True) -> Dict[str, Any]:
    """
    Evaluates changeset with explicit positive eligibility.
    Decisions:
      - NO_OP: Only documentation or explicitly ignored files changed.
      - FAST_ELIGIBLE: All changed files match fast_eligible_patterns, none trigger full rebuild.
      - FULL_REQUIRED: At least one file matches full_triggers.
      - UNKNOWN_BLOCKED: Diff could not be resolved, or changes include files outside any rule.
    """
    rules = config.get("classification_rules", {})
    full_triggers = rules.get("full_triggers", [])
    fast_patterns = rules.get("fast_eligible_patterns", [])
    ignore_patterns = rules.get("ignore_patterns", [])

    commands = config.get("deployment_commands", {})

    # If git diff failed or could not be determined
    if not diff_resolved:
        return {
            "decision": "UNKNOWN_BLOCKED",
            "risk_level": "CRITICAL_BLOCKED",
            "reason": "Unable to resolve Git commit diff against verified deployment baseline commit. Deployment blocked pending verification.",
            "unclassified_files": [],
            "matched_triggers": [],
            "migration_impact": [],
            "dependency_impact": [],
            "container_impact": [],
            "recommended_action": "Verify commit hashes and execute full rebuild manually or specify base commit explicitly.",
            "recommended_command": commands.get("full", ""),
            "stop_conditions": ["Unresolved git diff", "Missing previous deployment reference"]
        }

    if not diff_files:
        return {
            "decision": "NO_OP",
            "risk_level": "LOW",
            "reason": "Zero modified files detected between target commit and base commit.",
            "unclassified_files": [],
            "matched_triggers": [],
            "migration_impact": [],
            "dependency_impact": [],
            "container_impact": [],
            "recommended_action": "No deployment action necessary.",
            "recommended_command": "None",
            "stop_conditions": []
        }

    matched_full = []
    migration_files = []
    dependency_files = []
    container_files = []

    fast_eligible_files = []
    ignored_files = []
    unclassified_files = []

    migration_regex = re.compile(r"(migrations/|db/migrate/|schema\.prisma|alembic/)", re.IGNORECASE)
    dependency_regex = re.compile(r"(requirements.*\.txt$|pyproject\.toml$|package(-lock)?\.json$|Gemfile|go\.mod$|Cargo\.lock$)", re.IGNORECASE)
    container_regex = re.compile(r"(Dockerfile|docker-compose.*\.ya?ml$|\.docker/|k8s/|helm/)", re.IGNORECASE)

    for f in diff_files:
        is_ignored = any(re.search(pat, f) for pat in ignore_patterns)
        if is_ignored:
            ignored_files.append(f)
            continue

        is_full = False
        for trig in full_triggers:
            pattern = trig.get("pattern", "")
            reason = trig.get("reason", "Rule matched")
            if pattern and re.search(pattern, f):
                matched_full.append({"file": f, "pattern": pattern, "reason": reason})
                is_full = True
                break

        if is_full:
            if migration_regex.search(f):
                migration_files.append(f)
            if dependency_regex.search(f):
                dependency_files.append(f)
            if container_regex.search(f):
                container_files.append(f)
            continue

        # Check explicit positive fast eligibility
        is_fast = any(re.search(pat, f) for pat in fast_patterns)
        if is_fast:
            fast_eligible_files.append(f)
        else:
            # File is NOT ignored, NOT in full triggers, and NOT in fast whitelist
            unclassified_files.append(f)

    # Decision Matrix
    if unclassified_files:
        decision = "UNKNOWN_BLOCKED"
        risk = "HIGH"
        reason = f"Changeset contains {len(unclassified_files)} unclassified file(s) that do not match fast-eligible or ignore rules."
        action = "Manual inspection required. Update classification rules or execute full build with review."
        cmd = commands.get("full", "")
    elif matched_full:
        decision = "FULL_REQUIRED"
        risk = "HIGH" if (migration_files or container_files) else "MEDIUM"
        reason = f"Full rebuild required due to {len(matched_full)} trigger(s) across {len(diff_files)} file(s)."
        action = "Execute full container/dependency rebuild and migration pipeline."
        cmd = commands.get("full", "")
    elif fast_eligible_files:
        decision = "FAST_ELIGIBLE"
        risk = "LOW"
        reason = f"All {len(fast_eligible_files)} modified file(s) match positive fast-eligible patterns with no schema or container changes."
        action = "Safe for in-place worker reload or lightweight restart."
        cmd = commands.get("fast", "")
    else:
        decision = "NO_OP"
        risk = "LOW"
        reason = f"All {len(ignored_files)} modified file(s) are documentation or non-runtime assets."
        action = "No runtime deployment needed."
        cmd = "None"

    return {
        "decision": decision,
        "risk_level": risk,
        "reason": reason,
        "unclassified_files": unclassified_files,
        "matched_triggers": matched_full,
        "migration_impact": migration_files,
        "dependency_impact": dependency_files,
        "container_impact": container_files,
        "recommended_action": action,
        "recommended_command": cmd,
        "stop_conditions": [
            "Database migration conflict or lock timeout",
            "Root partition free disk space below threshold",
            "More than 3 failed deployment attempts"
        ]
    }

def check_local_git(expected_branch: str, check_remote_sync: bool = False, cwd: Optional[str] = None) -> Dict[str, Any]:
    results = {
        "clean": False,
        "branch_ok": False,
        "synced_with_remote": False,
        "current_branch": "",
        "local_head": "",
        "remote_head": "",
        "errors": []
    }
    
    code, current_branch, err = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if code != 0:
        results["errors"].append(f"Git branch check failed: {err}")
        return results

    results["current_branch"] = current_branch
    if current_branch != expected_branch:
        results["errors"].append(f"Expected release branch '{expected_branch}', but currently on '{current_branch}'")
    else:
        results["branch_ok"] = True

    code, status, _ = run_cmd(["git", "status", "--porcelain"], cwd=cwd)
    if code == 0 and not status:
        results["clean"] = True
    else:
        results["errors"].append("Working tree has uncommitted or untracked changes.")

    code, local_head, _ = run_cmd(["git", "rev-parse", "HEAD"], cwd=cwd)
    results["local_head"] = local_head if code == 0 else ""

    if check_remote_sync:
        # Query live remote reference without relying solely on local cache
        code_ls, remote_ls, err_ls = run_cmd(["git", "ls-remote", "origin", f"refs/heads/{expected_branch}"], cwd=cwd)
        if code_ls == 0 and remote_ls:
            remote_head = remote_ls.split()[0].strip()
            results["remote_head"] = remote_head
            if local_head == remote_head:
                results["synced_with_remote"] = True
            else:
                results["errors"].append(
                    f"Local HEAD ({local_head[:8]}) does not match live remote origin/{expected_branch} ({remote_head[:8]}). Push or pull first."
                )
        else:
            # Fall back to local tracking reference
            code_rem, remote_head, _ = run_cmd(["git", "rev-parse", f"origin/{expected_branch}"], cwd=cwd)
            if code == 0 and code_rem == 0:
                results["remote_head"] = remote_head
                if local_head == remote_head:
                    results["synced_with_remote"] = True
                else:
                    results["errors"].append(f"Local HEAD ({local_head[:8]}) differs from tracked origin/{expected_branch} ({remote_head[:8]}).")
            else:
                results["errors"].append(f"Could not verify remote origin/{expected_branch}: {err_ls}")
    else:
        results["synced_with_remote"] = True

    return results

def check_remote_host(ssh_host: str, min_disk_mb: int = 5120, commit_path: str = "/var/run/deployed_commit", required_containers: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Performs read-only remote host diagnostics via SSH. Fails closed on any error.
    """
    res = {
        "ssh_connected": False,
        "disk_ok": False,
        "free_disk_mb": 0,
        "deployed_commit": "",
        "containers_ok": False,
        "running_containers": [],
        "errors": []
    }

    test_cmd = (
        f"echo SSH_OK; "
        f"echo '---DF---'; df -m /; "
        f"echo '---COMMIT---'; cat {commit_path} 2>/dev/null || true; "
        f"echo '---CONTAINERS---'; (docker ps --format '{{{{.Names}}}}' 2>/dev/null || podman ps --format '{{{{.Names}}}}' 2>/dev/null || true)"
    )

    ssh_args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", ssh_host, test_cmd]
    code, stdout, stderr = run_cmd(ssh_args, timeout=15)

    if code != 0 or "SSH_OK" not in stdout:
        res["errors"].append(f"Cannot reach remote host '{ssh_host}' via SSH: {stderr or stdout}")
        return res

    res["ssh_connected"] = True

    # Parse disk space
    df_match = re.search(r"---DF---\s*[\r\n]+([^\r\n]+)[\r\n]+([^\r\n]+)", stdout)
    if df_match:
        data_line = df_match.group(2).strip()
        tokens = re.split(r"\s+", data_line)
        if len(tokens) >= 4 and tokens[3].isdigit():
            res["free_disk_mb"] = int(tokens[3])
            if res["free_disk_mb"] >= min_disk_mb:
                res["disk_ok"] = True
            else:
                res["errors"].append(f"Remote disk free space ({res['free_disk_mb']} MB) is below threshold ({min_disk_mb} MB).")
        else:
            res["errors"].append(f"Unable to parse free disk space from: {data_line}")
    else:
        res["errors"].append("Could not extract disk usage from remote df output.")

    # Parse deployed commit
    commit_match = re.search(r"---COMMIT---\s*[\r\n]+([0-9a-fA-F]{7,40})", stdout)
    if commit_match:
        res["deployed_commit"] = commit_match.group(1).strip()

    # Parse running containers
    cont_match = re.search(r"---CONTAINERS---\s*[\r\n]+([\s\S]*?)$", stdout)
    if cont_match:
        lines = [c.strip() for c in cont_match.group(1).splitlines() if c.strip()]
        res["running_containers"] = lines
        if required_containers:
            missing = [c for c in required_containers if c not in lines]
            if missing:
                res["errors"].append(f"Missing required running container(s): {', '.join(missing)}")
            else:
                res["containers_ok"] = True
        else:
            res["containers_ok"] = True

    return res

def audit_safety_string(text: str) -> Dict[str, Any]:
    violations = []
    for pat, desc in DANGEROUS_COMMAND_PATTERNS:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            violations.append({
                "matched_pattern": pat,
                "description": desc,
                "snippet": match.group(0).strip()
            })
    return {
        "safe": len(violations) == 0,
        "violations": violations,
        "limitation_notice": LIMITATION_NOTICE
    }

def probe_http_health(url: str, expected_status: int = 200, timeout: int = 10, retries: int = 3, backoff: float = 2.0) -> bool:
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ProductionDeployGuardian/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == expected_status:
                    return True
        except urllib.error.HTTPError as e:
            if e.code == expected_status:
                return True
        except Exception:
            pass
        if attempt < retries:
            time.sleep(backoff)
    return False

def main():
    parser = argparse.ArgumentParser(description="Production Deploy Guardian CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: classify
    cls_parser = subparsers.add_parser("classify", help="Classify deployment mode from git diff with positive eligibility")
    cls_parser.add_argument("--config", default="guardian_config.json", help="Path to guardian_config.json")
    cls_parser.add_argument("--base-commit", default=None, help="Previously deployed commit hash")
    cls_parser.add_argument("--target-commit", default="HEAD", help="Target commit hash")
    cls_parser.add_argument("--files", nargs="*", default=None, help="Explicit list of files to evaluate instead of git diff")
    cls_parser.add_argument("--json", action="store_true", help="Output pure JSON")

    # Subcommand: preflight
    pf_parser = subparsers.add_parser("preflight", help="Run pre-release local git and optional remote diagnostics")
    pf_parser.add_argument("--config", default="guardian_config.json", help="Path to config file")
    pf_parser.add_argument("--check-remote-sync", action="store_true", help="Check live remote origin branch sync")
    pf_parser.add_argument("--check-remote-host", action="store_true", help="Run safe remote SSH telemetry (disk, containers)")
    pf_parser.add_argument("--json", action="store_true", help="Output pure JSON")

    # Subcommand: audit-safety
    audit_parser = subparsers.add_parser("audit-safety", help="Scan commands or script files for dangerous operations")
    audit_parser.add_argument("--file", help="Path to script file to inspect")
    audit_parser.add_argument("--command", help="Raw command line string to inspect")
    audit_parser.add_argument("--json", action="store_true", help="Output pure JSON")

    # Subcommand: verify-health
    health_parser = subparsers.add_parser("verify-health", help="Verify post-deployment HTTP endpoints")
    health_parser.add_argument("--config", default="guardian_config.json", help="Path to config file")
    health_parser.add_argument("--url", help="Direct endpoint URL to probe")
    health_parser.add_argument("--expected-status", type=int, default=200, help="Expected HTTP status")
    health_parser.add_argument("--retries", type=int, default=3, help="Number of retry attempts")
    health_parser.add_argument("--json", action="store_true", help="Output pure JSON")

    args = parser.parse_args()

    if args.subcommand == "classify":
        cfg = load_config(args.config)
        diff_resolved = True
        if args.files is not None:
            files = args.files
        else:
            diff_resolved, files, diff_err = get_git_diff_files(args.base_commit, args.target_commit)

        res = classify_changes(files, cfg, diff_resolved=diff_resolved)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"=== Deployment Classification: {res['decision']} (Risk: {res['risk_level']}) ===")
            print(f"Reason: {res['reason']}")
            if res["unclassified_files"]:
                print("Unclassified Files (Requires Review):")
                for uf in res["unclassified_files"]:
                    print(f"  ? {uf}")
            if res["matched_triggers"]:
                print("Full Rebuild Triggers:")
                for r in res["matched_triggers"]:
                    print(f"  ! {r['file']} -> {r['reason']}")
            if res["migration_impact"]:
                print(f"Database Migrations ({len(res['migration_impact'])}): {', '.join(res['migration_impact'])}")
            if res["dependency_impact"]:
                print(f"Dependency Updates ({len(res['dependency_impact'])}): {', '.join(res['dependency_impact'])}")
            print(f"Action: {res['recommended_action']}")
            if res["recommended_command"]:
                print(f"Command: {res['recommended_command']}")

        sys.exit(0 if res["decision"] in ("FAST_ELIGIBLE", "NO_OP", "FULL_REQUIRED") else 1)

    elif args.subcommand == "preflight":
        cfg = load_config(args.config)
        branch = cfg.get("release_branch", "main")
        git_res = check_local_git(branch, check_remote_sync=args.check_remote_sync)
        local_passed = git_res["clean"] and git_res["branch_ok"] and git_res["synced_with_remote"]

        remote_res = None
        remote_passed = True
        if args.check_remote_host:
            remote_cfg = cfg.get("remote", {})
            host = remote_cfg.get("ssh_host")
            if not host:
                remote_passed = False
                remote_res = {"errors": ["No remote.ssh_host specified in configuration."]}
            else:
                min_disk = remote_cfg.get("min_disk_free_mb", 5120)
                commit_path = remote_cfg.get("commit_file_path", "/var/run/deployed_commit")
                req_containers = cfg.get("health_check", {}).get("required_containers", [])
                remote_res = check_remote_host(host, min_disk_mb=min_disk, commit_path=commit_path, required_containers=req_containers)
                remote_passed = remote_res["ssh_connected"] and remote_res["disk_ok"] and remote_res["containers_ok"]

        overall_passed = local_passed and remote_passed
        output = {
            "passed": overall_passed,
            "local_git": git_res,
            "remote_host": remote_res
        }

        if args.json:
            print(json.dumps(output, indent=2))
        else:
            status_text = "PASS" if overall_passed else "FAIL"
            print(f"=== Preflight Gate: {status_text} ===")
            if not local_passed:
                print("Local Git Issues:")
                for err in git_res["errors"]:
                    print(f"  - {err}")
            else:
                print(f"Local Git: Clean on branch '{git_res['current_branch']}' (HEAD: {git_res['local_head'][:8]})")

            if args.check_remote_host and remote_res:
                if not remote_passed:
                    print("Remote Host Issues:")
                    for err in remote_res["errors"]:
                        print(f"  - {err}")
                else:
                    print(f"Remote Host: Connected. Disk Free: {remote_res['free_disk_mb']} MB. Deployed: {remote_res['deployed_commit'][:8] if remote_res['deployed_commit'] else 'None'}")

        sys.exit(0 if overall_passed else 1)

    elif args.subcommand == "audit-safety":
        content = ""
        if args.file:
            if not os.path.isfile(args.file):
                print(f"File not found: {args.file}", file=sys.stderr)
                sys.exit(1)
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        elif args.command:
            content = args.command
        else:
            print("Provide either --file or --command to audit", file=sys.stderr)
            sys.exit(1)

        audit_res = audit_safety_string(content)
        if args.json:
            print(json.dumps(audit_res, indent=2))
        else:
            if audit_res["safe"]:
                print("[SAFETY AUDIT: PASS] No forbidden destructive operations detected.")
            else:
                print(f"[SAFETY AUDIT: FAIL] Detected {len(audit_res['violations'])} dangerous pattern(s):")
                for v in audit_res["violations"]:
                    print(f"  - Snippet: '{v['snippet']}' => {v['description']}")
            print(f"\nNotice: {audit_res['limitation_notice']}")
        sys.exit(0 if audit_res["safe"] else 1)

    elif args.subcommand == "verify-health":
        if args.url:
            endpoints = [{"url": args.url, "expected_status": args.expected_status}]
        else:
            cfg = load_config(args.config)
            endpoints = cfg.get("health_check", {}).get("endpoints", [])

        if not endpoints:
            print("No health check endpoints defined.", file=sys.stderr)
            sys.exit(1)

        all_ok = True
        results = []
        for ep in endpoints:
            url = ep.get("url")
            expected = ep.get("expected_status", 200)
            timeout = ep.get("timeout_seconds", 10)
            ok = probe_http_health(url, expected_status=expected, timeout=timeout, retries=args.retries)
            results.append({"url": url, "expected_status": expected, "ok": ok})
            if not ok:
                all_ok = False

        if args.json:
            print(json.dumps({"healthy": all_ok, "results": results}, indent=2))
        else:
            for r in results:
                status = "OK" if r["ok"] else "FAIL"
                print(f"[{status}] {r['url']} (Expected: {r['expected_status']})")
            if all_ok:
                print("[HEALTH: PASS] All endpoints responsive.")
            else:
                print("[HEALTH: FAIL] One or more endpoints failed.")
        sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
