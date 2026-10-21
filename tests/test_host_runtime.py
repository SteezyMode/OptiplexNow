"""Simulated controlled Wolf first-start tests. Never access a real Docker daemon."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server"))
import host_docker  # noqa: E402
import host_runtime as rt  # noqa: E402
import host_stage  # noqa: E402
import host_transaction as tx  # noqa: E402

DIGEST = "sha256:" + "a" * 64
CID = "a" * 64
CID_OTHER = "b" * 64
PLAN = {
    "tool": "now-host-plan", "schema_version": 1, "mode": "read_only_preview",
    "decision": "blocked", "may_apply": False, "changes_performed": False,
}
CHECKS = ("architecture", "operating_system", "gpu_detection", "hardware_encoder",
          "nvidia_driver", "nvidia_drm_modeset", "virtual_controller_devices",
          "udev", "container_runtime", "wolf_ports", "disk_space", "memory")


def report(**changes):
    statuses = {name: "pass" for name in CHECKS}
    statuses.update(changes)
    return {
        "schema_version": 1, "tool": "now-host-preflight", "read_only": True,
        "verified_streaming": False, "overall": "unknown",
        "checks": [{"id": key, "status": value, "detail": "test only"}
                   for key, value in statuses.items()],
    }


class FakeDocker:
    def __init__(self):
        self.ids = []
        self.image = True
        self.volume = True
        self.running = True
        self.health = "not_configured"
        self.raise_start = False
        self.create_then_fail = False
        self.ambiguous_after_start = False
        self.events = []

    def project_ids(self):
        self.events.append("project_ids")
        return tuple(self.ids)

    def has_image(self, image):
        self.events.append(("image", image))
        return self.image

    def has_driver_volume(self, name):
        self.events.append(("volume", name))
        return self.volume

    def start_once(self, path):
        self.events.append(("start", path))
        if self.create_then_fail:
            self.ids = [CID]
            raise host_docker.DockerError("simulated failure after creation")
        if self.raise_start:
            raise host_docker.DockerError("simulated failure before creation")
        self.ids = [CID, CID_OTHER] if self.ambiguous_after_start else [CID]

    def inspect_owned(self, container_id, expected_image):
        self.events.append(("inspect", container_id, expected_image))
        if container_id not in self.ids:
            raise host_docker.DockerError("not owned")
        return {"id": container_id, "image": expected_image,
                "running": self.running, "health": self.health}

    def remove_owned(self, container_id, expected_image):
        self.events.append(("remove", container_id, expected_image))
        self.ids.remove(container_id)


class HostRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="now-runtime-input-")
        self.addCleanup(temporary.cleanup)
        self.input_root = Path(temporary.name)
        self.workspace = Path("/tmp") / ("now-runtime-fixture-" + uuid4().hex)
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))

    def prepare(self, gpu="amd"):
        folder = self.input_root / ("bundle-" + gpu)
        if not folder.exists():
            host_stage.stage(folder, host_stage.make_bundle(
                PLAN, digest=DIGEST, render_node="/dev/dri/renderD128",
                gpu_vendor=gpu))
        tx.prepare(folder, self.workspace)
        return folder

    def journal(self):
        return json.loads((self.workspace / rt.JOURNAL).read_text())

    def grant(self):
        return {
            "operation": "start_wolf",
            "workspace": str(self.workspace),
            "generation": tx._state(self.workspace)["active"],
            "source": "simulated_owner",
        }

    def test_success_is_running_but_not_stream_verified(self):
        self.prepare()
        docker = FakeDocker()
        result = rt.simulate_first_start(
            self.workspace, report(), docker, approval=self.grant())
        self.assertEqual(result["result"], "simulated_start_only")
        self.assertFalse(result["stream_verified"])
        self.assertEqual(self.journal()["phase"], "started_unverified_stream")
        self.assertFalse(self.journal()["stream_verified"])
        self.assertEqual(self.journal()["container_id"], CID)
        self.assertEqual(self.journal()["image"], "ghcr.io/games-on-whales/wolf@" + DIGEST)
        self.assertIn(("inspect", CID, "ghcr.io/games-on-whales/wolf@" + DIGEST), docker.events)
        self.assertEqual(tx._state(self.workspace)["runtime"], "not_started")
        self.assertNotIn(("remove", CID, "ghcr.io/games-on-whales/wolf@" + DIGEST), docker.events)
        self.assertFalse((self.workspace / tx.LOCK_FILE).exists())

    def test_explicit_owner_approval_required_before_docker(self):
        self.prepare()
        docker = FakeDocker()
        with self.assertRaises(rt.ActivationBlocked):
            rt.simulate_first_start(self.workspace, report(), docker,
                                    approval=None)
        self.assertEqual(docker.events, [])
        self.assertFalse((self.workspace / rt.JOURNAL).exists())

    def test_stale_or_mismatched_generation_approval_is_refused(self):
        self.prepare()
        for change in (
            {"generation": "b" * 64},
            {"workspace": "/tmp/not-the-approved-workspace"},
            {"operation": "remove_wolf"},
            {"source": "unverified_client"},
            {"unexpected": "extra"},
        ):
            with self.subTest(change=change):
                approval = self.grant()
                approval.update(change)
                docker = FakeDocker()
                with self.assertRaisesRegex(rt.ActivationBlocked, "approval"):
                    rt.simulate_first_start(
                        self.workspace, report(), docker, approval=approval)
                self.assertEqual(docker.events, [])
        self.assertFalse((self.workspace / rt.JOURNAL).exists())

    def test_read_only_reconciliation_never_mutates_containers(self):
        self.prepare()
        docker = FakeDocker()
        rt.simulate_first_start(
            self.workspace, report(), docker, approval=self.grant())
        before = list(docker.events)
        review = rt.review_attempt(self.workspace, docker)
        self.assertTrue(review["matches_recorded_identity"])
        self.assertEqual(review["recorded_container_id"], CID)
        self.assertEqual(review["observed_container_ids"], [CID])
        self.assertEqual(review["action"], "manual_review_only")
        self.assertFalse(review["stream_verified"])
        self.assertEqual(docker.ids, [CID])
        self.assertFalse(any(e[0] in ("remove", "start")
                             for e in docker.events[len(before):]
                             if isinstance(e, tuple)))
        docker.ids = [CID_OTHER]
        mismatch = rt.review_attempt(self.workspace, docker)
        self.assertFalse(mismatch["matches_recorded_identity"])
        self.assertEqual(mismatch["observed_container_ids"], [CID_OTHER])
        self.assertEqual(docker.ids, [CID_OTHER])

    def test_corrupt_or_symlink_journal_refused_for_review(self):
        self.prepare()
        docker = FakeDocker()
        rt.simulate_first_start(
            self.workspace, report(), docker, approval=self.grant())
        path = self.workspace / rt.JOURNAL
        path.write_text('{"phase":"starting"}')
        with self.assertRaises(rt.ActivationBlocked):
            rt.review_attempt(self.workspace, docker)
        path.unlink()
        path.symlink_to(self.workspace / tx.CURRENT_FILE)
        with self.assertRaises(rt.ActivationBlocked):
            rt.review_attempt(self.workspace, docker)

    def test_live_docker_adapter_refused_even_for_read_only_reconciliation(self):
        self.prepare()
        docker = FakeDocker()
        rt.simulate_first_start(
            self.workspace, report(), docker, approval=self.grant())
        real = object.__new__(host_docker.LocalDocker)
        with self.assertRaisesRegex(rt.ActivationBlocked, "not enabled"):
            rt.review_attempt(self.workspace, real)

    def test_live_docker_adapter_always_refused_even_if_approved(self):
        self.prepare()
        # Intentionally bypass constructor: we do not open a real Docker socket.
        real = object.__new__(host_docker.LocalDocker)
        with self.assertRaisesRegex(rt.ActivationBlocked, "not enabled"):
            rt.simulate_first_start(self.workspace, report(), real,
                                    approval=self.grant())
        self.assertFalse((self.workspace / rt.JOURNAL).exists())

    def test_unverified_encoder_and_occupied_wolf_ports_block_start(self):
        self.prepare()
        for changes in ({"hardware_encoder": "unknown"},
                        {"wolf_ports": "attention"},
                        {"operating_system": "unknown"},
                        {"architecture": "unsupported"}):
            with self.subTest(changes=changes):
                docker = FakeDocker()
                with self.assertRaises(rt.ActivationBlocked):
                    rt.simulate_first_start(
                        self.workspace, report(**changes), docker,
                        approval=self.grant())
                self.assertEqual(docker.events, [])
        self.assertFalse((self.workspace / rt.JOURNAL).exists())

    def test_existing_compose_project_is_never_adopted_or_restarted(self):
        self.prepare()
        docker = FakeDocker()
        docker.ids = [CID]
        with self.assertRaisesRegex(rt.ActivationBlocked, "refuse adoption"):
            rt.simulate_first_start(self.workspace, report(), docker,
                                    approval=self.grant())
        self.assertNotIn(("start", self.workspace), docker.events)
        self.assertEqual(docker.ids, [CID])
        self.assertFalse((self.workspace / rt.JOURNAL).exists())

    def test_missing_pinned_image_blocks_before_changes(self):
        self.prepare()
        docker = FakeDocker()
        docker.image = False
        with self.assertRaisesRegex(rt.ActivationBlocked, "not present"):
            rt.simulate_first_start(self.workspace, report(), docker,
                                    approval=self.grant())
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "start"
                             for x in docker.events))
        self.assertFalse((self.workspace / rt.JOURNAL).exists())

    def test_nvidia_driver_volume_never_assumed_ready(self):
        self.prepare(gpu="nvidia")
        docker = FakeDocker()
        with self.assertRaisesRegex(rt.ActivationBlocked, "attestation"):
            rt.simulate_first_start(self.workspace, report(), docker,
                                    approval=self.grant())
        self.assertIn(("volume", host_stage.DRIVER_VOLUME), docker.events)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "start"
                             for x in docker.events))
        self.assertFalse((self.workspace / rt.JOURNAL).exists())

    def test_failed_start_with_unjournaled_container_requires_manual_recovery(self):
        self.prepare(gpu="intel")
        docker = FakeDocker()
        docker.create_then_fail = True
        with self.assertRaises(host_docker.DockerError):
            rt.simulate_first_start(self.workspace, report(), docker,
                                    approval=self.grant())
        self.assertEqual(docker.ids, [CID])
        self.assertNotIn(("remove", CID, "ghcr.io/games-on-whales/wolf@" + DIGEST), docker.events)
        self.assertEqual(self.journal()["phase"], "manual_recovery_required")
        self.assertIsNone(self.journal()["container_id"])
        self.assertFalse(self.journal()["stream_verified"])
        self.assertFalse((self.workspace / tx.LOCK_FILE).exists())

    def test_start_failure_before_creation_marks_manual_recovery(self):
        self.prepare()
        docker = FakeDocker()
        docker.raise_start = True
        with self.assertRaises(host_docker.DockerError):
            rt.simulate_first_start(self.workspace, report(), docker,
                                    approval=self.grant())
        self.assertEqual(docker.ids, [])
        self.assertEqual(self.journal()["phase"], "manual_recovery_required")
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "remove"
                             for x in docker.events))

    def test_ambiguous_new_containers_are_never_removed(self):
        self.prepare()
        docker = FakeDocker()
        docker.ambiguous_after_start = True
        with self.assertRaisesRegex(rt.ActivationBlocked, "exactly one"):
            rt.simulate_first_start(self.workspace, report(), docker,
                                    approval=self.grant())
        self.assertEqual(docker.ids, [CID, CID_OTHER])
        self.assertEqual(self.journal()["phase"], "manual_recovery_required")
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "remove"
                             for x in docker.events))

    def test_stopped_or_unhealthy_container_is_cleaned_when_verified_owned(self):
        for state in ({"running": False}, {"health": "unhealthy"}):
            with self.subTest(state=state):
                if self.workspace.exists():
                    shutil.rmtree(self.workspace)
                self.prepare()
                docker = FakeDocker()
                for k, value in state.items():
                    setattr(docker, k, value)
                with self.assertRaises(rt.ActivationBlocked):
                    rt.simulate_first_start(self.workspace, report(), docker,
                                            approval=self.grant())
                self.assertEqual(docker.ids, [])
                self.assertEqual(self.journal()["phase"], "failed_cleaned")
                shutil.rmtree(self.workspace)

    def test_existing_journal_disables_automatic_retry(self):
        self.prepare()
        docker = FakeDocker()
        rt.simulate_first_start(self.workspace, report(), docker,
                                approval=self.grant())
        another = FakeDocker()
        with self.assertRaisesRegex(rt.ActivationBlocked, "journal"):
            rt.simulate_first_start(self.workspace, report(), another,
                                    approval=self.grant())
        self.assertEqual(another.events, [])

    def test_modified_generation_refused_before_any_docker_call(self):
        self.prepare()
        state = tx._state(self.workspace)
        compose = self.workspace / tx.GEN_DIR / state["active"] / "compose.yaml"
        compose.write_text(compose.read_text().replace("restart", "privileged"))
        docker = FakeDocker()
        with self.assertRaises(rt.ActivationBlocked):
            rt.simulate_first_start(self.workspace, report(), docker,
                                    approval=self.grant())
        self.assertEqual(docker.events, [])
        self.assertFalse((self.workspace / rt.JOURNAL).exists())


if __name__ == "__main__":
    unittest.main()
