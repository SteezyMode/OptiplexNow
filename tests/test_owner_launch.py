"""Offline transaction tests, no real Wolf, client access, Docker or Steam."""
import copy
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from owner_access import OwnerStore, PolicyError
from owner_launch import (launch_owner_steam, owner_launch_status, read_lease,
                          write_lease, stop_owner_steam, reconcile_stopped_owner_steam)
from test_owner_lobby import fixtures


class FakeWolf:
    def __init__(self, data=None, *, create=None, join=None):
        self.data = data or fixtures()
        self.calls = []
        self.create = create
        self.join = join

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        table = {
            "/api/v1/clients": self.data[1],
            "/api/v1/profiles": self.data[2],
            "/api/v1/apps": self.data[3],
            "/api/v1/sessions": self.data[4],
            "/api/v1/lobbies": self.data[5],
        }
        if method == "GET":
            return copy.deepcopy(table[path])
        if method == "POST" and path == "/api/v1/lobbies/create":
            if isinstance(self.create, Exception):
                raise self.create
            return self.create if self.create is not None else {
                "success": True, "lobby_id": "test_lobby_01"}
        if method == "POST" and path == "/api/v1/lobbies/join":
            if isinstance(self.join, Exception):
                raise self.join
            return self.join if self.join is not None else {"success": True}
        raise AssertionError("Unexpected Wolf operation " + method + path)


class StatefulWolf(FakeWolf):
    """Native-lobby test double with a mutable live lobby and STOP endpoint."""
    def __init__(self):
        super().__init__()
        self.lobby = None
        self.pin = None
        self.fail_stop = False

    def __call__(self, method, path, body=None):
        if (method, path) == ("GET", "/api/v1/lobbies"):
            self.calls.append((method, path, None))
            return {"success": True, "lobbies": [copy.deepcopy(self.lobby)]
                    if self.lobby is not None else []}
        if (method, path) == ("POST", "/api/v1/lobbies/create"):
            response = super().__call__(method, path, body)
            self.pin = list(body["pin"])
            self.lobby = {
                "id": response["lobby_id"], "name": "Steam",
                "started_by_profile_id": body["profile_id"],
                "pin_required": True, "multi_user": False,
                "connected_sessions": [],
            }
            return response
        if (method, path) == ("POST", "/api/v1/lobbies/join"):
            response = super().__call__(method, path, body)
            self.lobby["connected_sessions"] = [body["moonlight_session_id"]]
            return response
        if (method, path) == ("POST", "/api/v1/lobbies/stop"):
            self.calls.append((method, path, copy.deepcopy(body)))
            if self.fail_stop:
                raise TimeoutError("PRIVATE remote daemon state")
            if body["lobby_id"] != self.lobby["id"] or body["pin"] != self.pin:
                return {"success": False}
            self.lobby = None
            return {"success": True}
        return super().__call__(method, path, body)


class OwnerLaunchTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.store = OwnerStore(str(Path(self.root.name) / "private"))
        policy = fixtures()[0]
        with self.store.locked() as fd:
            self.store.write(fd, policy)

    def test_not_executable_without_explicit_host_approval(self):
        api = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "disabled by default"):
            launch_owner_steam("1001", api, store=self.store)
        self.assertEqual(api.calls, [])
        self.assertEqual(owner_launch_status(self.store), {"status": "idle"})

    def test_calls_native_wolf_in_safe_order_and_persists_blocking_lease(self):
        api = FakeWolf()
        result = launch_owner_steam(
            "1001", api, store=self.store, execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(result, {
            "success": True, "status": "joined",
            "manual_review_required_for_next_launch": True
        })
        self.assertEqual(
            [(m, p) for (m, p, _) in api.calls],
            [("GET", "/api/v1/clients"), ("GET", "/api/v1/profiles"),
             ("GET", "/api/v1/apps"), ("GET", "/api/v1/sessions"),
             ("GET", "/api/v1/lobbies"),
             ("POST", "/api/v1/lobbies/create"),
             ("POST", "/api/v1/lobbies/join")])
        create = api.calls[5][2]
        joined = api.calls[6][2]
        self.assertEqual(create["profile_id"], "user")
        self.assertEqual(create["runner_state_folder"],
                         "profile-data/user/WolfSteam")
        self.assertEqual(create["video_settings"]["video_producer_buffer_caps"],
                         "video/x-raw")
        self.assertEqual(joined["lobby_id"], "test_lobby_01")
        self.assertEqual(joined["moonlight_session_id"], "1001")
        self.assertEqual(joined["pin"], create["pin"])
        self.assertEqual(owner_launch_status(self.store), {
            "status": "joined", "manual_review_required": True})
        with self.store.locked() as fd:
            lease = read_lease(fd)
            self.assertEqual(lease["state"], "joined")
            self.assertEqual(lease["client_id"], "1001")
            self.assertEqual(lease["lobby_id"], "test_lobby_01")
            self.assertEqual(stat.S_IMODE(
                (Path(self.root.name) / "private" / "owner-steam-lease.json")
                .stat().st_mode), 0o600)
        raw = (Path(self.root.name) / "private" /
               "owner-steam-lease.json").read_text()
        # Private PIN must survive process restart for StopLobby. Never return
        # it in API status or a client-facing response.
        self.assertIn('"pin"', raw)
        self.assertEqual(len(__import__("json").loads(raw)["pin"]), 8)
        self.assertNotIn("pin", str(result))
        self.assertNotIn("pin", str(owner_launch_status(self.store)))
        self.assertNotIn("WolfSteam", raw)
        self.assertNotIn("aes_key", raw)
        self.assertNotIn("SECRET", raw)
        self.assertNotIn("test_lobby_01", str(result))

    def test_second_request_fails_before_any_wolf_call(self):
        launch_owner_steam("1001", FakeWolf(), store=self.store,
                           execution_approved=True, video_caps="video/x-raw")
        another = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "manual review"):
            launch_owner_steam("1001", another, store=self.store,
                               execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(another.calls, [])

    def test_missing_caps_refuses_before_lease_or_create(self):
        api = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "caps"):
            launch_owner_steam("1001", api, store=self.store,
                               execution_approved=True)
        self.assertFalse(any(call[0] == "POST" for call in api.calls))
        self.assertEqual(owner_launch_status(self.store), {"status": "idle"})

    def test_create_timeout_blocks_retry_without_guessing_rollback(self):
        api = FakeWolf(create=TimeoutError("PRIVATE remote failure"))
        with self.assertRaisesRegex(PolicyError, "state uncertain"):
            launch_owner_steam("1001", api, store=self.store,
                               execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(len([c for c in api.calls if c[0] == "POST"]), 1)
        self.assertEqual(owner_launch_status(self.store)["status"], "uncertain")
        with self.store.locked() as fd:
            self.assertIsNone(read_lease(fd)["lobby_id"])
        with self.assertRaisesRegex(PolicyError, "manual review"):
            launch_owner_steam("1001", FakeWolf(), store=self.store,
                               execution_approved=True, video_caps="video/x-raw")

    def test_join_failure_keeps_lobby_for_explicit_recovery(self):
        api = FakeWolf(join={"success": False, "error": "PRIVATE"})
        with self.assertRaisesRegex(PolicyError, "state uncertain"):
            launch_owner_steam("1001", api, store=self.store,
                               execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(
            [(m, p) for (m, p, _) in api.calls if m == "POST"],
            [("POST", "/api/v1/lobbies/create"),
             ("POST", "/api/v1/lobbies/join")])
        with self.store.locked() as fd:
            lease = read_lease(fd)
            self.assertEqual(lease["state"], "uncertain")
            self.assertEqual(lease["lobby_id"], "test_lobby_01")
        self.assertFalse(any(
            method == "POST" and path.endswith("/stop")
            for method, path, _ in api.calls))

    def test_invalid_create_response_never_attempts_join(self):
        api = FakeWolf(create={"success": True, "lobby_id": "../other"})
        with self.assertRaisesRegex(PolicyError, "state uncertain"):
            launch_owner_steam("1001", api, store=self.store,
                               execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(len([c for c in api.calls if c[0] == "POST"]), 1)

    def test_unapproved_client_fails_before_steam_inventory_read(self):
        api = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "not paired"):
            launch_owner_steam("9999", api, store=self.store,
                               execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(api.calls, [("GET", "/api/v1/clients", None)])
        self.assertEqual(owner_launch_status(self.store)["status"], "idle")

    def test_revoked_grant_fails_without_steam_inventory_or_write(self):
        with self.store.locked() as fd:
            data = self.store.read(fd)
            data["devices"][0]["revoked"] = True
            self.store.write(fd, data)
        api = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "no owner"):
            launch_owner_steam("1001", api, store=self.store,
                               execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(api.calls, [("GET", "/api/v1/clients", None)])
        self.assertEqual(owner_launch_status(self.store)["status"], "idle")

    def test_another_session_or_lobby_fails_before_post_and_lease(self):
        for kind in ("session", "lobby"):
            with self.subTest(kind=kind):
                data = list(fixtures())
                if kind == "session":
                    data[4]["sessions"].append({
                        "client_id": "2002", "app_id": "steam"})
                else:
                    data[5]["lobbies"] = [{"id": "busy"}]
                api = FakeWolf(data=tuple(data))
                with self.assertRaises(PolicyError):
                    launch_owner_steam("1001", api, store=self.store,
                                       execution_approved=True, video_caps="video/x-raw")
                self.assertFalse(any(c[0] == "POST" for c in api.calls))
                self.assertEqual(owner_launch_status(self.store)["status"], "idle")

    def test_tampered_lease_refused_without_auto_clear(self):
        path = Path(self.root.name) / "private" / "owner-steam-lease.json"
        path.write_text('{"bad":"data"}')
        path.chmod(0o600)
        with self.assertRaises(PolicyError):
            owner_launch_status(self.store)
        with self.assertRaises(PolicyError):
            launch_owner_steam("1001", FakeWolf(), store=self.store,
                               execution_approved=True, video_caps="video/x-raw")

    def test_symlinked_lease_refused_without_following(self):
        path = Path(self.root.name) / "private" / "owner-steam-lease.json"
        path.symlink_to(Path(self.root.name) / "private" / "owner-access.json")
        with self.assertRaises(OSError):
            owner_launch_status(self.store)

    def test_rejects_malformed_lease_before_write(self):
        with self.store.locked() as fd:
            invalid = {"version": True, "id": "false", "client_id": "1001",
                       "workspace_id": "bad", "state": [], "lobby_id": None}
            with self.assertRaises(PolicyError):
                write_lease(fd, invalid)
            self.assertIsNone(read_lease(fd))


    def test_persists_v2_pin_and_explicit_stop_archives_blocker(self):
        api = StatefulWolf()
        result = launch_owner_steam(
            "1001", api, store=self.store,
            execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(result["status"], "joined")
        with self.store.locked() as fd:
            lease = read_lease(fd)
            self.assertEqual(lease["version"], 2)
            self.assertEqual(lease["pin"], api.pin)
        stopped = stop_owner_steam(api, store=self.store, confirmed_stop=True)
        self.assertEqual(stopped, {"success": True, "status": "idle",
                                   "lease_archived": True})
        posts = [p for m, p, _ in api.calls if m == "POST"]
        self.assertEqual(posts, ["/api/v1/lobbies/create",
                                 "/api/v1/lobbies/join",
                                 "/api/v1/lobbies/stop"])
        self.assertEqual(owner_launch_status(self.store), {"status": "idle"})
        names = list((Path(self.root.name) / "private").glob(
            "owner-steam-lease.closed-*.json"))
        self.assertEqual(len(names), 1)
        self.assertEqual(stat.S_IMODE(names[0].stat().st_mode), 0o600)
        self.assertNotIn("pin", str(stopped))
        # Relaunch may now proceed only through the normal owner preflight.
        relaunched = launch_owner_steam(
            "1001", api, store=self.store,
            execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(relaunched["status"], "joined")

    def test_stop_requires_approval_and_refuses_mismatched_lobby(self):
        api = StatefulWolf()
        launch_owner_steam("1001", api, store=self.store,
                           execution_approved=True, video_caps="video/x-raw")
        with self.assertRaisesRegex(PolicyError, "approval"):
            stop_owner_steam(api, store=self.store)
        api.lobby["started_by_profile_id"] = "other"
        with self.assertRaisesRegex(PolicyError, "differs"):
            stop_owner_steam(api, store=self.store, confirmed_stop=True)
        self.assertEqual(len([1 for m, p, _ in api.calls
                              if p == "/api/v1/lobbies/stop"]), 0)
        self.assertEqual(owner_launch_status(self.store)["status"], "joined")

    def test_stop_failure_blocks_repeat_and_leaves_pin_private(self):
        api = StatefulWolf()
        launch_owner_steam("1001", api, store=self.store,
                           execution_approved=True, video_caps="video/x-raw")
        api.fail_stop = True
        with self.assertRaisesRegex(PolicyError, "unverified") as err:
            stop_owner_steam(api, store=self.store, confirmed_stop=True)
        self.assertNotIn("PRIVATE", str(err.exception))
        self.assertEqual(owner_launch_status(self.store)["status"], "uncertain")
        with self.assertRaisesRegex(PolicyError, "uncertain"):
            stop_owner_steam(api, store=self.store, confirmed_stop=True)
        self.assertEqual(len([1 for m, p, _ in api.calls
                              if p == "/api/v1/lobbies/stop"]), 1)

    def test_legacy_v1_lease_is_safe_to_read_but_never_stopped_without_pin(self):
        api = StatefulWolf()
        launch_owner_steam("1001", api, store=self.store,
                           execution_approved=True, video_caps="video/x-raw")
        with self.store.locked() as fd:
            lease = read_lease(fd)
            lease["version"] = 1
            del lease["pin"]
            write_lease(fd, lease)
        with self.assertRaisesRegex(PolicyError, "no recoverable PIN"):
            stop_owner_steam(api, store=self.store, confirmed_stop=True)
        self.assertEqual(api.lobby["name"], "Steam")
        self.assertEqual(owner_launch_status(self.store)["status"], "joined")

    def test_legacy_idle_reconciliation_rejects_lingering_sessions_and_lobbies(self):
        api = StatefulWolf()
        launch_owner_steam("1001", api, store=self.store,
                           execution_approved=True, video_caps="video/x-raw")
        with self.assertRaisesRegex(PolicyError, "Explicit"):
            reconcile_stopped_owner_steam(api, store=self.store)
        with self.assertRaisesRegex(PolicyError, "active"):
            reconcile_stopped_owner_steam(
                api, store=self.store, confirmed_runtime_stopped=True,
                confirmed_no_other_steam_writer=True)
        api.lobby = None
        with self.assertRaisesRegex(PolicyError, "active"):
            reconcile_stopped_owner_steam(
                api, store=self.store, confirmed_runtime_stopped=True,
                confirmed_no_other_steam_writer=True)
        api.data[4]["sessions"] = []
        result = reconcile_stopped_owner_steam(
            api, store=self.store, confirmed_runtime_stopped=True,
            confirmed_no_other_steam_writer=True)
        self.assertEqual(result["status"], "idle")
        self.assertTrue(result["lease_archived"])
        self.assertEqual(owner_launch_status(self.store), {"status": "idle"})

    def test_invalid_persisted_pin_denied(self):
        with self.store.locked() as fd:
            from uuid import uuid4
            invalid = {
                "version": 2, "id": str(uuid4()), "client_id": "1001",
                "workspace_id": self.store.read(fd)["workspaces"][0]["id"],
                "state": "creating", "lobby_id": None, "pin": [True] * 8,
            }
            with self.assertRaisesRegex(PolicyError, "PIN"):
                write_lease(fd, invalid)
            self.assertIsNone(read_lease(fd))


if __name__ == "__main__":
    unittest.main()
