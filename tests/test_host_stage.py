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
        self.assertEqual(wolf["environment"]["NVIDIA_DRIVER_VOLUME_NAME"],
                         host_stage.DRIVER_VOLUME)
        self.assertEqual(compose["volumes"][host_stage.DRIVER_VOLUME],
                         {"external": True})
        self.assertIn(host_stage.DRIVER_VOLUME + ":/usr/nvidia:rw", wolf["volumes"])
        self.assertIn("/dev/nvidia0:/dev/nvidia0", wolf["devices"])
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock:rw", wolf["volumes"])
        self.assertIn("./wolf:/etc/wolf:rw", wolf["volumes"])
        self.assertIn("/dev/uinput:/dev/uinput", wolf["devices"])
        self.assertNotIn("deploy", wolf)
        self.assertNotIn("NVIDIA_VISIBLE_DEVICES", wolf["environment"])
        self.assertNotIn("container_name", wolf)
        self.assertEqual(list(compose["services"]), ["wolf"])


    def test_amd_and_intel_use_standard_drm_without_nvidia_volume(self):
        for gpu in ("amd", "intel"):
            with self.subTest(gpu=gpu):
                files = host_stage.make_bundle(
                    BLOCKED_PLAN, digest=DUMMY_DIGEST, render_node=RENDER,
                    gpu_vendor=gpu)
                compose = json.loads("\\n".join(files["compose.yaml"].splitlines()[1:]))
                wolf = compose["services"]["wolf"]
                manifest = json.loads(files["manifest.json"])
                self.assertEqual(manifest["gpu_vendor"], gpu)
                self.assertIsNone(manifest["driver_volume"])
                self.assertIsNone(manifest["nvidia_method"])
                self.assertFalse(manifest["driver_volume_prepared"])
                self.assertNotIn("volumes", compose)
                self.assertNotIn("NVIDIA_DRIVER_VOLUME_NAME", wolf["environment"])
                self.assertNotIn("/usr/nvidia", " ".join(wolf["volumes"]))
                self.assertNotIn("/dev/nvidia", " ".join(wolf["devices"]))
                self.assertIn("/dev/dri:/dev/dri", wolf["devices"])
                self.assertIn("/dev/uinput:/dev/uinput", wolf["devices"])
                self.assertIn("/dev/uhid:/dev/uhid", wolf["devices"])
                self.assertEqual(wolf["environment"]["WOLF_RENDER_NODE"], RENDER)
                self.assertFalse(manifest["deploy_supported"])

    def test_gpu_backend_validation_and_multigpu_render_node_match(self):
        with self.assertRaises(ValueError):
            host_stage.make_bundle(BLOCKED_PLAN, digest=DUMMY_DIGEST,
                                   render_node=RENDER, gpu_vendor="unknown")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vendor_file = root / "class/drm/renderD129/device/vendor"
            vendor_file.parent.mkdir(parents=True)
            vendor_file.write_text("0x10de\\n")
            host_stage.check_render_vendor("nvidia", RENDER, root)
            with self.assertRaises(ValueError):
                host_stage.check_render_vendor("amd", RENDER, root)
            with self.assertRaises(ValueError):
                host_stage.check_render_vendor("intel", RENDER, root)
            vendor_file.write_text("0x1002\\n")
            host_stage.check_render_vendor("amd", RENDER, root)
            with self.assertRaises(ValueError):
                host_stage.check_render_vendor("nvidia", RENDER, root)
            vendor_file.write_text("0x8086\\n")
            host_stage.check_render_vendor("intel", RENDER, root)

    def test_manifest_forbids_installation_and_implicit_adoption(self):
        manifest = json.loads(self.bundle()["manifest.json"])
        self.assertFalse(manifest["deploy_supported"])
        self.assertFalse(manifest["changes_to_host_services"])
        self.assertFalse(manifest["unmanaged_containers_may_be_adopted"])
        self.assertFalse(manifest["existing_data_may_be_deleted"])
        self.assertEqual(manifest["approval"], "not_granted")
        self.assertEqual(manifest["nvidia_method"], "manual_external_driver_volume")
        self.assertEqual(manifest["driver_volume"], host_stage.DRIVER_VOLUME)
        self.assertIs(manifest["driver_volume_prepared"], False)
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
