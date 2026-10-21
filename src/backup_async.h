#ifndef OPTIPLEX_NOW_BACKUP_ASYNC_H
#define OPTIPLEX_NOW_BACKUP_ASYNC_H

#include <gio/gio.h>

/* Invoke the unchanged encrypted-backup helper without blocking GTK.
 * The passphrase is copied into short-lived memory, delivered only on
 * standard input, then explicitly erased. No shell, argv or environment
 * variable ever contains it.
 *
 * Restore is intentionally not cancellable: the v1 backup helper writes
 * several identity files and killing it mid-restore can leave partial state.
 * The caller must display modal progress and keep the app running.
 */
void now_backup_run_async(const char *helper, gboolean restore, const char *path,
                          const char *password, GAsyncReadyCallback callback,
                          gpointer user_data);

gboolean now_backup_run_finish(GAsyncResult *result, GError **error);

#endif
