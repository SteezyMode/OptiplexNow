"""Optional Music contract: nav availability, fail-safe fallback and host isolation.

These checks are static/contract-only, not a real slskd or phone acceptance test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src" / "main.c").read_text(encoding="utf-8")
COMPOSE = (ROOT / "deploy" / "music" / "compose.yaml").read_text(encoding="utf-8")
README = (ROOT / "deploy" / "music" / "README.md").read_text(encoding="utf-8")
UI_MUSIC = (ROOT / "src" / "ui_music.c").read_text(encoding="utf-8")


class OptionalMusicContract(unittest.TestCase):
    def test_music_is_a_real_top_level_page(self):
        self.assertIn('GtkWidget*music_tab=button("MUSIC","navtab");', MAIN)
        self.assertIn('now_nav_mark_tab(music_tab,"music");', MAIN)
        self.assertIn('G_CALLBACK(on_music_tab)', MAIN)
        self.assertIn('gtk_stack_add_named(GTK_STACK(main_pages),music_home,"music");', MAIN)
        self.assertIn('GtkWidget*music_home=now_music_build(browser_open,on_settings);', MAIN)
        self.assertIn('gtk_list_box_insert(GTK_LIST_BOX(view->list),row,-1);', UI_MUSIC)
        self.assertIn('g_subprocess_communicate_utf8_async', UI_MUSIC)
        self.assertIn('music_advanced', UI_MUSIC)
        self.assertIn('Advanced · DroppedNeedle', UI_MUSIC)

    def test_existing_dashboard_music_action_opens_the_new_tab(self):
        self.assertIn('else if(n==2)on_music_tab(NULL,NULL);', MAIN)
        self.assertIn('on_music_tab(GtkWidget*w,gpointer data)', MAIN)
        self.assertIn('now_nav_show_page(main_pages,"music");', MAIN)
        self.assertIn('query_start(view,"albums",NULL,"Your albums");', UI_MUSIC)
        self.assertIn('view->open_url(cfg[6])', UI_MUSIC)
        self.assertIn('wipe_free(view->app_password);', UI_MUSIC)
        self.assertIn('G_SUBPROCESS_FLAGS_STDERR_SILENCE', UI_MUSIC)

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
