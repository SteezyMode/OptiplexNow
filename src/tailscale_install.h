#ifndef OPTIPLEX_NOW_TAILSCALE_INSTALL_H
#define OPTIPLEX_NOW_TAILSCALE_INSTALL_H

#include <gio/gio.h>

/* Invokes only the installed, root-owned Tailscale installer via PolicyKit.
 * Never executes arbitrary scripts, shells or remotely provided arguments.
 */
void now_tailscale_install_async(GAsyncReadyCallback callback, gpointer data);
gboolean now_tailscale_install_finish(GAsyncResult *result, GError **error);

#endif
