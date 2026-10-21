#ifndef OPTIPLEX_NOW_SSH_AUTHORIZE_H
#define OPTIPLEX_NOW_SSH_AUTHORIZE_H

#include <gio/gio.h>

/* Use a worker for one explicitly approved SSH public-key installation.
 * User/password/fingerprint entry belongs to independent GTK askpass windows.
 */
void now_ssh_authorize_async(const char *host, const char *user,
                             GCancellable *cancel, GAsyncReadyCallback callback,
                             gpointer data);
gboolean now_ssh_authorize_finish(GAsyncResult *result, GError **error);

#endif
