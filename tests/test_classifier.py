import os
import unittest
import sys

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from deploy_guardian import classify_changes

class TestDeploymentClassifier(unittest.TestCase):
    def setUp(self):
        self.config = {
            "classification_rules": {
                "full_triggers": [
                    {"pattern": r"^migrations/|^db/migrate/", "reason": "Database migration detected"},
                    {"pattern": r"requirements.*\.txt$|package\.json$", "reason": "Dependency manifest changed"},
                    {"pattern": r"Dockerfile|docker-compose.*\.ya?ml$", "reason": "Container configuration changed"},
                    {"pattern": r"^frontend/src/", "reason": "Frontend SPA source modified"}
                ],
                "fast_eligible_patterns": [
                    r"views?\.py$",
                    r"serializers?\.py$",
                    r"templates/.*\.html$",
                    r"^app/services/"
                ],
                "ignore_patterns": [
                    r"^docs/",
                    r"\.md$"
                ]
            },
            "deployment_commands": {
                "fast": "app-fast-deploy",
                "full": "app-full-deploy"
            }
        }

    def test_migration_triggers_full(self):
        files = ["migrations/0002_add_field.py", "app/views.py"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["decision"], "FULL_REQUIRED")
        self.assertEqual(res["risk_level"], "HIGH")
        self.assertIn("migrations/0002_add_field.py", res["migration_impact"])
        self.assertEqual(res["recommended_command"], "app-full-deploy")

    def test_requirements_triggers_full(self):
        files = ["requirements.txt"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["decision"], "FULL_REQUIRED")
        self.assertIn("requirements.txt", res["dependency_impact"])

    def test_frontend_triggers_full(self):
        files = ["frontend/src/App.vue"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["decision"], "FULL_REQUIRED")

    def test_stateless_code_triggers_fast_with_positive_match(self):
        files = ["app/views.py", "app/services/calculator.py"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["decision"], "FAST_ELIGIBLE")
        self.assertEqual(res["risk_level"], "LOW")
        self.assertEqual(len(res["unclassified_files"]), 0)
        self.assertEqual(res["recommended_command"], "app-fast-deploy")

    def test_unclassified_file_triggers_unknown_blocked(self):
        # A file that does not match full triggers, fast whitelist, or ignore patterns
        files = ["scripts/sysadmin_task.sh", "app/views.py"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["decision"], "UNKNOWN_BLOCKED")
        self.assertEqual(res["risk_level"], "HIGH")
        self.assertIn("scripts/sysadmin_task.sh", res["unclassified_files"])

    def test_docs_only_triggers_noop(self):
        files = ["docs/README.md", "RELEASE.md"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["decision"], "NO_OP")
        self.assertEqual(res["risk_level"], "LOW")

    def test_empty_diff_triggers_noop(self):
        res = classify_changes([], self.config, diff_resolved=True)
        self.assertEqual(res["decision"], "NO_OP")

    def test_unresolved_diff_triggers_unknown_blocked(self):
        res = classify_changes([], self.config, diff_resolved=False)
        self.assertEqual(res["decision"], "UNKNOWN_BLOCKED")
        self.assertEqual(res["risk_level"], "CRITICAL_BLOCKED")

    def test_missing_base_commit_diff_fails_closed(self):
        from deploy_guardian import get_git_diff_files
        ok, files, err = get_git_diff_files(None)
        self.assertFalse(ok)
        self.assertEqual(len(files), 0)
        self.assertIn("Missing verified deployment baseline", err)

        ok_empty, files_empty, err_empty = get_git_diff_files("   ")
        self.assertFalse(ok_empty)
        self.assertIn("Missing verified deployment baseline", err_empty)

if __name__ == "__main__":
    unittest.main()
