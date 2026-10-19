"""Source regression checks for optional services and retained client settings.

The GTK build, packaging checks and live GUI smoke tests are separate requirements.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "main.c").read_text()
PRESET_SOURCE = (ROOT / "src" / "presets.c").read_text()


class OptionalServiceTests(unittest.TestCase):
    def test_service_tiles_have_a_single_home(self):
        self.assertIn("static GtkWidget *tiles[9]", SOURCE)
        self.assertIn('gtk_expander_new("ADDITIONAL SERVICES")', SOURCE)
        self.assertIn("gtk_grid_attach(GTK_GRID(chosen?grid:extras_grid),tiles[i]", SOURCE)
        self.assertIn("unsigned featured=featured_mask();int primary=0,other=0;", SOURCE)
        self.assertIn("for(int i=0;i<9;i++){tiles[i]=button(names[i]", SOURCE)

    def test_primary_and_tray_are_independently_selected(self):
        self.assertIn("#define TRAY_ALL_BUTTONS 511u", SOURCE)
        self.assertIn("#define TRAY_DEFAULT_BUTTONS 255u", SOURCE)
        self.assertIn("GtkWidget*featured_checks[9],*tray_checks[9]", SOURCE)
        self.assertIn('"PRIMARY","storagehead"', SOURCE)
        self.assertIn('"TRAY","storagehead"', SOURCE)
        self.assertIn("gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(featured_checks[i]))", SOURCE)
        self.assertIn("gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(tray_checks[i]))", SOURCE)
        self.assertIn("snprintf(cfg[FEATURED_MASK_SETTING],512", SOURCE)
        self.assertIn("snprintf(cfg[TRAY_MASK_SETTING],512", SOURCE)
        self.assertIn("for(int i=0;i<9;i++)if(mask & (1u<<i))tray_menu_item(captions[i],i);", SOURCE)
        self.assertIn("else if(action==8)on_bruiser_ai(NULL,NULL);", SOURCE)

    def test_old_layout_and_config_migrate_safely(self):
        self.assertIn("#define CONFIG_COUNT 16", SOURCE)
        self.assertIn("#define FEATURED_MASK_SETTING 15", SOURCE)
        self.assertIn("#define NEW_INSTALL_FEATURED_MASK 207u", SOURCE)
        self.assertIn("#define EXISTING_INSTALL_FEATURED_MASK 255u", SOURCE)
        self.assertIn("if(!has_featured)snprintf(cfg[FEATURED_MASK_SETTING]", SOURCE)
        self.assertIn('"tray_buttons","ai_url","featured_actions"', SOURCE)
        self.assertIn('"255","","207"', SOURCE)
        self.assertIn("last_columns=-1;", SOURCE)

    def test_ai_url_and_admin_are_optional(self):
        self.assertIn("if(*cfg[14]){", SOURCE)
        self.assertIn("if(!now_safe_preset_url(cfg[14]))return 0;", SOURCE)
        self.assertIn('snprintf(base,sizeof base,"http://%s:3000",cfg[0]);', SOURCE)
        self.assertIn('snprintf(out,cap,"%s/admin/settings",base);', SOURCE)
        self.assertIn("browser_open(url);", SOURCE)
        self.assertIn('button("BRUISER AI ADMIN","setupaction")', SOURCE)
        self.assertNotIn("bruiser.monumentrisk.com", SOURCE)

    def test_old_connection_preset_remains_importable(self):
        self.assertIn("#define PRESET_COUNT 10", PRESET_SOURCE)
        self.assertIn("7,10,14}", PRESET_SOURCE)
        self.assertIn("PRESET_HEADER_V2", PRESET_SOURCE)
        self.assertIn("PRESET_HEADER_V1", PRESET_SOURCE)
        self.assertIn("if(c->preset_loaded){safe_copy(cfg[10],512,c->staged[10]);safe_copy(cfg[14],512,c->staged[14]);}", SOURCE)
        self.assertIn("if(*line && *line!='#')", PRESET_SOURCE)
        self.assertIn("if(!now_safe_preset_url(v[14]))return 0;", PRESET_SOURCE)


if __name__ == "__main__":
    unittest.main()
