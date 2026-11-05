#!/usr/bin/env python3
"""
Production Deploy Guardian CLI.
Deterministic deployment classifier, preflight gate, safety auditor, and health verifier.
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

FORBIDDEN_COMMAND_PATTERNS = [
    (r"docker\s+volume\s+prune", "Indiscriminate Docker volume prune causes permanent data loss"),
    (r"docker\s+system\s+prune.*--volumes", "Docker system prune with --volumes deletes application state"),
    (r"rm\s+-rf\s+(/|/var|/etc|/opt|/home|/root|/var/lib|/data|media|backups)", "Dangerous recursive deletion on persistent root or data path"),
    (r"git\s+push\s+.*--force", "Force pushing destroys remote Git history"),
    (r"git\s+reset\s+--hard", "Hard reset on production host destroys uncommitted state or leads to detached heads"),
    (r"DROP\s+(DATABASE|TABLE)\s+", "Destructive raw SQL drop statement"),
    (r"TRUNCATE\s+TABLE\s+", "Destructive raw SQL truncate statement"),
    (r"(cat|type|echo)\s+.*\.env(\s+|$)", "Echoing or printing raw .env contents leaks secrets into logs")
]

def load_config(config_path: str) -> Dict[str, Any]:
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_cmd(cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

def get_git_diff_files(base_commit: Optional[str], target_commit: str = "HEAD") -> List[str]:
    if not base_commit:
        code, out, _ = run_cmd(["git", "diff", "--name-only", "HEAD~1", target_commit])
        if code != 0 or not out:
            return []
        return [line.strip() for line in out.splitlines() if line.strip()]
    code, out, err = run_cmd(["git", "diff", "--name-only", base_commit, target_commit])
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]

def classify_changes(diff_files: List[str], config: Dict[str, Any]) -> Dict[str, Any]:
    rules = config.get("classification_rules", {})
    full_triggers = rules.get("full_triggers", [])
    ignore_patterns = rules.get("ignore_patterns", [])

    filtered_files = []
    ignored_files = []

    for f in diff_files:
        is_ignored = False
        for pat in ignore_patterns:
            if re.search(pat, f):
                is_ignored = True
                break
        if is_ignored:
            ignored_files.append(f)
        else:
            filtered_files.append(f)

    if not diff_files:
        return {
            "mode": "Full",
            "reason": "No diff files detected or unable to resolve commit diff (conservative fallback to Full)",
            "matched_rules": [],
            "filtered_files": [],
            "ignored_files": [],
            "recommended_command": config.get("deployment_commands", {}).get("full", "")
        }

    matched_rules = []
    for f in filtered_files:
        for trig in full_triggers:
            pattern = trig.get("pattern", "")
            reason = trig.get("reason", "Rule matched")
            if pattern and re.search(pattern, f):
                matched_rules.append({"file": f, "pattern": pattern, "reason": reason})

    if matched_rules:
        mode = "Full"
        summary_reason = f"Full rebuild required due to {len(matched_rules)} trigger(s)."
    else:
        if not filtered_files and ignored_files:
            mode = "No-Op"
            summary_reason = "All changed files match ignore patterns (e.g. docs/comments)."
        else:
            mode = "Fast"
            summary_reason = f"Safe for fast in-place reload ({len(filtered_files)} file(s) modified)."

    rec_cmd = config.get("deployment_commands", {}).get(mode.lower(), "")
    if mode == "No-Op":
        rec_cmd = "None (Documentation or ignored files only)"

    return {
        "mode": mode,
        "reason": summary_reason,
        "matched_rules": matched_rules,
        "filtered_files": filtered_files,
        "ignored_files": ignored_files,
        "recommended_command": rec_cmd
    }

def check_local_git(expected_branch: str) -> Dict[str, Any]:
    results = {"clean": False, "branch_ok": False, "synced_with_remote": False, "errors": []}
    
    code, current_branch, err = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if code != 0:
        results["errors"].append(f"Git branch check failed: {err}")
        return results

    if current_branch != expected_branch:
        results["errors"].append(f"Expected release branch '{expected_branch}', but currently on '{current_branch}'")
    else:
        results["branch_ok"] = True

    code, status, _ = run_cmd(["git", "status", "--porcelain"])
    if code == 0 and not status:
        results["clean"] = True
    else:
        results["errors"].append("Working tree has uncommitted or untracked changes.")

    code, local_head, _ = run_cmd(["git", "rev-parse", "HEAD"])
    code_rem, remote_head, _ = run_cmd(["git", "rev-parse", f"origin/{expected_branch}"])
    if code == 0 and code_rem == 0:
        if local_head == remote_head:
            results["synced_with_remote"] = True
        else:
            results["errors"].append(f"Local HEAD ({local_head[:8]}) does not match remote origin/{expected_branch} ({remote_head[:8]}). Push changes first.")
    else:
        results["errors"].append(f"Could not verify remote tracking reference for origin/{expected_branch}")

    return results

def audit_safety_string(text: str) -> List[Dict[str, str]]:
    violations = []
    for pat, desc in FORBIDDEN_COMMAND_PATTERNS:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            violations.append({
                "matched_pattern": pat,
                "description": desc,
                "snippet": match.group(0)
            })
    return violations

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
    cls_parser = subparsers.add_parser("classify", help="Classify deployment mode from git diff")
    cls_parser.add_argument("--config", default="guardian_config.json", help="Path to guardian_config.json")
    cls_parser.add_argument("--base-commit", default=None, help="Previously deployed commit hash")
    cls_parser.add_argument("--target-commit", default="HEAD", help="Target commit hash")
    cls_parser.add_argument("--files", nargs="*", default=None, help="Explicit list of files to evaluate instead of git diff")
    cls_parser.add_argument("--json", action="store_true", help="Output pure JSON")

    # Subcommand: preflight
    pf_parser = subparsers.add_parser("preflight", help="Run pre-release git and quality checks")
    pf_parser.add_argument("--config", default="guardian_config.json", help="Path to config file")
    pf_parser.add_argument("--skip-remote-sync", action="store_true", help="Skip remote origin matching check")
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
        if args.files is not None:
            files = args.files
        else:
            files = get_git_diff_files(args.base_commit, args.target_commit)
        res = classify_changes(files, cfg)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[CLASSIFICATION] Mode: {res['mode']}")
            print(f"Reason: {res['reason']}")
            if res["matched_rules"]:
                print("Matched Triggers:")
                for r in res["matched_rules"]:
                    print(f"  - {r['file']} -> {r['reason']}")
            if res.get("recommended_command"):
                print(f"Authoritative Command: {res['recommended_command']}")
        sys.exit(0 if res["mode"] in ("Fast", "No-Op") else 0)

    elif args.subcommand == "preflight":
        cfg = load_config(args.config)
        branch = cfg.get("release_branch", "main")
        git_res = check_local_git(branch)
        passed = git_res["clean"] and git_res["branch_ok"] and (git_res["synced_with_remote"] or args.skip_remote_sync)
        output = {
            "passed": passed,
            "git": git_res
        }
        if args.json:
            print(json.dumps(output, indent=2))
        else:
            status_text = "PASS" if passed else "FAIL"
            print(f"[PREFLIGHT: {status_text}]")
            for err in git_res["errors"]:
                if args.skip_remote_sync and "does not match remote" in err:
                    continue
                print(f"  - ERROR: {err}")
            if passed:
                print("  Working tree clean, branch verified, and ready for release.")
        sys.exit(0 if passed else 1)

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

        violations = audit_safety_string(content)
        safe = len(violations) == 0
        output = {"safe": safe, "violations": violations}
        if args.json:
            print(json.dumps(output, indent=2))
        else:
            if safe:
                print("[SAFETY AUDIT: PASS] No forbidden destructive operations detected.")
            else:
                print(f"[SAFETY AUDIT: FAIL] Detected {len(violations)} forbidden pattern(s):")
                for v in violations:
                    print(f"  - Pattern: '{v['snippet']}' => {v['description']}")
        sys.exit(0 if safe else 1)

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
