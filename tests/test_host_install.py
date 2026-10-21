"""Live installer safety-contract tests; no Docker mutation in CI."""
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server"))
import host_install as installer  # noqa: E402

PIN = "sha256:" + "a" * 64


class CleanHostInstallerTests(unittest.TestCase):
    def test_root_required_before_any_host_mutation(self):
        with mock.patch.object(installer.os, "geteuid", return_value=1000):
            with self.assertRaisesRegex(installer.InstallationError, "Root authority"):
                installer.install("intel", "/dev/dri/renderD128", PIN, "INSTALL-WOLF")

    def test_explicit_confirm_required_before_any_host_mutation(self):
        with mock.patch.object(installer.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(installer.InstallationError, "confirmation"):
                installer.install("intel", "/dev/dri/renderD128", PIN, "")

    def test_nvidia_is_not_accidentally_enabled(self):
        with mock.patch.object(installer.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(installer.InstallationError, "NVIDIA"):
                installer.install("nvidia", "/dev/dri/renderD129", PIN, "INSTALL-WOLF")

    def test_mutable_or_malformed_digest_refused(self):
        with mock.patch.object(installer.os, "geteuid", return_value=0):
            for value in ("stable", PIN + "; rm -rf /", "sha256:" + "A" * 64):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    installer.install("intel", "/dev/dri/renderD128", value,
                                      "INSTALL-WOLF")

    def test_install_composes_one_owned_intel_service_with_persistent_state(self):
        workspace = Path("/var/lib/optiplex-now/host")
        data = json.loads(installer._render_compose(
            "intel", "/dev/dri/renderD128", PIN, workspace))
        self.assertEqual(data["name"], installer.PROJECT)
        self.assertEqual(set(data["services"]), {"wolf"})
        wolf = data["services"]["wolf"]
        self.assertEqual(wolf["image"], installer.IMAGE_PREFIX + PIN)
        self.assertEqual(wolf["restart"], "unless-stopped")
        self.assertEqual(wolf["pull_policy"], "never")
        self.assertEqual(wolf["profiles"], [])
        self.assertEqual(wolf["network_mode"], "host")
        self.assertIn(str(workspace / "wolf") + ":/etc/wolf:rw", wolf["volumes"])
        self.assertNotIn("volumes", data)
        self.assertNotIn("NVIDIA_DRIVER_VOLUME_NAME", wolf["environment"])
        self.assertEqual(wolf["labels"]["io.optiplex-now.managed"],
                         "host-install-pilot")

    def test_real_check_on_ci_host_never_reports_installed(self):
        # Uses the runner's actual hardware, process/net and /dev trees.
        # A CI runner lacking a supported GPU must refuse candidacy.
        result = installer._host_checks("nvidia", "/dev/dri/renderD128")
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("NVIDIA volume preparation has not been implemented",
                      result["blockers"])
        self.assertNotIn("stream_verified", result)

    def test_docker_argv_uses_fixed_local_unix_socket_and_pinned_env(self):
        completed = mock.Mock(returncode=0, stdout=b"ok", stderr=b"")
        with mock.patch.object(installer.subprocess, "run", return_value=completed) as run:
            self.assertEqual(installer._docker(["compose", "version"]), "ok")
        args = run.call_args.args[0]
        self.assertEqual(args[:3], ["/usr/bin/docker", "--host",
                                    "unix:///var/run/docker.sock"])
        self.assertEqual(args[3:], ["compose", "version"])
        self.assertEqual(run.call_args.kwargs["env"]["DOCKER_CONFIG"],
                         "/nonexistent/now-host-docker-config")
        self.assertEqual(run.call_args.kwargs["stdin"], installer.subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
