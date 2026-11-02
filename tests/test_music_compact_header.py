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
        self.assertIn('G_CALLBACK(music_focus_search)',UI)
        self.assertIn('music_show_search(view,TRUE)',UI)

    def test_compact_album_and_song_chrome(self):
        self.assertIn('gtk_widget_set_size_request(view->hero_art,96,96)',UI)
        self.assertIn('min-height:30px',CSS)
        self.assertIn('button#music-song-row #music-row-title {font-size:13px',CSS)
        self.assertIn('button#music-song-action.music-transport',CSS)
        self.assertNotIn('min-height:62px',CSS)


if __name__=="__main__":
    unittest.main()
