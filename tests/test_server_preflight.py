"""No host integration: all preflight command responses are synthetic fixtures."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

FILE = Path(__file__).resolve().parents[1] / "server" / "server-preflight.py"
spec = importlib.util.spec_from_file_location("server_preflight", FILE)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class Result:
    def __init__(self, stdout):
        self.stdout = stdout


class ServerPreflightTests(unittest.TestCase):
    def fixture(self, *, binaries=(), responses=None, release='ID=pop\nVERSION_ID="24.04"',
                arch="x86_64"):
        calls = []
        responses = responses or {}

        def runner(args):
            calls.append(tuple(args))
            return Result(responses[tuple(args)]) if tuple(args) in responses else None

        report = preflight.collect(
            os_release=release, arch=arch, memory_kib=16777216,
            home_free_bytes=40 * 1073741824,
            which=lambda name: "/usr/bin/" + name if name in binaries else None,
            runner=runner)
        self.assertTrue(all(cmd in preflight.READ_COMMANDS for cmd in calls))
        self.assertTrue(all(cmd[0] in binaries for cmd in calls))
        self.assertIs(report["changes_made"], False)
        self.assertEqual(report["streaming_ready"], "not_tested")
        self.assertFalse(report["hardware"]["encoder_tested"])
        self.assertEqual(report["schema_version"], 1)
        return report, calls

    def test_connected_and_working_reference_shape(self):
        report, calls = self.fixture(
            binaries=("nvidia-smi", "lspci", "tailscale", "docker", "systemctl", "ss"),
            responses={
                preflight.READ_COMMANDS[0]: json.dumps({
                    "BackendState": "Running",
                    "Self": {"DNSName": "private-host.private-tailnet.ts.net",
                             "TailscaleIPs": ["100.1.2.3"]},
                    "Peer": {"secret-peer": {"DNSName": "other-device"}}}),
                preflight.READ_COMMANDS[1]: "NVIDIA RTX 3050, 595.104.02\n",
                preflight.READ_COMMANDS[2]:
                    "01:00.0 VGA compatible controller [0300]: NVIDIA [10de:2582]\n",
                preflight.READ_COMMANDS[3]: "28.5.1",
                preflight.READ_COMMANDS[4]:
                    "wolf|ghcr.io/games-on-whales/wolf:stable\n",
                preflight.READ_COMMANDS[7]: "active\n",
                preflight.READ_COMMANDS[8]:
                    "tcp LISTEN 0 4096 127.0.0.1:47984 0.0.0.0:*\n",
            })
        self.assertTrue(report["platform"]["initial_test_scope_match"])
        self.assertEqual(report["components"]["tailscale"], "connected")
        self.assertEqual(report["components"]["docker"], "accessible")
        self.assertEqual(report["components"]["wolf"], "detected")
        self.assertEqual(report["hardware"]["nvidia_driver_gpus"][0]["driver"], "595.104.02")
        self.assertEqual(report["streaming_ports_listening"], [47984])
        serialised = json.dumps(report)
        for secret in ("private-host", "private-tailnet", "100.1.2.3",
                       "secret-peer", "other-device"):
            self.assertNotIn(secret, serialised)
        self.assertIn(preflight.READ_COMMANDS[0], calls)

    def test_clean_host(self):
        report, calls = self.fixture()
        self.assertEqual(calls, [])
        self.assertTrue(report["platform"]["initial_test_scope_match"])
        self.assertEqual(report["components"]["tailscale"], "not_installed")
        self.assertEqual(report["components"]["docker"], "not_installed")
        self.assertEqual(report["components"]["wolf"], "not_detected")
        self.assertIsNone(report["streaming_ports_listening"])

    def test_outside_test_scope(self):
        report, _ = self.fixture(release='ID="debian"\nVERSION_ID="13"', arch="aarch64")
        self.assertFalse(report["platform"]["initial_test_scope_match"])
        self.assertTrue(any("Outside initial" in note for note in report["observations"]))

    def test_malformed_os_release_never_executed_or_copied(self):
        report, _ = self.fixture(release='ID="ubuntu;$(touch /tmp/never)"\nVERSION_ID=24.04\nUSER_EMAIL=private@example.com')
        self.assertEqual(report["platform"]["os_id"], "unknown")
        self.assertNotIn("private@example.com", json.dumps(report))
        self.assertNotIn("touch /tmp", json.dumps(report))

    def test_inaccessible_docker_not_mistaken_for_absent_wolf(self):
        report, _ = self.fixture(binaries=("docker",))
        self.assertEqual(report["components"]["docker"], "unavailable")
        self.assertEqual(report["components"]["wolf"], "unknown")

    def test_tailscale_errors_are_redacted(self):
        cases = [
            (json.dumps({"BackendState": "NeedsLogin"}), "needs_login"),
            (json.dumps({"BackendState": "Stopped"}), "stopped"),
            (json.dumps({"BackendState": "Starting"}), "unknown"),
            ("{private_token", "unknown"),
        ]
        for output, expected in cases:
            with self.subTest(expected=expected):
                report, _ = self.fixture(
                    binaries=("tailscale",),
                    responses={preflight.READ_COMMANDS[0]: output})
                self.assertEqual(report["components"]["tailscale"], expected)
                self.assertNotIn("private_token", json.dumps(report))

    def test_detect_both_backends(self):
        report, _ = self.fixture(
            binaries=("docker", "sunshine", "systemctl"),
            responses={
                preflight.READ_COMMANDS[3]: "28.0",
                preflight.READ_COMMANDS[4]:
                    "wolf|ghcr.io/games-on-whales/wolf:stable",
                preflight.READ_COMMANDS[5]: "active\n",
            })
        self.assertEqual(report["components"]["sunshine"], "running")
        self.assertEqual(report["components"]["wolf"], "detected")
        self.assertTrue(any("Both streaming backends" in x for x in report["observations"]))

    def test_listening_ports_without_addresses(self):
        raw = ("tcp LISTEN 0 4096 192.168.0.55:48010 0.0.0.0:*\n"
               "udp UNCONN 0 0 [::]:47998 [::]:*\n"
               "tcp LISTEN 0 2048 0.0.0.0:443 0.0.0.0:*\n")
        self.assertEqual(preflight.ports_from_ss(raw), [47998, 48010])
        report, _ = self.fixture(binaries=("ss",),
                                 responses={preflight.READ_COMMANDS[8]: raw})
        self.assertNotIn("192.168.0.55", json.dumps(report))
        self.assertNotIn("0.0.0.0", json.dumps(report))

    def test_command_failures_are_safe(self):
        def timeout(args):
            raise subprocess.TimeoutExpired(args, timeout=3)
        report = preflight.collect(
            os_release="ID=ubuntu\nVERSION_ID=24.04", arch="x86_64",
            memory_kib=1, home_free_bytes=0,
            which=lambda _: "/usr/bin/test", runner=timeout)
        self.assertFalse(report["changes_made"])
        self.assertEqual(report["components"]["docker"], "unavailable")
        self.assertEqual(report["components"]["tailscale"], "unknown")


if __name__ == "__main__":
    unittest.main()
