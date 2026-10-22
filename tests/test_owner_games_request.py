"""Owner Games host request gate: offline tests, no network or real Docker."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

from owner_access import OwnerStore, PolicyError
from owner_launch import read_lease, write_lease
from owner_games_request import handle_owner_games_request
from test_owner_launch import StatefulWolf
from test_owner_lobby import fixtures


class TrustedGamesGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = OwnerStore(str(Path(self.tmp.name) / "private"))
        with self.store.locked() as fd:
            self.store.write(fd, fixtures()[0])
        self.api = StatefulWolf()
        self.requests = lambda action: {"version": 1, "action": action}

    def call(self, action, *, client="1001", approved=False, caps="video/x-raw"):
        return handle_owner_games_request(
            self.requests(action), verified_client_id=client, store=self.store,
            wolf_api=self.api, host_video_caps=caps, host_approved=approved)

    def test_status_is_read_only_and_never_leaks_client_or_private_fields(self):
        self.assertEqual(self.call("status"),
                         {"success": True, "status": "wolf_ui_connected"})
        self.assertTrue(all(method == "GET" for method, _, _ in self.api.calls))
        self.assertNotIn("1001", str(self.call("status")))
        self.assertNotIn("pin", str(self.call("status")))
        with self.store.locked() as fd:
            self.assertIsNone(read_lease(fd))

    def test_start_stop_start_uses_same_owner_workspace_with_private_v2_lease(self):
        result = self.call("start", approved=True)
        self.assertEqual(result["status"], "joined")
        self.assertEqual(self.call("status")["status"], "in_use")
        self.assertTrue(self.call("status")["same_device"])
        with self.store.locked() as fd:
            lease = read_lease(fd)
            self.assertEqual(lease["version"], 2)
            self.assertEqual(len(lease["pin"]), 8)
        stopped = self.call("stop", approved=True)
        self.assertEqual(stopped, {"success": True, "status": "idle",
                                   "lease_archived": True})
        self.assertEqual(self.call("status")["status"], "wolf_ui_connected")
        self.assertEqual(self.call("start", approved=True)["status"], "joined")
        posts = [path for method, path, _ in self.api.calls if method == "POST"]
        self.assertEqual(posts, [
            "/api/v1/lobbies/create", "/api/v1/lobbies/join",
            "/api/v1/lobbies/stop", "/api/v1/lobbies/create",
            "/api/v1/lobbies/join",
        ])
        # Neither shared owner workspace nor private PIN comes from the request.
        self.assertNotIn("pin", str(self.requests("start")))

    def test_invalid_requests_fail_before_any_wolf_calls(self):
        for request in (
            {"version": 1, "action": "start", "client_id": "1001"},
            {"version": 1, "action": "start", "host_video_caps": "video/x-raw"},
            {"version": 1, "action": "exec", "command": "docker ps"},
            {"version": True, "action": "start"},
            {"version": 2, "action": "stop"},
            "status", {}, [], None,
        ):
            with self.subTest(request=request):
                with self.assertRaises(PolicyError):
                    handle_owner_games_request(
                        request, verified_client_id="1001", store=self.store,
                        wolf_api=self.api, host_approved=True)
        self.assertEqual(self.api.calls, [])

    def test_transport_identity_cannot_be_selected_by_request(self):
        with self.assertRaises(PolicyError):
            self.call("start", client="2002", approved=True)
        self.assertFalse(any(method == "POST" for method, _, _ in self.api.calls))
        with self.store.locked() as fd:
            self.assertIsNone(read_lease(fd))

    def test_unapproved_requests_are_denied_without_post(self):
        with self.assertRaisesRegex(PolicyError, "not enabled"):
            self.call("start", approved=False)
        with self.assertRaisesRegex(PolicyError, "not enabled"):
            self.call("stop", approved=False)
        self.assertFalse(any(method == "POST" for method, _, _ in self.api.calls))

    def test_different_connected_moonlight_device_is_rejected(self):
        data = list(copy.deepcopy(fixtures()))
        data[1]["clients"].append({
            "client_id": "2002", "app_state_folder": "client-2"})
        data[4]["sessions"][0]["client_id"] = "2002"
        self.api.data = tuple(data)
        with self.assertRaisesRegex(PolicyError, "another device"):
            self.call("start", approved=True)
        self.assertFalse(any(method == "POST" for method, _, _ in self.api.calls))

    def test_stale_existing_lease_blocks_second_start(self):
        self.call("start", approved=True)
        n = len([p for m, p, _ in self.api.calls if m == "POST"])
        with self.assertRaisesRegex(PolicyError, "blocking lease"):
            self.call("start", approved=True)
        self.assertEqual(n, len([p for m, p, _ in self.api.calls if m == "POST"]))

    def test_lobby_without_lease_and_other_session_are_not_idle(self):
        self.api.lobby = {
            "id": "unknown", "name": "Steam",
            "started_by_profile_id": "other",
        }
        self.assertEqual(self.call("status")["status"], "busy")
        with self.assertRaises(PolicyError):
            self.call("start", approved=True)
        self.api.lobby = None
        self.api.data[4]["sessions"].append({
            "client_id": "1002", "app_id": "other"})
        self.assertEqual(self.call("status")["status"], "busy")
        self.assertFalse(any(m == "POST" for m, _, _ in self.api.calls))

    def test_revoked_client_cannot_start_or_stop(self):
        self.call("start", approved=True)
        with self.store.locked() as fd:
            policy = self.store.read(fd)
            policy["devices"][0]["revoked"] = True
            self.store.write(fd, policy)
        count = len(self.api.calls)
        with self.assertRaisesRegex(PolicyError, "authorization"):
            self.call("stop", approved=True)
        with self.assertRaisesRegex(PolicyError, "authorization"):
            self.call("status")
        self.assertGreaterEqual(len(self.api.calls), count)
        self.assertTrue(self.api.lobby)
        with self.store.locked() as fd:
            self.assertIsNotNone(read_lease(fd))

    def test_missing_verified_caps_cannot_write_lease(self):
        with self.assertRaisesRegex(PolicyError, "caps"):
            self.call("start", approved=True, caps=None)
        self.assertFalse(any(m == "POST" for m, _, _ in self.api.calls))
        with self.store.locked() as fd:
            self.assertIsNone(read_lease(fd))

    def test_no_request_can_stop_unrelated_lease(self):
        self.call("start", approved=True)
        # A forged transport identity still fails the enrolled grant.
        with self.assertRaises(PolicyError):
            self.call("stop", client="2002", approved=True)
        self.assertIsNotNone(self.api.lobby)


if __name__ == "__main__":
    unittest.main()
