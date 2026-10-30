"""Source regression checks for optional services and retained client settings.

The GTK build, packaging checks and live GUI smoke tests are separate requirements.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "main.c").read_text()
SETTINGS = (ROOT / "src" / "ui_settings.c").read_text()
SETTINGS_HEADER = (ROOT / "src" / "ui_settings.h").read_text()
PRESET_SOURCE = (ROOT / "src" / "presets.c").read_text()
CONFIG_SOURCE = (ROOT / "src" / "config.c").read_text()
CONFIG_HEADER = (ROOT / "src" / "config.h").read_text()
TRAY_HEADER = (ROOT / "src" / "tray_prefs.h").read_text()
TRAY_SOURCE = (ROOT / "src" / "tray_prefs.c").read_text()


class OptionalServiceTests(unittest.TestCase):
    def test_service_tiles_have_a_single_home(self):
        self.assertIn("static GtkWidget *tiles[9]", SOURCE)
        self.assertIn('gtk_expander_new("ADDITIONAL SERVICES")', SOURCE)
        self.assertIn("gtk_grid_attach(GTK_GRID(chosen?grid:extras_grid),tiles[i]", SOURCE)
        self.assertIn("unsigned featured=featured_mask();int primary=0,other=0;", SOURCE)
        self.assertIn("for(int i=0;i<8;i++){tiles[i]=button(names[i]", SOURCE)

    def test_primary_and_tray_are_independently_selected(self):
        # The actual order, mask, persistence and label behaviors are tested
        # by compiled tests/test_tray_prefs.c, including malformed input.
        self.assertIn("#define NOW_TRAY_DEFAULT_MASK 255u", TRAY_HEADER)
        self.assertIn("now_tray_parse_mask(cfg[TRAY_MASK_SETTING])", SOURCE)
        self.assertIn("now_tray_service_caption(action, desktop, caption", SOURCE)
        self.assertIn("now_tray_order_load(order)", SOURCE)
        self.assertIn("now_tray_order_save(ordered)", SOURCE)
        self.assertIn("now_tray_desktop_caption_save(new_caption)", SOURCE)
        # Checkbox widgets now live in the long-lived in-window Settings form.
        self.assertIn("GtkWidget *fields[8], *diskentry, *combo, *featured_checks[8], *tray_checks[8];", SETTINGS_HEADER)
        self.assertIn("**featured_checks=form->featured_checks,**tray_checks=form->tray_checks", SOURCE)
        self.assertIn('const char*head_names[]={"SERVICE","PRIMARY","TRAY","MOVE"};', SETTINGS)
        self.assertIn("gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(featured_checks[i]))", SOURCE)
        self.assertIn("gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(tray_checks[i]))", SOURCE)
        self.assertIn("snprintf(cfg[FEATURED_MASK_SETTING],512", SOURCE)
        self.assertIn("snprintf(cfg[TRAY_MASK_SETTING],512", SOURCE)
        self.assertIn("G_CALLBACK(tray_order_move)", SETTINGS)
        self.assertIn("gtk_list_box_get_row_at_index(GTK_LIST_BOX(order_list),n)", SOURCE)
        self.assertIn("gtk_menu_item_new_with_label(caption)", SOURCE)
        self.assertNotIn("else if(action==8)on_bruiser_ai(NULL,NULL);", SOURCE)
        self.assertNotIn("static void tray_order_load(", SOURCE)

    def test_old_layout_and_config_migrate_safely(self):
        self.assertIn("#define CONFIG_COUNT 17", CONFIG_HEADER)
        self.assertIn("#define FEATURED_MASK_SETTING 15", CONFIG_HEADER)
        self.assertIn("#define NEW_INSTALL_FEATURED_MASK 207u", SOURCE)
        self.assertIn("#define EXISTING_INSTALL_FEATURED_MASK 255u", CONFIG_HEADER)
        self.assertIn("if (!has_featured)", CONFIG_SOURCE)
        self.assertIn('"ai_url", "featured_actions", "web_gaming_url"', CONFIG_SOURCE)
        self.assertIn('"", "", "255", "", "207", ""', CONFIG_SOURCE)
        self.assertIn("last_columns=-1;", SOURCE)

    def test_ai_url_and_admin_are_optional(self):
        self.assertIn("if(*cfg[14]){", SOURCE)
        self.assertIn("if(!now_safe_preset_url(cfg[14]))return 0;", SOURCE)
        self.assertIn('snprintf(base,sizeof base,"http://%s:3000",cfg[0]);', SOURCE)
        self.assertIn('snprintf(out,cap,"%s/admin/settings",base);', SOURCE)
        self.assertIn("browser_open(url);", SOURCE)
        self.assertNotIn('button("BRUISER AI ADMIN","setupaction")', SOURCE)
        self.assertNotIn('"WEB GAMING","BRUISER AI"}', SOURCE)
        self.assertIn('button("STREAMING SETUP (MOONLIGHT + WOLF)","setupaction")', SETTINGS)
        self.assertIn('label("UPDATES & MAINTENANCE","modalheading")', SETTINGS)
        self.assertNotIn("bruiser.monumentrisk.com", SOURCE)

    def test_old_connection_preset_remains_importable(self):
        self.assertIn("#define PRESET_COUNT 11", PRESET_SOURCE)
        self.assertIn("7,10,14,16}", PRESET_SOURCE)
        self.assertIn("PRESET_HEADER_V2", PRESET_SOURCE)
        self.assertIn("PRESET_HEADER_V1", PRESET_SOURCE)
        self.assertIn("if(c->preset_loaded){", SOURCE)
        for index in (10, 14, 16):
            self.assertIn(f"safe_copy(cfg[{index}],512,c->staged[{index}]);", SOURCE)
        self.assertIn("if(*line && *line!='#')", PRESET_SOURCE)
        self.assertIn("if(!now_safe_preset_url(v[14])||!now_safe_preset_url(v[16]))return 0;", PRESET_SOURCE)


if __name__ == "__main__":
    unittest.main()
