"""Unit tests for the local Wolf pairing adapter (no Docker required)."""
import importlib.util
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wolf_pair_local", ROOT / "src" / "wolf-pair-local.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class WolfPairLocalTests(unittest.TestCase):
    def test_pending_redacts_pair_secrets(self):
        response = {"success": True, "requests": [
            {"client_ip": "100.1.2.3", "pair_secret": "TOP_SECRET"},
        ]}
        with mock.patch.object(bridge, "call_api", return_value=response):
            with mock.patch.object(sys, "argv", ["wolf-pair-local", "pending"]):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                    bridge.main()
        result = output.getvalue()
        self.assertNotIn("TOP_SECRET", result)
        self.assertEqual(json.loads(result)["clients"][0]["index"], 1)

    def test_pair_submits_only_selected_secret(self):
        pending = {"success": True, "requests": [
            {"client_ip": "100.1.2.3", "pair_secret": "chosen"},
            {"client_ip": "100.1.2.4", "pair_secret": "other"},
        ]}
        with mock.patch.object(bridge, "call_api", side_effect=[pending, {"success": True}]) as call:
            with mock.patch.object(sys, "argv", ["wolf-pair-local", "pair"]):
                with mock.patch("sys.stdin", io.StringIO('{"index":1,"pin":"1234"}')):
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                        bridge.main()
        self.assertEqual(call.call_args_list[1].args, ("POST", "/api/v1/pair/client", {"pair_secret": "chosen", "pin": "1234"}))
        self.assertEqual(json.loads(output.getvalue()), {"success": True})

    def test_invalid_pin_rejected_before_api_access(self):
        with mock.patch.object(bridge, "call_api") as call:
            with mock.patch.object(sys, "argv", ["wolf-pair-local", "pair"]):
                with mock.patch("sys.stdin", io.StringIO('{"index":1,"pin":"not a pin"}')):
                    with self.assertRaises(ValueError):
                        bridge.main()
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
