"""Portable first-run defaults and configurable service URLs.

Checks that a distributed client does not embed the test owner's service
domains, and that upgrades continue to use saved configuration.
"""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "src" / "main.c").read_text(encoding="utf-8")


class FreshClientMediaTests(unittest.TestCase):
    def test_new_client_has_no_private_server_defaults(self):
        begin = SOURCE.index("static void config_load(void)")
        end = SOURCE.index("static unsigned tray_button_mask(void)", begin)
        loader = SOURCE[begin:end]
        fresh = loader.split('FILE*f=fopen(config_path,"r");if(!f){', 1)[1].split("return;", 1)[0]
        self.assertIn("first_run=1;", fresh)
        self.assertNotIn("monumentrisk.com", SOURCE)
        self.assertNotIn('"optiplex","","",""', SOURCE)
        self.assertNotIn("safe_copy(cfg[5],512,", fresh)
        self.assertIn("safe_copy(cfg[i],512,eq)", loader)

    def test_urls_use_config_not_reference_domains(self):
        self.assertIn('"featured_actions","web_gaming_url"', SOURCE)
        self.assertIn('open_web_gaming_path("/settings");', SOURCE)
        self.assertIn('open_web_gaming_path("/?launch=steam");', SOURCE)
        self.assertIn('gtk_entry_set_text(GTK_ENTRY(web_url_entry),cfg[16]);', SOURCE)
        self.assertIn('safe_copy(cfg[16],512,web_url);', SOURCE)
        self.assertIn('if(now_safe_preset_url(url))safe_copy(cfg[5+i],512,url);', SOURCE)
        self.assertIn('browser_open(cfg[ix]);', SOURCE)
        self.assertIn('browser_open(cfg[7]);', SOURCE)
        self.assertNotIn('snprintf(cfg[6],512,"http://%s:8688"', SOURCE)
        self.assertNotIn('snprintf(cfg[7],512,"http://%s:8085"', SOURCE)
        self.assertNotIn('"Legacy Downloads URL (unused)"', SOURCE)

    def test_saved_urls_preserved_on_upgrade(self):
        loader = SOURCE[SOURCE.index("static void config_load(void)"):
                        SOURCE.index("static unsigned tray_button_mask(void)")]
        self.assertIn("if(!strcmp(line,keys[i]))", loader)
        self.assertIn("safe_copy(cfg[i],512,eq)", loader)
        self.assertIn("FILE*f=fopen(config_path", loader)


if __name__ == "__main__":
    unittest.main()
