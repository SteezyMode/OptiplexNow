"""Keep the managed Games workflow integrated with the compact main-window UI.

This only asserts structural wiring. Real client + host behavior requires the
physical acceptance checklist in issue #154. Not a claim of P0 readiness.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "main.c").read_text(encoding="utf-8")
MAKE = (ROOT / "Makefile").read_text(encoding="utf-8")


class CombinedGamesUITests(unittest.TestCase):
    def test_one_window_navigation_and_managed_games_button(self):
        self.assertIn('GtkWidget*back=button("‹ DASHBOARD","navback");', SOURCE)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),settings_view,"settings");', SOURCE)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),software_scroll,"software");', SOURCE)
        self.assertIn('static void launch_steam(void){managed_games_begin(FALSE,FALSE);}', SOURCE)
        self.assertNotIn('static void launch_steam(void){launch_wolf_app("Steam");}', SOURCE)
        self.assertIn('now_games_request_async(helper,action,managed_games.host,', SOURCE)
        self.assertIn('managed_games_open_wolf_ui()', SOURCE)
        self.assertIn('static void managed_games_observed(', SOURCE)
        self.assertIn('managed_games_reconcile_after_exit', SOURCE)

    def test_restricted_transport_compiled_and_tested(self):
        self.assertIn('src/games_flow.c', MAKE)
        self.assertIn('check-games-flow:', MAKE)
        self.assertIn('check-games-flow', (ROOT / ".github/workflows/ci.yml").read_text())
        self.assertTrue((ROOT / "src/owner-games-client.py").exists())
        self.assertTrue((ROOT / "server/owner_games_ssh.py").exists())

    def test_no_extra_settings_dialog_on_navigation(self):
        section = SOURCE.split("static void on_settings(void*w,void*p){",1)[1].split(
            "/* Setup assistant.",1)[0]
        self.assertNotIn('gtk_dialog_new_with_buttons("OptiPlex Now | Settings"',section)
        self.assertIn('g_signal_connect(save,"clicked",G_CALLBACK(settings_save),form)',section)
        self.assertIn('g_signal_connect(cancel,"clicked",G_CALLBACK(settings_discard),NULL)',section)


if __name__ == "__main__":
    unittest.main()
