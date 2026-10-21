"""Pure filesystem transaction tests. No Docker, GPU, sudo or network actions."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server"))
import host_plan  # noqa: E402
import host_stage  # noqa: E402
import host_transaction as tx  # noqa: E402

BLOCKED = {
    "tool": "now-host-plan", "schema_version": host_plan.PLAN_SCHEMA,
    "mode": "read_only_preview", "decision": "blocked",
    "may_apply": False, "changes_performed": False,
}
DIGEST1 = "sha256:" + "a" * 64
DIGEST2 = "sha256:" + "b" * 64


class HostTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="now-bundle-input-")
        self.addCleanup(temporary.cleanup)
        self.source_root = Path(temporary.name)
        self.workspace = Path("/tmp") / ("now-managed-fixture-" + uuid4().hex)
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))

    def staged(self, digest=DIGEST1, gpu="nvidia"):
        target = self.source_root / ("stage-" + gpu + "-" + digest[-5:])
        if not target.exists():
            host_stage.stage(target, host_stage.make_bundle(
                BLOCKED, digest=digest, render_node="/dev/dri/renderD129", gpu_vendor=gpu))
        return target

    def read_state(self):
        return json.loads((self.workspace / tx.CURRENT_FILE).read_text())

    def test_first_prepare_creates_private_owned_generation_not_a_container(self):
        result = tx.prepare(self.staged(), self.workspace)
        self.assertEqual(result["result"], "prepared_not_deployed")
        state = self.read_state()
        self.assertEqual(state["runtime"], "not_started")
        self.assertEqual(state["active"], result["generation"])
        self.assertIsNone(state["previous"])
        self.assertTrue((self.workspace / "wolf").is_dir())
        manifest = json.loads((self.workspace / tx.GEN_DIR / state["active"] /
                               "manifest.json").read_text())
        self.assertFalse(manifest["deploy_supported"])
        self.assertFalse(manifest["driver_volume_prepared"])
        self.assertEqual(self.workspace.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.workspace / tx.CURRENT_FILE).stat().st_mode & 0o777,
                         0o600)
        self.assertFalse((self.workspace / tx.LOCK_FILE).exists())

    def test_compose_always_binds_persistent_wolf_config_in_workspace(self):
        tx.prepare(self.staged(), self.workspace)
        state = self.read_state()
        blob = (self.workspace / tx.GEN_DIR / state["active"] /
                "compose.yaml").read_text()
        compose = json.loads(blob.split("\n", 1)[1])
        self.assertIn(str(self.workspace / "wolf") + ":/etc/wolf:rw",
                      compose["services"]["wolf"]["volumes"])
        self.assertNotIn("./wolf:/etc/wolf:rw",
                         compose["services"]["wolf"]["volumes"])
        self.assertNotIn("container_name", compose["services"]["wolf"])

    def test_idempotent_prepare_keeps_identity_and_persistent_files(self):
        first = tx.prepare(self.staged(), self.workspace)
        (self.workspace / "wolf" / "owner-settings.toml").write_text("keep me")
        second = tx.prepare(self.staged(), self.workspace)
        self.assertEqual(first["generation"], second["generation"])
        self.assertEqual(self.read_state()["previous"], None)
        self.assertEqual((self.workspace / "wolf" / "owner-settings.toml").read_text(),
                         "keep me")

    def test_upgrade_and_configuration_rollback_preserve_data(self):
        first = tx.prepare(self.staged(DIGEST1), self.workspace)
        (self.workspace / "wolf" / "test-save").write_bytes(b"persistent")
        second = tx.prepare(self.staged(DIGEST2), self.workspace)
        self.assertNotEqual(first["generation"], second["generation"])
        self.assertEqual(self.read_state()["previous"], first["generation"])
        restored = tx.rollback(self.workspace)
        self.assertEqual(restored["generation"], first["generation"])
        self.assertEqual(self.read_state()["previous"], second["generation"])
        self.assertEqual((self.workspace / "wolf" / "test-save").read_bytes(),
                         b"persistent")
        self.assertTrue((self.workspace / tx.GEN_DIR / second["generation"]).exists())


    def test_amd_and_intel_generations_prepare_without_driver_volume(self):
        for gpu in ("amd", "intel"):
            with self.subTest(gpu=gpu):
                workspace = Path("/tmp") / ("now-managed-" + gpu + "-" + uuid4().hex)
                self.addCleanup(lambda root=workspace: shutil.rmtree(root, ignore_errors=True))
                result = tx.prepare(self.staged(gpu=gpu), workspace)
                compose_file = workspace / tx.GEN_DIR / result["generation"] / "compose.yaml"
                compose = json.loads(compose_file.read_text().split("\\n", 1)[1])
                wolf = compose["services"]["wolf"]
                self.assertNotIn("volumes", compose)
                self.assertNotIn("NVIDIA_DRIVER_VOLUME_NAME", wolf["environment"])
                self.assertNotIn("nvidia", " ".join(wolf["devices"]).lower())
                self.assertIn(str(workspace / "wolf") + ":/etc/wolf:rw", wolf["volumes"])
                self.assertEqual(
                    tx.prepare(self.staged(gpu=gpu), workspace)["generation"],
                    result["generation"])

    def test_switch_gpu_profile_is_versioned_and_configuration_rollback_works(self):
        first = tx.prepare(self.staged(gpu="amd"), self.workspace)
        (self.workspace / "wolf" / "settings.cfg").write_text("preserve")
        second = tx.prepare(self.staged(gpu="nvidia"), self.workspace)
        self.assertNotEqual(first["generation"], second["generation"])
        result = tx.rollback(self.workspace)
        self.assertEqual(result["generation"], first["generation"])
        self.assertEqual((self.workspace / "wolf" / "settings.cfg").read_text(),
                         "preserve")
        self.assertEqual(self.read_state()["runtime"], "not_started")

    def test_rejects_gpu_manifest_mismatch(self):
        bundle = self.staged(gpu="intel")
        path = bundle / "manifest.json"
        data = json.loads(path.read_text())
        data["gpu_vendor"] = "nvidia"
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            tx.prepare(bundle, self.workspace)
        self.assertFalse(self.workspace.exists())

    def test_no_previous_generation_refuses_rollback(self):
        tx.prepare(self.staged(), self.workspace)
        with self.assertRaises(ValueError):
            tx.rollback(self.workspace)

    def test_refuses_to_adopt_foreign_directory(self):
        self.workspace.mkdir()
        (self.workspace / "important-user-file").write_text("do not touch")
        with self.assertRaises(ValueError):
            tx.prepare(self.staged(), self.workspace)
        self.assertEqual((self.workspace / "important-user-file").read_text(),
                         "do not touch")

    def test_lock_refuses_concurrent_or_crashed_writer(self):
        tx.prepare(self.staged(), self.workspace)
        (self.workspace / tx.LOCK_FILE).write_text("existing")
        with self.assertRaises(FileExistsError):
            tx.prepare(self.staged(DIGEST2), self.workspace)
        self.assertTrue((self.workspace / tx.LOCK_FILE).exists())
        self.assertEqual(self.read_state()["previous"], None)

    def test_rejects_tampered_staging_unsafe_volumes_and_mutable_image(self):
        bundle = self.staged()
        file = bundle / "compose.yaml"
        original = file.read_text()
        file.write_text(original.replace(
            "/var/run/docker.sock:/var/run/docker.sock:rw",
            "/:/host:rw"))
        with self.assertRaises(ValueError):
            tx.prepare(bundle, self.workspace)
        self.assertFalse(self.workspace.exists())
        file.write_text(original.replace("sha256:" + "a" * 64, "stable"))
        with self.assertRaises(ValueError):
            tx.prepare(bundle, self.workspace)
        self.assertFalse(self.workspace.exists())

    def test_rejects_other_workspace_paths(self):
        for location in (Path("/"), Path("/etc/now-host"), Path("/var/lib/now-host"),
                         Path("/home/new-now"), Path("relative"), Path("/tmp/a/b")):
            with self.subTest(location=location), self.assertRaises(ValueError):
                tx._validate_workspace(location)

    def test_symlink_workspace_and_state_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="now-managed-target-") as target:
            self.workspace.symlink_to(Path(target))
            with self.assertRaises(ValueError):
                tx.prepare(self.staged(), self.workspace)
            self.workspace.unlink()
        tx.prepare(self.staged(), self.workspace)
        state_path = self.workspace / tx.CURRENT_FILE
        state_path.unlink()
        state_path.symlink_to(self.workspace / tx.OWNER_FILE)
        with self.assertRaises(ValueError):
            tx.prepare(self.staged(DIGEST2), self.workspace)

    def test_write_failure_preserves_active_generation_for_retry(self):
        first = tx.prepare(self.staged(), self.workspace)
        old_current = (self.workspace / tx.CURRENT_FILE).read_bytes()
        with patch.object(tx, "_write_current", side_effect=OSError("simulated disk full")):
            with self.assertRaises(OSError):
                tx.prepare(self.staged(DIGEST2), self.workspace)
        self.assertEqual(old_current, (self.workspace / tx.CURRENT_FILE).read_bytes())
        self.assertFalse((self.workspace / tx.LOCK_FILE).exists())
        self.assertEqual(self.read_state()["active"], first["generation"])
        second = tx.prepare(self.staged(DIGEST2), self.workspace)
        self.assertNotEqual(second["generation"], first["generation"])

    def test_initial_failure_before_generation_keeps_retryable_workspace(self):
        with patch.object(tx, "_write_exclusive") as fail:
            fail.side_effect = OSError("simulated input failure")
            with self.assertRaises(OSError):
                tx.prepare(self.staged(), self.workspace)
        # Incomplete work is not accidentally adopted; manual remediation needed.
        with self.assertRaises(ValueError):
            tx.prepare(self.staged(), self.workspace)

    def test_missing_and_oversized_input_is_rejected(self):
        staged = self.staged()
        (staged / "README.txt").unlink()
        with self.assertRaises(ValueError):
            tx.prepare(staged, self.workspace)
        (staged / "README.txt").write_text("x" * (tx.MAX_FILE + 1))
        with self.assertRaises(ValueError):
            tx.prepare(staged, self.workspace)
        self.assertFalse(self.workspace.exists())


if __name__ == "__main__":
    unittest.main()
