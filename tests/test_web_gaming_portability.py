"""Regression checks for portable Web Gaming endpoint configuration.

Source-level contract supplements the GTK smoke tests. Don't allow a dev-only
endpoint to be reintroduced as a default for customers.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/main.c").read_text(encoding="utf-8")


class WebGamingPortabilityTests(unittest.TestCase):
    def test_no_developer_hardcoded_stream_url(self):
        self.assertNotIn("games.monumentrisk.com", SOURCE)

    def test_url_has_an_explicit_optional_config_key(self):
        self.assertIn('"web_gaming_url"', SOURCE)
        self.assertIn('#define CONFIG_COUNT 17', SOURCE)
        self.assertIn('gtk_entry_set_text(GTK_ENTRY(web_entry),cfg[16])', SOURCE)
        self.assertIn('safe_copy(cfg[16],512,web_url)', SOURCE)

    def test_launch_requires_configured_url(self):
        self.assertRegex(SOURCE, r'else if\(n==7\)\{\s+if\(!\*cfg\[16\]\|\|!now_safe_preset_url\(cfg\[16\]\)\)')
        self.assertIn('else browser_open(cfg[16]);', SOURCE)

    def test_does_not_override_current_user_connection(self):
        self.assertIn('if(c->preset_loaded){safe_copy(cfg[10]', SOURCE)
        self.assertNotIn('safe_copy(cfg[16],512,"https://', SOURCE)


if __name__ == "__main__":
    unittest.main()
