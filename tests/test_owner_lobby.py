"""Request-plan regression tests for the supported Wolf-UI lobby flow.

All Wolf API data here is fabricated. No Steam instance or Wolf daemon is used.
"""
import copy
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from owner_access import PolicyError, approve_device, new_owner
from owner_lobby import plan_owner_steam_lobby, fill_join_lobby


def fixtures():
    p = {"success": True, "profiles": [
        {"id": "moonlight-profile-id", "apps": [
            {"title": "Wolf UI", "id": "wolf-ui-id"}]},
        {"id": "user", "name": "Personal", "pin": [9, 8, 7, 6], "apps": [
            {"title": "Steam", "icon_png_path": "/some-icon.png",
             "render_node": "/dev/dri/renderD128",
             "runner": {"type": "docker", "name": "WolfSteam",
                        "image": "example.invalid/steam:test",
                        "mounts": [], "env": ["A=1"],
                        "devices": [], "ports": []}}]}
    ]}
    clients = {"success": True, "clients": [
        {"client_id": "1001", "app_state_folder": "1001"}]}
    policy = new_owner("user", p)
    approve_device(policy, "1001", clients)
    apps = {"success": True, "apps": [
        {"title": "Wolf UI", "id": "wolf-ui-id"},
        {"title": "Steam", "id": "steam-direct-id"}]}
    sessions = {"success": True, "sessions": [
        {"client_id": "1001", "app_id": "wolf-ui-id",
         "aes_key": "SECRET-KEY-NEVER-RETRIEVED", "aes_iv": "SECRET-IV",
         "video_width": 1280, "video_height": 720,
         "video_refresh_rate": 30, "audio_channel_count": 2,
         "client_settings": {"run_uid": 1000, "run_gid": 1000}}]}
    lobbies = {"success": True, "lobbies": []}
    return policy, clients, p, apps, sessions, lobbies


