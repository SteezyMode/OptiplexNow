"""No-Docker tests for the review-only Wolf host staging bundle."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server"))
import host_stage  # noqa: E402

DUMMY_DIGEST = "sha256:" + "a" * 64  # Deliberately fictional fixture, NOT an image.
RENDER = "/dev/dri/renderD129"
BLOCKED_PLAN = {
    "tool": "now-host-plan",
    "schema_version": 1,
    "mode": "read_only_preview",
    "decision": "blocked",
    "may_apply": False,
    "changes_performed": False,
}


class HostStageTests(unittest.TestCase):
    def bundle(self):
        return host_stage.make_bundle(BLOCKED_PLAN, digest=DUMMY_DIGEST,
                                      render_node=RENDER)

    def test_compose_matches_upstream_wolf_nvidia_requirements(self):
        files = self.bundle()
        self.assertTrue(files["compose.yaml"].startswith("# OFFLINE REVIEW ONLY"))
        compose = json.loads("\n".join(files["compose.yaml"].splitlines()[1:]))
        wolf = compose["services"]["wolf"]
        self.assertEqual(wolf["image"], "ghcr.io/games-on-whales/wolf@" + DUMMY_DIGEST)
        self.assertEqual(wolf["profiles"], [host_stage.PROFILE])
        self.assertEqual(wolf["pull_policy"], "never")
        self.assertEqual(wolf["restart"], "no")
        self.assertEqual(wolf["network_mode"], "host")
        self.assertEqual(wolf["environment"]["WOLF_RENDER_NODE"], RENDER)
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock:rw", wolf["volumes"])
        self.assertIn("./wolf:/etc/wolf:rw", wolf["volumes"])
        self.assertIn("/dev/uinput:/dev/uinput", wolf["devices"])
        self.assertEqual(
            wolf["deploy"]["resources"]["reservations"]["devices"][0]["capabilities"],
            ["gpu"])
        self.assertNotIn("container_name", wolf)
        self.assertEqual(list(compose["services"]), ["wolf"])

    def test_manifest_forbids_installation_and_implicit_adoption(self):
        manifest = json.loads(self.bundle()["manifest.json"])
        self.assertFalse(manifest["deploy_supported"])
        self.assertFalse(manifest["changes_to_host_services"])
        self.assertFalse(manifest["unmanaged_containers_may_be_adopted"])
        self.assertFalse(manifest["existing_data_may_be_deleted"])
        self.assertEqual(manifest["approval"], "not_granted")
        self.assertNotIn("password", json.dumps(manifest))

    def test_image_digest_rejects_mutable_tags_and_injection(self):
        for value in ("stable", "sha256:abcd", "sha256:" + "G" * 64,
                      DUMMY_DIGEST + "\nservices: {}", "ghcr.io/fake@" + DUMMY_DIGEST):
            with self.subTest(value=value), self.assertRaises(ValueError):
                host_stage.validate_digest(value)

    def test_render_device_rejects_wrong_paths(self):
        for value in ("renderD129", "/dev/dri/card0", "/dev/nvidia0",
                      "/dev/dri/renderD129/../bad", "/dev/dri/renderD129\nfoo"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                host_stage.validate_render_node(value)

    def test_only_blocked_plan_can_be_staged(self):
        for changed in ({"may_apply": True}, {"decision": "ready"},
                        {"mode": "deploy"}, {"schema_version": 9},
                        {"changes_performed": True}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                host_stage.make_bundle(BLOCKED_PLAN | changed,
                                       digest=DUMMY_DIGEST, render_node=RENDER)

    def test_creates_new_staging_only_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "preview"
            output = host_stage.stage(target, self.bundle())
            self.assertEqual(output, target)
            self.assertEqual({p.name for p in target.iterdir()},
                             {"wolf", "compose.yaml", "manifest.json", "README.txt"})
            self.assertEqual(list((target / "wolf").iterdir()), [])
            content = (target / "compose.yaml").read_bytes()
            with self.assertRaises(FileExistsError):
                host_stage.stage(target, self.bundle())
            self.assertEqual((target / "compose.yaml").read_bytes(), content)
            self.assertEqual(set(p.name for p in root.iterdir()), {"preview"})

    def test_refuses_symlink_targets_and_protected_system_folders(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual = root / "existing"
            actual.mkdir()
            link = root / "linked"
            link.symlink_to(actual)
            with self.assertRaises(FileExistsError):
                host_stage.stage(link, self.bundle())
            with self.assertRaises(ValueError):
                host_stage.stage(Path("/etc/now-host-test"), self.bundle())
            with self.assertRaises(ValueError):
                host_stage.stage(Path("relative/output"), self.bundle())

    def test_failed_creation_cleans_only_new_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "candidate"
            with self.assertRaises(KeyError):
                host_stage.stage(target, {"compose.yaml": "{}"})
            self.assertFalse(target.exists())

    def test_actual_compose_parser_when_installed(self):
        docker = shutil.which("docker")
        if not docker:
            self.skipTest("Docker Compose CLI absent; JSON/YAML structure checked above")
        try:
            available = subprocess.run([docker, "compose", "version"], capture_output=True,
                                       text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self.skipTest("Docker Compose unavailable")
        if available.returncode:
            self.skipTest("Docker Compose plugin unavailable")
        with tempfile.TemporaryDirectory() as temp:
            folder = host_stage.stage(Path(temp) / "preview", self.bundle())
            result = subprocess.run([docker, "compose", "-f",
                                     str(folder / "compose.yaml"), "config", "--quiet"],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
