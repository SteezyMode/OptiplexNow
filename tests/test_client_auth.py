"""Tailscale auth readiness must be read-only and safe for the GTK wizard."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "client_auth", HERE / "src" / "client_auth.py")
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


class Result:
    def __init__(self, state=None, code=0, body=None):
        self.returncode = code
        self.stdout = body if body is not None else json.dumps(
            {"BackendState": state, "Self": {"ID": "nPrivate", "TailscaleIPs": ["100.88.22.4"]}})


class TestClientTailscaleAuth(unittest.TestCase):
    def test_connected_logged_in_does_not_invoke_login(self):
        calls = []
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return Result("Running")
        self.assertEqual(auth.tailscale_state(which=lambda x: "/usr/bin/tailscale",
                                              runner=runner), "connected")
        self.assertEqual([a for a, _ in calls],
                         [["tailscale", "status", "--json"]])
        self.assertEqual(calls[0][1]["timeout"], 3)

    def test_missing_never_invokes_runner(self):
        def forbidden(*a, **kw):
            self.fail("Missing Tailscale must not run a command")
        self.assertEqual(auth.tailscale_state(which=lambda x: None,
                                              runner=forbidden), "missing")

    def test_login_stopped_and_invalid_states(self):
        self.assertEqual(auth.classify({"BackendState": "NeedsLogin"}), "login_required")
        self.assertEqual(auth.classify({"BackendState": "Stopped"}), "disconnected")
        self.assertEqual(auth.classify({"BackendState": "NoState"}), "disconnected")
        self.assertEqual(auth.classify({"BackendState": "Running"}), "unavailable")
        self.assertEqual(auth.classify({"BackendState": "Starting"}), "unavailable")
        self.assertEqual(auth.classify(None), "unavailable")
        self.assertEqual(auth.classify({"BackendState": "Running", "Self": []}), "unavailable")
        self.assertEqual(auth.classify({"BackendState": "Running", "Self": {"TailscaleIPs": ["192.168.1.2"]}}), "unavailable")
        self.assertEqual(auth.classify({"BackendState": "Running", "Self": {"TailscaleIPs": ["100.100.100.100"]}}), "unavailable")

    def test_command_failure_large_output_invalid_json_and_timeout(self):
        for proc in (
            Result(code=1), Result(body="garbage"),
            Result(body="x" * 524289), Result(body="[]")):
            self.assertEqual(auth.tailscale_state(
                which=lambda x: "tailscale", runner=lambda *a, **kw: proc),
                "unavailable")
        def timeout(*args, **kw):
            raise subprocess.TimeoutExpired(args[0], 3)
        self.assertEqual(auth.tailscale_state(
            which=lambda x: "tailscale", runner=timeout), "unavailable")

    def test_only_fixed_state_outputs_no_tailscale_secrets(self):
        fixture = {"BackendState": "Running", "Self": {
            "ID": "very-secret-token", "DNSName": "private-user.tailnet", "TailscaleIPs": ["100.99.5.23"]}}
        self.assertEqual(auth.classify(fixture), "connected")
        self.assertTrue(auth.STATES.issuperset({
            "connected", "login_required", "disconnected",
            "unavailable", "missing"}))


if __name__ == "__main__":
    unittest.main()