class OwnerLobbyTests(unittest.TestCase):
    def plan(self, data=None, client_id="1001", pin=None):
        if data is None:
            data = fixtures()
        return plan_owner_steam_lobby(*data[:1], client_id, *data[1:],
                                     pin_digits=pin or [1, 2, 3, 4, 5, 6, 7, 8])

    def test_builds_wolf_ui_compatible_private_lobby(self):
        plan = self.plan()
        create = plan["create_body"]
        self.assertEqual(plan["create_path"], "/api/v1/lobbies/create")
        self.assertEqual(plan["join_path"], "/api/v1/lobbies/join")
        self.assertEqual(create["profile_id"], "user")
        self.assertEqual(create["runner_state_folder"], "profile-data/user/WolfSteam")
        self.assertEqual(create["name"], "Steam")
        self.assertFalse(create["multi_user"])
        self.assertFalse(create["stop_when_everyone_leaves"])
        self.assertEqual(create["pin"], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(create["video_settings"]["width"], 1280)
        self.assertEqual(create["video_settings"]["height"], 720)
        self.assertEqual(create["video_settings"]["refresh_rate"], 30)
        self.assertEqual(create["video_settings"]["runner_render_node"],
                         "/dev/dri/renderD128")
        self.assertEqual(create["audio_settings"]["channel_count"], 2)
        self.assertEqual(create["runner"]["name"], "WolfSteam")
        self.assertEqual(create["client_settings"]["run_uid"], 1000)
        self.assertEqual(plan["join_template"]["moonlight_session_id"], "1001")
        self.assertIsNone(plan["join_template"]["lobby_id"])
        self.assertNotIn("aes_key", str(plan))
        self.assertNotIn("SECRET-KEY", str(plan))
        self.assertNotIn("SECRET-IV", str(plan))
        self.assertNotIn("pin_required", str(plan))

    def test_join_uses_returned_wolf_lobby_id_only(self):
        plan = self.plan()
        body = fill_join_lobby(plan, {"success": True, "lobby_id": "lobby_17"})
        self.assertEqual(body, {"lobby_id": "lobby_17",
                                "moonlight_session_id": "1001",
                                "pin": [1, 2, 3, 4, 5, 6, 7, 8]})
        self.assertIsNone(plan["join_template"]["lobby_id"])
        for result in (
            {"success": False, "lobby_id": "lobby_17"},
            {"success": True, "lobby_id": "../../other"},
            {"success": True, "lobby_id": ""},
            {},
        ):
            with self.subTest(result=result):
                with self.assertRaises(PolicyError):
                    fill_join_lobby(plan, result)

    def test_unapproved_or_revoked_client_cannot_build(self):
        policy, clients, p, apps, sess, lobbies = fixtures()
        policy["devices"][0]["revoked"] = True
        with self.assertRaisesRegex(PolicyError, "authorization"):
            self.plan((policy, clients, p, apps, sess, lobbies))
        policy["devices"] = []
        with self.assertRaisesRegex(PolicyError, "authorization"):
            self.plan((policy, clients, p, apps, sess, lobbies))
        with self.assertRaises(PolicyError):
            self.plan((policy, clients, p, apps, sess, lobbies), client_id="9999")

    def test_owner_profile_must_be_present(self):
        data = list(fixtures())
        data[2]["profiles"] = [data[2]["profiles"][0]]
        with self.assertRaisesRegex(PolicyError, "unavailable"):
            self.plan(tuple(data))

    def test_must_stream_actual_wolf_ui_on_approved_device(self):
        data = list(fixtures())
        data[4]["sessions"][0]["app_id"] = "steam-direct-id"
        with self.assertRaisesRegex(PolicyError, "Wolf UI"):
            self.plan(tuple(data))
        data = list(fixtures())
        data[4]["sessions"] = []
        with self.assertRaisesRegex(PolicyError, "Wolf UI"):
            self.plan(tuple(data))
        data = list(fixtures())
        data[3]["apps"].append({"title": "Wolf UI", "id": "another"})
        with self.assertRaisesRegex(PolicyError, "Ambiguous"):
            self.plan(tuple(data))

    def test_busy_session_blocks_second_writer(self):
        data = list(fixtures())
        data[4]["sessions"].append({
            "client_id": "1002", "app_id": "steam-direct-id",
            "aes_key": "SHOULD-NOT-BE-ECHOED"})
        with self.assertRaisesRegex(PolicyError, "Another Wolf session"):
            self.plan(tuple(data))

    def test_disconnected_lobby_still_blocks_duplicate_steam(self):
        data = list(fixtures())
        data[5]["lobbies"] = [{
            "id": "old-lobby",
            "started_by_profile_id": "user",
            "runner_state_folder": "profile-data/user/WolfSteam",
            "connected_sessions": [],
        }]
        with self.assertRaisesRegex(PolicyError, "Existing Wolf lobby"):
            self.plan(tuple(data))

    def test_invalid_or_conflicting_live_inventory_fails_closed(self):
        for idx, field in ((3, "apps"), (4, "sessions"), (5, "lobbies")):
            data = list(fixtures())
            data[idx][field] = None
            with self.subTest(field=field):
                with self.assertRaises(PolicyError):
                    self.plan(tuple(data))
        data = list(fixtures())
        data[4]["sessions"][0]["client_settings"] = None
        with self.assertRaises(PolicyError):
            self.plan(tuple(data))
        data = list(fixtures())
        for bad in ("../../Steam", "..", ".hidden", "Steam..Other", ""):
            with self.subTest(runner_name=bad):
                data = list(fixtures())
                data[2]["profiles"][1]["apps"][0]["runner"]["name"] = bad
                with self.assertRaises(PolicyError):
                    self.plan(tuple(data))

    def test_runner_missing_required_wolf_fields_refused(self):
        for missing in ("type", "name", "image", "mounts", "env",
                        "devices", "ports"):
            with self.subTest(missing=missing):
                data = list(fixtures())
                del data[2]["profiles"][1]["apps"][0]["runner"][missing]
                with self.assertRaises(PolicyError):
                    self.plan(tuple(data))
        data = list(fixtures())
        data[2]["profiles"][1]["apps"][0]["runner"]["type"] = "process"
        with self.assertRaisesRegex(PolicyError, "Incomplete Wolf Docker"):
            self.plan(tuple(data))

    def test_pin_is_validated_and_not_guessed_by_client(self):
        data = fixtures()
        for pin in ([1], [1,2,3,4,5,6,7,99], "12345678", [True]*8):
            with self.subTest(pin=pin):
                with self.assertRaises(PolicyError):
                    plan_owner_steam_lobby(
                        data[0], "1001", *data[1:], pin_digits=pin)
        p = plan_owner_steam_lobby(data[0], "1001", *data[1:])
        self.assertEqual(len(p["create_body"]["pin"]), 8)
        self.assertEqual(p["create_body"]["pin"], p["join_template"]["pin"])
        self.assertTrue(all(0 <= d <= 9 for d in p["create_body"]["pin"]))


if __name__ == "__main__":
    unittest.main()
