#ifndef OPTIPLEX_NOW_SERVICE_PROBE_H
#define OPTIPLEX_NOW_SERVICE_PROBE_H

#include <gio/gio.h>

#define NOW_SERVICE_PROBE_COUNT 3
#define NOW_SERVICE_PROBE_URL_MAX 512
#define NOW_SERVICE_PROBE_STATE_MAX 48

typedef struct NowServiceProbe NowServiceProbe;

typedef struct {
    char state[NOW_SERVICE_PROBE_STATE_MAX];
} NowServiceProbeEntry;

/* Invoked on the caller's GLib main context. Entries and error are borrowed. */
typedef void (*NowServiceProbeCallback)(
    gpointer context, const NowServiceProbeEntry entries[NOW_SERVICE_PROBE_COUNT],
    const GError *error);

NowServiceProbe *now_service_probe_new(NowServiceProbeCallback callback,
                                       gpointer context, guint deadline_ms);

/* Copies and validates URLs before scheduling any request. Empty URLs are
 * valid and reported NOT SET UP. Only one request per wizard is permitted.
 */
gboolean now_service_probe_start(NowServiceProbe *probe,
                                  const char *const urls[NOW_SERVICE_PROBE_COUNT]);
gboolean now_service_probe_busy(const NowServiceProbe *probe);

/* Disconnect callback and cancel any request. Worker reference owns memory
 * until it finishes, so no destroyed GTK widget is retained.
 */
void now_service_probe_close(NowServiceProbe *probe);

#endif
