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
        self.assertIn('GtkWidget*music_home=now_music_build(browser_open,on_settings,music_tray_changed);', MAIN)
        self.assertIn('gtk_list_box_insert(GTK_LIST_BOX(view->list),row,-1);', UI_MUSIC)
        self.assertIn('g_subprocess_communicate_utf8_async', UI_MUSIC)
        self.assertIn('music_advanced', UI_MUSIC)
        self.assertIn('Advanced · DroppedNeedle', UI_MUSIC)

    def test_existing_dashboard_music_action_opens_the_new_tab(self):
        self.assertIn('else if(n==2)on_music_tab(NULL,NULL);', MAIN)
        self.assertIn('on_music_tab(GtkWidget*w,gpointer data)', MAIN)
        self.assertIn('now_nav_show_page(main_pages,"music");', MAIN)
        self.assertIn('query_start(view,"home",NULL,"Music Home");', UI_MUSIC)
        self.assertIn('view->open_url(cfg[6])', UI_MUSIC)
        self.assertIn('wipe_free(view->app_password);', UI_MUSIC)
        self.assertIn('g_strcmp0(view->bound_url,cfg[6])', UI_MUSIC)
        self.assertIn('view->bound_url=g_strdup(cfg[6]);', UI_MUSIC)
        self.assertIn('G_SUBPROCESS_FLAGS_STDERR_SILENCE', UI_MUSIC)
        self.assertIn("music_start_track(view,selected);", UI_MUSIC)
        self.assertIn("now_music_playback_start(view->playback", UI_MUSIC)
        self.assertIn("gtk_widget_set_no_show_all(view->player_bar,TRUE);", UI_MUSIC)
        self.assertIn('now_music_is_playing_session()', MAIN)
        self.assertIn('now_music_is_paused()?"Resume music":"Pause music"', MAIN)
        self.assertIn('now_music_can_next()', MAIN)
        self.assertIn('G_CALLBACK(tray_music_previous)', MAIN)
        self.assertIn('G_CALLBACK(tray_music_pause)', MAIN)
        self.assertIn('G_CALLBACK(tray_music_next)', MAIN)
        self.assertIn('shutil.copy2(root/' + "'src/music_player.py'", (ROOT / "package.py").read_text())
        self.assertIn('mpv, gnome-keyring', (ROOT / "package.py").read_text())
        self.assertIn('music_vault_begin(view,"lookup",NULL)', UI_MUSIC)
        self.assertIn('music_vault_begin(view,"store",form)', UI_MUSIC)
        self.assertIn('music_vault_begin(view,"clear",NULL)', UI_MUSIC)
        self.assertIn('view->remember_pending=TRUE;', UI_MUSIC)
        self.assertIn('g_signal_connect(view->root,"map",G_CALLBACK(music_opened),view)', UI_MUSIC)
        self.assertIn('if(view->vault_attempted_url &&', UI_MUSIC)
        self.assertIn('g_strcmp0(view->bound_url,cfg[6])', UI_MUSIC)
        self.assertIn('gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),FALSE)', UI_MUSIC)
        helper = (ROOT / 'src/music_keyring.py').read_text(encoding='utf-8')
        self.assertIn('Secret.password_store_sync', helper)
        self.assertIn('Secret.password_lookup_sync', helper)
        self.assertIn('Secret.password_clear_sync', helper)
        self.assertNotIn('open(",w")', helper)
        package = (ROOT / 'package.py').read_text(encoding='utf-8')
        self.assertIn('gir1.2-secret-1', package)
        self.assertIn("music_keyring.py", package)

    def test_real_music_feeds_and_private_cover_art_in_ui(self):
        transport = (ROOT / "src/music_subsonic.py").read_text(encoding="utf-8")
        for kind in ('"home"', '"albums"', '"recent"', '"new"', '"liked"',
                     '"artists"', '"playlists"'):
            self.assertIn(kind, UI_MUSIC)
        self.assertIn('"getStarred2"', transport)
        self.assertIn('"getAlbumList2"', transport)
        self.assertIn('"newest"', transport)
        self.assertIn('if args.operation == "home" and not albums:', transport)
        self.assertIn('music_show_empty(view,job->operation)', UI_MUSIC)
        self.assertIn('view->hero_play=music_button("Play");', UI_MUSIC)
        self.assertIn('music_play_visible(data,0);', UI_MUSIC)
        self.assertIn('"getCoverArt"', transport)
        self.assertIn('"image/jpeg", "image/png", "image/webp"', transport)
        self.assertIn('MAX_COVER = 3 * 1024 * 1024', transport)
        self.assertIn('g_subprocess_communicate_async(proc,sent,job->cancel,', UI_MUSIC)
        self.assertIn('gdk_pixbuf_loader_set_size(loader,pixels,pixels);', UI_MUSIC)
        self.assertIn('g_strcmp0(job->server_url,cfg[6])==0', UI_MUSIC)
        self.assertIn('gtk_widget_set_no_show_all(view->hero_row,TRUE);', UI_MUSIC)
        self.assertIn('music_art_start(view,song->cover_id,TRUE);', UI_MUSIC)
        self.assertIn('G_CALLBACK(music_advanced)', UI_MUSIC)
        self.assertNotIn('getCoverArt?id=', UI_MUSIC)

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
