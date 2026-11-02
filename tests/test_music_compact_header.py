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
        self.assertIn('gtk_scrolled_window_set_min_content_width(GTK_SCROLLED_WINDOW(sidebar_scroll),172)',UI)
        self.assertIn('gtk_widget_set_name(sidebar_rail,"music-sidebar-rail")',UI)
        self.assertIn('"#music-sidebar-rail {background:#1b241e',CSS)
        self.assertIn('"#music-sidebar {background:transparent',CSS)
        self.assertIn('gtk_box_pack_end(GTK_BOX(sidebar_rail),advanced,FALSE,FALSE,0)',UI)
        self.assertIn('GtkWidget *filter=music_button(filter_labels[i])',UI)
        self.assertIn('music_align_nav_label(filter)',UI)
        self.assertNotIn('folder-music-symbolic',UI)
        self.assertNotIn('GtkWidget *b=music_button(titles[i])',UI)
        self.assertIn('"#music-library-filters button#music-filter.now-action',CSS)
        self.assertIn('"#music-sidebar button#music-library-root.now-action',CSS)

    def test_compact_album_and_song_chrome(self):
        self.assertIn('gtk_widget_set_size_request(view->hero_art,96,96)',UI)
        self.assertIn('min-height:30px',CSS)
        self.assertIn('button#music-song-row #music-row-title {font-size:13px',CSS)
        self.assertIn('button#music-song-action.music-transport',CSS)
        self.assertNotIn('min-height:62px',CSS)


if __name__=="__main__":
    unittest.main()
