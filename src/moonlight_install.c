#include "moonlight_install.h"

#include <string.h>

static gboolean run_flatpak(GCancellable *cancel, const char *const argv[],
                            const char *step, GError **error)
{
    if (g_cancellable_set_error_if_cancelled(cancel, error)) {
        return FALSE;
    }
    GSubprocess *process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDOUT_SILENCE | G_SUBPROCESS_FLAGS_STDERR_SILENCE,
        error);
    if (!process) {
        return FALSE;
    }
    gboolean finished = g_subprocess_wait(process, cancel, error);
    if (!finished) {
        /* Cancellation must not leave an installation running behind NOW. */
        g_subprocess_force_exit(process);
        g_subprocess_wait(process, NULL, NULL);
        g_object_unref(process);
        return FALSE;
    }
    gboolean successful = g_subprocess_get_successful(process);
    g_object_unref(process);
    if (!successful) {
        g_set_error(error, G_IO_ERROR, G_IO_ERROR_FAILED,
                    "%s failed. Check Flatpak, network access, and available disk space.",
                    step);
        return FALSE;
    }
    return TRUE;
}

static void moonlight_install_worker(GTask *task, gpointer source, gpointer data,
                                     GCancellable *cancel)
{
    (void)source;
    (void)data;
    const char *const add_remote[] = {
        "flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
        "https://dl.flathub.org/repo/flathub.flatpakrepo", NULL
    };
    const char *const install[] = {
        "flatpak", "install", "--user", "--assumeyes", "--noninteractive",
        "flathub", "com.moonlight_stream.Moonlight", NULL
    };
    GError *error = NULL;
    if (!run_flatpak(cancel, add_remote, "Adding Flathub", &error) ||
        !run_flatpak(cancel, install, "Installing Moonlight", &error)) {
        g_task_return_error(task, error);
        return;
    }
    g_task_return_boolean(task, TRUE);
}

void now_moonlight_install_async(GCancellable *cancel,
                                 GAsyncReadyCallback callback, gpointer data)
{
    GTask *task = g_task_new(NULL, cancel, callback, data);
    g_task_set_source_tag(task, now_moonlight_install_async);
    g_task_run_in_thread(task, moonlight_install_worker);
    g_object_unref(task);
}

gboolean now_moonlight_install_finish(GAsyncResult *result, GError **error)
{
    g_return_val_if_fail(G_IS_TASK(result), FALSE);
    g_return_val_if_fail(g_task_get_source_tag(G_TASK(result)) ==
                         now_moonlight_install_async, FALSE);
    return g_task_propagate_boolean(G_TASK(result), error);
}
