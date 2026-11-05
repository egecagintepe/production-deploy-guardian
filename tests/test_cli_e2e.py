import json
import os
import subprocess
import sys
import tempfile
import unittest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "deploy_guardian.py")

class TestDeployGuardianCLI(unittest.TestCase):
    def test_classify_cli_json_fast_eligible(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "guardian_config.example.json")
        cmd = [
            sys.executable, CLI_PATH, "classify",
            "--config", config_path,
            "--files", "app/views.py", "app/controllers/user.py",
            "--json"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["decision"], "FAST_ELIGIBLE")
        self.assertEqual(data["risk_level"], "LOW")

    def test_classify_cli_json_full_required(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "guardian_config.example.json")
        cmd = [
            sys.executable, CLI_PATH, "classify",
            "--config", config_path,
            "--files", "migrations/0001_initial.py", "app/views.py",
            "--json"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["decision"], "FULL_REQUIRED")
        self.assertEqual(data["risk_level"], "HIGH")

    def test_classify_cli_json_unknown_blocked(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "guardian_config.example.json")
        cmd = [
            sys.executable, CLI_PATH, "classify",
            "--config", config_path,
            "--files", "unregistered_script.sh",
            "--json"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 1)  # Non-zero on UNKNOWN_BLOCKED
        data = json.loads(res.stdout)
        self.assertEqual(data["decision"], "UNKNOWN_BLOCKED")

    def test_classify_cli_missing_base_commit_triggers_unknown_blocked(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "guardian_config.example.json")
        cmd = [
            sys.executable, CLI_PATH, "classify",
            "--config", config_path,
            "--json"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 1)  # Non-zero on UNKNOWN_BLOCKED
        data = json.loads(res.stdout)
        self.assertEqual(data["decision"], "UNKNOWN_BLOCKED")
        self.assertIn("baseline", data["reason"].lower())

    def test_audit_safety_cli(self):
        # Safe command
        cmd_safe = [sys.executable, CLI_PATH, "audit-safety", "--command", "echo Hello", "--json"]
        res_safe = subprocess.run(cmd_safe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res_safe.returncode, 0)
        self.assertTrue(json.loads(res_safe.stdout)["safe"])

        # Unsafe command
        cmd_unsafe = [sys.executable, CLI_PATH, "audit-safety", "--command", "docker volume prune -f", "--json"]
        res_unsafe = subprocess.run(cmd_unsafe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res_unsafe.returncode, 1)
        self.assertFalse(json.loads(res_unsafe.stdout)["safe"])

if __name__ == "__main__":
    unittest.main()

