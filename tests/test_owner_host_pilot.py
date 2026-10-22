"""Offline host-pilot tests. No real Wolf/GPU/Steam/Docker or SSH."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

from owner_access import OwnerStore, PolicyError
from owner_host_pilot import (
    inspect_candidate as _inspect_candidate,
    enroll_current_owner as _enroll_current_owner,
    launch_enrolled_owner as _launch_enrolled_owner,
)

# Offline fixtures explicitly model a host with software/non-zero-copy caps.
# Runtime code deliberately has no default: a real operator must verify this.
TEST_VIDEO_CAPS = "video/x-raw"

def inspect_candidate(*args, **kwargs):
    return _inspect_candidate(*args, video_caps=kwargs.pop("video_caps", TEST_VIDEO_CAPS),
                              **kwargs)

def enroll_current_owner(*args, **kwargs):
    return _enroll_current_owner(*args, video_caps=kwargs.pop("video_caps", TEST_VIDEO_CAPS),
                                 **kwargs)

def launch_enrolled_owner(*args, **kwargs):
    return _launch_enrolled_owner(*args, video_caps=kwargs.pop("video_caps", TEST_VIDEO_CAPS),
                                  **kwargs)
from owner_launch import owner_launch_status
from owner_steam_pilot import run as cli_run
from test_owner_launch import FakeWolf
from test_owner_lobby import fixtures


class HostPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = OwnerStore(str(self.root / "private"))

    def test_readonly_preflight_calls_five_get_and_redacts_client(self):
        api = FakeWolf()
        report, client, _, _ = inspect_candidate(api)
        self.assertEqual(client, "1001")
        self.assertTrue(report["steam_runner_validated"])
        self.assertFalse(report["steam_launch_performed"])
        self.assertFalse(report["remote_client_authentication_implemented"])
        self.assertEqual(len(api.calls), 5)
        self.assertTrue(all(c[0] == "GET" for c in api.calls))
        self.assertNotIn("1001", str(report))
        self.assertNotIn("SECRET", str(report))
        self.assertFalse((self.root / "private").exists())

    def test_inspect_cli_requires_no_state_directory(self):
        api = FakeWolf()
        result = cli_run(SimpleNamespace(action="inspect", profile="user",
                                         state_dir=None, video_caps=TEST_VIDEO_CAPS), api=api)
        self.assertTrue(result["success"])
        self.assertFalse((self.root / "private").exists())

    def test_preflight_refuses_not_wolf_ui_other_sessions_and_lobby(self):
        for mutation in ("no-session", "wrong-app", "two-sessions",
                         "lobby", "unpaired", "duplicate-record",
                         "conflicting-record", "missing-runner"):
            with self.subTest(mutation=mutation):
                p, clients, profiles, apps, sessions, lobbies = copy.deepcopy(fixtures())
                if mutation == "no-session":
                    sessions["sessions"] = []
                elif mutation == "wrong-app":
                    sessions["sessions"][0]["app_id"] = "steam-direct-id"
                elif mutation == "two-sessions":
                    sessions["sessions"].append(dict(sessions["sessions"][0]))
                elif mutation == "lobby":
                    lobbies["lobbies"].append({"id": "existing"})
                elif mutation == "unpaired":
                    clients["clients"] = []
                elif mutation == "duplicate-record":
                    clients["clients"].append(dict(clients["clients"][0]))
                elif mutation == "conflicting-record":
                    clients["clients"].append({"client_id": "1001",
                                               "app_state_folder": "different"})
                elif mutation == "missing-runner":
                    del profiles["profiles"][1]["apps"][0]["runner"]["devices"]
                api = FakeWolf(data=(p, clients, profiles, apps, sessions, lobbies))
                with self.assertRaises(PolicyError):
                    inspect_candidate(api)
                self.assertTrue(all(c[0] == "GET" for c in api.calls))
                self.assertFalse((self.root / "private").exists())

    def test_unverified_caps_fail_before_any_write_or_post(self):
        api = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "caps"):
            _inspect_candidate(api)
        self.assertEqual(len(api.calls), 5)
        self.assertFalse(any(c[0] == "POST" for c in api.calls))
        self.assertFalse((self.root / "private").exists())

    def test_enrollment_requires_both_operator_confirmations(self):
        for owner, device in ((False, False), (True, False), (False, True)):
            api = FakeWolf()
            with self.assertRaisesRegex(PolicyError, "consent"):
                enroll_current_owner(api, self.store,
                                     confirmed_owner=owner,
                                     confirmed_device=device)
            self.assertEqual(api.calls, [])
            self.assertFalse((self.root / "private").exists())

    def test_enrollment_is_private_and_cannot_overwrite(self):
        api = FakeWolf()
        result = enroll_current_owner(api, self.store,
                                      confirmed_owner=True,
                                      confirmed_device=True)
        self.assertTrue(result["owner_policy_enrolled"])
        self.assertNotIn("1001", str(result))
        path = self.root / "private" / "owner-access.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.store.locked() as fd:
            stored = self.store.read(fd)
        self.assertEqual(stored["workspaces"][0]["profile_id"], "user")
        self.assertEqual(stored["devices"][0]["client_id"], "1001")
        with self.assertRaisesRegex(PolicyError, "already exists"):
            enroll_current_owner(FakeWolf(), self.store,
                                 confirmed_owner=True, confirmed_device=True)

    def test_launch_requires_all_three_manual_safety_confirmations(self):
        api = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "consent"):
            launch_enrolled_owner(api, self.store)
        self.assertEqual(api.calls, [])

    def test_only_enrolled_active_device_can_create_join(self):
        enroll_current_owner(FakeWolf(), self.store,
                             confirmed_owner=True, confirmed_device=True)
        api = FakeWolf()
        result = launch_enrolled_owner(
            api, self.store,
            confirmed_live_steam=True,
            confirmed_no_other_steam_writer=True,
            confirmed_legacy_links_reviewed=True)
        self.assertEqual(result["status"], "joined")
        posts = [c for c in api.calls if c[0] == "POST"]
        self.assertEqual([c[1] for c in posts],
                         ["/api/v1/lobbies/create", "/api/v1/lobbies/join"])
        self.assertEqual(posts[0][2]["profile_id"], "user")
        self.assertEqual(posts[1][2]["moonlight_session_id"], "1001")
        self.assertEqual(owner_launch_status(self.store)["status"], "joined")
        other = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "manual review"):
            launch_enrolled_owner(
                other, self.store, confirmed_live_steam=True,
                confirmed_no_other_steam_writer=True,
                confirmed_legacy_links_reviewed=True)
        self.assertFalse(any(c[0] == "POST" for c in other.calls))

    def test_launch_does_not_grant_fresh_or_revoked_client(self):
        enroll_current_owner(FakeWolf(), self.store,
                             confirmed_owner=True, confirmed_device=True)
        p, c, pr, a, s, l = copy.deepcopy(fixtures())
        c["clients"].append({"client_id": "2002", "app_state_folder": "two"})
        s["sessions"][0]["client_id"] = "2002"
        api = FakeWolf(data=(p, c, pr, a, s, l))
        with self.assertRaisesRegex(PolicyError, "no owner"):
            launch_enrolled_owner(
                api, self.store, confirmed_live_steam=True,
                confirmed_no_other_steam_writer=True,
                confirmed_legacy_links_reviewed=True)
        self.assertFalse(any(call[0] == "POST" for call in api.calls))
        self.assertEqual(owner_launch_status(self.store)["status"], "idle")

    def test_launch_cli_refuses_relative_state_path(self):
        args = SimpleNamespace(action="launch", profile="user",
                               state_dir="relative", confirm_live_steam=True,
                               confirm_no_other_steam_writer=True,
                               confirm_legacy_links_reviewed=True)
        api = FakeWolf()
        with self.assertRaisesRegex(PolicyError, "absolute"):
            cli_run(args, api=api)
        self.assertEqual(api.calls, [])


if __name__ == "__main__":
    unittest.main()
