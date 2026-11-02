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
                           void (*open_settings)(void *, void *));

#endif
