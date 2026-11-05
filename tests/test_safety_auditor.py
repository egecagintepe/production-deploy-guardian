import os
import unittest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from deploy_guardian import audit_safety_string

class TestSafetyAuditor(unittest.TestCase):
    def test_clean_commands_pass(self):
        cmd = "docker compose up -d web && curl -s http://localhost/healthz"
        res = audit_safety_string(cmd)
        self.assertTrue(res["safe"])
        self.assertEqual(len(res["violations"]), 0)
        self.assertIn("limitation_notice", res)

    def test_volume_prune_detected(self):
        cmd = "docker volume prune -f"
        res = audit_safety_string(cmd)
        self.assertFalse(res["safe"])
        self.assertEqual(len(res["violations"]), 1)
        self.assertIn("volume", res["violations"][0]["description"].lower())

    def test_chained_command_volume_rm_detected(self):
        cmd = "git pull && docker compose down && docker volume rm my_data_vol && docker compose up -d"
        res = audit_safety_string(cmd)
        self.assertFalse(res["safe"])
        self.assertTrue(any("volume" in v["description"].lower() for v in res["violations"]))

    def test_system_prune_volumes_detected(self):
        cmd = "docker system prune -a --volumes -f"
        res = audit_safety_string(cmd)
        self.assertFalse(res["safe"])

    def test_rm_rf_persistent_root_detected(self):
        for path in ["/var/lib/postgresql", "/data", "/opt", "/root"]:
            cmd = f"rm -rf {path}"
            res = audit_safety_string(cmd)
            self.assertFalse(res["safe"], f"Failed to detect dangerous rm on {path}")

    def test_git_force_push_variants_detected(self):
        variants = [
            "git push origin main --force",
            "git push origin main -f",
            "git push origin +main:main"
        ]
        for cmd in variants:
            res = audit_safety_string(cmd)
            self.assertFalse(res["safe"], f"Failed to detect force push in: {cmd}")

    def test_git_hard_reset_and_clean_detected(self):
        for cmd in ["git reset --hard HEAD~1", "git clean -fdx"]:
            res = audit_safety_string(cmd)
            self.assertFalse(res["safe"], f"Failed to detect: {cmd}")

    def test_sql_drop_table_detected(self):
        cmd = "psql -U postgres -d app_db -c 'DROP TABLE users CASCADE;'"
        res = audit_safety_string(cmd)
        self.assertFalse(res["safe"])

    def test_env_cat_and_echo_detected(self):
        for cmd in ["cat .env", "echo secret > .env", "type .env"]:
            res = audit_safety_string(cmd)
            self.assertFalse(res["safe"], f"Failed on: {cmd}")

if __name__ == "__main__":
    unittest.main()
