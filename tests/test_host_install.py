"""Live installer safety-contract tests; no Docker mutation in CI."""
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server"))
import host_install as installer  # noqa: E402
import host_nvidia  # noqa: E402

PIN = "sha256:" + "a" * 64


class CleanHostInstallerTests(unittest.TestCase):
    def test_existing_wolf_blocks_new_install_even_if_ports_are_unbound(self):
        def snapshot(image, state="exited"):
            return {"Id":"a"*64,"Name":"/old-wolf",
                    "Config":{"Image":image},
                    "HostConfig":{"NetworkMode":"bridge"},
                    "State":{"Status":state}}
        def report(*records):
            import host_services
            return host_services.assess(list(records))
        self.assertIsNone(installer._existing_wolf_check(report()))
        for existing in (
            report(snapshot("ghcr.io/games-on-whales/wolf:stable")),
            report(snapshot("ghcr.io/games-on-whales/wolf:old", "running")),
            report(snapshot("ghcr.io/games-on-whales/wolf:stable"),
                   snapshot("ghcr.io/games-on-whales/wolf:old")),
            report(),
        ):
            # A valid empty Docker report is the only installable case.
            finding = installer._existing_wolf_check(existing)
            if existing["services"]["wolf"]["docker_count"] == 0:
                self.assertIsNone(finding)
            else:
                self.assertIn("existing Wolf", finding)
        self.assertIn("cannot inspect", installer._existing_wolf_check(
            {"tool":"now-host-services", "docker_access":"unavailable",
             "services":{"wolf":{"status":"unknown","docker_count":0}}}))
        self.assertIsNotNone(installer._existing_wolf_check({}))

    def test_privileged_install_rechecks_existing_wolf_at_apply_time(self):
        import inspect
        source = inspect.getsource(installer._host_checks)
        self.assertIn("if privileged:", source)
        self.assertIn("_existing_wolf_check(host_services.collect())", source)

    def test_root_required_before_any_host_mutation(self):
        with mock.patch.object(installer.os, "geteuid", return_value=1000):
            with self.assertRaisesRegex(installer.InstallationError, "Root authority"):
                installer.install("intel", "/dev/dri/renderD128", PIN, "INSTALL-WOLF")

    def test_explicit_confirm_required_before_any_host_mutation(self):
        with mock.patch.object(installer.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(installer.InstallationError, "confirmation"):
                installer.install("intel", "/dev/dri/renderD128", PIN, "")

    def test_nvidia_requires_verified_sha_before_host_mutation(self):
        with mock.patch.object(installer.os, "geteuid", return_value=0):
            for checksum in (None, "", "f" * 63, "g" * 64, "F" * 64):
                with self.subTest(checksum=checksum), self.assertRaises(host_nvidia.DriverError):
                    installer.install("nvidia", "/dev/dri/renderD129", PIN,
                                      "INSTALL-WOLF", checksum)
            with self.assertRaises(installer.InstallationError):
                installer.install("amd", "/dev/dri/renderD128", PIN,
                                  "INSTALL-WOLF", "f" * 64)

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

    def test_real_nvidia_eligibility_on_ci_runner_never_reports_stream_verified(self):
        result = installer._host_checks("nvidia", "/dev/dri/renderD128")
        self.assertIn(result["decision"], {"blocked", "candidate", "candidate_after_admin_check"})
        self.assertNotIn("stream_verified", result)
        self.assertIn("nvidia_driver_version", result)


    def test_nvidia_compose_requires_versioned_driver_volume(self):
        volume = host_nvidia.volume_name("580.95.05", "f" * 64)
        data = json.loads(installer._render_compose(
            "nvidia", "/dev/dri/renderD129", PIN,
            Path("/var/lib/optiplex-now/host"), nvidia_volume=volume))
        wolf = data["services"]["wolf"]
        self.assertEqual(data["volumes"], {volume: {"external": True}})
        self.assertEqual(wolf["environment"]["NVIDIA_DRIVER_VOLUME_NAME"], volume)
        self.assertIn(volume + ":/usr/nvidia:rw", wolf["volumes"])
        self.assertNotIn("now-nvidia-driver-vol:/usr/nvidia:rw", wolf["volumes"])
        with self.assertRaises(installer.InstallationError):
            installer._render_compose(
                "nvidia", "/dev/dri/renderD129", PIN,
                Path("/var/lib/optiplex-now/host"))
        with self.assertRaises(installer.InstallationError):
            installer._render_compose(
                "intel", "/dev/dri/renderD128", PIN,
                Path("/var/lib/optiplex-now/host"), nvidia_volume=volume)

    def test_driver_recipe_checks_download_and_rejects_bad_versions(self):
        source = host_nvidia.RECIPE.read_text()
        self.assertIn("sha256sum --check --status", source)
        self.assertIn("https://download.nvidia.com/XFree86/Linux-x86_64/", source)
        self.assertIn("NV_SHA256", source)
        self.assertEqual(host_nvidia.volume_name("580.95.05", "f" * 64),
                         "now-nvidia-580-95-05-" + "f" * 16)
        for value in ("stable", "580.95;bad", "12.5.1", "532.4", "000.0.0"):
            with self.subTest(value=value), self.assertRaises(host_nvidia.DriverError):
                host_nvidia.validate_driver_version(value)

    def test_versioned_volume_uses_verified_copy_and_never_deletes_volume(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as root:
            records = []
            version = "580.95.05"
            sha = "f" * 64
            name = host_nvidia.volume_name(version, sha)
            def docker(args, timeout=30):
                records.append(args)
                if args[:2] == ["volume", "ls"]:
                    return ""
                if args[0] == "build":
                    return "sha256:" + "b" * 64
                if args[:2] == ["volume", "create"]:
                    return name
                if args[:2] == ["volume", "inspect"]:
                    return json.dumps({
                        "io.optiplex-now.managed": "host-install-pilot",
                        "io.optiplex-now.nvidia.version": version,
                        "io.optiplex-now.nvidia.installer-sha256": sha,
                    })
                if args[0] == "create":
                    return "a" * 64
                if args[0] == "rm":
                    return ""
                raise AssertionError("Unexpected Docker operation")
            phases = []
            result = host_nvidia.prepare_volume(
                docker, driver_version=version, installer_sha=sha,
                build_context=Path(root), progress=phases.append)
            self.assertEqual(result["name"], name)
            self.assertEqual(phases[-1], "driver_volume_ready")
            self.assertIn("NV_SHA256=" + sha, records[1])
            self.assertEqual([a[0] for a in records][-2:], ["create", "rm"])
            self.assertFalse(any(a[:2] == ["volume", "rm"] for a in records))

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
