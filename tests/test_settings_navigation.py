"""Regression checks for compact single-window GTK main navigation.

Native GTK compilation, install smoke tests and physical low-resolution
interaction checks are separate requirements.
"""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "src" / "main.c").read_text(encoding="utf-8")


class SettingsNavigationTests(unittest.TestCase):
    def test_settings_reuses_main_stack_and_categories(self):
        section = SOURCE.split("static void on_settings(void*w,void*p){", 1)[1].split(
            "/* Setup assistant.", 1)[0]
        self.assertNotIn('gtk_dialog_new_with_buttons("OptiPlex Now | Settings"', section)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),settings_view,"settings")', section)
        self.assertIn('GtkWidget*stack=gtk_stack_new();', section)
        for category in ("gaming", "preferences", "connection"):
            self.assertIn(f'settings_page(stack,"{category}")', section)
        self.assertIn('settings_link(pages[k],stack,"‹ BACK TO SETTINGS","home")', section)
        self.assertIn('gtk_stack_set_visible_child_name(GTK_STACK(stack),"home");', section)
        self.assertIn('gtk_widget_show_all(settings_view);', section)

    def test_compact_initial_width_and_independent_scrolling(self):
        self.assertIn('int initial_width=640;', SOURCE)
        self.assertIn('int initial_height=500;', SOURCE)
        self.assertIn('now_ui_state_window_size(&initial_width,&initial_height);', SOURCE)
        self.assertIn('initial_width=MIN(initial_width,MAX(400,workarea.width-64));', SOURCE)
        self.assertIn('initial_height=MIN(initial_height,MAX(340,workarea.height-100));', SOURCE)
        self.assertIn('g_signal_connect(win,"configure-event",G_CALLBACK(on_window_configure),NULL);', SOURCE)
        self.assertIn('gtk_window_set_resizable(GTK_WINDOW(win),TRUE);', SOURCE)
        self.assertIn('gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC)', SOURCE)
        self.assertIn('gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(settings_view),', SOURCE)
        self.assertIn('gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(dash_scroll),', SOURCE)

    def test_software_dashboard_info_and_settings_share_one_stack(self):
        self.assertIn('gtk_container_add(GTK_CONTAINER(win),window_root);', SOURCE)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),dash_scroll,"dashboard");', SOURCE)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),software_scroll,"software");', SOURCE)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),info_view,"info");', SOURCE)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),settings_view,"settings");', SOURCE)
        self.assertIn('GtkWidget*dashboard_tab=button("DASHBOARD","navtab");', SOURCE)
        self.assertIn('now_nav_mark_tab(dashboard_tab,"dashboard");', SOURCE)
        self.assertNotIn('GtkWidget*back=button("‹ DASHBOARD","navback");', SOURCE)
        self.assertIn('g_signal_connect(main_pages,"notify::visible-child"', SOURCE)
        self.assertNotIn('settings_link(software,main_pages,"‹ DASHBOARD","dashboard")', SOURCE)
        self.assertIn('add(software,grid,0);', SOURCE)
        self.assertIn('add(software,extras,0);', SOURCE)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),games_page,"games");', SOURCE)
        self.assertIn('now_nav_bind_link(other_apps,main_pages,"software");', SOURCE)
        self.assertIn('now_nav_bind_link(games_tab,main_pages,"games");', SOURCE)
        self.assertIn('g_signal_connect(videos_tab,"clicked",G_CALLBACK(on_videos_tab),NULL);', SOURCE)
        self.assertNotIn('button("SOFTWARE","navtab")', SOURCE)

    def test_settings_save_cancel_and_pair_callbacks_have_valid_lifetimes(self):
        self.assertIn('PairContext server_context, relay_context;', SOURCE)
        self.assertIn('PresetExportContext export_context;', SOURCE)
        self.assertIn('g_object_set_data_full(G_OBJECT(settings_view),"now-settings-form",form,g_free)', SOURCE)
        self.assertIn('g_signal_connect(save,"clicked",G_CALLBACK(settings_save),form);', SOURCE)
        self.assertIn('g_signal_connect(cancel,"clicked",G_CALLBACK(settings_discard),NULL);', SOURCE)
        self.assertIn('config_save();', SOURCE)
        self.assertIn('g_timeout_add(200,tray_rebuild_after_settings,NULL);', SOURCE)
        self.assertIn('on_web_gaming_admin', SOURCE)
        self.assertIn('on_web_gaming_settings', SOURCE)
        self.assertIn('on_games_setup_from_settings', SOURCE)
        self.assertIn('if(settings_view)settings_discard(NULL,NULL);', SOURCE)
        self.assertNotIn('gtk_dialog_run(GTK_DIALOG(d));\n if(resp==GTK_RESPONSE_OK)', SOURCE)


if __name__ == "__main__":
    unittest.main()
