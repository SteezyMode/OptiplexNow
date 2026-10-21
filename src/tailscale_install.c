#include "tailscale_install.h"

static void install_worker(GTask *task, gpointer source_object, gpointer task_data,
                           GCancellable *cancellable)
{
    (void)source_object;
    (void)task_data;

    const char *argv[] = {
        "pkexec", "/usr/bin/python3",
        "/usr/lib/optiplex-now/tailscale-install.py", NULL
    };
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(
        argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_SILENCE,
        &error);
    if (!process) {
        g_task_return_error(task, error);
        return;
    }

    char *output = NULL;
    gboolean completed = g_subprocess_communicate_utf8(
        process, NULL, cancellable, &output, NULL, &error);
    if (!completed) {
        g_subprocess_force_exit(process);
        g_object_unref(process);
        g_free(output);
        g_task_return_error(task, error);
        return;
    }

    const char *message = output ? g_strstrip(output) : "";
    gboolean installed = g_subprocess_get_successful(process) &&
                         (g_strcmp0(message, "INSTALLED") == 0 ||
                          g_strcmp0(message, "ALREADY_INSTALLED") == 0);
    g_object_unref(process);
    g_free(output);
    if (!installed) {
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_FAILED,
                                "Tailscale installation was declined or failed.");
        return;
    }
    g_task_return_boolean(task, TRUE);
}

void now_tailscale_install_async(GAsyncReadyCallback callback, gpointer data)
{
    GTask *task = g_task_new(NULL, NULL, callback, data);
    g_task_set_source_tag(task, now_tailscale_install_async);
    g_task_run_in_thread(task, install_worker);
    g_object_unref(task);
}

gboolean now_tailscale_install_finish(GAsyncResult *result, GError **error)
{
    g_return_val_if_fail(G_IS_TASK(result), FALSE);
    g_return_val_if_fail(g_task_get_source_tag(G_TASK(result)) ==
                         now_tailscale_install_async, FALSE);
    return g_task_propagate_boolean(G_TASK(result), error);
}
