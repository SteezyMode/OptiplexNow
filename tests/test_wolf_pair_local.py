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


    def test_owner_status_queries_read_only_endpoints_and_redacts_secrets(self):
        profiles = {"success": True, "profiles": [
            {"id": "moonlight-profile-id", "apps": [{"title": "Steam"}]},
            {"id": "user", "pin": [1, 2, 3, 4],
             "apps": [{"title": "Steam", "runner": {"env": ["SECRET=bad"]}}]},
        ]}
        clients = {"success": True, "clients": [
            {"client_id": "1234", "app_state_folder": "1234",
             "settings": {"private_token": "PRIVATE"}},
            {"client_id": "1234", "app_state_folder": "1234"},
            {"client_id": "5678", "app_state_folder": "5678"},
        ]}
        with mock.patch.object(bridge, "call_api", side_effect=[profiles, clients]) as api:
            with mock.patch.object(sys, "argv", ["wolf-pair-local", "owner-status"]):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                    bridge.main()
        result = json.loads(output.getvalue())
        self.assertEqual([c.args for c in api.call_args_list], [
            ("GET", "/api/v1/profiles"), ("GET", "/api/v1/clients")])
        self.assertEqual(result["status"], "single_named_candidate")
        self.assertEqual(result["named_steam_candidates"], [{"profile_id": "user"}])
        self.assertEqual(result["unique_paired_clients"], 2)
        self.assertEqual(result["identical_duplicate_records"], 1)
        self.assertTrue(result["direct_steam_available"])
        self.assertFalse(result["can_auto_assign"])
        self.assertFalse(result["owner_mapping_verified"])
        self.assertNotIn("SECRET", output.getvalue())
        self.assertNotIn("PRIVATE", output.getvalue())
        self.assertNotIn("pin", output.getvalue())

    def test_owner_status_missing_profile_does_not_invent_steam_owner(self):
        result = bridge.owner_profile_readiness(
            {"success": True, "profiles": [
                {"id": "moonlight-profile-id", "apps": [{"title": "Steam"}]}
            ]},
            {"success": True, "clients": []})
        self.assertEqual(result["status"], "none")
        self.assertEqual(result["named_steam_candidates"], [])
        self.assertFalse(result["can_auto_assign"])

    def test_owner_status_multiple_profiles_must_not_choose_one(self):
        result = bridge.owner_profile_readiness(
            {"success": True, "profiles": [
                {"id": "user", "apps": [{"title": "Steam"}]},
                {"id": "another", "apps": [{"title": "Steam"}]}
            ]},
            {"success": True, "clients": []})
        self.assertEqual(result["status"], "multiple_named_candidates")
        self.assertEqual(len(result["named_steam_candidates"]), 2)
        self.assertFalse(result["owner_mapping_verified"])

    def test_owner_status_rejects_conflicting_duplicate_clients(self):
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            bridge.owner_profile_readiness(
                {"success": True, "profiles": []},
                {"success": True, "clients": [
                    {"client_id": "1234", "app_state_folder": "1234"},
                    {"client_id": "1234", "app_state_folder": "other"}
                ]})

    def test_owner_status_rejects_duplicate_named_profile_ids(self):
        with self.assertRaisesRegex(ValueError, "Duplicate Wolf profile"):
            bridge.owner_profile_readiness(
                {"success": True, "profiles": [
                    {"id": "user", "apps": []},
                    {"id": "user", "apps": []}
                ]}, {"success": True, "clients": []})

    def test_owner_status_rejects_missing_or_bad_inventory(self):
        for profiles, clients in [
            ({}, {"success": True, "clients": []}),
            ({"success": True, "profiles": None}, {"success": True, "clients": []}),
            ({"success": True, "profiles": []}, {"success": False, "clients": []}),
            ({"success": True, "profiles": [None]}, {"success": True, "clients": []}),
            ({"success": True, "profiles": [{"id": "x", "apps": []}]},
             {"success": True, "clients": [{"client_id": 42, "app_state_folder": "42"}]}),
        ]:
            with self.subTest(profiles=profiles, clients=clients):
                with self.assertRaises(ValueError):
                    bridge.owner_profile_readiness(profiles, clients)

    def test_owner_status_rejects_ambiguous_steam_app_definitions(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            bridge.owner_profile_readiness(
                {"success": True, "profiles": [
                    {"id": "user", "apps": [{"title": "Steam"}, {"title": "Steam"}]}
                ]}, {"success": True, "clients": []})


if __name__ == "__main__":
    unittest.main()
