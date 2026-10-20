#ifndef OPTIPLEX_NOW_WOLF_TRANSPORT_H
#define OPTIPLEX_NOW_WOLF_TRANSPORT_H

#include <gio/gio.h>

/*
 * Run the existing trusted SSH bridge off the GTK main thread.
 * Callback runs on the calling thread's GMainContext.
 * Cancellation discards the response and requests child-process termination;
 * it cannot revoke an authorization already accepted by the host.
 */
void now_wolf_request_async(const char *script, const char *action,
                            const char *host, const char *user,
                            const char *payload, GCancellable *cancellable,
                            GAsyncReadyCallback callback, gpointer user_data);

/* Caller owns the returned UTF-8 text and must g_free it. NULL means failure. */
char *now_wolf_request_finish(GAsyncResult *result, GError **error);

#endif
