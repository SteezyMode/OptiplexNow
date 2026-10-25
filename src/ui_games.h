#ifndef NOW_UI_GAMES_H
#define NOW_UI_GAMES_H
#include <gtk/gtk.h>
/* Presentation only; owner authorization stays in the existing controller. */
GtkWidget *now_games_page_new(GCallback on_play, GCallback on_settings,
                              GtkWidget **status_label);
#endif
