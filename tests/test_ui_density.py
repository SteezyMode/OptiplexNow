"""Keep user-facing lists dense and page headings nonduplicative.

These are source contracts; the native CI build still compiles the GTK UI.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
MUSIC=(ROOT/"src/ui_music.c").read_text()
MAIN=(ROOT/"src/main.c").read_text()
DOWNLOADS=(ROOT/"src/downloads_flow.c").read_text()
GAMES=(ROOT/"src/ui_games.c").read_text()
SETTINGS=(ROOT/"src/ui_settings.c").read_text()


class DenseLayoutContract(unittest.TestCase):
    def test_song_rows_use_single_line_title_and_inline_metadata(self):
        self.assertIn('gtk_widget_set_name(button,!g_strcmp0(kind,"song")?"music-song-row":"music-row")',MUSIC)
        self.assertIn("is_song?GTK_ORIENTATION_HORIZONTAL",MUSIC)
        self.assertIn("gtk_label_set_single_line_mode(GTK_LABEL(primary),TRUE)",MUSIC)
        self.assertIn('gtk_label_set_max_width_chars(GTK_LABEL(secondary),25)',MUSIC)
        self.assertIn('min-height:30px;',MAIN)
        self.assertIn('button#music-song-action.music-transport',MAIN)
        self.assertNotIn('min-height:62px;',MAIN)

    def test_song_details_valid_through_tooltip(self):
        self.assertIn('gtk_widget_set_tooltip_text(button,tooltip)',MUSIC)
        self.assertLess(MUSIC.index('char *tooltip=g_strdup_printf("%s\\n%s",title,detail);'),
                        MUSIC.index('g_free(detail);',MUSIC.index('char *tooltip=g_strdup_printf')))

    def test_music_page_uses_pinned_sidebar_settings(self):
        self.assertNotIn('gtk_label_new("MUSIC")',MUSIC)
        self.assertIn('gtk_button_set_label(GTK_BUTTON(advanced),"Settings")',MUSIC)
        self.assertIn('gtk_box_pack_end(GTK_BOX(sidebar_rail),advanced,FALSE,FALSE,0)',MUSIC)
        self.assertIn('gtk_box_pack_start(GTK_BOX(sidebar_rail),sidebar_scroll,TRUE,TRUE,0)',MUSIC)

    def test_downloads_has_one_toolbar_and_vpn_is_inline(self):
        self.assertNotIn('gtk_label_new("DOWNLOADS")',DOWNLOADS)
        self.assertIn('GtkWidget *actions_row=toolbar;',DOWNLOADS)
        self.assertIn('gtk_box_pack_end(GTK_BOX(actions_row),vpn_button,FALSE,FALSE,0)',DOWNLOADS)
        self.assertIn('G_CALLBACK(on_refresh_clicked)',DOWNLOADS)

    def test_selected_tabs_replace_redundant_top_level_titles(self):
        self.assertNotIn('gtk_label_new("GAMES")',GAMES)
        self.assertNotIn('add(videos_home,label("VIDEOS","modalheading"),0);',MAIN)
        self.assertNotIn('add(home,label("SETTINGS","modalheading"),0);',SETTINGS)


if __name__ == "__main__":
    unittest.main()
