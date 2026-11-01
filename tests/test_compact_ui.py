"""Small-screen layout contracts for the GTK Dashboard, Videos and Settings.

Structural guards complement native GTK tests; do not claim a real host test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/main.c").read_text(encoding="utf-8")
SETTINGS = (ROOT / "src/ui_settings.c").read_text(encoding="utf-8")
GAMES = (ROOT / "src/ui_games.c").read_text(encoding="utf-8")


class CompactUiTests(unittest.TestCase):
    def test_video_launch_matches_steam_tile(self):
        self.assertIn('gtk_widget_set_name(play,"tile");', GAMES)
        self.assertIn('gtk_widget_set_size_request(play,-1,56);', GAMES)
        self.assertIn('video_browser=button("OPEN VIDEO LIBRARY  ↗","tile")', MAIN)
        self.assertIn('gtk_widget_set_size_request(video_browser,-1,56)', MAIN)
        self.assertNotIn('gtk_style_context_add_class(gtk_widget_get_style_context(video_browser),"now-primary")', MAIN)
        self.assertIn('G_CALLBACK(videos_open_browser)', MAIN)

    def test_hidden_pages_and_cap_do_not_force_full_width(self):
        self.assertIn('gtk_stack_set_hhomogeneous(GTK_STACK(main_pages),FALSE)', MAIN)
        self.assertIn('gtk_stack_set_hhomogeneous(GTK_STACK(stack),FALSE)', SETTINGS)
        self.assertIn('gtk_label_set_ellipsize(GTK_LABEL(metric_gpu),PANGO_ELLIPSIZE_END)', MAIN)
        self.assertIn('  ·  cap %s', MAIN)

    def test_two_column_dashboard_metrics_and_power_reflow(self):
        self.assertIn('int metric_cols=width>=720?3:2;', MAIN)
        self.assertIn('int pcols=width>=560?4:2;', MAIN)
        self.assertIn('gtk_grid_attach(GTK_GRID(metrics),storage,0,2,2,1)', MAIN)
        self.assertIn('gtk_grid_attach(GTK_GRID(metrics),storage,2,0,1,2)', MAIN)
        self.assertIn('g_object_ref(storage)', MAIN)
        self.assertIn('g_object_unref(storage)', MAIN)
        self.assertIn('gtk_grid_attach(GTK_GRID(power_grid),powers[i],i%pcols,i/pcols,1,1)', MAIN)

    def test_settings_home_uses_balanced_responsive_navigation_tiles(self):
        self.assertIn('gtk_flow_box_set_min_children_per_line(GTK_FLOW_BOX(menu),1)', SETTINGS)
        self.assertIn('gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(menu),2)', SETTINGS)
        self.assertIn('gtk_flow_box_set_homogeneous(GTK_FLOW_BOX(menu),TRUE)', SETTINGS)
        self.assertIn('settings_menu_button(home_menu,"OTHER APPS  ›")', SETTINGS)
        self.assertIn('settings_menu_button(home_menu,"SYSTEM INFO  ›")', SETTINGS)
        self.assertIn('settings_menu_link(home_menu,stack,"HOST GPU  ›","gpu")', SETTINGS)
        self.assertIn('settings_menu_link(home_menu,stack,"CONNECTIONS & SERVER  ›","connection")', SETTINGS)
        self.assertIn('"#settingscard {background:#222724', MAIN)
        self.assertIn('gtk_widget_set_halign(b,GTK_ALIGN_FILL)', SETTINGS)

    def test_downloads_vpn_is_on_own_row_at_minimum_width(self):
        flow = (ROOT / "src" / "downloads_flow.c").read_text(encoding="utf-8")
        self.assertIn('GtkWidget *toolbar=gtk_box_new(GTK_ORIENTATION_VERTICAL,6)', flow)
        self.assertIn('gtk_box_pack_end(GTK_BOX(status_row),vpn_button,FALSE,FALSE,0)', flow)
        self.assertIn('gtk_box_pack_start(GTK_BOX(status_row),title,TRUE,TRUE,0)', flow)
        for action in ("refresh", "advanced_button", "back_button"):
            self.assertIn(f'gtk_box_pack_start(GTK_BOX(actions_row),{action},FALSE,FALSE,0)',flow)
            self.assertNotIn(f'gtk_box_pack_start(GTK_BOX(toolbar),{action},FALSE,FALSE,0)',flow)
        self.assertIn('g_signal_connect(vpn_button,"clicked",G_CALLBACK(on_vpn_clicked),NULL)',flow)
        self.assertIn('g_signal_connect(advanced_button,"clicked",G_CALLBACK(show_web),NULL)',flow)
        self.assertIn('g_signal_connect(back_button,"clicked",G_CALLBACK(show_queue),NULL)',flow)

    def test_settings_actions_use_natural_width(self):
        self.assertIn('gtk_widget_set_halign(b,GTK_ALIGN_START)', SETTINGS)
        self.assertIn('!strcmp(id,"setupaction")', SETTINGS)
        self.assertIn('!strcmp(id,"navback")', SETTINGS)
        self.assertIn('gtk_label_set_line_wrap(GTK_LABEL(l),TRUE)', SETTINGS)
        self.assertIn('gtk_label_set_max_width_chars(GTK_LABEL(l),48)', SETTINGS)


if __name__ == "__main__":
    unittest.main()
