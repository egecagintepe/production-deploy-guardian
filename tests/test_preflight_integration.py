import os
import shutil
import tempfile
import unittest
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from deploy_guardian import check_local_git

class TestPreflightIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Initialize synthetic git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_clean_working_tree_passes(self):
        # Create commit
        file_path = os.path.join(self.test_dir, "test.txt")
        with open(file_path, "w") as f:
            f.write("hello\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        res = check_local_git(expected_branch="main", check_remote_sync=False, cwd=self.test_dir)
        self.assertTrue(res["clean"])
        self.assertTrue(res["branch_ok"])
        self.assertEqual(len(res["errors"]), 0)

    def test_dirty_working_tree_fails(self):
        # Create commit
        file_path = os.path.join(self.test_dir, "test.txt")
        with open(file_path, "w") as f:
            f.write("hello\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Dirty modification
        with open(file_path, "a") as f:
            f.write("dirty change\n")

        res = check_local_git(expected_branch="main", check_remote_sync=False, cwd=self.test_dir)
        self.assertFalse(res["clean"])
        self.assertTrue(any("uncommitted" in err for err in res["errors"]))

    def test_wrong_branch_fails(self):
        subprocess.run(["git", "checkout", "-b", "feature-x"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        file_path = os.path.join(self.test_dir, "test.txt")
        with open(file_path, "w") as f:
            f.write("hello\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        res = check_local_git(expected_branch="main", check_remote_sync=False, cwd=self.test_dir)
        self.assertFalse(res["branch_ok"])
        self.assertTrue(any("Expected release branch 'main'" in err for err in res["errors"]))

if __name__ == "__main__":
    unittest.main()

