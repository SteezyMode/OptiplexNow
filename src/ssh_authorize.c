#include "ssh_authorize.h"

#include <signal.h>
#include <string.h>

typedef struct {
    char *host;
    char *user;
} SSHRequest;

static void ssh_request_free(gpointer data)
{
    SSHRequest *request = data;
    g_free(request->host);
    g_free(request->user);
    g_free(request);
}

static void ssh_authorize_worker(GTask *task, gpointer source, gpointer data,
                                  GCancellable *cancel)
{
    (void)source;
    SSHRequest *request = data;
    if (g_task_return_error_if_cancelled(task)) {
        return;
    }
    const char *argv[] = {
        "/usr/bin/python3", "/usr/lib/optiplex-now/ssh-authorize.py",
        request->host, request->user, NULL
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
        process, NULL, cancel, &output, NULL, &error);
    if (!completed) {
        /* SIGTERM is handled by Python and forwarded to its SSH process group.
         * Do not leave ssh-copy-id or a credential prompt running after cancel. */
        g_subprocess_send_signal(process, SIGTERM);
        g_subprocess_wait(process, NULL, NULL);
        g_object_unref(process);
        g_free(output);
        g_task_return_error(task, error);
        return;
    }

    gboolean success = g_subprocess_get_successful(process) &&
                       g_strcmp0(g_strstrip(output ? output : ""), "AUTHORIZED") == 0;
    g_object_unref(process);
    g_free(output);
    if (!success) {
        g_task_return_new_error(
            task, G_IO_ERROR, G_IO_ERROR_FAILED,
            "The SSH key was not authorized. Check the host, password, and SSH permissions.");
        return;
    }
    g_task_return_boolean(task, TRUE);
}

void now_ssh_authorize_async(const char *host, const char *user,
                             GCancellable *cancel, GAsyncReadyCallback callback,
                             gpointer data)
{
    GTask *task = g_task_new(NULL, cancel, callback, data);
    g_task_set_source_tag(task, now_ssh_authorize_async);
    if (!host || !*host || !user || !*user) {
        g_task_return_new_error(task, G_IO_ERROR, G_IO_ERROR_INVALID_ARGUMENT,
                                "Enter a server and SSH account first.");
    } else {
        SSHRequest *request = g_new0(SSHRequest, 1);
        request->host = g_strdup(host);
        request->user = g_strdup(user);
        g_task_set_task_data(task, request, ssh_request_free);
        g_task_run_in_thread(task, ssh_authorize_worker);
    }
    g_object_unref(task);
}

gboolean now_ssh_authorize_finish(GAsyncResult *result, GError **error)
{
    g_return_val_if_fail(G_IS_TASK(result), FALSE);
    g_return_val_if_fail(g_task_get_source_tag(G_TASK(result)) ==
                         now_ssh_authorize_async, FALSE);
    return g_task_propagate_boolean(G_TASK(result), error);
}
