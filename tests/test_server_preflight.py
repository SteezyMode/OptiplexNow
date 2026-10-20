"""No host integration: all preflight command responses are synthetic fixtures."""
import importlib.util
import json
import io
from contextlib import redirect_stdout
from unittest.mock import patch
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


    def test_sunshine_plan_clean_machine_requires_approval(self):
        inventory, _ = self.fixture()
        plan = preflight.build_install_plan(inventory, "sunshine")
        self.assertEqual(plan["phase"], "advisory_only")
        self.assertFalse(plan["can_install"])
        self.assertTrue(plan["needs_explicit_approval"])
        steps = {item["id"]: item for item in plan["steps"]}
        self.assertEqual(steps["streaming_host"]["status"], "action_needed")
        self.assertEqual(steps["remote_access"]["status"], "optional")
        self.assertEqual(steps["encoder"]["status"], "review_required")
        self.assertNotIn("runtime", steps)
        self.assertIn("Compatible encoder not verified", plan["blocking_reasons"])

    def test_wolf_plan_requires_container_runtime_and_manual_review(self):
        inventory, _ = self.fixture(binaries=("docker",))
        plan = preflight.build_install_plan(inventory, "wolf")
        steps = {item["id"]: item for item in plan["steps"]}
        self.assertEqual(steps["runtime"]["status"], "review_required")
        self.assertIn("Container runtime not accessible", plan["blocking_reasons"])
        self.assertEqual(steps["streaming_host"]["status"], "review_required")
        self.assertNotIn("install", str(plan["phase"]).lower().replace("advisory_only", ""))

    def test_wolf_clean_host_lists_container_prerequisite(self):
        report, _ = self.fixture()
        plan = preflight.build_install_plan(report, "wolf")
        step = {x["id"]: x for x in plan["steps"]}
        self.assertEqual(step["runtime"]["status"], "action_needed")
        self.assertEqual(step["streaming_host"]["status"], "action_needed")

    def test_existing_services_are_preserved_and_not_considered_ready(self):
        inventory, _ = self.fixture(
            binaries=("systemctl", "sunshine", "docker"),
            responses={
                preflight.READ_COMMANDS[3]: "Docker version",
                preflight.READ_COMMANDS[4]: "wolf|ghcr.io/games-on-whales/wolf:stable",
                preflight.READ_COMMANDS[5]: "active\n",
            })
        plan = preflight.build_install_plan(inventory, "sunshine")
        steps = {item["id"]: item for item in plan["steps"]}
        self.assertEqual(steps["streaming_host"]["status"], "verify_required")
        self.assertEqual(steps["other_host"]["status"], "review_required")
        self.assertIn("Other streaming host already detected", plan["blocking_reasons"])
        self.assertFalse(plan["can_install"])

    def test_listener_not_assumed_port_conflict(self):
        inventory, _ = self.fixture(
            binaries=("ss",),
            responses={
                preflight.READ_COMMANDS[8]: "tcp LISTEN 0 4096 10.1.2.3:47984 0.0.0.0:*"
            })
        plan = preflight.build_install_plan(inventory, "wolf")
        step = next(x for x in plan["steps"] if x["id"] == "ports")
        self.assertEqual(step["status"], "review_required")
        self.assertIn("cannot identify ownership", step["detail"])
        self.assertNotIn("10.1.2.3", json.dumps(plan))

    def test_connected_tailscale_does_not_mean_remotely_reachable(self):
        inventory, _ = self.fixture(
            binaries=("tailscale",),
            responses={preflight.READ_COMMANDS[0]:
                       json.dumps({"BackendState": "Running", "Peer": {"key": "private"}})})
        plan = preflight.build_install_plan(inventory, "sunshine")
        step = next(x for x in plan["steps"] if x["id"] == "remote_access")
        self.assertEqual(step["status"], "verify_required")
        self.assertIn("not tested", step["detail"])
        self.assertNotIn("private", json.dumps(plan))

    def test_cli_backend_json_additive_and_no_host_probes(self):
        inventory, calls = self.fixture()
        for choice in ("sunshine", "wolf"):
            with self.subTest(choice=choice), patch.object(preflight, "collect", return_value=inventory):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(preflight.main(["--json", "--backend", choice]), 0)
                obj = json.loads(output.getvalue())
                self.assertEqual(obj["schema_version"], 1)
                self.assertEqual(obj["install_plan"]["backend"], choice)
                self.assertFalse(obj["install_plan"]["can_install"])
        with patch.object(preflight, "collect", return_value=inventory):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(preflight.main(["--json"]), 0)
            self.assertNotIn("install_plan", json.loads(output.getvalue()))
        self.assertFalse(calls)

    def test_human_plan_is_explicitly_not_executable(self):
        inventory, _ = self.fixture()
        inventory["install_plan"] = preflight.build_install_plan(inventory, "sunshine")
        output = preflight.format_human(inventory)
        self.assertIn("PROPOSED SUNSHINE SETUP PLAN", output)
        self.assertIn("NO INSTALLER", output)
        self.assertIn("No changes made", output)
        self.assertNotIn("sudo", output)

    def test_unknown_backend_cannot_be_planned(self):
        inventory, _ = self.fixture()
        with self.assertRaises(ValueError):
            preflight.build_install_plan(inventory, "unrecognized")


if __name__ == "__main__":
    unittest.main()
