"""Regression checks for the single-dialog Settings navigation.

Native GTK compilation, install smoke tests and manual low-resolution UI checks
remain separate requirements.
"""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "src" / "main.c").read_text(encoding="utf-8")


class SettingsNavigationTests(unittest.TestCase):
    def test_one_dialog_and_internal_categories(self):
        section = SOURCE.split("static void on_settings(void*w,void*p)", 1)[1].split("/* Setup assistant.", 1)[0]
        self.assertEqual(section.count('gtk_dialog_new_with_buttons("OptiPlex Now | Settings"'), 1)
        self.assertIn('GtkWidget*stack=gtk_stack_new();', section)
        for category in ("gaming", "preferences", "connection"):
            self.assertIn(f'settings_page(stack,"{category}")', section)
        self.assertIn('settings_link(pages[k],stack,"‹ BACK TO SETTINGS","home")', section)
        self.assertIn('gtk_stack_set_visible_child_name(GTK_STACK(stack),"home");', section)

    def test_default_size_and_scrollable_pages(self):
        self.assertIn('gtk_window_set_default_size(GTK_WINDOW(d),680,550);', SOURCE)
        self.assertIn('gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC)', SOURCE)

    def test_existing_save_path_and_admin_actions(self):
        section = SOURCE.split("static void on_settings(void*w,void*p)", 1)[1].split("/* Setup assistant.", 1)[0]
        for expected in ('gtk_dialog_run(GTK_DIALOG(d))', 'if(resp==GTK_RESPONSE_OK)', 'config_save();tray_build_menu();',
                         'on_web_gaming_admin', 'on_web_gaming_settings', 'on_games_setup_from_settings'):
            self.assertIn(expected, section)


if __name__ == "__main__":
    unittest.main()
