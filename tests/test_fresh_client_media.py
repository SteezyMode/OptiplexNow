"""Household beta: fresh NOW installs have media URL ready, upgrades do not.

The complete native GTK build, Debian packaging and smoke tests also run in CI.
"""
from pathlib import Path
import re
import unittest

SOURCE=(Path(__file__).resolve().parents[1]/"src"/"main.c").read_text(encoding="utf-8")

class FreshClientMediaTests(unittest.TestCase):
    def test_first_run_prefills_https_video_service(self):
        begin=SOURCE.index("static void config_load(void)")
        end=SOURCE.index("static unsigned tray_button_mask(void)",begin)
        loader=SOURCE[begin:end]
        self.assertIn('FILE*f=fopen(config_path,"r");if(!f){',loader)
        fresh=loader.split('FILE*f=fopen(config_path,"r");if(!f){',1)[1].split("return;",1)[0]
        self.assertIn("first_run=1;",fresh)
        self.assertIn('safe_copy(cfg[5],512,"https://media.monumentrisk.com");',fresh)
        self.assertIn('return;',loader)

    def test_existing_config_never_overwritten_with_home_url(self):
        loader=SOURCE[SOURCE.index("static void config_load(void)"):
                      SOURCE.index("static unsigned tray_button_mask(void)")]
        suffix=loader.split('FILE*f=fopen(config_path,"r");if(!f){',1)[1].split("return;",1)[1]
        self.assertNotIn("media.monumentrisk.com",suffix)
        self.assertIn('safe_copy(cfg[i],512,eq)',suffix)
        self.assertIn('if(!strcmp(line,keys[i]))',suffix)
        defaults=SOURCE[SOURCE.index("static const char *defaults[]="):
                        SOURCE.index("static char cfg[CONFIG_COUNT]")]
        self.assertNotIn("media.monumentrisk.com",defaults)

    def test_service_uses_saved_config_and_wizard_prefill(self):
        self.assertIn('const char *keys[]={"host","user","relay","relay_user","wake_command","videos"',SOURCE)
        self.assertIn('int ix=n==1?5:6;',SOURCE)
        self.assertIn('browser_open(cfg[ix]);',SOURCE)
        self.assertIn('gtk_entry_set_text(GTK_ENTRY(c->service_inputs[i]),c->staged[i+5])',SOURCE)
        self.assertIn('if(now_safe_preset_url(url))safe_copy(cfg[5+i],512,url);',SOURCE)
        self.assertNotIn("media.monumentrisk.com?",SOURCE)
        # This is a demo-build default, not a replacement Web Gaming service.
        self.assertIn('browser_open("https://games.monumentrisk.com/?launch=steam");',SOURCE)
        self.assertIn('"featured_actions"',SOURCE)

if __name__=="__main__":
    unittest.main()
