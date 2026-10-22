#ifndef OPTIPLEX_NOW_GAMES_FLOW_H
#define OPTIPLEX_NOW_GAMES_FLOW_H

#include <gio/gio.h>

/* Narrow device-key Games response, not a raw SSH/Wolf protocol. */
typedef enum {
    NOW_GAMES_NEEDS_WOLF_UI,
    NOW_GAMES_WOLF_UI_CONNECTED,
    NOW_GAMES_BUSY,
    NOW_GAMES_IN_USE,
    NOW_GAMES_JOINED,
    NOW_GAMES_IDLE,
    NOW_GAMES_RUNNING,
    NOW_GAMES_FINISHED
} NowGamesReply;

/* Invoke only the installed, fixed Python Games helper off the GTK thread.
 * No ssh arguments, profiles, PINs, paths or device IDs come from GTK.
 * The helper itself uses a separate restricted Ed25519 key, never admin SSH.
 */
void now_games_request_async(const char *script, const char *action,
                             const char *host, const char *user,
                             GCancellable *cancellable,
                             GAsyncReadyCallback callback, gpointer user_data);
gboolean now_games_request_finish(GAsyncResult *result, NowGamesReply *reply,
                                  GError **error);

/* Prefer the packaged helper beside a rootlessly extracted usr/bin executable;
 * use /usr/lib for a normal OS installation. Caller frees returned path.
 */
char *now_games_helper_for_executable(const char *executable_path);

/* Safe, exact finite-state parser for the helper's private UI text mode. */
gboolean now_games_parse_reply(const char *line, NowGamesReply *reply);

#endif
