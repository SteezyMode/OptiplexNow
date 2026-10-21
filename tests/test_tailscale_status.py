"""Pure Tailscale status classification and subprocess simulation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

path = Path(__file__).resolve().parents[1] / "src" / "tailscale-status.py"
spec = importlib.util.spec_from_file_location("now_tailscale_status", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TailscaleStatusTests(unittest.TestCase):
    def test_connected_only_with_valid_self_ip(self):
        self.assertEqual(module.classify({"BackendState": "Running",
                                           "Self": {"TailscaleIPs": ["100.75.1.2"]}}),
                         "CONNECTED")
        for addresses in ([], ["not-an-ip"], ["0.0.0.0"], None):
            with self.subTest(addresses=addresses):
                self.assertEqual(module.classify({"BackendState": "Running",
                    "Self": {"TailscaleIPs": addresses}}), "UNAVAILABLE")

    def test_signed_out_and_stopped_are_not_connected(self):
        self.assertEqual(module.classify({"BackendState": "NeedsLogin"}), "SIGN_IN")
        self.assertEqual(module.classify({"BackendState": "NeedsMachineAuth"}), "SIGN_IN")
        self.assertEqual(module.classify({"BackendState": "Stopped"}), "NOT_CONNECTED")
        self.assertEqual(module.classify({"BackendState": "Starting"}), "NOT_CONNECTED")
        self.assertEqual(module.classify({}), "UNAVAILABLE")

    def test_missing_binary_is_explicit(self):
        with mock.patch.object(module.shutil, "which", return_value=None):
            self.assertEqual(module.status(), "NOT_INSTALLED")

    def test_malformed_json_and_timeout_are_not_connection(self):
        with mock.patch.object(module.shutil, "which", return_value="/usr/bin/tailscale"):
            with mock.patch.object(module.subprocess, "run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = "{bad"
                self.assertEqual(module.status(), "UNAVAILABLE")
                run.side_effect = subprocess.TimeoutExpired(cmd="tailscale", timeout=4)
                self.assertEqual(module.status(), "UNAVAILABLE")

    def test_reads_status_without_updating_network(self):
        data = {"BackendState": "Running",
                "Self": {"TailscaleIPs": ["100.64.3.1"]}}
        with mock.patch.object(module.shutil, "which", return_value="/usr/bin/tailscale"):
            with mock.patch.object(module.subprocess, "run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = json.dumps(data)
                self.assertEqual(module.status(), "CONNECTED")
                args = run.call_args
                self.assertEqual(args.args[0], ["tailscale", "status", "--json"])
                self.assertEqual(args.kwargs["timeout"], 4)


if __name__ == "__main__":
    unittest.main()
