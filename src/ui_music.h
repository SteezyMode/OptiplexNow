#ifndef NOW_UI_MUSIC_H
#define NOW_UI_MUSIC_H

#include <gtk/gtk.h>

/* Optional user-only library browser. No music service is required by Alpha 1.
 * It uses a dedicated per-user OpenSubsonic app password, remembered in
 * the user's OS Secret Service after one successful connection and loaded
 * automatically on later runs. Live API requests use stdin only.
 * No slskd/admin credentials are ever needed by this widget.
 */
GtkWidget *now_music_build(void (*open_url)(const char *),
                           void (*open_settings)(void *, void *),
                           void (*tray_changed)(void));

/* Existing NOW tray actions remain intact; these are an ephemeral,
 * single-client-local subsection only when Music owns a live session. */
gboolean now_music_is_playing_session(void);
gboolean now_music_is_paused(void);
gboolean now_music_can_next(void);
const char *now_music_caption(void);
void now_music_previous(void);
void now_music_toggle_pause(void);
void now_music_next(void);

#endif
