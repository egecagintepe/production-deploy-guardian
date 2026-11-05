import os
import unittest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from deploy_guardian import audit_safety_string

class TestSafetyAuditor(unittest.TestCase):
    def test_clean_commands_pass(self):
        cmd = "docker compose up -d web && curl -s http://localhost/healthz"
        violations = audit_safety_string(cmd)
        self.assertEqual(len(violations), 0)

    def test_volume_prune_detected(self):
        cmd = "docker volume prune -f"
        violations = audit_safety_string(cmd)
        self.assertEqual(len(violations), 1)
        self.assertIn("volume prune", violations[0]["description"].lower())

    def test_system_prune_volumes_detected(self):
        cmd = "docker system prune -a --volumes -f"
        violations = audit_safety_string(cmd)
        self.assertEqual(len(violations), 1)

    def test_rm_rf_persistent_root_detected(self):
        cmd = "rm -rf /var/lib/postgresql"
        violations = audit_safety_string(cmd)
        self.assertEqual(len(violations), 1)

    def test_git_force_push_detected(self):
        cmd = "git push origin main --force"
        violations = audit_safety_string(cmd)
        self.assertEqual(len(violations), 1)

    def test_git_hard_reset_detected(self):
        cmd = "ssh remote 'git reset --hard HEAD'"
        violations = audit_safety_string(cmd)
        self.assertEqual(len(violations), 1)

    def test_sql_drop_table_detected(self):
        cmd = "psql -U postgres -d app_db -c 'DROP TABLE users CASCADE;'"
        violations = audit_safety_string(cmd)
        self.assertEqual(len(violations), 1)

    def test_env_cat_detected(self):
        cmd = "cat .env | grep SECRET"
        violations = audit_safety_string(cmd)
        self.assertEqual(len(violations), 1)

if __name__ == "__main__":
    unittest.main()
