import unittest
from pathlib import Path


class CiWorkflowTests(unittest.TestCase):
    def test_verify_workflow_checks_manifest_before_regressions(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("Verify source manifest is current", workflow)
        self.assertIn(".\\\\tools\\\\update_source_manifest.ps1", workflow)
        self.assertIn("git diff --exit-code -- SOURCE_MANIFEST.sha256", workflow)
        self.assertLess(workflow.index("Verify source manifest is current"), workflow.index("Run server and browser regressions"))


if __name__ == "__main__":
    unittest.main()
