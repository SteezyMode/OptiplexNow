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
        self.assertIn("music_play_visible(view,selected);", UI_MUSIC)
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

    def test_standard_music_navigation_and_advanced_are_separate(self):
        # Match familiar Home, Search, Your Library and player navigation.
        self.assertIn('gtk_label_new(i==3?"YOUR LIBRARY":"BROWSE")', UI_MUSIC)
        self.assertIn('const char *ops[]={"home",NULL,"discover","playlists","artists","albums",', UI_MUSIC)
        self.assertIn('const char *titles[]={"Home","Search","Discover","Playlists","Artists",', UI_MUSIC)
        self.assertIn('G_CALLBACK(music_focus_search)', UI_MUSIC)
        self.assertIn('gtk_widget_grab_focus(view->search);', UI_MUSIC)
        self.assertIn('gtk_menu_button_set_popup(GTK_MENU_BUTTON(advanced),menu);', UI_MUSIC)
        self.assertIn('gtk_menu_item_new_with_label("Advanced · DroppedNeedle")', UI_MUSIC)
        self.assertIn('gtk_menu_item_new_with_label("Forget this device")', UI_MUSIC)
        self.assertNotIn('gtk_box_pack_end(GTK_BOX(sidebar),forget', UI_MUSIC)
        self.assertNotIn('gtk_box_pack_end(GTK_BOX(sidebar),settings', UI_MUSIC)
        self.assertIn('"#music-library-label', MAIN)
        contract = (ROOT / "docs" / "MUSIC-UX.md").read_text(encoding="utf-8")
        self.assertIn("Your Library", contract)
        self.assertIn("Downloads", contract)
        self.assertIn("contextual", contract.lower())

    def test_real_music_feeds_and_private_cover_art_in_ui(self):
        transport = (ROOT / "src/music_subsonic.py").read_text(encoding="utf-8")
        for kind in ('"home"', '"albums"', '"recent"', '"new"', '"liked"',
                     '"artists"', '"playlists"'):
            self.assertIn(kind, UI_MUSIC)
        self.assertIn('gtk_widget_set_name(view->root,"music-home");', UI_MUSIC)
        self.assertIn('gtk_widget_set_name(sidebar,"music-sidebar");', UI_MUSIC)
        self.assertIn('gtk_widget_set_name(view->player_bar,"music-player");', UI_MUSIC)
        self.assertIn('gtk_widget_set_name(view->list,"music-library");', UI_MUSIC)
        self.assertIn('"#music-sidebar button#music-nav.now-action', MAIN)
        self.assertIn('"#music-player {background:', MAIN)
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

    def test_album_pagination_keeps_previous_rows(self):
        self.assertIn("album_offset", UI_MUSIC)
        self.assertIn("job->append_albums", UI_MUSIC)
        self.assertIn("render_rows(view,output,job->append_albums)", UI_MUSIC)
        self.assertIn('music_button("Load more albums")', UI_MUSIC)
        self.assertIn('query_start(view,"albums",value,"All albums")', UI_MUSIC)
        self.assertIn('gtk_widget_set_sensitive(view->load_more,TRUE)', UI_MUSIC)
        transport = (ROOT / "src" / "music_subsonic.py").read_text(encoding="utf-8")
        self.assertIn('ALBUM_PAGE_SIZE = 200', transport)
        self.assertIn('offset % ALBUM_PAGE_SIZE', transport)

    def test_one_time_music_setup_is_compact_and_never_asks_username(self):
        self.assertNotIn('Username (optional)', UI_MUSIC)
        self.assertNotIn('view->user=gtk_entry_new()', UI_MUSIC)
        self.assertNotIn('gtk_entry_get_text(GTK_ENTRY(view->user))', UI_MUSIC)
        self.assertNotIn('Music access key (one-time)', UI_MUSIC)
        self.assertNotIn('not the regular account login password', UI_MUSIC)
        self.assertIn('GtkWidget *connect_button=music_button("Retry Access")', UI_MUSIC)
        self.assertIn('G_CALLBACK(music_retry_access)', UI_MUSIC)
        self.assertIn('gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),FALSE)', UI_MUSIC)
        self.assertIn('gtk_revealer_set_reveal_child(GTK_REVEALER(view->connect_panel),TRUE)', UI_MUSIC)
        self.assertIn('view->username=g_strdup("")', UI_MUSIC)
        self.assertIn('music_vault_begin(view,"lookup",NULL)', UI_MUSIC)

    def test_local_volume_slider_and_backend_contract(self):
        self.assertIn('gtk_scale_new_with_range(GTK_ORIENTATION_HORIZONTAL,0,100,1)', UI_MUSIC)
        self.assertIn('G_CALLBACK(music_volume_changed)', UI_MUSIC)
        self.assertIn('now_music_playback_volume(view->playback,view->volume)', UI_MUSIC)
        self.assertIn('view->volume=75;', UI_MUSIC)
        transport = (ROOT / 'src' / 'music_playback.c').read_text()
        self.assertIn('g_strdup_printf("%d",initial_volume)', transport)

    def test_catalog_search_can_work_before_music_password_setup(self):
        self.assertIn('const gboolean catalog=!g_strcmp0(operation,"catalog") ||',UI_MUSIC)
        self.assertIn('const char *server_url=catalog?cfg[6]:view->bound_url;',UI_MUSIC)
        self.assertIn('job->input=catalog?g_strdup(""):g_strdup_printf(',UI_MUSIC)
        self.assertIn('query_start(view,connected?"search":"catalog",value,',UI_MUSIC)
        self.assertIn('"Searching the music catalog..."',UI_MUSIC)
        self.assertIn('gtk_widget_set_sensitive(button,FALSE);',UI_MUSIC)
        transport=(ROOT/"src"/"music_subsonic.py").read_text(encoding="utf-8")
        self.assertIn('if args.operation == "catalog":',transport)
        self.assertIn('catalog_search(args.base_url',transport)

    def test_discover_is_a_page_not_a_text_query(self):
        self.assertIn('!g_strcmp0(operation,"discover")', UI_MUSIC)
        self.assertIn('!g_strcmp0(operation,"catalog")) &&', UI_MUSIC)
        self.assertIn('(!value || !*value)', UI_MUSIC)
        self.assertIn('g_strdup(""):g_strdup_printf(', UI_MUSIC)
        transport=(ROOT/"src"/"music_subsonic.py").read_text(encoding="utf-8")
        self.assertIn('if args.operation in ("catalog", "discover"):', transport)
        self.assertIn('rest_request(args.base_url, "discover"', transport)

    def test_real_discover_sections_and_request_buttons(self):
        self.assertIn('!strcmp(kind,"section")', UI_MUSIC)
        self.assertIn('gtk_list_box_insert(GTK_LIST_BOX(view->list),heading,-1);', UI_MUSIC)
        self.assertIn('gtk_button_new_with_label("Add to Library")', UI_MUSIC)
        self.assertIn('G_CALLBACK(music_request_album)', UI_MUSIC)
        self.assertIn('g_subprocess_communicate_utf8_async(proc,"",job->cancel', UI_MUSIC)
        self.assertIn('status_set(view,"Album requested.', UI_MUSIC)
        self.assertIn('!g_strcmp0(operation,"discover")', UI_MUSIC)
        self.assertIn('G_CALLBACK(music_seek_changed)', UI_MUSIC)
        self.assertIn('now_music_playback_seek(view->playback,target)', UI_MUSIC)
        self.assertIn('shutil.copy2(root/' + "'src/music_http_stream.py'",(ROOT/"package.py").read_text())
        self.assertIn('shutil.copy2(root/' + "'src/music_rest.py'",(ROOT/"package.py").read_text())

    def test_music_request_status_is_polling_existing_backend_not_duplicated(self):
        self.assertIn('g_timeout_add_seconds(15,music_status_tick,view)', UI_MUSIC)
        self.assertIn('g_hash_table_remove_all(view->album_buttons);', UI_MUSIC)
        self.assertIn('g_hash_table_replace(view->album_buttons,g_strdup(id),request);',
                      UI_MUSIC)
        self.assertIn('music_refresh_status(view);',UI_MUSIC)
        self.assertIn('G_SUBPROCESS_FLAGS_STDERR_SILENCE',UI_MUSIC)
        self.assertIn('gtk_button_set_label(GTK_BUTTON(button),fields[1]);',UI_MUSIC)
        self.assertIn('view->status_inflight=TRUE;', UI_MUSIC)
        transport=(ROOT/"src"/"music_rest.py").read_text()
        self.assertIn('def _download_rows(result:',transport)
        self.assertIn('args.operation=="downloads"',transport)
        self.assertIn('"Downloaded — check library"',transport)

    def test_approved_owner_music_auto_enrollment_is_noninteractive(self):
        self.assertIn('static void music_auto_enroll(MusicView *view)',UI_MUSIC)
        self.assertIn('music_auto_enroll(view);',UI_MUSIC)
        self.assertIn('view->auto_enroll_attempted=TRUE;',UI_MUSIC)
        self.assertIn('view->auto_enroll_busy=TRUE;',UI_MUSIC)
        self.assertIn('G_SUBPROCESS_FLAGS_STDERR_SILENCE',UI_MUSIC)
        self.assertIn('g_strcmp0(job->server_url,cfg[6])==0',UI_MUSIC)
        self.assertIn('music_vault_begin(view,"lookup",NULL);',UI_MUSIC)
        self.assertIn('"Checking approved Music access..."',UI_MUSIC)
        package=(ROOT/"package.py").read_text()
        for helper in ("music_device_client.py","owner_music_ssh.py",
                       "music_device_provision.py","music_device_ledger.py"):
            self.assertIn(helper,package)
        self.assertIn("'wolf-pair-local.py', 'music_subsonic.py'",package)
        ssh=(ROOT/"server"/"owner_games_ssh.py").read_text()
        self.assertIn('request.get("action") == "music_access"',ssh)
        self.assertIn('verified_client_id=verified_client_id',ssh)

    def test_retry_access_after_owner_approval_does_not_force_restart(self):
        self.assertIn('gtk_menu_item_new_with_label("Retry Music Access")',UI_MUSIC)
        self.assertIn('G_CALLBACK(music_retry_access)',UI_MUSIC)
        self.assertIn('view->auto_enroll_attempted=FALSE;',UI_MUSIC)
        self.assertIn('music_auto_enroll(view);',UI_MUSIC)
        self.assertIn('This device already has Music playback access.',UI_MUSIC)

    def test_standard_album_grid_preserves_track_list_and_limits_art_fetches(self):
        self.assertIn("gtk_flow_box_new()", UI_MUSIC)
        self.assertIn("gtk_flow_box_insert(GTK_FLOW_BOX(view->cards),card,-1);", UI_MUSIC)
        self.assertIn("gtk_flow_box_set_max_children_per_line", UI_MUSIC)
        self.assertIn("gtk_widget_set_name(card,\"music-card\")", UI_MUSIC)
        self.assertIn("music_card_art_start(view,cover,art);", UI_MUSIC)
        self.assertIn("view->card_art_count>=16", UI_MUSIC)
        self.assertIn("job->serial==", UI_MUSIC)
        self.assertIn("view->card_art_serial", UI_MUSIC)
        self.assertIn("gtk_widget_show(view->cards_scroll);", UI_MUSIC)
        self.assertIn("gtk_widget_show(view->list_scroll);", UI_MUSIC)
        self.assertIn("gtk_widget_set_no_show_all(view->cards_scroll,TRUE)", UI_MUSIC)
        self.assertIn("gtk_list_box_insert(GTK_LIST_BOX(view->list),row,-1)", UI_MUSIC)
        self.assertIn('"#music-card-grid', MAIN)

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
