import os
import unittest
import tempfile
import json
import sys

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from deploy_guardian import classify_changes, load_config

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
        self.assertEqual(res["mode"], "Full")
        self.assertTrue(any("Database migration" in r["reason"] for r in res["matched_rules"]))
        self.assertEqual(res["recommended_command"], "app-full-deploy")

    def test_requirements_triggers_full(self):
        files = ["requirements.txt"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["mode"], "Full")
        self.assertTrue(any("Dependency manifest" in r["reason"] for r in res["matched_rules"]))

    def test_frontend_triggers_full(self):
        files = ["frontend/src/App.vue"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["mode"], "Full")
        self.assertTrue(any("Frontend SPA source" in r["reason"] for r in res["matched_rules"]))

    def test_stateless_code_triggers_fast(self):
        files = ["app/views.py", "app/services/calculator.py"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["mode"], "Fast")
        self.assertEqual(len(res["matched_rules"]), 0)
        self.assertEqual(res["recommended_command"], "app-fast-deploy")

    def test_docs_only_triggers_noop(self):
        files = ["docs/README.md", "RELEASE.md"]
        res = classify_changes(files, self.config)
        self.assertEqual(res["mode"], "No-Op")
        self.assertEqual(len(res["filtered_files"]), 0)
        self.assertEqual(len(res["ignored_files"]), 2)

    def test_empty_diff_fallback_to_full(self):
        res = classify_changes([], self.config)
        self.assertEqual(res["mode"], "Full")
        self.assertIn("fallback to Full", res["reason"])

if __name__ == "__main__":
    unittest.main()
