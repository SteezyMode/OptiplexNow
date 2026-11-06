"""Keep native Videos and Downloads buttons in NOW's shared dark theme.

The GTK smoke tests exercise rendering and startup; these static assertions
guard against introducing more unstyled stock-white GTK buttons.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class NativeActionThemeTests(unittest.TestCase):
    def test_shared_theme_has_contrast_and_interaction_states(self):
        css = (SRC / "ui_theme.c").read_text()
        for selector in (
            "button.now-action {background:#222724;color:#ece8e0",
            "button.now-action:hover",
            "button.now-action:focus",
            "button.now-action:active",
            "button.now-action:disabled",
            "button.now-action label",
            "button.now-action.now-primary {background:#c47d65;color:#101111",
            "button.now-action.now-primary:disabled",
            "button.now-action.now-sort {background:#1e2320",
        ):
            self.assertIn(selector, css)

    def test_video_launch_matches_steam_dark_tile(self):
        src = (SRC / "main.c").read_text()
        games = (SRC / "ui_games.c").read_text()
        self.assertIn('video_browser=button("OPEN VIDEO LIBRARY  ↗","tile")', src)
        self.assertIn('gtk_widget_set_size_request(video_browser,-1,56)', src)
        self.assertIn('gtk_widget_set_name(play,"tile")', games)
        self.assertIn('gtk_widget_set_size_request(play,-1,56)', games)
        self.assertIn('"#tile {background:#1e211f', (SRC / "ui_theme.c").read_text())
        self.assertIn('"#tile:hover {background:#b96b5e', (SRC / "ui_theme.c").read_text())
        self.assertNotIn('gtk_style_context_add_class(gtk_widget_get_style_context(video_browser),"now-primary")', src)

    def test_downloads_toolbar_search_and_queue(self):
        checks = {
            "downloads_flow.c": ("refresh", "advanced_button", "back_button"),
            "downloads_search_view.c": ("s->button", "button"),
            "downloads_destination_view.c": ("s->up", "s->add", "s->new_folder", "s->pin_place"),
        }
        for file, widgets in checks.items():
            src = (SRC / file).read_text()
            for widget in widgets:
                with self.subTest(file=file, widget=widget):
                    self.assertIn(
                        'gtk_style_context_add_class(gtk_widget_get_style_context('
                        + widget + '),"now-action");',
                        src)
        queue = (SRC / "downloads_queue_view.c").read_text()
        self.assertIn("gtk_menu_popup_at_pointer",queue)
        self.assertNotIn("gtk_expander_new",queue)
        destination = (SRC / "downloads_destination_view.c").read_text()
        # Folder *rows* deliberately use the native flat treatment, not
        # large action-button styling. This resembles a normal file browser.
        self.assertIn(
            'gtk_style_context_add_class(gtk_widget_get_style_context(button),"flat");',
            destination)
        self.assertIn('g_object_set(folder_icon,"icon-name","folder"', destination)
        search = (SRC / "downloads_search_view.c").read_text()
        self.assertIn(
            'gtk_style_context_add_class(gtk_widget_get_style_context(button),"now-sort");',
            search)
        self.assertIn(
            'gtk_style_context_add_class(gtk_widget_get_style_context(s->button),"now-primary");',
            search)


if __name__ == "__main__":
    unittest.main()
