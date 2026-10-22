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
                          write_lease)
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
            "1001", api, store=self.store, execution_approved=True)
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
        self.assertNotIn('"pin"', raw)
        self.assertNotIn("WolfSteam", raw)
        self.assertNotIn("aes_key", raw)
        self.assertNotIn("SECRET", raw)
        self.assertNotIn("test_lobby_01", str(result))

    def test_second_request_fails_before_any_wolf_call(self):
        launch_owner_steam("1001", FakeWolf(), store=self.store,
                           execution_approved=True)
        another = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "manual review"):
            launch_owner_steam("1001", another, store=self.store,
                               execution_approved=True)
        self.assertEqual(another.calls, [])

    def test_create_timeout_blocks_retry_without_guessing_rollback(self):
        api = FakeWolf(create=TimeoutError("PRIVATE remote failure"))
        with self.assertRaisesRegex(PolicyError, "state uncertain"):
            launch_owner_steam("1001", api, store=self.store,
                               execution_approved=True)
        self.assertEqual(len([c for c in api.calls if c[0] == "POST"]), 1)
        self.assertEqual(owner_launch_status(self.store)["status"], "uncertain")
        with self.store.locked() as fd:
            self.assertIsNone(read_lease(fd)["lobby_id"])
        with self.assertRaisesRegex(PolicyError, "manual review"):
            launch_owner_steam("1001", FakeWolf(), store=self.store,
                               execution_approved=True)

    def test_join_failure_keeps_lobby_for_explicit_recovery(self):
        api = FakeWolf(join={"success": False, "error": "PRIVATE"})
        with self.assertRaisesRegex(PolicyError, "state uncertain"):
            launch_owner_steam("1001", api, store=self.store,
                               execution_approved=True)
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
                               execution_approved=True)
        self.assertEqual(len([c for c in api.calls if c[0] == "POST"]), 1)

    def test_unapproved_client_fails_before_steam_inventory_read(self):
        api = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "not paired"):
            launch_owner_steam("9999", api, store=self.store,
                               execution_approved=True)
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
                               execution_approved=True)
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
                                       execution_approved=True)
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
                               execution_approved=True)

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


if __name__ == "__main__":
    unittest.main()
