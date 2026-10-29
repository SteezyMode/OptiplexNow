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

    def test_release_requires_tag_or_exact_one_time_v121_merge(self):
        data = (WORKFLOWS / "release.yml").read_text()
        # Routine releases still require an explicit immutable version tag.
        self.assertRegex(data, r"(?m)^\s+tags:\s*$")
        self.assertIn("- 'v*'", data)
        self.assertNotIn("workflow_dispatch:", data)
        self.assertNotIn("--clobber", data)
        self.assertIn("GITHUB_REF_NAME", data)
        self.assertIn('dpkg-deb -f "$package" Version', data)
        self.assertIn('gh release view "$tag"', data)
        self.assertIn("--verify-tag", data)

        # Explicit owner-requested one-time v1.21.0 publication: changing
        # any ordinary main file or pushing a PR cannot publish. Only the
        # curated notes path plus exact squash-merge instruction can do so.
        self.assertIn("    branches:\n      - main", data)
        self.assertIn("    paths:\n      - 'docs/releases/v1.21.0.md'", data)
        self.assertIn("github.ref == 'refs/heads/main'", data)
        self.assertIn("contains(github.event.head_commit.message, '[publish-v1.21.0]')", data)
        self.assertIn('version="1.21.0"', data)
        self.assertIn('test "$(sed -nE', data)
        self.assertIn('package.py)" = "$version"', data)
        self.assertIn('gh api -X POST "repos/$GH_REPO/git/refs"', data)
        self.assertIn('-f ref="refs/tags/$tag" -f sha="$GITHUB_SHA"', data)
        # This explicitly chosen existing-host build is the official download.
        self.assertIn("--latest", data)
        self.assertNotIn("--latest=false", data)
        self.assertNotIn("--prerelease", data)

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
