#ifndef NOW_DESKTOP_AUTOSTART_H
#define NOW_DESKTOP_AUTOSTART_H
#include <glib.h>

/* XDG per-user login startup; never edits the system launcher or starts a
 * service. Return FALSE for an unsafe or unrecognized existing entry. */
gboolean now_desktop_autostart_get(gboolean *enabled);
gboolean now_desktop_autostart_set(gboolean enabled);
#endif
