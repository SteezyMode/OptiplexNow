"""Source regression checks for optional services and retained client settings.

The GTK build, packaging checks and live GUI smoke tests are separate requirements.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "main.c").read_text()
PRESET_SOURCE = (ROOT / "src" / "presets.c").read_text()
CONFIG_SOURCE = (ROOT / "src" / "config.c").read_text()
CONFIG_HEADER = (ROOT / "src" / "config.h").read_text()


class OptionalServiceTests(unittest.TestCase):
    def test_service_tiles_have_a_single_home(self):
        self.assertIn("static GtkWidget *tiles[9]", SOURCE)
        self.assertIn('gtk_expander_new("ADDITIONAL SERVICES")', SOURCE)
        self.assertIn("gtk_grid_attach(GTK_GRID(chosen?grid:extras_grid),tiles[i]", SOURCE)
        self.assertIn("unsigned featured=featured_mask();int primary=0,other=0;", SOURCE)
        self.assertIn("for(int i=0;i<8;i++){tiles[i]=button(names[i]", SOURCE)

    def test_primary_and_tray_are_independently_selected(self):
        self.assertIn("#define TRAY_ALL_BUTTONS 255u", SOURCE)
        self.assertIn("#define TRAY_DEFAULT_BUTTONS 255u", SOURCE)
        self.assertIn("GtkWidget*featured_checks[8],*tray_checks[8]", SOURCE)
        self.assertIn('const char*head_names[]={"SERVICE","PRIMARY","TRAY","MOVE"};', SOURCE)
        self.assertIn("gtk_label_set_xalign(GTK_LABEL(heading),h==0?0.0f:0.5f);", SOURCE)
        self.assertIn("gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(featured_checks[i]))", SOURCE)
        self.assertIn("gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(tray_checks[i]))", SOURCE)
        self.assertIn("snprintf(cfg[FEATURED_MASK_SETTING],512", SOURCE)
        self.assertIn("snprintf(cfg[TRAY_MASK_SETTING],512", SOURCE)
        self.assertIn("int order[8];tray_order_load(order);", SOURCE)
        self.assertIn("if(!(mask & (1u<<i)))continue;", SOURCE)
        self.assertIn("tray_order_save(ordered);", SOURCE)
        self.assertIn("G_CALLBACK(tray_order_move)", SOURCE)
        self.assertIn("gtk_list_box_get_row_at_index(GTK_LIST_BOX(order_list),n)", SOURCE)
        self.assertIn("gtk_list_box_insert(GTK_LIST_BOX(order_list),row,-1)", SOURCE)
        self.assertIn("gtk_menu_item_new_with_label(caption)", SOURCE)
        self.assertIn('snprintf(caption,sizeof caption,"%s — %s",names[i],i==6?desktop:descriptions[i]);', SOURCE)
        self.assertNotIn("else if(action==8)on_bruiser_ai(NULL,NULL);", SOURCE)

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
        self.assertIn('button("STREAMING SETUP (MOONLIGHT + WOLF)","setupaction")', SOURCE)
        self.assertIn('label("UPDATES & MAINTENANCE","modalheading")', SOURCE)
        self.assertNotIn("bruiser.monumentrisk.com", SOURCE)

    def test_old_connection_preset_remains_importable(self):
        self.assertIn("#define PRESET_COUNT 11", PRESET_SOURCE)
        self.assertIn("7,10,14,16}", PRESET_SOURCE)
        self.assertIn("PRESET_HEADER_V2", PRESET_SOURCE)
        self.assertIn("PRESET_HEADER_V1", PRESET_SOURCE)
        self.assertIn("if(c->preset_loaded){safe_copy(cfg[10],512,c->staged[10]);safe_copy(cfg[14],512,c->staged[14]);safe_copy(cfg[16],512,c->staged[16]);}", SOURCE)
        self.assertIn("if(*line && *line!='#')", PRESET_SOURCE)
        self.assertIn("if(!now_safe_preset_url(v[14])||!now_safe_preset_url(v[16]))return 0;", PRESET_SOURCE)


if __name__ == "__main__":
    unittest.main()
