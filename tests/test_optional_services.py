"""Cheap source-level regression checks for the optional service boundary.

These catch accidental dashboard expansion or presets excluding the AI URL.
Build/compile tests and live-client smoke tests are separate requirements.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "main.c").read_text()


class OptionalServiceTests(unittest.TestCase):
    def test_primary_dashboard_stays_eight_buttons(self):
        self.assertIn("static GtkWidget *tiles[8]", SOURCE)
        self.assertIn("for(int i=0;i<8;i++){tiles[i]=button(names[i]", SOURCE)
        self.assertIn('gtk_expander_new("ADDITIONAL SERVICES")', SOURCE)
        self.assertIn('button("BRUISER AI","setupaction")', SOURCE)

    def test_optional_tray_entry_is_individually_opt_in(self):
        self.assertIn("#define TRAY_ALL_BUTTONS 511u", SOURCE)
        self.assertIn("#define TRAY_DEFAULT_BUTTONS 255u", SOURCE)
        self.assertIn('"tray_buttons","ai_url"', SOURCE)
        self.assertIn('"Web Gaming","Bruiser AI"', SOURCE)
        self.assertIn("GtkWidget*tray_checks[9]", SOURCE)
        self.assertIn("for(int i=0;i<9;i++)if(gtk_toggle_button_get_active(tray_checks[i]))", SOURCE)
        self.assertIn("for(int i=0;i<9;i++)if(mask & (1u<<i))tray_menu_item(captions[i],i);", SOURCE)
        self.assertIn("else if(action==8)on_bruiser_ai(NULL,NULL);", SOURCE)
        # Existing installations start with eight enabled shortcuts and Bruiser off.
        self.assertIn('"255",""', SOURCE)

    def test_ai_url_is_optional_and_configured_not_hardcoded(self):
        self.assertIn('"tray_buttons","ai_url"', SOURCE)
        self.assertIn("if(*cfg[14]){", SOURCE)
        self.assertIn("if(!safe_preset_url(cfg[14]))return 0;", SOURCE)
        self.assertIn('snprintf(base,sizeof base,"http://%s:3000",cfg[0]);', SOURCE)
        self.assertIn('snprintf(out,cap,"%s/admin/settings",base);', SOURCE)
        self.assertIn("browser_open(url);", SOURCE)
        self.assertIn('button("BRUISER AI ADMIN","setupaction")', SOURCE)
        self.assertNotIn("bruiser.monumentrisk.com", SOURCE)

    def test_preset_v1_can_be_imported_and_v2_contains_ai(self):
        self.assertIn("#define CONFIG_COUNT 15", SOURCE)
        self.assertIn("#define PRESET_COUNT 10", SOURCE)
        self.assertIn("7,10,14}", SOURCE)
        self.assertIn("# OptiPlex Now server preset v2", SOURCE)
        self.assertIn("if(c->preset_loaded){safe_copy(cfg[10],512,c->staged[10]);safe_copy(cfg[14],512,c->staged[14]);}", SOURCE)
        # Reader ignores comment/header lines and matches optional known fields.
        self.assertIn("if(*line && *line!='#')", SOURCE)
        self.assertIn("if(!safe_preset_url(v[14]))return 0;", SOURCE)


if __name__ == "__main__":
    unittest.main()
