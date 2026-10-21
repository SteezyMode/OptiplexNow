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
                with mock.patch("sys.stdin", io.StringIO('{"index":1,"client_ip":"100.1.2.3","pin":"1234"}')):
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


    def test_changed_client_ip_rejected_before_authorization(self):
        pending = {"success": True, "requests": [
            {"client_ip": "100.1.2.99", "pair_secret": "not-selected"},
        ]}
        with mock.patch.object(bridge, "call_api", return_value=pending) as call:
            with mock.patch.object(sys, "argv", ["wolf-pair-local", "pair"]):
                request = '{"index":1,"client_ip":"100.1.2.3","pin":"1234"}'
                with mock.patch("sys.stdin", io.StringIO(request)):
                    with self.assertRaisesRegex(ValueError, "Pending clients changed"):
                        bridge.main()
        call.assert_called_once_with("GET", "/api/v1/pair/pending")

    def test_expired_index_rejected_before_authorization(self):
        pending = {"success": True, "requests": []}
        with mock.patch.object(bridge, "call_api", return_value=pending) as call:
            with mock.patch.object(sys, "argv", ["wolf-pair-local", "pair"]):
                request = '{"index":1,"client_ip":"100.1.2.3","pin":"1234"}'
                with mock.patch("sys.stdin", io.StringIO(request)):
                    with self.assertRaisesRegex(ValueError, "expired"):
                        bridge.main()
        call.assert_called_once_with("GET", "/api/v1/pair/pending")

    def test_missing_secret_does_not_authorize(self):
        pending = {"success": True, "requests": [
            {"client_ip": "100.1.2.3", "pair_secret": None},
        ]}
        with mock.patch.object(bridge, "call_api", return_value=pending) as call:
            with mock.patch.object(sys, "argv", ["wolf-pair-local", "pair"]):
                request = '{"index":1,"client_ip":"100.1.2.3","pin":"1234"}'
                with mock.patch("sys.stdin", io.StringIO(request)):
                    with self.assertRaisesRegex(ValueError, "missing secret"):
                        bridge.main()
        call.assert_called_once_with("GET", "/api/v1/pair/pending")

    def test_upstream_wolf_refusal_is_reported(self):
        pending = {"success": True, "requests": [
            {"client_ip": "100.1.2.3", "pair_secret": "fictional-secret"},
        ]}
        with mock.patch.object(bridge, "call_api",
                               side_effect=[pending, {"success": False}]) as call:
            with mock.patch.object(sys, "argv", ["wolf-pair-local", "pair"]):
                request = '{"index":1,"client_ip":"100.1.2.3","pin":"1234"}'
                with mock.patch("sys.stdin", io.StringIO(request)):
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                        bridge.main()
        self.assertEqual(json.loads(output.getvalue()), {"success": False})
        self.assertEqual(call.call_count, 2)

    def test_non_numeric_and_oversized_pins_are_rejected(self):
        with mock.patch.object(bridge, "call_api") as call:
            for pin in ("12", "12AB", "1234567890123", ""):
                with self.subTest(pin=pin):
                    with mock.patch.object(sys, "argv", ["wolf-pair-local", "pair"]):
                        request = json.dumps({"index": 1, "client_ip": "100.1.2.3", "pin": pin})
                        with mock.patch("sys.stdin", io.StringIO(request)):
                            with self.assertRaises(ValueError):
                                bridge.main()
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
