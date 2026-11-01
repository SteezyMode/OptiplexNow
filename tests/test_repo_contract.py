"""Repository invariants: publication is an explicit, versioned operation."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

class WorkflowSafetyTests(unittest.TestCase):
    def test_only_documented_now_workflows_exist(self):
        found = {p.name for p in WORKFLOWS.glob("*.yml")}
        found |= {p.name for p in WORKFLOWS.glob("*.yaml")}
        self.assertEqual(found, {"ci.yml", "release.yml", "wolf-real-compat.yml"})

    def test_real_wolf_workflow_is_pr_scoped_and_disposable(self):
        data = (WORKFLOWS / "wolf-real-compat.yml").read_text()
        for value in ("pull_request:", "workflow_dispatch:", "contents: read",
                      "--network none", "RUNNER_TEMP", "server/probe_real_wolf.py",
                      "io.optiplex-now.compat-disposable=true", "@sha256:"):
            self.assertIn(value, data)
        for value in ("push:", "branches:", "gh release", "upload-artifact",
                      "--privileged", "/var/run/docker.sock"):
            self.assertNotIn(value, data)

    def test_release_requires_tag_or_exact_one_time_current_version_merge(self):
        data = (WORKFLOWS / "release.yml").read_text()
        package = (ROOT / "package.py").read_text()
        token = 'DEFAULT_VERSION = "'
        self.assertIn(token, package)
        version = package.partition(token)[2].split('"', 1)[0]
        self.assertRegex(version, r"^[0-9]+[.][0-9]+[.][0-9]+$")
        self.assertRegex(data, r"(?m)^\s+tags:\s*$")
        for value in ("- 'v*'", "GITHUB_REF_NAME",
                      'dpkg-deb -f "$package" Version', 'gh release view "$tag"',
                      "--verify-tag", "    branches:\n      - main",
                      "github.ref == 'refs/heads/main'",
                      'test "$(sed -nE', 'package.py)" = "$version"',
                      'gh api -X POST "repos/$GH_REPO/git/refs"',
                      '-f ref="refs/tags/$tag" -f sha="$GITHUB_SHA"', "--latest"):
            self.assertIn(value, data)
        self.assertIn(f"    paths:\n      - 'docs/releases/v{version}.md'", data)
        self.assertIn(f"contains(github.event.head_commit.message, '[publish-v{version}]')", data)
        self.assertIn(f'version="{version}"', data)
        for value in ("workflow_dispatch:", "--clobber", "--latest=false", "--prerelease"):
            self.assertNotIn(value, data)

    def test_binary_release_assets_not_stored_in_source(self):
        self.assertFalse((ROOT / "downloads").exists())

    def test_ci_cannot_publish(self):
        data = (WORKFLOWS / "ci.yml").read_text()
        self.assertIn("contents: read", data)
        self.assertIn("pull_request:", data)
        self.assertNotIn("gh release", data)
        self.assertNotIn("--clobber", data)

if __name__ == "__main__":
    unittest.main()
