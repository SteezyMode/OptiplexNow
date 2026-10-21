#ifndef OPTIPLEX_NOW_MOONLIGHT_INSTALL_H
#define OPTIPLEX_NOW_MOONLIGHT_INSTALL_H

#include <gio/gio.h>

/* Only installs com.moonlight_stream.Moonlight to the current user's
 * Flatpak installation, after explicit GUI confirmation.
 * Caller owns the cancellable until the completion callback.
 */
void now_moonlight_install_async(GCancellable *cancel,
                                 GAsyncReadyCallback callback, gpointer data);
gboolean now_moonlight_install_finish(GAsyncResult *result, GError **error);

#endif
