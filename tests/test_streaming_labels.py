"""Ensure UI names reflect streaming beyond gaming without changing routes."""
from pathlib import Path
import unittest


MAIN = (Path(__file__).resolve().parents[1] / "src" / "main.c").read_text()


class StreamingLabelTests(unittest.TestCase):
    def test_studio_desktop_tray_label_matches_existing_wolf_stream(self):
        self.assertIn('"Desktop  |  Studio"', MAIN)
        self.assertNotIn('"Desktop  |  XFCE"', MAIN)
        self.assertIn('static void launch_desktop(void){launch_wolf_app("OptiPlex Studio Desktop");}', MAIN)

    def test_moonlight_setup_is_generic_streaming_settings(self):
        self.assertIn('button("STREAMING SETTINGS","setupaction")', MAIN)
        self.assertIn('gtk_dialog_new_with_buttons("Streaming Settings"', MAIN)
        self.assertNotIn('button("GAMES SETUP","setupaction")', MAIN)
        self.assertIn('Moonlight streams games and desktops.', MAIN)
        self.assertIn('Save your work before continuing.', MAIN)

    def test_game_specific_shortcut_remains_game_specific(self):
        self.assertIn('static void launch_steam(void){launch_wolf_app("Steam");}', MAIN)
        self.assertIn('"Games  |  Steam"', MAIN)


if __name__ == "__main__":
    unittest.main()
