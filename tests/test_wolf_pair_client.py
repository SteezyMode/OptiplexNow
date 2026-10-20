"""Test the pairing transport without connecting to an SSH server."""
import importlib.util
import pathlib
import unittest
from unittest import mock

path = pathlib.Path(__file__).resolve().parents[1] / "src" / "wolf-pair-client.py"
spec = importlib.util.spec_from_file_location("wolf_pair_client", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class WolfPairTransportTests(unittest.TestCase):
    def test_rejects_invalid_host(self):
        with self.assertRaises(ValueError):
            mod.validated("host; echo invalid", "optiplex")

    def test_rejects_invalid_user(self):
        with self.assertRaises(ValueError):
            mod.validated("100.100.100.100", "-bad")

    def test_pair_pin_is_stdin_not_argv(self):
        payload = {"index": 1, "client_ip": "100.1.2.3", "pin": "1234"}
        with mock.patch.object(mod.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = b'{"success":true}'
            self.assertEqual(mod.invoke("100.100.100.100", "optiplex", "pair", payload), {"success": True})
            argv = run.call_args.args[0]
            self.assertNotIn("1234", " ".join(argv))
            self.assertIn(b'"pin": "1234"', run.call_args.kwargs["input"])
            self.assertIn("BatchMode=yes", argv)

    def test_refuses_unexpected_action(self):
        with self.assertRaises(ValueError):
            mod.invoke("100.100.100.100", "optiplex", "delete")


if __name__ == "__main__":
    unittest.main()
