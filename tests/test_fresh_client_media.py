"""Source-level portability safeguards.

The actual config file read/write and migration behavior is covered by
tests/test_config.c, built and run in CI through make check-config.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "main.c").read_text(encoding="utf-8")
CONFIG = (ROOT / "src" / "config.c").read_text(encoding="utf-8")


class FreshClientMediaTests(unittest.TestCase):
    def test_new_install_does_not_embed_reference_service_domains(self):
        self.assertNotIn("monumentrisk.com", SOURCE)
        self.assertNotIn("monumentrisk.com", CONFIG)
        self.assertIn("now_config_load();", SOURCE)
        self.assertIn('extern int first_run;', (ROOT / "src" / "config.h").read_text())

    def test_services_use_configured_urls(self):
        self.assertIn('"web_gaming_url"', CONFIG)
        self.assertIn('open_web_gaming_path("/settings");', SOURCE)
        self.assertIn('open_web_gaming_path("/?launch=steam");', SOURCE)
        self.assertIn('gtk_entry_set_text(GTK_ENTRY(web_url_entry),cfg[16]);', SOURCE)
        self.assertIn('safe_copy(cfg[16],512,web_url);', SOURCE)
        self.assertIn('browser_open(cfg[ix]);', SOURCE)
        self.assertIn('browser_open(cfg[7]);', SOURCE)
        self.assertNotIn('"Legacy Downloads URL (unused)"', SOURCE)
        self.assertNotIn('snprintf(cfg[7],512,"http://%s:8085"', SOURCE)


if __name__ == "__main__":
    unittest.main()
