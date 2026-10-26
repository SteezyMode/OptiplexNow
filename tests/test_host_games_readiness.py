"""Wolf clean-host Games inspect tests: no Docker or live host access."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import host_games_readiness as games  # noqa: E402


V2 = '''
config_version = 2
paired_clients = []
[[profiles]]
id = "moonlight-profile-id"
[[profiles.apps]]
title = "Wolf UI"
[profiles.apps.runner]
type = "docker"
[[profiles]]
id = "user"
name = "Owner"
[[profiles.apps]]
title = "Steam"
[profiles.apps.runner]
type = "docker"
name = "WolfSteam"
'''
V3 = '''
config_version = 3
paired_clients = [{client_cert="A PRIVATE CERT THAT MUST NEVER APPEAR"}]
[[apps]]
title = "Steam"
[apps.runner]
type = "docker"
name = "WolfSteam"
'''


class WolfGamesReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="now-wolf-games-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "wolf"
        (self.root / "cfg").mkdir(parents=True)
        self.config = self.root / "cfg" / "config.toml"

    def test_no_first_boot_config_is_pending_not_a_stream(self):
        r = games.inspect_config(self.root)
        self.assertEqual(r["state"], "wolf_config_pending")
        self.assertFalse(r["first_game_verified"])

    def test_named_owner_steam_candidate_does_not_certify_gameplay(self):
        self.config.write_text(V2, encoding="utf-8")
        report = games.inspect_config(self.root)
        self.assertEqual(report["state"], "named_steam_candidate")
        self.assertEqual(report["wolf_config_version"], 2)
        self.assertTrue(report["named_owner_profile_found"])
        self.assertTrue(report["steam_app_configured"])
        self.assertFalse(report["owner_steam_home_present"])
        home = self.root / "profile_data" / "user" / "Steam"
        home.mkdir(parents=True)
        report = games.inspect_config(self.root)
        self.assertTrue(report["owner_steam_home_present"])
        self.assertFalse(report["steam_login_verified"])
        self.assertFalse(report["client_enrollment_verified"])
        self.assertFalse(report["video_audio_controller_verified"])

    def test_modern_v3_app_is_per_device_not_an_owner_profile(self):
        self.config.write_text(V3, encoding="utf-8")
        report = games.inspect_config(self.root)
        self.assertEqual(report["wolf_config_version"], 3)
        self.assertEqual(report["state"], "v3_per_device_state_requires_owner_mapping")
        self.assertFalse(report["named_owner_profile_found"])
        self.assertTrue(report["steam_app_configured"])
        self.assertNotIn("PRIVATE CERT", json.dumps(report))

    def test_absent_or_duplicate_named_profile_refuses_to_guess(self):
        for cfg in (
            V2.replace('id = "user"', 'id = "other"'),
            V2 + '\n[[profiles]]\nid = "user"\n',
        ):
            with self.subTest(config=cfg[-60:]):
                self.config.write_text(cfg, encoding="utf-8")
                self.assertEqual(
                    games.inspect_config(self.root)["state"],
                    "named_owner_profile_missing_or_ambiguous")

    def test_nonsteam_and_noncontainer_apps_cannot_claim_ready(self):
        for cfg in (
            V2.replace('title = "Steam"', 'title = "Firefox"'),
            V2.replace('type = "docker"\nname = "WolfSteam"', 'type = "process"\nname = "WolfSteam"'),
        ):
            self.config.write_text(cfg, encoding="utf-8")
            self.assertEqual(games.inspect_config(self.root)["state"],
                             "steam_app_missing")
        self.config.write_text(V3.replace('title = "Steam"', 'title = "Browser"'), encoding="utf-8")
        self.assertEqual(games.inspect_config(self.root)["state"],
                         "steam_app_missing")

    def test_malformed_config_symlink_and_oversized_content_fail_closed(self):
        self.config.write_text("not\tvalid <<", encoding="utf-8")
        self.assertEqual(games.inspect_config(self.root)["state"],
                         "wolf_config_invalid")
        self.config.write_bytes(b"x" * (games.MAX_CONFIG_BYTES + 1))
        self.assertEqual(games.inspect_config(self.root)["state"],
                         "wolf_config_unsafe_or_oversized")
        self.config.unlink()
        target = Path(self.tmp.name) / "outside.toml"
        target.write_text(V2)
        self.config.symlink_to(target)
        self.assertEqual(games.inspect_config(self.root)["state"],
                         "wolf_config_unsafe_or_oversized")

    def test_unknown_version_is_not_treated_as_named_profile(self):
        self.config.write_text(V2.replace("config_version = 2", "config_version = 5"))
        self.assertEqual(games.inspect_config(self.root)["state"],
                         "wolf_config_version_unsupported")


if __name__ == "__main__":
    unittest.main()
