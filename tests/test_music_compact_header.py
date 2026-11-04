"""The Music library header must not consume three permanent rows."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"src/ui_music.c").read_text(encoding="utf-8")
CSS=(ROOT/"src/main.c").read_text(encoding="utf-8")


class CompactMusicHeaderTests(unittest.TestCase):
    def test_search_is_hidden_until_icon_is_clicked(self):
        self.assertIn('view->search_toggle=music_icon_button("system-search-symbolic","Search music")',UI)
        self.assertIn('gtk_stack_add_named(GTK_STACK(view->header_stack),view->search,"search")',UI)
        self.assertIn('gtk_stack_set_visible_child_name(GTK_STACK(view->header_stack),"browse")',UI)
        self.assertIn('G_CALLBACK(music_toggle_search)',UI)
        self.assertIn('G_CALLBACK(music_search_escape)',UI)
        self.assertIn('GTK_STACK_TRANSITION_TYPE_NONE',UI)
        self.assertIn('gtk_widget_grab_focus(view->search)',UI)
        self.assertNotIn('music_button("Search")',UI)
        self.assertNotIn('GtkWidget *searchrow=gtk_box_new(',UI)

    def test_shuffle_and_song_count_share_header_row(self):
        self.assertIn('GtkWidget *header_row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,4)',UI)
        self.assertIn('gtk_box_pack_start(GTK_BOX(browse_header),view->heading,TRUE,TRUE,0)',UI)
        self.assertIn('gtk_box_pack_end(GTK_BOX(browse_header),view->shuffle_all,FALSE,FALSE,0)',UI)
        self.assertIn('gtk_box_pack_end(GTK_BOX(header_row),view->search_toggle,FALSE,FALSE,0)',UI)
        self.assertNotIn('gtk_box_pack_start(GTK_BOX(maincol),view->shuffle_all',UI)
        self.assertIn('g_strdup_printf("%s · %d %s",job->heading,',UI)
        self.assertIn('char *heading=partial?g_strdup(job->heading):',UI)
        self.assertIn('view->song_has_more',UI)
        self.assertIn('gtk_widget_set_no_show_all(view->shuffle_all,TRUE)',UI)

    def test_existing_search_and_song_interactions_stay_wired(self):
        self.assertIn('g_signal_connect(view->search,"activate",G_CALLBACK(music_search),view)',UI)
        self.assertIn('query_start(view,connected?"search":"catalog",value,',UI)
        self.assertIn('G_CALLBACK(music_shuffle_all)',UI)
        self.assertIn('G_CALLBACK(music_library_clicked)',UI)
        self.assertIn('music_show_search(view,g_strcmp0(page,"search")!=0)',UI)

    def test_library_sidebar_collapses_without_losing_song_navigation(self):
        self.assertIn('gtk_label_new("Your Library")',UI)
        self.assertIn('gtk_widget_set_name(library_button,"music-library-root")',UI)
        self.assertIn('music_library_expand(view,!was_open)',UI)
        self.assertIn('query_start(view,"songs",NULL,"All songs")',UI)
        self.assertIn('gtk_revealer_set_reveal_child(GTK_REVEALER(view->library_revealer),expanded)',UI)
        self.assertIn('music_library_expand(view,FALSE)',UI)
        self.assertIn('gtk_widget_set_size_request(sidebar_rail,172,-1)',UI)
        self.assertIn('gtk_scrolled_window_set_min_content_width(GTK_SCROLLED_WINDOW(sidebar_scroll),162)',UI)
        self.assertIn('gtk_widget_set_name(sidebar_rail,"music-sidebar-rail")',UI)
        self.assertIn('"#music-sidebar-rail {background:#181b19',CSS)
        self.assertIn('"#music-sidebar {background:transparent',CSS)
        self.assertIn('gtk_box_pack_end(GTK_BOX(sidebar_rail),advanced,FALSE,FALSE,0)',UI)
        self.assertIn('GtkWidget *filter=music_button(filter_labels[i])',UI)
        self.assertIn('music_align_nav_label(filter)',UI)
        self.assertNotIn('folder-music-symbolic',UI)
        self.assertNotIn('GtkWidget *b=music_button(titles[i])',UI)
        self.assertIn('"#music-library-filters button#music-filter.now-action',CSS)
        self.assertIn('"#music-sidebar button#music-library-root.now-action',CSS)

    def test_wide_window_expands_library_not_sidebar(self):
        self.assertIn('gtk_widget_set_halign(view->root,GTK_ALIGN_FILL)',UI)
        self.assertIn('gtk_widget_set_hexpand(view->root,TRUE)',UI)
        self.assertIn('gtk_widget_set_halign(content,GTK_ALIGN_FILL)',UI)
        self.assertIn('gtk_widget_set_hexpand(content,TRUE)',UI)
        self.assertIn('gtk_box_pack_start(GTK_BOX(content),sidebar_rail,FALSE,FALSE,0)',UI)
        self.assertIn('gtk_widget_set_hexpand(sidebar_rail,FALSE)',UI)
        self.assertIn('gtk_widget_set_halign(sidebar_rail,GTK_ALIGN_START)',UI)
        self.assertIn('gtk_widget_set_halign(maincol,GTK_ALIGN_FILL)',UI)
        self.assertIn('gtk_widget_set_hexpand(maincol,TRUE)',UI)
        self.assertIn('gtk_box_pack_start(GTK_BOX(content),maincol,TRUE,TRUE,0)',UI)

    def test_music_palette_matches_application_not_separate_green_theme(self):
        start=CSS.index('"#music-home {')
        end=CSS.index('"button.now-action {',start)
        section=CSS[start:end]
        self.assertIn('"#music-home {background:#101111;color:#ece8e0;}"',section)
        self.assertIn('"#music-sidebar-rail {background:#181b19',section)
        self.assertIn('#c47d65',section)
        for old in ('#111613','#1b241e','#304036','#314438',
                    '#1a221c','#253329','#35473a','#202c24'):
            self.assertNotIn(old,section)

    def test_tray_current_song_activates_music_and_restores_window(self):
        a=CSS.index("static void tray_music_open_current(")
        b=CSS.index("static guint music_tray_rebuild_pending",a)
        callback=CSS[a:b]
        self.assertIn("if(!now_music_is_playing_session())return;",callback)
        self.assertIn("on_music_tab(NULL,NULL);",callback)
        self.assertIn("tray_show_window();",callback)
        self.assertNotIn("now_music_next()",callback)
        self.assertNotIn("now_music_toggle_pause()",callback)
        self.assertIn('g_signal_connect(playing,"activate",G_CALLBACK(tray_music_open_current),NULL)',CSS)
        self.assertIn('gtk_widget_set_tooltip_text(playing,caption)',CSS)
        self.assertNotIn("gtk_widget_set_sensitive(playing,FALSE)",CSS)

    def test_compact_now_playing_with_one_line_title(self):
        a=UI.index("GtkWidget *track_info=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,4)")
        b=UI.index("gtk_box_pack_start(GTK_BOX(player_line),track_info,TRUE,TRUE,0)",a)
        c=UI.index("gtk_box_pack_end(GTK_BOX(player_line),controls,FALSE,FALSE,0)",b)
        self.assertLess(b,c)
        self.assertIn("gtk_widget_set_size_request(view->playing_art,34,34)",UI)
        self.assertIn("gtk_box_pack_start(GTK_BOX(track_info),now_playing,TRUE,TRUE,0)",UI)
        self.assertIn("gtk_widget_set_size_request(now_playing,0,-1)",UI)
        self.assertIn("gtk_label_set_line_wrap(GTK_LABEL(view->playing_label),FALSE)",UI)
        self.assertIn("gtk_label_set_lines(GTK_LABEL(view->playing_label),1)",UI)
        self.assertIn("gtk_widget_set_tooltip_text(view->playing_label,",UI)
        self.assertNotIn("gtk_box_pack_start(GTK_BOX(controls),now_playing",UI)

    def test_album_actions_are_small_icons_with_defined_queue_semantics(self):
        self.assertIn("gtk_widget_set_size_request(view->hero_art,52,52)",UI)
        self.assertIn("job->playing?34:52",UI)
        self.assertIn("gtk_label_set_lines(GTK_LABEL(view->hero_title),2)",UI)
        self.assertIn("gtk_widget_set_size_request(header_text,0,-1)",UI)
        self.assertIn('music_icon_button("media-playback-start-symbolic",',UI)
        self.assertIn('"Play album from the beginning"',UI)
        self.assertIn('music_icon_button("media-playlist-shuffle-symbolic",',UI)
        self.assertIn('"Shuffle this album"',UI)
        self.assertIn("gtk_box_pack_start(GTK_BOX(album_actions),view->hero_play,FALSE,FALSE,0)",UI)
        self.assertIn("gtk_box_pack_start(GTK_BOX(album_actions),view->hero_shuffle,FALSE,FALSE,0)",UI)
        self.assertIn("gtk_box_pack_start(GTK_BOX(album_actions),view->hero_like,FALSE,FALSE,0)",UI)
        self.assertIn("gtk_widget_set_size_request(view->hero_shuffle,28,28)",UI)
        self.assertIn("gtk_widget_set_size_request(view->hero_play,28,28)",UI)
        self.assertIn("gtk_widget_set_tooltip_text(view->hero_title,title)",UI)
        self.assertIn("gtk_widget_set_sensitive(view->hero_shuffle,",UI)
        self.assertIn("g_random_int_range(0,(int)view->visible_tracks->len)",UI)
        self.assertIn("music_play_visible(view,first);",UI)
        self.assertIn("music_play_visible(view,0);",UI)
        self.assertIn("gtk_box_pack_end(GTK_BOX(view->hero_row),album_actions,FALSE,FALSE,0)",UI)
        self.assertNotIn("gtk_box_pack_start(GTK_BOX(header_text),album_actions",UI)
        self.assertNotIn("gtk_box_pack_end(GTK_BOX(view->hero_row),view->hero_play",UI)
        self.assertNotIn('music_button("Play album")',UI)

    def test_compact_album_and_song_chrome(self):
        self.assertIn('gtk_widget_set_size_request(view->hero_art,52,52)',UI)
        self.assertIn('min-height:25px',CSS)
        self.assertIn('button#music-song-row #music-row-title {font-size:13px',CSS)
        self.assertIn('button#music-song-action.music-transport',CSS)
        self.assertNotIn('min-height:62px',CSS)

    def test_liked_songs_keep_the_same_heart_icon_in_both_states(self):
        self.assertIn('static GtkWidget *music_heart_image(gboolean liked)',UI)
        self.assertIn('gtk_widget_set_opacity(image,liked?1.0:0.40)',UI)
        self.assertIn('music_heart_button(FALSE,"Like current song")',UI)
        self.assertIn('music_heart_button(FALSE,"Like this album")',UI)
        self.assertIn('GtkWidget *like=music_heart_button(liked,',UI)
        self.assertNotIn('"non-starred-symbolic"',UI)
        self.assertIn('G_CALLBACK(music_playlist_clicked)',UI)

    def test_album_and_artist_hearts_use_typed_operations(self):
        self.assertIn('liked?"unlike_album":"like_album"',UI)
        self.assertIn('liked?"unlike_artist":"like_artist"',UI)
        self.assertIn('liked?"unlike":"like"',UI)
        self.assertIn('g_str_has_prefix(job->operation,"like")',UI)
        self.assertIn('g_strcmp0(job->kind,"album") && g_strcmp0(job->kind,"artist")',UI)
        self.assertIn('liked?"Unlike album":"Like album"',UI)
        self.assertIn('liked?"Unlike artist":"Like artist"',UI)

    def test_now_playing_can_add_current_song_to_existing_or_new_playlist(self):
        self.assertIn("*playing_add, *pause_button",UI)
        self.assertIn('music_icon_button("list-add-symbolic","Add current song to playlist")',UI)
        self.assertIn('gtk_widget_set_name(view->playing_add,"music-playing-add")',UI)
        self.assertIn('G_CALLBACK(music_playlist_clicked),view->playing_add',UI)
        self.assertIn('gtk_box_pack_start(GTK_BOX(track_info),view->playing_add,FALSE,FALSE,0)',UI)
        self.assertIn('g_strdup(current?current->id:"")',UI)
        self.assertIn('gtk_widget_set_sensitive(view->playing_add,current!=NULL)',UI)
        self.assertIn('button#music-playing-add.music-transport',CSS)
        self.assertIn('button#music-playing-like.music-transport',CSS)

    def test_single_horizontal_player_line_with_thin_seek_below(self):
        self.assertIn('view->player_bar=gtk_box_new(GTK_ORIENTATION_VERTICAL,0)',UI)
        self.assertIn('gtk_container_set_border_width(GTK_CONTAINER(view->player_bar),2)',UI)
        self.assertIn('GtkWidget *player_line=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,3)',UI)
        self.assertIn('gtk_box_pack_start(GTK_BOX(player_line),track_info,TRUE,TRUE,0)',UI)
        self.assertIn('gtk_box_pack_end(GTK_BOX(player_line),controls,FALSE,FALSE,0)',UI)
        self.assertIn('gtk_box_pack_start(GTK_BOX(view->player_bar),player_line,FALSE,FALSE,0)',UI)
        self.assertIn('gtk_box_pack_start(GTK_BOX(view->player_bar),timeline,FALSE,FALSE,0)',UI)
        self.assertIn('gtk_widget_set_hexpand(timeline,TRUE)',UI)
        self.assertNotIn('gtk_box_pack_start(GTK_BOX(view->player_bar),controls',UI)
        self.assertIn('gtk_widget_set_size_request(view->pause_button,32,32)',UI)
        self.assertIn('gtk_widget_set_size_request(view->previous_button,28,28)',UI)
        self.assertIn('gtk_widget_set_size_request(view->next_button,28,28)',UI)
        self.assertIn('gtk_widget_set_size_request(view->playing_art,34,34)',UI)
        self.assertIn('gtk_widget_set_size_request(view->volume_slider,52,-1)',UI)
        self.assertIn('border-top:1px solid #414743;border-radius:0;padding:2px 3px;',CSS)
        self.assertIn('min-height:32px;min-width:32px;',CSS)
        self.assertIn('view->seek_caption=gtk_label_new("0:00 / 0:00")',UI)

    def test_song_action_feedback_never_occupies_track_viewport(self):
        self.assertNotIn('status_set(view,"Song added to playlist.")',UI)
        self.assertNotIn('Added to Liked Songs.',UI)
        self.assertNotIn('Removed from Liked Songs.',UI)
        self.assertNotIn('status_set(view,"Album requested.',UI)
        self.assertIn('gtk_button_set_label(GTK_BUTTON(job->button),"Requested")',UI)
        self.assertIn('status_set(view,"Could not update Music library. Try again.")',UI)

    def test_flat_song_rows_use_space_for_songs_not_cards(self):
        self.assertIn('gtk_widget_set_size_request(like,24,24)',UI)
        self.assertIn('gtk_widget_set_size_request(add,24,24)',UI)
        self.assertIn('border-radius:0;padding:1px 4px;min-height:25px',CSS)
        self.assertIn('background:transparent;border-bottom:1px solid #363d39',CSS)


if __name__=="__main__":
    unittest.main()
