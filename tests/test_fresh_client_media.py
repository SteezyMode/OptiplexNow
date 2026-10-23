"""Source-level portability safeguards.

The actual config file read/write and migration behavior is covered by
tests/test_config.c, built and run in CI through make check-config.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "main.c").read_text(encoding="utf-8")
CONFIG = (ROOT / "src" / "config.c").read_text(encoding="utf-8")
SERVICE_SAVER = (ROOT / "src" / "wizard_services.c").read_text(encoding="utf-8")


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
        self.assertIn('open_discovered_videos();', SOURCE)
        self.assertIn('browser_open(cfg[5]);', SOURCE)
        self.assertIn('browser_open(cfg[6]);', SOURCE)
        self.assertIn('browser_open(cfg[7]);', SOURCE)
        self.assertNotIn('"Legacy Downloads URL (unused)"', SOURCE)
        self.assertNotIn('snprintf(cfg[7],512,"http://%s:8085"', SOURCE)


    def test_services_are_committed_before_final_wizard_page(self):
        # A user may navigate away after Next without pressing Finish.
        self.assertIn("if(page==c->finish_page)wizard_save(c);", SOURCE)
        self.assertIn("c->finish_page=six;", SOURCE)
        # Implementation details live in a GTK-free helper, whose actual
        # persistence behavior is tested by make check-wizard-services.
        self.assertIn("now_wizard_store_services(cfg,urls)", SOURCE)
        self.assertIn("now_safe_preset_url(urls[i])", SERVICE_SAVER)

    def test_wolf_pairing_search_is_bounded_and_owner_approved(self):
        # Structural guards: full behavior still requires physical GTK tests.
        self.assertIn("state->auto_refresh_id = g_timeout_add_seconds(3,", SOURCE)
        self.assertIn("3 * 60 * G_USEC_PER_SEC", SOURCE)
        self.assertIn('wolf_ui_start(state, "pending-text", NULL);', SOURCE)
        self.assertIn("wolf_ui_start(state, \"pair\", payload);", SOURCE)
        self.assertIn("g_source_remove(state->auto_refresh_id);", SOURCE)
        self.assertIn("GTK_IS_WINDOW(toplevel)", SOURCE)
        self.assertIn('"CONNECT TO GAME HOST","setupaction"', SOURCE)



if __name__ == "__main__":
    unittest.main()
