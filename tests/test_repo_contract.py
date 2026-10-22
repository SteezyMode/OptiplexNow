"""Repository invariants: releases are explicit, versioned operations, not CI side effects.

Deliberately standard-library-only so normal unittest discovery checks this.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class WorkflowSafetyTests(unittest.TestCase):
    def test_only_documented_now_workflows_exist(self):
        found = {p.name for p in WORKFLOWS.glob("*.yml")}
        found |= {p.name for p in WORKFLOWS.glob("*.yaml")}
        # Deliberate third workflow: isolated upstream Wolf API compatibility.
        # It cannot publish releases or inspect the working owner server.
        self.assertEqual(found, {"ci.yml", "release.yml", "wolf-real-compat.yml"},
                         "New workflows require a deliberate release-safety review.")

    def test_real_wolf_workflow_is_pr_scoped_and_disposable(self):
        data = (WORKFLOWS / "wolf-real-compat.yml").read_text()
        self.assertIn("pull_request:", data)
        self.assertIn("workflow_dispatch:", data)
        self.assertIn("contents: read", data)
        self.assertNotIn("push:", data)
        self.assertNotIn("branches:", data)
        self.assertNotIn("gh release", data)
        self.assertNotIn("upload-artifact", data)
        self.assertNotIn("--privileged", data)
        self.assertIn("--network none", data)
        self.assertIn("io.optiplex-now.compat-disposable=true", data)
        self.assertIn("RUNNER_TEMP", data)
        self.assertIn("server/probe_real_wolf.py", data)
        self.assertNotIn("/var/run/docker.sock", data)
        self.assertIn("@sha256:", data)

    def test_release_never_runs_on_main_or_manual_dispatch(self):
        data = (WORKFLOWS / "release.yml").read_text()
        self.assertRegex(data, r"(?m)^\s+tags:\s*$")
        self.assertIn("- 'v*'", data)
        self.assertNotRegex(data, r"(?m)^\s+branches:\s*")
        self.assertNotIn("workflow_dispatch:", data)
        self.assertNotIn("--clobber", data)
        self.assertIn("GITHUB_REF_NAME", data)
        self.assertIn('dpkg-deb -f "$package" Version', data)
        self.assertIn('gh release view "$GITHUB_REF_NAME"', data)

    def test_binary_release_assets_not_stored_in_source(self):
        self.assertFalse((ROOT / "downloads").exists(),
                         "Historic .deb files belong in GitHub Releases, not source control.")

    def test_ci_cannot_publish(self):
        data = (WORKFLOWS / "ci.yml").read_text()
        self.assertIn("contents: read", data)
        self.assertIn("pull_request:", data)
        self.assertNotIn("gh release", data)
        self.assertNotIn("--clobber", data)


if __name__ == "__main__":
    unittest.main()
