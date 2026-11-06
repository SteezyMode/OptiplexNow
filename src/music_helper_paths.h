#ifndef OPTIPLEX_NOW_MUSIC_HELPER_PATHS_H
#define OPTIPLEX_NOW_MUSIC_HELPER_PATHS_H

#include <glib.h>

/* Only trusted, built-in helper types; never accept file names from Music
 * search results, servers, device enrollment or user-provided form fields. */
typedef enum {
    NOW_MUSIC_HELPER_PLAYER = 1,
    NOW_MUSIC_HELPER_SUBSONIC = 2,
} NowMusicHelperKind;

/* Caller owns the returned gchar*. NULL only for unsupported kind. */
char *now_music_helper_path(NowMusicHelperKind kind);

/* Pure policy seam for offline tests; not used for external input.
 * The production wrapper checks /proc/self/exe and the checkout itself. */
char *now_music_helper_path_for_executable(NowMusicHelperKind kind,
                                           const char *executable,
                                           gboolean checkout_has_helper);
#endif
