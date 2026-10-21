"""Mock the exact local Docker CLI commands; never invoke a daemon."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server"))
import host_docker as docker  # noqa: E402

CID = "a" * 64
IMAGE = "ghcr.io/games-on-whales/wolf@sha256:" + "b" * 64


def adapter():
    result = object.__new__(docker.LocalDocker)
    result.base = ["/usr/bin/docker", "--host", "unix:///var/run/docker.sock"]
    result.env = {"DOCKER_CONFIG": "/nonexistent/now-host-docker-config"}
    result.executable = "/usr/bin/docker"
    return result


def response(value, returncode=0):
    return subprocess.CompletedProcess([], returncode, value, "")


class HostDockerTests(unittest.TestCase):
    def test_read_only_container_inventory_uses_exact_local_endpoint(self):
        client = adapter()
        with patch.object(docker.subprocess, "run", return_value=response(CID + "\n")) as run:
            self.assertEqual(client.project_ids(), (CID,))
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3],
                         ["/usr/bin/docker", "--host", "unix:///var/run/docker.sock"])
        self.assertEqual(argv[3:],
                         ["ps", "--all", "--no-trunc",
                          "--filter", "label=com.docker.compose.project=optiplex-now-host-pilot",
                          "--format", "{{.ID}}"])
        self.assertFalse(run.call_args.kwargs["check"])
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_docker_project_identity_rejects_duplicate_invalid_rows(self):
        client = adapter()
        for output in ("whoops\n", CID + "\n" + CID + "\n"):
            with patch.object(docker.subprocess, "run", return_value=response(output)):
                with self.assertRaises(docker.DockerError):
                    client.project_ids()

    def test_docker_image_pin_required_no_tags(self):
        client = adapter()
        for image in ("stable", IMAGE + " --privileged", "other/image@" + IMAGE):
            with self.assertRaises(docker.DockerError):
                client.has_image(image)
        with patch.object(docker.subprocess, "run",
                          return_value=response("sha256:" + "c" * 64 + "\n")) as run:
            self.assertTrue(client.has_image(IMAGE))
        self.assertEqual(run.call_args.args[0][-4:], [
            "image", "inspect", "--format", "{{.Id}}", IMAGE][-4:])

    def test_docker_adapter_never_broadens_driver_volume_name(self):
        client = adapter()
        with self.assertRaises(docker.DockerError):
            client.has_driver_volume("user-data")
        with patch.object(docker.subprocess, "run",
                          return_value=response("now-nvidia-driver-vol\n")):
            self.assertTrue(client.has_driver_volume("now-nvidia-driver-vol"))

    def test_inspect_requires_both_now_and_compose_labels(self):
        client = adapter()
        labels = {
            "com.docker.compose.project": docker.PROJECT,
            "com.docker.compose.service": "wolf",
            "io.optiplex-now.managed": "prototype",
            "io.optiplex-now.role": "streaming",
        }
        with patch.object(docker.subprocess, "run", side_effect=[
            response(CID), response(IMAGE), response(json.dumps(labels)),
            response(json.dumps(
                {"Running": True, "Health": {"Status": "healthy"}}))
        ]):
            result = client.inspect_owned(CID, IMAGE)
            self.assertEqual(result["health"], "healthy")
            self.assertEqual(result["id"], CID)
            self.assertEqual(result["image"], IMAGE)
        for key in labels:
            altered = dict(labels)
            altered[key] = "unrelated"
            with self.subTest(key=key), patch.object(
                docker.subprocess, "run", side_effect=[
                    response(CID), response(IMAGE), response(json.dumps(altered))
                ]
            ):
                with self.assertRaises(docker.DockerError):
                    client.inspect_owned(CID, IMAGE)

    def test_full_id_and_image_are_required_for_container_identity(self):
        client = adapter()
        for malformed in (CID[:12], "not-a-container", CID + "x"):
            with self.assertRaises(docker.DockerError):
                client.inspect_owned(malformed, IMAGE)
        with patch.object(docker.subprocess, "run", side_effect=[
            response("c" * 64),
        ]):
            with self.assertRaisesRegex(docker.DockerError, "identity"):
                client.inspect_owned(CID, IMAGE)
        with patch.object(docker.subprocess, "run", side_effect=[
            response(CID), response("ghcr.io/games-on-whales/wolf@sha256:" + "d" * 64),
        ]):
            with self.assertRaisesRegex(docker.DockerError, "image digest"):
                client.inspect_owned(CID, IMAGE)
        with self.assertRaises(docker.DockerError):
            client.inspect_owned(CID, "stable")

    def test_removal_refuses_changed_identity_even_with_matching_labels(self):
        client = adapter()
        with patch.object(client, "inspect_owned", return_value={
            "id": "c" * 64, "image": IMAGE, "running": True
        }):
            with patch.object(docker.subprocess, "run") as run:
                with self.assertRaises(docker.DockerError):
                    client.remove_owned(CID, IMAGE)
                run.assert_not_called()

    def test_remove_exact_id_only_after_label_check_without_volumes(self):
        client = adapter()
        with patch.object(client, "inspect_owned", return_value={
            "id": CID, "image": IMAGE, "running": True, "health": "healthy",
        }) as inspect:
            with patch.object(docker.subprocess, "run",
                              return_value=response("")) as run:
                client.remove_owned(CID, IMAGE)
        inspect.assert_called_once_with(CID, IMAGE)
        self.assertEqual(run.call_args.args[0],
                         client.base + ["rm", "--force", CID])
        self.assertNotIn("down", run.call_args.args[0])
        self.assertNotIn("--volumes", run.call_args.args[0])

    def test_start_once_never_pulls_or_recreates_dependent_services(self):
        client = adapter()
        file = Path("/tmp/now-test/generations/" + "a" * 64 + "/compose.yaml")
        with patch.object(docker.subprocess, "run",
                          return_value=response("")) as run:
            client.start_once(file)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], client.base)
        self.assertIn("--no-recreate", argv)
        self.assertIn("--no-deps", argv)
        self.assertIn("--no-build", argv)
        self.assertEqual(argv[argv.index("--pull") + 1], "never")
        self.assertEqual(argv[-1], "wolf")
        self.assertNotIn("--remove-orphans", argv)
        self.assertNotIn("--force-recreate", argv)

    def test_daemon_error_and_timeout_redact_raw_stderr(self):
        client = adapter()
        with patch.object(docker.subprocess, "run",
                          return_value=subprocess.CompletedProcess(
                              [], 1, "", "sensitive-token=do-not-log")):
            with self.assertRaises(docker.DockerError) as error:
                client.project_ids()
            self.assertNotIn("sensitive-token", str(error.exception))
        with patch.object(docker.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(
                              ["docker"], 12, stderr=b"sensitive-token")):
            with self.assertRaises(docker.DockerError) as error:
                client.project_ids()
            self.assertNotIn("sensitive-token", str(error.exception))

    def test_unbounded_output_is_rejected(self):
        client = adapter()
        with patch.object(docker.subprocess, "run",
                          return_value=response("x" * (docker.MAX_RESULT + 1))):
            with self.assertRaisesRegex(docker.DockerError, "limit"):
                client.project_ids()


if __name__ == "__main__":
    unittest.main()
