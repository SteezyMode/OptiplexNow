#ifndef OPTIPLEX_NOW_TRAY_MENU_H
#define OPTIPLEX_NOW_TRAY_MENU_H

#include <gtk/gtk.h>
#include "tray_prefs.h"

/* A borrowed, immutable snapshot for one menu build. The app owns callbacks,
 * service permissions, preferences and AppIndicator/status-icon lifecycle.
 * Only GTK presentation belongs here. */
typedef struct {
    unsigned service_mask;
    int service_order[NOW_TRAY_ACTIONS];
    const char *desktop_caption;
    gboolean music_session;
    gboolean music_paused;
    gboolean music_can_next;
    const char *music_caption;
    GCallback on_action;
    GCallback on_music_open_current;
    GCallback on_music_previous;
    GCallback on_music_toggle_pause;
    GCallback on_music_next;
} NowTrayMenuModel;

/* Returns a fully populated/shown GTK menu with an app-owned strong ref.
 * The caller publishes the replacement before releasing the old widget with
 * now_tray_menu_owned_destroy() (see tray_menu_lifetime.h for SNI safety).
 * No host or network I/O; service authority remains with the app. */
GtkWidget *now_tray_menu_new(const NowTrayMenuModel *model);

#endif
