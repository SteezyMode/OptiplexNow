"""Source-level identity safeguards for the GTK visual-coherence pass.

A real Xvfb/UI run and human screenshot review remain separate gates.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/main.c").read_text(encoding="utf-8")
APP_CSS = (ROOT / "src/ui_theme.c").read_text(encoding="utf-8")
THEME = (ROOT / "src/now-theme.css").read_text(encoding="utf-8")
GAMES = (ROOT / "src/ui_games.c").read_text(encoding="utf-8")


class VisualCoherenceTests(unittest.TestCase):
    def test_single_warm_hover_accent_and_qualified_health_status(self):
        self.assertNotIn("#2a9d8f", APP_CSS, "Teal must not be a generic action hover")
        for name in ("#setupaction:hover", "assistant button:hover",
                     "dialog .dialog-action-area button:hover", "menuitem:hover"):
            self.assertIn(name, APP_CSS)
        self.assertIn("background:#39302c;color:#ece8e0", APP_CSS)
        self.assertIn("border-color:#c47d65", APP_CSS)
        self.assertIn("#84d9a7", APP_CSS)  # Positive telemetry remains separate
        self.assertIn("#9d3543", APP_CSS)  # Destructive hover remains separate
        self.assertIn("VPN: UNVERIFIED", MAIN)

    def test_child_labels_keep_contrast_on_colored_action_states(self):
        for selector in (
            "#navtab.active label", "#navtab:hover label",
            "#navback:hover label", "#tile:hover label",
            "#tile:active label", "#power:hover label",
            "#downloadsubtab.active label", "#downloadconfirm label",
            "#danger:hover label", "#setting:hover label",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, APP_CSS)
        self.assertIn("#danger:hover label {color:#fafaf8;}", APP_CSS)
        self.assertIn("#tile:hover label,#tile:active label {color:#101111;}", APP_CSS)

    def test_focus_states_and_balanced_type(self):
        self.assertIn("#navtab:focus", APP_CSS)
        self.assertIn("#tile:focus", APP_CSS)
        self.assertIn("#setupaction:focus", APP_CSS)
        self.assertIn("font-size:28px;font-weight:900", APP_CSS)
        self.assertIn("#modalheading {font-size:16px", APP_CSS)
        self.assertIn("font-size:11px", THEME)

    def test_gpu_power_window_uses_same_dark_theme_as_other_dialogs(self):
        power = (ROOT / "src/gpu-power-ui.py").read_text(encoding="utf-8")
        approvals = (ROOT / "src/owner-approvals-ui.py").read_text(encoding="utf-8")
        for source in (power, approvals):
            self.assertIn("from now_theme import install as install_theme", source)
            self.assertIn("install_theme()", source)
        self.assertIn("Gtk.init([])", power)
        self.assertIn("PowerWindow(*argv)", power)

    def test_existing_primary_tiles_and_no_new_host_actions(self):
        self.assertIn('gtk_widget_set_name(play,"tile");', GAMES)
        self.assertIn('video_browser=button("OPEN VIDEO LIBRARY  ↗","tile")', MAIN)
        self.assertIn('gtk_widget_set_size_request(video_browser,-1,56);', MAIN)
        self.assertIn('gtk_event_box_set_visible_window(GTK_EVENT_BOX(gpu_hitbox),FALSE);', MAIN)
        self.assertIn('int pcols=width>=560?3:2;', MAIN)


if __name__ == "__main__":
    unittest.main()
