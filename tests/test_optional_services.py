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

    def test_ai_url_is_optional_and_configured_not_hardcoded(self):
        self.assertIn('"tray_buttons","ai_url"', SOURCE)
        self.assertIn("if(!safe_preset_url(cfg[14])||!*cfg[14])", SOURCE)
        self.assertIn("browser_open(cfg[14]);", SOURCE)
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
