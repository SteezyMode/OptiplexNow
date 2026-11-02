"""Optional Music contract: nav availability, fail-safe fallback and host isolation.

These checks are static/contract-only, not a real slskd or phone acceptance test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src" / "main.c").read_text(encoding="utf-8")
COMPOSE = (ROOT / "deploy" / "music" / "compose.yaml").read_text(encoding="utf-8")
README = (ROOT / "deploy" / "music" / "README.md").read_text(encoding="utf-8")


class OptionalMusicContract(unittest.TestCase):
    def test_music_is_a_real_top_level_page(self):
        self.assertIn('GtkWidget*music_tab=button("MUSIC","navtab");', MAIN)
        self.assertIn('now_nav_mark_tab(music_tab,"music");', MAIN)
        self.assertIn('G_CALLBACK(on_music_tab)', MAIN)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),music_home,"music");', MAIN)
        self.assertIn('GtkWidget*music_browser=button("DISCOVER MUSIC  ↗","tile");', MAIN)
        self.assertIn('G_CALLBACK(music_open_browser)', MAIN)

    def test_existing_dashboard_music_action_opens_the_new_tab(self):
        self.assertIn('else if(n==2)on_music_tab(NULL,NULL);', MAIN)
        self.assertIn('on_music_tab(GtkWidget*w,gpointer data)', MAIN)
        self.assertIn('now_nav_show_page(main_pages,"music");', MAIN)
        self.assertIn('now_safe_preset_url(cfg[6])', MAIN)
        self.assertIn('browser_open(cfg[6]);', MAIN)
        self.assertIn('if(!*cfg[6] || !now_safe_preset_url(cfg[6]))', MAIN)

    def test_services_are_optional_and_not_publicly_listening(self):
        self.assertIn('127.0.0.1:8688:8688', COMPOSE)
        self.assertIn('127.0.0.1:5030:5030', COMPOSE)
        self.assertIn('droppedneedle/droppedneedle:v2.15.0', COMPOSE)
        self.assertIn('slskd/slskd:0.26.2', COMPOSE)
        self.assertNotIn('Funnel', COMPOSE)
        self.assertNotIn('docker compose up', MAIN)
        self.assertIn('not installed or alpha-accepted', README)
        self.assertIn('Private Alpha 1', README)

    def test_complete_common_parent_mappings(self):
        self.assertEqual(COMPOSE.count('MUSIC_MEDIA_ROOT:?Set MUSIC_MEDIA_ROOT'), 2)
        self.assertIn('/data/slskd/complete', COMPOSE)
        for part in ('/slskd:/app', '/droppedneedle/config:/app/config',
                     '/droppedneedle/cache:/app/cache',
                     '/droppedneedle/plugins:/app/plugins'):
            self.assertIn(part, COMPOSE)


if __name__ == "__main__":
    unittest.main()
