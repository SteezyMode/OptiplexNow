#ifndef OPTIPLEX_NOW_TAILSCALE_ASYNC_H
#define OPTIPLEX_NOW_TAILSCALE_ASYNC_H

#include <gio/gio.h>
#include <stddef.h>

#define NOW_TAILSCALE_MAX_SERVERS 200

typedef struct {
    char address[128];
    char label[256];
} NowTailscaleServer;

/* A helper request never runs on GTK's main thread. Only fixed, bundled
 * helper paths should be supplied by production callers. The result is
 * allocated UTF-8 text; callers free it with g_free().
 */
void now_tailscale_run_async(const char *helper, GCancellable *cancellable,
                            GAsyncReadyCallback callback, gpointer user_data);
char *now_tailscale_run_finish(GAsyncResult *result, GError **error);

/* Parsed output is an untrusted list from find-servers.py, not authorization. */
int now_tailscale_parse_servers(const char *output, NowTailscaleServer *servers,
                               size_t capacity);

#endif
